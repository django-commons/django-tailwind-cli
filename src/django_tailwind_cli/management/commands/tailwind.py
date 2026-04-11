"""`tailwind` management command."""

import importlib.util
import functools
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import FrameType
from typing import Any
from collections.abc import Callable

from django_tailwind_cli.utils import http
import typer
from django.conf import settings
from django.core.management.base import CommandError
from django_typer.management import Typer

from django_tailwind_cli.config import Config, get_config

app = Typer(  # pyright: ignore[reportUnknownVariableType]
    name="tailwind",
    help="""Tailwind CSS integration for Django projects.

This command provides seamless integration between Django and Tailwind CSS,
allowing you to build, watch, and serve your Tailwind styles without Node.js.

Examples:
  python manage.py tailwind setup          # Interactive setup guide (start here!)
  python manage.py tailwind build          # Build production CSS
  python manage.py tailwind build --force  # Force rebuild ignoring cache
  python manage.py tailwind watch          # Watch for changes during development
  python manage.py tailwind runserver      # Run Django with Tailwind watch mode
  python manage.py tailwind download_cli   # Download Tailwind CLI binary
  python manage.py tailwind config         # Show current configuration
  python manage.py tailwind troubleshoot   # Troubleshooting guide
  python manage.py tailwind optimize       # Performance optimization tips

For more information about a specific command, use:
  python manage.py tailwind COMMAND --help""",
    rich_markup_mode="markdown",
)  # type: ignore


# DECORATORS AND COMMON SETUP ---------------------------------------------------------------------


def handle_command_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to handle common command errors consistently.

    Args:
        func: Function to wrap with error handling.

    Returns:
        Wrapped function with consistent error handling.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except CommandError as e:
            typer.secho(f"❌ Command error: {e}", fg=typer.colors.RED)
            _suggest_command_error_solutions(str(e))
            sys.exit(1)
        except FileNotFoundError as e:
            typer.secho(f"❌ File not found: {e}", fg=typer.colors.RED)
            _suggest_file_error_solutions(str(e))
            sys.exit(1)
        except PermissionError as e:
            typer.secho(f"❌ Permission denied: {e}", fg=typer.colors.RED)
            _suggest_permission_error_solutions(str(e))
            sys.exit(1)
        except Exception as e:
            typer.secho(f"❌ Unexpected error: {e}", fg=typer.colors.RED)
            _suggest_general_error_solutions(str(e))
            sys.exit(1)

    return wrapper


def _suggest_command_error_solutions(error_msg: str) -> None:
    """Provide actionable suggestions for command errors."""
    error_msg_lower = error_msg.lower()

    if "staticfiles_dirs" in error_msg_lower:
        typer.secho("\n💡 Solution:", fg=typer.colors.YELLOW)
        typer.secho("   Add STATICFILES_DIRS to your Django settings.py:", fg=typer.colors.BLUE)
        typer.secho("   STATICFILES_DIRS = [BASE_DIR / 'assets']", fg=typer.colors.GREEN)

    elif "base_dir" in error_msg_lower:
        typer.secho("\n💡 Solution:", fg=typer.colors.YELLOW)
        typer.secho("   Ensure BASE_DIR is properly set in your Django settings.py:", fg=typer.colors.BLUE)
        typer.secho("   BASE_DIR = Path(__file__).resolve().parent.parent", fg=typer.colors.GREEN)

    elif "tailwind css 3.x" in error_msg_lower:
        typer.secho("\n💡 Solution:", fg=typer.colors.YELLOW)
        typer.secho("   Use django-tailwind-cli v2.21.1 for Tailwind CSS 3.x:", fg=typer.colors.BLUE)
        typer.secho("   pip install 'django-tailwind-cli==2.21.1'", fg=typer.colors.GREEN)
        typer.secho("   Or upgrade to Tailwind CSS 4.x (recommended)", fg=typer.colors.GREEN)

    elif "version" in error_msg_lower:
        typer.secho("\n💡 Solution:", fg=typer.colors.YELLOW)
        typer.secho("   Check your TAILWIND_CLI_VERSION setting:", fg=typer.colors.BLUE)
        typer.secho("   TAILWIND_CLI_VERSION = 'latest'  # or specific version like '4.1.3'", fg=typer.colors.GREEN)


def _suggest_file_error_solutions(error_msg: str) -> None:
    """Provide actionable suggestions for file not found errors."""
    typer.secho("\n💡 Suggestions:", fg=typer.colors.YELLOW)

    if "tailwindcss" in error_msg.lower():
        typer.secho("   • Download the Tailwind CLI binary:", fg=typer.colors.BLUE)
        typer.secho("     python manage.py tailwind download_cli", fg=typer.colors.GREEN)
        typer.secho("   • Check your TAILWIND_CLI_PATH setting", fg=typer.colors.BLUE)

    elif ".css" in error_msg.lower():
        typer.secho("   • Ensure your CSS input file exists", fg=typer.colors.BLUE)
        typer.secho("   • Check TAILWIND_CLI_SRC_CSS setting", fg=typer.colors.BLUE)
        typer.secho("   • Run: python manage.py tailwind build", fg=typer.colors.GREEN)

    else:
        typer.secho("   • Check the file path is correct", fg=typer.colors.BLUE)
        typer.secho("   • Ensure the directory exists", fg=typer.colors.BLUE)
        typer.secho("   • Verify file permissions", fg=typer.colors.BLUE)


def _suggest_permission_error_solutions(_error_msg: str) -> None:
    """Provide actionable suggestions for permission errors."""
    typer.secho("\n💡 Solutions:", fg=typer.colors.YELLOW)
    typer.secho("   • Check file/directory permissions:", fg=typer.colors.BLUE)
    typer.secho("     chmod 755 .django_tailwind_cli/", fg=typer.colors.GREEN)
    typer.secho("   • Ensure the parent directory is writable", fg=typer.colors.BLUE)
    typer.secho("   • Try running with appropriate user permissions", fg=typer.colors.BLUE)
    typer.secho("   • On Windows, check if files are locked by another process", fg=typer.colors.BLUE)


def _suggest_general_error_solutions(error_msg: str) -> None:
    """Provide general troubleshooting suggestions."""
    error_msg_lower = error_msg.lower()

    typer.secho("\n💡 Troubleshooting steps:", fg=typer.colors.YELLOW)

    if "network" in error_msg_lower or "connection" in error_msg_lower:
        typer.secho("   • Check your internet connection", fg=typer.colors.BLUE)
        typer.secho("   • Try again (temporary network issues)", fg=typer.colors.BLUE)
        typer.secho("   • Set a specific version instead of 'latest':", fg=typer.colors.BLUE)
        typer.secho("     TAILWIND_CLI_VERSION = '4.1.3'", fg=typer.colors.GREEN)

    elif "import" in error_msg_lower or "module" in error_msg_lower:
        typer.secho("   • Ensure django-tailwind-cli is installed:", fg=typer.colors.BLUE)
        typer.secho("     pip install django-tailwind-cli", fg=typer.colors.GREEN)
        typer.secho("   • Add 'django_tailwind_cli' to INSTALLED_APPS", fg=typer.colors.BLUE)

    else:
        typer.secho("   • Check your Django settings configuration", fg=typer.colors.BLUE)
        typer.secho("   • Verify STATICFILES_DIRS is set correctly", fg=typer.colors.BLUE)
        typer.secho("   • Try: python manage.py tailwind download_cli", fg=typer.colors.GREEN)
        typer.secho("   • For help: python manage.py tailwind --help", fg=typer.colors.GREEN)


# COMMANDS ---------------------------------------------------------------------


