"""Tests for additional management commands with missing coverage.

This file focuses on testing commands that were missing from the main test suite,
specifically targeting the config, troubleshoot, and optimize commands.
Also includes tests for error handling and edge cases.
"""

import io
from pathlib import Path

from functools import partial

import click
import pytest
from django.conf import LazySettings
from django.core.management import CommandError, call_command
from pytest import CaptureFixture
from pytest_mock import MockerFixture

from django_tailwind_cli.config import get_config
from django_tailwind_cli.management.commands._group import TailwindCommand, TailwindGroup, keyword_argv
from django_tailwind_cli.management.commands.tailwind import app, handle_command_errors
from tests.helpers import write_fake_cli


@pytest.fixture(autouse=True)
def configure_test_settings(tmp_project: Path, settings: LazySettings, mocker: MockerFixture):
    """Configure settings for all tests in this module."""
    # Outside STATICFILES_DIRS on purpose — a source CSS below it warns, see config.py.
    settings.TAILWIND_CLI_SRC_CSS = tmp_project / "css" / "input.css"
    settings.TAILWIND_CLI_USE_DAISY_UI = False
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True

    # Mock subprocess to avoid actual CLI calls
    mocker.patch("subprocess.run")

    mocker.patch(
        "django_tailwind_cli.utils.http.download_with_progress",
        side_effect=partial(write_fake_cli, content=b"fake binary content"),
    )


class TestConfigCommand:
    """Test the config command that displays configuration information."""

    def test_config_command_basic_output(self, capsys: CaptureFixture[str]):
        """Test that config command displays basic configuration information."""
        call_command("tailwind", "config")
        captured = capsys.readouterr()

        # Check for main sections
        assert "🔧 Django Tailwind CLI Configuration" in captured.out
        assert "📦 Version Information:" in captured.out
        assert "📁 File Paths:" in captured.out
        assert "⚙️ Django Settings:" in captured.out
        assert "💻 Platform Information:" in captured.out
        assert "🔗 Command URLs:" in captured.out
        assert "📊 Status Summary:" in captured.out

    def test_config_command_version_info(self, capsys: CaptureFixture[str]):
        """Test that config command shows version information."""
        call_command("tailwind", "config")
        captured = capsys.readouterr()

        assert "Tailwind CSS Version: 4.0.0" in captured.out
        assert "DaisyUI Enabled: No" in captured.out
        assert "Auto Download: Yes" in captured.out

    def test_config_command_with_daisy_ui(self, settings: LazySettings, capsys: CaptureFixture[str]):
        """Test config command shows correct DaisyUI status when enabled."""
        settings.TAILWIND_CLI_USE_DAISY_UI = True
        call_command("tailwind", "config")
        captured = capsys.readouterr()

        assert "DaisyUI Enabled: Yes" in captured.out

    def test_config_command_with_auto_download_disabled(self, settings: LazySettings, capsys: CaptureFixture[str]):
        """Test config command shows correct auto download status when disabled."""
        settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
        call_command("tailwind", "config")
        captured = capsys.readouterr()

        assert "Auto Download: No" in captured.out

    def test_config_command_file_paths(self, capsys: CaptureFixture[str]):
        """Test that config command shows file paths and existence status."""
        config = get_config()

        # Create some files to test existence checks
        config.src_css.parent.mkdir(parents=True, exist_ok=True)
        config.src_css.write_text("@import 'tailwindcss';")

        call_command("tailwind", "config")
        captured = capsys.readouterr()

        assert "CLI Binary:" in captured.out
        assert "CSS Entries" in captured.out
        assert "Source:" in captured.out
        assert "Output:" in captured.out
        assert "✅" in captured.out  # At least one file exists
        assert "❌" in captured.out  # Some files don't exist

    def test_config_command_django_settings(self, settings: LazySettings, capsys: CaptureFixture[str]):
        """Test that config command displays Django settings."""
        settings.TAILWIND_CLI_PATH = "/custom/path"
        settings.TAILWIND_CLI_SRC_CSS = "custom/input.css"
        settings.TAILWIND_CLI_DIST_CSS = "custom/output.css"

        call_command("tailwind", "config")
        captured = capsys.readouterr()

        assert "STATICFILES_DIRS:" in captured.out
        assert "TAILWIND_CLI_VERSION: 4.0.0" in captured.out
        assert "TAILWIND_CLI_PATH: /custom/path" in captured.out
        assert "TAILWIND_CLI_SRC_CSS: custom/input.css" in captured.out
        assert "TAILWIND_CLI_DIST_CSS: custom/output.css" in captured.out

    def test_config_command_platform_info(self, capsys: CaptureFixture[str]):
        """Test that config command displays platform information."""
        call_command("tailwind", "config")
        captured = capsys.readouterr()

        assert "Operating System:" in captured.out
        assert "Architecture:" in captured.out
        assert "Binary Extension:" in captured.out

    def test_config_command_download_url(self, capsys: CaptureFixture[str]):
        """Test that config command displays download URL."""
        call_command("tailwind", "config")
        captured = capsys.readouterr()

        assert "Download URL:" in captured.out
        assert "github.com" in captured.out

    def test_config_command_status_summary_ready(self, capsys: CaptureFixture[str]):
        """Test config command shows ready status when files exist."""
        config = get_config()

        # Create CLI binary and source CSS
        config.cli_path.parent.mkdir(parents=True, exist_ok=True)
        config.cli_path.write_text("fake binary")
        config.src_css.parent.mkdir(parents=True, exist_ok=True)
        config.src_css.write_text("@import 'tailwindcss';")

        call_command("tailwind", "config")
        captured = capsys.readouterr()

        assert "✅ Ready to build CSS" in captured.out

    def test_config_command_status_summary_setup_required(self, capsys: CaptureFixture[str]):
        """Test config command shows setup required when files missing."""
        call_command("tailwind", "config")
        captured = capsys.readouterr()

        assert "⚠️  Setup required" in captured.out
        assert "python manage.py tailwind download_cli" in captured.out
        assert "python manage.py tailwind build" in captured.out


