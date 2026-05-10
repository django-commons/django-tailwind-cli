"""Integration tests for django-tailwind-cli workflows.

These tests verify end-to-end functionality including CLI download,
file operations, and cross-platform compatibility.
"""
# pyright: reportPrivateUsage=false

import os
import platform
import signal
import threading
import time
from pathlib import Path
from collections.abc import Callable
from typing import Any
from unittest.mock import Mock, patch

import pytest
from django.conf import LazySettings
from django_tailwind_cli.utils import http
from django.core.management import call_command
from pytest import CaptureFixture
from pytest_mock import MockerFixture

from django_tailwind_cli.config import get_config
from django_tailwind_cli.management.commands.tailwind import (
    DAISY_UI_SOURCE_CSS,
    DEFAULT_SOURCE_CSS,
    _WATCH_SPAWN_STAGGER_S,
    MultiWatchProcessManager,
    ProcessManager,
    _run_watch_loop,
)


def _call_directly(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Helper that bypasses django.utils.autoreload.run_with_reloader in tests."""
    return func(*args, **kwargs)


def _clear_legacy_css_settings(settings: LazySettings) -> None:
    """Drop single-file CSS settings so CSS_MAP is the sole source of truth."""
    for name in ("TAILWIND_CLI_SRC_CSS", "TAILWIND_CLI_DIST_CSS"):
        if hasattr(settings, name):
            delattr(settings, name)


class TestBuildWorkflowIntegration:
    """Test complete build workflow from setup to CSS generation."""

    def test_full_build_workflow_from_scratch(self, settings: LazySettings, tmp_path: Path):
        """Test complete build workflow starting from no files."""
        # Setup isolated environment
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.TAILWIND_CLI_SRC_CSS = tmp_path / "source.css"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True

        # Mock network requests
        def mock_download(
            url: str,
            filepath: Path,
            timeout: int = 30,
            progress_callback: Callable[[int, int, float], None] | None = None,
        ) -> None:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(b"fake-cli-binary")

        with patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=mock_download):
            # Mock subprocess to avoid actual CLI execution
            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

                # Execute build command
                call_command("tailwind", "build")

                # Verify CLI was downloaded
                config = get_config()
                assert config.cli_path.exists()
                assert config.cli_path.read_bytes() == b"fake-cli-binary"

                # Verify source CSS was created
                assert config.src_css.exists()
                assert config.src_css.read_text() == DEFAULT_SOURCE_CSS

                # Verify subprocess was called with correct arguments
                mock_subprocess.assert_called()
                call_args = mock_subprocess.call_args[0][0]
                assert str(config.cli_path) in call_args
                assert "--input" in call_args
                assert "--output" in call_args
                assert "--minify" in call_args

    def test_build_with_existing_custom_css(self, settings: LazySettings, tmp_path: Path):
        """Test build workflow preserves existing custom CSS content."""
        # Setup with custom CSS
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.TAILWIND_CLI_SRC_CSS = tmp_path / "custom.css"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        # Create custom CSS file
        custom_css = '@import "tailwindcss";\n@theme { --color-primary: blue; }\n'
        settings.TAILWIND_CLI_SRC_CSS.parent.mkdir(parents=True, exist_ok=True)
        settings.TAILWIND_CLI_SRC_CSS.write_text(custom_css)

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            call_command("tailwind", "build")

            # Verify custom CSS content is preserved
            assert settings.TAILWIND_CLI_SRC_CSS.read_text() == custom_css

    def test_build_with_daisy_ui_integration(self, settings: LazySettings, tmp_path: Path):
        """Test build workflow with DaisyUI enabled."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.TAILWIND_CLI_SRC_CSS = tmp_path / "source.css"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_USE_DAISY_UI = True
        settings.TAILWIND_CLI_VERSION = "4.1.3"

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            call_command("tailwind", "build")

            # Verify DaisyUI CSS template was used
            config = get_config()
            assert config.src_css.read_text() == DAISY_UI_SOURCE_CSS
            assert config.use_daisy_ui is True

    def test_build_force_rebuild_workflow(self, settings: LazySettings, tmp_path: Path):
        """Test force rebuild bypasses optimization checks."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.TAILWIND_CLI_SRC_CSS = tmp_path / "source.css"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        # Setup existing files
        config = get_config()
        config.cli_path.parent.mkdir(parents=True, exist_ok=True)
        config.cli_path.write_bytes(b"fake-cli")
        config.cli_path.chmod(0o755)
        config.src_css.parent.mkdir(parents=True, exist_ok=True)
        config.src_css.write_text(DEFAULT_SOURCE_CSS)
        config.dist_css.parent.mkdir(parents=True, exist_ok=True)
        config.dist_css.write_text("/* existing css */")

        # Make dist_css newer than src_css
        src_mtime = time.time() - 100
        dist_mtime = time.time() - 50
        os.utime(config.src_css, (src_mtime, src_mtime))
        os.utime(config.dist_css, (dist_mtime, dist_mtime))

        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            # Test normal build (should skip)
            call_command("tailwind", "build")
            mock_subprocess.assert_not_called()

            # Test force build (should execute)
            call_command("tailwind", "build", "--force")
            mock_subprocess.assert_called_once()

    def test_build_with_multiple_css_entries(self, settings: LazySettings, tmp_path: Path):
        """Test build command processes all CSS entries from CSS_MAP."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_VERSION = "4.1.3"

        # Configure multiple CSS entries
        settings.TAILWIND_CLI_CSS_MAP = [
            ("admin.css", "admin.output.css"),
            ("web.css", "web.output.css"),
        ]
        _clear_legacy_css_settings(settings)

        # Create source CSS files
        (tmp_path / "admin.css").write_text('@import "tailwindcss";')
        (tmp_path / "web.css").write_text('@import "tailwindcss";')

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):

            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            call_command("tailwind", "build", "--force")

            # Verify subprocess was called twice (once per CSS entry)
            assert mock_subprocess.call_count == 2

            # Verify correct arguments for each entry
            calls = mock_subprocess.call_args_list
            call_args_0 = calls[0][0][0]
            call_args_1 = calls[1][0][0]

            # First call should be for admin.css
            assert "admin.css" in str(call_args_0)
            assert "admin.output.css" in str(call_args_0)
            assert "--minify" in call_args_0

            # Second call should be for web.css
            assert "web.css" in str(call_args_1)
            assert "web.output.css" in str(call_args_1)
            assert "--minify" in call_args_1


