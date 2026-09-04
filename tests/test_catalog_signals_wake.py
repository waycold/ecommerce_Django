"""
tests/test_catalog_signals_wake.py

Regression coverage for apps.catalog.signals.queue_embedding_sync: when the
best-effort "wake" ping to the Chatbot-Engine-Gateway fails (timeout,
connection refused, DNS failure, unexpected 5xx -- anything), the failure
must be logged (it previously vanished into a bare `except Exception: pass`
with zero observability), and saving the Item must still succeed without
raising or hanging regardless of the outcome of that ping.

The EmbeddingSyncTask row itself (the actual outbox record the Gateway's
polling cycle depends on) must also still be created even when the wake
ping fails -- the ping is a pure optimization on top of it.
"""
import logging

import httpx
import pytest
from django.test import override_settings

from apps.catalog.models import EmbeddingSyncTask, Item


@override_settings(AI_AGENT_GATEWAY_URL="http://gateway.invalid")
def test_wake_failure_is_logged_as_warning(db, django_capture_on_commit_callbacks, caplog):
    """A Gateway wake ping that raises must produce a visible warning log,
    not silence the exception."""
    with caplog.at_level(logging.WARNING, logger="apps.catalog.signals"):
        with django_capture_on_commit_callbacks(execute=True):
            Item.objects.create(
                title="Wireless Keyboard",
                description="Compact mechanical keyboard",
                price=50,
                cost=20,
                stock=3,
            )

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "expected a warning log record for the failed wake ping"
    message = warnings[0].getMessage()
    assert "wake" in message.lower()
    assert "Gateway" in message
    # exc_info=True must be attached so the actual exception (connection
    # error, timeout, whatever) is visible to whoever reads the logs.
    assert warnings[0].exc_info is not None


def test_item_save_does_not_raise_when_wake_ping_fails(db, monkeypatch, django_capture_on_commit_callbacks):
    """Creating/editing a product must never fail because the Gateway is
    unreachable -- the wake ping is best-effort only."""

    def _boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", _boom)

    with django_capture_on_commit_callbacks(execute=True):
        item = Item.objects.create(
            title="Gaming Mouse",
            description="High DPI optical sensor",
            price=30,
            cost=10,
            stock=7,
        )

    # The save completed and the outbox row was still created despite the
    # wake ping raising inside the on_commit callback.
    assert item.pk is not None
    assert EmbeddingSyncTask.objects.filter(item=item).exists()


def test_item_save_does_not_raise_on_slow_unreachable_gateway(db, monkeypatch, django_capture_on_commit_callbacks, caplog):
    """Simulates a hanging/unreachable Gateway (httpx raises its own timeout
    exception) and confirms the save still completes and the failure is
    logged -- this is the scenario the reduced WAKE_TIMEOUT_SECONDS bounds
    in production."""

    def _timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", _timeout)

    with caplog.at_level(logging.WARNING, logger="apps.catalog.signals"):
        with django_capture_on_commit_callbacks(execute=True):
            item = Item.objects.create(
                title="USB-C Hub",
                description="Multiport adapter",
                price=25,
                cost=8,
                stock=15,
            )

    assert item.pk is not None
    assert EmbeddingSyncTask.objects.filter(item=item).exists()
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@override_settings(AI_AGENT_GATEWAY_URL="http://gateway.invalid")
def test_irrelevant_field_update_does_not_trigger_wake_or_log(db, django_capture_on_commit_callbacks, caplog):
    """A save whose update_fields don't touch the embedded text should skip
    the whole _enqueue closure -- no task, no wake attempt, no log noise."""
    item = Item.objects.create(
        title="Desk Lamp",
        description="LED lamp",
        price=15,
        cost=5,
        stock=20,
    )
    EmbeddingSyncTask.objects.all().delete()
    caplog.clear()

    with caplog.at_level(logging.WARNING, logger="apps.catalog.signals"):
        with django_capture_on_commit_callbacks(execute=True):
            item.stock = 19
            item.save(update_fields=["stock"])

    assert not EmbeddingSyncTask.objects.filter(item=item).exists()
    assert not any(r.levelno == logging.WARNING for r in caplog.records)
