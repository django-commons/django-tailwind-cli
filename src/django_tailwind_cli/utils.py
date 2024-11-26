"""
Utility functions.

This module contains utility functions to read the configuration, download the CLI and determine
the various paths.
"""

import os
import platform
from pathlib import Path
from typing import Optional

from django.conf import settings

from django_tailwind_cli import conf


def get_system_name(system: str) -> str:
    """Normalize the system name."""
    if system == "darwin":
        return "macos"
    return system


def get_machine_name(machine: str) -> str:
    """Normalize the machine name."""
    if machine in ["x86_64", "amd64"]:
        return "x64"
    elif machine == "aarch64":
        return "arm64"
    return machine


def get_system_and_machine() -> tuple[str, str]:
    """Get the system and machine name."""
    system = get_system_name(platform.system().lower())
    machine = get_machine_name(platform.machine().lower())
    return system, machine


def get_download_url() -> str:
    """Get the download URL for the Tailwind CSS CLI."""
    system, machine = get_system_and_machine()

    # Determine the file extension based on the operating system
    extension = ".exe" if system == "windows" else ""

    # Get Tailwind configuration details
    repo_url = conf.get_tailwind_cli_src_repo()
    version = conf.get_tailwind_cli_version()
    asset_name = conf.get_tailwind_cli_asset_name()

    # Construct and return the download URL
    download_url = (
        f"https://github.com/{repo_url}/releases/download/"
        f"v{version}/{asset_name}-{system}-{machine}{extension}"
    )
    return download_url


def get_existing_cli_path(cli_path: Optional[Path]) -> Optional[Path]:
    """Check if the given CLI path points to a valid executable."""
    return (
        cli_path
        if cli_path and cli_path.exists() and cli_path.is_file() and os.access(cli_path, os.X_OK)
        else None
    )


def get_full_executable_name(system: str, machine: str, version: str) -> str:
    """Construct the full executable name based on system and machine architecture."""
    extension = ".exe" if system == "windows" else ""
    return f"tailwindcss-{system}-{machine}-{version}{extension}"


def get_full_cli_path() -> Path:
    """Get path to the Tailwind CSS CLI."""
    cli_path_str = conf.get_tailwind_cli_path()
    cli_path = Path(cli_path_str).expanduser() if cli_path_str else None

    # Check if the CLI path points to a valid existing executable
    existing_cli_path = get_existing_cli_path(cli_path)
    if existing_cli_path:
        return existing_cli_path

    # Otherwise try to calculate the full CLI path as usual
    system, machine = get_system_and_machine()
    executable_name = get_full_executable_name(system, machine, conf.get_tailwind_cli_version())

    if cli_path is None:
        return Path(settings.BASE_DIR) / executable_name
    else:
        return cli_path / executable_name


def get_full_src_css_path() -> Path:
    """Get path to the source css."""
    cli_src_css = conf.get_tailwind_cli_src_css()
    if cli_src_css is None:
        raise ValueError(
            "No source CSS file specified. Please set TAILWIND_SRC_CSS in your settings."
        )
    return Path(settings.BASE_DIR) / cli_src_css


def get_full_dist_css_path() -> Path:
    """Get path to the compiled css."""
    if settings.STATICFILES_DIRS is None or len(settings.STATICFILES_DIRS) == 0:
        raise ValueError("STATICFILES_DIRS is empty. Please add a path to your static files.")

    return Path(settings.STATICFILES_DIRS[0]) / conf.get_tailwind_cli_dist_css()


def get_full_config_file_path() -> Path:
    """Get path to the tailwind.config.js file."""
    return Path(settings.BASE_DIR) / conf.get_tailwind_cli_config_file()


def validate_settings() -> None:
    """Validate the settings."""
    if settings.STATICFILES_DIRS is None or len(settings.STATICFILES_DIRS) == 0:
        raise ValueError("STATICFILES_DIRS is empty. Please add a path to your static files.")
