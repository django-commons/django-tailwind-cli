"""Improved management commands tests with better performance and reliability.

This file replaces test_management_commands.py to fix hanging/slowness issues
by implementing better mocking strategies, timeouts, and process management.
"""
# pyright: reportPrivateUsage=false

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from functools import partial

import pytest
from django.apps import apps
from django.conf import LazySettings
from django.core.management import CommandError, call_command
from pytest import CaptureFixture
from pytest_mock import MockerFixture

from semver import Version

from django_tailwind_cli.config import get_config, managed_dir
from django_tailwind_cli.management.commands._process import LIFELINE_ENV
from django_tailwind_cli.management.commands.tailwind import _run_watch_loop_in_reloader_child
from django_tailwind_cli.management.commands._source_css import (
    AUTO_SOURCE_COMMENT,
    DAISY_UI_SOURCE_CSS,
    DEFAULT_SOURCE_CSS,
    ensure_source_css,
)
from tests.helpers import install_fake_cli, write_fake_cli


class TestFastCommands:
    """Fast tests that don't involve process management."""

    @pytest.fixture(autouse=True)
    def setup_fast_tests(self, tmp_project: Path, settings: LazySettings, mocker: MockerFixture):
        """Lightweight setup for fast tests."""
        settings.TAILWIND_CLI_SRC_CSS = tmp_project / "source.css"

        # Mock only what's necessary for fast tests
        mocker.patch("subprocess.run")

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli)

    def test_calling_unknown_subcommand(self):
        """Test handling of unknown subcommands."""
        with pytest.raises(CommandError, match="No such command 'not_a_valid_command'"):
            call_command("tailwind", "not_a_valid_command")

    @pytest.mark.parametrize("use_daisy_ui", [True, False])
    def test_create_src_css_if_non_exists(self, settings: LazySettings, use_daisy_ui: bool):
        """Test CSS source file creation."""
        settings.TAILWIND_CLI_USE_DAISY_UI = use_daisy_ui
        c = get_config()
        assert c.src_css is not None
        assert not c.src_css.exists()

        call_command("tailwind", "build")

        assert c.src_css.exists()
        expected_content = DAISY_UI_SOURCE_CSS if use_daisy_ui else DEFAULT_SOURCE_CSS
        assert expected_content == c.src_css.read_text()

    def test_download_cli_basic(self):
        """Test basic CLI download functionality."""
        c = get_config()
        assert not c.cli_path.exists()

        call_command("tailwind", "download_cli")

        assert c.cli_path.exists()

    def test_remove_cli_commands(self, capsys: CaptureFixture[str]):
        """Test CLI removal functionality."""
        c = get_config()

        # Test removing non-existent CLI
        call_command("tailwind", "remove_cli")
        captured = capsys.readouterr()
        assert "Tailwind CSS CLI not found at" in captured.out

        # Test removing existing CLI
        c.cli_path.parent.mkdir(parents=True, exist_ok=True)
        c.cli_path.write_text("fake cli")

        call_command("tailwind", "remove_cli")
        captured = capsys.readouterr()
        assert "Removed Tailwind CSS CLI at" in captured.out
        assert not c.cli_path.exists()


class TestSystemBinaryMode:
    """Tests for TAILWIND_CLI_USE_SYSTEM_BINARY behaviour at the command layer."""

    @pytest.fixture(autouse=True)
    def setup_system_binary(
        self,
        settings: LazySettings,
        tmp_path: Path,
        mocker: MockerFixture,
    ):
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
        settings.TAILWIND_CLI_SRC_CSS = tmp_path / "source.css"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        # Create a fake "system binary" and have shutil.which return it
        fake_binary = tmp_path / "bin" / "tailwindcss"
        fake_binary.parent.mkdir(parents=True, exist_ok=True)
        fake_binary.write_text("#!/bin/sh\nexit 0\n")
        fake_binary.chmod(0o755)
        mocker.patch("shutil.which", return_value=str(fake_binary))

        # Mock subprocess so no real commands run
        mocker.patch("subprocess.run")
        mocker.patch("django_tailwind_cli.config.detect_binary_version", return_value=None)

        # Mock the download function — if it gets called, the test has regressed
        self.mock_download = mocker.patch("django_tailwind_cli.utils.http.download_with_progress")
        self.fake_binary = fake_binary

    def test_download_cli_is_skipped_in_system_mode(self, capsys: CaptureFixture[str]):
        """download_cli should not hit the network when using a system binary."""
        call_command("tailwind", "download_cli")

        # No download happened
        self.mock_download.assert_not_called()
        # User gets a friendly message instead
        captured = capsys.readouterr()
        assert "system" in captured.out.lower()

    def test_build_skips_download_in_system_mode(self):
        """tailwind build should not trigger a download in system binary mode."""
        call_command("tailwind", "build")

        self.mock_download.assert_not_called()

    def test_remove_cli_refuses_system_binary(self, capsys: CaptureFixture[str]):
        """remove_cli must not delete a system-installed binary."""
        call_command("tailwind", "remove_cli")

        # The binary must still exist — we did not install it and must not remove it.
        assert self.fake_binary.exists()
        captured = capsys.readouterr()
        assert "system" in captured.out.lower()

    def test_config_command_reports_system_binary_origin(self, capsys: CaptureFixture[str]):
        """`tailwind config` should indicate that a system binary is in use."""
        call_command("tailwind", "config")

        captured = capsys.readouterr()
        assert "system binary" in captured.out.lower()


