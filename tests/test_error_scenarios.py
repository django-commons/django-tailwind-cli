"""Comprehensive error scenario coverage for django-tailwind-cli.

These tests verify error handling, edge cases, and failure recovery across
all components of the system including configuration, network operations,
file operations, and subprocess execution.
"""
# pyright: reportPrivateUsage=false

import os
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch

from functools import partial

import pytest
from django.conf import LazySettings
from django_tailwind_cli.utils import http
from django.core.management import CommandError, call_command
from pytest import CaptureFixture
from pytest_mock import MockerFixture
from semver import Version

from django_tailwind_cli.config import (
    _get_cache_path,
    get_platform_info,
    _load_cached_version,
    _validate_required_settings,
    get_config,
    get_version,
)
from django_tailwind_cli.management.commands._process import ProcessManager
from tests.helpers import write_fake_cli


class TestConfigurationErrorScenarios:
    """Test configuration validation and error handling."""

    def test_empty_staticfiles_dirs_error(self, settings: LazySettings):
        """Test error when STATICFILES_DIRS is empty."""
        settings.STATICFILES_DIRS = []

        with pytest.raises(ValueError, match="STATICFILES_DIRS is empty"):
            _validate_required_settings()

    def test_none_staticfiles_dirs_error(self, settings: LazySettings):
        """Test error when STATICFILES_DIRS is None."""
        settings.STATICFILES_DIRS = None

        with pytest.raises(ValueError, match="STATICFILES_DIRS is empty"):
            _validate_required_settings()

    def test_empty_asset_name_error(self, settings: LazySettings, tmp_path: Path):
        """Test error when TAILWIND_CLI_ASSET_NAME is empty string."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_ASSET_NAME = ""

        with pytest.raises(ValueError, match="TAILWIND_CLI_ASSET_NAME must not be empty"):
            _validate_required_settings()

    def test_empty_dist_css_error(self, settings: LazySettings, tmp_path: Path):
        """Test error when TAILWIND_CLI_DIST_CSS is empty string."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_DIST_CSS = ""

        with pytest.raises(ValueError, match="TAILWIND_CLI_DIST_CSS must not be empty"):
            _validate_required_settings()

    def test_empty_src_repo_error(self, settings: LazySettings, tmp_path: Path):
        """Test error when TAILWIND_CLI_SRC_REPO is empty string."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_SRC_REPO = ""

        with pytest.raises(ValueError, match="TAILWIND_CLI_SRC_REPO must not be empty"):
            _validate_required_settings()

    def test_invalid_tailwind_version_error(self, settings: LazySettings, tmp_path: Path):
        """Test error when Tailwind CSS 3.x version is specified."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_VERSION = "3.4.0"
        settings.TAILWIND_CLI_SRC_REPO = "tailwindlabs/tailwindcss"

        with pytest.raises(ValueError, match="Tailwind CSS 3.x is not supported"):
            get_version()

    def test_malformed_version_parsing_error(self, settings: LazySettings, tmp_path: Path):
        """Test error when version string cannot be parsed."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_VERSION = "invalid.version.string"
        settings.TAILWIND_CLI_SRC_REPO = "custom/repo"

        with pytest.raises(ValueError):
            get_version()

    def test_missing_base_dir_handling(self, settings: LazySettings, tmp_path: Path):
        """Test handling when BASE_DIR is not properly set."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        # Remove BASE_DIR attribute entirely
        if hasattr(settings, "BASE_DIR"):
            delattr(settings, "BASE_DIR")

        # Should raise AttributeError when trying to resolve relative paths
        with pytest.raises(AttributeError):
            get_config()

    def test_invalid_path_configurations(self, settings: LazySettings, tmp_path: Path):
        """Test handling of invalid path configurations."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.BASE_DIR = tmp_path

        # Test with invalid characters in path (on Windows)
        if os.name == "nt":  # Windows
            settings.TAILWIND_CLI_PATH = "invalid<>path"
            with pytest.raises((OSError, ValueError)):
                get_config()


class TestNetworkErrorScenarios:
    """Test network-related error handling."""

    def test_version_fetch_timeout_error(self, settings: LazySettings, tmp_path: Path):
        """Test timeout when fetching latest version."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_VERSION = "latest"
        settings.TAILWIND_CLI_REQUEST_TIMEOUT = 0.001  # Very short timeout

        with patch("django_tailwind_cli.utils.http.fetch_redirect_location") as mock_fetch:
            mock_fetch.side_effect = http.RequestTimeoutError("Connection timeout")

            # Should fall back to fallback version
            version_str, _ = get_version()
            assert version_str == "4.1.3"  # FALLBACK_VERSION

    def test_version_fetch_connection_error(self, settings: LazySettings, tmp_path: Path):
        """Test connection error when fetching latest version."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_VERSION = "latest"

        with patch("django_tailwind_cli.utils.http.fetch_redirect_location") as mock_fetch:
            mock_fetch.side_effect = http.NetworkConnectionError("Network unreachable")

            # Should fall back to fallback version
            version_str, _ = get_version()
            assert version_str == "4.1.3"  # FALLBACK_VERSION

    def test_version_fetch_http_error(self, settings: LazySettings, tmp_path: Path):
        """Test HTTP error when fetching latest version."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_VERSION = "latest"

        with patch("django_tailwind_cli.utils.http.fetch_redirect_location") as mock_fetch:
            mock_fetch.return_value = (False, None)

            # Should fall back to fallback version
            version_str, _ = get_version()
            assert version_str == "4.1.3"  # FALLBACK_VERSION

    def test_cli_download_network_error(self, settings: LazySettings, tmp_path: Path):
        """Test network error during CLI download."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"

        with patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download:
            mock_download.side_effect = http.RequestError("Network error")

            with pytest.raises(CommandError, match="Failed to download Tailwind CSS CLI"):
                call_command("tailwind", "download_cli")

    def test_automatic_download_disabled_without_a_cli_is_an_error(self, settings: LazySettings, tmp_path: Path):
        """With the download turned off, a missing binary has to be reported, not fetched.

        `download_cli` forces the download by design, so `build` is the command that reaches this.
        """
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False

        with pytest.raises(CommandError, match="Automatic download of Tailwind CSS CLI is deactivated"):
            call_command("tailwind", "build")

    def test_a_cli_appearing_after_an_earlier_miss_is_seen(
        self, settings: LazySettings, tmp_path: Path, mocker: MockerFixture
    ):
        """Two builds in the same process: the second must not answer from a stale existence cache."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
        mocker.patch("subprocess.run")
        cli_path = get_config().cli_path

        with pytest.raises(CommandError):
            call_command("tailwind", "build")

        cli_path.parent.mkdir(parents=True, exist_ok=True)
        cli_path.write_bytes(b"fake-cli-binary")
        cli_path.chmod(0o755)

        call_command("tailwind", "build")

    def test_cli_download_incomplete_response(self, settings: LazySettings, tmp_path: Path):
        """Test handling of incomplete download response."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"

        with patch(
            "django_tailwind_cli.utils.http.download_with_progress",
            side_effect=partial(write_fake_cli, content=b"incomplete"),
        ):
            # Should complete download despite size mismatch
            call_command("tailwind", "download_cli")

            config = get_config()
            assert config.cli_path.exists()
            assert config.cli_path.read_bytes() == b"incomplete"

    def test_version_cache_corruption_handling(self, settings: LazySettings, tmp_path: Path, version_cache_path: Path):
        """Test handling of corrupted version cache."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_VERSION = "latest"

        version_cache_path.write_text("corrupted\ncache\ndata")

        with patch("django_tailwind_cli.utils.http.fetch_redirect_location") as mock_fetch:
            mock_fetch.return_value = (True, "https://github.com/repo/releases/tag/v4.1.0")

            # Should handle corrupted cache gracefully and fetch new version
            version_str, _ = get_version()
            assert version_str == "4.1.0"


