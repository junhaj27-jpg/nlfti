import os
from django.core.exceptions import ImproperlyConfigured
from .settings import *  # noqa: F403,F401

DEBUG=False
if SECRET_KEY=="dev-only-insecure-key" or len(SECRET_KEY)<32:  # noqa: F405
    raise ImproperlyConfigured("운영 환경에는 32자 이상의 DJANGO_SECRET_KEY가 필요합니다.")
if not os.getenv("DATABASE_URL","").startswith("postgresql://"):
    raise ImproperlyConfigured("운영 환경에는 PostgreSQL DATABASE_URL이 필요합니다.")
ALLOWED_HOSTS=[value.strip() for value in os.getenv("DJANGO_ALLOWED_HOSTS","").split(",") if value.strip()]
if not ALLOWED_HOSTS: raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS를 설정하십시오.")
CSRF_TRUSTED_ORIGINS=[value.strip() for value in os.getenv("CSRF_TRUSTED_ORIGINS","").split(",") if value.strip()]

MIDDLEWARE.insert(1,"whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES={
    "default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},
    "staticfiles":{"BACKEND":"whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO","https")
SECURE_SSL_REDIRECT=os.getenv("DJANGO_SECURE_SSL_REDIRECT","1")=="1"
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SECURE_HSTS_SECONDS=int(os.getenv("DJANGO_HSTS_SECONDS","3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=False
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY="same-origin"
X_FRAME_OPTIONS="DENY"
AUTH_PASSWORD_VALIDATORS=[
    {"NAME":"django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME":"django.contrib.auth.password_validation.MinimumLengthValidator","OPTIONS":{"min_length":12}},
    {"NAME":"django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME":"django.contrib.auth.password_validation.NumericPasswordValidator"},
]