class TestSubprocessCommands:
    """Tests for commands that involve subprocess calls - with better mocking."""

    @pytest.fixture(autouse=True)
    def setup_subprocess_tests(
        self,
        tmp_project: Path,
        settings: LazySettings,
        mocker: MockerFixture,
        bypass_autoreload: None,  # noqa: ARG002  (requested for its side effect)
    ):
        """Setup with comprehensive subprocess mocking."""
        settings.TAILWIND_CLI_SRC_CSS = tmp_project / "source.css"

        # Mock all subprocess-related calls comprehensively
        self.mock_subprocess_run = mocker.patch("subprocess.run")
        self.mock_subprocess_popen = mocker.patch("subprocess.Popen")

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli)

        # Configure Popen mock to return immediately
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 0
        mock_process.terminate.return_value = None
        mock_process.kill.return_value = None
        mock_process.returncode = 0
        mock_process.stderr = None  # skip the stderr drain thread
        self.mock_subprocess_popen.return_value = mock_process

    @pytest.mark.timeout(5)  # Prevent hanging
    def test_build_subprocess_calls(self):
        """Test build command subprocess behavior."""
        call_command("tailwind", "build")

        # Verify subprocess.run was called
        assert self.mock_subprocess_run.call_count >= 1

    @pytest.mark.timeout(5)
    def test_build_minifies_by_default(self):
        """Build command includes --minify by default."""
        call_command("tailwind", "build")
        cmd = self.mock_subprocess_run.call_args_list[-1].args[0]
        assert "--minify" in cmd

    @pytest.mark.timeout(5)
    def test_build_respects_automatic_minify_setting_true(self, settings: LazySettings):
        """TAILWIND_CLI_AUTOMATIC_MINIFY=True explicitly set still minifies."""
        settings.TAILWIND_CLI_AUTOMATIC_MINIFY = True
        call_command("tailwind", "build")
        cmd = self.mock_subprocess_run.call_args_list[-1].args[0]
        assert "--minify" in cmd

    @pytest.mark.timeout(5)
    def test_build_respects_automatic_minify_setting(self, settings: LazySettings):
        """TAILWIND_CLI_AUTOMATIC_MINIFY=False disables minification."""
        settings.TAILWIND_CLI_AUTOMATIC_MINIFY = False
        call_command("tailwind", "build")
        cmd = self.mock_subprocess_run.call_args_list[-1].args[0]
        assert "--minify" not in cmd

    @pytest.mark.timeout(5)
    def test_build_no_minify_flag_overrides_setting(self, settings: LazySettings):
        """--no-minify CLI flag overrides the setting."""
        settings.TAILWIND_CLI_AUTOMATIC_MINIFY = True
        call_command("tailwind", "build", "--no-minify")
        cmd = self.mock_subprocess_run.call_args_list[-1].args[0]
        assert "--minify" not in cmd

    @pytest.mark.timeout(5)
    def test_build_minify_flag_overrides_setting(self, settings: LazySettings):
        """--minify CLI flag overrides TAILWIND_CLI_AUTOMATIC_MINIFY=False."""
        settings.TAILWIND_CLI_AUTOMATIC_MINIFY = False
        call_command("tailwind", "build", "--minify")
        cmd = self.mock_subprocess_run.call_args_list[-1].args[0]
        assert "--minify" in cmd

    @pytest.mark.timeout(5)
    def test_build_with_keyboard_interrupt(self, capsys: CaptureFixture[str]):
        """Test build command handling of KeyboardInterrupt."""
        self.mock_subprocess_run.side_effect = KeyboardInterrupt

        call_command("tailwind", "build")
        captured = capsys.readouterr()
        assert "Canceled building production stylesheet." in captured.out

    @pytest.mark.timeout(5)
    def test_watch_subprocess_calls(self):
        """One stylesheet gets one watcher process."""
        self.mock_subprocess_popen.return_value.poll.return_value = 0

        call_command("tailwind", "watch")

        self.mock_subprocess_popen.assert_called_once()
        assert "--watch" in self.mock_subprocess_popen.call_args.args[0]

    @pytest.mark.timeout(5)
    def test_watch_streams_output(self):
        """The watcher writes rebuilds straight to the terminal; a captured stdout would never be shown."""
        self.mock_subprocess_popen.return_value.poll.return_value = 0

        call_command("tailwind", "watch")

        assert "stdout" not in self.mock_subprocess_popen.call_args.kwargs

    @pytest.mark.timeout(5)
    def test_watch_with_keyboard_interrupt(self, capsys: CaptureFixture[str]):
        """Test watch command handling of KeyboardInterrupt."""
        self.mock_subprocess_popen.side_effect = KeyboardInterrupt

        call_command("tailwind", "watch")
        captured = capsys.readouterr()
        assert "Stopped watching for changes." in captured.out


class TestProcessManagementCommands:
    """Tests for commands involving process management - heavily mocked."""

    @pytest.fixture(autouse=True)
    def setup_process_tests(self, tmp_project: Path, mocker: MockerFixture):
        """Setup with complete process mocking."""
        # runserver shells out to `python manage.py ...` and checks for it first.
        (tmp_project / "manage.py").touch()

        # Mock ALL process-related functionality
        mocker.patch("subprocess.run")
        mocker.patch("subprocess.Popen")

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli)

        # Mock the ProcessManager entirely to prevent real process creation
        self.mock_process_manager = mocker.patch("django_tailwind_cli.management.commands.tailwind.ProcessManager")
        mock_manager_instance = Mock()
        mock_manager_instance.start_concurrent_processes.return_value = None
        self.mock_process_manager.return_value = mock_manager_instance

        # Mock importlib checks for django-extensions
        self.mock_find_spec = mocker.patch("importlib.util.find_spec")

    @pytest.mark.timeout(3)
    def test_runserver_without_manage_py_says_so_instead_of_spawning(self, tmp_path: Path):
        """Both spawned commands are `python manage.py ...`; without it they fail after the fact."""
        (tmp_path / "manage.py").unlink()

        with pytest.raises(CommandError) as excinfo:
            call_command("tailwind", "runserver")

        assert str(tmp_path / "manage.py") in str(excinfo.value)
        assert "tailwind watch" in str(excinfo.value)
        self.mock_process_manager.assert_not_called()

    @pytest.mark.timeout(3)  # Short timeout since these should be fast
    def test_runserver_without_django_extensions(self):
        """Test runserver when django-extensions is not available."""
        self.mock_find_spec.return_value = None  # django-extensions not found

        call_command("tailwind", "runserver")

        # Verify ProcessManager was called
        self.mock_process_manager.assert_called_once()
        mock_instance = self.mock_process_manager.return_value
        mock_instance.start_concurrent_processes.assert_called_once()

    @pytest.mark.timeout(3)
    def test_runserver_with_django_extensions(self):
        """Test runserver when django-extensions is available."""

        # Mock both django-extensions and werkzeug as available
        def mock_find_spec(name: str) -> object | None:
            return Mock() if name in ["django_extensions", "werkzeug"] else None

        self.mock_find_spec.side_effect = mock_find_spec

        call_command("tailwind", "runserver")

        # Should still use ProcessManager
        self.mock_process_manager.assert_called_once()

    @pytest.mark.timeout(3)
    def test_runserver_with_custom_port(self):
        """Test runserver with custom port."""
        self.mock_find_spec.return_value = None

        call_command("tailwind", "runserver", "8080")

        # Verify the command was processed
        self.mock_process_manager.assert_called_once()

    @pytest.mark.timeout(3)
    def test_runserver_forwards_unknown_flags_in_argv_order(self):
        """Unknown flags and positional args are forwarded verbatim to the underlying command."""
        self.mock_find_spec.return_value = None  # plain runserver branch

        call_command("tailwind", "runserver", "8080", "--noreload", "--nothreading")

        mock_instance = self.mock_process_manager.return_value
        mock_instance.start_concurrent_processes.assert_called_once()
        watch_cmd, server_cmd = mock_instance.start_concurrent_processes.call_args.args
        # Watch cmd is unchanged
        assert watch_cmd[-3:] == ["manage.py", "tailwind", "watch"]
        # Server cmd ends with the runserver target, then "--" and the user's argv in order
        assert server_cmd[-5:] == ["runserver", "--", "8080", "--noreload", "--nothreading"]

    @pytest.mark.timeout(3)
    def test_runserver_picks_runserver_plus_when_extensions_installed(self, mocker: MockerFixture):
        """With django_extensions in INSTALLED_APPS and werkzeug available, runserver_plus is selected."""

        def is_installed(name: str) -> bool:
            return name == "django_extensions"

        def mock_find_spec(name: str) -> object | None:
            return Mock() if name == "werkzeug" else None

        mocker.patch.object(apps, "is_installed", side_effect=is_installed)
        self.mock_find_spec.side_effect = mock_find_spec

        call_command("tailwind", "runserver")

        mock_instance = self.mock_process_manager.return_value
        _, server_cmd = mock_instance.start_concurrent_processes.call_args.args
        assert server_cmd[server_cmd.index("--server-command") + 1] == "runserver_plus"

    @pytest.mark.timeout(3)
    def test_runserver_needs_django_extensions_in_installed_apps(self):
        """django-extensions in the environment alone does not register runserver_plus."""

        def mock_find_spec(name: str) -> object | None:
            return Mock() if name in ["django_extensions", "werkzeug"] else None

        self.mock_find_spec.side_effect = mock_find_spec

        call_command("tailwind", "runserver")

        mock_instance = self.mock_process_manager.return_value
        _, server_cmd = mock_instance.start_concurrent_processes.call_args.args
        assert server_cmd[server_cmd.index("--server-command") + 1] == "runserver"

    @pytest.mark.timeout(3)
    def test_runserver_respects_force_default_runserver(self):
        """--force-default-runserver pins the command to plain runserver even with extensions."""

        def mock_find_spec(name: str) -> object | None:
            return Mock() if name in ["django_extensions", "werkzeug"] else None

        self.mock_find_spec.side_effect = mock_find_spec

        call_command("tailwind", "runserver", "--force-default-runserver")

        mock_instance = self.mock_process_manager.return_value
        _, server_cmd = mock_instance.start_concurrent_processes.call_args.args
        assert server_cmd[server_cmd.index("--server-command") + 1] == "runserver"
        # The tailwind-specific flag is never forwarded to Django
        assert "--force-default-runserver" not in server_cmd

    @pytest.mark.timeout(3)
    def test_runserver_server_command_runs_the_server_with_a_lifeline(self, mocker: MockerFixture):
        """The server subprocess watches the lifeline, then runs Django's command with the user's argv."""
        calls = Mock()
        mocker.patch("django_tailwind_cli.management.commands.tailwind.stop_with_lifeline", calls.stop_with_lifeline)
        mocker.patch("django_tailwind_cli.management.commands.tailwind.execute_from_command_line", calls.execute)

        call_command("tailwind", "runserver", "--server-command", "runserver_plus", "--", "8080", "--nothreading")

        # In this order: the server blocks until it exits.
        assert calls.mock_calls == [
            mocker.call.stop_with_lifeline(),
            mocker.call.execute([sys.argv[0], "runserver_plus", "8080", "--nothreading"]),
        ]
        self.mock_process_manager.assert_not_called()