@handle_command_errors
@app.command()
def build(
    *,
    force: bool = typer.Option(
        False,
        "--force",
        help="Force rebuild even if output is up to date.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed build information and diagnostics.",
    ),
    minify: bool | None = typer.Option(
        None,
        "--minify/--no-minify",
        help=(
            "Produce a minified stylesheet. Defaults to the value of the "
            "TAILWIND_CLI_AUTOMATIC_MINIFY Django setting (True if unset)."
        ),
    ),
) -> None:
    """Build production-ready CSS file(s).

    This command processes your Tailwind CSS input file(s) and generates optimized
    production CSS file(s) with only the styles actually used in your templates.

    \b
    The build process:
    1. Scans all Django templates for Tailwind class usage
    2. Generates CSS with only the used utility classes
    3. Minifies the output for optimal file size
    4. Saves to your configured output path (STATICFILES_DIRS)

    \b
    Examples:
        # Build production CSS (skips if already up-to-date)
        python manage.py tailwind build

        # Force rebuild even if output seems current
        python manage.py tailwind build --force

        # Show detailed build information
        python manage.py tailwind build --verbose

    \b
    Output location:
        Single-file mode: STATICFILES_DIRS[0]/css/tailwind.css
        (configurable via TAILWIND_CLI_DIST_CSS setting)

        Multi-file mode: Each entry in TAILWIND_CLI_CSS_MAP
    """
    start_time = time.time()
    config = get_config()

    effective_minify: bool = (
        bool(getattr(settings, "TAILWIND_CLI_AUTOMATIC_MINIFY", True)) if minify is None else minify
    )

    if verbose:
        typer.secho("🏗️  Starting Tailwind CSS build process...", fg=typer.colors.CYAN)
        typer.secho(f"   • CSS entries: {len(config.css_entries)}", fg=typer.colors.BLUE)
        for entry in config.css_entries:
            typer.secho(f"   • [{entry.name}] {entry.src_css} -> {entry.dist_css}", fg=typer.colors.BLUE)
        typer.secho(f"   • CLI Path: {config.cli_path}", fg=typer.colors.BLUE)
        typer.secho(f"   • Version: {config.version_str}", fg=typer.colors.BLUE)
        typer.secho(f"   • DaisyUI: {'enabled' if config.use_daisy_ui else 'disabled'}", fg=typer.colors.BLUE)

    _setup_tailwind_environment_with_verbose(verbose=verbose)

    # Build each CSS entry
    entries_built = 0
    entries_skipped = 0

    for entry in config.css_entries:
        # Check if rebuild is necessary (unless forced)
        if not force and not _should_rebuild_css(entry.src_css, entry.dist_css):
            entries_skipped += 1
            if verbose:
                typer.secho(f"⏭️  [{entry.name}] Build skipped: output is up-to-date", fg=typer.colors.YELLOW)
                if entry.src_css.exists() and entry.dist_css.exists():
                    src_mtime = entry.src_css.stat().st_mtime
                    dist_mtime = entry.dist_css.stat().st_mtime
                    typer.secho(f"   • Source modified: {time.ctime(src_mtime)}", fg=typer.colors.BLUE)
                    typer.secho(f"   • Output modified: {time.ctime(dist_mtime)}", fg=typer.colors.BLUE)
            continue

        if verbose:
            build_cmd = config.get_build_cmd(entry, minify=effective_minify)
            typer.secho(f"⚡ [{entry.name}] Executing Tailwind CSS build command...", fg=typer.colors.CYAN)
            typer.secho(f"   • Command: {' '.join(build_cmd)}", fg=typer.colors.BLUE)

        _execute_tailwind_command(
            config.get_build_cmd(entry, minify=effective_minify),
            success_message=f"Built production stylesheet '{entry.dist_css}'.",
            error_message=f"Failed to build production stylesheet '{entry.name}'",
            verbose=verbose,
        )
        entries_built += 1

    # Summary
    if entries_skipped > 0 and entries_built == 0:
        typer.secho(
            f"All {entries_skipped} stylesheet(s) are up to date. Use --force to rebuild.",
            fg=typer.colors.CYAN,
        )
    elif verbose:
        end_time = time.time()
        build_duration = end_time - start_time
        typer.secho(
            f"✅ Build completed in {build_duration:.3f}s ({entries_built} built, {entries_skipped} skipped)",
            fg=typer.colors.GREEN,
        )


@handle_command_errors
@app.command()
def watch(
    *,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed watch information and diagnostics.",
    ),
    no_reloader: bool = typer.Option(
        False,
        "--noreload",
        help="Disable auto-reload on Python file changes.",
    ),
):
    """Start Tailwind CSS in watch mode for development.

    \b
    Watch mode automatically rebuilds your CSS whenever you change:
    - Django template files (*.html)
    - Python files that might contain Tailwind classes
    - Your Tailwind input CSS file
    - JavaScript files (if configured)

    \b
    The watcher provides instant feedback during development, showing:
    - File change detection
    - Build progress and timing
    - Any build errors or warnings

    \b
    By default the Python process that runs the watch mode is itself
    auto-reloaded on any .py file change (using Django's own autoreload
    machinery — the same one runserver uses). This means that installing
    a new Django app or editing settings.py rebuilds the source.css and
    restarts the Tailwind CLI subprocess automatically. Pass --noreload
    to disable this and run the watch loop in a single process.

    \b
    Examples:
        # Start watch mode with auto-reload
        python manage.py tailwind watch

        # Watch with detailed diagnostics
        python manage.py tailwind watch --verbose

        # Single-process watch without auto-reload
        python manage.py tailwind watch --noreload

    \b
    Tips:
        - Keep this running in a separate terminal during development
        - Use alongside 'python manage.py runserver' for full development setup
        - Or use 'python manage.py tailwind runserver' to run both together

    Press Ctrl+C to stop watching.
    """
    if no_reloader:
        _run_watch_loop(verbose=verbose)
        return

    from django.utils import autoreload

    autoreload.run_with_reloader(_run_watch_loop, verbose=verbose)  # pyright: ignore[reportUnknownMemberType]