class TestWatchModeIntegration:
    """Test watch mode functionality and process management."""

    @pytest.fixture(autouse=True)
    def _bypass_autoreload(self, mocker: MockerFixture):
        """tailwind watch wraps its loop in django.utils.autoreload.run_with_reloader.

        In tests we bypass the reloader (which would fork a child process) and call
        the inner callable directly so assertions still apply to the same process.
        """
        mocker.patch(
            "django.utils.autoreload.run_with_reloader",
            side_effect=_call_directly,
        )

    def test_watch_mode_setup_and_execution(self, settings: LazySettings, tmp_path: Path):
        """Test watch mode command execution flow."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.TAILWIND_CLI_SRC_CSS = tmp_path / "source.css"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_VERSION = "4.1.3"  # Avoid latest version fetch

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            call_command("tailwind", "watch")

            # Verify watch command was constructed correctly
            call_args = mock_subprocess.call_args[0][0]
            assert "--watch" in call_args
            assert "--input" in call_args
            assert "--output" in call_args
            assert "--minify" not in call_args  # Watch mode shouldn't minify

    def test_watch_with_multiple_css_entries(self, settings: LazySettings, tmp_path: Path):
        """Test watch command starts multiple processes for CSS_MAP entries."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_VERSION = "4.1.3"

        # Configure multiple CSS entries
        settings.TAILWIND_CLI_CSS_MAP = [
            ("admin.css", "admin.output.css"),
            ("web.css", "web.output.css"),
        ]
        _clear_legacy_css_settings(settings)

        # Create source CSS files
        (tmp_path / "admin.css").write_text('@import "tailwindcss";')
        (tmp_path / "web.css").write_text('@import "tailwindcss";')

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.Popen") as mock_popen,
        ):

            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func

            # Mock Popen to simulate running processes that exit immediately
            mock_process = Mock()
            mock_process.poll.return_value = 0  # Process already exited
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            call_command("tailwind", "watch")

            # Verify Popen was called twice (once per CSS entry)
            assert mock_popen.call_count == 2

            # Verify correct arguments for each entry
            calls = mock_popen.call_args_list
            call_args_0 = calls[0][0][0]
            call_args_1 = calls[1][0][0]

            # First call should be for admin.css with --watch flag
            assert "admin.css" in str(call_args_0)
            assert "admin.output.css" in str(call_args_0)
            assert "--watch" in call_args_0

            # Second call should be for web.css with --watch flag
            assert "web.css" in str(call_args_1)
            assert "web.output.css" in str(call_args_1)
            assert "--watch" in call_args_1

    def test_watch_with_css_map_runs_in_worker_thread(self, settings: LazySettings, tmp_path: Path):
        """Regression for #201: multi-entry watch must work outside the main thread.

        Django's autoreload.run_with_reloader executes the wrapped callable
        in a worker thread. signal.signal() raises ValueError there, so the
        multi-entry watch path must not rely on signal handlers.
        """
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        settings.TAILWIND_CLI_CSS_MAP = [
            ("admin.css", "admin.output.css"),
            ("web.css", "web.output.css"),
        ]
        _clear_legacy_css_settings(settings)

        (tmp_path / "admin.css").write_text('@import "tailwindcss";')
        (tmp_path / "web.css").write_text('@import "tailwindcss";')

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.Popen") as mock_popen,
        ):

            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func

            mock_process = Mock()
            mock_process.poll.return_value = 0  # already exited → monitor loop returns immediately
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            errors: list[BaseException] = []

            def runner() -> None:
                try:
                    _run_watch_loop(verbose=False)
                except BaseException as exc:
                    errors.append(exc)

            worker = threading.Thread(target=runner)
            worker.start()
            worker.join(timeout=5)

            assert not worker.is_alive(), "_run_watch_loop did not terminate within 5s"
            assert not errors, f"_run_watch_loop crashed in worker thread: {errors[0]!r}"

    @pytest.mark.parametrize(
        "entry_count,expected_staggers",
        [(2, 1), (3, 2), (4, 3)],
    )
    def test_watch_staggers_multi_entry_spawn(
        self,
        settings: LazySettings,
        tmp_path: Path,
        mocker: MockerFixture,
        entry_count: int,
        expected_staggers: int,
    ):
        """Multi-entry Popen calls must be spaced by _WATCH_SPAWN_STAGGER_S to avoid the Bun DLOPEN race."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        settings.TAILWIND_CLI_CSS_MAP = [(f"src{i}.css", f"out{i}.output.css") for i in range(entry_count)]
        _clear_legacy_css_settings(settings)

        for i in range(entry_count):
            (tmp_path / f"src{i}.css").write_text('@import "tailwindcss";')

        def mock_download_func(
            url: str,
            filepath: Path,
            timeout: int = 30,
            progress_callback: Callable[[int, int, float], None] | None = None,
        ) -> None:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(b"fake-cli-binary")
            filepath.chmod(0o755)

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=mock_download_func)

        mock_process = Mock()
        mock_process.poll.return_value = 0  # exits immediately so monitor loop returns
        mock_process.wait.return_value = 0
        mock_popen = mocker.patch("subprocess.Popen", return_value=mock_process)

        # Patch only the time reference inside tailwind.py to avoid disturbing
        # the rest of the test runtime.
        mock_sleep = mocker.patch("django_tailwind_cli.management.commands.tailwind.time.sleep")

        call_command("tailwind", "watch")

        assert mock_popen.call_count == entry_count
        stagger_calls = [c for c in mock_sleep.call_args_list if c.args == (_WATCH_SPAWN_STAGGER_S,)]
        assert len(stagger_calls) == expected_staggers, (
            f"expected {expected_staggers} stagger sleeps, got {len(stagger_calls)} of {mock_sleep.call_args_list}"
        )

    def test_watch_keyboard_interrupt_handling(
        self, settings: LazySettings, tmp_path: Path, capsys: CaptureFixture[str]
    ):
        """Test watch mode handles KeyboardInterrupt gracefully."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)
        settings.TAILWIND_CLI_VERSION = "4.1.3"  # Avoid latest version fetch

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func
            mock_subprocess.side_effect = KeyboardInterrupt()

            call_command("tailwind", "watch")

            captured = capsys.readouterr()
            assert "Stopped watching for changes." in captured.out