class TestTemplateScanning:
    """Tests for template scanning with optimized filesystem operations."""

    @pytest.fixture(autouse=True)
    def setup_template_tests(self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture):
        """Setup for template scanning tests."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        # Create minimal test template structure
        template_dir = tmp_path / "templates" / "app"
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / "test.html").write_text("<html></html>")

        # Mock subprocess to avoid CLI calls
        mocker.patch("subprocess.run")

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli)


class TestAutoSourceExternalApps:
    """Tests for TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS auto @source injection."""

    def test_build_source_css_default_is_backward_compatible(self):
        """With inject_external_apps=False the content equals DEFAULT_SOURCE_CSS."""
        from django_tailwind_cli.management.commands._source_css import build_source_css_content

        content = build_source_css_content(use_daisy_ui=False, inject_external_apps=False)
        assert content == DEFAULT_SOURCE_CSS

    def test_build_source_css_daisyui_default_is_backward_compatible(self):
        """DaisyUI variant with inject_external_apps=False equals DAISY_UI_SOURCE_CSS."""
        from django_tailwind_cli.management.commands._source_css import build_source_css_content

        content = build_source_css_content(use_daisy_ui=True, inject_external_apps=False)
        assert content == DAISY_UI_SOURCE_CSS

    def test_build_source_css_injects_external_app(self, mocker: MockerFixture):
        """With an external app present, an @source directive is added."""
        from django_tailwind_cli.management.commands._source_css import build_source_css_content

        mocker.patch(
            "django_tailwind_cli.management.commands._source_css.discover_external_app_base_dirs",
            return_value=[Path("/opt/editable/extra")],
        )

        content = build_source_css_content(use_daisy_ui=False, inject_external_apps=True)

        assert content.startswith('@import "tailwindcss";\n')
        assert '@source "/opt/editable/extra";' in content
        assert "Auto-generated" in content

    def test_build_source_css_injects_multiple_external_apps_in_sorted_order(self, mocker: MockerFixture):
        """Multiple external apps each get their own @source, sorted."""
        from django_tailwind_cli.management.commands._source_css import build_source_css_content

        mocker.patch(
            "django_tailwind_cli.management.commands._source_css.discover_external_app_base_dirs",
            return_value=[Path("/opt/editable/alpha"), Path("/opt/editable/beta")],
        )

        content = build_source_css_content(use_daisy_ui=False, inject_external_apps=True)

        lines = content.splitlines()
        assert '@source "/opt/editable/alpha";' in lines
        assert '@source "/opt/editable/beta";' in lines
        alpha_idx = lines.index('@source "/opt/editable/alpha";')
        beta_idx = lines.index('@source "/opt/editable/beta";')
        assert alpha_idx < beta_idx

    def test_build_source_css_idempotent(self, mocker: MockerFixture):
        """Calling the builder twice with the same discovery yields identical output."""
        from django_tailwind_cli.management.commands._source_css import build_source_css_content

        mocker.patch(
            "django_tailwind_cli.management.commands._source_css.discover_external_app_base_dirs",
            return_value=[Path("/opt/editable/extra")],
        )

        first = build_source_css_content(use_daisy_ui=True, inject_external_apps=True)
        second = build_source_css_content(use_daisy_ui=True, inject_external_apps=True)
        assert first == second

    def test_build_source_css_flag_disabled_skips_injection(self, mocker: MockerFixture):
        """With inject_external_apps=False, discovery is not invoked and no @source is added."""
        from django_tailwind_cli.management.commands._source_css import build_source_css_content

        discover = mocker.patch("django_tailwind_cli.management.commands._source_css.discover_external_app_base_dirs")

        content = build_source_css_content(use_daisy_ui=False, inject_external_apps=False)

        discover.assert_not_called()
        assert "@source" not in content

    def test_discover_external_app_ignores_internal(
        self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture
    ):
        """Apps whose path lies under BASE_DIR are not returned."""
        from django_tailwind_cli.management.commands._source_css import discover_external_app_base_dirs

        settings.BASE_DIR = tmp_path
        internal_app = tmp_path / "myapp"
        internal_app.mkdir()

        mocker.patch(
            "django.apps.apps.get_app_configs",
            return_value=[Mock(path=str(internal_app))],
        )

        assert discover_external_app_base_dirs() == []

    def test_discover_external_app_ignores_site_packages(
        self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture
    ):
        """Apps installed in a standard site-packages dir are not returned."""
        from django_tailwind_cli.management.commands._source_css import discover_external_app_base_dirs

        settings.BASE_DIR = tmp_path / "project"
        settings.BASE_DIR.mkdir()

        fake_site_packages = tmp_path / "site-packages"
        fake_site_packages.mkdir()
        installed_app = fake_site_packages / "some_third_party"
        installed_app.mkdir()

        mocker.patch(
            "django_tailwind_cli.management.commands._source_css._get_site_packages_paths",
            return_value=[fake_site_packages],
        )
        mocker.patch(
            "django.apps.apps.get_app_configs",
            return_value=[Mock(path=str(installed_app))],
        )

        assert discover_external_app_base_dirs() == []

    def test_discover_external_app_returns_editable_install(
        self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture
    ):
        """An app outside both BASE_DIR and site-packages is returned (the target case)."""
        from django_tailwind_cli.management.commands._source_css import discover_external_app_base_dirs

        settings.BASE_DIR = tmp_path / "project"
        settings.BASE_DIR.mkdir()

        fake_site_packages = tmp_path / "site-packages"
        fake_site_packages.mkdir()

        editable_app = tmp_path / "editable" / "extra"
        editable_app.mkdir(parents=True)

        mocker.patch(
            "django_tailwind_cli.management.commands._source_css._get_site_packages_paths",
            return_value=[fake_site_packages],
        )
        mocker.patch(
            "django.apps.apps.get_app_configs",
            return_value=[Mock(path=str(editable_app))],
        )

        result = discover_external_app_base_dirs()
        assert result == [editable_app.resolve()]

    def test_discover_external_app_mixed_internal_and_external(
        self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture
    ):
        """Only the external app is returned when internal + site-packages + external coexist."""
        from django_tailwind_cli.management.commands._source_css import discover_external_app_base_dirs

        settings.BASE_DIR = tmp_path / "project"
        settings.BASE_DIR.mkdir()

        internal_app = settings.BASE_DIR / "myapp"
        internal_app.mkdir()

        fake_site_packages = tmp_path / "site-packages"
        fake_site_packages.mkdir()
        third_party_app = fake_site_packages / "thirdparty"
        third_party_app.mkdir()

        editable_app = tmp_path / "editable" / "extra"
        editable_app.mkdir(parents=True)

        mocker.patch(
            "django_tailwind_cli.management.commands._source_css._get_site_packages_paths",
            return_value=[fake_site_packages],
        )
        mocker.patch(
            "django.apps.apps.get_app_configs",
            return_value=[
                Mock(path=str(internal_app)),
                Mock(path=str(third_party_app)),
                Mock(path=str(editable_app)),
            ],
        )

        result = discover_external_app_base_dirs()
        assert result == [editable_app.resolve()]

    def test_watch_without_noreload_uses_autoreload(self, mocker: MockerFixture):
        """The default watch path delegates to django.utils.autoreload.run_with_reloader."""

        def _noop(func: Any, *args: Any, **kwargs: Any) -> None:
            return None

        run_with_reloader = mocker.patch(
            "django.utils.autoreload.run_with_reloader",
            side_effect=_noop,
        )
        run_watch_loop = mocker.patch("django_tailwind_cli.management.commands.tailwind.run_watch_loop")

        call_command("tailwind", "watch")

        run_with_reloader.assert_called_once()
        # The first positional arg is the reloadable callable, which runs the watch loop.
        run_with_reloader.call_args.args[0](verbose=False)
        run_watch_loop.assert_called_once_with(verbose=False)
        # ...and verbose=False is forwarded through kwargs.
        assert run_with_reloader.call_args.kwargs == {"verbose": False}
        # The lifeline for the reloader child must not stay behind in this process.
        assert LIFELINE_ENV not in os.environ

    def test_reloader_child_reports_a_missing_file_like_noreload(
        self, mocker: MockerFixture, capsys: CaptureFixture[str]
    ):
        """Under the reloader a FileNotFoundError gets the same report and exit code as with --noreload."""
        mocker.patch(
            "django_tailwind_cli.management.commands.tailwind.run_watch_loop",
            side_effect=FileNotFoundError("source.css"),
        )
        exit_process = mocker.patch("django_tailwind_cli.management.commands.tailwind.os._exit", side_effect=SystemExit)

        with pytest.raises(SystemExit):
            _run_watch_loop_in_reloader_child(verbose=False)

        exit_process.assert_called_once_with(1)
        err = capsys.readouterr().err
        assert "❌ File not found: source.css" in err
        assert "CommandError: source.css" in err

    def test_watch_with_noreload_calls_loop_directly(self, mocker: MockerFixture):
        """--noreload bypasses autoreload and runs the loop in the current process."""
        run_with_reloader = mocker.patch("django.utils.autoreload.run_with_reloader")
        run_watch_loop = mocker.patch("django_tailwind_cli.management.commands.tailwind.run_watch_loop")

        call_command("tailwind", "watch", "--noreload")

        run_with_reloader.assert_not_called()
        run_watch_loop.assert_called_once_with(verbose=False)

    def test_create_src_css_writes_injected_content(
        self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture
    ):
        """End-to-end: when the setting is on, the written source.css contains the @source line."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / "tailwindcss"
        settings.TAILWIND_CLI_VERSION = "4.0.0"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS = True

        editable_app = tmp_path.parent / "ext" / "editable_app"
        editable_app.mkdir(parents=True, exist_ok=True)

        mocker.patch("subprocess.run")
        mocker.patch(
            "django_tailwind_cli.management.commands._source_css.discover_external_app_base_dirs",
            return_value=[editable_app],
        )

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli)

        call_command("tailwind", "build")

        c = get_config()
        assert c.src_css.exists()
        written = c.src_css.read_text()
        assert '@import "tailwindcss";' in written
        assert f'@source "{editable_app}";' in written


