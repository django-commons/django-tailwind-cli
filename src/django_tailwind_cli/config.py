"""Configuration management for django-tailwind-cli.

This module handles all configuration aspects of the Tailwind CSS integration,
including version management, path resolution, and Django settings validation.

Configuration Settings:
    The following Django settings are recognized:

    Core Settings:
        STATICFILES_DIRS (required): List of directories for static files
            Example: STATICFILES_DIRS = [BASE_DIR / 'assets']

        TAILWIND_CLI_VERSION (optional): Tailwind CSS version to use
            Default: 'latest'
            Example: TAILWIND_CLI_VERSION = '4.1.3'
            Special: 'latest' fetches newest version from GitHub

    Path Settings:
        TAILWIND_CLI_PATH (optional): Path to CLI binary or directory
            Default: '.django_tailwind_cli' (in project root)
            Example: TAILWIND_CLI_PATH = '/usr/local/bin/tailwindcss'

        TAILWIND_CLI_SRC_CSS (optional): Input CSS file path (single-file mode)
            Default: '.django_tailwind_cli/source.css' (auto-created)
            Example: TAILWIND_CLI_SRC_CSS = 'src/styles/main.css'
            Note: Cannot be used with TAILWIND_CLI_CSS_MAP

        TAILWIND_CLI_DIST_CSS (optional): Output CSS file path (single-file mode)
            Default: 'css/tailwind.css' (relative to STATICFILES_DIRS[0])
            Example: TAILWIND_CLI_DIST_CSS = 'dist/main.css'
            Note: Cannot be used with TAILWIND_CLI_CSS_MAP

        TAILWIND_CLI_CSS_MAP (optional): Multiple CSS entry points (multi-file mode)
            Default: None (uses single-file mode)
            Example: TAILWIND_CLI_CSS_MAP = [
                ('admin.css', 'admin.output.css'),
                ('web.css', 'web.output.css'),
            ]
            Note: Cannot be used with TAILWIND_CLI_SRC_CSS or TAILWIND_CLI_DIST_CSS

    Advanced Settings:
        TAILWIND_CLI_USE_DAISY_UI (optional): Enable DaisyUI components
            Default: False
            Example: TAILWIND_CLI_USE_DAISY_UI = True

        TAILWIND_CLI_SRC_REPO (optional): Custom Tailwind CLI repository
            Default: 'tailwindlabs/tailwindcss' (or DaisyUI variant)
            Example: TAILWIND_CLI_SRC_REPO = 'custom/tailwind-fork'

        TAILWIND_CLI_ASSET_NAME (optional): CLI asset name for downloads
            Default: 'tailwindcss' (or 'tailwindcss-extra' for DaisyUI)
            Example: TAILWIND_CLI_ASSET_NAME = 'tailwind-custom'

        TAILWIND_CLI_AUTOMATIC_DOWNLOAD (optional): Auto-download CLI
            Default: True
            Example: TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False

        TAILWIND_CLI_REQUEST_TIMEOUT (optional): Network request timeout
            Default: 10 (seconds)
            Example: TAILWIND_CLI_REQUEST_TIMEOUT = 30

Examples of complete settings configuration:

    # Minimal configuration
    STATICFILES_DIRS = [BASE_DIR / 'assets']

    # Production configuration
    STATICFILES_DIRS = [BASE_DIR / 'static']
    TAILWIND_CLI_VERSION = '4.1.3'  # Pin to specific version
    TAILWIND_CLI_DIST_CSS = 'css/app.css'

    # Development with DaisyUI
    STATICFILES_DIRS = [BASE_DIR / 'assets']
    TAILWIND_CLI_USE_DAISY_UI = True
    TAILWIND_CLI_SRC_CSS = 'src/styles/main.css'

    # Custom CLI setup
    STATICFILES_DIRS = [BASE_DIR / 'static']
    TAILWIND_CLI_PATH = '/opt/tailwindcss/bin/tailwindcss'
    TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False

    # Multiple CSS entry points (e.g., admin + public website)
    STATICFILES_DIRS = [BASE_DIR / 'assets']
    TAILWIND_CLI_CSS_MAP = [
        ('admin.css', 'admin.output.css'),    # Admin panel styles
        ('web.css', 'web.output.css'),        # Public website styles
    ]
"""

