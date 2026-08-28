"""What `tailwind troubleshoot`, `optimize` and `config` write to the terminal.

Separated from the commands because these bodies only print: between them they are over 200
`typer.secho` calls with no return value, and keeping them beside the code that builds CSS made
both harder to read. `print_configuration` is the exception that reports rather than advises — it
reads the settings and stats the files it names.

The commands in `tailwind.py` stay the entry points; their docstrings are the `--help` text.
"""

from __future__ import annotations

import typer
from django.conf import settings

from django_tailwind_cli.config import get_config, get_platform_info


def print_troubleshooting_guide() -> None:
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

    # Issue 8: Deployment / collectstatic ordering
    typer.secho("\n❓ Issue 8: Styles missing after deployment", fg=typer.colors.YELLOW, bold=True)
    typer.secho(
        "   Symptoms: ValueError: Missing staticfiles manifest entry for 'css/tailwind.css'",
        fg=typer.colors.BLUE,
    )
    typer.secho("   Cause: collectstatic ran before the stylesheet was built", fg=typer.colors.BLUE)
    typer.secho("   Solutions:", fg=typer.colors.GREEN)
    typer.secho("   1. Build before collecting, in this order:", fg=typer.colors.WHITE)
    typer.secho("      python manage.py tailwind build", fg=typer.colors.GREEN)
    typer.secho("      python manage.py collectstatic --noinput", fg=typer.colors.GREEN)
    typer.secho("   2. Keep the source CSS outside STATICFILES_DIRS", fg=typer.colors.WHITE)
    typer.secho("      Otherwise collectstatic fails with MissingFileError", fg=typer.colors.BLUE)
    typer.secho("   3. See the WhiteNoise notes for a full sample configuration:", fg=typer.colors.WHITE)
    typer.secho("      https://django-tailwind-cli.rtfd.io/latest/whitenoise.html", fg=typer.colors.GREEN)

    # Diagnostic commands
    typer.secho("\n🔧 Diagnostic Commands", fg=typer.colors.CYAN, bold=True)
    typer.secho("   Run these to gather information:", fg=typer.colors.BLUE)
    typer.secho("   python manage.py tailwind config          # Show configuration", fg=typer.colors.GREEN)
    typer.secho("   python manage.py tailwind build --verbose # Detailed build info", fg=typer.colors.GREEN)
    typer.secho("   python manage.py tailwind setup           # Guided setup", fg=typer.colors.GREEN)

    # Getting more help
    typer.secho("\n💬 Need More Help?", fg=typer.colors.CYAN, bold=True)
    typer.secho("   • Documentation: https://django-tailwind-cli.rtfd.io/", fg=typer.colors.BLUE)
    typer.secho(
        "   • GitHub Issues: https://github.com/django-commons/django-tailwind-cli/issues", fg=typer.colors.BLUE
    )
    typer.secho("   • Command help: python manage.py tailwind COMMAND --help", fg=typer.colors.BLUE)

    typer.secho("\n✨ Pro tip: Run 'python manage.py tailwind setup' for guided configuration!", fg=typer.colors.YELLOW)


def print_performance_tips() -> None:
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


def print_configuration() -> None:
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
