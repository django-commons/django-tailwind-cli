from typing import Optional

from django.conf import settings

DEFAULT_VERSION = "3.4.13"
DEFAULT_SRC_REPO = "tailwindlabs/tailwindcss"


def get_tailwind_cli_version() -> str:
    """Get the version of the Tailwind CSS CLI."""
    return getattr(settings, "TAILWIND_CLI_VERSION", DEFAULT_VERSION)


def get_tailwind_cli_path() -> str:
    """Get the path to the Tailwind CSS CLI."""
    return getattr(settings, "TAILWIND_CLI_PATH", "~/.local/bin/")


def get_tailwind_cli_automatic_download() -> bool:
    """Get the automatic download setting for the Tailwind CSS CLI."""
    return getattr(settings, "TAILWIND_CLI_AUTOMATIC_DOWNLOAD", True)


def get_tailwind_cli_src_css() -> Optional[str]:
    """Get the source css file for the Tailwind CSS CLI."""
    return getattr(settings, "TAILWIND_CLI_SRC_CSS", None)


def get_tailwind_cli_dist_css() -> str:
    """Get the dist css file for the Tailwind CSS CLI."""
    return getattr(settings, "TAILWIND_CLI_DIST_CSS", "css/tailwind.css")


def get_tailwind_cli_config_file() -> str:
    """Get the config file for the Tailwind CSS CLI."""
    return getattr(settings, "TAILWIND_CLI_CONFIG_FILE", "tailwind.config.js")


def get_tailwind_cli_src_repo() -> str:
    """Get the source repository for the Tailwind CSS CLI."""
    return getattr(settings, "TAILWIND_CLI_SRC_REPO", DEFAULT_SRC_REPO)


def get_tailwind_cli_asset_name() -> str:
    """Get the asset name for the Tailwind CSS CLI."""
    return getattr(settings, "TAILWIND_CLI_ASSET_NAME", "tailwindcss")
