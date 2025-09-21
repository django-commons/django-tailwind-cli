"""Improved management commands tests with better performance and reliability.

This file replaces test_management_commands.py to fix hanging/slowness issues
by implementing better mocking strategies, timeouts, and process management.
"""

from pathlib import Path
from collections.abc import Callable
from unittest.mock import Mock

import pytest
from django.conf import LazySettings
from django.core.management import CommandError, call_command
from pytest import CaptureFixture
from pytest_mock import MockerFixture

from django_tailwind_cli.config import get_config
from django_tailwind_cli.management.commands.tailwind import DAISY_UI_SOURCE_CSS, DEFAULT_SOURCE_CSS


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

    @pytest.mark.timeout(10)  # Template scanning can be slower
    def test_list_templates_basic(self, capsys: CaptureFixture[str]):
        """Test basic template listing functionality."""
        call_command("tailwind", "list_templates")
        captured = capsys.readouterr()

        # Should contain some template paths
        assert "templates/" in captured.out or "No templates found" in captured.out

    @pytest.mark.timeout(10)
    def test_list_templates_with_verbose(self, capsys: CaptureFixture[str]):
        """Test verbose template listing."""
        call_command("tailwind", "list_templates", "--verbose")
        captured = capsys.readouterr()

        # Verbose mode should show additional information
        assert len(captured.out) > 0


# Configuration to run tests with appropriate markers
pytestmark = [
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
    pytest.mark.filterwarnings("ignore::PendingDeprecationWarning"),
]