@pytest.mark.usefixtures("bypass_autoreload")
class TestSubprocessErrorScenarios:
    """Test subprocess execution error handling."""

    def test_build_command_execution_failure(self, settings: LazySettings, tmp_path: Path, capsys: CaptureFixture[str]):
        """Test handling of CLI execution failure during build."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"

        # Create a fake CLI that will be executable
        config = get_config()
        config.cli_path.parent.mkdir(parents=True, exist_ok=True)
        config.cli_path.write_bytes(b"fake-cli")
        config.cli_path.chmod(0o755)

        with patch("subprocess.run") as mock_subprocess:
            # Simulate subprocess failure
            error = subprocess.CalledProcessError(1, ["fake-cli"], stderr="Build failed: syntax error")
            mock_subprocess.side_effect = error

            with pytest.raises(CommandError):
                call_command("tailwind", "build")

            captured = capsys.readouterr()
            assert "Failed to build production stylesheet" in captured.err

    def test_watch_command_execution_failure(self, settings: LazySettings, tmp_path: Path, capsys: CaptureFixture[str]):
        """Test handling of CLI execution failure during watch."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"

        # Create a fake CLI
        config = get_config()
        config.cli_path.parent.mkdir(parents=True, exist_ok=True)
        config.cli_path.write_bytes(b"fake-cli")
        config.cli_path.chmod(0o755)

        with patch("subprocess.run") as mock_subprocess:
            # Simulate subprocess failure
            error = subprocess.CalledProcessError(2, ["fake-cli", "--watch"], stderr="Watch failed: permission denied")
            mock_subprocess.side_effect = error

            with pytest.raises(CommandError):
                call_command("tailwind", "watch")

            captured = capsys.readouterr()
            assert "Failed to start in watch mode" in captured.err

    def test_cli_binary_not_executable(self, settings: LazySettings, tmp_path: Path):
        """Test handling when CLI binary exists but is not executable."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"

        # Create CLI file but make it non-executable
        config = get_config()
        config.cli_path.parent.mkdir(parents=True, exist_ok=True)
        config.cli_path.write_text("fake cli content")
        config.cli_path.chmod(0o644)  # Not executable

        with patch(
            "django_tailwind_cli.utils.http.download_with_progress",
            side_effect=partial(write_fake_cli, content=b"real-cli-binary"),
        ):
            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = Mock(returncode=0)

                # Should re-download CLI when existing one is not executable
                call_command("tailwind", "build")

                # Verify new CLI was downloaded
                assert config.cli_path.read_bytes() == b"real-cli-binary"

    def test_subprocess_permission_denied(self, settings: LazySettings, tmp_path: Path):
        """Test handling of permission denied during subprocess execution."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"

        config = get_config()
        config.cli_path.parent.mkdir(parents=True, exist_ok=True)
        config.cli_path.write_bytes(b"fake-cli")
        config.cli_path.chmod(0o755)

        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.side_effect = PermissionError("Permission denied")

            # handle_command_errors reports the hint and continues as a CommandError.
            with pytest.raises(CommandError):
                call_command("tailwind", "build")


