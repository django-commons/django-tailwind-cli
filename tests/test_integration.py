"""Integration tests for django-tailwind-cli workflows.

These tests exercise command workflows and file operations with stubbed downloads and subprocesses.
They do not run the real Tailwind compiler.
"""
# pyright: reportPrivateUsage=false

import contextlib
import io
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any
from pathlib import Path
from unittest.mock import Mock, patch


import pytest
from django.conf import LazySettings
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest import CaptureFixture
from pytest_mock import MockerFixture

from django_tailwind_cli.config import get_config
from django_tailwind_cli.management.commands._process import (
    _WATCH_SPAWN_STAGGER_S,
    MultiWatchProcessManager,
    ProcessManager,
    _drain_filtered_stderr,
    _is_bun_noise,
)
from django_tailwind_cli.management.commands._source_css import (
    DAISY_UI_SOURCE_CSS,
    DEFAULT_SOURCE_CSS,
)
from django_tailwind_cli.management.commands.tailwind import run_watch_loop
from tests.helpers import install_python_cli, install_stdin_probe_cli, install_stdin_wait_cli, write_fake_cli


def _clear_legacy_css_settings(settings: LazySettings) -> None:
    """Drop single-file CSS settings so CSS_MAP is the sole source of truth."""
    for name in ("TAILWIND_CLI_SRC_CSS", "TAILWIND_CLI_DIST_CSS"):
        if hasattr(settings, name):
            delattr(settings, name)


