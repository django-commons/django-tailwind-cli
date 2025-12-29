"""Django template tags for Tailwind CSS integration.

This module provides template tags for including Tailwind CSS files in Django templates.
The tags automatically handle debug vs production modes and respect configuration settings.

Usage:
    In your Django template:

    ```html
    {% load tailwind_cli %}
    <!DOCTYPE html>
    <html>
    <head>
        <title>My App</title>
        {% tailwind_css %}
    </head>
    <body>
        <!-- Your content -->
    </body>
    </html>
    ```

    With multiple CSS entry points (TAILWIND_CLI_CSS_MAP):

    ```html
    {% load tailwind_cli %}
    <head>
        <!-- Include all CSS files -->
        {% tailwind_css %}

        <!-- Or include a specific CSS file by name -->
        {% tailwind_css "admin" %}
    </head>
    ```

Available template tags:
    - tailwind_css: Includes the Tailwind CSS file(s) with appropriate cache busting
"""

from django import template
from django.conf import settings

from django_tailwind_cli.config import get_config

register = template.Library()


@register.inclusion_tag("tailwind_cli/tailwind_css.html")  # type: ignore
def tailwind_css(name: str | None = None) -> dict[str, bool | list[str]]:
    """Include Tailwind CSS file(s) in templates with debug-aware cache handling.

    This template tag automatically includes the Tailwind CSS file(s) in your templates.
    It handles different behavior for development vs production:

    - **Development mode (DEBUG=True):** Includes CSS without cache headers for instant updates
    - **Production mode (DEBUG=False):** Includes CSS with cache-friendly headers

    Args:
        name: Optional name of specific CSS entry to include (for multi-file mode).
              If None, includes all CSS files (works for both single and multi-file modes).

    Returns:
        dict: Template context containing:
            - debug (bool): Whether Django is in debug mode
            - tailwind_css_files (list[str]): List of CSS file paths relative to static files

    Example:
        ```html
        {% load tailwind_cli %}
        <head>
            <!-- Include all CSS files -->
            {% tailwind_css %}

            <!-- Include specific CSS file (multi-file mode) -->
            {% tailwind_css "admin" %}
        </head>
        ```

        Single-file mode renders to:
        ```html
        <link rel="stylesheet" href="/static/css/tailwind.css">
        ```

        Multi-file mode (all files) renders to:
        ```html
        <link rel="stylesheet" href="/static/admin.output.css">
        <link rel="stylesheet" href="/static/web.output.css">
        ```

    Configuration:
        - TAILWIND_CLI_DIST_CSS: Single CSS file path (default: 'css/tailwind.css')
        - TAILWIND_CLI_CSS_MAP: List of (source, destination) tuples for multiple CSS files
        - DEBUG: Controls cache behavior and development features
    """
    config = get_config()

    if name:
        # Specific file requested - find matching entry
        for entry in config.css_entries:
            if entry.name == name:
                return {
                    "debug": settings.DEBUG,
                    "tailwind_css_files": [entry.dist_css_base],
                }
        # Name not found - return empty list
        return {"debug": settings.DEBUG, "tailwind_css_files": []}
    else:
        # All files
        return {
            "debug": settings.DEBUG,
            "tailwind_css_files": [entry.dist_css_base for entry in config.css_entries],
        }
