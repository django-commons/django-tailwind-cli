"""Django app configuration for django-tailwind-cli.

This module defines the Django app configuration for the Tailwind CSS integration.
It handles app registration and provides metadata for Django's app system.
"""

from django.apps import AppConfig


class DjangoTailwindCliConfig(AppConfig):
    """Django app configuration for Tailwind CSS CLI integration.

    This app provides seamless Tailwind CSS integration for Django projects
    without requiring Node.js. It includes:

    - Management commands for building and watching CSS files
    - Template tags for including Tailwind CSS in templates
    - Automatic CLI binary management
    - Development and production optimization features

    The app is automatically discovered when 'django_tailwind_cli' is added
    to INSTALLED_APPS in Django settings.

    Attributes:
        default_auto_field: Default primary key field type for models
        name: The Python module path for this app
        verbose_name: Human-readable name for Django admin and introspection
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "django_tailwind_cli"
    verbose_name = "Django Tailwind CLI"
