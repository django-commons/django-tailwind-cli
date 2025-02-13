import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from django.conf import settings
from semver import Version

FALLBACK_VERSION = "4.0.6"


@dataclass
class Config:
    version_str: str
    version: Version
    cli_path: Path
    download_url: str
    dist_css: Path
    dist_css_base: str
    src_css: Optional[Path]
    config_file: Optional[Path]
    automatic_download: bool = True

    @property
    def watch_cmd(self) -> list[str]:
        result = [
            str(self.cli_path),
            "--output",
            str(self.dist_css),
            "--watch",
        ]

        if self.src_css:
            result.extend(["--input", str(self.src_css)])

        return result

    @property
    def build_cmd(self) -> list[str]:
        result = [
            str(self.cli_path),
            "--output",
            str(self.dist_css),
            "--minify",
        ]

        if self.src_css:
            result.extend(["--input", str(self.src_css)])

        return result


def get_version() -> tuple[str, Version]:
    """
    Retrieves the version of Tailwind CSS specified in the Django settings or fetches the latest
    version from the Tailwind CSS GitHub repository.

    Returns:
        tuple[str, Version]: A tuple containing the version string and the parsed Version object.

    Raises:
        ValueError: If the TAILWIND_CLI_SRC_REPO setting is None when the version is set to
        "latest".
    """
    version_str = getattr(settings, "TAILWIND_CLI_VERSION", "latest")

    if version_str == "latest":
        repo_url = getattr(settings, "TAILWIND_CLI_SRC_REPO", "tailwindlabs/tailwindcss")
        if not repo_url:
            raise ValueError("TAILWIND_CLI_SRC_REPO must not be None.")
        r = requests.get(f"https://github.com/{repo_url}/releases/latest/", timeout=2)
        if r.ok and "location" in r.headers:
            version_str = r.headers["location"].rstrip("/").split("/")[-1].replace("v", "")
        else:
            version_str = FALLBACK_VERSION

    return version_str, Version.parse(version_str)


def get_config() -> Config:
    if settings.STATICFILES_DIRS is None or len(settings.STATICFILES_DIRS) == 0:
        raise ValueError("STATICFILES_DIRS is empty. Please add a path to your static files.")

    # Determine the system and machine we are running on
    system = platform.system().lower()
    system = "macos" if system == "darwin" else system

    machine = platform.machine().lower()
    if machine in ["x86_64", "amd64"]:
        machine = "x64"
    elif machine == "aarch64":
        machine = "arm64"

    # Yeah, windows has this exe thingy..
    extension = ".exe" if system == "windows" else ""

    # Read version from settings
    version_str, version = get_version()

    # Determine the full path to the CLI
    cli_path = Path(getattr(settings, "TAILWIND_CLI_PATH", "~/.local/bin/") or settings.BASE_DIR)
    if cli_path.exists() and cli_path.is_file() and os.access(cli_path, os.X_OK):
        cli_path = cli_path.expanduser().resolve()
    else:
        cli_path = cli_path.expanduser() / f"tailwindcss-{system}-{machine}-{version_str}{extension}"

    # Determine the download url for the cli
    if not (asset_name := getattr(settings, "TAILWIND_CLI_ASSET_NAME", "tailwindcss")):
        raise ValueError("TAILWIND_CLI_ASSET_NAME must not be None.")
    if not (repo_url := getattr(settings, "TAILWIND_CLI_SRC_REPO", "tailwindlabs/tailwindcss")):
        raise ValueError("TAILWIND_CLI_SRC_REPO must not be None.")
    download_url = (
        f"https://github.com/{repo_url}/releases/download/v{version_str}/{asset_name}-{system}-{machine}{extension}"
    )

    # Determine the full path to the dist css file
    if not (dist_css_base := getattr(settings, "TAILWIND_CLI_DIST_CSS", "css/tailwind.css")):
        raise ValueError("TAILWIND_CLI_DIST_CSS must not be None.")
    dist_css = Path(settings.STATICFILES_DIRS[0]) / dist_css_base

    # Determine the full path to the source css file.
    # It is optional for Tailwind CSS < 4.0.0, but required for >= 4.0.0.
    if version >= Version.parse("4.0.0"):
        if not (src_css := getattr(settings, "TAILWIND_CLI_SRC_CSS", "css/source.css")):
            raise ValueError("TAILWIND_CLI_SRC_CSS must not be None.")
        src_css = Path(settings.STATICFILES_DIRS[0]) / src_css
    else:
        if not (src_css := getattr(settings, "TAILWIND_CLI_SRC_CSS", None)):
            src_css = None
        else:
            src_css = Path(settings.STATICFILES_DIRS[0]) / src_css

    # Determine the full path to the config file.
    # It is optional for Tailwind CSS >= 4.0.0, but required for < 4.0.0.
    if version < Version.parse("4.0.0"):
        if not (config_file := getattr(settings, "TAILWIND_CLI_CONFIG_FILE", "tailwind.config.js")):
            raise ValueError("TAILWIND_CLI_CONFIG_FILE must not be None.")
        config_file = Path(settings.BASE_DIR) / config_file
    else:
        if config_file := getattr(settings, "TAILWIND_CLI_CONFIG_FILE", None):
            raise ValueError("TAILWIND_CLI_CONFIG_FILE is not used by this library with Tailwind CSS >= 4.x.")
        config_file = None

    # Determine if the CLI should be downloaded automatically
    automatic_download = getattr(settings, "TAILWIND_CLI_AUTOMATIC_DOWNLOAD", True)

    # return configuration
    return Config(
        version_str=version_str,
        version=version,
        cli_path=cli_path,
        download_url=download_url,
        dist_css=dist_css,
        dist_css_base=dist_css_base,
        src_css=src_css,
        config_file=config_file,
        automatic_download=automatic_download,
    )
