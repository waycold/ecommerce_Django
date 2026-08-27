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
import httpx

from apps.catalog.models import Item, EmbeddingSyncTask, build_embedding_text


@receiver(post_save, sender=Item)
def queue_embedding_sync(sender, instance, **kwargs):
    relevant_fields = {"title", "description", "category_id", "brand_id", "label"}
    if kwargs.get("update_fields") and not (set(kwargs["update_fields"]) & relevant_fields):
        return  # the save didn't touch anything that affects the embedded text

    def _enqueue():
        content_hash = hashlib.sha256(build_embedding_text(instance).encode("utf-8")).hexdigest()
        EmbeddingSyncTask.objects.create(item=instance, content_hash=content_hash)
        try:
            httpx.post(
                f"{settings.AI_AGENT_GATEWAY_URL}/internal/embeddings/wake",
                headers={"X-Internal-Secret": settings.INTERNAL_API_SECRET},
                timeout=2.0,
            )
        except Exception:
            pass  # best-effort -- never block the actual save

    transaction.on_commit(_enqueue)