class TestDefaultGitignore:
    """Tests for ensure_default_gitignore() — the auto .gitignore drop-in."""

    def test_ensure_default_gitignore_creates_star_file(self, settings: LazySettings, tmp_path: Path):
        """In default mode the helper writes '*\\n' into .django_tailwind_cli/.gitignore."""
        from django_tailwind_cli.management.commands._download import ensure_default_gitignore

        settings.BASE_DIR = tmp_path
        # TAILWIND_CLI_PATH intentionally not set → default mode
        default_dir = tmp_path / ".django_tailwind_cli"
        default_dir.mkdir()

        ensure_default_gitignore()

        gitignore = default_dir / ".gitignore"
        assert gitignore.exists()
        assert gitignore.read_text() == "*\n"

    def test_ensure_default_gitignore_skipped_for_custom_path(self, settings: LazySettings, tmp_path: Path):
        """With a custom TAILWIND_CLI_PATH, the helper is a no-op."""
        from django_tailwind_cli.management.commands._download import ensure_default_gitignore

        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = str(tmp_path / "custom" / "tailwindcss")

        # The default dir can still exist from a previous run — the helper
        # should leave it alone when a custom path is active.
        default_dir = tmp_path / ".django_tailwind_cli"
        default_dir.mkdir()

        ensure_default_gitignore()

        assert not (default_dir / ".gitignore").exists()

    def test_ensure_default_gitignore_preserves_existing_file(self, settings: LazySettings, tmp_path: Path):
        """If the user already wrote a .gitignore, we don't overwrite it."""
        from django_tailwind_cli.management.commands._download import ensure_default_gitignore

        settings.BASE_DIR = tmp_path
        default_dir = tmp_path / ".django_tailwind_cli"
        default_dir.mkdir()
        existing = default_dir / ".gitignore"
        existing.write_text("# hand-written\n*.log\n")

        ensure_default_gitignore()

        assert existing.read_text() == "# hand-written\n*.log\n"

    def test_ensure_default_gitignore_noop_when_dir_missing(self, settings: LazySettings, tmp_path: Path):
        """If the managed dir was never created, the helper simply returns."""
        from django_tailwind_cli.management.commands._download import ensure_default_gitignore

        settings.BASE_DIR = tmp_path
        # No default_dir created

        ensure_default_gitignore()  # must not raise

        assert not (tmp_path / ".django_tailwind_cli").exists()