class TestBuildWorkflowIntegration:
    """Test complete build workflow from setup to CSS generation."""

    def test_full_build_workflow_from_scratch(self, settings: LazySettings, tmp_project: Path):
        """Test complete build workflow starting from no files."""
        # Setup isolated environment
        settings.TAILWIND_CLI_SRC_CSS = tmp_project / "source.css"
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True

        # Mock network requests
        with patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli):
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

    def test_build_with_existing_custom_css(self, settings: LazySettings, tmp_project: Path):
        """Test build workflow preserves existing custom CSS content."""
        # Setup with custom CSS
        settings.TAILWIND_CLI_SRC_CSS = tmp_project / "custom.css"

        # Create custom CSS file
        custom_css = '@import "tailwindcss";\n@theme { --color-primary: blue; }\n'
        settings.TAILWIND_CLI_SRC_CSS.parent.mkdir(parents=True, exist_ok=True)
        settings.TAILWIND_CLI_SRC_CSS.write_text(custom_css)

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            mock_download.side_effect = write_fake_cli
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            call_command("tailwind", "build")

            # Verify custom CSS content is preserved
            assert settings.TAILWIND_CLI_SRC_CSS.read_text() == custom_css

    def test_build_with_daisy_ui_integration(self, settings: LazySettings, tmp_project: Path):
        """Test build workflow with DaisyUI enabled."""
        settings.TAILWIND_CLI_SRC_CSS = tmp_project / "source.css"
        settings.TAILWIND_CLI_USE_DAISY_UI = True
        settings.TAILWIND_CLI_VERSION = "4.1.3"

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            mock_download.side_effect = write_fake_cli
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            call_command("tailwind", "build")

            # Verify DaisyUI CSS template was used
            config = get_config()
            assert config.src_css.read_text() == DAISY_UI_SOURCE_CSS
            assert config.use_daisy_ui is True

    @pytest.mark.parametrize(
        "command, change",
        [
            ("build", "template"),
            ("build", "import"),
            ("build", "minify"),
            ("build", "unchanged"),
            ("build", "force"),
            ("setup", "template"),
        ],
    )
    def test_build_runs_again_with_existing_output(
        self,
        settings: LazySettings,
        tmp_project_with_cli: Path,
        stub_subprocess_run: Mock,
        command: str,
        change: str,
    ):
        """Every explicit build must let Tailwind process all inputs and options."""
        settings.TAILWIND_CLI_VERSION = "latest"
        settings.TAILWIND_CLI_SRC_CSS = tmp_project_with_cli.parent / "source.css"
        config = get_config()
        imported = config.src_css.parent / "theme.css"
        imported.write_text("@theme { --color-brand: red; }")
        config.src_css.write_text('@import "tailwindcss";\n@import "./theme.css";\n')
        template = config.src_css.parent / "index.html"
        template.write_text('<div class="text-red-500">Hello</div>')

        call_command("tailwind", "build")
        stub_subprocess_run.assert_called_once()
        # Stand in for the output of the successful CLI call; deterministic mtimes
        # make the old shortcut skip the next build regardless of clock resolution.
        config.dist_css.parent.mkdir(parents=True, exist_ok=True)
        config.dist_css.write_text("/* first build */")
        os.utime(config.src_css, (100, 100))
        os.utime(config.dist_css, (200, 200))
        stub_subprocess_run.reset_mock()

        options: list[str] = []
        if change == "template":
            template.write_text('<div class="text-blue-500">Hello</div>')
        elif change == "import":
            imported.write_text("@theme { --color-brand: blue; }")
        elif change == "minify":
            options = ["--no-minify"]
        elif change == "force":
            options = ["--force"]

        call_command("tailwind", command, *options)

        stub_subprocess_run.assert_called_once_with(
            [str(config.cli_path), "--input", str(config.src_css), "--output", str(config.dist_css)]
            + ([] if change == "minify" else ["--minify"]),
            cwd=settings.BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_build_with_multiple_css_entries(self, settings: LazySettings, tmp_project: Path):
        """Test build command processes all CSS entries from CSS_MAP."""
        settings.TAILWIND_CLI_VERSION = "4.1.3"

        # Configure multiple CSS entries
        settings.TAILWIND_CLI_CSS_MAP = [
            ("admin.css", "admin.output.css"),
            ("web.css", "web.output.css"),
        ]
        _clear_legacy_css_settings(settings)

        # Create source CSS files
        (tmp_project / "admin.css").write_text('@import "tailwindcss";')
        (tmp_project / "web.css").write_text('@import "tailwindcss";')

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_download.side_effect = write_fake_cli
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


@pytest.mark.usefixtures("bypass_autoreload")
class TestWatchModeIntegration:
    """Test watch mode functionality and process management."""

    def test_watch_mode_setup_and_execution(self, settings: LazySettings, tmp_project: Path, stub_watch_popen: Mock):
        """Test watch mode command execution flow."""
        settings.TAILWIND_CLI_SRC_CSS = tmp_project / "source.css"
        settings.TAILWIND_CLI_VERSION = "4.1.3"  # Avoid latest version fetch

        with patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download:
            # Mock download function to create actual file
            mock_download.side_effect = write_fake_cli

            call_command("tailwind", "watch")

            # Verify watch command was constructed correctly
            call_args = stub_watch_popen.call_args[0][0]
            assert "--watch" in call_args
            assert "--input" in call_args
            assert "--output" in call_args
            assert "--minify" not in call_args  # Watch mode shouldn't minify

    def test_watch_with_multiple_css_entries(self, settings: LazySettings, tmp_project: Path):
        """Test watch command starts multiple processes for CSS_MAP entries."""
        settings.TAILWIND_CLI_VERSION = "4.1.3"

        # Configure multiple CSS entries
        settings.TAILWIND_CLI_CSS_MAP = [
            ("admin.css", "admin.output.css"),
            ("web.css", "web.output.css"),
        ]
        _clear_legacy_css_settings(settings)

        # Create source CSS files
        (tmp_project / "admin.css").write_text('@import "tailwindcss";')
        (tmp_project / "web.css").write_text('@import "tailwindcss";')

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.Popen") as mock_popen,
        ):
            mock_download.side_effect = write_fake_cli

            # Mock Popen to simulate running processes that exit immediately
            mock_process = Mock()
            mock_process.poll.return_value = 0  # Process already exited
            mock_process.wait.return_value = 0
            mock_process.stderr = None  # skip the stderr drain thread
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

    def test_watch_with_css_map_runs_in_worker_thread(self, settings: LazySettings, tmp_project: Path):
        """Regression for #201: multi-entry watch must work outside the main thread.

        Django's autoreload.run_with_reloader executes the wrapped callable
        in a worker thread. signal.signal() raises ValueError there, so the
        multi-entry watch path must not rely on signal handlers.
        """
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        settings.TAILWIND_CLI_CSS_MAP = [
            ("admin.css", "admin.output.css"),
            ("web.css", "web.output.css"),
        ]
        _clear_legacy_css_settings(settings)

        (tmp_project / "admin.css").write_text('@import "tailwindcss";')
        (tmp_project / "web.css").write_text('@import "tailwindcss";')

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.Popen") as mock_popen,
        ):
            mock_download.side_effect = write_fake_cli

            mock_process = Mock()
            mock_process.poll.return_value = 0  # already exited → monitor loop returns immediately
            mock_process.wait.return_value = 0
            mock_process.stderr = None  # skip the stderr drain thread
            mock_popen.return_value = mock_process

            errors: list[BaseException] = []

            def runner() -> None:
                try:
                    run_watch_loop(verbose=False)
                except BaseException as exc:
                    errors.append(exc)

            worker = threading.Thread(target=runner)
            worker.start()
            worker.join(timeout=5)

            assert not worker.is_alive(), "run_watch_loop did not terminate within 5s"
            assert not errors, f"run_watch_loop crashed in worker thread: {errors[0]!r}"

    @pytest.mark.skipif(sys.platform == "win32", reason="select() does not accept pipes on Windows")
    @pytest.mark.usefixtures("stdin_from_dev_null")
    @pytest.mark.parametrize("project", ["tmp_project", "tmp_project_with_css_map"])
    def test_watcher_stdin_stays_open_without_terminal(
        self, settings: LazySettings, request: pytest.FixtureRequest, project: str
    ):
        """The Tailwind 4 CLI ends `--watch` on stdin EOF, which happens at once under `mise run`."""
        request.getfixturevalue(project)
        install_stdin_probe_cli(settings.TAILWIND_CLI_PATH)

        run_watch_loop()

        entries = get_config().css_entries
        assert [entry.dist_css.read_text() for entry in entries] == ["open"] * len(entries)

    @pytest.mark.skipif(sys.platform == "win32", reason="the fake CLI is a shell script")
    @pytest.mark.parametrize("project", ["tmp_project", "tmp_project_with_css_map"])
    def test_a_watcher_that_exits_with_an_error_fails_the_command(
        self, settings: LazySettings, request: pytest.FixtureRequest, capsys: CaptureFixture[str], project: str
    ):
        """One message naming the stylesheet, and a non-zero exit, with one stylesheet or several."""
        request.getfixturevalue(project)
        install_python_cli(settings.TAILWIND_CLI_PATH, "sys.exit(2)\n")
        first_entry = get_config().css_entries[0].name

        with pytest.raises(CommandError, match=f"Watch process for '{first_entry}' exited with code 2"):
            run_watch_loop()

        assert "Stopped watching for changes." not in capsys.readouterr().out

    @pytest.mark.skipif(sys.platform == "win32", reason="the fake CLI is a shell script")
    @pytest.mark.usefixtures("tmp_project_with_css_map")
    def test_failed_watcher_stderr_is_kept_and_the_others_shutdown_output_dropped(
        self, settings: LazySettings, capfd: CaptureFixture[str]
    ):
        """The failed watcher's last lines say why; the stopped watchers' output would bury them."""
        install_python_cli(
            settings.TAILWIND_CLI_PATH,
            """\
import signal
import time

def stop(*_):
    sys.stderr.write("web: shutting down\\n")
    sys.exit(0)

if "admin" in output_path:
    time.sleep(0.2)
    sys.stderr.write("admin: cannot parse admin.css\\n")
    sys.exit(2)
signal.signal(signal.SIGTERM, stop)
time.sleep(30)
""",
        )

        with pytest.raises(CommandError, match="Watch process for 'admin' exited with code 2"):
            run_watch_loop()

        err = capfd.readouterr().err
        assert "admin: cannot parse admin.css" in err
        assert "web: shutting down" not in err

    @pytest.mark.skipif(sys.platform == "win32", reason="the fake CLI is a shell script")
    @pytest.mark.usefixtures("tmp_project")
    def test_single_watcher_stderr_drops_bun_noise(self, settings: LazySettings, capfd: CaptureFixture[str]):
        """The Bun filter used to cover only TAILWIND_CLI_CSS_MAP setups."""
        install_python_cli(
            settings.TAILWIND_CLI_PATH,
            'sys.stderr.write("EIO: i/o error\\nError: Cannot apply unknown utility class\\n")\n',
        )

        run_watch_loop()

        err = capfd.readouterr().err
        assert "Cannot apply unknown utility class" in err
        assert "EIO" not in err

    @pytest.mark.parametrize(
        "entry_count,expected_staggers",
        [(2, 1), (3, 2), (4, 3)],
    )
    def test_watch_staggers_multi_entry_spawn(
        self,
        settings: LazySettings,
        tmp_project: Path,
        mocker: MockerFixture,
        entry_count: int,
        expected_staggers: int,
    ):
        """Multi-entry Popen calls must be spaced by _WATCH_SPAWN_STAGGER_S to avoid the Bun DLOPEN race."""
        settings.TAILWIND_CLI_VERSION = "4.1.3"
        settings.TAILWIND_CLI_CSS_MAP = [(f"src{i}.css", f"out{i}.output.css") for i in range(entry_count)]
        _clear_legacy_css_settings(settings)

        for i in range(entry_count):
            (tmp_project / f"src{i}.css").write_text('@import "tailwindcss";')

        mocker.patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli)

        mock_process = Mock()
        mock_process.poll.return_value = 0  # exits immediately so monitor loop returns
        mock_process.wait.return_value = 0
        mock_process.stderr = None  # skip the stderr drain thread
        mock_popen = mocker.patch("subprocess.Popen", return_value=mock_process)

        mock_sleep = mocker.patch("django_tailwind_cli.management.commands._process.time.sleep")

        call_command("tailwind", "watch")

        assert mock_popen.call_count == entry_count
        stagger_calls = [c for c in mock_sleep.call_args_list if c.args == (_WATCH_SPAWN_STAGGER_S,)]
        assert len(stagger_calls) == expected_staggers, (
            f"expected {expected_staggers} stagger sleeps, got {len(stagger_calls)} of {mock_sleep.call_args_list}"
        )

    @pytest.mark.usefixtures("tmp_project")
    def test_watch_keyboard_interrupt_handling(self, settings: LazySettings, capsys: CaptureFixture[str]):
        """Test watch mode handles KeyboardInterrupt gracefully."""
        settings.TAILWIND_CLI_VERSION = "4.1.3"  # Avoid latest version fetch

        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.Popen") as mock_popen,
        ):
            # Mock download function to create actual file
            mock_download.side_effect = write_fake_cli
            mock_popen.side_effect = KeyboardInterrupt()

            call_command("tailwind", "watch")

            captured = capsys.readouterr()
            assert "Stopped watching for changes." in captured.out


