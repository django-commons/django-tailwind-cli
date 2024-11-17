import pytest

from django_tailwind_cli import conf, utils


@pytest.fixture(autouse=True)
def configure_settings(settings):
    settings.BASE_DIR = "/home/user/project"


def test_validate_settigns(settings):
    settings.STATICFILES_DIRS = []
    with pytest.raises(
        ValueError, match="STATICFILES_DIRS is empty. Please add a path to your static files."
    ):
        utils.validate_settings()


def test_get_full_config_file_path():
    assert "/home/user/project/tailwind.config.js" == str(utils.get_full_config_file_path())


def test_get_full_dist_css_path_without_staticfiles_dir_set(settings):
    settings.STATICFILES_DIRS = None
    with pytest.raises(
        ValueError, match="STATICFILES_DIRS is empty. Please add a path to your static files."
    ):
        utils.get_full_dist_css_path()


def test_get_full_dist_css_path_with_staticfiles_dir_set(settings):
    settings.STATICFILES_DIRS = ["/home/user/project"]
    assert "/home/user/project/css/tailwind.css" == str(utils.get_full_dist_css_path())


def test_get_full_src_css_path():
    with pytest.raises(
        ValueError,
        match="No source CSS file specified. Please set TAILWIND_SRC_CSS in your settings.",
    ):
        utils.get_full_src_css_path()


def test_get_full_src_css_path_with_changed_tailwind_cli_src_css(settings):
    settings.TAILWIND_CLI_SRC_CSS = "css/source.css"
    assert "/home/user/project/css/source.css" == str(utils.get_full_src_css_path())


def test_get_system_and_machine(mocker):
    platform_system = mocker.patch("platform.system")

    platform_system.return_value = "Windows"
    [system, _] = utils.get_system_and_machine()
    assert system == "windows"

    platform_system.return_value = "Darwin"
    [system, _] = utils.get_system_and_machine()
    assert system == "macos"

    platform_machine = mocker.patch("platform.machine")

    platform_machine.return_value = "x86_64"
    [_, machine] = utils.get_system_and_machine()
    assert machine == "x64"

    platform_machine.return_value = "amd64"
    [_, machine] = utils.get_system_and_machine()
    assert machine == "x64"

    platform_machine.return_value = "aarch64"
    [_, machine] = utils.get_system_and_machine()
    assert machine == "arm64"


@pytest.mark.parametrize(
    "platform,machine,result",
    [
        ("Windows", "x86_64", "tailwindcss-windows-x64.exe"),
        ("Windows", "amd64", "tailwindcss-windows-x64.exe"),
        ("Darwin", "aarch64", "tailwindcss-macos-arm64"),
        ("Darwin", "arm64", "tailwindcss-macos-arm64"),
    ],
)
def test_get_download_url(mocker, platform, machine, result):
    platform_system = mocker.patch("platform.system")
    platform_machine = mocker.patch("platform.machine")

    platform_system.return_value = platform
    platform_machine.return_value = machine
    assert utils.get_download_url().endswith(result)


@pytest.mark.parametrize(
    "platform,machine,result",
    [
        ("Windows", "x86_64", f"tailwindcss-windows-x64-{conf.DEFAULT_VERSION}.exe"),
        ("Windows", "amd64", f"tailwindcss-windows-x64-{conf.DEFAULT_VERSION}.exe"),
        ("Darwin", "aarch64", f"tailwindcss-macos-arm64-{conf.DEFAULT_VERSION}"),
        ("Darwin", "arm64", f"tailwindcss-macos-arm64-{conf.DEFAULT_VERSION}"),
    ],
)
def test_get_full_cli_path(mocker, platform, machine, result):
    assert "/.local/bin/tailwindcss-" in str(utils.get_full_cli_path())

    platform_system = mocker.patch("platform.system")
    platform_machine = mocker.patch("platform.machine")

    platform_system.return_value = platform
    platform_machine.return_value = machine
    assert str(utils.get_full_cli_path()).endswith(result)


def test_get_full_cli_path_with_existing_executable(tmp_path, settings):
    settings.TAILWIND_CLI_PATH = tmp_path / "tailwindcss.exe"
    settings.TAILWIND_CLI_PATH.touch(mode=0o755, exist_ok=True)
    assert utils.get_full_cli_path() == tmp_path / "tailwindcss.exe"


def test_get_full_cli_path_with_changed_tailwind_cli_path(settings):
    settings.TAILWIND_CLI_PATH = "/opt/bin"
    assert "/opt/bin/tailwindcss-" in str(utils.get_full_cli_path())