# Configuration to run tests with appropriate markers
pytestmark = [
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
    pytest.mark.filterwarnings("ignore::PendingDeprecationWarning"),
]


class TestSourceCssEncoding:
    @pytest.mark.parametrize("already_exists", [False, True])
    def test_generated_unicode_source_is_written_once(self, tmp_path: Path, already_exists: bool):
        from django_tailwind_cli.management.commands._source_css import _ensure_one_source_css

        src_css = tmp_path / "source.css"
        content = f'{DEFAULT_SOURCE_CSS}\n{AUTO_SOURCE_COMMENT}\n@source "/editable/\u0645\u0644\u0641\u0627\u062a";\n'
        if already_exists:
            src_css.write_bytes(content.encode("utf-8"))

        assert _ensure_one_source_css(src_css, content, manages_the_file=True, verbose=False) is not already_exists
        assert src_css.read_text(encoding="utf-8") == content
        assert not _ensure_one_source_css(src_css, content, manages_the_file=True, verbose=False)
        assert not src_css.with_suffix(".css.bak").exists()

    @pytest.mark.parametrize(
        "edited_bytes",
        [
            f'{DEFAULT_SOURCE_CSS}@source "../\u0645\u0644\u0641\u0627\u062a";\n'.encode(),
            b'@import "tailwindcss";\n@source "../caf\xe9";\n',
        ],
        ids=["utf8", "legacy-encoding"],
    )
    def test_hand_edits_are_backed_up_without_changing_bytes(self, tmp_path: Path, edited_bytes: bytes):
        from django_tailwind_cli.management.commands._source_css import _ensure_one_source_css

        src_css = tmp_path / "source.css"
        src_css.write_bytes(edited_bytes)

        assert _ensure_one_source_css(src_css, DEFAULT_SOURCE_CSS, manages_the_file=True, verbose=False)

        assert src_css.with_suffix(".css.bak").read_bytes() == edited_bytes
        assert src_css.read_text(encoding="utf-8") == DEFAULT_SOURCE_CSS


