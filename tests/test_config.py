from pathlib import Path

import pytest
from django.conf import LazySettings
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from django_tailwind_cli.config import get_config, get_version


@pytest.fixture(autouse=True)
def configure_settings(
    settings: LazySettings,
    mocker: MockerFixture,
):
    settings.BASE_DIR = Path("/home/user/project")
    settings.STATICFILES_DIRS = (settings.BASE_DIR / "assets",)
    request_get = mocker.patch("requests.get")
    request_get.return_value.headers = {"location": "https://github.com/tailwindlabs/tailwindcss/releases/tag/v4.0.10"}


@pytest.mark.parametrize(
    "version_str, version",
    [
        ("4.0.0", (4, 0, 0)),
        ("3.4.17", (3, 4, 17)),
    ],
)
def test_get_version(settings: SettingsWrapper, version_str: str, version: tuple[int, int, int]):
    settings.TAILWIND_CLI_VERSION = version_str
    r_version_str, r_version = get_version()
    assert r_version_str == version_str
    assert r_version.major == version[0]
    assert r_version.minor == version[1]
    assert r_version.patch == version[2]


def test_get_version_latest(settings: SettingsWrapper):
    r_version_str, r_version = get_version()
    assert r_version_str == "4.0.10"
    assert r_version.major == 4
    assert r_version.minor == 0
    assert r_version.patch == 10


def test_get_version_latest_without_proper_http_response(mocker: MockerFixture):
    request_get = mocker.patch("requests.get")
    request_get.return_value.ok = False

    r_version_str, r_version = get_version()
    assert r_version_str == "4.0.6"
    assert r_version.major == 4
    assert r_version.minor == 0
    assert r_version.patch == 6


def test_get_version_latest_without_redirect(mocker: MockerFixture):
    request_get = mocker.patch("requests.get")
    request_get.return_value.headers = {}

    r_version_str, r_version = get_version()
    assert r_version_str == "4.0.6"
    assert r_version.major == 4
    assert r_version.minor == 0
    assert r_version.patch == 6


def test_default_config():
    c = get_config()
    assert c.version.major >= 4
    assert ".local/bin/tailwindcss" in str(c.cli_path)
    assert c.version_str in str(c.cli_path)
    assert c.download_url.startswith(
        f"https://github.com/tailwindlabs/tailwindcss/releases/download/v{c.version_str}/tailwindcss-"
    )
    assert str(c.dist_css) == "/home/user/project/assets/css/tailwind.css"
    assert c.src_css is not None
    assert str(c.src_css) == "/home/user/project/assets/css/source.css"
    assert c.config_file is None


def test_default_config_for_tailwind_css_3_x(settings: LazySettings):
    settings.TAILWIND_CLI_VERSION = "3.4.13"
    c = get_config()
    assert c.version.major == 3
    assert ".local/bin/tailwindcss" in str(c.cli_path)
    assert c.version_str in str(c.cli_path)
    assert c.download_url.startswith(
        f"https://github.com/tailwindlabs/tailwindcss/releases/download/v{c.version_str}/tailwindcss-"
    )
    assert str(c.dist_css) == "/home/user/project/assets/css/tailwind.css"
    assert c.src_css is None
    assert c.config_file is not None
    assert str(c.config_file) == "/home/user/project/tailwind.config.js"


def test_set_tailwind_cli_src_css_for_tailwind_css_3_x(settings: LazySettings):
    settings.TAILWIND_CLI_VERSION = "3.4.13"
    settings.TAILWIND_CLI_SRC_CSS = "assets/css/source.css"
    c = get_config()
    assert c.src_css is not None


def test_invalid_settings_for_staticfiles_dirs(settings: LazySettings):
    settings.STATICFILES_DIRS = []
    with pytest.raises(ValueError, match="STATICFILES_DIRS is empty. Please add a path to your static files."):
        get_config()

    settings.STATICFILES_DIRS = None
    with pytest.raises(ValueError, match="STATICFILES_DIRS is empty. Please add a path to your static files."):
        get_config()


def test_invalid_settings_for_tailwind_cli_dist_css(settings: LazySettings):
    settings.TAILWIND_CLI_DIST_CSS = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_DIST_CSS must not be None."):
        get_config()


def test_invalid_settings_for_tailwind_cli_assert_name(settings: LazySettings):
    settings.TAILWIND_CLI_ASSET_NAME = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_ASSET_NAME must not be None."):
        get_config()


def test_invalid_settings_for_tailwind_cli_src_repo(settings: LazySettings):
    settings.TAILWIND_CLI_SRC_REPO = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_SRC_REPO must not be None."):
        get_config()


def test_invalid_settings_for_tailwind_cli_src_css(settings: LazySettings):
    settings.TAILWIND_CLI_SRC_CSS = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_SRC_CSS must not be None."):
        get_config()