def _run_watch_loop(*, verbose: bool = False) -> None:
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

    _setup_tailwind_environment_with_verbose(verbose=verbose)

    if verbose:
        typer.secho("🔄 Starting file watcher...", fg=typer.colors.CYAN)

    if len(config.css_entries) == 1:
        # Single entry - use existing simple approach
        _execute_tailwind_command(
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


@handle_command_errors
@app.command(name="download_cli")
def download_cli():
    """Download the Tailwind CSS CLI binary.

    This command downloads the standalone Tailwind CSS CLI binary for your
    platform. The CLI is required to build and watch your CSS files.

    \b
    The download process:
    1. Detects your operating system and architecture
    2. Downloads the appropriate binary from GitHub releases
    3. Saves it to your project directory
    4. Makes it executable (on Unix-like systems)

    \b
    Binary location:
        Default: .django_tailwind_cli/ in your project root
        Custom: Set TAILWIND_CLI_PATH in settings

    \b
    Examples:
        # Download the CLI binary
        python manage.py tailwind download_cli

        # The CLI will be downloaded to:
        # - macOS: .django_tailwind_cli/tailwindcss-macos-[arch]-[version]
        # - Linux: .django_tailwind_cli/tailwindcss-linux-[arch]-[version]
        # - Windows: .django_tailwind_cli/tailwindcss-windows-[arch]-[version].exe

    \b
    Notes:
        - This is usually done automatically on first build/watch
        - Re-run to update to a newer version
        - Internet connection required
        - No Node.js or npm required!
    """
    _download_cli(force_download=True)


@handle_command_errors
@app.command(name="config")
def show_config():
    """Show current Tailwind CSS configuration.

    This command displays the current configuration settings and their values,
    helping you understand how django-tailwind-cli is configured in your project.

    \b
    Information displayed:
    - All configuration paths (CLI, CSS input/output)
    - Version information
    - Django settings values
    - File existence status
    - Platform information

    \b
    Examples:
        # Show current configuration
        python manage.py tailwind config

    \b
    Use this to:
        - Debug configuration issues
        - Verify settings are applied correctly
        - Check file paths and versions
        - Understand your current setup
    """
    from django.core.management.color import color_style

    color_style()  # Initialize color styling
    config = get_config()

    typer.secho("\n🔧 Django Tailwind CLI Configuration", fg=typer.colors.CYAN, bold=True)
    typer.secho("=" * 50, fg=typer.colors.CYAN)

    # Version information
    typer.secho("\n📦 Version Information:", fg=typer.colors.YELLOW, bold=True)
    typer.secho(f"   Tailwind CSS Version: {config.version_str}", fg=typer.colors.GREEN)
    typer.secho(f"   DaisyUI Enabled: {'Yes' if config.use_daisy_ui else 'No'}", fg=typer.colors.GREEN)
    typer.secho(f"   Auto Download: {'Yes' if config.automatic_download else 'No'}", fg=typer.colors.GREEN)

    # Path information
    typer.secho("\n📁 File Paths:", fg=typer.colors.YELLOW, bold=True)
    cli_exists = "✅" if config.cli_path.exists() else "❌"
    origin = "system binary" if config.uses_system_binary else "managed download"
    typer.secho(f"   CLI Binary: {config.cli_path} {cli_exists} ({origin})", fg=typer.colors.GREEN)

    # CSS Entries
    typer.secho(f"\n📄 CSS Entries ({len(config.css_entries)}):", fg=typer.colors.YELLOW, bold=True)
    for entry in config.css_entries:
        src_exists = "✅" if entry.src_css.exists() else "❌"
        dist_exists = "✅" if entry.dist_css.exists() else "❌"
        typer.secho(f"   [{entry.name}]", fg=typer.colors.CYAN)
        typer.secho(f"      Source: {entry.src_css} {src_exists}", fg=typer.colors.GREEN)
        typer.secho(f"      Output: {entry.dist_css} {dist_exists}", fg=typer.colors.GREEN)

    # Django Settings
    typer.secho("\n⚙️ Django Settings:", fg=typer.colors.YELLOW, bold=True)
    staticfiles_dirs = getattr(settings, "STATICFILES_DIRS", None)
    typer.secho(f"   STATICFILES_DIRS: {staticfiles_dirs}", fg=typer.colors.GREEN)

    version_setting = getattr(settings, "TAILWIND_CLI_VERSION", "latest")
    typer.secho(f"   TAILWIND_CLI_VERSION: {version_setting}", fg=typer.colors.GREEN)

    cli_path_setting = getattr(settings, "TAILWIND_CLI_PATH", None)
    if cli_path_setting:
        typer.secho(f"   TAILWIND_CLI_PATH: {cli_path_setting}", fg=typer.colors.GREEN)

    if getattr(settings, "TAILWIND_CLI_USE_SYSTEM_BINARY", False):
        typer.secho("   TAILWIND_CLI_USE_SYSTEM_BINARY: True", fg=typer.colors.GREEN)
        system_binary_name = getattr(settings, "TAILWIND_CLI_SYSTEM_BINARY_NAME", None)
        if system_binary_name:
            typer.secho(f"   TAILWIND_CLI_SYSTEM_BINARY_NAME: {system_binary_name}", fg=typer.colors.GREEN)

    # Show CSS settings based on mode
    css_map_setting = getattr(settings, "TAILWIND_CLI_CSS_MAP", None)
    if css_map_setting:
        typer.secho(f"   TAILWIND_CLI_CSS_MAP: {css_map_setting}", fg=typer.colors.GREEN)
    else:
        src_css_setting = getattr(settings, "TAILWIND_CLI_SRC_CSS", None)
        if src_css_setting:
            typer.secho(f"   TAILWIND_CLI_SRC_CSS: {src_css_setting}", fg=typer.colors.GREEN)

        dist_css_setting = getattr(settings, "TAILWIND_CLI_DIST_CSS", None)
        if dist_css_setting:
            typer.secho(f"   TAILWIND_CLI_DIST_CSS: {dist_css_setting}", fg=typer.colors.GREEN)

    # Platform information
    from django_tailwind_cli.config import get_platform_info

    platform_info = get_platform_info()
    typer.secho("\n💻 Platform Information:", fg=typer.colors.YELLOW, bold=True)
    typer.secho(f"   Operating System: {platform_info.system}", fg=typer.colors.GREEN)
    typer.secho(f"   Architecture: {platform_info.machine}", fg=typer.colors.GREEN)
    typer.secho(f"   Binary Extension: {platform_info.extension or 'none'}", fg=typer.colors.GREEN)

    # Commands
    typer.secho("\n🔗 Command URLs:", fg=typer.colors.YELLOW, bold=True)
    typer.secho(f"   Download URL: {config.download_url}", fg=typer.colors.BLUE)

    # Status summary
    typer.secho("\n📊 Status Summary:", fg=typer.colors.YELLOW, bold=True)
    cli_exists = config.cli_path.exists()
    all_src_exist = all(entry.src_css.exists() for entry in config.css_entries)
    if cli_exists and all_src_exist:
        typer.secho("   ✅ Ready to build CSS", fg=typer.colors.GREEN)
    else:
        typer.secho("   ⚠️  Setup required", fg=typer.colors.YELLOW)
        if not cli_exists:
            typer.secho("      • Run: python manage.py tailwind download_cli", fg=typer.colors.BLUE)
        if not all_src_exist:
            typer.secho("      • Run: python manage.py tailwind build", fg=typer.colors.BLUE)


@handle_command_errors
@app.command(name="setup")
def setup_guide():
    """Interactive setup guide for django-tailwind-cli.

    This command provides step-by-step guidance for setting up Tailwind CSS
    in your Django project, from installation to first build.

    \b
    The guide covers:
    1. Installation verification
    2. Django settings configuration
    3. CLI binary download
    4. First CSS build
    5. Template integration
    6. Development workflow

    \b
    Examples:
        # Run the interactive setup guide
        python manage.py tailwind setup

    \b
    This is perfect for:
        - First-time setup
        - Troubleshooting configuration issues
        - Learning the development workflow
        - Migrating from other Tailwind setups
    """
    typer.secho("\n🚀 Django Tailwind CLI Setup Guide", fg=typer.colors.CYAN, bold=True)
    typer.secho("=" * 50, fg=typer.colors.CYAN)

    # Step 1: Check installation
    typer.secho("\n📦 Step 1: Installation Check", fg=typer.colors.YELLOW, bold=True)
    try:
        from django_tailwind_cli import __version__

        typer.secho(f"   ✅ django-tailwind-cli is installed (version: {__version__})", fg=typer.colors.GREEN)
    except ImportError:
        typer.secho("   ❌ django-tailwind-cli not found", fg=typer.colors.RED)
        typer.secho("   Run: pip install django-tailwind-cli", fg=typer.colors.BLUE)
        return

    # Step 2: Check Django settings
    typer.secho("\n⚙️ Step 2: Django Settings Check", fg=typer.colors.YELLOW, bold=True)

    # Check INSTALLED_APPS
    installed_apps = getattr(settings, "INSTALLED_APPS", [])
    if "django_tailwind_cli" in installed_apps:
        typer.secho("   ✅ 'django_tailwind_cli' in INSTALLED_APPS", fg=typer.colors.GREEN)
    else:
        typer.secho("   ❌ 'django_tailwind_cli' not in INSTALLED_APPS", fg=typer.colors.RED)
        typer.secho("   Add to your settings.py:", fg=typer.colors.BLUE)
        typer.secho("   INSTALLED_APPS = [", fg=typer.colors.GREEN)
        typer.secho("       ...", fg=typer.colors.GREEN)
        typer.secho("       'django_tailwind_cli',", fg=typer.colors.GREEN)
        typer.secho("   ]", fg=typer.colors.GREEN)

    # Check STATICFILES_DIRS
    staticfiles_dirs = getattr(settings, "STATICFILES_DIRS", None)
    if staticfiles_dirs and len(staticfiles_dirs) > 0:
        typer.secho(f"   ✅ STATICFILES_DIRS configured: {staticfiles_dirs[0]}", fg=typer.colors.GREEN)
    else:
        typer.secho("   ❌ STATICFILES_DIRS not configured", fg=typer.colors.RED)
        typer.secho("   Add to your settings.py:", fg=typer.colors.BLUE)
        typer.secho("   STATICFILES_DIRS = [BASE_DIR / 'assets']", fg=typer.colors.GREEN)
        typer.secho("   (or any directory name you prefer)", fg=typer.colors.BLUE)
        return

    # Step 3: Configuration check
    typer.secho("\n🔧 Step 3: Configuration Status", fg=typer.colors.YELLOW, bold=True)
    try:
        config = get_config()
        typer.secho("   ✅ Configuration loaded successfully", fg=typer.colors.GREEN)
        typer.secho(f"   Version: {config.version_str}", fg=typer.colors.BLUE)
        typer.secho(f"   CLI Path: {config.cli_path}", fg=typer.colors.BLUE)
        typer.secho(f"   CSS Output: {config.dist_css}", fg=typer.colors.BLUE)
    except Exception as e:
        typer.secho(f"   ❌ Configuration error: {e}", fg=typer.colors.RED)
        return

    # Step 4: CLI Binary check
    typer.secho("\n💾 Step 4: Tailwind CLI Binary", fg=typer.colors.YELLOW, bold=True)
    if config.cli_path.exists():
        typer.secho("   ✅ Tailwind CLI binary exists", fg=typer.colors.GREEN)
    else:
        typer.secho("   ⬇️  Downloading Tailwind CLI binary...", fg=typer.colors.YELLOW)
        try:
            _download_cli(force_download=True)
            typer.secho("   ✅ Tailwind CLI binary downloaded", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"   ❌ Download failed: {e}", fg=typer.colors.RED)
            return

    # Step 5: CSS files check
    typer.secho("\n🎨 Step 5: CSS Files Setup", fg=typer.colors.YELLOW, bold=True)
    if not config.src_css.exists():
        typer.secho("   📝 Creating source CSS file...", fg=typer.colors.YELLOW)
        config.src_css.parent.mkdir(parents=True, exist_ok=True)
        if config.use_daisy_ui:
            from django_tailwind_cli.management.commands.tailwind import DAISY_UI_SOURCE_CSS

            config.src_css.write_text(DAISY_UI_SOURCE_CSS)
            typer.secho("   ✅ DaisyUI source CSS created", fg=typer.colors.GREEN)
        else:
            from django_tailwind_cli.management.commands.tailwind import DEFAULT_SOURCE_CSS

            config.src_css.write_text(DEFAULT_SOURCE_CSS)
            typer.secho("   ✅ Default source CSS created", fg=typer.colors.GREEN)
    else:
        typer.secho("   ✅ Source CSS file exists", fg=typer.colors.GREEN)

    # Step 6: First build
    typer.secho("\n🏗️ Step 6: First Build", fg=typer.colors.YELLOW, bold=True)
    if not config.dist_css.exists():
        typer.secho("   🔨 Building CSS for the first time...", fg=typer.colors.YELLOW)
        try:
            config.dist_css.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(config.build_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                typer.secho("   ✅ First build completed successfully!", fg=typer.colors.GREEN)
            else:
                typer.secho(f"   ❌ Build failed: {result.stderr}", fg=typer.colors.RED)
                return
        except Exception as e:
            typer.secho(f"   ❌ Build error: {e}", fg=typer.colors.RED)
            return
    else:
        typer.secho("   ✅ CSS output file exists", fg=typer.colors.GREEN)

    # Step 7: Template integration guide
    typer.secho("\n📄 Step 7: Template Integration", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Add this to your base template:", fg=typer.colors.BLUE)
    typer.secho("", fg=typer.colors.BLUE)
    typer.secho("   {% load static tailwind_cli %}", fg=typer.colors.GREEN)
    typer.secho("   <!DOCTYPE html>", fg=typer.colors.GREEN)
    typer.secho("   <html>", fg=typer.colors.GREEN)
    typer.secho("   <head>", fg=typer.colors.GREEN)
    typer.secho("       <title>My Site</title>", fg=typer.colors.GREEN)
    typer.secho("       {% tailwind_css %}", fg=typer.colors.GREEN)
    typer.secho("   </head>", fg=typer.colors.GREEN)
    typer.secho('   <body class="bg-gray-100">', fg=typer.colors.GREEN)
    typer.secho('       <h1 class="text-3xl font-bold text-blue-600">Hello Tailwind!</h1>', fg=typer.colors.GREEN)
    typer.secho("   </body>", fg=typer.colors.GREEN)
    typer.secho("   </html>", fg=typer.colors.GREEN)

    # Step 8: Development workflow
    typer.secho("\n🔄 Step 8: Development Workflow", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   For development, use one of these workflows:", fg=typer.colors.BLUE)
    typer.secho("", fg=typer.colors.BLUE)
    typer.secho("   Option 1 - Single command (recommended):", fg=typer.colors.CYAN)
    typer.secho("   python manage.py tailwind runserver", fg=typer.colors.GREEN)
    typer.secho("", fg=typer.colors.BLUE)
    typer.secho("   Option 2 - Separate terminals:", fg=typer.colors.CYAN)
    typer.secho("   Terminal 1: python manage.py tailwind watch", fg=typer.colors.GREEN)
    typer.secho("   Terminal 2: python manage.py runserver", fg=typer.colors.GREEN)
    typer.secho("", fg=typer.colors.BLUE)
    typer.secho("   For production builds:", fg=typer.colors.CYAN)
    typer.secho("   python manage.py tailwind build", fg=typer.colors.GREEN)

    # Success message
    typer.secho("\n🎉 Setup Complete!", fg=typer.colors.GREEN, bold=True)
    typer.secho("   Your Django project is now ready to use Tailwind CSS!", fg=typer.colors.GREEN)
    typer.secho("   Start development with: python manage.py tailwind runserver", fg=typer.colors.CYAN)
    typer.secho("   For help anytime: python manage.py tailwind --help", fg=typer.colors.BLUE)


@handle_command_errors
@app.command(name="troubleshoot")
def troubleshoot():
    """Troubleshooting guide for common issues.

    This command provides solutions for the most common issues encountered
    when using django-tailwind-cli, with step-by-step debugging guidance.

    \b
    Common issues covered:
    - CSS not updating in browser
    - Build failures and errors
    - Missing or incorrect configuration
    - Permission and download issues
    - Template integration problems

    \b
    Examples:
        # Run the troubleshooting guide
        python manage.py tailwind troubleshoot

    \b
    Use this when:
        - Styles aren't appearing in your browser
        - Build or watch commands fail
        - Getting configuration errors
        - Need to debug your setup
    """
    typer.secho("\n🔍 Django Tailwind CLI Troubleshooting Guide", fg=typer.colors.CYAN, bold=True)
    typer.secho("=" * 55, fg=typer.colors.CYAN)

    # Issue 1: CSS not updating
    typer.secho("\n❓ Issue 1: CSS not updating in browser", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Symptoms: Changes to templates don't reflect in styles", fg=typer.colors.BLUE)
    typer.secho("   Solutions:", fg=typer.colors.GREEN)
    typer.secho("   1. Ensure watch mode is running:", fg=typer.colors.WHITE)
    typer.secho("      python manage.py tailwind watch", fg=typer.colors.GREEN)
    typer.secho("   2. Check browser cache (Ctrl+F5 / Cmd+Shift+R)", fg=typer.colors.WHITE)
    typer.secho("   3. Verify template has {% load tailwind_cli %} and {% tailwind_css %}", fg=typer.colors.WHITE)
    typer.secho("   4. Check if CSS file exists:", fg=typer.colors.WHITE)
    typer.secho("      python manage.py tailwind config", fg=typer.colors.GREEN)

    # Issue 2: Build failures
    typer.secho("\n❓ Issue 2: Build/watch command fails", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Symptoms: Commands exit with errors", fg=typer.colors.BLUE)
    typer.secho("   Solutions:", fg=typer.colors.GREEN)
    typer.secho("   1. Check if CLI binary exists:", fg=typer.colors.WHITE)
    typer.secho("      python manage.py tailwind download_cli", fg=typer.colors.GREEN)
    typer.secho("   2. Verify STATICFILES_DIRS is configured:", fg=typer.colors.WHITE)
    typer.secho("      STATICFILES_DIRS = [BASE_DIR / 'assets']", fg=typer.colors.GREEN)
    typer.secho("   3. Check file permissions:", fg=typer.colors.WHITE)
    typer.secho("      chmod 755 .django_tailwind_cli/", fg=typer.colors.GREEN)
    typer.secho("   4. Try force rebuild:", fg=typer.colors.WHITE)
    typer.secho("      python manage.py tailwind build --force", fg=typer.colors.GREEN)

    # Issue 3: Configuration errors
    typer.secho("\n❓ Issue 3: Configuration errors", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Symptoms: Settings-related error messages", fg=typer.colors.BLUE)
    typer.secho("   Solutions:", fg=typer.colors.GREEN)
    typer.secho("   1. Run the setup guide:", fg=typer.colors.WHITE)
    typer.secho("      python manage.py tailwind setup", fg=typer.colors.GREEN)
    typer.secho("   2. Verify settings.py has:", fg=typer.colors.WHITE)
    typer.secho("      INSTALLED_APPS = [..., 'django_tailwind_cli']", fg=typer.colors.GREEN)
    typer.secho("      STATICFILES_DIRS = [BASE_DIR / 'assets']", fg=typer.colors.GREEN)
    typer.secho("   3. Check current configuration:", fg=typer.colors.WHITE)
    typer.secho("      python manage.py tailwind config", fg=typer.colors.GREEN)

    # Issue 4: Template integration
    typer.secho("\n❓ Issue 4: Template integration problems", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Symptoms: CSS not loading in templates", fg=typer.colors.BLUE)
    typer.secho("   Solutions:", fg=typer.colors.GREEN)
    typer.secho("   1. Ensure template loads the tags:", fg=typer.colors.WHITE)
    typer.secho("      {% load static tailwind_cli %}", fg=typer.colors.GREEN)
    typer.secho("   2. Add CSS tag in <head> section:", fg=typer.colors.WHITE)
    typer.secho("      {% tailwind_css %}", fg=typer.colors.GREEN)
    typer.secho("   3. Check static files are served correctly:", fg=typer.colors.WHITE)
    typer.secho("      python manage.py runserver", fg=typer.colors.GREEN)
    typer.secho("   4. Verify static URL in settings:", fg=typer.colors.WHITE)
    typer.secho("      STATIC_URL = '/static/'", fg=typer.colors.GREEN)

    # Issue 5: Permission issues
    typer.secho("\n❓ Issue 5: Permission denied errors", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Symptoms: Cannot write files or execute CLI", fg=typer.colors.BLUE)
    typer.secho("   Solutions:", fg=typer.colors.GREEN)
    typer.secho("   1. Fix directory permissions:", fg=typer.colors.WHITE)
    typer.secho("      chmod 755 .django_tailwind_cli/", fg=typer.colors.GREEN)
    typer.secho("   2. Ensure CLI is executable:", fg=typer.colors.WHITE)
    typer.secho("      chmod +x .django_tailwind_cli/tailwindcss-*", fg=typer.colors.GREEN)
    typer.secho("   3. Check parent directory is writable", fg=typer.colors.WHITE)
    typer.secho("   4. Re-download CLI binary:", fg=typer.colors.WHITE)
    typer.secho("      python manage.py tailwind download_cli", fg=typer.colors.GREEN)

    # Issue 6: Network/download issues
    typer.secho("\n❓ Issue 6: Download or network failures", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Symptoms: Cannot download CLI binary", fg=typer.colors.BLUE)
    typer.secho("   Solutions:", fg=typer.colors.GREEN)
    typer.secho("   1. Check internet connection", fg=typer.colors.WHITE)
    typer.secho("   2. Set specific version instead of 'latest':", fg=typer.colors.WHITE)
    typer.secho("      TAILWIND_CLI_VERSION = '4.1.3'", fg=typer.colors.GREEN)
    typer.secho("   3. Increase timeout:", fg=typer.colors.WHITE)
    typer.secho("      TAILWIND_CLI_REQUEST_TIMEOUT = 30", fg=typer.colors.GREEN)
    typer.secho("   4. Try manual download from GitHub releases", fg=typer.colors.WHITE)

    # Issue 7: Tailwind classes not working
    typer.secho("\n❓ Issue 7: Tailwind classes not working", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Symptoms: Classes in HTML don't produce styles", fg=typer.colors.BLUE)
    typer.secho("   Solutions:", fg=typer.colors.GREEN)
    typer.secho("   1. Ensure templates are covered by @source directives in your CSS", fg=typer.colors.WHITE)
    typer.secho("   2. Check if using Tailwind CSS 4.x syntax:", fg=typer.colors.WHITE)
    typer.secho("      Some v3 classes may have changed", fg=typer.colors.BLUE)
    typer.secho("   3. Verify class names are correct (no typos)", fg=typer.colors.WHITE)
    typer.secho("   4. Try rebuild with force:", fg=typer.colors.WHITE)
    typer.secho("      python manage.py tailwind build --force", fg=typer.colors.GREEN)

    # Diagnostic commands
    typer.secho("\n🔧 Diagnostic Commands", fg=typer.colors.CYAN, bold=True)
    typer.secho("   Run these to gather information:", fg=typer.colors.BLUE)
    typer.secho("   python manage.py tailwind config          # Show configuration", fg=typer.colors.GREEN)
    typer.secho("   python manage.py tailwind build --verbose # Detailed build info", fg=typer.colors.GREEN)
    typer.secho("   python manage.py tailwind setup           # Interactive setup", fg=typer.colors.GREEN)

    # Getting more help
    typer.secho("\n💬 Need More Help?", fg=typer.colors.CYAN, bold=True)
    typer.secho("   • Documentation: https://django-tailwind-cli.rtfd.io/", fg=typer.colors.BLUE)
    typer.secho(
        "   • GitHub Issues: https://github.com/django-commons/django-tailwind-cli/issues", fg=typer.colors.BLUE
    )
    typer.secho("   • Command help: python manage.py tailwind COMMAND --help", fg=typer.colors.BLUE)

    typer.secho("\n✨ Pro tip: Run 'python manage.py tailwind setup' for guided configuration!", fg=typer.colors.YELLOW)


@handle_command_errors
@app.command(name="optimize")
def show_performance_tips():
    """Performance optimization tips and best practices.

    This command provides detailed guidance on optimizing your Tailwind CSS
    build performance and development workflow for the best possible experience.

    \b
    Areas covered:
    - Build performance optimization
    - File watching efficiency
    - Template scanning optimization
    - Production deployment best practices
    - Development workflow improvements
    - Common performance pitfalls

    \b
    Examples:
        # Show performance optimization tips
        python manage.py tailwind optimize

    \b
    Use this to:
        - Speed up development builds
        - Optimize production deployments
        - Reduce file watching overhead
        - Improve overall workflow efficiency
    """
    typer.secho("\n⚡ Django Tailwind CLI Performance Optimization", fg=typer.colors.CYAN, bold=True)
    typer.secho("=" * 55, fg=typer.colors.CYAN)

    # Build Performance
    typer.secho("\n🏗️ Build Performance", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Optimize your CSS build times:", fg=typer.colors.BLUE)
    typer.secho("   • Use file modification checks (automatic)", fg=typer.colors.GREEN)
    typer.secho("   • Only force rebuild when necessary: --force", fg=typer.colors.GREEN)
    typer.secho("   • Pin Tailwind version in production: TAILWIND_CLI_VERSION", fg=typer.colors.GREEN)
    typer.secho("   • Disable automatic downloads in CI: TAILWIND_CLI_AUTOMATIC_DOWNLOAD=False", fg=typer.colors.GREEN)

    # File Watching
    typer.secho("\n👀 File Watching Efficiency", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Optimize development file watching:", fg=typer.colors.BLUE)
    typer.secho("   • Use 'tailwind runserver' for integrated development", fg=typer.colors.GREEN)
    typer.secho("   • Exclude unnecessary directories from template scanning", fg=typer.colors.GREEN)
    typer.secho("   • Keep templates organized in standard Django locations", fg=typer.colors.GREEN)
    typer.secho("   • Use .gitignore patterns for large file trees", fg=typer.colors.GREEN)

    # Template Optimization
    typer.secho("\n📄 Template Scanning", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Optimize template discovery:", fg=typer.colors.BLUE)
    typer.secho("   • Declare template sources with @source directives in your CSS", fg=typer.colors.GREEN)
    typer.secho("   • Organize templates in app-specific directories", fg=typer.colors.GREEN)
    typer.secho("   • Avoid deeply nested template hierarchies", fg=typer.colors.GREEN)
    typer.secho("   • Use standard Django template patterns", fg=typer.colors.GREEN)

    # Production Optimization
    typer.secho("\n🚀 Production Deployment", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Best practices for production:", fg=typer.colors.BLUE)
    typer.secho("   • Pre-install CLI binary in Docker images", fg=typer.colors.GREEN)
    typer.secho("   • Use specific version: TAILWIND_CLI_VERSION='4.1.3'", fg=typer.colors.GREEN)
    typer.secho("   • Build CSS during container build, not runtime", fg=typer.colors.GREEN)
    typer.secho("   • Serve CSS with proper cache headers", fg=typer.colors.GREEN)

    # Development Workflow
    typer.secho("\n🛠️ Development Workflow", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Streamline your development process:", fg=typer.colors.BLUE)
    typer.secho("   • Use verbose mode for troubleshooting: --verbose", fg=typer.colors.GREEN)
    typer.secho("   • Monitor build times with verbose output", fg=typer.colors.GREEN)
    typer.secho("   • Configure IDE for Tailwind CSS IntelliSense", fg=typer.colors.GREEN)
    typer.secho("   • Set up proper static file serving", fg=typer.colors.GREEN)

    # Common Pitfalls
    typer.secho("\n⚠️ Common Performance Pitfalls", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Avoid these common issues:", fg=typer.colors.BLUE)
    typer.secho("   ❌ Running builds on every request", fg=typer.colors.RED)
    typer.secho("   ❌ Not using file watching in development", fg=typer.colors.RED)
    typer.secho("   ❌ Scanning unnecessary file types", fg=typer.colors.RED)
    typer.secho("   ❌ Using --force without need", fg=typer.colors.RED)
    typer.secho("   ❌ Not pinning versions in production", fg=typer.colors.RED)

    # Configuration Examples
    typer.secho("\n⚙️ Performance Configuration Examples", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Development settings:", fg=typer.colors.BLUE)
    typer.secho("   TAILWIND_CLI_VERSION = 'latest'  # Auto-update", fg=typer.colors.GREEN)
    typer.secho("   TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True", fg=typer.colors.GREEN)
    typer.secho("\n   Production settings:", fg=typer.colors.BLUE)
    typer.secho("   TAILWIND_CLI_VERSION = '4.1.3'  # Pin version", fg=typer.colors.GREEN)
    typer.secho("   TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False", fg=typer.colors.GREEN)
    typer.secho("   TAILWIND_CLI_PATH = '/usr/local/bin/tailwindcss'", fg=typer.colors.GREEN)

    # Monitoring
    typer.secho("\n📊 Performance Monitoring", fg=typer.colors.YELLOW, bold=True)
    typer.secho("   Monitor and measure performance:", fg=typer.colors.BLUE)
    typer.secho("   • Build times: python manage.py tailwind build --verbose", fg=typer.colors.GREEN)
    typer.secho("   • Configuration check: python manage.py tailwind config", fg=typer.colors.GREEN)
    typer.secho("   • File watching logs: python manage.py tailwind watch --verbose", fg=typer.colors.GREEN)

    typer.secho(
        "\n✨ Pro tip: Start with 'python manage.py tailwind runserver' for the best development experience!",
        fg=typer.colors.CYAN,
    )


@handle_command_errors
@app.command(name="remove_cli")
def remove_cli():
    """Remove the Tailwind CSS CLI."""
    c = get_config()

    if c.uses_system_binary:
        typer.secho(
            f"Refusing to remove system Tailwind CSS CLI at '{c.cli_path}'. "
            "It was installed outside of django-tailwind-cli (e.g. via Homebrew) and must be "
            "uninstalled the same way.",
            fg=typer.colors.YELLOW,
        )
        return

    if c.cli_path.exists():
        c.cli_path.unlink()
        typer.secho(f"Removed Tailwind CSS CLI at '{c.cli_path}'.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Tailwind CSS CLI not found at '{c.cli_path}'.", fg=typer.colors.RED)


@app.command(
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
)
def runserver(
    ctx: typer.Context,
    *,
    force_default_runserver: bool = typer.Option(
        False,
        help="Force vanilla runserver even if django-extensions is installed.",
    ),
):
    """Run Django development server with Tailwind CSS watch mode.

    Combines `tailwind watch` and Django's runserver in one terminal, with
    signal-clean shutdown of both processes on Ctrl+C. If `django-extensions`
    plus `werkzeug` are installed, `runserver_plus` is used by default — pass
    `--force-default-runserver` to opt out.

    \b
    All positional arguments and options other than `--force-default-runserver`
    are forwarded verbatim to the underlying server command. That means every
    runserver / runserver_plus flag is supported, including ones this wrapper
    does not know about:

    \b
        python manage.py tailwind runserver
        python manage.py tailwind runserver 8080
        python manage.py tailwind runserver 0.0.0.0:8000 --noreload
        python manage.py tailwind runserver --print-sql --ipdb
        python manage.py tailwind runserver --extra-file .env --reloader-interval 5

    \b
    For the full list of forwarded flags, see:
        python manage.py runserver --help
        python manage.py runserver_plus --help   (with django-extensions)
    """
    use_plus = (
        importlib.util.find_spec("django_extensions")
        and importlib.util.find_spec("werkzeug")
        and not force_default_runserver
    )
    server_command = "runserver_plus" if use_plus else "runserver"

    watch_cmd = [sys.executable, "manage.py", "tailwind", "watch"]
    server_cmd = [sys.executable, "manage.py", server_command, *ctx.args]

    process_manager = ProcessManager()
    process_manager.start_concurrent_processes(watch_cmd, server_cmd)


# PROCESS MANAGEMENT FUNCTIONS -------------------------------------------------------------------


class ProcessManager:
    """Manages concurrent processes for Tailwind watch and Django runserver."""

    def __init__(self) -> None:
        self.processes: list[subprocess.Popen[str]] = []
        self.shutdown_requested = False

    def start_concurrent_processes(self, watch_cmd: list[str], server_cmd: list[str]) -> None:
        """Start watch and server processes concurrently with proper cleanup.

        Args:
            watch_cmd: Command to start Tailwind watch process.
            server_cmd: Command to start Django development server.
        """
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            # Start Tailwind watch process
            watch_process = subprocess.Popen(
                watch_cmd,
                cwd=settings.BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
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

            # Monitor processes
            self._monitor_processes()

        except Exception as e:
            typer.secho(f"Error starting processes: {e}", fg=typer.colors.RED)
            self._cleanup_processes()
            raise

    def _signal_handler(self, _signum: int, _frame: FrameType | None) -> None:
        """Handle shutdown signals gracefully."""
        typer.secho("\\nShutdown signal received, stopping processes...", fg=typer.colors.YELLOW)
        self.shutdown_requested = True
        self._cleanup_processes()

    def _monitor_processes(self) -> None:
        """Monitor running processes and handle their lifecycle."""
        while not self.shutdown_requested and any(p.poll() is None for p in self.processes):
            time.sleep(0.5)

            # Check if any process has exited unexpectedly
            for process in self.processes:
                if process.poll() is not None and process.returncode != 0:
                    typer.secho(f"Process exited with code {process.returncode}", fg=typer.colors.RED)
                    self.shutdown_requested = True
                    break

        # Clean up any remaining processes
        self._cleanup_processes()

    def _cleanup_processes(self) -> None:
        """Clean up all managed processes."""
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


class MultiWatchProcessManager:
    """Manages multiple Tailwind watch processes for multi-file mode."""

    def __init__(self) -> None:
        self.processes: list[subprocess.Popen[str]] = []
        self.shutdown_requested = False

    def start_watch_processes(self, config: Config, *, verbose: bool = False) -> None:
        """Start watch processes for all CSS entries.

        Args:
            config: Configuration object with css_entries.
            verbose: Whether to show detailed information.
        """
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            for entry in config.css_entries:
                watch_cmd = config.get_watch_cmd(entry)
                if verbose:
                    typer.secho(f"🚀 Starting watch for '{entry.name}'...", fg=typer.colors.CYAN)
                    typer.secho(f"   • Command: {' '.join(watch_cmd)}", fg=typer.colors.BLUE)

                process = subprocess.Popen(
                    watch_cmd,
                    cwd=settings.BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self.processes.append(process)
                typer.secho(f"Watching '{entry.name}': {entry.src_css}", fg=typer.colors.GREEN)

            self._monitor_processes()
        except Exception as e:
            typer.secho(f"Error starting watch processes: {e}", fg=typer.colors.RED)
            self._cleanup_processes()
            raise

    def _signal_handler(self, _signum: int, _frame: FrameType | None) -> None:
        """Handle shutdown signals gracefully."""
        typer.secho("\nShutdown signal received, stopping watch processes...", fg=typer.colors.YELLOW)
        self.shutdown_requested = True
        self._cleanup_processes()

    def _monitor_processes(self) -> None:
        """Monitor all watch processes."""
        while not self.shutdown_requested and any(p.poll() is None for p in self.processes):
            time.sleep(0.5)

            for i, process in enumerate(self.processes):
                if process.poll() is not None and process.returncode != 0:
                    typer.secho(f"Watch process {i} exited with code {process.returncode}", fg=typer.colors.RED)
                    self.shutdown_requested = True
                    break

        self._cleanup_processes()

    def _cleanup_processes(self) -> None:
        """Clean up all watch processes."""
        for process in self.processes:
            if process.poll() is None:
                try:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                except (OSError, subprocess.SubprocessError):
                    pass
        self.processes.clear()
        typer.secho("Stopped watching for changes.", fg=typer.colors.GREEN)


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
            typer.secho(f"Progress: {progress:.1f}% ({downloaded}/{total_size} bytes)", fg=typer.colors.CYAN)
            last_progress = progress

    try:
        typer.secho("Downloading Tailwind CSS CLI...", fg=typer.colors.YELLOW)
        http.download_with_progress(url, filepath, timeout=30, progress_callback=progress_callback)
        typer.secho("Download completed!", fg=typer.colors.GREEN)

    except http.RequestError as e:
        raise CommandError(f"Failed to download Tailwind CSS CLI: {e}") from e


def _setup_tailwind_environment_with_verbose(*, verbose: bool = False) -> None:
    """Common setup for all Tailwind commands with verbose logging."""
    if verbose:
        typer.secho("⚙️  Setting up Tailwind environment...", fg=typer.colors.CYAN)
    _download_cli_with_verbose(verbose=verbose)
    _create_standard_config_with_verbose(verbose=verbose)
    _ensure_default_gitignore()


def _ensure_default_gitignore() -> None:
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


def _should_rebuild_css(src_css: Path, dist_css: Path) -> bool:
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


def _execute_tailwind_command(
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
        typer.secho(f"{error_message}: {error_detail}", fg=typer.colors.RED)
        sys.exit(1)


# FILE OPERATION OPTIMIZATIONS --------------------------------------------------------------------


def _should_recreate_file(file_path: Path, content: str) -> bool:
    """Check if a file needs to be recreated based on content and modification time.

    Args:
        file_path: Path to the file to check.
        content: New content that would be written.

    Returns:
        True if file should be recreated, False if it's up to date.
    """
    if not file_path.exists():
        return True

    try:
        current_content = file_path.read_text()
        if current_content != content:
            return True
    except (OSError, UnicodeDecodeError):
        # If we can't read the file, recreate it
        return True

    return False


def _is_cli_up_to_date(cli_path: Path, _expected_version: str) -> bool:
    """Check if CLI binary is up to date and functional.

    Args:
        cli_path: Path to the CLI binary.
        _expected_version: Expected version string (currently unused but kept for future enhancement).

    Returns:
        True if CLI is up to date and functional.
    """
    if not cli_path.exists():
        return False

    # Check if CLI is executable
    if not os.access(cli_path, os.X_OK):
        return False

    # For now, we assume existing CLI is functional
    # Could be enhanced to check version via subprocess call using _expected_version
    return True


# Global cache for file existence checks
_FILE_CACHE: dict[str, tuple[float, bool]] = {}


def _check_file_exists_cached(file_path: Path, cache_duration: float = 5.0) -> bool:
    """Check file existence with caching to avoid repeated filesystem calls.

    Args:
        file_path: Path to check.
        cache_duration: Cache duration in seconds.

    Returns:
        True if file exists (from cache or filesystem).
    """
    global _FILE_CACHE
    cache_key = str(file_path)
    current_time = time.time()

    # Check cache
    if cache_key in _FILE_CACHE:
        last_check, existed = _FILE_CACHE[cache_key]
        if current_time - last_check < cache_duration:
            return existed

    # Check filesystem and update cache
    exists = file_path.exists()
    _FILE_CACHE[cache_key] = (current_time, exists)
    return exists


# UTILITY FUNCTIONS -------------------------------------------------------------------------------


def _download_cli(*, force_download: bool = False) -> None:
    """Assure that the CLI is loaded if automatic downloads are activated."""
    _download_cli_with_verbose(verbose=False, force_download=force_download)


def _download_cli_with_verbose(*, verbose: bool = False, force_download: bool = False) -> None:
    """Assure that the CLI is loaded with optional verbose logging."""
    c = get_config()

    if verbose:
        typer.secho("🔍 Checking Tailwind CSS CLI availability...", fg=typer.colors.CYAN)
        typer.secho(f"   • CLI Path: {c.cli_path}", fg=typer.colors.BLUE)
        typer.secho(f"   • Version: {c.version_str}", fg=typer.colors.BLUE)
        typer.secho(f"   • Download URL: {c.download_url}", fg=typer.colors.BLUE)
        typer.secho(f"   • Automatic download: {c.automatic_download}", fg=typer.colors.BLUE)

    # System-binary mode: the CLI lives on PATH, never download it.
    if c.uses_system_binary:
        if verbose:
            typer.secho("✅ Using system Tailwind CSS CLI — download skipped", fg=typer.colors.GREEN)
        typer.secho(
            f"Using system Tailwind CSS CLI at '{c.cli_path}'.",
            fg=typer.colors.GREEN,
        )
        return

    if not force_download and not c.automatic_download:
        if not _check_file_exists_cached(c.cli_path):
            if verbose:
                typer.secho("❌ CLI not found and automatic download is disabled", fg=typer.colors.RED)
            raise CommandError(
                "Automatic download of Tailwind CSS CLI is deactivated. Please download the Tailwind CSS CLI manually."
            )
        if verbose:
            typer.secho("✅ CLI found, automatic download not needed", fg=typer.colors.GREEN)
        return

    # Use optimized CLI check for existing installations
    if not force_download and _is_cli_up_to_date(c.cli_path, c.version_str):
        if verbose:
            typer.secho("✅ CLI is up-to-date and functional", fg=typer.colors.GREEN)
        typer.secho(
            f"Tailwind CSS CLI already exists at '{c.cli_path}'.",
            fg=typer.colors.GREEN,
        )
        return

    if verbose:
        typer.secho("📥 Starting CLI download...", fg=typer.colors.CYAN)

    typer.secho("Tailwind CSS CLI not found.", fg=typer.colors.RED)
    typer.secho(f"Downloading Tailwind CSS CLI from '{c.download_url}'.", fg=typer.colors.YELLOW)

    # Download with progress indication
    _download_cli_with_progress(c.download_url, c.cli_path)

    # Make CLI executable
    c.cli_path.chmod(0o755)

    if verbose:
        import stat

        file_stats = c.cli_path.stat()
        typer.secho(f"📁 File permissions: {stat.filemode(file_stats.st_mode)}", fg=typer.colors.BLUE)
        typer.secho(f"📏 File size: {file_stats.st_size:,} bytes", fg=typer.colors.BLUE)

    typer.secho(f"Downloaded Tailwind CSS CLI to '{c.cli_path}'.", fg=typer.colors.GREEN)


DEFAULT_SOURCE_CSS = '@import "tailwindcss";\n'
DAISY_UI_SOURCE_CSS = '@import "tailwindcss";\n@plugin "daisyui";\n'


def _get_site_packages_paths() -> list[Path]:
    """Return all known site-packages paths used to filter out regular installs.

    We combine ``site.getsitepackages()``, ``site.getusersitepackages()`` and
    ``sysconfig.get_paths()`` to catch every standard location — editable
    installs of the user's own source packages live outside all of these.
    """
    import site
    import sysconfig

    paths: set[Path] = set()
    for p in site.getsitepackages():
        paths.add(Path(p).resolve())
    try:
        user_site = site.getusersitepackages()
        if user_site:
            paths.add(Path(user_site).resolve())
    except AttributeError:  # pragma: no cover - defensive
        pass
    for key in ("purelib", "platlib"):
        p = sysconfig.get_paths().get(key)
        if p:
            paths.add(Path(p).resolve())
    return sorted(paths)


def _is_under(child: Path, parent: Path) -> bool:
    """Return True if ``child`` lies under ``parent`` in the filesystem tree."""
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _discover_external_app_base_dirs() -> list[Path]:
    """Return base dirs of installed Django apps that need explicit @source.

    An app is considered "external" if its path is NOT under ``BASE_DIR``
    (Tailwind's CWD walk would not reach it) AND NOT under any known
    site-packages directory (regular pip installs are not user-editable
    source). This targets the editable-install case from issue #187.
    """
    from django.apps import apps

    base_dir = Path(settings.BASE_DIR).resolve()
    site_packages = _get_site_packages_paths()
    external: list[Path] = []

    for app_config in apps.get_app_configs():
        app_path = Path(app_config.path).resolve()
        if _is_under(app_path, base_dir):
            continue
        if any(_is_under(app_path, sp) for sp in site_packages):
            continue
        external.append(app_path)

    return sorted(external)


def _build_source_css_content(*, use_daisy_ui: bool, inject_external_apps: bool) -> str:
    """Build the auto-generated source.css content.

    Starts from the minimal ``@import "tailwindcss";`` (+ ``@plugin "daisyui";``
    when DaisyUI is enabled) and appends one ``@source`` directive per
    discovered external Django app base dir.
    """
    lines = ['@import "tailwindcss";']
    if use_daisy_ui:
        lines.append('@plugin "daisyui";')

    if inject_external_apps:
        external = _discover_external_app_base_dirs()
        if external:
            lines.append("")
            lines.append("/* Auto-generated: installed apps outside BASE_DIR and site-packages. */")
            for app_path in external:
                lines.append(f'@source "{app_path}";')

    return "\n".join(lines) + "\n"


def _create_standard_config_with_verbose(*, verbose: bool = False) -> None:
    """Create a standard Tailwind CSS config file with optional verbose logging."""
    c = get_config()

    if verbose:
        typer.secho("📄 Checking Tailwind CSS source configuration...", fg=typer.colors.CYAN)
        typer.secho(f"   • Source CSS path: {c.src_css}", fg=typer.colors.BLUE)
        typer.secho(f"   • Overwrite default: {c.overwrite_default_config}", fg=typer.colors.BLUE)
        typer.secho(f"   • DaisyUI enabled: {c.use_daisy_ui}", fg=typer.colors.BLUE)

    if not c.src_css:
        if verbose:
            typer.secho("⏭️  No source CSS path configured, skipping creation", fg=typer.colors.YELLOW)
        return

    # Build content dynamically — includes auto @source directives for
    # external apps when TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS is enabled.
    content = _build_source_css_content(
        use_daisy_ui=c.use_daisy_ui,
        inject_external_apps=c.auto_source_external_apps,
    )

    if verbose:
        typer.secho(f"📝 Content template: {'DaisyUI' if c.use_daisy_ui else 'Default'}", fg=typer.colors.BLUE)

    # Only create/update if:
    # 1. overwrite_default_config is True (meaning we're using default path) AND file doesn't exist
    # 2. OR overwrite_default_config is True AND the content should be recreated
    should_create = False
    if c.overwrite_default_config:
        # For default config, only create if file doesn't exist or content differs
        should_create = _should_recreate_file(c.src_css, content)
        if verbose:
            existing_msg = "exists with different content" if c.src_css.exists() else "does not exist"
            typer.secho(f"🔍 File check (default config): {existing_msg}", fg=typer.colors.BLUE)
    else:
        # For custom config path, only create if file doesn't exist
        should_create = not c.src_css.exists()
        if verbose:
            existing_msg = "exists (preserving)" if c.src_css.exists() else "does not exist"
            typer.secho(f"🔍 File check (custom config): {existing_msg}", fg=typer.colors.BLUE)

    if should_create:
        if verbose:
            typer.secho("📝 Creating/updating source CSS file...", fg=typer.colors.CYAN)

        c.src_css.parent.mkdir(parents=True, exist_ok=True)
        c.src_css.write_text(content)

        if verbose:
            typer.secho(f"✅ Created directory: {c.src_css.parent}", fg=typer.colors.GREEN)
            typer.secho(f"📄 Content length: {len(content)} characters", fg=typer.colors.BLUE)

        typer.secho(
            f"Created Tailwind Source CSS at '{c.src_css}'",
            fg=typer.colors.GREEN,
        )
    elif verbose:
        typer.secho("⏭️  Source CSS file is up-to-date, no changes needed", fg=typer.colors.GREEN)
