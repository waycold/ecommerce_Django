"""
apps/catalog/management/commands/requeue_stale_embedding_tasks.py

Reaper for the EmbeddingSyncTask outbox: get_pending_embedding_tasks_service
(apps.catalog.rag_service) only ever claims tasks in PENDING, atomically
flipping them to PROCESSING for the Gateway to work on. If the Gateway
crashes or is killed mid-batch, those tasks stay in PROCESSING forever --
nothing else selects for that status, so they become invisible to both the
Gateway and any human looking at the queue.

This command reverts any PROCESSING task whose `updated_at` is older than a
configurable staleness threshold back to PENDING, so the next Gateway poll
cycle picks it up again.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import EmbeddingSyncTask


class Command(BaseCommand):
    help = (
        'Requeues EmbeddingSyncTask rows stuck in PROCESSING (e.g. the Gateway '
        'crashed or was killed mid-batch) back to PENDING, so they are picked '
        'up again by the next embeddings/pending poll cycle.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=30,
            help='Age threshold in minutes: PROCESSING tasks not updated within this '
                 'many minutes are considered stale and reverted to PENDING (default: 30).',
        )

    def handle(self, *args, **options):
        minutes = options['minutes']
        cutoff = timezone.now() - timezone.timedelta(minutes=minutes)

        stale_task_ids = list(
            EmbeddingSyncTask.objects.filter(
                status=EmbeddingSyncTask.Status.PROCESSING,
                updated_at__lt=cutoff,
            ).values_list('pk', flat=True)
        )

        requeued_count = 0
        if stale_task_ids:
            requeued_count = EmbeddingSyncTask.objects.filter(pk__in=stale_task_ids).update(
                status=EmbeddingSyncTask.Status.PENDING
            )

        self.stdout.write(self.style.SUCCESS(
            f'Requeued {requeued_count} stale PROCESSING task(s) (older than {minutes} minute(s)) to PENDING.'
        ))