class TestTroubleshootCommand:
    """Test the troubleshoot command that provides debugging help."""

    def test_troubleshoot_command_basic_output(self, capsys: CaptureFixture[str]):
        """Test that troubleshoot command displays help information."""
        call_command("tailwind", "troubleshoot")
        captured = capsys.readouterr()

        # Check for main troubleshooting sections
        assert "🔍 Django Tailwind CLI Troubleshooting Guide" in captured.out
        assert "❓ Issue 1: CSS not updating in browser" in captured.out
        assert "❓ Issue 2: Build/watch command fails" in captured.out
        assert "🔧 Diagnostic Commands" in captured.out

    def test_troubleshoot_covers_the_collectstatic_manifest_failure(self, capsys: CaptureFixture[str]):
        """The most common deployment failure has to be findable by its error string."""
        call_command("tailwind", "troubleshoot")
        captured = capsys.readouterr()

        assert "Missing staticfiles manifest entry" in captured.out
        assert "python manage.py tailwind build" in captured.out
        assert "python manage.py collectstatic --noinput" in captured.out


class TestSetupCommand:
    """Test the setup guide."""

    def test_setup_guide_spells_out_the_production_order(self, capsys: CaptureFixture[str], mocker: MockerFixture):
        """A build that runs after collectstatic leaves the manifest without an entry."""
        # The guide only reaches its closing steps when the trial build succeeds.
        mocker.patch("subprocess.run", return_value=mocker.Mock(returncode=0, stderr=""))

        call_command("tailwind", "setup")
        captured = capsys.readouterr()

        assert "python manage.py tailwind build" in captured.out
        assert "python manage.py collectstatic --noinput" in captured.out


class TestOptimizeCommand:
    """Test the optimize command that provides performance tips."""

    def test_optimize_command_basic_output(self, capsys: CaptureFixture[str]):
        """Test that optimize command displays optimization tips."""
        call_command("tailwind", "optimize")
        captured = capsys.readouterr()

        # Check for optimization content
        assert "⚡ Django Tailwind CLI Performance Optimization" in captured.out
        assert "🏗️ Build Performance" in captured.out
        assert "👀 File Watching Efficiency" in captured.out
        assert "🚀 Production Deployment" in captured.out


