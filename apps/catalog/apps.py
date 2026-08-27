from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.catalog'
    label = 'catalog'

    def ready(self):
        import apps.catalog.signals  # noqa: F401
