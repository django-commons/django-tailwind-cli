"""Tests for additional management commands with missing coverage.

This file focuses on testing commands that were missing from the main test suite,
specifically targeting the config, troubleshoot, and optimize commands.
Also includes tests for error handling and edge cases.
"""

from pathlib import Path
from collections.abc import Callable

import pytest
from django.conf import LazySettings
from django.core.management import CommandError, call_command
from pytest import CaptureFixture
from pytest_mock import MockerFixture

from django_tailwind_cli.config import get_config
from django_tailwind_cli.management.commands.tailwind import handle_command_errors


@pytest.fixture(autouse=True)
def configure_test_settings(settings: LazySettings, tmp_path: Path, mocker: MockerFixture):
    """Configure settings for all tests in this module."""
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = tmp_path / "tailwindcss"
    settings.TAILWIND_CLI_VERSION = "4.0.0"
    settings.TAILWIND_CLI_SRC_CSS = tmp_path / "assets" / "css" / "input.css"
    settings.STATICFILES_DIRS = (tmp_path / "assets",)
    settings.TAILWIND_CLI_USE_DAISY_UI = False
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True

    # Mock subprocess to avoid actual CLI calls
    mocker.patch("subprocess.run")

    def mock_download(
        url: str, filepath: Path, timeout: int = 30, progress_callback: Callable[[int, int, float], None] | None = None
    ) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(b"fake binary content")

    mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=mock_download)


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


class TestErrorHandling:
    """Test error handling decorator and error scenarios."""

    def test_handle_command_errors_decorator_command_error(self, mocker: MockerFixture):
        """Test error decorator handles CommandError properly."""
        mock_exit = mocker.patch("sys.exit")
        mock_secho = mocker.patch("typer.secho")

        @handle_command_errors
        def failing_function():
            raise CommandError("Test command error")

        failing_function()

        mock_secho.assert_called()
        mock_exit.assert_called_with(1)
        # Check that error message is displayed
        error_calls = [call for call in mock_secho.call_args_list if "❌ Command error:" in str(call)]
        assert len(error_calls) > 0

    def test_handle_command_errors_decorator_file_not_found(self, mocker: MockerFixture):
        """Test error decorator handles FileNotFoundError properly."""
        mock_exit = mocker.patch("sys.exit")
        mock_secho = mocker.patch("typer.secho")

        @handle_command_errors
        def failing_function():
            raise FileNotFoundError("Test file not found")

        failing_function()

        mock_secho.assert_called()
        mock_exit.assert_called_with(1)
        # Check that error message is displayed
        error_calls = [call for call in mock_secho.call_args_list if "❌ File not found:" in str(call)]
        assert len(error_calls) > 0

    def test_handle_command_errors_decorator_permission_error(self, mocker: MockerFixture):
        """Test error decorator handles PermissionError properly."""
        mock_exit = mocker.patch("sys.exit")
        mock_secho = mocker.patch("typer.secho")

        @handle_command_errors
        def failing_function():
            raise PermissionError("Test permission denied")

        failing_function()

        mock_secho.assert_called()
        mock_exit.assert_called_with(1)
        # Check that error message is displayed
        error_calls = [call for call in mock_secho.call_args_list if "❌ Permission denied:" in str(call)]
        assert len(error_calls) > 0

    def test_handle_command_errors_decorator_generic_exception(self, mocker: MockerFixture):
        """Test error decorator handles generic exceptions properly."""
        mock_exit = mocker.patch("sys.exit")
        mock_secho = mocker.patch("typer.secho")

        @handle_command_errors
        def failing_function():
            raise ValueError("Test generic error")

        failing_function()

        mock_secho.assert_called()
        mock_exit.assert_called_with(1)
        # Check that error message is displayed
        error_calls = [call for call in mock_secho.call_args_list if "❌ Unexpected error:" in str(call)]
        assert len(error_calls) > 0

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
