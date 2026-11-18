"""Running the Tailwind CLI alongside something else, and shutting both down cleanly.

`tailwind runserver` pairs one watcher with Django's development server; `tailwind watch` runs one watcher per
CSS entry. The lifecycle is the same either way: spawn, watch for an unexpected exit, terminate on
Ctrl+C, escalate to kill if that hangs. It lives in one place, and the two entry points differ only
in what they start and how they report.
"""

from __future__ import annotations

import os
import re
import signal
import sys
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from functools import partial
from types import FrameType
from typing import IO, Any

import click
from django.conf import settings
from django.core.management.base import CommandError

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


@contextmanager
def lifeline(*, inheritable: bool = False) -> Iterator[int]:
    """Yield the read end of a pipe whose write end only this process holds.

    The read end reaches EOF when the write end closes: on leaving this block, or when this process
    dies, also by SIGKILL. A child that reads it learns that this process is gone.

    The Tailwind CLI gets one as stdin, because it ends `--watch` on stdin EOF. An inherited stdin
    can be at EOF from the start, for example in a parallel `mise run` task. A `tailwind watch`
    child gets an inheritable one through `LIFELINE_ENV`, see `stop_with_lifeline`.
    """
    read_fd, write_fd = os.pipe()
    if inheritable:
        os.set_inheritable(read_fd, True)
    try:
        yield read_fd
    finally:
        os.close(write_fd)
        os.close(read_fd)


# The file descriptor number of an inherited lifeline read end.
LIFELINE_ENV = "TAILWIND_CLI_LIFELINE_FD"


@contextmanager
def exported_lifeline() -> Iterator[None]:
    """Hold an inheritable lifeline whose read end `LIFELINE_ENV` names for child processes.

    Django's reloader starts its child with ``close_fds=False``, so the child inherits it.
    """
    previous = os.environ.get(LIFELINE_ENV)
    with lifeline(inheritable=True) as read_fd:
        os.environ[LIFELINE_ENV] = str(read_fd)
        try:
            yield
        finally:
            if previous is None:
                del os.environ[LIFELINE_ENV]
            else:
                os.environ[LIFELINE_ENV] = previous


def _lifeline_popen_kwargs(read_fd: int) -> dict[str, Any]:
    """Return the Popen arguments that hand a child the lifeline ``read_fd``.

    Windows has no ``pass_fds``, so a child there gets no lifeline.
    """
    if sys.platform == "win32":
        return {}
    return {"env": {**os.environ, LIFELINE_ENV: str(read_fd)}, "pass_fds": (read_fd,)}


def stop_with_lifeline() -> None:
    """Send this process SIGTERM once the lifeline from `LIFELINE_ENV` reaches EOF.

    `tailwind runserver` hands a lifeline to its watch and server children. Django's reloader parent
    hands one to its `tailwind watch` child. A SIGKILL to the parent skips its cleanup, and without
    the lifeline its children keep running. Django's reloader turns SIGTERM into `sys.exit`, which
    also ends the reloader child. A watch process that exits closes the Tailwind CLI's stdin.
    Without the variable, for example in a `tailwind watch` started from a shell, nothing happens.
    """
    fd = os.environ.get(LIFELINE_ENV)
    if fd is None:
        return

    def wait() -> None:
        try:
            while os.read(int(fd), 1):
                pass
        except OSError:
            # The descriptor did not survive into this process; there is no lifeline to wait on.
            return
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=wait, daemon=True).start()


def _is_bun_noise(line: str) -> bool:
    """Return True if the line looks like a Bun native-runtime crash trace."""
    return bool(_BUN_NOISE.match(line))


