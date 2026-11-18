"""Helpers shared across test modules.

Plain functions live here rather than in ``conftest.py``: pytest loads that module itself, and
importing from it is a pytest anti-pattern. Fixtures still belong in ``conftest.py``.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path


def write_fake_cli(
    url: str,
    filepath: Path,
    timeout: int = 30,
    progress_callback: Callable[[int, int, float], None] | None = None,
    *,
    content: bytes = b"fake-cli-binary",
) -> None:
    """Stand-in for ``http.download_with_progress`` that just puts bytes at the target path.

    The signature mirrors the real function because it is installed as a ``side_effect``, so it is
    called with the production call's arguments. ``content`` is keyword-only, which keeps it clear
    of that call.

    No chmod: the caller does that itself right after the download returns
    (``ensure_cli_binary``), so a stub that sets the mode only hides whether it does.

    Args:
        content: Bytes to write. Tests that assert on the file's content pass their own.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(content)


def install_fake_cli(path: Path, *, content: bytes = b"fake-cli-binary") -> Path:
    """Put an executable fake CLI binary at ``path``, as if it had already been installed.

    Not the same function as ``write_fake_cli``, and the chmod is why — see its docstring above.
    This one claims the binary is already there, so the executable bit is part of the claim.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    path.chmod(0o755)
    return path


# Shared start of the fake CLIs below: answer `--help` with a version line, otherwise find `--output`.
_FAKE_CLI_PREAMBLE = """\
import os
import select
import sys

if "--watch" not in sys.argv:
    print("tailwindcss v4.0.0")
    sys.exit(0)
output_path = sys.argv[sys.argv.index("--output") + 1]
os.makedirs(os.path.dirname(output_path), exist_ok=True)
"""

_STDIN_PROBE_TAIL = """\
ready, _, _ = select.select([sys.stdin], [], [], 0.1)
state = "eof" if ready and sys.stdin.buffer.read(1) == b"" else "open"
with open(output_path, "w") as output:
    output.write(state)
"""

_STDIN_WAIT_TAIL = """\
with open(output_path, "w") as output:
    output.write(str(os.getpid()))
sys.stdin.buffer.read()
"""


def install_python_cli(path: Path, tail: str) -> Path:
    """Put an executable fake CLI at ``path`` that runs the preamble plus ``tail`` with this interpreter.

    The preamble answers ``--help`` with a version line and sets ``output_path`` from ``--output``.

    A ``/bin/sh`` wrapper rather than a ``#!python`` shebang: the kernel rejects a shebang with
    spaces in the interpreter path or one longer than its limit.
    """
    script_path = path.with_name(f"{path.name}.py")
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(_FAKE_CLI_PREAMBLE + tail)
    wrapper = f'#!/bin/sh\nexec "{sys.executable}" -I -S "{script_path}" "$@"\n'
    return install_fake_cli(path, content=wrapper.encode())


def install_stdin_probe_cli(path: Path) -> Path:
    """Put an executable fake CLI at ``path`` that reports its stdin state when watching.

    The Tailwind 4 CLI ends ``--watch`` once stdin reaches EOF. This fake writes ``eof`` or
    ``open`` to its ``--output`` file instead, then exits so the watch command returns.
    POSIX only: ``select()`` on a pipe is not available on Windows.
    """
    return install_python_cli(path, _STDIN_PROBE_TAIL)


def install_stdin_wait_cli(path: Path) -> Path:
    """Put an executable fake CLI at ``path`` that watches until its stdin reaches EOF.

    It writes its PID to its ``--output`` file, then blocks on stdin, as the Tailwind 4 CLI does.
    POSIX only.
    """
    return install_python_cli(path, _STDIN_WAIT_TAIL)
