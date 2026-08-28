"""Running the Tailwind CLI alongside something else, and shutting both down cleanly.

`tailwind runserver` pairs one watcher with Django's development server; `tailwind watch` runs one watcher per
CSS entry once there is more than one of them. The lifecycle is the same either way — spawn,
watch for an unexpected exit, terminate on Ctrl+C, escalate to kill if that hangs — so it lives in
one place and the two entry points differ only in what they start and how they report.
"""

from __future__ import annotations

import re
import signal
import sys
import subprocess
import threading
import time
from collections.abc import Callable
from types import FrameType
from typing import IO

import typer
from django.conf import settings

from django_tailwind_cli.config import Config


# Bun-built tailwindcss occasionally leaks unhandled native-module errors
# (DLOPEN race on startup, EIO on shutdown when its watch FD is closed under
# it). The traces are upstream noise — neither actionable nor caused by
# user code. We drop matching lines from forwarded stderr while keeping
# Tailwind's own diagnostics intact.
_BUN_NOISE = re.compile(
    r"""
    ^EIO:\ i/o\ error          |   # EIO header
    ^Bun\ v\d                  |   # crash footer
    ^error:\ dlopen\(          |   # DLOPEN header
    ^\d+\ ?\|                  |   # numbered source-context line
    ^\s+(?:fd|syscall|errno|code):  |   # error-detail field
    ^\s+at\ <anonymous>\ \(/\$bunfs/   |   # bunfs stack frame
    ^\s+\^\s*$                 |   # caret pointer
    ^\s+code:\s*"(?:EIO|ERR_DLOPEN_FAILED)"   # error-code value
    """,
    re.VERBOSE,
)

# Delay between successive multi-watch Popen calls. The Bun-built tailwindcss
# standalone binary extracts its embedded @parcel/watcher native module to
# /$bunfs/ on first use; two parallel spawns race on the same path and one
# crashes with ERR_DLOPEN_FAILED. Staggering by 300 ms sidesteps the race
# without being noticeable in interactive use.
_WATCH_SPAWN_STAGGER_S = 0.3


def _is_bun_noise(line: str) -> bool:
    """Return True if the line looks like a Bun native-runtime crash trace."""
    return bool(_BUN_NOISE.match(line))


def _drain_filtered_stderr(stream: IO[str], is_shutting_down: Callable[[], bool]) -> None:
    """Forward subprocess stderr to the parent's stderr, dropping Bun noise.

    Runs in a daemon thread until the subprocess closes the pipe. Drops every
    line once `is_shutting_down()` returns True — post-shutdown stderr is not
    actionable and just churns output during cleanup.
    """
    for line in stream:
        if is_shutting_down() or _is_bun_noise(line):
            continue
        sys.stderr.write(line)
        sys.stderr.flush()


class _BaseProcessManager:
    """Spawn processes, watch them, and take them all down together."""

    # Printed once on Ctrl+C or SIGTERM, before anything is terminated.
    _SHUTDOWN_MESSAGE = "\nShutdown signal received, stopping processes..."

    # Printed once every managed process is gone. None for the runserver pairing, where the server's
    # own shutdown output already says what happened.
    _SHUTDOWN_NOTICE: str | None = None

    def __init__(self) -> None:
        self.processes: list[subprocess.Popen[str]] = []
        self.shutdown_requested = False

    def _signal_handler(self, _signum: int, _frame: FrameType | None) -> None:
        """Adapter for signal.signal — delegates to the idempotent shutdown request."""
        self._request_shutdown()

    def _request_shutdown(self) -> None:
        """Print the shutdown message once and flip the flag. Idempotent.

        Cleanup is owned by the entry point's finally.
        """
        if self.shutdown_requested:
            return
        typer.secho(self._SHUTDOWN_MESSAGE, fg=typer.colors.YELLOW)
        self.shutdown_requested = True

    def _monitor_processes(self) -> None:
        """Monitor running processes. Cleanup is owned by the entry point's finally."""
        while not self.shutdown_requested and any(p.poll() is None for p in self.processes):
            time.sleep(0.5)

            # Check if any process has exited unexpectedly
            for index, process in enumerate(self.processes):
                if process.poll() is not None and process.returncode != 0:
                    typer.secho(self._exit_notice(index, process.returncode), fg=typer.colors.RED)
                    self.shutdown_requested = True
                    break

    def _cleanup_processes(self) -> None:
        """Terminate every managed process, escalating to kill if one will not go."""
        for process in self.processes:
            if process.poll() is None:
                try:
                    # Try graceful shutdown first
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        # Force kill if graceful shutdown fails
                        process.kill()
                        process.wait()
                except (OSError, subprocess.SubprocessError):
                    # Process might have already exited
                    pass

        self.processes.clear()

        if self._SHUTDOWN_NOTICE:
            typer.secho(self._SHUTDOWN_NOTICE, fg=typer.colors.GREEN)

    def _exit_notice(self, index: int, returncode: int) -> str:  # noqa: ARG002
        """Describe a process that died on its own. Overridden where the index means something."""
        return f"Process exited with code {returncode}"


