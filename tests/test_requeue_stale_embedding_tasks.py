"""
tests/test_requeue_stale_embedding_tasks.py

Fase 3, Tarea 2: apps/catalog/rag_service.py::get_pending_embedding_tasks_service
only ever claims EmbeddingSyncTask rows in PENDING -- if the Gateway crashes
mid-batch, a task it claimed (flipped to PROCESSING) is never picked up
again by anything. This covers the reaper management command
(requeue_stale_embedding_tasks) that reverts stale PROCESSING tasks back to
PENDING, plus the end-to-end loop: requeue -> re-claimed by
get_pending_embedding_tasks_service -> completed via
POST /api/v1/internal/catalog/embeddings/upsert/ (now CSRF-exempt per Fase 0,
Tarea 4, so the reencolada task can actually finish this time instead of
403-ing again).
"""

import json

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Category, EMBEDDING_DIM, EmbeddingSyncTask, Item
from apps.catalog.rag_service import get_pending_embedding_tasks_service


def _make_item(title="Test Item"):
    category = Category.objects.get_or_create(name="Electronics")[0]
    return Item.objects.create(title=title, price=10, stock=5, category=category)


def _make_task(item, status, updated_at, content_hash="abc123"):
    """Creates an EmbeddingSyncTask then force-sets updated_at via .update(),
    since auto_now on save()/create() would otherwise stamp "now" regardless
    of what's passed in."""
    task = EmbeddingSyncTask.objects.create(item=item, status=status, content_hash=content_hash)
    EmbeddingSyncTask.objects.filter(pk=task.pk).update(updated_at=updated_at)
    task.refresh_from_db()
    return task


@pytest.mark.django_db
class TestRequeueStaleEmbeddingTasksCommand:
    def test_reverts_only_stale_processing_task(self, capsys):
        item = _make_item()
        now = timezone.now()

        stale_processing = _make_task(
            item, EmbeddingSyncTask.Status.PROCESSING, now - timezone.timedelta(minutes=45)
        )
        fresh_processing = _make_task(
            item, EmbeddingSyncTask.Status.PROCESSING, now - timezone.timedelta(minutes=5)
        )
        already_pending = _make_task(
            item, EmbeddingSyncTask.Status.PENDING, now - timezone.timedelta(minutes=90)
        )

        call_command("requeue_stale_embedding_tasks", "--minutes", "30")

        stale_processing.refresh_from_db()
        fresh_processing.refresh_from_db()
        already_pending.refresh_from_db()

        assert stale_processing.status == EmbeddingSyncTask.Status.PENDING
        assert fresh_processing.status == EmbeddingSyncTask.Status.PROCESSING
        assert already_pending.status == EmbeddingSyncTask.Status.PENDING

        output = capsys.readouterr().out
        assert "Requeued 1 stale PROCESSING task" in output

    def test_default_threshold_is_30_minutes(self, capsys):
        item = _make_item()
        now = timezone.now()

        just_under_default = _make_task(
            item, EmbeddingSyncTask.Status.PROCESSING, now - timezone.timedelta(minutes=20)
        )
        past_default = _make_task(
            item, EmbeddingSyncTask.Status.PROCESSING, now - timezone.timedelta(minutes=31)
        )

        call_command("requeue_stale_embedding_tasks")

        just_under_default.refresh_from_db()
        past_default.refresh_from_db()

        assert just_under_default.status == EmbeddingSyncTask.Status.PROCESSING
        assert past_default.status == EmbeddingSyncTask.Status.PENDING

        output = capsys.readouterr().out
        assert "Requeued 1 stale PROCESSING task" in output

    def test_no_stale_tasks_reports_zero_and_touches_nothing(self, capsys):
        item = _make_item()
        now = timezone.now()
        fresh = _make_task(item, EmbeddingSyncTask.Status.PROCESSING, now - timezone.timedelta(minutes=1))

        call_command("requeue_stale_embedding_tasks", "--minutes", "30")

        fresh.refresh_from_db()
        assert fresh.status == EmbeddingSyncTask.Status.PROCESSING
        assert "Requeued 0 stale PROCESSING task" in capsys.readouterr().out

    def test_done_and_error_tasks_are_never_touched(self, capsys):
        item = _make_item()
        old = timezone.now() - timezone.timedelta(hours=2)
        done_task = _make_task(item, EmbeddingSyncTask.Status.DONE, old)
        error_task = _make_task(item, EmbeddingSyncTask.Status.ERROR, old)

        call_command("requeue_stale_embedding_tasks", "--minutes", "30")

        done_task.refresh_from_db()
        error_task.refresh_from_db()
        assert done_task.status == EmbeddingSyncTask.Status.DONE
        assert error_task.status == EmbeddingSyncTask.Status.ERROR


@pytest.mark.django_db
class TestRequeuedTaskIsVisibleAgain:
    """Criterio de aceptación: la tarea reencolada a PENDING vuelve a ser
    tomada por get_pending_embedding_tasks_service en el siguiente ciclo --
    ya no queda invisible."""

    def test_requeued_task_is_reclaimed_by_pending_service(self):
        item = _make_item()
        stale = _make_task(
            item,
            EmbeddingSyncTask.Status.PROCESSING,
            timezone.now() - timezone.timedelta(hours=1),
        )

        # Before the reaper runs: invisible to the pending-claim service --
        # this is exactly the "lost forever" bug.
        result, status_code = get_pending_embedding_tasks_service()
        assert status_code == 200
        assert stale.pk not in [t['task_id'] for t in result['tasks']] and result['count'] == 0

        call_command("requeue_stale_embedding_tasks", "--minutes", "30")

        result, status_code = get_pending_embedding_tasks_service()
        assert status_code == 200
        assert result['count'] == 1
        assert result['tasks'][0]['task_id'] == str(stale.pk)

        stale.refresh_from_db()
        assert stale.status == EmbeddingSyncTask.Status.PROCESSING  # re-claimed atomically


@pytest.mark.django_db
class TestRequeuedTaskCompletesEndToEndAfterCsrfFix:
    """With Fase 0 tarea 4 already deployed (embeddings/upsert and
    embeddings/mark-error no longer 403 under strict CSRF), a task requeued
    by this reaper must be able to actually finish a real Gateway round trip
    instead of just changing status and getting stuck again."""

    def test_requeued_task_completes_via_real_upsert_call(self):
        item = _make_item()
        stale = _make_task(
            item,
            EmbeddingSyncTask.Status.PROCESSING,
            timezone.now() - timezone.timedelta(hours=1),
        )

        call_command("requeue_stale_embedding_tasks", "--minutes", "30")

        # Simulates the Gateway's real poll cycle: claim, then report success.
        claimed, claim_status = get_pending_embedding_tasks_service()
        assert claim_status == 200
        assert claimed['count'] == 1
        task_id = claimed['tasks'][0]['task_id']

        strict_csrf_client = Client(enforce_csrf_checks=True)
        upsert_url = reverse('internal:internal_catalog_embeddings_upsert')

        response = strict_csrf_client.post(
            upsert_url,
            data=json.dumps({
                'item_id': item.id,
                'task_id': task_id,
                'vector': [0.1] * EMBEDDING_DIM,
                'content_hash': 'deadbeef',
            }),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=settings.INTERNAL_API_SECRET,
        )

        assert response.status_code == 200, response.content
        stale.refresh_from_db()
        assert stale.status == EmbeddingSyncTask.Status.DONE
