"""What `tailwind troubleshoot`, `optimize` and `config` write to the terminal.

Separated from the commands because these bodies only print: between them they are over 200
`click.secho` calls with no return value, and keeping them beside the code that builds CSS made
both harder to read. `print_configuration` is the exception that reports rather than advises — it
reads the settings and stats the files it names.

The commands in `tailwind.py` stay the entry points; their docstrings are the `--help` text.
"""

from __future__ import annotations

import click
from django.conf import settings

from django_tailwind_cli.config import get_config, get_platform_info


def print_troubleshooting_guide() -> None:
    click.secho("\n🔍 Django Tailwind CLI Troubleshooting Guide", fg="cyan", bold=True)
    click.secho("=" * 55, fg="cyan")

    # Issue 1: CSS not updating
    click.secho("\n❓ Issue 1: CSS not updating in browser", fg="yellow", bold=True)
    click.secho("   Symptoms: Changes to templates don't reflect in styles", fg="blue")
    click.secho("   Solutions:", fg="green")
    click.secho("   1. Ensure watch mode is running:", fg="white")
    click.secho("      python manage.py tailwind watch", fg="green")
    click.secho("   2. Check browser cache (Ctrl+F5 / Cmd+Shift+R)", fg="white")
    click.secho("   3. Verify template has {% load tailwind_cli %} and {% tailwind_css %}", fg="white")
    click.secho("   4. Check if CSS file exists:", fg="white")
    click.secho("      python manage.py tailwind config", fg="green")

    # Issue 2: Build failures
    click.secho("\n❓ Issue 2: Build/watch command fails", fg="yellow", bold=True)
    click.secho("   Symptoms: Commands exit with errors", fg="blue")
    click.secho("   Solutions:", fg="green")
    click.secho("   1. Check if CLI binary exists:", fg="white")
    click.secho("      python manage.py tailwind download_cli", fg="green")
    click.secho("   2. Verify STATICFILES_DIRS is configured:", fg="white")
    click.secho("      STATICFILES_DIRS = [BASE_DIR / 'assets']", fg="green")
    click.secho("   3. Check file permissions:", fg="white")
    click.secho("      chmod 755 .django_tailwind_cli/", fg="green")
    click.secho("   4. Try force rebuild:", fg="white")
    click.secho("      python manage.py tailwind build --force", fg="green")

    # Issue 3: Configuration errors
    click.secho("\n❓ Issue 3: Configuration errors", fg="yellow", bold=True)
    click.secho("   Symptoms: Settings-related error messages", fg="blue")
    click.secho("   Solutions:", fg="green")
    click.secho("   1. Run the setup guide:", fg="white")
    click.secho("      python manage.py tailwind setup", fg="green")
    click.secho("   2. Verify settings.py has:", fg="white")
    click.secho("      INSTALLED_APPS = [..., 'django_tailwind_cli']", fg="green")
    click.secho("      STATICFILES_DIRS = [BASE_DIR / 'assets']", fg="green")
    click.secho("   3. Check current configuration:", fg="white")
    click.secho("      python manage.py tailwind config", fg="green")

    # Issue 4: Template integration
    click.secho("\n❓ Issue 4: Template integration problems", fg="yellow", bold=True)
    click.secho("   Symptoms: CSS not loading in templates", fg="blue")
    click.secho("   Solutions:", fg="green")
    click.secho("   1. Ensure template loads the tags:", fg="white")
    click.secho("      {% load static tailwind_cli %}", fg="green")
    click.secho("   2. Add CSS tag in <head> section:", fg="white")
    click.secho("      {% tailwind_css %}", fg="green")
    click.secho("   3. Check static files are served correctly:", fg="white")
    click.secho("      python manage.py runserver", fg="green")
    click.secho("   4. Verify static URL in settings:", fg="white")
    click.secho("      STATIC_URL = '/static/'", fg="green")

    # Issue 5: Permission issues
    click.secho("\n❓ Issue 5: Permission denied errors", fg="yellow", bold=True)
    click.secho("   Symptoms: Cannot write files or execute CLI", fg="blue")
    click.secho("   Solutions:", fg="green")
    click.secho("   1. Fix directory permissions:", fg="white")
    click.secho("      chmod 755 .django_tailwind_cli/", fg="green")
    click.secho("   2. Ensure CLI is executable:", fg="white")
    click.secho("      chmod +x .django_tailwind_cli/tailwindcss-*", fg="green")
    click.secho("   3. Check parent directory is writable", fg="white")
    click.secho("   4. Re-download CLI binary:", fg="white")
    click.secho("      python manage.py tailwind download_cli", fg="green")

    # Issue 6: Network/download issues
    click.secho("\n❓ Issue 6: Download or network failures", fg="yellow", bold=True)
    click.secho("   Symptoms: Cannot download CLI binary", fg="blue")
    click.secho("   Solutions:", fg="green")
    click.secho("   1. Check internet connection", fg="white")
    click.secho("   2. Set specific version instead of 'latest':", fg="white")
    click.secho("      TAILWIND_CLI_VERSION = '4.1.3'", fg="green")
    click.secho("   3. Increase timeout:", fg="white")
    click.secho("      TAILWIND_CLI_REQUEST_TIMEOUT = 30", fg="green")
    click.secho("   4. Try manual download from GitHub releases", fg="white")

    # Issue 7: Tailwind classes not working
    click.secho("\n❓ Issue 7: Tailwind classes not working", fg="yellow", bold=True)
    click.secho("   Symptoms: Classes in HTML don't produce styles", fg="blue")
    click.secho("   Solutions:", fg="green")
    click.secho("   1. Ensure templates are covered by @source directives in your CSS", fg="white")
    click.secho("   2. Check if using Tailwind CSS 4.x syntax:", fg="white")
    click.secho("      Some v3 classes may have changed", fg="blue")
    click.secho("   3. Verify class names are correct (no typos)", fg="white")
    click.secho("   4. Try rebuild with force:", fg="white")
    click.secho("      python manage.py tailwind build --force", fg="green")

    # Issue 8: Deployment / collectstatic ordering
    click.secho("\n❓ Issue 8: Styles missing after deployment", fg="yellow", bold=True)
    click.secho(
        "   Symptoms: ValueError: Missing staticfiles manifest entry for 'css/tailwind.css'",
        fg="blue",
    )
    click.secho("   Cause: collectstatic ran before the stylesheet was built", fg="blue")
    click.secho("   Solutions:", fg="green")
    click.secho("   1. Build before collecting, in this order:", fg="white")
    click.secho("      python manage.py tailwind build", fg="green")
    click.secho("      python manage.py collectstatic --noinput", fg="green")
    click.secho("   2. Keep the source CSS outside STATICFILES_DIRS", fg="white")
    click.secho("      Otherwise collectstatic fails with MissingFileError", fg="blue")
    click.secho("   3. See the WhiteNoise notes for a full sample configuration:", fg="white")
    click.secho("      https://django-tailwind-cli.rtfd.io/latest/whitenoise.html", fg="green")

    # Diagnostic commands
    click.secho("\n🔧 Diagnostic Commands", fg="cyan", bold=True)
    click.secho("   Run these to gather information:", fg="blue")
    click.secho("   python manage.py tailwind config          # Show configuration", fg="green")
    click.secho("   python manage.py tailwind build --verbose # Detailed build info", fg="green")
    click.secho("   python manage.py tailwind setup           # Guided setup", fg="green")

    # Getting more help
    click.secho("\n💬 Need More Help?", fg="cyan", bold=True)
    click.secho("   • Documentation: https://django-tailwind-cli.rtfd.io/", fg="blue")
    click.secho("   • GitHub Issues: https://github.com/django-commons/django-tailwind-cli/issues", fg="blue")
    click.secho("   • Command help: python manage.py tailwind COMMAND --help", fg="blue")

    click.secho("\n✨ Pro tip: Run 'python manage.py tailwind setup' for guided configuration!", fg="yellow")


