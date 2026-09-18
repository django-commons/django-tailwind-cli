# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture
from django.core.management import call_command
from django.core.management.base import CommandError
from django_tailwind_cli.config import ConfigurationError
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


@pytest.mark.parametrize("cache_state", ["missing", "expired"])
def test_render_does_not_look_up_latest_release(
    settings: LazySettings,
    template_string: str,
    version_cache_path: Path,
    mocker: MockerFixture,
    cache_state: str,
):
    settings.TAILWIND_CLI_VERSION = "latest"
    if cache_state == "expired":
        version_cache_path.write_text("tailwindlabs/tailwindcss\n4.1.3\n0\n")
    lookup = mocker.patch(
        "django_tailwind_cli.utils.http.fetch_redirect_location",
        return_value=(True, "https://github.com/tailwindlabs/tailwindcss/releases/tag/v4.2.7"),
    )

    rendered = engines["django"].from_string(template_string).render({})

    assert 'href="/static/css/tailwind.css"' in rendered
    lookup.assert_not_called()


def test_render_does_not_require_a_system_binary(
    settings: LazySettings,
    template_string: str,
    mocker: MockerFixture,
):
    settings.TAILWIND_CLI_VERSION = "4.1.3"
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    lookup = mocker.patch("django_tailwind_cli.config.shutil.which", return_value=None)

    rendered = engines["django"].from_string(template_string).render({})

    assert 'href="/static/css/tailwind.css"' in rendered
    lookup.assert_not_called()


@pytest.mark.parametrize(
    "setting",
    [
        "TAILWIND_CLI_ASSET_NAME",
        "TAILWIND_CLI_SRC_REPO",
        "TAILWIND_CLI_SYSTEM_BINARY_NAME",
    ],
)
def test_cli_configuration_errors_do_not_break_rendering(
    settings: LazySettings,
    template_string: str,
    setting: str,
):
    setattr(settings, setting, "")
    template = engines["django"].from_string(template_string)

    assert 'href="/static/css/tailwind.css"' in template.render({})
    with pytest.raises(CommandError, match=setting):
        call_command("tailwind", "build")


@pytest.mark.parametrize(
    "invalid_settings, message",
    [
        (
            {"TAILWIND_CLI_CSS_MAP": [("admin.css", "admin.out.css")], "TAILWIND_CLI_SRC_CSS": "source.css"},
            "Cannot use TAILWIND_CLI_CSS_MAP",
        ),
        ({"TAILWIND_CLI_CSS_MAP": [("admin.css", "out.css"), ("web.css", "out.css")]}, "duplicate destination"),
    ],
)
def test_render_still_rejects_invalid_css_settings(
    settings: LazySettings,
    template_string: str,
    invalid_settings: dict[str, Any],
    message: str,
):
    for name, value in invalid_settings.items():
        setattr(settings, name, value)

    with pytest.raises(ConfigurationError, match=message):
        engines["django"].from_string(template_string).render({})


def test_render_uses_static_storage_and_current_settings(
    settings: LazySettings,
    template_string: str,
    mocker: MockerFixture,
):
    settings.DEBUG = False
    storage_url = mocker.patch(
        "django.contrib.staticfiles.storage.staticfiles_storage.url",
        side_effect="https://static.example/{}?version=123".format,
    )
    template = engines["django"].from_string(template_string)
    assert 'href="https://static.example/css/tailwind.css?version=123"' in template.render({})

    settings.TAILWIND_CLI_DIST_CSS = "css/updated.css"
    assert 'href="https://static.example/css/updated.css?version=123"' in template.render({})
    storage_url.assert_called_with("css/updated.css")
