import json
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from apps.catalog.models import Item, Category, Brand, Supplier, Comments
from apps.orders.models import Order, OrderItem, Profile

AMAZON_INGEST_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "amazon_ingest_cache.json"

# Comments.body is truncated to 1000 chars when a real review is copied in
# by generator_service.py (`rev["text"][:1000]`); truncate cache text the
# same way so a stored comment body can be matched back to its review.
BODY_TRUNCATE_LEN = 1000


class Command(BaseCommand):
    help = 'Audits current dataset volume, integrity, and category coverage across the catalog and orders'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.HTTP_INFO("=== Running Dataset Audit ==="))

        users_count = User.objects.exclude(is_superuser=True).count()
        profiles_count = Profile.objects.count()
        items_count = Item.objects.count()
        categories_count = Category.objects.count()
        brands_count = Brand.objects.count()
        suppliers_count = Supplier.objects.count()
        orders_count = Order.objects.count()
        order_items_count = OrderItem.objects.count()
        comments_count = Comments.objects.count()

        self.stdout.write(self.style.SUCCESS(f"Total Users: {users_count}"))
        self.stdout.write(self.style.SUCCESS(f"Total Profiles: {profiles_count}"))
        self.stdout.write(self.style.SUCCESS(f"Total Items: {items_count}"))
        self.stdout.write(self.style.SUCCESS(f"Total Categories: {categories_count}"))
        self.stdout.write(self.style.SUCCESS(f"Total Brands: {brands_count}"))
        self.stdout.write(self.style.SUCCESS(f"Total Suppliers: {suppliers_count}"))
        self.stdout.write(self.style.SUCCESS(f"Total Orders: {orders_count}"))
        self.stdout.write(self.style.SUCCESS(f"Total OrderItems: {order_items_count}"))
        self.stdout.write(self.style.SUCCESS(f"Total Comments: {comments_count}"))

        discrepancies = self._audit_review_attribution()

        self.stdout.write(self.style.SUCCESS("=== Dataset Audit Completed Successfully ==="))

        if discrepancies:
            raise CommandError(
                f"Dataset audit failed: {len(discrepancies)} Comments have a real Amazon "
                "review body attributed to the wrong Item."
            )

    def _audit_review_attribution(self):
        """Cross-checks Comments.body against apps/analytics/data/amazon_ingest_cache.json.

        Comments has no is_real/source/parent_asin field, so a synthetic
        comment can't be told apart from a real one by a plain query. What
        *can* be checked directly: a real review's text is a near-unique
        fingerprint of the product it was written for (its parent_asin). If
        a Comments.body matches a real review's text verbatim, that
        Comments.item.external_id must equal the parent_asin that review
        belongs to -- otherwise the review text was pasted onto the wrong
        product (the generator_service.py bug this check exists to catch:
        `random.choice(cat_items)` instead of resolving by parent_asin).

        A Comments whose body does not match any real review text at all is
        not an error -- it's just a synthetic sample_bodies comment, which
        the generator creates for any item regardless of external_id.
        """
        self.stdout.write(self.style.HTTP_INFO("--- Auditing review attribution (real reviews vs. Comments) ---"))

        text_to_asins = self._load_review_text_to_asin_map()
        if not text_to_asins:
            self.stdout.write(self.style.WARNING(
                f"No usable reviews found in {AMAZON_INGEST_CACHE_PATH}; skipping review attribution audit."
            ))
            return []

        comments = Comments.objects.values('id', 'body', 'item_id', 'item__external_id')

        checkable_count = 0
        discrepancies = []
        for comment in comments:
            expected_asins = text_to_asins.get(comment['body'])
            if not expected_asins:
                continue  # synthetic body (or a review not in the cache) -- nothing to verify

            checkable_count += 1
            if comment['item__external_id'] not in expected_asins:
                discrepancies.append({
                    'comment_id': comment['id'],
                    'actual_item_id': comment['item_id'],
                    'actual_external_id': comment['item__external_id'],
                    'expected_external_ids': sorted(expected_asins),
                })

        self.stdout.write(self.style.SUCCESS(f"Checkable Comments (body matches a real review): {checkable_count}"))

        if not discrepancies:
            self.stdout.write(self.style.SUCCESS("Review attribution discrepancies: 0"))
            return []

        self.stdout.write(self.style.ERROR(f"Review attribution discrepancies: {len(discrepancies)}"))
        for d in discrepancies:
            self.stdout.write(self.style.ERROR(
                f"  Comments(id={d['comment_id']}): attributed to Item(id={d['actual_item_id']}, "
                f"external_id={d['actual_external_id']!r}) but body belongs to parent_asin "
                f"{d['expected_external_ids']!r}"
            ))

        return discrepancies

    def _load_review_text_to_asin_map(self):
        """Maps a (truncated) real review text -> the set of parent_asins it
        actually belongs to. A set, not a single value, because the same
        review text could in principle appear verbatim for more than one
        product in the cache; a Comments is only flagged if its item's
        external_id isn't among the legitimate owners of that text.
        """
        if not AMAZON_INGEST_CACHE_PATH.exists():
            return {}

        with open(AMAZON_INGEST_CACHE_PATH, 'r', encoding='utf-8') as f:
            cache = json.load(f)

        text_to_asins = defaultdict(set)
        for review in cache.get('reviews', []):
            parent_asin = review.get('parent_asin')
            text = review.get('text')
            if not parent_asin or not text:
                continue
            text_to_asins[text[:BODY_TRUNCATE_LEN]].add(parent_asin)

        return text_to_asins
