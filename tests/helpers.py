"""Helpers shared across test modules.

Plain functions live here rather than in ``conftest.py``: pytest loads that module itself, and
importing from it is a pytest anti-pattern. Fixtures still belong in ``conftest.py``.
"""

from __future__ import annotations

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
