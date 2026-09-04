"""
tests/test_cloudinary_storage.py

Fase 1, Tarea 1: config/settings/production.py must serve media
(Item.img, Profile.image) from Cloudinary instead of FileSystemStorage over
Render's ephemeral web-dyno disk, so uploaded images survive a redeploy.

Design decision (documented here, not just in the plan): production fails
fast at boot -- same as INTERNAL_API_SECRET/JWT_SECRET_KEY/
CHATBOT_READONLY_DATABASE_URL in tests/test_settings_fail_fast.py -- if
CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET are not all set, rather than
silently falling back to FileSystemStorage. A silent fallback here would
quietly reintroduce the exact bug this task exists to close.

Same importlib re-import pattern as tests/test_settings_fail_fast.py (see
that file's module docstring for why a subprocess `manage.py check` doesn't
work with this repo's `load_dotenv(override=True)`): evict the target
settings module from sys.modules and re-import it so its module-level code
runs again against the current os.environ, while config.settings.base stays
cached (its own load_dotenv() already ran once at pytest-django startup).
"""

import importlib
import sys

import pytest


def _import_fresh_production_settings():
    sys.modules.pop('config.settings.production', None)
    return importlib.import_module('config.settings.production')


def _import_fresh_testing_settings():
    sys.modules.pop('config.settings.testing', None)
    return importlib.import_module('config.settings.testing')


def _import_fresh_local_settings():
    sys.modules.pop('config.settings.local', None)
    return importlib.import_module('config.settings.local')


def _set_other_required_production_env(monkeypatch):
    """Sets every production-required env var *except* the Cloudinary
    trio, so tests can isolate the Cloudinary fail-fast check from the
    unrelated Fase 0 ones that already run earlier in production.py."""
    monkeypatch.setenv('DJANGO_SECRET_KEY', 'test-django-secret-key')
    monkeypatch.setenv('INTERNAL_API_SECRET', 'test-internal-api-secret')
    monkeypatch.setenv('JWT_SECRET_KEY', 'test-jwt-secret-key')
    monkeypatch.setenv('CHATBOT_READONLY_DATABASE_URL', 'sqlite:///./chatbot_readonly_test.sqlite3')


class TestProductionUsesCloudinaryWhenConfigured:
    def test_storage_backend_is_cloudinary_when_env_vars_present(self, monkeypatch):
        _set_other_required_production_env(monkeypatch)
        monkeypatch.setenv('CLOUDINARY_CLOUD_NAME', 'test-cloud-name')
        monkeypatch.setenv('CLOUDINARY_API_KEY', 'test-cloudinary-api-key')
        monkeypatch.setenv('CLOUDINARY_API_SECRET', 'test-cloudinary-api-secret')

        module = _import_fresh_production_settings()

        assert module.STORAGES['default']['BACKEND'] == 'cloudinary_storage.storage.MediaCloudinaryStorage'
        assert module.CLOUDINARY_STORAGE == {
            'CLOUD_NAME': 'test-cloud-name',
            'API_KEY': 'test-cloudinary-api-key',
            'API_SECRET': 'test-cloudinary-api-secret',
        }
        # staticfiles must be untouched by the media-storage switch.
        assert module.STORAGES['staticfiles']['BACKEND'] == (
            'apps.core.storage.NonStrictCompressedManifestStaticFilesStorage'
        )


class TestProductionCloudinaryFailFast:
    """Chosen behavior for missing Cloudinary env vars in production:
    fail fast (ValueError), consistent with the rest of Fase 0's critical
    secrets -- never a silent fallback to ephemeral FileSystemStorage."""

    def test_missing_all_cloudinary_vars_raises(self, monkeypatch):
        _set_other_required_production_env(monkeypatch)
        monkeypatch.delenv('CLOUDINARY_CLOUD_NAME', raising=False)
        monkeypatch.delenv('CLOUDINARY_API_KEY', raising=False)
        monkeypatch.delenv('CLOUDINARY_API_SECRET', raising=False)

        with pytest.raises(ValueError, match='CLOUDINARY'):
            _import_fresh_production_settings()

    def test_missing_only_api_secret_raises(self, monkeypatch):
        """All three are required -- two out of three set is still a
        failure, not a partial/degraded success."""
        _set_other_required_production_env(monkeypatch)
        monkeypatch.setenv('CLOUDINARY_CLOUD_NAME', 'test-cloud-name')
        monkeypatch.setenv('CLOUDINARY_API_KEY', 'test-cloudinary-api-key')
        monkeypatch.delenv('CLOUDINARY_API_SECRET', raising=False)

        with pytest.raises(ValueError, match='CLOUDINARY'):
            _import_fresh_production_settings()


class TestLocalAndTestingKeepFileSystemStorage:
    """local.py and config/settings/testing.py must never depend on
    Cloudinary -- they run on SQLite for dev/test convenience and the test
    suite uploads test files straight to MEDIA_ROOT."""

    def test_testing_settings_use_filesystem_storage(self, monkeypatch):
        # Cloudinary vars being set (e.g. present in a dev's real .env)
        # must not change testing's storage backend.
        monkeypatch.setenv('CLOUDINARY_CLOUD_NAME', 'test-cloud-name')
        monkeypatch.setenv('CLOUDINARY_API_KEY', 'test-cloudinary-api-key')
        monkeypatch.setenv('CLOUDINARY_API_SECRET', 'test-cloudinary-api-secret')

        module = _import_fresh_testing_settings()

        assert module.STORAGES['default']['BACKEND'] == 'django.core.files.storage.FileSystemStorage'

    def test_local_settings_use_filesystem_storage(self, monkeypatch):
        monkeypatch.setenv('CLOUDINARY_CLOUD_NAME', 'test-cloud-name')
        monkeypatch.setenv('CLOUDINARY_API_KEY', 'test-cloudinary-api-key')
        monkeypatch.setenv('CLOUDINARY_API_SECRET', 'test-cloudinary-api-secret')

        module = _import_fresh_local_settings()

        assert module.STORAGES['default']['BACKEND'] == 'django.core.files.storage.FileSystemStorage'

    def test_currently_loaded_test_settings_use_filesystem_storage(self):
        """Sanity check against the actual settings this whole suite runs
        under (config.settings.testing, per pytest.ini)."""
        from django.conf import settings

        assert settings.STORAGES['default']['BACKEND'] == 'django.core.files.storage.FileSystemStorage'


class TestCloudinaryAppsRegistered:
    """INSTALLED_APPS ordering required by django-cloudinary-storage:
    cloudinary_storage before django.contrib.staticfiles, cloudinary before
    this project's own apps."""

    def test_installed_apps_ordering(self):
        from django.conf import settings

        apps = settings.INSTALLED_APPS
        assert 'cloudinary_storage' in apps
        assert 'cloudinary' in apps
        assert apps.index('cloudinary_storage') < apps.index('django.contrib.staticfiles')
        assert apps.index('cloudinary') < apps.index('apps.core')
