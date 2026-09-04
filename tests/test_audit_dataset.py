"""
tests/test_audit_dataset.py

Fase 2, Tarea 1 (audit side): apps/analytics/management/commands/audit_dataset.py
must be able to detect the generator_service.py bug where a real Amazon
review's text gets attributed to the wrong Item (picked by
`random.choice(cat_items)` instead of resolved by parent_asin).

Comments has no is_real/source/parent_asin column, so the check has to
cross-reference Comments.body against apps/analytics/data/amazon_ingest_cache.json:
if a comment's body matches a real review verbatim, that comment's
Item.external_id must equal the parent_asin that review actually belongs to.

These tests fabricate a small, self-contained cache file (monkeypatching the
command's AMAZON_INGEST_CACHE_PATH) instead of depending on the real
apps/analytics/data/amazon_ingest_cache.json, so the detection logic itself
is exercised deterministically regardless of whether the other agent's
generator_service.py fix has landed yet.
"""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.analytics.management.commands import audit_dataset
from apps.catalog.models import Category, Comments, Item
from django.contrib.auth.models import User

REAL_REVIEW_TEXT = (
    "This spray is really nice. It smells really good, goes on really "
    "fine, and does the trick."
)
OTHER_REAL_REVIEW_TEXT = "Sturdy case, fits my phone perfectly and the color is exactly as pictured."


def _write_cache(tmp_path, reviews):
    cache_path = tmp_path / "amazon_ingest_cache.json"
    cache_path.write_text(
        json.dumps({"schema_version": 2, "products": [], "reviews": reviews}),
        encoding="utf-8",
    )
    return cache_path


def _make_item(title, external_id):
    category = Category.objects.get_or_create(name="Beauty")[0]
    return Item.objects.create(
        title=title,
        price=10,
        category=category,
        external_id=external_id,
    )


def _make_user(username):
    return User.objects.create_user(username=username, password="password123")


