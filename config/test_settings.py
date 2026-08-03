"""
Настройки для запуска тестов на SQLite.
Использование: python manage.py test --settings=config.test_settings
"""
from config.settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
    }
}

# В тестах отправка почты не требуется
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
