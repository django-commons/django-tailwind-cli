"""Django system checks for django-tailwind-cli.

Checks run on ``manage.py check``, on ``runserver``, and on every ``manage.py tailwind`` subcommand.
The last of those is not free: django-click skips Django's checks, so each subcommand runs them
itself (``TailwindCommand`` in ``management/commands/_group.py`` — deliberately not the group
callback, which would also check on ``tailwind COMMAND --help``). That covers the moments where a broken CSS
layout matters without putting the work on the template rendering path.
"""

from __future__ import annotations

import re
from typing import Any

from django.core.checks import Warning as DjangoWarning
from django.core.checks import register

from django.conf import settings

from django_tailwind_cli.config import (
    ConfigurationError,
    daisy_ui_directives,
    daisy_ui_plugin_reference,
    downloads_cli_extra,
    find_own_src_css,
    find_src_css_in_static_dirs,
)

SRC_CSS_IN_STATIC_DIR = "django_tailwind_cli.W001"
CLI_EXTRA_DEPRECATED = "django_tailwind_cli.W002"
BARE_DAISY_UI_PLUGIN = "django_tailwind_cli.W003"

_BARE_DAISY_UI_PLUGIN = re.compile(r"""@plugin\s+(["'])daisyui(?:/theme)?\1""")


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
    except ConfigurationError:
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


@register()
def check_cli_extra_deprecation(app_configs: Any, **kwargs: Any) -> list[DjangoWarning]:  # noqa: ARG001
    """Report a configuration that downloads tailwind-cli-extra."""
    try:
        extra = downloads_cli_extra()
    except ConfigurationError:
        # The commands report an invalid TAILWIND_CLI_DAISY_UI_SOURCE themselves.
        return []
    if not extra:
        return []

    return [
        DjangoWarning(
            "Loading daisyUI through tailwind-cli-extra is deprecated and will be removed.",
            hint=(
                'Set TAILWIND_CLI_DAISY_UI_SOURCE = "plugin" to use the official Tailwind CLI with '
                "daisyUI's plugin bundle. A source CSS of your own must then load the plugin by its path, "
                "which 'manage.py tailwind config' prints."
            ),
            id=CLI_EXTRA_DEPRECATED,
        )
    ]


@register()
def check_daisy_ui_plugin_reference(app_configs: Any, **kwargs: Any) -> list[DjangoWarning]:  # noqa: ARG001
    """Report an own source CSS that loads daisyUI by name while daisyUI is loaded as a plugin.

    Only tailwind-cli-extra resolves ``@plugin "daisyui"``. The official CLI fails with
    "Can't resolve 'daisyui'", which does not name the setting that caused it.
    The managed source CSS is skipped: the next build rewrites it.
    """
    if not getattr(settings, "TAILWIND_CLI_USE_DAISY_UI", False):
        return []
    try:
        if downloads_cli_extra():
            return []
        own_src_css = find_own_src_css()
    except ConfigurationError:
        return []

    warnings: list[DjangoWarning] = []
    for src_css in own_src_css:
        try:
            content = src_css.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _BARE_DAISY_UI_PLUGIN.search(content):
            continue
        plugin_dir = daisy_ui_plugin_reference(src_css.parent)
        source_not, plugin = daisy_ui_directives(plugin_dir)
        warnings.append(
            DjangoWarning(
                f"The Tailwind source CSS {src_css} loads daisyUI by name with @plugin.",
                hint=(
                    "The official Tailwind CLI cannot resolve that name. "
                    f'Replace @plugin "daisyui" with {plugin.rstrip(";")}. '
                    f'Replace @plugin "daisyui/theme" with @plugin "{plugin_dir}/daisyui-theme.mjs". '
                    "Keep the options. "
                    f"Add {source_not} so the bundles are not scanned."
                ),
                id=BARE_DAISY_UI_PLUGIN,
            )
        )
    return warnings