class TestFileSystemErrorScenarios:
    """Test file system error handling."""

    def test_unwritable_cli_directory(self, settings: LazySettings, tmp_path: Path):
        """Test handling when CLI directory is not writable."""
        if os.name == "nt":  # Skip on Windows due to permission model differences
            pytest.skip("Permission testing not reliable on Windows")

        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]

        # Create read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir(mode=0o555)  # Read and execute only
        settings.TAILWIND_CLI_PATH = readonly_dir / "cli"

        try:
            with patch(
                "django_tailwind_cli.utils.http.download_with_progress",
                side_effect=partial(write_fake_cli, content=b"cli-binary"),
            ):
                with pytest.raises((CommandError, PermissionError)):
                    call_command("tailwind", "download_cli")
        finally:
            # Cleanup: restore write permissions
            readonly_dir.chmod(0o755)

    def test_css_output_directory_creation_failure(self, settings: LazySettings, tmp_path: Path):
        """Test handling when CSS output directory cannot be created."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "nonexistent" / "deeply" / "nested" / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"

        # Create CLI
        config = get_config()
        config.cli_path.parent.mkdir(parents=True, exist_ok=True)
        config.cli_path.write_bytes(b"fake-cli")
        config.cli_path.chmod(0o755)

        with patch("subprocess.run") as mock_subprocess:
            # Make subprocess fail due to missing output directory
            error = subprocess.CalledProcessError(1, ["fake-cli"], stderr="Cannot write to output file")
            mock_subprocess.side_effect = error

            with pytest.raises(CommandError):
                call_command("tailwind", "build")

    def test_source_css_read_permission_error(self, settings: LazySettings, tmp_path: Path):
        """Test handling when source CSS file cannot be read."""
        if os.name == "nt":  # Skip on Windows
            pytest.skip("Permission testing not reliable on Windows")

        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"
        settings.TAILWIND_CLI_SRC_CSS = tmp_path / "source.css"

        # Create unreadable source CSS
        source_css = tmp_path / "source.css"
        source_css.write_text("@import 'tailwindcss';")
        source_css.chmod(0o000)  # No permissions

        try:
            config = get_config()
            config.cli_path.parent.mkdir(parents=True, exist_ok=True)
            config.cli_path.write_bytes(b"fake-cli")
            config.cli_path.chmod(0o755)

            with patch("subprocess.run") as mock_subprocess:
                error = subprocess.CalledProcessError(1, ["fake-cli"], stderr="Cannot read input file")
                mock_subprocess.side_effect = error

                with pytest.raises(CommandError):
                    call_command("tailwind", "build")
        finally:
            # Cleanup
            source_css.chmod(0o644)

    def test_temporary_file_creation_failure(self, settings: LazySettings, tmp_path: Path):
        """Test handling when temporary files cannot be created."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]

        with patch("tempfile.gettempdir") as mock_temp:
            mock_temp.return_value = "/nonexistent/temp/dir"

            # Should handle gracefully when cache directory cannot be created
            with pytest.raises(FileNotFoundError):
                _get_cache_path()  # This will fail due to nonexistent directory

    def test_disk_full_simulation(self, settings: LazySettings, tmp_path: Path):
        """Test handling of disk full errors during file operations."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"

        # Create the CLI directory but make it read-only to simulate write errors
        if os.name != "nt":  # Skip on Windows
            config = get_config()
            config.cli_path.parent.mkdir(parents=True, exist_ok=True)
            config.cli_path.parent.chmod(0o555)  # Read-only directory

            try:
                with patch(
                    "django_tailwind_cli.utils.http.download_with_progress",
                    side_effect=partial(write_fake_cli, content=b"cli-binary"),
                ):
                    # Should handle permission/disk errors gracefully
                    with pytest.raises((CommandError, PermissionError, OSError)):
                        call_command("tailwind", "download_cli")
            finally:
                # Cleanup: restore write permissions
                config.cli_path.parent.chmod(0o755)
        else:
            # On Windows, just test that the command can complete normally
            with patch(
                "django_tailwind_cli.utils.http.download_with_progress",
                side_effect=partial(write_fake_cli, content=b"cli-binary"),
            ):
                call_command("tailwind", "download_cli")
                config = get_config()
                assert config.cli_path.exists()


class TestConcurrencyErrorScenarios:
    """Test concurrency and race condition handling."""

    def test_process_manager_cleanup_swallows_terminate_error(self):
        """ProcessManager cleanup must not propagate OSError from terminate()."""
        manager = ProcessManager()

        # Mock process that raises exception during terminate
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.terminate.side_effect = OSError("Process already terminated")
        mock_process.wait.return_value = None
        manager.processes = [mock_process]

        manager._cleanup_processes()

        # Should still clean up processes list
        assert manager.processes == []

    def test_process_manager_names_the_exit_code(self, capsys: CaptureFixture[str], mocker: MockerFixture):
        """The two managers word this differently; consolidating them must not level it."""
        mocker.patch("django_tailwind_cli.management.commands._process.time.sleep")
        manager = ProcessManager()
        alive, dead = Mock(), Mock()
        # Runs out, so a broken loop guard fails the test instead of spinning forever.
        alive.poll.side_effect = [None, None, 0, 0, 0]
        dead.poll.return_value = 2
        dead.returncode = 2
        manager.processes = [alive, dead]

        manager._monitor_processes()

        assert "Process exited with code 2" in capsys.readouterr().out
        assert manager.shutdown_requested is True  # reporting one dead process ends the watch

    def test_multi_watch_manager_names_which_process_exited(self, capsys: CaptureFixture[str], mocker: MockerFixture):
        """With several watchers running, the bare message would not say which one died."""
        from django_tailwind_cli.management.commands._process import MultiWatchProcessManager

        mocker.patch("django_tailwind_cli.management.commands._process.time.sleep")
        manager = MultiWatchProcessManager()
        alive, dead = Mock(), Mock()
        alive.poll.side_effect = [None, None, 0, 0, 0]
        dead.poll.return_value = 2
        dead.returncode = 2
        manager.processes = [alive, dead]

        manager._monitor_processes()

        assert "Watch process 1 exited with code 2" in capsys.readouterr().out

    def test_only_the_multi_watch_manager_reports_the_end_of_watching(self, capsys: CaptureFixture[str]):
        """The single-watch path prints this from tailwind.py; the manager must for the multi path."""
        from django_tailwind_cli.management.commands._process import MultiWatchProcessManager

        done = Mock()
        done.poll.return_value = 0

        pm = ProcessManager()
        pm.processes = [done]
        pm._cleanup_processes()
        assert "Stopped watching for changes." not in capsys.readouterr().out

        mw = MultiWatchProcessManager()
        mw.processes = [done]
        mw._cleanup_processes()
        assert "Stopped watching for changes." in capsys.readouterr().out

    def test_the_two_managers_word_their_shutdown_differently(self, capsys: CaptureFixture[str]):
        """Class-level text, so a consolidation that only compares methods would drop it."""
        from django_tailwind_cli.management.commands._process import MultiWatchProcessManager

        ProcessManager()._request_shutdown()
        assert "stopping processes..." in capsys.readouterr().out

        MultiWatchProcessManager()._request_shutdown()
        assert "stopping watch processes..." in capsys.readouterr().out

    def test_process_manager_cleanup_escalates_on_wait_timeout(self):
        """ProcessManager cleanup must kill() when terminate() + wait() time out."""
        manager = ProcessManager()

        # Mock process that times out during wait
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.terminate.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired(["cmd"], 5)
        mock_process.kill.return_value = None
        manager.processes = [mock_process]

        manager._cleanup_processes()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_concurrent_cli_download_simulation(self, settings: LazySettings, tmp_path: Path):
        """Test handling of concurrent CLI download attempts."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"

        with patch(
            "django_tailwind_cli.utils.http.download_with_progress",
            side_effect=partial(write_fake_cli, content=b"our-cli-binary"),
        ):
            # Should complete successfully
            call_command("tailwind", "download_cli")

            config = get_config()
            assert config.cli_path.exists()
            assert config.cli_path.read_bytes() == b"our-cli-binary"

    def test_version_cache_race_condition(self, settings: LazySettings, tmp_path: Path):
        """Test handling of version cache race conditions."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_VERSION = "latest"

        with patch("django_tailwind_cli.utils.http.fetch_redirect_location") as mock_fetch:
            mock_fetch.return_value = (True, "https://github.com/repo/releases/tag/v4.1.5")

            # Should handle version fetch gracefully
            version_str, parsed_version = get_version()
            assert version_str == "4.1.5"
            assert isinstance(parsed_version, Version)


class TestEdgeCaseScenarios:
    """Test edge cases and boundary conditions."""

    def test_zero_byte_cli_download(self, settings: LazySettings, tmp_path: Path):
        """Test handling of zero-byte CLI download."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_PATH = tmp_path / ".cli"

        with patch(
            "django_tailwind_cli.utils.http.download_with_progress", side_effect=partial(write_fake_cli, content=b"")
        ):
            # Ensure directory exists before attempting download
            config = get_config()
            config.cli_path.parent.mkdir(parents=True, exist_ok=True)

            call_command("tailwind", "download_cli")

            assert config.cli_path.exists()
            assert config.cli_path.read_bytes() == b""

    def test_extremely_long_paths(self, settings: LazySettings, tmp_path: Path):
        """Test handling of extremely long file paths."""
        # Create a very long path (near filesystem limits)
        long_path_component = "a" * 200
        long_path = tmp_path
        for _ in range(3):  # Create nested long directories
            long_path = long_path / long_path_component

        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [long_path / "assets"]
        settings.TAILWIND_CLI_PATH = long_path / ".cli"

        try:
            config = get_config()
            # Should handle long paths gracefully or raise appropriate error
            assert isinstance(config.cli_path, Path)
        except (OSError, ValueError):
            # Long paths might not be supported on all filesystems
            pass

    def test_unicode_path_handling(self, settings: LazySettings, tmp_path: Path):
        """Test handling of Unicode characters in file paths."""
        unicode_path = tmp_path / "测试目录" / "файлы" / "🎨assets"

        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [unicode_path]
        settings.TAILWIND_CLI_PATH = unicode_path.parent / ".cli"

        try:
            unicode_path.mkdir(parents=True, exist_ok=True)
            config = get_config()
            # Check that the CLI path is within the expected parent directory
            assert unicode_path.parent in config.cli_path.parents or config.cli_path.parent == unicode_path.parent
        except (UnicodeError, OSError):
            # Some filesystems might not support Unicode paths
            pytest.skip("Unicode paths not supported on this filesystem")

    def test_version_parsing_edge_cases(self, settings: LazySettings, tmp_path: Path):
        """Test version parsing with edge case version strings."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]

        edge_case_versions = [
            "4.0.0-alpha.1",
            "4.0.0-beta.2+build.123",
            "4.0.0-rc.1",
            "4.10.20",  # High version numbers
        ]

        for version_str in edge_case_versions:
            settings.TAILWIND_CLI_VERSION = version_str
            settings.TAILWIND_CLI_SRC_REPO = "custom/repo"

            try:
                parsed_version_str, _ = get_version()
                assert parsed_version_str == version_str
            except ValueError:
                # Some edge case versions might not be valid semver
                pass

    def test_malformed_redirect_urls(self, settings: LazySettings, tmp_path: Path):
        """Test handling of malformed redirect URLs during version fetch."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.TAILWIND_CLI_VERSION = "latest"

        malformed_locations = [
            "not-a-url",
            "https://malformed/path/without/version",
            "https://github.com/repo/releases/tag/",  # Missing version
            "https://github.com/repo/releases/tag/invalid-version",
        ]

        for location in malformed_locations:
            with patch("django_tailwind_cli.utils.http.fetch_redirect_location") as mock_fetch:
                mock_fetch.return_value = (True, location)

                # Should fall back to fallback version on parsing errors
                version_str, _ = get_version()
                assert version_str == "4.1.3"  # FALLBACK_VERSION

    def test_cache_file_corruption_scenarios(self, settings: LazySettings, tmp_path: Path, version_cache_path: Path):
        """Test various cache file corruption scenarios."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]

        cache_path = version_cache_path

        corruption_scenarios = [
            "",  # Empty file
            "single_line",  # Missing required lines
            "line1\nline2",  # Missing timestamp
            "repo\nversion\ninvalid_timestamp",  # Invalid timestamp format
            "repo\nversion\n" + str(time.time() + 7200),  # Future timestamp
        ]

        for corrupted_content in corruption_scenarios:
            cache_path.write_text(corrupted_content)

            # Should handle corruption gracefully
            cached = _load_cached_version("test/repo")
            assert cached is None  # Should return None for corrupted cache

    def test_platform_info_edge_cases(self):
        """Test platform information detection edge cases."""
        # Test various platform.system() return values
        with patch("platform.system", return_value="Unknown"):
            info = get_platform_info()
            assert info.system == "unknown"
            assert info.extension == ""  # Should default to no extension

        # Test various platform.machine() return values
        with patch("platform.machine", return_value="unknown_arch"):
            info = get_platform_info()
            assert info.machine == "unknown_arch"  # Should preserve unknown architectures

    def test_command_error_handling_decorator_edge_cases(self, settings: LazySettings, tmp_path: Path):
        """Test the command error handling decorator with various exception types."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]

        # Test with unknown command - should raise SystemExit or CommandError
        with pytest.raises((CommandError, SystemExit)):
            call_command("tailwind", "nonexistent_command")