class TestProcessManagerIntegration:
    """Test ProcessManager for runserver integration."""

    def test_process_manager_initialization(self):
        """Test ProcessManager creates clean initial state."""
        manager = ProcessManager()
        assert manager.processes == []
        assert manager.shutdown_requested is False

    def test_process_manager_cleanup_on_shutdown(self):
        """Test ProcessManager properly cleans up processes."""
        manager = ProcessManager()
        # Mock process that's still running
        mock_process = Mock()
        mock_process.poll.return_value = None  # Still running
        mock_process.terminate.return_value = None
        mock_process.wait.return_value = None
        manager.processes = [mock_process]

        manager._cleanup_processes()

        # Verify cleanup was called
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called()
        assert manager.processes == []

    def test_process_manager_handles_already_exited_processes(self):
        """Test ProcessManager handles processes that already exited."""
        manager = ProcessManager()
        # Mock process that already exited
        mock_process = Mock()
        mock_process.poll.return_value = 0  # Already exited
        manager.processes = [mock_process]

        manager._cleanup_processes()

        # Should not call terminate on already-exited process
        mock_process.terminate.assert_not_called()
        assert manager.processes == []

    @pytest.mark.parametrize("manager_cls", [ProcessManager, MultiWatchProcessManager])
    def test_signal_handler_flips_shutdown_flag_without_cleanup(self, manager_cls: type):
        """Handler must only flip the flag — cleanup is owned by start_xxx' finally."""
        manager = manager_cls()
        mock_process = Mock()
        mock_process.poll.return_value = None
        manager.processes = [mock_process]

        manager._signal_handler(signal.SIGTERM, None)

        assert manager.shutdown_requested is True
        # Cleanup must NOT happen inside the handler — re-entrancy risk.
        mock_process.terminate.assert_not_called()
        assert manager.processes == [mock_process]

    @pytest.mark.parametrize("manager_cls", [ProcessManager, MultiWatchProcessManager])
    def test_sigterm_in_main_thread_triggers_shutdown(self, manager_cls: type):
        """SIGTERM received in the main thread must flip the shutdown flag."""
        manager = manager_cls()
        original = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, manager._signal_handler)
        try:
            signal.raise_signal(signal.SIGTERM)
            assert manager.shutdown_requested is True
        finally:
            signal.signal(signal.SIGTERM, original)

    @pytest.mark.parametrize("manager_cls", [ProcessManager, MultiWatchProcessManager])
    def test_signal_handler_is_idempotent(self, manager_cls: type, capsys: CaptureFixture[str]):
        """Repeated SIGTERMs must produce a single shutdown message (e.g. when pkill matches both wrapper and child)."""
        manager = manager_cls()
        manager._signal_handler(signal.SIGTERM, None)
        manager._signal_handler(signal.SIGTERM, None)
        manager._signal_handler(signal.SIGTERM, None)

        out = capsys.readouterr().out
        assert out.count("Shutdown signal received") == 1
        assert manager.shutdown_requested is True