# A manage.py for a project in its own directory, so a test can run real commands and SIGKILL them.
# Starts from tests.settings, as the suite does, and points the project at its directory like
# `tmp_project`. `_CSS_MAP_ENV` adds an admin/web `TAILWIND_CLI_CSS_MAP`.
_CSS_MAP_ENV = "TEST_TAILWIND_CLI_CSS_MAP"
_MANAGE_PY = f"""\
import os
import sys
from pathlib import Path

import django
from django.conf import settings
from django.core.management import execute_from_command_line

base = Path(__file__).resolve().parent
settings.BASE_DIR = base
settings.STATICFILES_DIRS = (base / "assets",)
settings.TAILWIND_CLI_PATH = base / "tailwindcss"
settings.TAILWIND_CLI_VERSION = "4.0.0"
if os.environ.get("{_CSS_MAP_ENV}"):
    settings.TAILWIND_CLI_CSS_MAP = [("admin.css", "admin.output.css"), ("web.css", "web.output.css")]
django.setup()

from django_tailwind_cli.management.commands import _process

_process._WATCH_SPAWN_STAGGER_S = 0

execute_from_command_line(sys.argv)
"""

# Runs its argv as a shell does, without a lifeline.
_SHELL_PARENT = [sys.executable, "-c", "import subprocess, sys; subprocess.run(sys.argv[1:])"]