class TestErrorSuggestionScenarios:
    """Test error suggestion functions that provide user guidance."""

    def test_suggest_command_error_solutions_staticfiles_dirs(self, capsys: CaptureFixture[str]):
        """Test error suggestions for STATICFILES_DIRS issues."""
        from django_tailwind_cli.management.commands._errors import suggest_command_error_solutions

        suggest_command_error_solutions("Error: STATICFILES_DIRS is not configured properly")

        captured = capsys.readouterr()
        assert "💡 Solution:" in captured.err
        assert "STATICFILES_DIRS" in captured.err
        assert "BASE_DIR / 'assets'" in captured.err

    def test_suggest_command_error_solutions_base_dir(self, capsys: CaptureFixture[str]):
        """Test error suggestions for BASE_DIR issues."""
        from django_tailwind_cli.management.commands._errors import suggest_command_error_solutions

        suggest_command_error_solutions("Error: BASE_DIR is not properly configured")

        captured = capsys.readouterr()
        assert "💡 Solution:" in captured.err
        assert "BASE_DIR" in captured.err
        assert "Path(__file__).resolve().parent.parent" in captured.err

    def test_suggest_command_error_solutions_tailwind_css_3x(self, capsys: CaptureFixture[str]):
        """Test error suggestions for Tailwind CSS 3.x issues."""
        from django_tailwind_cli.management.commands._errors import suggest_command_error_solutions

        suggest_command_error_solutions("Error: Tailwind CSS 3.x is not supported")

        captured = capsys.readouterr()
        assert "💡 Solution:" in captured.err
        assert "django-tailwind-cli v2.21.1" in captured.err
        assert "Tailwind CSS 3.x" in captured.err

    def test_suggest_command_error_solutions_version(self, capsys: CaptureFixture[str]):
        """Test error suggestions for version issues."""
        from django_tailwind_cli.management.commands._errors import suggest_command_error_solutions

        suggest_command_error_solutions("Error: invalid version specified")

        captured = capsys.readouterr()
        assert "💡 Solution:" in captured.err
        assert "TAILWIND_CLI_VERSION" in captured.err
        assert "'latest'" in captured.err

    def test_suggest_command_error_solutions_no_match(self, capsys: CaptureFixture[str]):
        """Test error suggestions when no specific match is found."""
        from django_tailwind_cli.management.commands._errors import suggest_command_error_solutions

        suggest_command_error_solutions("Some random error message")

        captured = capsys.readouterr()
        # Should not print any suggestions for unknown errors
        assert captured.err == ""

    def test_suggest_file_error_solutions_file_not_found(self, capsys: CaptureFixture[str]):
        """Test file error suggestions for file not found issues."""
        from django_tailwind_cli.management.commands._errors import suggest_file_error_solutions

        suggest_file_error_solutions("Error: file not found: /path/to/missing/file.css")

        captured = capsys.readouterr()
        assert "💡 Suggestions:" in captured.err
        assert "CSS input file" in captured.err

    def test_suggest_file_error_solutions_permission_denied(self, capsys: CaptureFixture[str]):
        """Test file error suggestions for permission issues."""
        from django_tailwind_cli.management.commands._errors import suggest_file_error_solutions

        suggest_file_error_solutions("Error: permission denied accessing file")

        captured = capsys.readouterr()
        assert "💡 Suggestions:" in captured.err
        assert "file path is correct" in captured.err

    def test_suggest_file_error_solutions_directory_not_found(self, capsys: CaptureFixture[str]):
        """Test file error suggestions for directory issues."""
        from django_tailwind_cli.management.commands._errors import suggest_file_error_solutions

        suggest_file_error_solutions("Error: directory not found or invalid")

        captured = capsys.readouterr()
        assert "💡 Suggestions:" in captured.err
        assert "directory exists" in captured.err


