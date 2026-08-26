"""
Testing settings for pytest suite.
Optimized for high-speed isolated unit and contract tests.
"""

from .base import *

DEBUG = False

# Fast SQLite in-memory database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Fast password hasher for instantaneous test execution
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Django 4.2+: STATICFILES_STORAGE was replaced by the STORAGES setting.
STORAGES = {
    **STORAGES,
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
