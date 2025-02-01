"""Tailwind template tags."""

from typing import Union

from django import template
from django.conf import settings

from django_tailwind_cli import config

register = template.Library()


@register.inclusion_tag("tailwind_cli/tailwind_css.html")  # type: ignore
def tailwind_css() -> dict[str, Union[bool, str]]:
    """Template tag to include the css files into the html templates."""
    c = config.get_config()
    return {"debug": settings.DEBUG, "tailwind_dist_css": str(c.dist_css_base)}