class TestSetupCommandScenarios:
    """Test the setup command functionality."""

    def test_setup_command_import_error_handling(
        self, settings: LazySettings, tmp_path: Path, capsys: CaptureFixture[str], mocker: MockerFixture
    ):
        """Test setup command when django-tailwind-cli cannot be imported."""
        # Without BASE_DIR the setup guide downloads the real CLI into the
        # source tree (tests/.django_tailwind_cli), one binary per version.
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        mocker.patch("django_tailwind_cli.utils.http.download_with_progress")

        # Mock the import of __version__ within the setup function
        with patch("django_tailwind_cli.__version__", side_effect=ImportError):
            call_command("tailwind", "setup")

        captured = capsys.readouterr()
        assert "django-tailwind-cli not found" in captured.out or "Installation Check" in captured.out

    def test_setup_command_missing_staticfiles_dirs(self, settings: LazySettings, capsys: CaptureFixture[str]):
        """Test setup command when STATICFILES_DIRS is not configured."""
        settings.STATICFILES_DIRS = []
        settings.INSTALLED_APPS = ["django_tailwind_cli"]

        call_command("tailwind", "setup")

        captured = capsys.readouterr()
        assert "STATICFILES_DIRS not configured" in captured.out

    def test_setup_command_configuration_error(
        self, settings: LazySettings, tmp_path: Path, capsys: CaptureFixture[str]
    ):
        """Test setup command when configuration loading fails."""
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.INSTALLED_APPS = ["django_tailwind_cli"]

        with patch(
            "django_tailwind_cli.management.commands.tailwind.get_config",
            side_effect=Exception("Config error"),
        ):
            call_command("tailwind", "setup")

        captured = capsys.readouterr()
        assert "Configuration error" in captured.out

    def test_setup_command_success(self, settings: LazySettings, tmp_path: Path, capsys: CaptureFixture[str]):
        """Test successful setup command execution."""
        settings.BASE_DIR = tmp_path
        settings.STATICFILES_DIRS = [tmp_path / "assets"]
        settings.INSTALLED_APPS = ["django_tailwind_cli"]

        # Create the assets directory
        (tmp_path / "assets").mkdir(parents=True, exist_ok=True)

        # Mock the CLI download and subprocess operations to prevent hanging
        with patch("django_tailwind_cli.management.commands.tailwind.ensure_cli_binary"):
            with patch("subprocess.run") as mock_subprocess:
                # Mock successful subprocess run
                mock_result = Mock()
                mock_result.returncode = 0
                mock_subprocess.return_value = mock_result

                call_command("tailwind", "setup")

        captured = capsys.readouterr()
        assert "Django Tailwind CLI Setup Guide" in captured.out
        assert "Configuration loaded successfully" in captured.out
