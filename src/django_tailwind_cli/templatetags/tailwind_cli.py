"""Tailwind template tags."""

from typing import Union

from django import template
from django.conf import settings

register = template.Library()


@register.inclusion_tag("tailwind_cli/tailwind_css.html")  # type: ignore
def tailwind_css() -> dict[str, Union[bool, str]]:
    """Template tag to include the css files into the html templates."""
    dist_css_base = getattr(settings, "TAILWIND_CLI_DIST_CSS", "css/tailwind.css")
    return {"debug": settings.DEBUG, "tailwind_dist_css": str(dist_css_base)}
