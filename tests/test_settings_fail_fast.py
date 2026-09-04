"""
tests/test_settings_fail_fast.py

Fase 0, Tareas 2(c) y 5: config/settings/production.py must refuse to boot
(raise instead of completing import) when any of these environment
variables is missing, instead of silently falling back to a public,
hardcoded default (INTERNAL_API_SECRET, JWT_SECRET_KEY) or to the
unrestricted 'default' database connection (CHATBOT_READONLY_DATABASE_URL) --
the same fail-fast pattern config/settings/production.py already applies to
DJANGO_SECRET_KEY.

Why importlib re-import instead of a subprocess `manage.py check`: this
repo's config/settings/base.py calls `load_dotenv(override=True)`, and the
project's real .env file already defines DJANGO_SECRET_KEY and
INTERNAL_API_SECRET. `override=True` means a fresh subprocess would reload
those values from .env regardless of what's (un)set in the subprocess's own
env, making it impossible to simulate "the var is missing" that way without
touching the shared .env file. Instead, each test here deletes the variable
from os.environ (auto-restored by monkeypatch) and forces a *fresh* execution
of config.settings.production's module-level code by evicting it from
sys.modules before re-importing it -- config.settings.base is deliberately
left alone/cached, so its own load_dotenv() call (already executed once,
before this test file ever runs, as part of pytest-django's initial Django
setup under config.settings.testing) does not run again and re-inject the
value from .env.
"""

import importlib
import sys

import pytest


def _import_fresh_production_settings():
    """Evicts config.settings.production from sys.modules and re-imports it,
    so its module-level fail-fast checks run again against the current
    os.environ. On a raised exception, Python itself removes the
    partially-executed module from sys.modules, so callers don't need to
    clean up after a raises-path call."""
    sys.modules.pop('config.settings.production', None)
    return importlib.import_module('config.settings.production')


class TestProductionSecretsFailFast:
    """INTERNAL_API_SECRET and JWT_SECRET_KEY (Tarea 5)."""

    def test_missing_internal_api_secret_raises(self, monkeypatch):
        monkeypatch.setenv('DJANGO_SECRET_KEY', 'test-django-secret-key')
        monkeypatch.setenv('JWT_SECRET_KEY', 'test-jwt-secret-key')
        monkeypatch.setenv('CHATBOT_READONLY_DATABASE_URL', 'sqlite:///:memory:')
        monkeypatch.delenv('INTERNAL_API_SECRET', raising=False)

        with pytest.raises(ValueError, match='INTERNAL_API_SECRET'):
            _import_fresh_production_settings()

    def test_missing_jwt_secret_key_raises(self, monkeypatch):
        monkeypatch.setenv('DJANGO_SECRET_KEY', 'test-django-secret-key')
        monkeypatch.setenv('INTERNAL_API_SECRET', 'test-internal-api-secret')
        monkeypatch.setenv('CHATBOT_READONLY_DATABASE_URL', 'sqlite:///:memory:')
        monkeypatch.delenv('JWT_SECRET_KEY', raising=False)

        with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
            _import_fresh_production_settings()


class TestProductionChatbotReadonlyDatabaseUrlFailFast:
    """CHATBOT_READONLY_DATABASE_URL (Tarea 2c): production must never
    silently fall back to running the AI sandbox against the unrestricted
    'default' connection when the dedicated read-only role's URL is unset."""

    def test_missing_chatbot_readonly_database_url_raises(self, monkeypatch):
        monkeypatch.setenv('DJANGO_SECRET_KEY', 'test-django-secret-key')
        monkeypatch.setenv('INTERNAL_API_SECRET', 'test-internal-api-secret')
        monkeypatch.setenv('JWT_SECRET_KEY', 'test-jwt-secret-key')
        monkeypatch.delenv('CHATBOT_READONLY_DATABASE_URL', raising=False)

        with pytest.raises(ValueError, match='CHATBOT_READONLY_DATABASE_URL'):
            _import_fresh_production_settings()


class TestProductionSettingsBootWithAllSecretsPresent:
    """Sanity check: the fail-fast checks above don't false-positive when
    every required variable is actually set."""

    def test_imports_cleanly_with_all_required_env_vars(self, monkeypatch):
        monkeypatch.setenv('DJANGO_SECRET_KEY', 'test-django-secret-key')
        monkeypatch.setenv('INTERNAL_API_SECRET', 'test-internal-api-secret')
        monkeypatch.setenv('JWT_SECRET_KEY', 'test-jwt-secret-key')
        monkeypatch.setenv('CHATBOT_READONLY_DATABASE_URL', 'sqlite:///./chatbot_readonly_test.sqlite3')
        monkeypatch.setenv('CLOUDINARY_CLOUD_NAME', 'test-cloud-name')
        monkeypatch.setenv('CLOUDINARY_API_KEY', 'test-cloudinary-api-key')
        monkeypatch.setenv('CLOUDINARY_API_SECRET', 'test-cloudinary-api-secret')

        module = _import_fresh_production_settings()

        assert module.INTERNAL_API_SECRET == 'test-internal-api-secret'
        assert module.JWT_SECRET_KEY == 'test-jwt-secret-key'
        assert module.STORAGES['default']['BACKEND'] == 'cloudinary_storage.storage.MediaCloudinaryStorage'


def _import_fresh_base_settings(monkeypatch):
    """Same eviction trick as _import_fresh_production_settings(), applied to
    config.settings.base itself -- needed only for
    TestBaseSettingsChatbotReadonlyAlias below, since production.py's own
    `from config.settings.base import *` re-import does NOT re-execute an
    already-cached base module (see module docstring). Safe to do in
    isolation: this repo's already-configured django.conf.settings (built
    from config.settings.testing at pytest-django startup) copied base.py's
    values by reference at that time and is unaffected by reloading base.py
    as a plain, separate module object afterwards.

    Unlike the production.py helper, this one DOES force base.py's own
    top-level `load_dotenv(override=True)` call to run again -- that's the
    whole point of re-importing base.py itself. Left unpatched, that call
    would reload the project's real .env file and, since override=True means
    .env wins over whatever the test's monkeypatch just did, silently undo
    monkeypatch.delenv/setenv on any variable the real .env also defines
    (CHATBOT_READONLY_DATABASE_URL included, once a developer has set up
    their own real Neon role locally). Patching dotenv.load_dotenv to a
    no-op for the duration of this import neutralizes exactly that, without
    changing base.py itself.
    """
    monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: None)
    sys.modules.pop('config.settings.base', None)
    return importlib.import_module('config.settings.base')


class TestBaseSettingsChatbotReadonlyAlias:
    """
    Fase 0, Tarea 2(c): config/settings/base.py must only add the
    'chatbot_readonly' DATABASES alias when CHATBOT_READONLY_DATABASE_URL is
    actually set -- local dev and config/settings/testing.py (which replaces
    DATABASES outright, see its own module) must never gain it implicitly.
    """

    def test_alias_present_when_env_var_set(self, monkeypatch):
        monkeypatch.setenv('CHATBOT_READONLY_DATABASE_URL', 'sqlite:///./chatbot_readonly_test.sqlite3')
        module = _import_fresh_base_settings(monkeypatch)
        assert 'chatbot_readonly' in module.DATABASES

    def test_alias_absent_when_env_var_unset(self, monkeypatch):
        monkeypatch.delenv('CHATBOT_READONLY_DATABASE_URL', raising=False)
        module = _import_fresh_base_settings(monkeypatch)
        assert 'chatbot_readonly' not in module.DATABASES
