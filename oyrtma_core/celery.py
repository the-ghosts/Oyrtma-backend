"""
Celery configuration and initialization for OYRTMA backend
"""

import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oyrtma_core.settings')

app = Celery('oyrtma_core')

# Load configuration from Django settings with 'CELERY' namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')
