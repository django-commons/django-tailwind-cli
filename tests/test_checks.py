"""Tests for the Django system checks."""

import pytest
from pytest_django import Settings
from pytest_mock import MockerFixture

from django_tailwind_cli.checks import check_src_css_outside_static_dirs


pytestmark = pytest.mark.usefixtures("fake_project_settings")


def test_default_configuration_passes():
    """The managed default source CSS lives outside the static directories."""
    assert check_src_css_outside_static_dirs(app_configs=None) == []


def test_src_css_inside_staticfiles_dir_is_reported(settings: Settings):
    settings.TAILWIND_CLI_SRC_CSS = "assets/css/source.css"

    errors = check_src_css_outside_static_dirs(app_configs=None)

    assert len(errors) == 1
    assert errors[0].id == "django_tailwind_cli.W001"
    assert errors[0].msg == (
        "The Tailwind source CSS /home/user/project/assets/css/source.css lies inside the "
        "static files directory /home/user/project/assets."
    )


def test_src_css_outside_staticfiles_dir_passes(settings: Settings):
    settings.TAILWIND_CLI_SRC_CSS = "styles/source.css"

    assert check_src_css_outside_static_dirs(app_configs=None) == []


def test_second_staticfiles_dir_is_checked(settings: Settings):
    settings.STATICFILES_DIRS = (
        settings.BASE_DIR / "assets",
        settings.BASE_DIR / "vendor",
    )
    settings.TAILWIND_CLI_SRC_CSS = "vendor/source.css"

    assert len(check_src_css_outside_static_dirs(app_configs=None)) == 1


def test_prefixed_staticfiles_dir_entry_is_checked(settings: Settings):
    settings.STATICFILES_DIRS = (
        settings.BASE_DIR / "assets",
        ("vendor", str(settings.BASE_DIR / "vendor")),
    )
    settings.TAILWIND_CLI_SRC_CSS = "vendor/source.css"

    assert len(check_src_css_outside_static_dirs(app_configs=None)) == 1


def test_list_form_staticfiles_dir_entry_is_checked(settings: Settings):
    settings.STATICFILES_DIRS = [
        settings.BASE_DIR / "assets",
        ["vendor", str(settings.BASE_DIR / "vendor")],
    ]
    settings.TAILWIND_CLI_SRC_CSS = "vendor/source.css"

    assert len(check_src_css_outside_static_dirs(app_configs=None)) == 1


def test_relative_staticfiles_dir_entry_is_checked(settings: Settings, mocker: MockerFixture):
    """Django resolves a relative entry against the working directory."""
    mocker.patch("os.getcwd", return_value=str(settings.BASE_DIR))
    settings.STATICFILES_DIRS = ["assets"]
    settings.TAILWIND_CLI_SRC_CSS = "assets/source.css"

    assert len(check_src_css_outside_static_dirs(app_configs=None)) == 1


def test_every_css_map_source_is_reported(settings: Settings):
    settings.TAILWIND_CLI_CSS_MAP = [
        ("styles/admin.css", "admin.output.css"),
        ("assets/web.css", "web.output.css"),
        ("assets/shop.css", "shop.output.css"),
    ]

    errors = check_src_css_outside_static_dirs(app_configs=None)

    assert len(errors) == 2
    assert all(e.id == "django_tailwind_cli.W001" for e in errors)


def test_dist_css_does_not_trigger_the_check(settings: Settings):
    """The build output always lives in a static directory — only the source may not."""
    settings.TAILWIND_CLI_DIST_CSS = "css/tailwind.css"

    assert check_src_css_outside_static_dirs(app_configs=None) == []


def test_a_real_bug_is_not_swallowed(mocker: MockerFixture):
    """The guard exists for misconfiguration; a genuine ValueError must still reach `manage.py check`."""
    mocker.patch(
        "django_tailwind_cli.checks.find_src_css_in_static_dirs",
        side_effect=ValueError("something went wrong resolving a path"),
    )

    with pytest.raises(ValueError, match="resolving a path"):
        check_src_css_outside_static_dirs(app_configs=None)


def test_broken_configuration_is_left_to_the_commands(settings: Settings):
    """An unusable configuration raises elsewhere; the check must not mask it with its own error."""
    settings.STATICFILES_DIRS = []

    assert check_src_css_outside_static_dirs(app_configs=None) == []


def test_rendering_the_template_tag_emits_no_warning(settings: Settings, recwarn: pytest.WarningsRecorder):
    """The check replaced a warning that fired on every render."""
    from django.template import Context, Template

    settings.TAILWIND_CLI_SRC_CSS = "assets/css/source.css"

    rendered = Template("{% load tailwind_cli %}{% tailwind_css %}").render(Context({}))

    assert "css/tailwind.css" in rendered
    assert [w for w in recwarn.list if "static files directory" in str(w.message)] == []
