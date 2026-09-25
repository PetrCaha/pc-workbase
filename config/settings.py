"""PC WORKBASE: public, read-only portfolio demonstration."""
import os
import sys
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
TESTING = Path(sys.argv[0]).name == 'manage.py' and len(sys.argv) > 1 and sys.argv[1] == 'test'
SETUP = os.environ.get('WORKBASE_SETUP') == '1'
if SETUP and (len(sys.argv) < 2 or sys.argv[1] not in {'migrate', 'seed_demo', 'makemigrations', 'check', 'collectstatic', 'test'}):
    raise ImproperlyConfigured('WORKBASE_SETUP is restricted to offline management commands.')
if not SETUP and os.environ.get('WORKBASE_SETUP_DATABASE_URL'):
    raise ImproperlyConfigured('Remove owner database credentials from the public runtime environment.')
if os.environ.get('RENDER') and DEBUG:
    raise ImproperlyConfigured('DEBUG must be false on Render.')
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG or TESTING or SETUP:
        SECRET_KEY = 'local-workbase-development-only-not-for-public-deployment'
    else:
        raise ImproperlyConfigured('Set a private SECRET_KEY before starting PC WORKBASE.')
if not DEBUG and not TESTING and not SETUP and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith(('django-insecure-', 'local-', 'replace-'))):
    raise ImproperlyConfigured('Production SECRET_KEY must be a private random value of at least 50 characters.')
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]']
if TESTING:
    ALLOWED_HOSTS.append('testserver')
ALLOWED_HOSTS += [x.strip() for x in os.environ.get('ALLOWED_HOSTS', '').split(',') if x.strip()]
if os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
    ALLOWED_HOSTS.append(os.environ['RENDER_EXTERNAL_HOSTNAME'])
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if x.strip()]
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'rest_framework', 'records']
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'records.demo.middleware.DemoBoundaryMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'records.demo.middleware.DemoAccessMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR/'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages', 'records.context_processors.user_capabilities', 'records.demo.context.workspace']}}]
WSGI_APPLICATION = 'config.wsgi.application'
# No setup credentials are read by the public process.
database_url = os.environ.get('WORKBASE_SETUP_DATABASE_URL' if SETUP else 'DATABASE_URL')
if database_url:
    DATABASES = {'default': dj_database_url.parse(database_url, conn_max_age=60, conn_health_checks=True)}
    if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
        raise ImproperlyConfigured('DATABASE_URL must refer to the dedicated PostgreSQL demo database.')
    if not SETUP and not TESTING:
        DATABASES['default'].setdefault('OPTIONS', {})['options'] = '-c default_transaction_read_only=on -c statement_timeout=5000'
elif not DEBUG and not SETUP and not TESTING:
    raise ImproperlyConfigured('DATABASE_URL with read-only demo credentials is required.')
else:
    db_path = BASE_DIR/'demo.sqlite3'
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(db_path) if SETUP or TESTING else f'file:{db_path}?mode=ro', 'OPTIONS': {} if SETUP or TESTING else {'uri': True}}}
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'cs'
LANGUAGES = [('cs', 'Čeština'), ('en', 'English')]
LOCALE_PATHS = [BASE_DIR/'locale']
TIME_ZONE = 'Europe/Prague'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR/'static']
STATIC_ROOT = BASE_DIR/'staticfiles'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_NAME = 'workbase_session'
SESSION_COOKIE_AGE = 8 * 3600
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
LANGUAGE_COOKIE_SECURE = not DEBUG
LANGUAGE_COOKIE_SAMESITE = 'Lax'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = not DEBUG and not TESTING
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
CSRF_FAILURE_VIEW = 'records.demo.views.csrf_failure'
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'], 'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'], 'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer']}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DATA_UPLOAD_MAX_MEMORY_SIZE = 128 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
FILE_UPLOAD_HANDLERS = ['records.demo.uploads.RejectUploads']
DEMO_USER = 'anna.demo'
DEMO_REFERENCE_DATE = '2026-09-25'