import os
import platform
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from django_tailwind_cli.utils import http
from django.conf import settings
from semver import Version

FALLBACK_VERSION = "4.1.3"


class CSSEntry(NamedTuple):
    """A CSS source and destination path pair."""

    name: str  # Unique identifier derived from source filename (e.g., "admin", "web")
    src_css: Path  # Absolute path to source CSS file
    dist_css: Path  # Absolute path to output CSS file
    dist_css_base: str  # Relative path for template tag (e.g., "admin.output.css")


@dataclass
class Config:
    version_str: str
    version: Version
    cli_path: Path
    download_url: str
    css_entries: list[CSSEntry]
    overwrite_default_config: bool = True
    automatic_download: bool = True
    use_daisy_ui: bool = False

    # Backward compatibility properties
    @property
    def src_css(self) -> Path:
        """Return first source CSS path for backward compatibility."""
        return self.css_entries[0].src_css if self.css_entries else Path()

    @property
    def dist_css(self) -> Path:
        """Return first dist CSS path for backward compatibility."""
        return self.css_entries[0].dist_css if self.css_entries else Path()

    @property
    def dist_css_base(self) -> str:
        """Return first dist CSS base for backward compatibility."""
        return self.css_entries[0].dist_css_base if self.css_entries else ""

    def get_watch_cmd(self, entry: CSSEntry) -> list[str]:
        """Generate watch command for a specific CSS entry."""
        return [
            str(self.cli_path),
            "--input",
            str(entry.src_css),
            "--output",
            str(entry.dist_css),
            "--watch",
        ]

    def get_build_cmd(self, entry: CSSEntry) -> list[str]:
        """Generate build command for a specific CSS entry."""
        return [
            str(self.cli_path),
            "--input",
            str(entry.src_css),
            "--output",
            str(entry.dist_css),
            "--minify",
        ]

    @property
    def watch_cmd(self) -> list[str]:
        """Return watch command for first entry (backward compatibility)."""
        return self.get_watch_cmd(self.css_entries[0])

    @property
    def build_cmd(self) -> list[str]:
        """Return build command for first entry (backward compatibility)."""
        return self.get_build_cmd(self.css_entries[0])


class PlatformInfo(NamedTuple):
    """Platform information for CLI binary selection."""

    system: str
    machine: str
    extension: str


class VersionCache(NamedTuple):
    """Cached version information."""

    version_str: str
    version: Version
    timestamp: float


def _validate_required_settings() -> None:
    """Validate that required Django settings are configured.

    Raises:
        ValueError: If required settings are missing or invalid.
    """
    if settings.STATICFILES_DIRS is None or len(settings.STATICFILES_DIRS) == 0:
        raise ValueError(
            "STATICFILES_DIRS is empty. Please add a path to your static files. "
            "Add STATICFILES_DIRS = [BASE_DIR / 'assets'] to your Django settings."
        )

    # Validate TAILWIND_CLI_ASSET_NAME if set
    asset_name = getattr(settings, "TAILWIND_CLI_ASSET_NAME", None)
    if asset_name is not None and not asset_name:
        raise ValueError(
            "TAILWIND_CLI_ASSET_NAME must not be empty. Either remove the setting or provide a valid asset name."
        )

    # Validate TAILWIND_CLI_DIST_CSS if set
    dist_css = getattr(settings, "TAILWIND_CLI_DIST_CSS", None)
    if dist_css is not None and not dist_css:
        raise ValueError(
            "TAILWIND_CLI_DIST_CSS must not be empty. Either remove the setting or provide a valid CSS path."
        )

    # Validate TAILWIND_CLI_SRC_REPO if set
    src_repo = getattr(settings, "TAILWIND_CLI_SRC_REPO", None)
    if src_repo is not None and not src_repo:
        raise ValueError(
            "TAILWIND_CLI_SRC_REPO must not be empty. Either remove the setting or provide a valid repository URL."
        )

    # Validate mutual exclusivity of CSS settings
    _validate_css_settings()


