"""
apps/catalog/signals.py

Real-time outbox trigger: whenever an Item is saved in a way that could
change its semantic embedding text, queue an EmbeddingSyncTask for the
Chatbot-Engine-Gateway microservice to pick up and process, then best-effort
ping the Gateway to wake up and poll immediately instead of waiting for its
next scheduled poll cycle.

Note: bulk operations (QuerySet.update(), bulk_create(), bulk_update())
do NOT trigger Django's post_save signal. The full-catalog regeneration
pipeline (apps.analytics.services.generator_service.generate_dataset_pipeline)
therefore seeds EmbeddingSyncTask rows explicitly via bulk_create instead of
relying on this signal.
"""

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

import hashlib
import logging

import httpx

from apps.catalog.models import Item, EmbeddingSyncTask, build_embedding_text

logger = logging.getLogger(__name__)

# Kept short: this runs synchronously inside transaction.on_commit, so it
# still adds to the create/edit-product request's latency even though it's
# best-effort. A short timeout bounds that worst case; the Gateway's own
# polling cycle (see module docstring) is the backstop if the wake is lost.
WAKE_TIMEOUT_SECONDS = 0.5


@receiver(post_save, sender=Item)
def queue_embedding_sync(sender, instance, **kwargs):
    relevant_fields = {"title", "description", "category_id", "brand_id", "label"}
    if kwargs.get("update_fields") and not (set(kwargs["update_fields"]) & relevant_fields):
        return  # the save didn't touch anything that affects the embedded text

    def _enqueue():
        content_hash = hashlib.sha256(build_embedding_text(instance).encode("utf-8")).hexdigest()
        task = EmbeddingSyncTask.objects.create(item=instance, content_hash=content_hash)
        try:
            httpx.post(
                f"{settings.AI_AGENT_GATEWAY_URL}/internal/embeddings/wake",
                headers={"X-Internal-Secret": settings.INTERNAL_API_SECRET},
                timeout=WAKE_TIMEOUT_SECONDS,
            )
        except Exception:
            # Best-effort -- never let a Gateway hiccup fail or block the
            # actual product save, but a silent failure here means nobody
            # finds out the Gateway missed its wake-up call.
            logger.warning(
                "Gateway wake ping failed for Item %s (EmbeddingSyncTask %s); "
                "the sync task is still queued and will be picked up by the "
                "Gateway's next scheduled poll.",
                instance.pk,
                task.pk,
                exc_info=True,
            )

    transaction.on_commit(_enqueue)
