from pathlib import Path

import pytest
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from django_tailwind_cli.config import get_config, get_version


@pytest.fixture(autouse=True)
def configure_settings(
    settings: SettingsWrapper,
    mocker: MockerFixture,
):
    settings.BASE_DIR = Path("/home/user/project")
    settings.STATICFILES_DIRS = (settings.BASE_DIR / "assets",)
    request_get = mocker.patch("requests.get")
    request_get.return_value.headers = {"location": "https://github.com/tailwindlabs/tailwindcss/releases/tag/v4.1.3"}


@pytest.mark.parametrize(
    "version_str, expected_version_str, version",
    [
        ("4.0.0", "4.0.0", (4, 0, 0)),
        ("latest", "4.1.3", (4, 1, 3)),
    ],
)
def test_get_version(
    settings: SettingsWrapper, version_str: str, expected_version_str: str, version: tuple[int, int, int]
):
    settings.TAILWIND_CLI_VERSION = version_str
    r_version_str, r_version = get_version()
    assert r_version_str == expected_version_str
    assert r_version.major == version[0]
    assert r_version.minor == version[1]
    assert r_version.patch == version[2]


def test_get_version_latest_without_proper_http_response(mocker: MockerFixture):
    request_get = mocker.patch("requests.get")
    request_get.return_value.ok = False

    r_version_str, r_version = get_version()
    assert r_version_str == "4.1.3"
    assert r_version.major == 4
    assert r_version.minor == 1
    assert r_version.patch == 3


def test_get_version_latest_without_redirect(mocker: MockerFixture):
    request_get = mocker.patch("requests.get")
    request_get.return_value.headers = {}

    r_version_str, r_version = get_version()
    assert r_version_str == "4.1.3"
    assert r_version.major == 4
    assert r_version.minor == 1
    assert r_version.patch == 3


def test_get_version_with_official_repo_and_version_3(settings: SettingsWrapper):
    settings.TAILWIND_CLI_VERSION = "3.4.13"
    with pytest.raises(ValueError, match="Tailwind CSS 3.x is not supported by this version."):
        get_version()


def test_get_version_with_unofficial_repo_and_version_3(settings: SettingsWrapper):
    settings.TAILWIND_CLI_VERSION = "3.4.13"
    settings.TAILWIND_CLI_SRC_REPO = "oliverandrich/my-tailwindcss-cli"

    r_version_str, r_version = get_version()
    assert r_version_str == "3.4.13"
    assert r_version.major == 3
    assert r_version.minor == 4
    assert r_version.patch == 13


def test_default_config():
    c = get_config()
    assert c.version.major >= 4
    assert "django-tailwind-cli/tailwindcss" in str(c.cli_path)
    assert c.version_str in str(c.cli_path)
    assert c.download_url.startswith(
        f"https://github.com/tailwindlabs/tailwindcss/releases/download/v{c.version_str}/tailwindcss-"
    )
    assert str(c.dist_css) == "/home/user/project/assets/css/tailwind.css"
    assert c.src_css is not None
    assert str(c.src_css).endswith("django-tailwind-cli/source.css")


def test_invalid_settings_for_staticfiles_dirs(settings: SettingsWrapper):
    settings.STATICFILES_DIRS = []
    with pytest.raises(ValueError, match="STATICFILES_DIRS is empty. Please add a path to your static files."):
        get_config()

    settings.STATICFILES_DIRS = None
    with pytest.raises(ValueError, match="STATICFILES_DIRS is empty. Please add a path to your static files."):
        get_config()


def test_invalid_settings_for_tailwind_cli_dist_css(settings: SettingsWrapper):
    settings.TAILWIND_CLI_DIST_CSS = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_DIST_CSS must not be None."):
        get_config()


def test_invalid_settings_for_tailwind_cli_assert_name(settings: SettingsWrapper):
    settings.TAILWIND_CLI_ASSET_NAME = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_ASSET_NAME must not be None."):
        get_config()


def test_invalid_settings_for_tailwind_cli_src_repo(settings: SettingsWrapper):
    settings.TAILWIND_CLI_SRC_REPO = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_SRC_REPO must not be None."):
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
def test_get_cli_path(settings: SettingsWrapper, mocker: MockerFixture, platform: str, machine: str, result: str):
    settings.TAILWIND_CLI_VERSION = "4.0.0"

    platform_system = mocker.patch("platform.system")
    platform_system.return_value = platform

    platform_machine = mocker.patch("platform.machine")
    platform_machine.return_value = machine

    c = get_config()
    assert str(c.cli_path).endswith(result)


def test_cli_path_to_existing_file(settings: SettingsWrapper, tmp_path: Path):
    settings.TAILWIND_CLI_PATH = tmp_path / "tailwindcss"
    settings.TAILWIND_CLI_PATH.touch(mode=0o755, exist_ok=True)
    c = get_config()
    assert str(c.cli_path) == str(tmp_path / "tailwindcss")


def test_cli_path_to_existing_directory(settings: SettingsWrapper):
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
        "--input",
        str(c.src_css),
        "--output",
        str(c.dist_css),
        "--minify",
    ]


def test_watch_cmd():
    c = get_config()
    assert c.watch_cmd == [
        str(c.cli_path),
        "--input",
        str(c.src_css),
        "--output",
        str(c.dist_css),
        "--watch",
    ]
