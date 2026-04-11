"""Improved management commands tests with better performance and reliability.

This file replaces test_management_commands.py to fix hanging/slowness issues
by implementing better mocking strategies, timeouts, and process management.
"""
# pyright: reportPrivateUsage=false

from pathlib import Path
from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import pytest
from django.conf import LazySettings
from django.core.management import CommandError, call_command
from pytest import CaptureFixture
from pytest_mock import MockerFixture

from django_tailwind_cli.config import get_config
from django_tailwind_cli.management.commands.tailwind import DAISY_UI_SOURCE_CSS, DEFAULT_SOURCE_CSS


def _call_directly(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Helper that bypasses django.utils.autoreload.run_with_reloader in tests."""
    return func(*args, **kwargs)


class TestFastCommands:
    """Fast tests that don't involve process management."""

    @pytest.fixture(autouse=True)
    def setup_fast_tests(self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture):
        """Lightweight setup for fast tests."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / "tailwindcss"
        settings.TAILWIND_CLI_VERSION = "4.0.0"
        settings.TAILWIND_CLI_SRC_CSS = tmp_path / "source.css"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        # Mock only what's necessary for fast tests
        mocker.patch("subprocess.run")

        def mock_download(
            url: str,
            filepath: Path,
            timeout: int = 30,
            progress_callback: Callable[[int, int, float], None] | None = None,
        ) -> None:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(b"fake-cli-binary")

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=mock_download)

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
    def setup_subprocess_tests(self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture):
        """Setup with comprehensive subprocess mocking."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / "tailwindcss"
        settings.TAILWIND_CLI_VERSION = "4.0.0"
        settings.TAILWIND_CLI_SRC_CSS = tmp_path / "source.css"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        # Mock all subprocess-related calls comprehensively
        self.mock_subprocess_run = mocker.patch("subprocess.run")
        self.mock_subprocess_popen = mocker.patch("subprocess.Popen")

        # tailwind watch now wraps its loop in django.utils.autoreload.run_with_reloader.
        # In tests we bypass the reloader (which would fork a child process) and call
        # the inner callable directly so existing assertions still work.
        mocker.patch(
            "django.utils.autoreload.run_with_reloader",
            side_effect=_call_directly,
        )

        def mock_download(
            url: str,
            filepath: Path,
            timeout: int = 30,
            progress_callback: Callable[[int, int, float], None] | None = None,
        ) -> None:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(b"fake-cli-binary")

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=mock_download)

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
    def setup_process_tests(self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture):
        """Setup with complete process mocking."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / "tailwindcss"
        settings.TAILWIND_CLI_VERSION = "4.0.0"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        # Mock ALL process-related functionality
        mocker.patch("subprocess.run")
        mocker.patch("subprocess.Popen")

        def mock_download(
            url: str,
            filepath: Path,
            timeout: int = 30,
            progress_callback: Callable[[int, int, float], None] | None = None,
        ) -> None:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(b"fake-cli-binary")

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=mock_download)

        # Mock the ProcessManager entirely to prevent real process creation
        self.mock_process_manager = mocker.patch("django_tailwind_cli.management.commands.tailwind.ProcessManager")
        mock_manager_instance = Mock()
        mock_manager_instance.start_concurrent_processes.return_value = None
        self.mock_process_manager.return_value = mock_manager_instance

        # Mock importlib checks for django-extensions
        self.mock_find_spec = mocker.patch("importlib.util.find_spec")

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

        def mock_download(
            url: str,
            filepath: Path,
            timeout: int = 30,
            progress_callback: Callable[[int, int, float], None] | None = None,
        ) -> None:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(b"fake-cli-binary")

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=mock_download)


class TestAutoSourceExternalApps:
    """Tests for TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS auto @source injection."""

    def test_build_source_css_default_is_backward_compatible(self):
        """With inject_external_apps=False the content equals DEFAULT_SOURCE_CSS."""
        from django_tailwind_cli.management.commands.tailwind import _build_source_css_content

        content = _build_source_css_content(use_daisy_ui=False, inject_external_apps=False)
        assert content == DEFAULT_SOURCE_CSS

    def test_build_source_css_daisyui_default_is_backward_compatible(self):
        """DaisyUI variant with inject_external_apps=False equals DAISY_UI_SOURCE_CSS."""
        from django_tailwind_cli.management.commands.tailwind import _build_source_css_content

        content = _build_source_css_content(use_daisy_ui=True, inject_external_apps=False)
        assert content == DAISY_UI_SOURCE_CSS

    def test_build_source_css_injects_external_app(self, mocker: MockerFixture):
        """With an external app present, an @source directive is added."""
        from django_tailwind_cli.management.commands.tailwind import _build_source_css_content

        mocker.patch(
            "django_tailwind_cli.management.commands.tailwind._discover_external_app_base_dirs",
            return_value=[Path("/opt/editable/extra")],
        )

        content = _build_source_css_content(use_daisy_ui=False, inject_external_apps=True)

        assert content.startswith('@import "tailwindcss";\n')
        assert '@source "/opt/editable/extra";' in content
        assert "Auto-generated" in content

    def test_build_source_css_injects_multiple_external_apps_in_sorted_order(self, mocker: MockerFixture):
        """Multiple external apps each get their own @source, sorted."""
        from django_tailwind_cli.management.commands.tailwind import _build_source_css_content

        mocker.patch(
            "django_tailwind_cli.management.commands.tailwind._discover_external_app_base_dirs",
            return_value=[Path("/opt/editable/alpha"), Path("/opt/editable/beta")],
        )

        content = _build_source_css_content(use_daisy_ui=False, inject_external_apps=True)

        lines = content.splitlines()
        assert '@source "/opt/editable/alpha";' in lines
        assert '@source "/opt/editable/beta";' in lines
        alpha_idx = lines.index('@source "/opt/editable/alpha";')
        beta_idx = lines.index('@source "/opt/editable/beta";')
        assert alpha_idx < beta_idx

    def test_build_source_css_idempotent(self, mocker: MockerFixture):
        """Calling the builder twice with the same discovery yields identical output."""
        from django_tailwind_cli.management.commands.tailwind import _build_source_css_content

        mocker.patch(
            "django_tailwind_cli.management.commands.tailwind._discover_external_app_base_dirs",
            return_value=[Path("/opt/editable/extra")],
        )

        first = _build_source_css_content(use_daisy_ui=True, inject_external_apps=True)
        second = _build_source_css_content(use_daisy_ui=True, inject_external_apps=True)
        assert first == second

    def test_build_source_css_flag_disabled_skips_injection(self, mocker: MockerFixture):
        """With inject_external_apps=False, discovery is not invoked and no @source is added."""
        from django_tailwind_cli.management.commands.tailwind import _build_source_css_content

        discover = mocker.patch("django_tailwind_cli.management.commands.tailwind._discover_external_app_base_dirs")

        content = _build_source_css_content(use_daisy_ui=False, inject_external_apps=False)

        discover.assert_not_called()
        assert "@source" not in content

    def test_discover_external_app_ignores_internal(
        self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture
    ):
        """Apps whose path lies under BASE_DIR are not returned."""
        from django_tailwind_cli.management.commands.tailwind import _discover_external_app_base_dirs

        settings.BASE_DIR = tmp_path
        internal_app = tmp_path / "myapp"
        internal_app.mkdir()

        mocker.patch(
            "django.apps.apps.get_app_configs",
            return_value=[Mock(path=str(internal_app))],
        )

        assert _discover_external_app_base_dirs() == []

    def test_discover_external_app_ignores_site_packages(
        self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture
    ):
        """Apps installed in a standard site-packages dir are not returned."""
        from django_tailwind_cli.management.commands.tailwind import _discover_external_app_base_dirs

        settings.BASE_DIR = tmp_path / "project"
        settings.BASE_DIR.mkdir()

        fake_site_packages = tmp_path / "site-packages"
        fake_site_packages.mkdir()
        installed_app = fake_site_packages / "some_third_party"
        installed_app.mkdir()

        mocker.patch(
            "django_tailwind_cli.management.commands.tailwind._get_site_packages_paths",
            return_value=[fake_site_packages],
        )
        mocker.patch(
            "django.apps.apps.get_app_configs",
            return_value=[Mock(path=str(installed_app))],
        )

        assert _discover_external_app_base_dirs() == []

    def test_discover_external_app_returns_editable_install(
        self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture
    ):
        """An app outside both BASE_DIR and site-packages is returned (the target case)."""
        from django_tailwind_cli.management.commands.tailwind import _discover_external_app_base_dirs

        settings.BASE_DIR = tmp_path / "project"
        settings.BASE_DIR.mkdir()

        fake_site_packages = tmp_path / "site-packages"
        fake_site_packages.mkdir()

        editable_app = tmp_path / "editable" / "extra"
        editable_app.mkdir(parents=True)

        mocker.patch(
            "django_tailwind_cli.management.commands.tailwind._get_site_packages_paths",
            return_value=[fake_site_packages],
        )
        mocker.patch(
            "django.apps.apps.get_app_configs",
            return_value=[Mock(path=str(editable_app))],
        )

        result = _discover_external_app_base_dirs()
        assert result == [editable_app.resolve()]

    def test_discover_external_app_mixed_internal_and_external(
        self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture
    ):
        """Only the external app is returned when internal + site-packages + external coexist."""
        from django_tailwind_cli.management.commands.tailwind import _discover_external_app_base_dirs

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
            "django_tailwind_cli.management.commands.tailwind._get_site_packages_paths",
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

        result = _discover_external_app_base_dirs()
        assert result == [editable_app.resolve()]

    def test_watch_without_noreload_uses_autoreload(self, mocker: MockerFixture):
        """The default watch path delegates to django.utils.autoreload.run_with_reloader."""

        def _noop(func: Any, *args: Any, **kwargs: Any) -> None:
            return None

        run_with_reloader = mocker.patch(
            "django.utils.autoreload.run_with_reloader",
            side_effect=_noop,
        )
        run_watch_loop = mocker.patch("django_tailwind_cli.management.commands.tailwind._run_watch_loop")

        call_command("tailwind", "watch")

        run_with_reloader.assert_called_once()
        # The first positional arg is the reloadable callable.
        assert run_with_reloader.call_args.args[0] is run_watch_loop
        # ...and verbose=False is forwarded through kwargs.
        assert run_with_reloader.call_args.kwargs == {"verbose": False}

    def test_watch_with_noreload_calls_loop_directly(self, mocker: MockerFixture):
        """--noreload bypasses autoreload and runs the loop in the current process."""
        run_with_reloader = mocker.patch("django.utils.autoreload.run_with_reloader")
        run_watch_loop = mocker.patch("django_tailwind_cli.management.commands.tailwind._run_watch_loop")

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
            "django_tailwind_cli.management.commands.tailwind._discover_external_app_base_dirs",
            return_value=[editable_app],
        )

        def mock_download(
            url: str,
            filepath: Path,
            timeout: int = 30,
            progress_callback: Callable[[int, int, float], None] | None = None,
        ) -> None:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(b"fake-cli-binary")

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=mock_download)

        call_command("tailwind", "build")

        c = get_config()
        assert c.src_css.exists()
        written = c.src_css.read_text()
        assert '@import "tailwindcss";' in written
        assert f'@source "{editable_app}";' in written


# Configuration to run tests with appropriate markers
pytestmark = [
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
    pytest.mark.filterwarnings("ignore::PendingDeprecationWarning"),
]
