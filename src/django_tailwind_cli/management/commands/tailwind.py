"""`tailwind` management command."""

# click >= 8.4 made ParamType generic, while typer (capped below 0.26 by
# django-typer) still references it bare, so every typer.Option call below
# reads as partially unknown. reportUnnecessaryTypeIgnoreComment fails the
# lint once that is fixed upstream, which is the signal to delete them.

import importlib.util
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from django_tailwind_cli.utils import http
import typer
from django.conf import settings
from django.core.management.base import CommandError
from django_typer.management import Typer

from django_tailwind_cli.config import detect_binary_version, get_config, maybe_warn_version_mismatch
from django_tailwind_cli.management.commands._errors import handle_command_errors
from django_tailwind_cli.management.commands._process import (
    MultiWatchProcessManager,
    ProcessManager,
)
from django_tailwind_cli.management.commands._guides import (
    print_configuration,
    print_performance_tips,
    print_troubleshooting_guide,
)

app = Typer(  # pyright: ignore[reportUnknownVariableType]
    name="tailwind",
    help="""Tailwind CSS integration for Django projects.

This command provides seamless integration between Django and Tailwind CSS,
allowing you to build, watch, and serve your Tailwind styles without Node.js.

Examples:
  python manage.py tailwind setup          # Guided setup (start here)
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
)

# COMMANDS ---------------------------------------------------------------------


@handle_command_errors
@app.command()
def build(
    *,
    force: bool = typer.Option(  # pyright: ignore[reportUnknownMemberType]
        False,
        "--force",
        help="Force rebuild even if output is up to date.",
    ),
    verbose: bool = typer.Option(  # pyright: ignore[reportUnknownMemberType]
        False,
        "--verbose",
        "-v",
        help="Show detailed build information and diagnostics.",
    ),
    minify: bool | None = typer.Option(  # pyright: ignore[reportUnknownMemberType]
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
    verbose: bool = typer.Option(  # pyright: ignore[reportUnknownMemberType]
        False,
        "--verbose",
        "-v",
        help="Show detailed watch information and diagnostics.",
    ),
    no_reloader: bool = typer.Option(  # pyright: ignore[reportUnknownMemberType]
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

    autoreload.run_with_reloader(_run_watch_loop, verbose=verbose)


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
    print_configuration()


@handle_command_errors
@app.command(name="setup")
def setup_guide():
    """Guided setup for django-tailwind-cli.

    Walks the setup in order and stops at the first blocker with instructions
    for fixing it. Creates the source CSS file, downloads the CLI, and runs a
    first build — each only when it is missing. It prompts for nothing, so it
    is safe to run repeatedly.

    \b
    The steps:
    1. Installation check
    2. Django settings check
    3. Configuration status
    4. Tailwind CLI binary
    5. Source CSS file
    6. First build
    7. Template integration
    8. Development workflow

    \b
    Examples:
        # Run the setup guide
        python manage.py tailwind setup

    \b
    Useful for a first-time setup, for checking a configuration that is not
    behaving, or for seeing which pieces are already in place.
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
            config.src_css.write_text(DAISY_UI_SOURCE_CSS)
            typer.secho("   ✅ DaisyUI source CSS created", fg=typer.colors.GREEN)
        else:
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
    typer.secho("   For production builds, in this order:", fg=typer.colors.CYAN)
    typer.secho("   python manage.py tailwind build", fg=typer.colors.GREEN)
    typer.secho("   python manage.py collectstatic --noinput", fg=typer.colors.GREEN)

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
    - Missing styles after deployment (collectstatic ordering)

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
    print_troubleshooting_guide()


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
    print_performance_tips()


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
    force_default_runserver: bool = typer.Option(  # pyright: ignore[reportUnknownMemberType]
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
    # Both commands below are `python manage.py ...` run from BASE_DIR. Without that file the
    # subprocesses start, fail, and report a returncode — after this command has already claimed
    # to have started them. Say it up front instead.
    manage_py = Path(settings.BASE_DIR) / "manage.py"
    if not manage_py.exists():
        raise CommandError(
            f"No manage.py at '{manage_py}'. `tailwind runserver` runs Django's runserver as a "
            "subprocess from BASE_DIR and needs it there.\n"
            "If your project keeps manage.py elsewhere, run the two halves separately instead:\n"
            "  python manage.py tailwind watch\n"
            "  python manage.py runserver"
        )

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


# DOWNLOAD AND BUILD HELPERS ----------------------------------------------------------------------


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


def _is_cli_usable(cli_path: Path) -> bool:
    """Return True if the CLI binary is present and executable.

    The version is not consulted here. For a managed download it is part of the filename, so a
    version bump lands on a path that does not exist yet; for a binary the user supplied,
    ``_download_cli_with_verbose`` warns about a mismatch before reaching this point.
    """
    return cli_path.exists() and os.access(cli_path, os.X_OK)


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

    # A binary that is not ours — a system binary, or a file placed at TAILWIND_CLI_PATH — carries
    # no version in its name, so the only way to notice a TAILWIND_CLI_VERSION bump is to ask the
    # binary. A managed download does carry it, and asking would mean a subprocess on every build
    # plus a false alarm for forks whose release tags differ from the Tailwind version they bundle.
    if not force_download and not c.manages_cli_binary:
        maybe_warn_version_mismatch(c.cli_path, c.version_str)

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
        if not c.cli_path.exists():
            if verbose:
                typer.secho("❌ CLI not found and automatic download is disabled", fg=typer.colors.RED)
            raise CommandError(
                "Automatic download of Tailwind CSS CLI is deactivated. Please download the Tailwind CSS CLI manually."
            )
        if verbose:
            typer.secho("✅ CLI found, automatic download not needed", fg=typer.colors.GREEN)
        return

    # Use optimized CLI check for existing installations
    if not force_download and _is_cli_usable(c.cli_path):
        if verbose:
            typer.secho("✅ CLI is up-to-date and functional", fg=typer.colors.GREEN)
        typer.secho(
            f"Tailwind CSS CLI already exists at '{c.cli_path}'.",
            fg=typer.colors.GREEN,
        )
        return

    if verbose:
        typer.secho("📥 Starting CLI download...", fg=typer.colors.CYAN)

    if not c.manages_cli_binary and c.cli_path.exists():
        typer.secho(
            f"⚠️  Replacing '{c.cli_path}', which was not downloaded by django-tailwind-cli.",
            fg=typer.colors.YELLOW,
            bold=True,
        )
        typer.secho(
            "   TAILWIND_CLI_PATH points straight at this file, so the download overwrites it.\n"
            "   Point TAILWIND_CLI_PATH at a directory to keep your own build alongside.",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.secho("Tailwind CSS CLI not found.", fg=typer.colors.RED)

    typer.secho(f"Downloading Tailwind CSS CLI from '{c.download_url}'.", fg=typer.colors.YELLOW)

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
        typer.secho(f"📁 File permissions: {stat.filemode(file_stats.st_mode)}", fg=typer.colors.BLUE)
        typer.secho(f"📏 File size: {file_stats.st_size:,} bytes", fg=typer.colors.BLUE)

    typer.secho(f"Downloaded Tailwind CSS CLI to '{c.cli_path}'.", fg=typer.colors.GREEN)


DEFAULT_SOURCE_CSS = '@import "tailwindcss";\n'
DAISY_UI_SOURCE_CSS = '@import "tailwindcss";\n@plugin "daisyui";\n'
AUTO_SOURCE_COMMENT = "/* Auto-generated: installed apps outside BASE_DIR and site-packages. */"


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
        if app_path.is_relative_to(base_dir):
            continue
        if any(app_path.is_relative_to(sp) for sp in site_packages):
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
            lines.append(AUTO_SOURCE_COMMENT)
            for app_path in external:
                lines.append(f'@source "{app_path}";')

    return "\n".join(lines) + "\n"


_GENERATED_LINE_PATTERNS = (
    r"\s*",  # blank lines
    r'@import\s+"tailwindcss";',
    r'@plugin\s+"daisyui";',
    r'@source\s+"[^"]*";',
    re.escape(AUTO_SOURCE_COMMENT),
)
_GENERATED_LINE = re.compile("^(?:" + "|".join(_GENERATED_LINE_PATTERNS) + ")$")


def _looks_auto_generated(content: str) -> bool:
    """Return True if every line of ``content`` is one this library writes itself.

    Comparing against the *currently* generated content would be wrong: it changes when DaisyUI is
    toggled or when the set of external apps changes, and neither means the user edited the file.
    Checking the vocabulary instead only asks "could we have written this?".
    """
    return all(_GENERATED_LINE.match(line) for line in content.splitlines())


def _preserve_hand_edits(src_css: Path) -> None:
    """Copy the hand-edited source CSS aside and say where it went.

    The managed file is regenerated on every build, so the edits are going to be lost either way.
    Keeping a copy makes that recoverable instead of merely announced. The backup lives in the
    managed directory, which carries its own ``.gitignore``.
    """
    backup = src_css.with_suffix(".css.bak")
    backup.write_text(src_css.read_text())

    typer.secho(
        f"⚠️  '{src_css}' has hand edits that are about to be replaced.",
        fg=typer.colors.YELLOW,
        bold=True,
    )
    typer.secho(
        "   This file is managed by django-tailwind-cli and regenerated on every build.",
        fg=typer.colors.YELLOW,
    )
    typer.secho(f"   Your version has been copied to '{backup}'.", fg=typer.colors.YELLOW)
    typer.secho(
        "   To own it yourself, point TAILWIND_CLI_SRC_CSS at a file of your own — the library\n"
        "   never overwrites that one.",
        fg=typer.colors.YELLOW,
    )


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
        if c.overwrite_default_config and c.src_css.exists() and not _looks_auto_generated(c.src_css.read_text()):
            _preserve_hand_edits(c.src_css)

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
