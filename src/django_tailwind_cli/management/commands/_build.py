"""Running the Tailwind CLI, and deciding whether it needs running at all.

Watch lives here too: a single CSS entry runs the CLI directly, several hand off to
`_process.MultiWatchProcessManager`, and both are the same command from the outside.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import typer
from django.conf import settings
from django.core.management.base import CommandError

from django_tailwind_cli.config import get_config
from django_tailwind_cli.management.commands._download import ensure_cli_binary, ensure_default_gitignore
from django_tailwind_cli.management.commands._process import MultiWatchProcessManager
from django_tailwind_cli.management.commands._source_css import ensure_source_css


def run_watch_loop(*, verbose: bool = False) -> None:
    """Run the Tailwind CSS watch loop in the current process.

    This is invoked directly by ``tailwind watch --noreload`` and as the
    inner callable when Django's autoreload machinery spawns a child
    process for the default (auto-reload) path. On reload the entire
    child process is torn down and respawned, so this function starts
    from a clean slate every time — including a fresh get_config() call
    that picks up any INSTALLED_APPS or settings changes.
    """
    config = get_config()

    if verbose:
        typer.secho("👀 Starting Tailwind CSS watch mode...", fg=typer.colors.CYAN)
        typer.secho(f"   • CSS entries: {len(config.css_entries)}", fg=typer.colors.BLUE)
        for entry in config.css_entries:
            typer.secho(f"   • [{entry.name}] {entry.src_css} -> {entry.dist_css}", fg=typer.colors.BLUE)
        typer.secho(f"   • CLI Path: {config.cli_path}", fg=typer.colors.BLUE)
        typer.secho(f"   • Version: {config.version_str}", fg=typer.colors.BLUE)

    setup_tailwind_environment(verbose=verbose)

    if verbose:
        typer.secho("🔄 Starting file watcher...", fg=typer.colors.CYAN)

    if len(config.css_entries) == 1:
        # Single entry - use existing simple approach
        execute_tailwind_command(
            config.watch_cmd,
            success_message="Stopped watching for changes.",
            error_message="Failed to start in watch mode",
            capture_output=True,
            verbose=verbose,
        )
    else:
        # Multiple entries - use multi-process manager
        manager = MultiWatchProcessManager()
        manager.start_watch_processes(config, verbose=verbose)


def should_rebuild_css(src_css: Path, dist_css: Path) -> bool:
    """Check if CSS should be rebuilt based on file modification times.

    Args:
        src_css: Source CSS file path.
        dist_css: Distribution CSS file path.

    Returns:
        True if CSS should be rebuilt.
    """
    if not dist_css.exists():
        return True

    if not src_css.exists():
        return True

    try:
        src_mtime = src_css.stat().st_mtime
        dist_mtime = dist_css.stat().st_mtime
        return src_mtime > dist_mtime
    except OSError:
        # If we can't get modification times, rebuild to be safe
        return True


def setup_tailwind_environment(*, verbose: bool = False) -> None:
    """Put everything `build` and `watch` need in place: the binary, the source CSS, the gitignore."""
    if verbose:
        typer.secho("⚙️  Setting up Tailwind environment...", fg=typer.colors.CYAN)
    ensure_cli_binary(verbose=verbose)
    ensure_source_css(verbose=verbose)
    ensure_default_gitignore()


def execute_tailwind_command(
    cmd: list[str],
    *,
    success_message: str,
    error_message: str,
    capture_output: bool = True,
    verbose: bool = False,
) -> None:
    """Execute a Tailwind command with consistent error handling and optional verbose output.

    Args:
        cmd: Command to execute.
        success_message: Message to display on success.
        error_message: Message prefix for errors.
        capture_output: Whether to capture subprocess output.
        verbose: Whether to show detailed execution information.
    """
    try:
        if verbose:
            typer.secho(f"🚀 Executing: {' '.join(cmd)}", fg=typer.colors.CYAN)
            typer.secho(f"   • Working directory: {settings.BASE_DIR}", fg=typer.colors.BLUE)
            typer.secho(f"   • Capture output: {capture_output}", fg=typer.colors.BLUE)

        start_time = time.time()

        if capture_output:
            result = subprocess.run(cmd, cwd=settings.BASE_DIR, check=True, capture_output=True, text=True)
            if verbose and result.stdout:
                typer.secho("📤 Command output:", fg=typer.colors.BLUE)
                typer.echo(result.stdout)
        else:
            subprocess.run(cmd, cwd=settings.BASE_DIR, check=True)

        if verbose:
            end_time = time.time()
            execution_time = end_time - start_time
            typer.secho(f"⏱️  Command completed in {execution_time:.3f}s", fg=typer.colors.GREEN)

        typer.secho(success_message, fg=typer.colors.GREEN)
    except KeyboardInterrupt:
        if "build" in error_message.lower():
            typer.secho("Canceled building production stylesheet.", fg=typer.colors.RED)
        elif "watch" in error_message.lower():
            typer.secho("Stopped watching for changes.", fg=typer.colors.RED)
        else:
            typer.secho(f"Canceled {error_message.lower()}.", fg=typer.colors.RED)
    except subprocess.CalledProcessError as e:  # pragma: no cover
        if verbose:
            typer.secho(f"❌ Command failed with exit code {e.returncode}", fg=typer.colors.RED)
            if e.stdout:
                typer.secho("📤 Standard output:", fg=typer.colors.BLUE)
                typer.echo(e.stdout)
            if e.stderr:
                typer.secho("📢 Standard error:", fg=typer.colors.RED)
                typer.echo(e.stderr)

        error_detail = e.stderr if e.stderr else "An unknown error occurred."
        # Raised rather than exited: SystemExit is a BaseException, so handle_command_errors would
        # never see it, and call_command would take the host process down with it.
        raise CommandError(f"{error_message}: {error_detail}") from e