def _validate_css_settings() -> None:
    """Validate CSS configuration settings for mutual exclusivity.

    Raises:
        ValueError: If both single-file and multi-file configurations are present.
    """
    has_css_map = hasattr(settings, "TAILWIND_CLI_CSS_MAP") and settings.TAILWIND_CLI_CSS_MAP
    has_src_css = hasattr(settings, "TAILWIND_CLI_SRC_CSS") and settings.TAILWIND_CLI_SRC_CSS
    has_dist_css = hasattr(settings, "TAILWIND_CLI_DIST_CSS") and settings.TAILWIND_CLI_DIST_CSS

    if has_css_map and (has_src_css or has_dist_css):
        raise ValueError(
            "Cannot use TAILWIND_CLI_CSS_MAP together with TAILWIND_CLI_SRC_CSS or TAILWIND_CLI_DIST_CSS. "
            "Use either the single-file configuration (SRC_CSS/DIST_CSS) or the multi-file configuration "
            "(CSS_MAP), but not both."
        )

    # Validate CSS_MAP format if provided
    if has_css_map:
        css_map_raw = settings.TAILWIND_CLI_CSS_MAP
        if not isinstance(css_map_raw, (list, tuple)):
            raise ValueError("TAILWIND_CLI_CSS_MAP must be a list or tuple of (source, destination) pairs.")

        css_map: list[tuple[str, str]] | tuple[tuple[str, str], ...] = css_map_raw  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
        names_seen: set[str] = set()
        for i, entry in enumerate(css_map):
            # Runtime validation - pyright sees typed entry, but we validate for user input
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:  # pyright: ignore[reportUnnecessaryIsInstance]
                raise ValueError(f"TAILWIND_CLI_CSS_MAP entry {i} must be a (source, destination) pair, got {entry!r}.")
            src: str = str(entry[0])
            dist: str = str(entry[1])
            if not src or not dist:
                raise ValueError(f"TAILWIND_CLI_CSS_MAP entry {i} has empty source or destination path.")

            # Check for unique names
            name = Path(src).stem
            if name in names_seen:
                raise ValueError(
                    f"TAILWIND_CLI_CSS_MAP has duplicate entry name '{name}'. "
                    "Each source file must have a unique name (stem of filename)."
                )
            names_seen.add(name)


def get_platform_info() -> PlatformInfo:
    """Get platform information for CLI binary selection.

    Returns:
        PlatformInfo: Platform details needed for binary selection.
    """
    system = platform.system().lower()
    system = "macos" if system == "darwin" else system

    machine = platform.machine().lower()
    if machine in ["x86_64", "amd64"]:
        machine = "x64"
    elif machine == "aarch64":
        machine = "arm64"

    extension = ".exe" if system == "windows" else ""

    return PlatformInfo(system=system, machine=machine, extension=extension)


def _get_cache_path() -> Path:
    """Get the path for version cache file.

    Returns:
        Path: Path to the version cache file.
    """
    cache_dir = Path(tempfile.gettempdir()) / ".django-tailwind-cli"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / "version_cache.txt"


def _load_cached_version(repo_url: str) -> VersionCache | None:
    """Load cached version information.

    Args:
        repo_url: Repository URL to match against cache.

    Returns:
        VersionCache if valid cache exists, None otherwise.
    """
    cache_path = _get_cache_path()

    if not cache_path.exists():
        return None

    try:
        with cache_path.open("r") as f:
            lines = f.readlines()
            if len(lines) >= 3:
                cached_repo = lines[0].strip()
                version_str = lines[1].strip()
                timestamp = float(lines[2].strip())

                # Cache is valid for 1 hour
                if cached_repo == repo_url and (time.time() - timestamp) < 3600:
                    return VersionCache(
                        version_str=version_str, version=Version.parse(version_str), timestamp=timestamp
                    )
    except (OSError, ValueError, IndexError):
        # Ignore cache read errors
        pass

    return None