class TestSourceCssOverwriteWarning:
    """The managed source.css is overwritten; hand edits should not vanish silently."""

    @pytest.fixture(autouse=True)
    def _managed_source_css(
        self,
        settings: LazySettings,
        mocker: MockerFixture,
        tmp_project: Path,  # noqa: ARG002  (requested for its side effect)
    ):
        for name in ("TAILWIND_CLI_SRC_CSS", "TAILWIND_CLI_CSS_MAP"):
            if hasattr(settings, name):
                delattr(settings, name)
        mocker.patch("subprocess.run")

    def _src_css(self, tmp_path: Path) -> Path:
        return tmp_path / ".django_tailwind_cli" / "source.css"

    def _write(self, tmp_path: Path, content: str) -> Path:
        path = self._src_css(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_a_second_run_leaves_an_up_to_date_source_css_alone(self, tmp_path: Path):
        """Rewriting an identical file would look harmless, and is not.

        Asserted on what the function reports it wrote, because that is what `setup` reads to
        decide between "Created ..." and "up to date".
        """
        assert ensure_source_css() == {self._src_css(tmp_path)}
        assert ensure_source_css() == set()

    def test_hand_edited_source_css_warns_before_it_is_replaced(self, tmp_path: Path, capsys: CaptureFixture[str]):
        self._write(tmp_path, '@import "tailwindcss";\n\n@layer base {\n  html { font-size: 20px; }\n}\n')

        ensure_source_css()
        captured = capsys.readouterr()

        assert "hand edits" in captured.out.lower() or "edited" in captured.out.lower()
        assert "TAILWIND_CLI_SRC_CSS" in captured.out

    def test_a_hand_added_source_directive_counts_as_an_edit(self, tmp_path: Path, capsys: CaptureFixture[str]):
        """The likeliest hand edit of all: widening template discovery.

        AGENTS.md says discovery happens exclusively through @source, so this is what a user reaches
        for. The generated file has @source lines too, but only ever below the auto-generated
        comment — above it, the line is the user's.
        """
        edited = '@import "tailwindcss";\n@source "../templates";\n'
        self._write(tmp_path, edited)

        ensure_source_css()
        captured = capsys.readouterr()

        assert "hand edits" in captured.out.lower()
        assert self._src_css(tmp_path).with_suffix(".css.bak").read_text() == edited

    def test_our_own_source_directives_are_not_an_edit(self, tmp_path: Path, capsys: CaptureFixture[str]):
        """Below the auto-generated comment, an @source line is one we wrote."""
        self._write(
            tmp_path,
            f'@import "tailwindcss";\n\n{AUTO_SOURCE_COMMENT}\n@source "/somewhere/an_app";\n',
        )

        ensure_source_css()

        assert "hand edits" not in capsys.readouterr().out.lower()

    def test_hand_edits_are_kept_in_a_backup_beside_the_file(self, tmp_path: Path, capsys: CaptureFixture[str]):
        edited = '@import "tailwindcss";\n\n@theme {\n  --color-brand: #ff6600;\n}\n'
        self._write(tmp_path, edited)

        ensure_source_css()
        captured = capsys.readouterr()

        backup = self._src_css(tmp_path).with_suffix(".css.bak")
        assert backup.read_text() == edited
        assert str(backup) in captured.out

    def test_no_backup_is_left_behind_for_untouched_content(self, settings: LazySettings, tmp_path: Path):
        """Enabling DaisyUI rewrites the file — nothing was edited, so nothing needs keeping."""
        self._write(tmp_path, DEFAULT_SOURCE_CSS)
        settings.TAILWIND_CLI_USE_DAISY_UI = True

        ensure_source_css()

        assert self._src_css(tmp_path).read_text() == DAISY_UI_SOURCE_CSS
        assert not self._src_css(tmp_path).with_suffix(".css.bak").exists()

    def test_untouched_default_is_replaced_without_a_warning(
        self, settings: LazySettings, tmp_path: Path, capsys: CaptureFixture[str]
    ):
        """Switching DaisyUI on rewrites the file, but nothing was lost."""
        self._write(tmp_path, DEFAULT_SOURCE_CSS)
        settings.TAILWIND_CLI_USE_DAISY_UI = True

        ensure_source_css()
        captured = capsys.readouterr()

        assert "TAILWIND_CLI_SRC_CSS" not in captured.out
        assert self._src_css(tmp_path).read_text() == DAISY_UI_SOURCE_CSS

    def test_generated_source_directives_are_not_mistaken_for_edits(self, tmp_path: Path, capsys: CaptureFixture[str]):
        """A file carrying an auto-generated @source block is still ours, even for other apps."""
        self._write(
            tmp_path,
            '@import "tailwindcss";\n\n'
            "/* Auto-generated: installed apps outside BASE_DIR and site-packages. */\n"
            '@source "/somewhere/an_app_that_is_gone";\n',
        )

        ensure_source_css()
        captured = capsys.readouterr()

        assert "TAILWIND_CLI_SRC_CSS" not in captured.out

    def test_missing_file_does_not_warn(self, capsys: CaptureFixture[str]):
        ensure_source_css()
        captured = capsys.readouterr()

        assert "TAILWIND_CLI_SRC_CSS" not in captured.out


class TestSystemBinaryVersionMismatch:
    """A binary found on PATH is the user's; a version mismatch is reported, never resolved."""

    @pytest.fixture(autouse=True)
    def _system_binary(self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture):
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
        mocker.patch("shutil.which", return_value="/opt/homebrew/bin/tailwindcss")
        mocker.patch("subprocess.run")

    def _detect(self, mocker: MockerFixture, version: str | None):
        return mocker.patch(
            "django_tailwind_cli.config.detect_binary_version",
            return_value=Version.parse(version) if version else None,
        )

    def test_a_differing_version_warns(self, settings: LazySettings, mocker: MockerFixture):
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        self._detect(mocker, "4.2.0")

        with pytest.warns(UserWarning, match="4.1.3.*4.2.0"):
            call_command("tailwind", "build")

    def test_a_matching_version_is_quiet(
        self, settings: LazySettings, mocker: MockerFixture, recwarn: pytest.WarningsRecorder
    ):
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        detect = self._detect(mocker, "4.1.3")

        call_command("tailwind", "build")

        detect.assert_called_once()
        assert [w for w in recwarn.list if "reports version" in str(w.message)] == []

    def test_version_latest_accepts_whatever_is_installed(
        self, settings: LazySettings, mocker: MockerFixture, recwarn: pytest.WarningsRecorder
    ):
        settings.TAILWIND_CLI_VERSION = "latest"
        detect = self._detect(mocker, "4.2.0")

        call_command("tailwind", "build")

        detect.assert_not_called()
        assert [w for w in recwarn.list if "reports version" in str(w.message)] == []

    def test_undetectable_version_is_quiet(
        self, settings: LazySettings, mocker: MockerFixture, recwarn: pytest.WarningsRecorder
    ):
        """A binary that cannot be asked stays usable — unknown is not a mismatch."""
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        self._detect(mocker, None)

        call_command("tailwind", "build")

        assert [w for w in recwarn.list if "reports version" in str(w.message)] == []


class TestManagedBinaryIsNotVersionChecked:
    """A downloaded binary carries its version in the filename — do not read it back out."""

    @pytest.fixture(autouse=True)
    def _project(self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture):
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        mocker.patch("subprocess.run")

    def test_a_managed_download_does_not_warn_about_its_version(
        self, settings: LazySettings, mocker: MockerFixture, recwarn: pytest.WarningsRecorder
    ):
        """A fork whose release tag differs from the bundled Tailwind version must stay quiet.

        TAILWIND_CLI_USE_DAISY_UI reaches this by switching TAILWIND_CLI_SRC_REPO to
        tailwind-cli-extra, whose tags do not match the Tailwind version its binary reports —
        comparing the two warns on every single build.
        """
        settings.TAILWIND_CLI_VERSION = "2.1.3"
        settings.TAILWIND_CLI_SRC_REPO = "dobicinaitis/tailwind-cli-extra"
        cli_path = get_config().cli_path
        install_fake_cli(cli_path)
        mocker.patch(
            "django_tailwind_cli.config.detect_binary_version",
            return_value=Version.parse("4.1.13"),
        )

        call_command("tailwind", "build")

        assert [w for w in recwarn.list if "reports version" in str(w.message)] == []

    def test_download_cli_is_quiet_for_a_path_we_manage(self, mocker: MockerFixture, capsys: CaptureFixture[str]):
        """Nothing of the user's is at stake when the filename is ours."""
        mocker.patch(
            "django_tailwind_cli.utils.http.download_with_progress",
            side_effect=partial(write_fake_cli, content=b"official-cli"),
        )

        call_command("tailwind", "download_cli")

        assert "not downloaded by django-tailwind-cli" not in capsys.readouterr().out

    def test_a_managed_download_reads_no_version_out_of_the_binary(self, settings: LazySettings, mocker: MockerFixture):
        """No subprocess on the build path for the common case."""
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        cli_path = get_config().cli_path
        install_fake_cli(cli_path)
        detect = mocker.patch("django_tailwind_cli.config.detect_binary_version")

        call_command("tailwind", "build")

        detect.assert_not_called()


class TestVersionCacheAfterDownload:
    """detect_binary_version is cached; a fresh download has to invalidate that."""

    @pytest.fixture(autouse=True)
    def _project(self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture):
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_VERSION = "4.1.3"

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli)

    def test_the_version_is_read_again_after_a_download(self, mocker: MockerFixture):
        """Without a cache_clear the pre-download reading survives the replacement."""
        from django_tailwind_cli.config import detect_binary_version

        cli_path = get_config().cli_path
        install_fake_cli(cli_path, content=b"old-binary")

        run = mocker.patch("subprocess.run")
        run.return_value = mocker.Mock(returncode=0, stdout="tailwindcss v4.0.0")
        assert str(detect_binary_version(cli_path)) == "4.0.0"

        run.return_value = mocker.Mock(returncode=0, stdout="tailwindcss v4.1.3")
        call_command("tailwind", "download_cli")

        assert str(detect_binary_version(cli_path)) == "4.1.3"