def test_invalid_settings_for_tailwind_cli_config_file(settings: LazySettings):
    settings.TAILWIND_CLI_VERSION = "3.4.17"
    settings.TAILWIND_CLI_CONFIG_FILE = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_CONFIG_FILE must not be None."):
        get_config()

    settings.TAILWIND_CLI_VERSION = "4.0.0"
    settings.TAILWIND_CLI_CONFIG_FILE = "tailwind.config.js"
    with pytest.raises(
        ValueError, match="TAILWIND_CLI_CONFIG_FILE is not used by this library with Tailwind CSS >= 4.x."
    ):
        get_config()


@pytest.mark.parametrize(
    "platform,machine,result",
    [
        ("Windows", "x86_64", "tailwindcss-windows-x64.exe"),
        ("Windows", "amd64", "tailwindcss-windows-x64.exe"),
        ("Darwin", "aarch64", "tailwindcss-macos-arm64"),
        ("Darwin", "arm64", "tailwindcss-macos-arm64"),
    ],
)
def test_download_url(mocker: MockerFixture, platform: str, machine: str, result: str):
    platform_system = mocker.patch("platform.system")
    platform_system.return_value = platform

    platform_machine = mocker.patch("platform.machine")
    platform_machine.return_value = machine

    c = get_config()
    assert c.download_url.endswith(result)


@pytest.mark.parametrize(
    "platform,machine,result",
    [
        ("Windows", "x86_64", "tailwindcss-windows-x64-4.0.0.exe"),
        ("Windows", "amd64", "tailwindcss-windows-x64-4.0.0.exe"),
        ("Darwin", "aarch64", "tailwindcss-macos-arm64-4.0.0"),
        ("Darwin", "arm64", "tailwindcss-macos-arm64-4.0.0"),
    ],
)
def test_get_cli_path(settings: LazySettings, mocker: MockerFixture, platform: str, machine: str, result: str):
    settings.TAILWIND_CLI_VERSION = "4.0.0"

    platform_system = mocker.patch("platform.system")
    platform_system.return_value = platform

    platform_machine = mocker.patch("platform.machine")
    platform_machine.return_value = machine

    c = get_config()
    assert str(c.cli_path).endswith(result)


def test_cli_path_to_existing_file(settings: LazySettings, tmp_path: Path):
    settings.TAILWIND_CLI_PATH = tmp_path / "tailwindcss"
    settings.TAILWIND_CLI_PATH.touch(mode=0o755, exist_ok=True)
    c = get_config()
    assert str(c.cli_path) == str(tmp_path / "tailwindcss")


def test_cli_path_to_existing_directory(settings: LazySettings):
    settings.TAILWIND_CLI_PATH = "/opt/bin"
    c = get_config()
    assert "/opt/bin/tailwindcss-" in str(c.cli_path)


@pytest.mark.parametrize(
    "system, result",
    [
        ("Windows", "windows"),
        ("Darwin", "macos"),
        ("Linux", "linux"),
    ],
)
def test_system(system: str, result: str, mocker: MockerFixture):
    platform_system = mocker.patch("platform.system")
    platform_system.return_value = system

    c = get_config()
    assert result in str(c.cli_path)
    assert result in c.download_url


@pytest.mark.parametrize(
    "machine, result",
    [
        ("x86_64", "x64"),
        ("amd64", "x64"),
        ("aarch64", "arm64"),
    ],
)
def test_machine(machine: str, result: str, mocker: MockerFixture):
    platform_machine = mocker.patch("platform.machine")
    platform_machine.return_value = machine

    c = get_config()
    assert result in str(c.cli_path)
    assert result in c.download_url


def test_build_cmd():
    c = get_config()
    assert c.build_cmd == [
        str(c.cli_path),
        "--output",
        str(c.dist_css),
        "--minify",
        "--input",
        str(c.src_css),
    ]


def test_build_cmd_for_tailwind_css_3_x(settings: LazySettings):
    settings.TAILWIND_CLI_VERSION = "3.4.13"
    c = get_config()
    assert c.build_cmd == [
        str(c.cli_path),
        "--output",
        str(c.dist_css),
        "--minify",
        "--config",
        str(c.config_file),
    ]


def test_watch_cmd():
    c = get_config()
    assert c.watch_cmd == [
        str(c.cli_path),
        "--output",
        str(c.dist_css),
        "--watch",
        "--input",
        str(c.src_css),
    ]


def test_watch_cmd_for_tailwind_css_3_x(settings: LazySettings):
    settings.TAILWIND_CLI_VERSION = "3.4.13"
    c = get_config()
    assert c.watch_cmd == [
        str(c.cli_path),
        "--output",
        str(c.dist_css),
        "--watch",
    ]
