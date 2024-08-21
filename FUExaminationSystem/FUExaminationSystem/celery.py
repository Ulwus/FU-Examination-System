
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FUExaminationSystem.settings')

app = Celery('FUExaminationSystem')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.broker_connection_retry_on_startup = True

app.conf.beat_schedule = {
    'check-and-finish-exams': {
        'task': 'exams.tasks.check_and_finish_exams',
        'schedule': crontab(minute='*/1'),
    },
}