def _save_cached_version(repo_url: str, version_str: str) -> None:
    """Save version information to cache.

    Args:
        repo_url: Repository URL.
        version_str: Version string to cache.
    """
    cache_path = _get_cache_path()

    try:
        with cache_path.open("w") as f:
            f.write(f"{repo_url}\n{version_str}\n{time.time()}\n")
    except OSError:  # pragma: no cover
        # Ignore cache write errors
        pass


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
    use_daisy_ui = getattr(settings, "TAILWIND_CLI_USE_DAISY_UI", False)
    version_str = getattr(settings, "TAILWIND_CLI_VERSION", "latest")
    repo_url = getattr(
        settings,
        "TAILWIND_CLI_SRC_REPO",
        "tailwindlabs/tailwindcss" if not use_daisy_ui else "dobicinaitis/tailwind-cli-extra",
    )
    if not repo_url:
        raise ValueError("TAILWIND_CLI_SRC_REPO must not be None.")

    if version_str == "latest":
        # Try to load from cache first
        cached = _load_cached_version(repo_url)
        if cached:
            return cached.version_str, cached.version

        # Fetch latest version from GitHub
        timeout = getattr(settings, "TAILWIND_CLI_REQUEST_TIMEOUT", 10)
        try:
            success, location = http.fetch_redirect_location(
                f"https://github.com/{repo_url}/releases/latest/", timeout=timeout
            )
            if success and location:
                version_str = location.rstrip("/").split("/")[-1].replace("v", "")
                # Cache the result
                _save_cached_version(repo_url, version_str)
                return version_str, Version.parse(version_str)
        except (http.RequestError, ValueError):
            # Network or parsing error, fall back to cached or default
            pass

        return FALLBACK_VERSION, Version.parse(FALLBACK_VERSION)
    elif repo_url == "tailwindlabs/tailwindcss":
        version = Version.parse(version_str)
        if version.major < 4:
            raise ValueError(
                "Tailwind CSS 3.x is not supported by this version. Use version 2.21.1 if you want to use Tailwind 3."
            )
        return version_str, version
    else:
        return version_str, Version.parse(version_str)


def _resolve_cli_path(platform_info: PlatformInfo, version_str: str, asset_name: str) -> Path:
    """Resolve the CLI executable path.

    Args:
        platform_info: Platform information.
        version_str: Version string.
        asset_name: Asset name for the CLI.

    Returns:
        Path: Resolved path to the CLI executable.
    """
    cli_path = getattr(settings, "TAILWIND_CLI_PATH", None)
    if not cli_path:
        cli_path = ".django_tailwind_cli"

    cli_path = Path(cli_path)
    if not cli_path.is_absolute():
        cli_path = Path(settings.BASE_DIR) / cli_path

    if cli_path.exists() and cli_path.is_file() and os.access(cli_path, os.X_OK):
        return cli_path.expanduser().resolve()
    else:
        return (
            cli_path.expanduser()
            / f"{asset_name}-{platform_info.system}-{platform_info.machine}-{version_str}{platform_info.extension}"
        )


def _get_staticfile_path() -> str:
    """Get the base path for static files from STATICFILES_DIRS.

    Returns:
        str: Path to the first staticfiles directory.
    """
    first_staticfile_dir: str | tuple[str, str] = settings.STATICFILES_DIRS[0]
    if isinstance(first_staticfile_dir, tuple):
        # Handle prefixed staticfile dir
        return first_staticfile_dir[1]
    return first_staticfile_dir


