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
        'OPTIONS': {
            # SQLite's default DEFERRED transactions only take a lock on the
            # first read/write, so two concurrent transaction.atomic() blocks
            # can both acquire a SHARED read lock and then race to escalate
            # to a write lock -- a conflict SQLite reports as "database table
            # is locked" (SQLITE_LOCKED), which is NOT retried by the
            # busy_timeout used for plain "database is locked" (SQLITE_BUSY).
            # IMMEDIATE mode takes the write lock as soon as the transaction
            # starts, so a concurrent writer instead blocks on SQLITE_BUSY --
            # which busy_timeout does retry -- giving the same serialization
            # guarantee select_for_update() provides on Postgres.
            'transaction_mode': 'IMMEDIATE',
        },
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
