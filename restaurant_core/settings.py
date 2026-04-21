from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Automatically load environment variables from the .env file
load_dotenv(BASE_DIR / '.env')

# --- Security ----
# IMPORTANT: Replace with a strong secret key and set DEBUG=False in production.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-replace-this-in-production-use-env-variable'
)
# Warn clearly if using insecure key
if 'insecure' in SECRET_KEY:
    import warnings
    warnings.warn("Using insecure SECRET_KEY. Set DJANGO_SECRET_KEY environment variable for production.")
    
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# --- API Integration ---
# Set this to your backend's base URL (no trailing slash)
# Override via environment variable: export API_BASE_URL=http://your-backend.com/api
API_BASE_URL = os.environ.get('API_BASE_URL', 'http://localhost:9000/api')

# --- Installed Apps ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'customer_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'restaurant_core.urls'

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
                'customer_app.context_processors.demo_mode',
            ],
        },
    },
]

WSGI_APPLICATION = 'restaurant_core.wsgi.application'

# --- Database ----
# Using SQLite for development (Django sessions require a DB)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --- Session Configuration ---
# Auth tokens stored securely in server-side sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 7       # 7 days
SESSION_COOKIE_HTTPONLY = True        # Prevent JS access to session cookie
SESSION_COOKIE_SAMESITE = 'Lax'      # CSRF protection
# SESSION_COOKIE_SECURE = True        # Uncomment for HTTPS (production)

# --- Static Files ---
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'   # For production: run collectstatic

# --- Internationalization ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Logging ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'customer_app': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'WARNING',
        },
    },
}

# --- Demo Mode ---
DEMO_MODE = False