@pytest.mark.django_db
class TestAuditDatasetReviewAttribution:
    def test_detects_review_text_attributed_to_wrong_item(self, tmp_path, monkeypatch, capsys):
        """The exact bug this check exists for: a real review of parent_asin
        A ends up as a Comments.body on an Item whose external_id is B."""
        cache_path = _write_cache(tmp_path, [
            {"parent_asin": "B00YQ6X8EO", "text": REAL_REVIEW_TEXT, "rating": 5.0, "category": "Beauty"},
        ])
        monkeypatch.setattr(audit_dataset, "AMAZON_INGEST_CACHE_PATH", cache_path)

        correct_item = _make_item("Real product for B00YQ6X8EO", "B00YQ6X8EO")
        wrong_item = _make_item("Unrelated product", "B0OTHERASIN")
        user = _make_user("reviewer1")

        Comments.objects.create(user=user, item=wrong_item, body=REAL_REVIEW_TEXT, rating=5)

        with pytest.raises(CommandError, match="1 Comments"):
            call_command("audit_dataset")

        output = capsys.readouterr().out
        assert "Review attribution discrepancies: 1" in output
        assert f"Item(id={wrong_item.id}" in output
        assert "'B00YQ6X8EO'" in output
        assert correct_item.id  # correct item exists in the dataset, just wasn't picked

    def test_zero_discrepancies_when_review_attributed_to_correct_item(self, tmp_path, monkeypatch, capsys):
        """Fixed-generator shape: the review's text lives on the item whose
        external_id actually matches the review's parent_asin."""
        cache_path = _write_cache(tmp_path, [
            {"parent_asin": "B00YQ6X8EO", "text": REAL_REVIEW_TEXT, "rating": 5.0, "category": "Beauty"},
        ])
        monkeypatch.setattr(audit_dataset, "AMAZON_INGEST_CACHE_PATH", cache_path)

        correct_item = _make_item("Real product for B00YQ6X8EO", "B00YQ6X8EO")
        user = _make_user("reviewer1")
        Comments.objects.create(user=user, item=correct_item, body=REAL_REVIEW_TEXT, rating=5)

        call_command("audit_dataset")  # must not raise

        output = capsys.readouterr().out
        assert "Checkable Comments (body matches a real review): 1" in output
        assert "Review attribution discrepancies: 0" in output

    def test_synthetic_comment_is_not_checkable_and_not_a_discrepancy(self, tmp_path, monkeypatch, capsys):
        """A sample_bodies synthetic comment on an item that *does* have real
        reviews in the cache must not be flagged -- it simply isn't
        checkable, per the plan's design note."""
        cache_path = _write_cache(tmp_path, [
            {"parent_asin": "B00YQ6X8EO", "text": REAL_REVIEW_TEXT, "rating": 5.0, "category": "Beauty"},
        ])
        monkeypatch.setattr(audit_dataset, "AMAZON_INGEST_CACHE_PATH", cache_path)

        item = _make_item("Real product for B00YQ6X8EO", "B00YQ6X8EO")
        user = _make_user("reviewer1")
        Comments.objects.create(
            user=user, item=item,
            body="Excelente producto, cumplió con todas mis expectativas.",
            rating=4,
        )

        call_command("audit_dataset")  # must not raise

        output = capsys.readouterr().out
        assert "Checkable Comments (body matches a real review): 0" in output
        assert "Review attribution discrepancies: 0" in output

    def test_multiple_reviews_only_flags_the_actual_mismatch(self, tmp_path, monkeypatch, capsys):
        cache_path = _write_cache(tmp_path, [
            {"parent_asin": "ASIN-A", "text": REAL_REVIEW_TEXT, "rating": 5.0, "category": "Beauty"},
            {"parent_asin": "ASIN-B", "text": OTHER_REAL_REVIEW_TEXT, "rating": 4.0, "category": "Beauty"},
        ])
        monkeypatch.setattr(audit_dataset, "AMAZON_INGEST_CACHE_PATH", cache_path)

        item_a = _make_item("Product A", "ASIN-A")
        item_b = _make_item("Product B", "ASIN-B")
        user1 = _make_user("reviewer1")
        user2 = _make_user("reviewer2")

        # Correct attribution -- must not be flagged.
        Comments.objects.create(user=user1, item=item_a, body=REAL_REVIEW_TEXT, rating=5)
        # Wrong attribution -- review for ASIN-B's product pasted onto item_a.
        Comments.objects.create(user=user2, item=item_a, body=OTHER_REAL_REVIEW_TEXT, rating=4)

        with pytest.raises(CommandError, match="1 Comments"):
            call_command("audit_dataset")

        output = capsys.readouterr().out
        assert "Checkable Comments (body matches a real review): 2" in output
        assert "Review attribution discrepancies: 1" in output

    def test_body_truncated_to_1000_chars_still_matches(self, tmp_path, monkeypatch, capsys):
        """generator_service.py stores `rev["text"][:1000]`, so a long real
        review's text is truncated before it ever reaches Comments.body --
        the audit must truncate the cached review text the same way."""
        long_text = "A" * 1500
        cache_path = _write_cache(tmp_path, [
            {"parent_asin": "B00YQ6X8EO", "text": long_text, "rating": 5.0, "category": "Beauty"},
        ])
        monkeypatch.setattr(audit_dataset, "AMAZON_INGEST_CACHE_PATH", cache_path)

        wrong_item = _make_item("Unrelated product", "B0OTHERASIN")
        user = _make_user("reviewer1")
        Comments.objects.create(user=user, item=wrong_item, body=long_text[:1000], rating=5)

        with pytest.raises(CommandError, match="1 Comments"):
            call_command("audit_dataset")

        output = capsys.readouterr().out
        assert "Checkable Comments (body matches a real review): 1" in output
        assert "Review attribution discrepancies: 1" in output

    def test_missing_cache_file_skips_audit_without_crashing(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(audit_dataset, "AMAZON_INGEST_CACHE_PATH", tmp_path / "does_not_exist.json")

        call_command("audit_dataset")  # must not raise

        output = capsys.readouterr().out
        assert "skipping review attribution audit" in output

    def test_existing_summary_counts_are_preserved(self, tmp_path, monkeypatch, capsys):
        """The new check must be additive -- the pre-existing per-model
        counts this command already printed must still be there."""
        monkeypatch.setattr(audit_dataset, "AMAZON_INGEST_CACHE_PATH", tmp_path / "does_not_exist.json")

        call_command("audit_dataset")

        output = capsys.readouterr().out
        assert "Total Users:" in output
        assert "Total Items:" in output
        assert "Total Comments:" in output
        assert "=== Dataset Audit Completed Successfully ===" in output