class TestCustomCliPathVersionMismatch:
    """TAILWIND_CLI_PATH may point at a binary the library never downloaded."""

    @pytest.fixture(autouse=True)
    def _custom_binary(self, tmp_project: Path, settings: LazySettings, mocker: MockerFixture):
        # A path of the user's choosing rather than the managed one — that is the class's subject,
        # so it overrides what tmp_project set.
        self.binary = install_fake_cli(tmp_project / "my-tailwindcss")
        settings.TAILWIND_CLI_PATH = self.binary
        mocker.patch("subprocess.run")

    def _detect(self, mocker: MockerFixture, version: str | None):
        return mocker.patch(
            "django_tailwind_cli.config.detect_binary_version",
            return_value=Version.parse(version) if version else None,
        )

    def test_a_differing_binary_version_warns(self, settings: LazySettings, mocker: MockerFixture):
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        self._detect(mocker, "4.0.0")

        with pytest.warns(UserWarning, match="4.1.3.*4.0.0"):
            call_command("tailwind", "build")

    def test_the_binary_is_left_alone(self, settings: LazySettings, mocker: MockerFixture):
        """Warning only — the file was placed by the user and must not be replaced."""
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        self._detect(mocker, "4.0.0")
        download = mocker.patch("django_tailwind_cli.utils.http.download_with_progress")

        with pytest.warns(UserWarning):
            call_command("tailwind", "build")

        download.assert_not_called()
        assert self.binary.read_bytes() == b"fake-cli-binary"

    def test_automatic_download_disabled_still_warns(self, settings: LazySettings, mocker: MockerFixture):
        """The natural pairing with a hand-placed binary must not skip the check."""
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
        self._detect(mocker, "4.0.0")

        with pytest.warns(UserWarning, match="4.1.3.*4.0.0"):
            call_command("tailwind", "build")

    def test_download_cli_says_what_it_replaces(self, mocker: MockerFixture, capsys: CaptureFixture[str]):
        """Asking for a download explicitly does overwrite — but not without saying so."""
        mocker.patch(
            "django_tailwind_cli.utils.http.download_with_progress",
            side_effect=partial(write_fake_cli, content=b"official-cli"),
        )

        call_command("tailwind", "download_cli")
        captured = capsys.readouterr()

        assert str(self.binary) in captured.out
        assert "not downloaded by django-tailwind-cli" in captured.out
        assert self.binary.read_bytes() == b"official-cli"

    def test_download_cli_does_not_claim_the_binary_is_kept(
        self, settings: LazySettings, mocker: MockerFixture, recwarn: pytest.WarningsRecorder
    ):
        """The mismatch warning says the file is left as it is — not true when we are replacing it."""
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        self._detect(mocker, "4.0.0")
        mocker.patch(
            "django_tailwind_cli.utils.http.download_with_progress",
            side_effect=partial(write_fake_cli, content=b"official-cli"),
        )

        call_command("tailwind", "download_cli")

        assert [w for w in recwarn.list if "reports version" in str(w.message)] == []

    def test_a_matching_binary_version_is_quiet(
        self, settings: LazySettings, mocker: MockerFixture, recwarn: pytest.WarningsRecorder
    ):
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        detect = self._detect(mocker, "4.1.3")

        call_command("tailwind", "build")

        detect.assert_called_once_with(self.binary)
        assert [w for w in recwarn.list if "reports version" in str(w.message)] == []

    def test_version_latest_accepts_whatever_is_there(
        self, settings: LazySettings, mocker: MockerFixture, recwarn: pytest.WarningsRecorder
    ):
        settings.TAILWIND_CLI_VERSION = "latest"
        detect = self._detect(mocker, "4.0.0")

        call_command("tailwind", "build")

        detect.assert_not_called()  # 'latest' accepts whatever is installed, without asking
        assert [w for w in recwarn.list if "reports version" in str(w.message)] == []


class TestDaisyUiPluginDownload:
    """TAILWIND_CLI_DAISY_UI_SOURCE = "plugin" puts daisyUI's .mjs bundles into the managed directory."""

    @pytest.fixture(autouse=True)
    def plugin_mode(
        self,
        tmp_project_with_cli: Path,  # noqa: ARG002  (requested for its side effect)
        stub_subprocess_run: Mock,  # noqa: ARG002  (requested for its side effect)
        settings: LazySettings,
        mocker: MockerFixture,
    ):
        settings.TAILWIND_CLI_USE_DAISY_UI = True
        settings.TAILWIND_CLI_DAISY_UI_SOURCE = "plugin"
        settings.TAILWIND_CLI_DAISY_UI_VERSION = "5.8.2"
        self.download = mocker.patch(
            "django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli
        )

    @property
    def plugin_dir(self) -> Path:
        return managed_dir()

    def test_build_downloads_both_plugin_files(self):
        call_command("tailwind", "build")

        assert [call.args[:2] for call in self.download.call_args_list] == [
            (
                "https://github.com/saadeghi/daisyui/releases/download/v5.8.2/daisyui.mjs",
                self.plugin_dir / "daisyui.mjs",
            ),
            (
                "https://github.com/saadeghi/daisyui/releases/download/v5.8.2/daisyui-theme.mjs",
                self.plugin_dir / "daisyui-theme.mjs",
            ),
        ]

    def test_a_second_build_downloads_nothing(self):
        call_command("tailwind", "build")
        self.download.reset_mock()

        call_command("tailwind", "build")

        self.download.assert_not_called()

    def test_a_version_change_downloads_again(self, settings: LazySettings):
        call_command("tailwind", "build")
        self.download.reset_mock()
        settings.TAILWIND_CLI_DAISY_UI_VERSION = "5.9.0"

        call_command("tailwind", "build")

        assert self.download.call_count == 2
        assert "/v5.9.0/" in self.download.call_args_list[0].args[0]

    def test_download_cli_downloads_the_plugin_again(self):
        call_command("tailwind", "build")
        self.download.reset_mock()

        call_command("tailwind", "download_cli")

        assert self.download.call_count == 3  # the CLI and both plugin files

    def test_a_failed_download_is_a_command_error(self):
        from django_tailwind_cli.utils import http

        self.download.side_effect = http.RequestError("connection refused")

        with pytest.raises(CommandError, match="daisyUI"):
            call_command("tailwind", "build")

    def test_missing_plugin_without_automatic_download_is_a_command_error(self, settings: LazySettings):
        settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False

        with pytest.raises(CommandError, match="daisyui.mjs"):
            call_command("tailwind", "build")

        self.download.assert_not_called()

    def test_the_extra_source_downloads_no_plugin(self, settings: LazySettings):
        settings.TAILWIND_CLI_DAISY_UI_SOURCE = "extra"

        call_command("tailwind", "build")

        assert not any("saadeghi" in call.args[0] for call in self.download.call_args_list)

    def _install_plugin(self, version: str) -> None:
        for path in get_config().daisy_ui_plugin_files.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("installed")
        (self.plugin_dir / "daisyui.version").write_text(f"{version}\n")

    def test_a_failed_latest_lookup_keeps_the_installed_plugin(self, settings: LazySettings, mocker: MockerFixture):
        """Offline, an expired cache must not turn into a download of the fallback version."""
        settings.TAILWIND_CLI_DAISY_UI_VERSION = "latest"
        mocker.patch("django_tailwind_cli.utils.http.fetch_redirect_location", return_value=(False, None))
        self._install_plugin("5.9.0")

        call_command("tailwind", "build")

        self.download.assert_not_called()
        assert get_config().daisy_ui_version_str == "5.9.0"

    def test_the_plugin_directory_is_ignored_by_git(self):
        """tmp_project sets TAILWIND_CLI_PATH, so ensure_default_gitignore does not cover this directory."""
        call_command("tailwind", "build")

        assert (self.plugin_dir / ".gitignore").read_text() == "*\n"

    def test_an_existing_gitignore_is_kept(self):
        self.plugin_dir.mkdir(parents=True)
        (self.plugin_dir / ".gitignore").write_text("daisyui*\n")

        call_command("tailwind", "build")

        assert (self.plugin_dir / ".gitignore").read_text() == "daisyui*\n"

    def test_remove_cli_removes_the_plugin_files(self):
        call_command("tailwind", "build")

        call_command("tailwind", "remove_cli")

        assert not any(path.exists() for path in get_config().daisy_ui_plugin_files.values())
        assert not (self.plugin_dir / "daisyui.version").exists()

    def test_setup_downloads_the_plugin(self, capsys: CaptureFixture[str]):
        call_command("tailwind", "setup")

        assert self.download.call_count == 2
        assert "daisyUI plugin files are in place" in capsys.readouterr().out