class ProcessManager(_BaseProcessManager):
    """One Tailwind watcher beside Django's development server."""

    def start_concurrent_processes(self, watch_cmd: list[str], server_cmd: list[str]) -> None:
        """Start watch and server processes concurrently with proper cleanup.

        Args:
            watch_cmd: Command to start Tailwind watch process.
            server_cmd: Command to start Django development server.
        """
        # SIGINT propagates as KeyboardInterrupt via Python's default handler.
        # Override SIGTERM only on the main thread — signal.signal() raises
        # ValueError in worker threads (e.g. under Django's autoreloader).
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            # Start Tailwind watch process — inherit stdout/stderr so the
            # user sees watch output live and we avoid a pipe-fill deadlock:
            # the OS pipe buffer (~64 KB on Linux) would otherwise fill up
            # after a few minutes of rebuilds and block the watcher.
            watch_process = subprocess.Popen(
                watch_cmd,
                cwd=settings.BASE_DIR,
                text=True,
            )
            self.processes.append(watch_process)
            typer.secho("Started Tailwind CSS watch process", fg=typer.colors.GREEN)

            # Give Tailwind a moment to start
            time.sleep(1)

            # Start Django development server
            server_process = subprocess.Popen(
                server_cmd,
                cwd=settings.BASE_DIR,
                text=True,
            )
            self.processes.append(server_process)
            typer.secho("Started Django development server", fg=typer.colors.GREEN)

            self._monitor_processes()
        except KeyboardInterrupt:
            self._request_shutdown()
        except Exception as e:
            typer.secho(f"Error starting processes: {e}", fg=typer.colors.RED)
            raise
        finally:
            self._cleanup_processes()


class MultiWatchProcessManager(_BaseProcessManager):
    """One Tailwind watcher per entry in TAILWIND_CLI_CSS_MAP."""

    _SHUTDOWN_MESSAGE = "\nShutdown signal received, stopping watch processes..."
    _SHUTDOWN_NOTICE = "Stopped watching for changes."

    def _exit_notice(self, index: int, returncode: int) -> str:
        return f"Watch process {index} exited with code {returncode}"

    def start_watch_processes(self, config: Config, *, verbose: bool = False) -> None:
        """Start watch processes for all CSS entries.

        Args:
            config: Configuration object with css_entries.
            verbose: Whether to show detailed information.
        """
        # SIGINT propagates as KeyboardInterrupt via Python's default handler.
        # Override SIGTERM only on the main thread — signal.signal() raises
        # ValueError in worker threads (e.g. under Django's autoreloader).
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            for index, entry in enumerate(config.css_entries):
                if index > 0:
                    time.sleep(_WATCH_SPAWN_STAGGER_S)

                watch_cmd = config.get_watch_cmd(entry)
                if verbose:
                    typer.secho(f"🚀 Starting watch for '{entry.name}'...", fg=typer.colors.CYAN)
                    typer.secho(f"   • Command: {' '.join(watch_cmd)}", fg=typer.colors.BLUE)

                # Inherit stdout (high-volume rebuild progress) to avoid a pipe-fill
                # deadlock — the OS pipe buffer would otherwise block the watcher
                # after ~64 KB. stderr is captured so we can filter Bun's native-
                # runtime noise (DLOPEN race, EIO on shutdown) before it hits the
                # terminal; volume there is low enough that the drain thread keeps
                # up easily.
                process = subprocess.Popen(
                    watch_cmd,
                    cwd=settings.BASE_DIR,
                    text=True,
                    stderr=subprocess.PIPE,
                )
                self.processes.append(process)
                if process.stderr is not None:
                    threading.Thread(
                        target=_drain_filtered_stderr,
                        args=(process.stderr, lambda: self.shutdown_requested),
                        daemon=True,
                    ).start()
                typer.secho(f"Watching '{entry.name}': {entry.src_css}", fg=typer.colors.GREEN)

            self._monitor_processes()
        except KeyboardInterrupt:
            self._request_shutdown()
        except Exception as e:
            typer.secho(f"Error starting watch processes: {e}", fg=typer.colors.RED)
            raise
        finally:
            self._cleanup_processes()
