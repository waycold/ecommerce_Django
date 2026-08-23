#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input --settings=config.settings.production
python manage.py migrate --settings=config.settings.production
