from __future__ import annotations

import pathlib
from typing import Any

BASE_DIR = pathlib.Path(__file__).resolve().parent

DEBUG = False

SECRET_KEY = "NOTASECRET"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django.contrib.messages",
    "django_tailwind_cli",
]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3"}}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES: list[dict[str, Any]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

STATIC_URL = "/static/"
STATICFILES_DIRS = (BASE_DIR / "assets",)

USE_TZ = True

SILENCED_SYSTEM_CHECKS = ["staticfiles.W004"]

# Explicit test default (also matches the library default): disable auto
# @source injection so the generated source.css content is deterministic
# regardless of how django_tailwind_cli itself happens to be installed in
# the dev env (editable src/ vs. wheel). Feature tests opt back in
# explicitly where they exercise the external-app logic.
TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS = False
