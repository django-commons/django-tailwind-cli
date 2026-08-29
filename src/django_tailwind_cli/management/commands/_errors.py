"""Error handling for the management commands.

`handle_command_errors` and the four suggestion helpers are one unit: the decorator's whole job is
to pick which hint to print, and nothing else calls them.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import click
from django.core.management.base import CommandError

from django_tailwind_cli.config import ConfigurationError


def handle_command_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to handle common command errors consistently.

    Prints the message and a hint to stderr, then lets the failure continue. A missing file or an
    unwritable path is a user error, so it continues as a ``CommandError``: Django renders that as
    one line and exits 1, and a caller using ``call_command`` can still catch it — which
    ``sys.exit`` here would take away. Anything else is a bug in this package and keeps its
    traceback.

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
            click.secho(f"❌ Command error: {e}", fg="red", err=True)
            suggest_command_error_solutions(str(e))
            raise
        except ConfigurationError as e:
            click.secho(f"❌ Configuration error: {e}", fg="red", err=True)
            suggest_command_error_solutions(str(e))
            raise CommandError(str(e)) from e
        except FileNotFoundError as e:
            click.secho(f"❌ File not found: {e}", fg="red", err=True)
            suggest_file_error_solutions(str(e))
            raise CommandError(str(e)) from e
        except PermissionError as e:
            click.secho(f"❌ Permission denied: {e}", fg="red", err=True)
            suggest_permission_error_solutions(str(e))
            raise CommandError(str(e)) from e
        except (click.exceptions.Exit, click.exceptions.Abort):
            # click's own control flow, not a failure. These subclass Exception, so without this
            # clause the handler below announces a normal exit as "❌ Unexpected error: Exit: 0".
            raise
        except Exception as e:
            # Not a user error: keep the traceback so the bug is reportable.
            click.secho(f"❌ Unexpected error: {type(e).__name__}: {e}", fg="red", err=True)
            suggest_general_error_solutions(str(e))
            raise

    # An explicit marker, so the test that pins "every command is decorated" can look for this
    # decorator rather than for any wrapping at all — click.pass_context wraps too.
    wrapper.handles_command_errors = True  # pyright: ignore[reportAttributeAccessIssue]
    return wrapper


def suggest_command_error_solutions(error_msg: str) -> None:
    """Provide actionable suggestions for command errors."""
    error_msg_lower = error_msg.lower()

    if "staticfiles_dirs" in error_msg_lower:
        click.secho("\n💡 Solution:", fg="yellow", err=True)
        click.secho("   Add STATICFILES_DIRS to your Django settings.py:", fg="blue", err=True)
        click.secho("   STATICFILES_DIRS = [BASE_DIR / 'assets']", fg="green", err=True)

    elif "base_dir" in error_msg_lower:
        click.secho("\n💡 Solution:", fg="yellow", err=True)
        click.secho("   Ensure BASE_DIR is properly set in your Django settings.py:", fg="blue", err=True)
        click.secho("   BASE_DIR = Path(__file__).resolve().parent.parent", fg="green", err=True)

    elif "tailwind css 3.x" in error_msg_lower:
        click.secho("\n💡 Solution:", fg="yellow", err=True)
        click.secho("   Use django-tailwind-cli v2.21.1 for Tailwind CSS 3.x:", fg="blue", err=True)
        click.secho("   pip install 'django-tailwind-cli==2.21.1'", fg="green", err=True)
        click.secho("   Or upgrade to Tailwind CSS 4.x (recommended)", fg="green", err=True)

    elif "version" in error_msg_lower:
        click.secho("\n💡 Solution:", fg="yellow", err=True)
        click.secho("   Check your TAILWIND_CLI_VERSION setting:", fg="blue", err=True)
        click.secho("   TAILWIND_CLI_VERSION = 'latest'  # or specific version like '4.1.3'", fg="green", err=True)


def suggest_file_error_solutions(error_msg: str) -> None:
    """Provide actionable suggestions for file not found errors."""
    click.secho("\n💡 Suggestions:", fg="yellow", err=True)

    if "tailwindcss" in error_msg.lower():
        click.secho("   • Download the Tailwind CLI binary:", fg="blue", err=True)
        click.secho("     python manage.py tailwind download_cli", fg="green", err=True)
        click.secho("   • Check your TAILWIND_CLI_PATH setting", fg="blue", err=True)

    elif ".css" in error_msg.lower():
        click.secho("   • Ensure your CSS input file exists", fg="blue", err=True)
        click.secho("   • Check TAILWIND_CLI_SRC_CSS setting", fg="blue", err=True)
        click.secho("   • Run: python manage.py tailwind build", fg="green", err=True)

    else:
        click.secho("   • Check the file path is correct", fg="blue", err=True)
        click.secho("   • Ensure the directory exists", fg="blue", err=True)
        click.secho("   • Verify file permissions", fg="blue", err=True)


def suggest_permission_error_solutions(_error_msg: str) -> None:
    """Provide actionable suggestions for permission errors."""
    click.secho("\n💡 Solutions:", fg="yellow", err=True)
    click.secho("   • Check file/directory permissions:", fg="blue", err=True)
    click.secho("     chmod 755 .django_tailwind_cli/", fg="green", err=True)
    click.secho("   • Ensure the parent directory is writable", fg="blue", err=True)
    click.secho("   • Try running with appropriate user permissions", fg="blue", err=True)
    click.secho("   • On Windows, check if files are locked by another process", fg="blue", err=True)


def suggest_general_error_solutions(error_msg: str) -> None:
    """Provide general troubleshooting suggestions."""
    error_msg_lower = error_msg.lower()

    click.secho("\n💡 Troubleshooting steps:", fg="yellow", err=True)

    if "network" in error_msg_lower or "connection" in error_msg_lower:
        click.secho("   • Check your internet connection", fg="blue", err=True)
        click.secho("   • Try again (temporary network issues)", fg="blue", err=True)
        click.secho("   • Set a specific version instead of 'latest':", fg="blue", err=True)
        click.secho("     TAILWIND_CLI_VERSION = '4.1.3'", fg="green", err=True)

    elif "import" in error_msg_lower or "module" in error_msg_lower:
        click.secho("   • Ensure django-tailwind-cli is installed:", fg="blue", err=True)
        click.secho("     pip install django-tailwind-cli", fg="green", err=True)
        click.secho("   • Add 'django_tailwind_cli' to INSTALLED_APPS", fg="blue", err=True)

    else:
        click.secho("   • Check your Django settings configuration", fg="blue", err=True)
        click.secho("   • Verify STATICFILES_DIRS is set correctly", fg="blue", err=True)
        click.secho("   • Try: python manage.py tailwind download_cli", fg="green", err=True)
        click.secho("   • For help: python manage.py tailwind --help", fg="green", err=True)
