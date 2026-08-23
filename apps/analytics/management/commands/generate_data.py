import random
from django.core.management.base import BaseCommand
from apps.analytics.services import generate_dataset_pipeline


class Command(BaseCommand):
    help = 'Generates synthetic dataset for analytics based on Amazon Reviews 2023'

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed',
            type=int,
            help='Specify a seed for reproducible generation'
        )

    def handle(self, *args, **kwargs):
        seed = kwargs.get('seed')
        if seed is None:
            seed = random.randint(1, 1000000)

        def console_log(msg):
            self.stdout.write(self.style.SUCCESS(msg))

        self.stdout.write(self.style.SUCCESS(f"Initiating dataset generation (Seed: {seed})..."))
        generate_dataset_pipeline(seed=seed, console_callback=console_log)
        self.stdout.write(self.style.SUCCESS("Successfully completed data generation!"))
