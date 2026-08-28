"""
config/settings/base.py

Base settings common to all environments (local, testing, production).
"""

import os
import sys
from pathlib import Path
from decouple import config
import dj_database_url
from dotenv import load_dotenv

load_dotenv(override=True)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Secret Keys & Core Security ---
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-y8c8+malbq5$u=w8f&9u4ugb92p+ad9dwz)p)&(t@e^()^4_em',
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
    if host.strip()
]

# --- Application definition ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Modular Domains
    'apps.core',
    'apps.catalog',
    'apps.orders',
    'apps.analytics',
    
    # Third-party
    'rest_framework',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.InternalSecretMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.orders.context_processors.profile_image',
                'apps.orders.context_processors.user_jwt_token',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- Database ---
if 'test' in sys.argv or any('pytest' in str(arg) for arg in sys.argv):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': dj_database_url.config(
            default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
            conn_max_age=600,
        )
    }

# --- Password validation ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Internationalization ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --- Static & Media Files ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Django 4.2+: STATICFILES_STORAGE was replaced by the STORAGES setting.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'apps.core.storage.NonStrictCompressedManifestStaticFilesStorage',
    },
}
WHITENOISE_MANIFEST_STRICT = False

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
MEDIA_URL = '/uploads/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'uploads')

# --- Internal Microservice Security & JWT ---
INTERNAL_API_SECRET = os.environ.get(
    'INTERNAL_API_SECRET',
    config('INTERNAL_API_SECRET', default='django-insecure-internal-microservice-secret')
)

# Base URL of the sibling Chatbot-Engine-Gateway (FastAPI) microservice.
# Used only for the best-effort "wake up and poll for pending embeddings"
# ping fired from apps.catalog.signals.queue_embedding_sync -- never for
# fetching embeddings ourselves (Django never calls any embedding/LLM API).
AI_AGENT_GATEWAY_URL = os.environ.get(
    'AI_AGENT_GATEWAY_URL',
    config('AI_AGENT_GATEWAY_URL', default='https://ai-agent-gateway-sued.onrender.com')
)

JWT_SECRET_KEY = os.environ.get(
    'JWT_SECRET_KEY',
    config('JWT_SECRET_KEY', default=SECRET_KEY)
)
