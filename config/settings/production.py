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