class TestCLIDownloadIntegration:
    """Test CLI download and setup workflows."""

    def test_cli_download_with_progress_tracking(
        self, settings: LazySettings, tmp_path: Path, capsys: CaptureFixture[str]
    ):
        """Test CLI download shows progress information."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        def mock_download(
            url: str,
            filepath: Path,
            timeout: int = 30,
            progress_callback: Callable[[int, int, float], None] | None = None,
        ) -> None:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(b"fake-cli-binary")

        with patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=mock_download):
            call_command("tailwind", "download_cli")

            captured = capsys.readouterr()
            assert "Downloading Tailwind CSS CLI..." in captured.out
            assert "Download completed!" in captured.out

    def test_cli_download_network_error_handling(self, settings: LazySettings, tmp_path: Path):
        """Test CLI download handles network errors gracefully."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        with patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download:
            mock_download.side_effect = http.RequestError("Network error")

            with pytest.raises((http.RequestError, Exception)):  # Should raise CommandError
                call_command("tailwind", "download_cli")

    def test_cli_permissions_after_download(self, settings: LazySettings, tmp_path: Path):
        """Test CLI gets correct executable permissions after download."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        def mock_download(
            url: str,
            filepath: Path,
            timeout: int = 30,
            progress_callback: Callable[[int, int, float], None] | None = None,
        ) -> None:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(b"fake-cli-binary")

        with patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=mock_download):
            call_command("tailwind", "download_cli")

            config = get_config()
            # Check that file is executable (on Unix-like systems)
            if platform.system() != "Windows":
                assert os.access(config.cli_path, os.X_OK)


class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility scenarios."""

    @pytest.mark.parametrize(
        "mock_system,expected_extension",
        [
            ("Windows", ".exe"),
            ("Darwin", ""),
            ("Linux", ""),
        ],
    )
    def test_platform_specific_cli_paths(
        self, settings: LazySettings, tmp_path: Path, mock_system: str, expected_extension: str
    ):
        """Test CLI paths are platform-appropriate."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        with patch("platform.system", return_value=mock_system):
            config = get_config()
            assert config.cli_path.name.endswith(expected_extension)

    def test_path_handling_with_spaces(self, settings: LazySettings, tmp_path: Path):
        """Test paths with spaces are handled correctly."""
        # Create path with spaces
        spaced_path = tmp_path / "path with spaces"
        spaced_path.mkdir(parents=True, exist_ok=True)
        settings.BASE_DIR = spaced_path
        settings.TAILWIND_CLI_PATH = spaced_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (spaced_path / "assets",)
        settings.TAILWIND_CLI_VERSION = "4.1.3"  # Avoid latest version fetch

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            # Should not raise exception
            call_command("tailwind", "build")

            # Verify paths were handled correctly
            config = get_config()
            assert " " in str(config.cli_path)
            assert config.cli_path.exists()


class TestErrorRecoveryScenarios:
    """Test error recovery and resilience scenarios."""

    def test_recovery_from_corrupted_cli_binary(self, settings: LazySettings, tmp_path: Path):
        """Test recovery when CLI binary is corrupted."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        # Create corrupted CLI binary (not executable)
        config = get_config()
        config.cli_path.parent.mkdir(parents=True, exist_ok=True)
        config.cli_path.write_text("corrupted")  # Text file, not binary
        config.cli_path.chmod(0o644)  # Not executable

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            # Should re-download and fix the binary
            call_command("tailwind", "build")

            # Verify new binary was downloaded
            assert config.cli_path.read_bytes() == b"fake-cli-binary"
            if platform.system() != "Windows":
                assert os.access(config.cli_path, os.X_OK)

    def test_recovery_from_missing_directories(self, settings: LazySettings, tmp_path: Path):
        """Test recovery when required directories are missing."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / "missing" / "path" / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "missing" / "assets",)

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            # Should create missing directories and complete build
            call_command("tailwind", "build")

            config = get_config()
            assert config.cli_path.exists()
            assert config.src_css.exists()

    def test_handling_of_permission_errors(self, settings: LazySettings, tmp_path: Path):
        """Test handling of permission errors during file operations."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        # Create directory with restricted permissions (Unix only)
        if platform.system() != "Windows":
            restricted_dir = tmp_path / "restricted"
            restricted_dir.mkdir(mode=0o000)  # No permissions
            settings.TAILWIND_CLI_PATH = restricted_dir / "cli"

            with patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download:
                # Mock download function to create actual file
                def mock_download_func(
                    url: str,
                    filepath: Path,
                    timeout: int = 30,
                    progress_callback: Callable[[int, int, float], None] | None = None,
                ) -> None:
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    filepath.write_bytes(b"fake-cli-binary")
                    filepath.chmod(0o755)

                mock_download.side_effect = mock_download_func

                # Should handle permission error gracefully
                with pytest.raises((PermissionError, Exception)):  # May raise PermissionError or CommandError
                    call_command("tailwind", "download_cli")

            # Cleanup
            restricted_dir.chmod(0o755)


