"""`tailwind` management command."""

# click >= 8.4 made ParamType generic, while typer (capped below 0.26 by
# django-typer) still references it bare, so every typer.Option call below
# reads as partially unknown. reportUnnecessaryTypeIgnoreComment fails the
# lint once that is fixed upstream, which is the signal to delete them.

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import typer
from django.conf import settings
from django.core.management.base import CommandError
from django_typer.management import Typer

from django_tailwind_cli.config import get_config
from django_tailwind_cli.management.commands._errors import handle_command_errors
from django_tailwind_cli.management.commands._build import (
    execute_tailwind_command,
    run_watch_loop,
    setup_tailwind_environment,
    should_rebuild_css,
)
from django_tailwind_cli.management.commands._download import ensure_cli_binary
from django_tailwind_cli.management.commands._source_css import (
    DAISY_UI_SOURCE_CSS,
    DEFAULT_SOURCE_CSS,
)
from django_tailwind_cli.management.commands._process import (
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


@app.command()
@handle_command_errors
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

    setup_tailwind_environment(verbose=verbose)

    # Build each CSS entry
    entries_built = 0
    entries_skipped = 0

    for entry in config.css_entries:
        # Check if rebuild is necessary (unless forced)
        if not force and not should_rebuild_css(entry.src_css, entry.dist_css):
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

        execute_tailwind_command(
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


@app.command()
@handle_command_errors
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
        run_watch_loop(verbose=verbose)
        return

    from django.utils import autoreload

    autoreload.run_with_reloader(run_watch_loop, verbose=verbose)


@app.command(name="download_cli")
@handle_command_errors
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
    ensure_cli_binary(force_download=True)


@app.command(name="config")
@handle_command_errors
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


@app.command(name="setup")
@handle_command_errors
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
            ensure_cli_binary(force_download=True)
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


@app.command(name="troubleshoot")
@handle_command_errors
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


@app.command(name="optimize")
@handle_command_errors
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


@app.command(name="remove_cli")
@handle_command_errors
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


# FILE OPERATION OPTIMIZATIONS --------------------------------------------------------------------


# UTILITY FUNCTIONS -------------------------------------------------------------------------------