def print_performance_tips() -> None:
    click.secho("\n⚡ Django Tailwind CLI Performance Optimization", fg="cyan", bold=True)
    click.secho("=" * 55, fg="cyan")

    # Build Performance
    click.secho("\n🏗️ Build Performance", fg="yellow", bold=True)
    click.secho("   Optimize your CSS build times:", fg="blue")
    click.secho("   • Use file modification checks (automatic)", fg="green")
    click.secho("   • Only force rebuild when necessary: --force", fg="green")
    click.secho("   • Pin Tailwind version in production: TAILWIND_CLI_VERSION", fg="green")
    click.secho("   • Disable automatic downloads in CI: TAILWIND_CLI_AUTOMATIC_DOWNLOAD=False", fg="green")

    # File Watching
    click.secho("\n👀 File Watching Efficiency", fg="yellow", bold=True)
    click.secho("   Optimize development file watching:", fg="blue")
    click.secho("   • Use 'tailwind runserver' for integrated development", fg="green")
    click.secho("   • Exclude unnecessary directories from template scanning", fg="green")
    click.secho("   • Keep templates organized in standard Django locations", fg="green")
    click.secho("   • Use .gitignore patterns for large file trees", fg="green")

    # Template Optimization
    click.secho("\n📄 Template Scanning", fg="yellow", bold=True)
    click.secho("   Optimize template discovery:", fg="blue")
    click.secho("   • Declare template sources with @source directives in your CSS", fg="green")
    click.secho("   • Organize templates in app-specific directories", fg="green")
    click.secho("   • Avoid deeply nested template hierarchies", fg="green")
    click.secho("   • Use standard Django template patterns", fg="green")

    # Production Optimization
    click.secho("\n🚀 Production Deployment", fg="yellow", bold=True)
    click.secho("   Best practices for production:", fg="blue")
    click.secho("   • Pre-install CLI binary in Docker images", fg="green")
    click.secho("   • Use specific version: TAILWIND_CLI_VERSION='4.1.3'", fg="green")
    click.secho("   • Build CSS during container build, not runtime", fg="green")
    click.secho("   • Serve CSS with proper cache headers", fg="green")

    # Development Workflow
    click.secho("\n🛠️ Development Workflow", fg="yellow", bold=True)
    click.secho("   Streamline your development process:", fg="blue")
    click.secho("   • Use verbose mode for troubleshooting: --verbose", fg="green")
    click.secho("   • Monitor build times with verbose output", fg="green")
    click.secho("   • Configure IDE for Tailwind CSS IntelliSense", fg="green")
    click.secho("   • Set up proper static file serving", fg="green")

    # Common Pitfalls
    click.secho("\n⚠️ Common Performance Pitfalls", fg="yellow", bold=True)
    click.secho("   Avoid these common issues:", fg="blue")
    click.secho("   ❌ Running builds on every request", fg="red")
    click.secho("   ❌ Not using file watching in development", fg="red")
    click.secho("   ❌ Scanning unnecessary file types", fg="red")
    click.secho("   ❌ Using --force without need", fg="red")
    click.secho("   ❌ Not pinning versions in production", fg="red")

    # Configuration Examples
    click.secho("\n⚙️ Performance Configuration Examples", fg="yellow", bold=True)
    click.secho("   Development settings:", fg="blue")
    click.secho("   TAILWIND_CLI_VERSION = 'latest'  # Auto-update", fg="green")
    click.secho("   TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True", fg="green")
    click.secho("\n   Production settings:", fg="blue")
    click.secho("   TAILWIND_CLI_VERSION = '4.1.3'  # Pin version", fg="green")
    click.secho("   TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False", fg="green")
    click.secho("   TAILWIND_CLI_PATH = '/usr/local/bin/tailwindcss'", fg="green")

    # Monitoring
    click.secho("\n📊 Performance Monitoring", fg="yellow", bold=True)
    click.secho("   Monitor and measure performance:", fg="blue")
    click.secho("   • Build times: python manage.py tailwind build --verbose", fg="green")
    click.secho("   • Configuration check: python manage.py tailwind config", fg="green")
    click.secho("   • File watching logs: python manage.py tailwind watch --verbose", fg="green")

    click.secho(
        "\n✨ Pro tip: Start with 'python manage.py tailwind runserver' for the best development experience!",
        fg="cyan",
    )


