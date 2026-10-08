"""Django settings, env-driven via django-environ.

See dev/25_06_minimal_req.md (Config & deployment). Secrets and the Neon DATABASE_URL come
from the environment; DATABASE_URL is required (no SQLite fallback — fails fast if unset), and
so is SECRET_KEY unless DEBUG=True.
Defaults are Cloud-Run-friendly (`.run.app` host + `https://*.run.app` CSRF origin) so the
deployed service works out of the box; env vars still override.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env("DEBUG")
# Insecure fallback only in DEBUG; with DEBUG=False an unset SECRET_KEY fails fast
# (environ.ImproperlyConfigured) instead of signing sessions with a public key.
if DEBUG:
    SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me")
else:
    SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", ".run.app"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["https://*.run.app"])

# Cloud Run terminates TLS and forwards over HTTP with X-Forwarded-Proto: https. Without this,
# request.is_secure() is False and the CSRF Origin scheme check rejects the POST forms.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # local apps
    "profiles",
    "tracker",
    "tailoring",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Site-wide login: every view requires an authenticated user (admin views are exempt).
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# Single-user app: log in with the superuser via the admin login page (handles ?next=).
LOGIN_URL = "admin:login"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Neon over a plain DATABASE_URL. Required — no SQLite fallback; fails fast
# (environ.ImproperlyConfigured) if unset, in any environment.
DATABASES = {
    "default": env.db("DATABASE_URL"),
}
# Neon's pooled endpoint runs PgBouncer in transaction mode. psycopg3 prepared statements and
# server-side cursors break under it (they work for one-shot `migrate` but throw under the
# pooled gunicorn runtime), so disable both. Harmless on a direct (non-pooled) connection.
DATABASES["default"].setdefault("OPTIONS", {})["prepare_threshold"] = None
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- App config ---------------------------------------------------------------
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
