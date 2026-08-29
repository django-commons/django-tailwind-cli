"""Getting the Tailwind CLI binary onto disk.

A managed download carries its version in the filename, so a version bump lands on a path that does
not exist yet. A binary the user placed at `TAILWIND_CLI_PATH` does not, which is why the version
is read out of it and a mismatch is reported rather than resolved by overwriting somebody's file.
"""

from __future__ import annotations

import os
from pathlib import Path

import click
from django.conf import settings
from django.core.management.base import CommandError

from django_tailwind_cli.config import detect_binary_version, get_config, maybe_warn_version_mismatch
from django_tailwind_cli.utils import http


def ensure_default_gitignore() -> None:
    """Drop a single-star .gitignore into the managed `.django_tailwind_cli/` dir.

    The pattern ``*`` ignores every file in the directory — including the
    .gitignore itself — so ``git add .`` silently skips the whole folder
    without the user having to touch their project-level .gitignore.

    Only acts when ``TAILWIND_CLI_PATH`` is unset (default mode). Custom
    paths are left alone: we don't own them and a stray .gitignore there
    could conflict with whatever the user is doing.
    """
    if getattr(settings, "TAILWIND_CLI_PATH", None):
        return
    default_dir = Path(settings.BASE_DIR) / ".django_tailwind_cli"
    if not default_dir.exists():
        return
    gitignore = default_dir / ".gitignore"
    if gitignore.exists():
        return  # Respect whatever the user put there
    gitignore.write_text("*\n")


def _download_cli_with_progress(url: str, filepath: Path) -> None:
    """Download CLI with progress indication.

    Args:
        url: Download URL.
        filepath: Destination file path.
    """
    last_progress = 0

    def progress_callback(downloaded: int, total_size: int, progress: float) -> None:
        nonlocal last_progress
        # Show progress every 10%
        if total_size > 0 and int(progress / 10) > int(last_progress / 10):
            click.secho(f"Progress: {progress:.1f}% ({downloaded}/{total_size} bytes)", fg="cyan")
            last_progress = progress

    try:
        click.secho("Downloading Tailwind CSS CLI...", fg="yellow")
        http.download_with_progress(url, filepath, timeout=30, progress_callback=progress_callback)
        click.secho("Download completed!", fg="green")

    except http.RequestError as e:
        raise CommandError(f"Failed to download Tailwind CSS CLI: {e}") from e


def _is_cli_usable(cli_path: Path) -> bool:
    """Return True if the CLI binary is present and executable.

    The version is not consulted here. For a managed download it is part of the filename, so a
    version bump lands on a path that does not exist yet; for a binary the user supplied,
    ``ensure_cli_binary`` warns about a mismatch before reaching this point.
    """
    return cli_path.exists() and os.access(cli_path, os.X_OK)


def ensure_cli_binary(*, verbose: bool = False, force_download: bool = False) -> None:
    """Assure that the CLI is loaded with optional verbose logging."""
    c = get_config()

    if verbose:
        click.secho("🔍 Checking Tailwind CSS CLI availability...", fg="cyan")
        click.secho(f"   • CLI Path: {c.cli_path}", fg="blue")
        click.secho(f"   • Version: {c.version_str}", fg="blue")
        click.secho(f"   • Download URL: {c.download_url}", fg="blue")
        click.secho(f"   • Automatic download: {c.automatic_download}", fg="blue")

    # A binary that is not ours — a system binary, or a file placed at TAILWIND_CLI_PATH — carries
    # no version in its name, so the only way to notice a TAILWIND_CLI_VERSION bump is to ask the
    # binary. A managed download does carry it, and asking would mean a subprocess on every build
    # plus a false alarm for forks whose release tags differ from the Tailwind version they bundle.
    if not force_download and not c.manages_cli_binary:
        maybe_warn_version_mismatch(c.cli_path, c.version_str)

    # System-binary mode: the CLI lives on PATH, never download it.
    if c.uses_system_binary:
        if verbose:
            click.secho("✅ Using system Tailwind CSS CLI — download skipped", fg="green")
        click.secho(
            f"Using system Tailwind CSS CLI at '{c.cli_path}'.",
            fg="green",
        )
        return

    if not force_download and not c.automatic_download:
        if not c.cli_path.exists():
            if verbose:
                click.secho("❌ CLI not found and automatic download is disabled", fg="red")
            raise CommandError(
                "Automatic download of Tailwind CSS CLI is deactivated. Please download the Tailwind CSS CLI manually."
            )
        if verbose:
            click.secho("✅ CLI found, automatic download not needed", fg="green")
        return

    # Use optimized CLI check for existing installations
    if not force_download and _is_cli_usable(c.cli_path):
        if verbose:
            click.secho("✅ CLI is up-to-date and functional", fg="green")
        click.secho(
            f"Tailwind CSS CLI already exists at '{c.cli_path}'.",
            fg="green",
        )
        return

    if verbose:
        click.secho("📥 Starting CLI download...", fg="cyan")

    if not c.manages_cli_binary and c.cli_path.exists():
        click.secho(
            f"⚠️  Replacing '{c.cli_path}', which was not downloaded by django-tailwind-cli.",
            fg="yellow",
            bold=True,
        )
        click.secho(
            "   TAILWIND_CLI_PATH points straight at this file, so the download overwrites it.\n"
            "   Point TAILWIND_CLI_PATH at a directory to keep your own build alongside.",
            fg="yellow",
        )
    else:
        click.secho("Tailwind CSS CLI not found.", fg="red")

    click.secho(f"Downloading Tailwind CSS CLI from '{c.download_url}'.", fg="yellow")

    # Download with progress indication
    _download_cli_with_progress(c.download_url, c.cli_path)

    # Make CLI executable
    c.cli_path.chmod(0o755)

    # detect_binary_version is cached per path for the life of the process; the file behind that
    # path just changed, so the cached reading is now wrong.
    detect_binary_version.cache_clear()

    if verbose:
        import stat

        file_stats = c.cli_path.stat()
        click.secho(f"📁 File permissions: {stat.filemode(file_stats.st_mode)}", fg="blue")
        click.secho(f"📏 File size: {file_stats.st_size:,} bytes", fg="blue")

    click.secho(f"Downloaded Tailwind CSS CLI to '{c.cli_path}'.", fg="green")
