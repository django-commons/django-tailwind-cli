"""Django system checks for django-tailwind-cli.

Checks run on ``manage.py check``, on ``runserver``, and on every ``manage.py tailwind`` subcommand,
which declares ``requires_system_checks = "__all__"``. That covers the moments where a broken CSS
layout matters without putting the work on the template rendering path.
"""

from __future__ import annotations

from typing import Any

from django.core.checks import Warning as DjangoWarning
from django.core.checks import register

from django_tailwind_cli.config import find_src_css_in_static_dirs

SRC_CSS_IN_STATIC_DIR = "django_tailwind_cli.W001"


@register("staticfiles")
def check_src_css_outside_static_dirs(app_configs: Any, **kwargs: Any) -> list[DjangoWarning]:  # noqa: ARG001
    """Report every Tailwind source CSS file that ``collectstatic`` would collect.

    Such a file is rewritten by a manifest storage backend, which cannot resolve the
    ``@import "tailwindcss";`` inside it, and ``collectstatic`` fails with a ``MissingFileError``.

    This is a warning, not an error: without a manifest storage backend the only consequence is that
    the source file is published alongside the build output. Silence it through
    ``SILENCED_SYSTEM_CHECKS`` if that is what you want.
    """
    try:
        offenders = find_src_css_in_static_dirs()
    except ValueError:
        # The configuration is unusable for other reasons, and the commands report that themselves.
        return []

    return [
        DjangoWarning(
            f"The Tailwind source CSS {src_css} lies inside the static files directory {static_dir}.",
            hint=(
                "collectstatic will collect it, and a manifest storage backend then fails to "
                'resolve the @import "tailwindcss"; it contains. Move the source CSS outside of '
                "STATICFILES_DIRS."
            ),
            id=SRC_CSS_IN_STATIC_DIR,
        )
        for src_css, static_dir in offenders
    ]
