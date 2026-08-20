import os

from celery import Celery


# Set Django settings module
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)


# Create Celery application
app = Celery("config")


# Load Celery settings from Django settings
app.config_from_object(
    "django.conf:settings",
    namespace="CELERY",
)


# Automatically discover tasks.py from installed Django apps
app.autodiscover_tasks()