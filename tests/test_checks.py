"""Tests for the Django system checks."""

import pytest
from pytest_django import Settings
from pytest_mock import MockerFixture

from django.core.management import call_command
from django.core.management.base import BaseCommand

from django_tailwind_cli.checks import check_src_css_outside_static_dirs
from django_tailwind_cli.management.commands.tailwind import app


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


def test_a_subcommand_on_the_command_line_runs_the_system_checks(mocker: MockerFixture):
    """django-click skips Django's checks entirely, so the group has to run them itself.

    Without this, W001 would fire only on `manage.py check` and `runserver` — and nothing else in
    the suite would notice, because every other check test calls the function directly.
    """
    check = mocker.patch.object(BaseCommand, "check")

    app.run_from_argv(["manage.py", "tailwind", "config"])

    check.assert_called_once()


def test_call_command_skips_the_checks_as_django_does(mocker: MockerFixture):
    """`call_command` sets skip_checks=True unless told otherwise; this command is not special."""
    check = mocker.patch.object(BaseCommand, "check")

    call_command("tailwind", "config")

    check.assert_not_called()


def test_call_command_runs_the_checks_when_asked(mocker: MockerFixture):
    check = mocker.patch.object(BaseCommand, "check")

    call_command("tailwind", "config", skip_checks=False)

    check.assert_called_once()


def test_a_subcommand_help_screen_does_not_run_the_checks(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]):
    """`--help` is the one command reached for when a project is broken.

    Django never runs the checks for a help screen. click resolves a subcommand's `--help` while
    building that subcommand's context, which is after the group callback, so checks hung off the
    callback would kill `tailwind build --help` on a project whose checks fail.
    """
    check = mocker.patch.object(BaseCommand, "check")

    app.run_from_argv(["manage.py", "tailwind", "build", "--help"])

    assert "Usage:" in capsys.readouterr().out
    check.assert_not_called()


def test_skip_checks_on_the_command_line_skips_them(mocker: MockerFixture):
    """Every Django management command takes --skip-checks; django-click leaves it out."""
    check = mocker.patch.object(BaseCommand, "check")

    app.run_from_argv(["manage.py", "tailwind", "--skip-checks", "config"])

    check.assert_not_called()


def test_force_color_reaches_the_system_checks(mocker: MockerFixture):
    """The colour keywords have to survive `call_command`.

    django-click's --color callback runs while the context is built, but call_command pushes its
    keywords into the context afterwards, so the callback never sees them. Asserted through
    force_color, which cannot be true by accident: pytest's captured stdout is not a terminal, so
    an unstyled result is what every other path produces.
    """
    check = mocker.patch.object(BaseCommand, "check", autospec=True)

    call_command("tailwind", "config", skip_checks=False, force_color=True)

    command = check.call_args[0][0]
    assert command.style.ERROR("boom") != "boom"


def test_skip_checks_after_the_subcommand_skips_them(mocker: MockerFixture):
    """`manage.py <command> --skip-checks` is the spelling Django documents and every user knows.

    A group puts the option before the subcommand name, which nobody would guess.
    """
    check = mocker.patch.object(BaseCommand, "check")

    app.run_from_argv(["manage.py", "tailwind", "config", "--skip-checks"])

    check.assert_not_called()