def _resolve_css_paths() -> tuple[list[CSSEntry], bool]:
    """Resolve CSS input and output paths.

    Supports two configuration modes:
    1. Multi-file mode: TAILWIND_CLI_CSS_MAP = [('admin.css', 'admin.output.css'), ...]
    2. Single-file mode: TAILWIND_CLI_SRC_CSS and TAILWIND_CLI_DIST_CSS

    Returns:
        tuple: (list of CSSEntry, overwrite_default_config flag)

    Raises:
        ValueError: If TAILWIND_CLI_DIST_CSS is None in single-file mode.
    """
    staticfile_path = _get_staticfile_path()

    # Check for multi-file configuration
    css_map_raw = getattr(settings, "TAILWIND_CLI_CSS_MAP", None)
    if css_map_raw:
        # Type assertion after validation in _validate_css_settings()
        css_map: list[tuple[str, str]] = css_map_raw  # pyright: ignore[reportAssignmentType]
        entries: list[CSSEntry] = []
        for src, dist in css_map:
            src_path = Path(src)
            if not src_path.is_absolute():
                src_path = Path(settings.BASE_DIR) / src_path

            dist_path = Path(staticfile_path) / dist

            # Derive name from source filename without extension
            name = Path(src).stem

            entries.append(
                CSSEntry(
                    name=name,
                    src_css=src_path,
                    dist_css=dist_path,
                    dist_css_base=str(dist),
                )
            )

        # Multi-file mode never overwrites default config
        return entries, False

    # Single-file mode (existing behavior)
    dist_css_base = getattr(settings, "TAILWIND_CLI_DIST_CSS", "css/tailwind.css")
    if not dist_css_base:
        raise ValueError(
            "TAILWIND_CLI_DIST_CSS must not be None. Either remove the setting or provide a valid CSS path."
        )

    dist_css = Path(staticfile_path) / dist_css_base

    # Resolve source CSS path
    src_css = getattr(settings, "TAILWIND_CLI_SRC_CSS", None)
    if not src_css:
        src_css = ".django_tailwind_cli/source.css"
        overwrite_default_config = True
    else:
        overwrite_default_config = False

    src_css = Path(src_css)
    if not src_css.is_absolute():
        src_css = Path(settings.BASE_DIR) / src_css

    # Create single entry with default name
    entry = CSSEntry(
        name="tailwind",
        src_css=src_css,
        dist_css=dist_css,
        dist_css_base=str(dist_css_base),
    )

    return [entry], overwrite_default_config


def _get_repository_settings(*, use_daisy_ui: bool) -> tuple[str, str]:
    """Get repository URL and asset name based on DaisyUI setting.

    Args:
        use_daisy_ui: Whether DaisyUI support is enabled.

    Returns:
        tuple: (repo_url, asset_name)

    Raises:
        ValueError: If TAILWIND_CLI_ASSET_NAME is None.
    """
    if use_daisy_ui:
        default_repo = "dobicinaitis/tailwind-cli-extra"
        default_asset = "tailwindcss-extra"
    else:
        default_repo = "tailwindlabs/tailwindcss"
        default_asset = "tailwindcss"

    repo_url = getattr(settings, "TAILWIND_CLI_SRC_REPO", default_repo)
    asset_name = getattr(settings, "TAILWIND_CLI_ASSET_NAME", default_asset)

    # Validate asset name
    if not asset_name:
        raise ValueError(
            "TAILWIND_CLI_ASSET_NAME must not be None. Either remove the setting or provide a valid asset name."
        )

    return repo_url, asset_name


def get_config() -> Config:
    """Get Tailwind CLI configuration.

    Returns:
        Config: Complete configuration object.

    Raises:
        ValueError: If required settings are missing or invalid.
    """
    # Validate required settings
    _validate_required_settings()

    # Get basic settings
    use_daisy_ui = getattr(settings, "TAILWIND_CLI_USE_DAISY_UI", False)
    automatic_download = getattr(settings, "TAILWIND_CLI_AUTOMATIC_DOWNLOAD", True)

    # Get platform information
    platform_info = get_platform_info()

    # Get version information
    version_str, version = get_version()

    # Get repository and asset settings
    repo_url, asset_name = _get_repository_settings(use_daisy_ui=use_daisy_ui)

    # Resolve paths
    cli_path = _resolve_cli_path(platform_info, version_str, asset_name)
    css_entries, overwrite_default_config = _resolve_css_paths()

    # Build download URL
    download_url = (
        f"https://github.com/{repo_url}/releases/download/v{version_str}/"
        f"{asset_name}-{platform_info.system}-{platform_info.machine}{platform_info.extension}"
    )

    return Config(
        version_str=version_str,
        version=version,
        cli_path=cli_path,
        download_url=download_url,
        css_entries=css_entries,
        overwrite_default_config=overwrite_default_config,
        automatic_download=automatic_download,
        use_daisy_ui=use_daisy_ui,
    )