def _start_manage_py(
    tmp_path: Path, args: list[str], *, multi: bool = False, parent: list[str] | None = None, **popen_kwargs: Any
) -> subprocess.Popen[Any]:
    """Run `_MANAGE_PY` with ``args`` in ``tmp_path``, below ``parent`` if given."""
    manage_py = tmp_path / "manage.py"
    manage_py.write_text(_MANAGE_PY)
    repo_root = Path(__file__).resolve().parent.parent
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "tests.settings",
        "PYTHONPATH": str(repo_root),
        "PYTHONUNBUFFERED": "1",
    }
    if multi:
        env[_CSS_MAP_ENV] = "1"
    return subprocess.Popen(
        [*(parent or []), sys.executable, str(manage_py), *args], cwd=tmp_path, env=env, **popen_kwargs
    )


@pytest.mark.skipif(sys.platform == "win32", reason="the fake CLI is a shell script")
@pytest.mark.timeout(30)
def test_a_failing_watcher_ends_the_command_under_the_reloader(tmp_path: Path):
    """The reloader runs the watch loop in a thread, where a CommandError used to end only that thread.

    The reloader and ``--noreload`` report the failure in the same words.
    """
    install_python_cli(tmp_path / "tailwindcss", "sys.exit(2)\n")

    stderrs: list[str] = []
    for args in (["tailwind", "watch"], ["tailwind", "watch", "--noreload"]):
        watch_process = _start_manage_py(
            tmp_path, args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        try:
            _, stderr = watch_process.communicate(timeout=15)
        finally:
            watch_process.kill()
        assert watch_process.returncode == 1, args
        stderrs.append(stderr.decode())

    under_reloader, without_reloader = stderrs
    assert "❌ Command error: Watch process for 'tailwind' exited with code 2" in under_reloader
    assert "Traceback" not in under_reloader
    assert under_reloader == without_reloader


def _wait_for(condition: Callable[[], bool], what: str, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.05)


def _is_running(pid: int, kill: Callable[[int, int], None] = os.kill) -> bool:
    """Whether the process, or with ``os.killpg`` the process group, still exists."""
    try:
        kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


_RUNSERVER = ["tailwind", "runserver", "--force-default-runserver", "127.0.0.1:0"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals and pipes")
@pytest.mark.timeout(30)
@pytest.mark.parametrize(
    "args,multi,parent,survives",
    [
        (["tailwind", "watch", "--noreload"], False, None, False),
        (["tailwind", "watch", "--noreload"], True, None, False),
        (["tailwind", "watch"], True, None, False),
        (_RUNSERVER, True, None, False),
        (["tailwind", "watch"], False, _SHELL_PARENT, True),
    ],
    ids=["noreload-single", "noreload-multi", "reloader", "runserver", "background"],
)
def test_processes_after_sigkill(
    tmp_path: Path, args: list[str], multi: bool, parent: list[str] | None, survives: bool
):
    """Nothing `tailwind watch` or `tailwind runserver` starts may outlive it, even after SIGKILL.

    "reloader" kills Django's reloader parent while the watcher runs in its child. "runserver" kills
    `tailwind runserver` while Django's runserver and its reloader child run. "background" kills a
    parent without a lifeline, as a shell is, and the watcher has to keep running.
    """
    install_stdin_wait_cli(tmp_path / "tailwindcss")
    (tmp_path / "admin.css").write_text('@import "tailwindcss";')
    (tmp_path / "web.css").write_text('@import "tailwindcss";')
    outputs = ["admin.output.css", "web.output.css"] if multi else ["css/tailwind.css"]
    pid_files = [tmp_path / "assets" / output for output in outputs]
    # The test holds this stdin open, as a terminal does, so only the command can end the watcher.
    terminal_read, terminal_write = os.pipe()
    process = _start_manage_py(
        tmp_path,
        args,
        multi=multi,
        parent=parent,
        stdin=terminal_read,
        # Only the runserver case reads stdout. An unread pipe can fill and block the children.
        stdout=subprocess.PIPE if args == _RUNSERVER else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Its own process group, so the finally block also reaches orphaned children.
        start_new_session=True,
    )
    os.close(terminal_read)
    try:
        _wait_for(lambda: all(f.exists() and f.read_text() for f in pid_files), "the watchers to start")
        cli_pids = [int(f.read_text()) for f in pid_files]
        if args == _RUNSERVER:
            assert process.stdout is not None
            # Django prints this line once its reloader child serves.
            for line in process.stdout:
                if b"Quit the server with" in line:
                    break
            else:
                pytest.fail("Django's runserver did not start")

        process.kill()
        process.wait()

        if survives:
            time.sleep(0.3)
            assert all(_is_running(pid) for pid in cli_pids)
        else:
            _wait_for(lambda: not _is_running(process.pid, os.killpg), "every process in the group to exit")
    finally:
        os.close(terminal_write)
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        if process.stdout is not None:
            process.stdout.close()


class TestProcessManagerIntegration:
    """Test ProcessManager for runserver integration."""

    def test_process_manager_initialization(self):
        """Test ProcessManager creates clean initial state."""
        manager = ProcessManager()
        assert manager.processes == []
        assert manager.shutdown_requested is False

    def test_children_get_no_lifeline_on_windows(self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture):
        """Popen refuses ``pass_fds`` on Windows, so neither child may get it there."""
        monkeypatch.setattr(sys, "platform", "win32")
        popen = mocker.patch("subprocess.Popen")
        mocker.patch("signal.signal")
        mocker.patch("time.sleep")
        mocker.patch.object(ProcessManager, "_monitor_processes")

        ProcessManager().start_concurrent_processes(["watch"], ["server"])

        assert popen.call_count == 2
        assert all("pass_fds" not in call.kwargs for call in popen.call_args_list)

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


class TestBunStderrFilter:
    """Pattern-match and drain logic for filtering Bun native-runtime crash traces."""

    @pytest.mark.parametrize(
        "line",
        [
            "EIO: i/o error, read\n",
            "      fd: 7,\n",
            ' syscall: "read",\n',
            "   errno: -5,\n",
            '    code: "EIO"\n',
            "Bun v1.2.8 (macOS arm64)\n",
            "error: dlopen(/$bunfs/root/watcher-tzt47keb.node, 0x0001): tried...\n",
            "      at <anonymous> (/$bunfs/root/tailwindcss-macos-arm64:22717:29)\n",
            '    code: "ERR_DLOPEN_FAILED"\n',
            "22716 |   module.exports = __require(...);\n",
            "                                    ^\n",
        ],
    )
    def test_is_bun_noise_drops_known_patterns(self, line: str):
        assert _is_bun_noise(line) is True

    @pytest.mark.parametrize(
        "line",
        [
            "≈ tailwindcss v4.1.3\n",
            "Done in 32ms\n",
            '[ERROR] Could not resolve "tailwindcss"\n',
            "Watching 'admin': /path/to/admin.css\n",
            "warn - Cannot find module './foo'\n",
            "\n",  # blank line — drained but not filtered
        ],
    )
    def test_is_bun_noise_keeps_legitimate_lines(self, line: str):
        assert _is_bun_noise(line) is False

    def test_drain_filtered_stderr_drops_bun_noise(self, capsys: CaptureFixture[str]):
        stream = io.StringIO(
            "Done in 32ms\n"
            "EIO: i/o error, read\n"
            "      fd: 7,\n"
            "Bun v1.2.8 (macOS arm64)\n"
            '[ERROR] Could not resolve "tailwindcss"\n'
        )

        _drain_filtered_stderr(stream, lambda: False)

        err = capsys.readouterr().err
        assert "Done in 32ms" in err
        assert "[ERROR] Could not resolve" in err
        assert "EIO" not in err
        assert "Bun v" not in err
        assert "fd: 7" not in err

    def test_drain_filtered_stderr_drops_everything_after_shutdown(self, capsys: CaptureFixture[str]):
        """Post-shutdown stderr is just churn from terminating subprocesses; drop it."""
        stream = io.StringIO("Done in 32ms\n[ERROR] something legit\n")

        _drain_filtered_stderr(stream, lambda: True)

        err = capsys.readouterr().err
        assert err == ""


class TestCLIDownloadIntegration:
    """Test CLI download and setup workflows."""

    @pytest.mark.usefixtures("tmp_project")
    def test_cli_download_announces_start_and_completion(self, capsys: CaptureFixture[str]):
        """The command announces start and completion; byte progress is covered in test_http.py."""
        with patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli):
            call_command("tailwind", "download_cli")

            captured = capsys.readouterr()
            assert "Downloading Tailwind CSS CLI..." in captured.out
            assert "Download completed!" in captured.out

    @pytest.mark.usefixtures("tmp_project")
    def test_cli_permissions_after_download(self):
        """Test CLI gets correct executable permissions after download."""
        with patch("django_tailwind_cli.utils.http.download_with_progress", side_effect=write_fake_cli):
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
    @pytest.mark.usefixtures("tmp_project")
    def test_platform_specific_cli_paths(self, mock_system: str, expected_extension: str):
        """Test CLI paths are platform-appropriate."""
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
            mock_download.side_effect = write_fake_cli
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            # Should not raise exception
            call_command("tailwind", "build")

            # Verify paths were handled correctly
            config = get_config()
            assert " " in str(config.cli_path)
            assert config.cli_path.exists()


class TestErrorRecoveryScenarios:
    """Test error recovery and resilience scenarios."""

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
            mock_download.side_effect = write_fake_cli
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            # Should create missing directories and complete build
            call_command("tailwind", "build")

            config = get_config()
            assert config.cli_path.exists()
            assert config.src_css.exists()

    def test_handling_of_permission_errors(self, settings: LazySettings, tmp_project: Path):
        """Test handling of permission errors during file operations."""
        # Create directory with restricted permissions (Unix only)
        if platform.system() != "Windows":
            restricted_dir = tmp_project / "restricted"
            restricted_dir.mkdir(mode=0o000)  # No permissions
            settings.TAILWIND_CLI_PATH = restricted_dir / "cli"

            try:
                with patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download:
                    mock_download.side_effect = write_fake_cli

                    # Matching the errno rather than "Permission denied": glibc localises
                    # strerror, so the text depends on the contributor's locale.
                    with pytest.raises(CommandError, match=r"\[Errno 13\]"):
                        call_command("tailwind", "download_cli")
            finally:
                # `finally`, not a trailing statement: a 0o000 directory that outlives the test is
                # one pytest can never delete, so it renames it to garbage-* and warns about it on
                # every run from then on. Three of those had accumulated.
                restricted_dir.chmod(0o755)


@pytest.mark.usefixtures("bypass_autoreload")
class TestVerboseLoggingIntegration:
    """Test verbose logging across different commands."""

    @pytest.mark.usefixtures("tmp_project")
    def test_build_verbose_logging(self, capsys: CaptureFixture[str]):
        """Test verbose logging in build command."""
        with (
            patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download,
            patch("subprocess.run") as mock_subprocess,
        ):
            # Mock download function to create actual file
            mock_download.side_effect = write_fake_cli
            mock_subprocess.return_value = Mock(returncode=0, stdout="Build output", stderr="")

            call_command("tailwind", "build", "--verbose")

            captured = capsys.readouterr()
            assert "🏗️  Starting Tailwind CSS build process..." in captured.out
            assert "⚙️  Setting up Tailwind environment..." in captured.out
            assert "✅ Build completed in" in captured.out

    @pytest.mark.usefixtures("tmp_project", "stub_watch_popen")
    def test_watch_verbose_logging(self, capsys: CaptureFixture[str]):
        """Test verbose logging in watch command."""
        with patch("django_tailwind_cli.utils.http.download_with_progress") as mock_download:
            # Mock download function to create actual file
            mock_download.side_effect = write_fake_cli

            call_command("tailwind", "watch", "--verbose")

            captured = capsys.readouterr()
            assert "👀 Starting Tailwind CSS watch mode..." in captured.out
            assert "🔄 Starting file watcher..." in captured.out
