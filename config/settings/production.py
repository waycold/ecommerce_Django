"""
config/settings/production.py

Production-hardened settings with strict security headers, SSL enforcement, and CDN asset delivery.
"""

import os
from config.settings.base import *

DEBUG = False

# Ensure strict secret key in production
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable is required in production.")

# base.py falls back to a public, hardcoded value for local dev convenience
# when these are unset -- unacceptable in production, where that fallback
# would let anyone forge the X-Internal-Secret header or a staff JWT. Same
# fail-fast pattern as DJANGO_SECRET_KEY above: read with no valid default
# and refuse to boot if missing.
INTERNAL_API_SECRET = os.environ.get('INTERNAL_API_SECRET')
if not INTERNAL_API_SECRET:
    raise ValueError("INTERNAL_API_SECRET environment variable is required in production.")

JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is required in production.")

# The AI sandbox (apps.core.services.sql_sandbox_service) must run against
# the dedicated least-privilege `chatbot_readonly_role`, never the full
# Django role -- see docs/sql/create_chatbot_readonly_role.sql. base.py only
# adds DATABASES['chatbot_readonly'] when this env var is set; production
# must never silently fall back to the unrestricted 'default' connection.
if not os.environ.get('CHATBOT_READONLY_DATABASE_URL'):
    raise ValueError("CHATBOT_READONLY_DATABASE_URL environment variable is required in production.")

# Fase 1, Tarea 1: persistent media storage. base.py's STORAGES['default']
# is FileSystemStorage over Render's ephemeral web-dyno disk -- fine for
# local dev, but any product/profile image uploaded in production would be
# silently lost on the next redeploy. Same fail-fast rationale as the
# secrets above: this task exists specifically so "no uploaded image is
# ever lost", so a fallback to FileSystemStorage here would quietly
# reintroduce the exact P0 bug it's meant to close. Refuse to boot instead.
# Re-read (rather than reuse base.py's CLOUDINARY_STORAGE) for the same
# reason SECRET_KEY etc. are re-read above instead of trusted from base.py.
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}
if not (
    CLOUDINARY_STORAGE['CLOUD_NAME']
    and CLOUDINARY_STORAGE['API_KEY']
    and CLOUDINARY_STORAGE['API_SECRET']
):
    raise ValueError(
        "CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET "
        "environment variables are all required in production: without them, "
        "product/profile images would be written to Render's ephemeral disk "
        "and lost on the next redeploy."
    )

STORAGES = {
    **STORAGES,
    'default': {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
    },
}

# Parse allowed hosts
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
    if host.strip()
]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['.onrender.com', 'localhost', '127.0.0.1']

# Security Headers & Cookies
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