class TestDaisyUiPluginSourceCss:
    """In plugin mode the managed source.css loads daisyUI from the managed directory."""

    @pytest.fixture(autouse=True)
    def plugin_mode(self, settings: LazySettings, tmp_project: Path):  # noqa: ARG002  (requested for its side effect)
        for name in ("TAILWIND_CLI_SRC_CSS", "TAILWIND_CLI_CSS_MAP"):
            if hasattr(settings, name):
                delattr(settings, name)
        settings.TAILWIND_CLI_USE_DAISY_UI = True
        settings.TAILWIND_CLI_DAISY_UI_SOURCE = "plugin"

    def _src_css(self, tmp_path: Path) -> Path:
        return tmp_path / ".django_tailwind_cli" / "source.css"

    def _plugin_css(self, plugin_dir: str) -> str:
        return (
            '@import "tailwindcss";\n'
            f'@source not "{plugin_dir}/daisyui{{,*}}.mjs";\n'
            f'@plugin "{plugin_dir}/daisyui.mjs";\n'
        )

    def test_loads_the_plugin_by_a_relative_path(self, tmp_path: Path):
        ensure_source_css()

        assert self._src_css(tmp_path).read_text() == self._plugin_css(".")

    def test_seeds_an_own_source_css_with_a_path_relative_to_it(self, settings: LazySettings, tmp_path: Path):
        """The seeded file is the user's from then on and gets committed; an absolute path breaks elsewhere."""
        settings.TAILWIND_CLI_SRC_CSS = "src/styles/main.css"

        ensure_source_css()

        assert (tmp_path / "src/styles/main.css").read_text() == self._plugin_css("../../.django_tailwind_cli")

    @pytest.mark.parametrize("previous", [DEFAULT_SOURCE_CSS, DAISY_UI_SOURCE_CSS])
    def test_switching_to_the_plugin_is_not_a_hand_edit(self, tmp_path: Path, previous: str):
        self._src_css(tmp_path).parent.mkdir(parents=True)
        self._src_css(tmp_path).write_text(previous)

        ensure_source_css()

        assert not self._src_css(tmp_path).with_suffix(".css.bak").exists()

    def test_switching_back_to_extra_is_not_a_hand_edit(self, settings: LazySettings, tmp_path: Path):
        ensure_source_css()
        settings.TAILWIND_CLI_DAISY_UI_SOURCE = "extra"

        ensure_source_css()

        assert self._src_css(tmp_path).read_text() == DAISY_UI_SOURCE_CSS
        assert not self._src_css(tmp_path).with_suffix(".css.bak").exists()

    def test_plugin_options_are_a_hand_edit(self, tmp_path: Path):
        plugin_dir = (tmp_path / ".django_tailwind_cli").as_posix()
        self._src_css(tmp_path).parent.mkdir(parents=True)
        self._src_css(tmp_path).write_text(
            f'@import "tailwindcss";\n@plugin "{plugin_dir}/daisyui.mjs" {{\n  themes: nord --default;\n}}\n'
        )

        ensure_source_css()

        assert self._src_css(tmp_path).with_suffix(".css.bak").exists()


class TestDaisyUiPluginWithSystemBinary:
    """A system binary means no automatic downloads; download_cli still fetches the plugin on request."""

    @pytest.fixture(autouse=True)
    def system_binary_plugin_mode(
        self,
        tmp_project: Path,
        stub_subprocess_run: Mock,  # noqa: ARG002  (requested for its side effect)
        settings: LazySettings,
        mocker: MockerFixture,
    ):
        del settings.TAILWIND_CLI_PATH
        settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
        settings.TAILWIND_CLI_USE_DAISY_UI = True
        settings.TAILWIND_CLI_DAISY_UI_SOURCE = "plugin"
        settings.TAILWIND_CLI_DAISY_UI_VERSION = "5.8.2"
        binary = install_fake_cli(tmp_project / "bin" / "tailwindcss")
        mocker.patch("shutil.which", return_value=str(binary))
        mocker.patch("django_tailwind_cli.config.detect_binary_version", return_value=None)
        self.download = mocker.patch(
            "django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli
        )

    def test_remove_cli_removes_the_plugin_but_not_the_binary(self):
        call_command("tailwind", "download_cli")

        call_command("tailwind", "remove_cli")

        assert not (managed_dir() / "daisyui.mjs").exists()
        assert Path(get_config().cli_path).exists()

    def test_build_does_not_download_the_plugin(self):
        with pytest.raises(CommandError, match="download_cli"):
            call_command("tailwind", "build")

        self.download.assert_not_called()

    def test_download_cli_downloads_the_plugin(self):
        call_command("tailwind", "download_cli")

        assert self.download.call_count == 2


class TestReleaseLookupPerProcess:
    """A failed latest-release lookup is not repeated for every get_config() call of one command."""

    def test_a_build_looks_up_each_repository_once(
        self,
        tmp_project_with_cli: Path,  # noqa: ARG002  (requested for its side effect)
        stub_subprocess_run: Mock,  # noqa: ARG002  (requested for its side effect)
        settings: LazySettings,
        mocker: MockerFixture,
    ):
        settings.TAILWIND_CLI_VERSION = "latest"
        settings.TAILWIND_CLI_USE_DAISY_UI = True
        settings.TAILWIND_CLI_DAISY_UI_SOURCE = "plugin"
        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli)
        lookup = mocker.patch("django_tailwind_cli.utils.http.fetch_redirect_location", return_value=(False, None))

        call_command("tailwind", "build")

        assert sorted(call.args[0] for call in lookup.call_args_list) == [
            "https://github.com/saadeghi/daisyui/releases/latest/",
            "https://github.com/tailwindlabs/tailwindcss/releases/latest/",
        ]