@pytest.mark.usefixtures("bypass_autoreload")
class TestErrorHandling:
    """Test error handling decorator and error scenarios."""

    def test_handle_command_errors_decorator_command_error(self, mocker: MockerFixture):
        """The hint is printed, then the failure continues as a CommandError for Django to render."""
        mock_secho = mocker.patch("click.secho")

        @handle_command_errors
        def failing_function():
            raise CommandError("Test command error")

        with pytest.raises(CommandError):
            failing_function()

        assert [c for c in mock_secho.call_args_list if "❌ Command error:" in str(c)]

    def test_handle_command_errors_decorator_file_not_found(self, mocker: MockerFixture):
        """The hint is printed, then the failure continues as a CommandError for Django to render."""
        mock_secho = mocker.patch("click.secho")

        @handle_command_errors
        def failing_function():
            raise FileNotFoundError("Test file not found")

        with pytest.raises(CommandError):
            failing_function()

        assert [c for c in mock_secho.call_args_list if "❌ File not found:" in str(c)]

    def test_handle_command_errors_decorator_permission_error(self, mocker: MockerFixture):
        """The hint is printed, then the failure continues as a CommandError for Django to render."""
        mock_secho = mocker.patch("click.secho")

        @handle_command_errors
        def failing_function():
            raise PermissionError("Test permission denied")

        with pytest.raises(CommandError):
            failing_function()

        assert [c for c in mock_secho.call_args_list if "❌ Permission denied:" in str(c)]

    def test_click_control_flow_is_not_announced_as_an_error(self, capsys: CaptureFixture[str]):
        """`ctx.exit()` is a normal exit; it used to be reported as "❌ Unexpected error: Exit: 0"."""

        @handle_command_errors
        def exiting_function():
            raise click.exceptions.Exit(0)

        with pytest.raises(click.exceptions.Exit):
            exiting_function()

        assert capsys.readouterr().err == ""

    def test_handle_command_errors_decorator_generic_exception(self, mocker: MockerFixture):
        """A bug is not a user error: the hint is printed, the exception keeps its type."""
        mock_secho = mocker.patch("click.secho")

        @handle_command_errors
        def failing_function():
            raise ValueError("Test generic error")

        with pytest.raises(ValueError):
            failing_function()

        assert [c for c in mock_secho.call_args_list if "❌ Unexpected error:" in str(c)]

    def test_handle_command_errors_decorator_success(self, mocker: MockerFixture):
        """Test error decorator doesn't interfere with successful execution."""
        mock_exit = mocker.patch("sys.exit")

        @handle_command_errors
        def successful_function():
            return "success"

        result = successful_function()

        assert result == "success"
        mock_exit.assert_not_called()

    def test_build_verbose_flag(self, capsys: CaptureFixture[str]):
        """Test build command with verbose flag shows additional output."""
        config = get_config()
        config.cli_path.parent.mkdir(parents=True, exist_ok=True)
        config.cli_path.write_text("fake binary")

        call_command("tailwind", "build", "--verbose")
        captured = capsys.readouterr()

        # Should show verbose output about build process
        assert "Built production stylesheet" in captured.out

    def test_watch_verbose_flag(self, capsys: CaptureFixture[str]):
        """Test watch command with verbose flag shows additional output."""
        config = get_config()
        config.cli_path.parent.mkdir(parents=True, exist_ok=True)
        config.cli_path.write_text("fake binary")

        call_command("tailwind", "watch", "--verbose")
        captured = capsys.readouterr()

        # Should show verbose output about watching process
        assert "Watching for changes" in captured.out or "watch" in captured.out.lower()


class TestCommandErrorHandlingIsWiredUp:
    """handle_command_errors has to sit between click and the command, not beside it."""

    def test_every_command_has_the_decorator_inside_the_click_registration(self):
        """The original bug was a decorator stacked the wrong way round, on eight commands at once.

        A test that drives one command pins one command; this pins the shape for all of them.
        The marker is checked rather than plain wrapping, because click.pass_context wraps too —
        runserver would otherwise look decorated when it is not.
        """
        from django_tailwind_cli.management.commands.tailwind import app

        undecorated = sorted(
            name
            for name, command in app.commands.items()
            if command.callback is not None and not getattr(command.callback, "handles_command_errors", False)
        )

        assert undecorated == ["runserver"], (
            "runserver is deliberately undecorated — it raises CommandError with its own remedy. "
            f"Anything else here lost handle_command_errors: {undecorated}"
        )

    @pytest.mark.parametrize(
        "raised, heading, expected",
        [
            # A user error continues as a CommandError, which Django renders as one line.
            (CommandError("STATICFILES_DIRS is empty"), "❌ Command error:", CommandError),
            (FileNotFoundError("tailwindcss missing"), "❌ File not found:", CommandError),
            (PermissionError("cannot write"), "❌ Permission denied:", CommandError),
            # A bug keeps its type and its traceback, so it stays reportable.
            (RuntimeError("something else"), "❌ Unexpected error:", RuntimeError),
        ],
    )
    def test_a_failing_command_reports_and_reraises(
        self,
        mocker: MockerFixture,
        capsys: CaptureFixture[str],
        raised: Exception,
        heading: str,
        expected: type[Exception],
    ):
        """Driven through call_command, so the decorator order is what is under test."""
        mocker.patch("django_tailwind_cli.management.commands._guides.get_config", side_effect=raised)

        with pytest.raises(expected):
            call_command("tailwind", "config")

        assert heading in capsys.readouterr().err


