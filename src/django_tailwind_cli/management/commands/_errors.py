"""Error handling for the management commands.

`handle_command_errors` and the four suggestion helpers are one unit: the decorator's whole job is
to pick which hint to print, and nothing else calls them.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import typer
from django.core.management.base import CommandError


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
            typer.secho(f"❌ Command error: {e}", fg=typer.colors.RED, err=True)
            suggest_command_error_solutions(str(e))
            raise
        except FileNotFoundError as e:
            typer.secho(f"❌ File not found: {e}", fg=typer.colors.RED, err=True)
            suggest_file_error_solutions(str(e))
            raise CommandError(str(e)) from e
        except PermissionError as e:
            typer.secho(f"❌ Permission denied: {e}", fg=typer.colors.RED, err=True)
            suggest_permission_error_solutions(str(e))
            raise CommandError(str(e)) from e
        except Exception as e:
            # Not a user error: keep the traceback so the bug is reportable, and let click's own
            # Exit/Abort — which subclass RuntimeError — pass through untouched.
            typer.secho(f"❌ Unexpected error: {type(e).__name__}: {e}", fg=typer.colors.RED, err=True)
            suggest_general_error_solutions(str(e))
            raise

    return wrapper


def suggest_command_error_solutions(error_msg: str) -> None:
    """Provide actionable suggestions for command errors."""
    error_msg_lower = error_msg.lower()

    if "staticfiles_dirs" in error_msg_lower:
        typer.secho("\n💡 Solution:", fg=typer.colors.YELLOW, err=True)
        typer.secho("   Add STATICFILES_DIRS to your Django settings.py:", fg=typer.colors.BLUE, err=True)
        typer.secho("   STATICFILES_DIRS = [BASE_DIR / 'assets']", fg=typer.colors.GREEN, err=True)

    elif "base_dir" in error_msg_lower:
        typer.secho("\n💡 Solution:", fg=typer.colors.YELLOW, err=True)
        typer.secho("   Ensure BASE_DIR is properly set in your Django settings.py:", fg=typer.colors.BLUE, err=True)
        typer.secho("   BASE_DIR = Path(__file__).resolve().parent.parent", fg=typer.colors.GREEN, err=True)

    elif "tailwind css 3.x" in error_msg_lower:
        typer.secho("\n💡 Solution:", fg=typer.colors.YELLOW, err=True)
        typer.secho("   Use django-tailwind-cli v2.21.1 for Tailwind CSS 3.x:", fg=typer.colors.BLUE, err=True)
        typer.secho("   pip install 'django-tailwind-cli==2.21.1'", fg=typer.colors.GREEN, err=True)
        typer.secho("   Or upgrade to Tailwind CSS 4.x (recommended)", fg=typer.colors.GREEN, err=True)

    elif "version" in error_msg_lower:
        typer.secho("\n💡 Solution:", fg=typer.colors.YELLOW, err=True)
        typer.secho("   Check your TAILWIND_CLI_VERSION setting:", fg=typer.colors.BLUE, err=True)
        typer.secho(
            "   TAILWIND_CLI_VERSION = 'latest'  # or specific version like '4.1.3'", fg=typer.colors.GREEN, err=True
        )


def suggest_file_error_solutions(error_msg: str) -> None:
    """Provide actionable suggestions for file not found errors."""
    typer.secho("\n💡 Suggestions:", fg=typer.colors.YELLOW, err=True)

    if "tailwindcss" in error_msg.lower():
        typer.secho("   • Download the Tailwind CLI binary:", fg=typer.colors.BLUE, err=True)
        typer.secho("     python manage.py tailwind download_cli", fg=typer.colors.GREEN, err=True)
        typer.secho("   • Check your TAILWIND_CLI_PATH setting", fg=typer.colors.BLUE, err=True)

    elif ".css" in error_msg.lower():
        typer.secho("   • Ensure your CSS input file exists", fg=typer.colors.BLUE, err=True)
        typer.secho("   • Check TAILWIND_CLI_SRC_CSS setting", fg=typer.colors.BLUE, err=True)
        typer.secho("   • Run: python manage.py tailwind build", fg=typer.colors.GREEN, err=True)

    else:
        typer.secho("   • Check the file path is correct", fg=typer.colors.BLUE, err=True)
        typer.secho("   • Ensure the directory exists", fg=typer.colors.BLUE, err=True)
        typer.secho("   • Verify file permissions", fg=typer.colors.BLUE, err=True)


def suggest_permission_error_solutions(_error_msg: str) -> None:
    """Provide actionable suggestions for permission errors."""
    typer.secho("\n💡 Solutions:", fg=typer.colors.YELLOW, err=True)
    typer.secho("   • Check file/directory permissions:", fg=typer.colors.BLUE, err=True)
    typer.secho("     chmod 755 .django_tailwind_cli/", fg=typer.colors.GREEN, err=True)
    typer.secho("   • Ensure the parent directory is writable", fg=typer.colors.BLUE, err=True)
    typer.secho("   • Try running with appropriate user permissions", fg=typer.colors.BLUE, err=True)
    typer.secho("   • On Windows, check if files are locked by another process", fg=typer.colors.BLUE, err=True)


def suggest_general_error_solutions(error_msg: str) -> None:
    """Provide general troubleshooting suggestions."""
    error_msg_lower = error_msg.lower()

    typer.secho("\n💡 Troubleshooting steps:", fg=typer.colors.YELLOW, err=True)

    if "network" in error_msg_lower or "connection" in error_msg_lower:
        typer.secho("   • Check your internet connection", fg=typer.colors.BLUE, err=True)
        typer.secho("   • Try again (temporary network issues)", fg=typer.colors.BLUE, err=True)
        typer.secho("   • Set a specific version instead of 'latest':", fg=typer.colors.BLUE, err=True)
        typer.secho("     TAILWIND_CLI_VERSION = '4.1.3'", fg=typer.colors.GREEN, err=True)

    elif "import" in error_msg_lower or "module" in error_msg_lower:
        typer.secho("   • Ensure django-tailwind-cli is installed:", fg=typer.colors.BLUE, err=True)
        typer.secho("     pip install django-tailwind-cli", fg=typer.colors.GREEN, err=True)
        typer.secho("   • Add 'django_tailwind_cli' to INSTALLED_APPS", fg=typer.colors.BLUE, err=True)

    else:
        typer.secho("   • Check your Django settings configuration", fg=typer.colors.BLUE, err=True)
        typer.secho("   • Verify STATICFILES_DIRS is set correctly", fg=typer.colors.BLUE, err=True)
        typer.secho("   • Try: python manage.py tailwind download_cli", fg=typer.colors.GREEN, err=True)
        typer.secho("   • For help: python manage.py tailwind --help", fg=typer.colors.GREEN, err=True)
