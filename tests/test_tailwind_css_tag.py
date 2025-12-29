# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
import pytest
from django.conf import LazySettings
from django.template import engines


@pytest.fixture
def template_string():
    return "{% spaceless %}{% load tailwind_cli %}{% tailwind_css %}{% endspaceless %}"


def test_tailwind_css_tag_in_production(settings: LazySettings, template_string: str):
    settings.DEBUG = False
    template = engines["django"].from_string(template_string)
    assert (
        '<link rel="preload" href="/static/css/tailwind.css" as="style"><link rel="stylesheet" href="/static/css/tailwind.css">'  # noqa: E501
        == template.render({})
    )


def test_tailwind_css_tag_in_devmode(settings: LazySettings, template_string: str):
    settings.DEBUG = True
    template = engines["django"].from_string(template_string)
    assert '<link rel="stylesheet" href="/static/css/tailwind.css">' == template.render({})


def test_css_map_all_in_devmode(settings: LazySettings):
    settings.DEBUG = True
    settings.TAILWIND_CLI_CSS_MAP = [
        ("admin.css", "admin.output.css"),
        ("web.css", "web.output.css"),
    ]
    template = engines["django"].from_string(
        "{% spaceless %}{% load tailwind_cli %}{% tailwind_css %}{% endspaceless %}"
    )
    rendered = template.render({})
    assert '<link rel="stylesheet" href="/static/admin.output.css">' in rendered
    assert '<link rel="stylesheet" href="/static/web.output.css">' in rendered


def test_css_map_all_in_production(settings: LazySettings):
    settings.DEBUG = False
    settings.TAILWIND_CLI_CSS_MAP = [
        ("admin.css", "admin.output.css"),
        ("web.css", "web.output.css"),
    ]
    template = engines["django"].from_string(
        "{% spaceless %}{% load tailwind_cli %}{% tailwind_css %}{% endspaceless %}"
    )
    rendered = template.render({})
    assert '<link rel="preload" href="/static/admin.output.css" as="style">' in rendered
    assert '<link rel="stylesheet" href="/static/admin.output.css">' in rendered
    assert '<link rel="preload" href="/static/web.output.css" as="style">' in rendered
    assert '<link rel="stylesheet" href="/static/web.output.css">' in rendered


def test_css_map_specific_by_name(settings: LazySettings):
    settings.DEBUG = True
    settings.TAILWIND_CLI_CSS_MAP = [
        ("admin.css", "admin.output.css"),
        ("web.css", "web.output.css"),
    ]
    template = engines["django"].from_string(
        '{% spaceless %}{% load tailwind_cli %}{% tailwind_css "admin" %}{% endspaceless %}'
    )
    rendered = template.render({})
    assert '<link rel="stylesheet" href="/static/admin.output.css">' in rendered
    assert "web.output.css" not in rendered


def test_css_map_nonexistent_name(settings: LazySettings):
    settings.DEBUG = True
    settings.TAILWIND_CLI_CSS_MAP = [
        ("admin.css", "admin.output.css"),
        ("web.css", "web.output.css"),
    ]
    template = engines["django"].from_string(
        '{% spaceless %}{% load tailwind_cli %}{% tailwind_css "nonexistent" %}{% endspaceless %}'
    )
    rendered = template.render({})
    assert rendered == ""


def test_css_map_with_subdirectory(settings: LazySettings):
    settings.DEBUG = True
    settings.TAILWIND_CLI_CSS_MAP = [
        ("styles/admin.css", "css/admin.output.css"),
        ("styles/web.css", "css/web.output.css"),
    ]
    template = engines["django"].from_string(
        "{% spaceless %}{% load tailwind_cli %}{% tailwind_css %}{% endspaceless %}"
    )
    rendered = template.render({})
    assert '<link rel="stylesheet" href="/static/css/admin.output.css">' in rendered
    assert '<link rel="stylesheet" href="/static/css/web.output.css">' in rendered