class TestCallCommandKeywordOptions:
    """`call_command` accepts options as keywords, not only as positional strings.

    Django supports both spellings and this package did too under django-typer, verified against
    that tree. django-click pushes every keyword into the *group's* context, where a subcommand's
    option is unknown and Django's own options crash the group callback — so both directions need
    restoring, and the whole existing suite passes options positionally and would not notice.
    """

    def test_a_subcommand_flag_passed_as_a_keyword_takes_effect(self, capsys: CaptureFixture[str]):
        """Not merely accepted — it has to actually reach the command."""
        call_command("tailwind", "build", verbose=True)

        assert "Starting Tailwind CSS build process" in capsys.readouterr().out

    def test_a_subcommand_flag_left_out_stays_off(self, capsys: CaptureFixture[str]):
        call_command("tailwind", "build")

        assert "Starting Tailwind CSS build process" not in capsys.readouterr().out

    @pytest.mark.parametrize(
        "option",
        [
            {"verbosity": 0},
            {"traceback": True},
            {"color": False},
            {"no_color": True},
            {"force_color": True},
            {"stdout": io.StringIO()},
            {"stderr": io.StringIO()},
        ],
    )
    def test_djangos_own_options_do_not_crash_the_group(self, option: dict[str, object]):
        """`verbosity=0` is the common one — deploy scripts and other suites pass it routinely.

        The list is Django's own `base_stealth_options` plus the parsed options every management
        command carries; all seven were accepted under django-typer.
        """
        call_command("tailwind", "config", **option)

    def test_output_goes_to_a_supplied_stdout(self):
        """Accepting `stdout` and then writing past it would be the silent drop this class exists
        to prevent, so it is redirected rather than swallowed."""
        buffer = io.StringIO()

        call_command("tailwind", "config", stdout=buffer)

        assert "Django Tailwind CLI Configuration" in buffer.getvalue()

    def test_djangos_group_options_reach_the_click_context(self, mocker: MockerFixture):
        """Not merely accepted — they have to arrive.

        `call_command` pushes its keywords into the context *after* django-click has built it, so
        an option whose only effect is a parse callback is inert unless it goes back through argv.
        """
        seen: dict[str, object] = {}
        original = TailwindGroup.invoke

        def record(self: TailwindGroup, ctx: click.Context):
            # django-click records both on the context in a parse callback, so they are untyped
            # attributes rather than declared ones.
            seen["traceback"] = getattr(ctx, "traceback")  # noqa: B009
            seen["verbosity"] = getattr(ctx, "verbosity")  # noqa: B009
            return original(self, ctx)

        mocker.patch.object(TailwindGroup, "invoke", record)

        call_command("tailwind", "config", traceback=True, verbosity=0)

        assert seen == {"traceback": True, "verbosity": 0}

    def test_the_negative_spelling_of_a_flag_is_accepted(self):
        """`no_color` worked only because it was hand-listed; `no_traceback` is the same shape."""
        call_command("tailwind", "config", no_traceback=True)

    def test_a_group_option_value_does_not_shadow_the_subcommand(self, capsys: CaptureFixture[str]):
        """`settings="config"` names a settings module; `config` is also a subcommand.

        The routed group options are prepended to argv, so scanning all of argv for a command name
        finds the *value* and routes the caller's options to a command they never asked for.
        """
        call_command("tailwind", "build", settings="config", verbose=True)

        assert "Starting Tailwind CSS build process" in capsys.readouterr().out

    def test_a_keyword_belonging_to_another_subcommand_is_refused(self):
        """`verbose` is an option of `build`, not of `config`.

        Django's guard passes it, because the group reports every subcommand's options as valid,
        and the router then has nowhere to put it. Refusing beats dropping it in silence.
        """
        with pytest.raises(TypeError, match="verbose") as excinfo:
            call_command("tailwind", "config", verbose=True)

        # The message has to name what *is* valid; `config` carries only the standard --skip-checks.
        assert str(excinfo.value).endswith("Valid options are: skip_checks.")


def test_group_options_are_spelled_back_as_argv():
    """The one mechanism behind both directions: a keyword name, its negative spelling, and the
    argv click's own parser would have read."""
    kwargs: dict[str, object] = {"verbosity": 0, "no_traceback": True, "force_color": True}

    argv = keyword_argv(app.params, kwargs)

    assert argv == ["-v", "0", "--no-traceback", "--force-color"]
    assert kwargs == {}


def test_every_subcommand_is_a_tailwind_command():
    """The system checks hang off `TailwindCommand`, installed via click's `Group.command_class`.

    That attribute arrived in click 8.0. On an older click every subcommand would quietly be a
    plain `click.Command` and the checks would stop running with nothing to show for it, which is
    why `click>=8.0` is declared rather than left to django-click's `click>=7.1`.
    """
    assert app.commands
    assert [c for c in app.commands.values() if not isinstance(c, TailwindCommand)] == []
