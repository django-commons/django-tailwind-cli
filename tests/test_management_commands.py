"""Improved management commands tests with better performance and reliability.

This file replaces test_management_commands.py to fix hanging/slowness issues
by implementing better mocking strategies, timeouts, and process management.
"""
# pyright: reportPrivateUsage=false

from pathlib import Path
from typing import Any
from unittest.mock import Mock

from functools import partial

import pytest
from django.conf import LazySettings
from django.core.management import CommandError, call_command
from pytest import CaptureFixture
from pytest_mock import MockerFixture

from semver import Version

from django_tailwind_cli.config import get_config
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
        """Test watch command subprocess behavior."""
        call_command("tailwind", "watch")

        # Should call subprocess for watch mode
        assert self.mock_subprocess_run.call_count >= 1

    @pytest.mark.timeout(5)
    def test_watch_with_keyboard_interrupt(self, capsys: CaptureFixture[str]):
        """Test watch command handling of KeyboardInterrupt."""
        self.mock_subprocess_run.side_effect = KeyboardInterrupt

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
        # Server cmd ends with the runserver target followed by the user's argv in order
        assert server_cmd[-4:] == ["runserver", "8080", "--noreload", "--nothreading"]

    @pytest.mark.timeout(3)
    def test_runserver_picks_runserver_plus_when_extensions_installed(self):
        """With django-extensions + werkzeug available, runserver_plus is selected."""

        def mock_find_spec(name: str) -> object | None:
            return Mock() if name in ["django_extensions", "werkzeug"] else None

        self.mock_find_spec.side_effect = mock_find_spec

        call_command("tailwind", "runserver")

        mock_instance = self.mock_process_manager.return_value
        _, server_cmd = mock_instance.start_concurrent_processes.call_args.args
        # server_cmd: [python, "manage.py", "runserver_plus", ...]
        assert server_cmd[2] == "runserver_plus"

    @pytest.mark.timeout(3)
    def test_runserver_respects_force_default_runserver(self):
        """--force-default-runserver pins the command to plain runserver even with extensions."""

        def mock_find_spec(name: str) -> object | None:
            return Mock() if name in ["django_extensions", "werkzeug"] else None

        self.mock_find_spec.side_effect = mock_find_spec

        call_command("tailwind", "runserver", "--force-default-runserver")

        mock_instance = self.mock_process_manager.return_value
        _, server_cmd = mock_instance.start_concurrent_processes.call_args.args
        assert server_cmd[2] == "runserver"
        # The tailwind-specific flag is never forwarded to Django
        assert "--force-default-runserver" not in server_cmd


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
        # The first positional arg is the reloadable callable.
        assert run_with_reloader.call_args.args[0] is run_watch_loop
        # ...and verbose=False is forwarded through kwargs.
        assert run_with_reloader.call_args.kwargs == {"verbose": False}

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

        `build` calls this before comparing mtimes, so a needless rewrite pushes the source past
        the output and `should_rebuild_css` recompiles every time. Measured: with the file left
        alone a second `build` spawns the CLI 0 times, and 1 time if it is rewritten.

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