def _drain_filtered_stderr(stream: IO[str], is_shutting_down: Callable[[], bool]) -> None:
    """Forward subprocess stderr to the parent's stderr, dropping Bun noise.

    Runs in a daemon thread until the subprocess closes the pipe, then closes the stream. Drops every
    line once `is_shutting_down()` returns True: post-shutdown stderr is not actionable and just
    churns output during cleanup.
    """
    with stream:
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

    # Whether a failed process is reported as soon as it is noticed.
    _PRINTS_FAILURE = True

    def __init__(self) -> None:
        self.processes: list[subprocess.Popen[str]] = []
        self.shutdown_requested = False
        # The process that ended with an error first.
        self.failed_process: subprocess.Popen[str] | None = None
        self._drain_threads: list[threading.Thread] = []

    @property
    def failure(self) -> str | None:
        """The exit notice of the failed process, if one failed."""
        if self.failed_process is None:
            return None
        return self._exit_notice(self.failed_process, self.failed_process.returncode)

    def _signal_handler(self, _signum: int, _frame: FrameType | None) -> None:
        """Adapter for signal.signal — delegates to the idempotent shutdown request."""
        self._request_shutdown()

    def _request_shutdown(self) -> None:
        """Print the shutdown message once and flip the flag. Idempotent.

        Cleanup is owned by the entry point's finally.
        """
        if self.shutdown_requested:
            return
        click.secho(self._SHUTDOWN_MESSAGE, fg="yellow")
        self.shutdown_requested = True

    def _monitor_processes(self) -> None:
        """Monitor running processes. Cleanup is owned by the entry point's finally."""
        while True:
            self._check_for_failure()
            if self.shutdown_requested or all(p.poll() is not None for p in self.processes):
                return
            time.sleep(0.5)

    def _check_for_failure(self) -> None:
        """Record and report the first process that ended with an error, and end the watch.

        A process ended by SIGINT or SIGTERM is no failure. Ctrl+C signals the whole process group,
        so the watchers can end before this process stops them.
        """
        for process in self.processes:
            if process.poll() not in (None, 0, -signal.SIGINT, -signal.SIGTERM):
                self.failed_process = process
                if self._PRINTS_FAILURE:
                    click.secho(self.failure, fg="red")
                self.shutdown_requested = True
                return

    def _cleanup_processes(self) -> None:
        """Terminate every managed process, escalating to kill if one will not go."""
        running = [process for process in self.processes if process.poll() is None]
        for process in running:
            try:
                process.terminate()
            except OSError:
                # Process might have already exited
                pass
        # One deadline for all of them, so N stubborn processes take 5 seconds, not 5 * N.
        deadline = time.monotonic() + 5
        for process in running:
            try:
                try:
                    process.wait(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            except (OSError, subprocess.SubprocessError):
                # Process might have already exited
                pass

        # The stderr of a process that ended can still sit in its pipe.
        deadline = time.monotonic() + 1
        for thread in self._drain_threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))
        self._drain_threads.clear()
        self.processes.clear()

        # After a failure the exit notice says what happened; a green notice would read as success.
        if self._SHUTDOWN_NOTICE and self.failure is None:
            click.secho(self._SHUTDOWN_NOTICE, fg="green")

    def _exit_notice(self, process: subprocess.Popen[str], returncode: int) -> str:  # noqa: ARG002
        """Describe a process that died on its own. Overridden where the process has a name."""
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

        stack = ExitStack()
        try:
            # Start Tailwind watch process — inherit stdout/stderr so the
            # user sees watch output live and we avoid a pipe-fill deadlock:
            # the OS pipe buffer (~64 KB on Linux) would otherwise fill up
            # after a few minutes of rebuilds and block the watcher.
            # The lifeline ends both children if this process dies without cleanup.
            lifeline_read = stack.enter_context(lifeline(inheritable=True))
            watch_process = subprocess.Popen(
                watch_cmd,
                cwd=settings.BASE_DIR,
                text=True,
                **_lifeline_popen_kwargs(lifeline_read),
            )
            self.processes.append(watch_process)
            click.secho("Started Tailwind CSS watch process", fg="green")

            # Give Tailwind a moment to start
            time.sleep(1)

            server_process = subprocess.Popen(
                server_cmd,
                cwd=settings.BASE_DIR,
                text=True,
                **_lifeline_popen_kwargs(lifeline_read),
            )
            self.processes.append(server_process)
            click.secho("Started Django development server", fg="green")

            self._monitor_processes()
        except KeyboardInterrupt:
            self._request_shutdown()
        except Exception as e:
            click.secho(f"Error starting processes: {e}", fg="red")
            raise
        finally:
            self._cleanup_processes()
            stack.close()


class MultiWatchProcessManager(_BaseProcessManager):
    """One Tailwind watcher per CSS entry, for one stylesheet or a TAILWIND_CLI_CSS_MAP."""

    _SHUTDOWN_MESSAGE = "\nShutdown signal received, stopping watch processes..."
    _SHUTDOWN_NOTICE = "Stopped watching for changes."
    # start_watch_processes raises the notice as a CommandError after cleanup.
    _PRINTS_FAILURE = False

    def __init__(self) -> None:
        super().__init__()
        self.entry_names: dict[subprocess.Popen[str], str] = {}

    def _exit_notice(self, process: subprocess.Popen[str], returncode: int) -> str:
        return f"Watch process for '{self.entry_names[process]}' exited with code {returncode}"

    def _drops_stderr_of(self, process: subprocess.Popen[str]) -> bool:
        return self.shutdown_requested and process is not self.failed_process

    def start_watch_processes(self, config: Config, *, stdin: int | None = None, verbose: bool = False) -> None:
        """Start watch processes for all CSS entries.

        Args:
            config: Configuration object with css_entries.
            stdin: File descriptor for every watcher's stdin, see `lifeline`. None inherits it.
            verbose: Whether to show detailed information.

        Raises:
            CommandError: A watcher ended with a non-zero exit code.
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
                    click.secho(f"🚀 Starting watch for '{entry.name}'...", fg="cyan")
                    click.secho(f"   • Command: {' '.join(watch_cmd)}", fg="blue")

                # Inherit stdout (high-volume rebuild progress) to avoid a pipe-fill
                # deadlock — the OS pipe buffer would otherwise block the watcher
                # after ~64 KB. stderr is captured so we can filter Bun's native-
                # runtime noise (DLOPEN race, EIO on shutdown) before it hits the
                # terminal; volume there is low enough that the drain thread keeps
                # up easily.
                # The CLI writes UTF-8 whatever the locale; a byte the locale cannot decode would
                # end the drain thread, and the full pipe would then block the watcher.
                process = subprocess.Popen(
                    watch_cmd,
                    cwd=settings.BASE_DIR,
                    encoding="utf-8",
                    errors="replace",
                    stdin=stdin,
                    stderr=subprocess.PIPE,
                )
                self.processes.append(process)
                self.entry_names[process] = entry.name
                if process.stderr is not None:
                    thread = threading.Thread(
                        target=_drain_filtered_stderr,
                        # The failed watcher's last lines say why; the others' shutdown output is noise.
                        args=(process.stderr, partial(self._drops_stderr_of, process)),
                        daemon=True,
                    )
                    thread.start()
                    self._drain_threads.append(thread)
                click.secho(f"Watching '{entry.name}': {entry.src_css}", fg="green")

            self._monitor_processes()
        except KeyboardInterrupt:
            self._request_shutdown()
        except Exception as e:
            click.secho(f"Error starting watch processes: {e}", fg="red")
            raise
        finally:
            self._cleanup_processes()
        if self.failure:
            raise CommandError(self.failure)
