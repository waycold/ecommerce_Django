"""
config/settings/local.py

Development environment settings with debug enabled and SQLite fallback.
"""

from config.settings.base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Optional developer tooling or debug toolbar configuration can be appended here