def print_configuration() -> None:
    config = get_config()

    click.secho("\n🔧 Django Tailwind CLI Configuration", fg="cyan", bold=True)
    click.secho("=" * 50, fg="cyan")

    # Version information
    click.secho("\n📦 Version Information:", fg="yellow", bold=True)
    click.secho(f"   Tailwind CSS Version: {config.version_str}", fg="green")
    click.secho(f"   DaisyUI Enabled: {'Yes' if config.use_daisy_ui else 'No'}", fg="green")
    click.secho(f"   Auto Download: {'Yes' if config.automatic_download else 'No'}", fg="green")

    # Path information
    click.secho("\n📁 File Paths:", fg="yellow", bold=True)
    cli_exists = "✅" if config.cli_path.exists() else "❌"
    origin = "system binary" if config.uses_system_binary else "managed download"
    click.secho(f"   CLI Binary: {config.cli_path} {cli_exists} ({origin})", fg="green")

    # CSS Entries
    click.secho(f"\n📄 CSS Entries ({len(config.css_entries)}):", fg="yellow", bold=True)
    for entry in config.css_entries:
        src_exists = "✅" if entry.src_css.exists() else "❌"
        dist_exists = "✅" if entry.dist_css.exists() else "❌"
        click.secho(f"   [{entry.name}]", fg="cyan")
        click.secho(f"      Source: {entry.src_css} {src_exists}", fg="green")
        click.secho(f"      Output: {entry.dist_css} {dist_exists}", fg="green")

    # Django Settings
    click.secho("\n⚙️ Django Settings:", fg="yellow", bold=True)
    staticfiles_dirs = getattr(settings, "STATICFILES_DIRS", None)
    click.secho(f"   STATICFILES_DIRS: {staticfiles_dirs}", fg="green")

    version_setting = getattr(settings, "TAILWIND_CLI_VERSION", "latest")
    click.secho(f"   TAILWIND_CLI_VERSION: {version_setting}", fg="green")

    cli_path_setting = getattr(settings, "TAILWIND_CLI_PATH", None)
    if cli_path_setting:
        click.secho(f"   TAILWIND_CLI_PATH: {cli_path_setting}", fg="green")

    if getattr(settings, "TAILWIND_CLI_USE_SYSTEM_BINARY", False):
        click.secho("   TAILWIND_CLI_USE_SYSTEM_BINARY: True", fg="green")
        system_binary_name = getattr(settings, "TAILWIND_CLI_SYSTEM_BINARY_NAME", None)
        if system_binary_name:
            click.secho(f"   TAILWIND_CLI_SYSTEM_BINARY_NAME: {system_binary_name}", fg="green")

    # Show CSS settings based on mode
    css_map_setting = getattr(settings, "TAILWIND_CLI_CSS_MAP", None)
    if css_map_setting:
        click.secho(f"   TAILWIND_CLI_CSS_MAP: {css_map_setting}", fg="green")
    else:
        src_css_setting = getattr(settings, "TAILWIND_CLI_SRC_CSS", None)
        if src_css_setting:
            click.secho(f"   TAILWIND_CLI_SRC_CSS: {src_css_setting}", fg="green")

        dist_css_setting = getattr(settings, "TAILWIND_CLI_DIST_CSS", None)
        if dist_css_setting:
            click.secho(f"   TAILWIND_CLI_DIST_CSS: {dist_css_setting}", fg="green")

    # Platform information
    platform_info = get_platform_info()
    click.secho("\n💻 Platform Information:", fg="yellow", bold=True)
    click.secho(f"   Operating System: {platform_info.system}", fg="green")
    click.secho(f"   Architecture: {platform_info.machine}", fg="green")
    click.secho(f"   Binary Extension: {platform_info.extension or 'none'}", fg="green")

    # Commands
    click.secho("\n🔗 Command URLs:", fg="yellow", bold=True)
    click.secho(f"   Download URL: {config.download_url}", fg="blue")

    # Status summary
    click.secho("\n📊 Status Summary:", fg="yellow", bold=True)
    cli_exists = config.cli_path.exists()
    all_src_exist = all(entry.src_css.exists() for entry in config.css_entries)
    if cli_exists and all_src_exist:
        click.secho("   ✅ Ready to build CSS", fg="green")
    else:
        click.secho("   ⚠️  Setup required", fg="yellow")
        if not cli_exists:
            click.secho("      • Run: python manage.py tailwind download_cli", fg="blue")
        if not all_src_exist:
            click.secho("      • Run: python manage.py tailwind build", fg="blue")
