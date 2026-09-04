import random
import sys
from django.core.management.base import BaseCommand
from apps.analytics.services import generate_dataset_pipeline


class Command(BaseCommand):
    help = (
        'Generates synthetic dataset for analytics based on Amazon Reviews 2023. '
        'DESTRUCTIVE: first purges the entire product catalog, all orders, and all '
        'non-superuser user accounts. Intended for dev/demo environments only.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed',
            type=int,
            help='Specify a seed for reproducible generation'
        )
        parser.add_argument(
            '--noinput', '--force',
            action='store_true',
            dest='noinput',
            help=(
                "Skip the interactive confirmation prompt. For CI/staging automation "
                "against environments known not to hold real data -- never for routine "
                "interactive use."
            ),
        )

    def handle(self, *args, **kwargs):
        seed = kwargs.get('seed')
        if seed is None:
            seed = random.randint(1, 1000000)

        if not kwargs.get('noinput') and not self._confirm_destructive_purge():
            return

        def console_log(msg):
            self.stdout.write(self.style.SUCCESS(msg))

        self.stdout.write(self.style.SUCCESS(f"Initiating dataset generation (Seed: {seed})..."))
        generate_dataset_pipeline(seed=seed, console_callback=console_log)
        self.stdout.write(self.style.SUCCESS("Successfully completed data generation!"))

    def _confirm_destructive_purge(self) -> bool:
        """
        Same pattern Django itself uses for destructive commands (see 'flush'):
        require an explicit 'yes' before touching the database, and never call
        input() against a non-interactive stdin -- doing so would either raise
        or block forever waiting on input that will never arrive (e.g. a CI
        pipeline running this without --noinput by mistake).
        """
        self.stdout.write(self.style.WARNING(
            "This will PERMANENTLY DELETE the entire product catalog, every order, "
            "and every non-superuser user account before generating new synthetic "
            "data. This action cannot be undone."
        ))

        if not sys.stdin.isatty():
            self.stdout.write(self.style.WARNING(
                "Aborting: stdin is not interactive, so no confirmation can be read. "
                "Re-run with --noinput (or --force) only in CI/staging automation "
                "against environments known not to hold real data."
            ))
            return False

        answer = input("Type 'yes' to continue, or anything else to abort: ")
        if answer != 'yes':
            self.stdout.write(self.style.WARNING("Aborted: no data was modified."))
            return False

        return True
