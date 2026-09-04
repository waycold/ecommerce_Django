# Minimal container image for ecommerce_Django.
#
# Purpose: let the sibling E2E repo (rag-e2e-tests/) start this service as a
# container (via Testcontainers or docker-compose) instead of requiring a
# manually-run local dev server. This is NOT how Render deploys the app today
# (Render uses build.sh + a dashboard-configured start command) -- this image
# is for local/CI E2E orchestration only.
#
# DJANGO_SETTINGS_MODULE is intentionally left unset here so it falls back to
# manage.py's own default (config.settings.local). config.settings.production
# now fails to boot without several secrets (INTERNAL_API_SECRET,
# JWT_SECRET_KEY, CHATBOT_READONLY_DATABASE_URL, CLOUDINARY_*) that an E2E run
# has no reason to provide -- pass -e DJANGO_SETTINGS_MODULE=... at `docker
# run`/compose time only if a specific settings module is actually needed.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Applies migrations against whatever DATABASE_URL points at, then serves.
# Same gunicorn invocation already documented in README.md for Render.
CMD python manage.py migrate --noinput && \
    gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120
