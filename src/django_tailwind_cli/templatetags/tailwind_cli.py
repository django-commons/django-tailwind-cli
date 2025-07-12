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

Available template tags:
    - tailwind_css: Includes the Tailwind CSS file with appropriate cache busting
"""

from django import template
from django.conf import settings

register = template.Library()


@register.inclusion_tag("tailwind_cli/tailwind_css.html")  # type: ignore
def tailwind_css() -> dict[str, bool | str]:
    """Include Tailwind CSS file in templates with debug-aware cache handling.

    This template tag automatically includes the Tailwind CSS file in your templates.
    It handles different behavior for development vs production:

    - **Development mode (DEBUG=True):** Includes CSS without cache headers for instant updates
    - **Production mode (DEBUG=False):** Includes CSS with cache-friendly headers

    The CSS file path is determined by the TAILWIND_CLI_DIST_CSS setting, with a sensible
    default of 'css/tailwind.css' relative to STATICFILES_DIRS[0].

    Returns:
        dict: Template context containing:
            - debug (bool): Whether Django is in debug mode
            - tailwind_dist_css (str): Path to the CSS file relative to static files

    Example:
        ```html
        {% load tailwind_cli %}
        <head>
            {% tailwind_css %}
        </head>
        ```

        This renders to:
        ```html
        <!-- In development -->
        <link rel="stylesheet" href="/static/css/tailwind.css">

        <!-- In production -->
        <link rel="stylesheet" href="/static/css/tailwind.css" media="screen">
        ```

    Configuration:
        - TAILWIND_CLI_DIST_CSS: Custom CSS file path (default: 'css/tailwind.css')
        - DEBUG: Controls cache behavior and development features
    """
    dist_css_base = getattr(settings, "TAILWIND_CLI_DIST_CSS", "css/tailwind.css")
    return {"debug": settings.DEBUG, "tailwind_dist_css": str(dist_css_base)}
