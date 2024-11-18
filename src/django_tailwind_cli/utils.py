"""
Utility functions.

This module contains utility functions to read the configuration, download the CLI and determine
the various paths.
"""

import os
import platform
from pathlib import Path

from django.conf import settings

from django_tailwind_cli import conf


def get_system_and_machine() -> tuple[str, str]:
    """Get the system and machine name."""
    system = platform.system().lower()
    if system == "darwin":
        system = "macos"

    machine = platform.machine().lower()
    if machine in ["x86_64", "amd64"]:
        machine = "x64"
    elif machine == "aarch64":
        machine = "arm64"

    return system, machine


def get_download_url() -> str:
    """Get the download url for the Tailwind CSS CLI."""
    system, machine = get_system_and_machine()
    extension = ".exe" if system == "windows" else ""
    return (
        f"https://github.com/{conf.get_tailwind_cli_src_repo()}/releases/download/"
        f"v{conf.get_tailwind_cli_version()}/{conf.get_tailwind_cli_asset_name()}-{system}-{machine}{extension}"
    )


def get_full_cli_path() -> Path:
    """Get path to the Tailwind CSS CLI."""

    cli_path = (
        Path(conf.get_tailwind_cli_path()).expanduser() if conf.get_tailwind_cli_path() else None
    )

    # If Tailwind CSS CLI path points to an existing executable use is.
    if cli_path and cli_path.exists() and cli_path.is_file() and os.access(cli_path, os.X_OK):
        return cli_path

    # Otherwise try to calculate the full cli path as usual.
    system, machine = get_system_and_machine()
    extension = ".exe" if system == "windows" else ""
    executable_name = f"tailwindcss-{system}-{machine}-{conf.get_tailwind_cli_version()}{extension}"
    if cli_path is None:
        return Path(settings.BASE_DIR) / executable_name
    else:
        return cli_path / executable_name


def get_full_src_css_path() -> Path:
    """Get path to the source css."""
    cli_src_css = conf.get_tailwind_cli_src_css()
    if cli_src_css is None:
        msg = "No source CSS file specified. Please set TAILWIND_SRC_CSS in your settings."
        raise ValueError(msg)
    return Path(settings.BASE_DIR) / cli_src_css


def get_full_dist_css_path() -> Path:
    """Get path to the compiled css."""
    if settings.STATICFILES_DIRS is None or len(settings.STATICFILES_DIRS) == 0:
        msg = "STATICFILES_DIRS is empty. Please add a path to your static files."
        raise ValueError(msg)

    return Path(settings.STATICFILES_DIRS[0]) / conf.get_tailwind_cli_dist_css()


def get_full_config_file_path() -> Path:
    """Get path to the tailwind.config.js file."""
    return Path(settings.BASE_DIR) / conf.get_tailwind_cli_config_file()


def validate_settings() -> None:
    """Validate the settings."""
    if settings.STATICFILES_DIRS is None or len(settings.STATICFILES_DIRS) == 0:
        msg = "STATICFILES_DIRS is empty. Please add a path to your static files."
        raise ValueError(msg)