class TestVerboseLoggingIntegration:
    """Test verbose logging across different commands."""

    @pytest.fixture(autouse=True)
    def _bypass_autoreload(self, mocker: MockerFixture):
        """Bypass django autoreload — see TestWatchModeIntegration._bypass_autoreload."""
        mocker.patch(
            "django.utils.autoreload.run_with_reloader",
            side_effect=_call_directly,
        )

    def test_build_verbose_logging(self, settings: LazySettings, tmp_path: Path, capsys: CaptureFixture[str]):
        """Test verbose logging in build command."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func
            mock_subprocess.return_value = Mock(returncode=0, stdout="Build output", stderr="")

            call_command("tailwind", "build", "--verbose")

            captured = capsys.readouterr()
            assert "🏗️  Starting Tailwind CSS build process..." in captured.out
            assert "⚙️  Setting up Tailwind environment..." in captured.out
            assert "✅ Build completed in" in captured.out

    def test_watch_verbose_logging(self, settings: LazySettings, tmp_path: Path, capsys: CaptureFixture[str]):
        """Test verbose logging in watch command."""
        settings.BASE_DIR = tmp_path
        settings.TAILWIND_CLI_PATH = tmp_path / ".django_tailwind_cli"
        settings.STATICFILES_DIRS = (tmp_path / "assets",)

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            def mock_download_func(
                url: str,
                filepath: Path,
                timeout: int = 30,
                progress_callback: Callable[[int, int, float], None] | None = None,
            ) -> None:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(b"fake-cli-binary")
                filepath.chmod(0o755)

            mock_download.side_effect = mock_download_func
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            call_command("tailwind", "watch", "--verbose")

            captured = capsys.readouterr()
            assert "👀 Starting Tailwind CSS watch mode..." in captured.out
            assert "🔄 Starting file watcher..." in captured.out
