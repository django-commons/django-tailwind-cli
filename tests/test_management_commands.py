import sys
from pathlib import Path

import pytest
from django.conf import LazySettings
from django.core.management import CommandError, call_command
from pytest import CaptureFixture
from pytest_mock import MockerFixture

from django_tailwind_cli.config import get_config
from django_tailwind_cli.management.commands.tailwind import DEFAULT_SOURCE_CSS, DEFAULT_TAILWIND_CONFIG


@pytest.fixture(autouse=True, params=["4.0.0", "3.4.17"])
def configure_settings(request: pytest.FixtureRequest, mocker: MockerFixture, settings: LazySettings, tmp_path: Path):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = tmp_path
    settings.TAILWIND_CLI_VERSION = request.param
    settings.STATICFILES_DIRS = (settings.BASE_DIR / "assets",)

    mocker.resetall()
    mocker.patch("multiprocessing.Process.start")
    mocker.patch("multiprocessing.Process.join")
    mocker.patch("subprocess.run")
    request_get = mocker.patch("requests.get")
    request_get.return_value.content = b""


def test_calling_unknown_subcommand():
    with pytest.raises(CommandError, match="No such command 'not_a_valid_command'"):
        call_command("tailwind", "not_a_valid_command")


def test_create_tailwind_config_if_non_exists(settings: LazySettings, tmp_path: Path):
    if settings.TAILWIND_CLI_VERSION == "4.0.0":
        pytest.skip("Tailwind CSS CLI 4.0.0 does not use a tailwind.config.js file.")
    c = get_config()
    assert c.config_file is not None
    assert not c.config_file.exists()
    call_command("tailwind", "build")
    assert c.config_file.exists()
    assert DEFAULT_TAILWIND_CONFIG == c.config_file.read_text()


def test_with_existing_tailwind_config(settings: LazySettings, tmp_path: Path):
    if settings.TAILWIND_CLI_VERSION == "4.0.0":
        pytest.skip("Tailwind CSS CLI 4.0.0 does not use a tailwind.config.js file.")
    c = get_config()
    assert c.config_file is not None
    c.config_file.write_text("module.exports = {}")
    call_command("tailwind", "build")
    assert c.config_file.exists()
    assert "module.exports = {}" == c.config_file.read_text()
    assert DEFAULT_TAILWIND_CONFIG != c.config_file.read_text()


def test_create_src_css_if_non_exists(settings: LazySettings, tmp_path: Path):
    if settings.TAILWIND_CLI_VERSION == "3.4.17":
        pytest.skip("With Tailwind CSS CLI 3.4.17 a src css file is optional. But with 4.0.0 it is required.")
    c = get_config()
    assert c.src_css is not None
    assert not c.src_css.exists()
    call_command("tailwind", "build")
    assert c.src_css.exists()
    assert DEFAULT_SOURCE_CSS == c.src_css.read_text()


def test_with_existing_src_css(settings: LazySettings, tmp_path: Path):
    if settings.TAILWIND_CLI_VERSION == "3.4.17":
        pytest.skip("With Tailwind CSS CLI 3.4.17 a src css file is optional. But with 4.0.0 it is required.")
    c = get_config()
    assert c.src_css is not None
    c.src_css.parent.mkdir(parents=True, exist_ok=True)
    c.src_css.write_text('@import "tailwindcss";\n@theme {};\n')
    call_command("tailwind", "build")
    assert c.src_css.exists()
    assert '@import "tailwindcss";\n@theme {};\n' == c.src_css.read_text()
    assert DEFAULT_SOURCE_CSS != c.src_css.read_text()


def test_download_cli():
    c = get_config()
    assert not c.cli_path.exists()
    call_command("tailwind", "download_cli")
    assert c.cli_path.exists()


def test_download_cli_without_tailwind_cli_path(settings: LazySettings):
    settings.TAILWIND_CLI_PATH = None
    c = get_config()
    assert not c.cli_path.exists()
    call_command("tailwind", "download_cli")
    assert c.cli_path.exists()


def test_automatic_download_enabled():
    c = get_config()
    assert not c.cli_path.exists()
    call_command("tailwind", "build")
    assert c.cli_path.exists()


def test_automatic_download_disabled(settings: LazySettings):
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
    c = get_config()
    assert not c.cli_path.exists()
    with pytest.raises(CommandError, match="Automatic download of Tailwind CSS CLI is deactivated."):
        call_command("tailwind", "build")
    with pytest.raises(CommandError, match="Automatic download of Tailwind CSS CLI is deactivated."):
        call_command("tailwind", "watch")
    assert not c.cli_path.exists()


def test_manual_download_and_build(settings: LazySettings):
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
    call_command("tailwind", "download_cli")
    call_command("tailwind", "build")


def test_download_from_another_repo(settings: LazySettings, capsys: CaptureFixture[str]):
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
    settings.TAILWIND_CLI_SRC_REPO = "oliverandrich/mytailwind"
    call_command("tailwind", "download_cli")
    captured = capsys.readouterr()
    assert "oliverandrich/mytailwind" in captured.out


def test_remove_cli_with_existing_cli(settings: LazySettings, capsys: CaptureFixture[str]):
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True
    c = get_config()
    call_command("tailwind", "download_cli")
    assert c.cli_path.exists()
    call_command("tailwind", "remove_cli")
    assert not c.cli_path.exists()
    captured = capsys.readouterr()
    assert "Removed Tailwind CSS CLI at " in captured.out


def test_remove_cli_without_existing_cli(settings: LazySettings, capsys: CaptureFixture[str]):
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True
    call_command("tailwind", "remove_cli")
    captured = capsys.readouterr()
    assert "Tailwind CSS CLI not found at " in captured.out


def test_build_subprocess_run_called(mocker: MockerFixture):
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "build")
    assert 1 <= subprocess_run.call_count <= 2


def test_build_output_of_first_run(capsys: CaptureFixture[str]):
    call_command("tailwind", "build")
    captured = capsys.readouterr()
    assert "Tailwind CSS CLI not found." in captured.out
    assert "Tailwind CSS CLI already exists at" not in captured.out
    assert "Downloading Tailwind CSS CLI from " in captured.out
    assert "Built production stylesheet" in captured.out


def test_build_output_of_second_run(capsys: CaptureFixture[str]):
    call_command("tailwind", "build")
    capsys.readouterr()
    call_command("tailwind", "build")
    captured = capsys.readouterr()
    assert "Tailwind CSS CLI not found." not in captured.out
    assert "Tailwind CSS CLI already exists at" in captured.out
    assert "Downloading Tailwind CSS CLI from " not in captured.out
    assert "Built production stylesheet" in captured.out


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="The capturing of KeyboardInterupt fails with pytest every other time.",
)
def test_build_keyboard_interrupt(capsys: CaptureFixture[str], mocker: MockerFixture):
    subprocess_run = mocker.patch("subprocess.run")
    subprocess_run.side_effect = KeyboardInterrupt
    call_command("tailwind", "build")
    captured = capsys.readouterr()
    assert "Canceled building production stylesheet." in captured.out


def test_build_without_input_file(mocker: MockerFixture, settings: LazySettings):
    if settings.TAILWIND_CLI_VERSION == "4.0.0":
        pytest.skip("Tailwind CSS CLI 4.0.0 does not work without a source file.")
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "build")
    _name, args, _kwargs = subprocess_run.mock_calls[0]
    assert "--input" not in args[0]


def test_build_with_input_file(settings: LazySettings, tmp_path: Path, mocker: MockerFixture):
    settings.TAILWIND_CLI_SRC_CSS = "css/source.css"
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "build")
    _name, args, _kwargs = subprocess_run.mock_calls[0]
    assert "--input" in args[0]


def test_watch_subprocess_run_called(mocker: MockerFixture):
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "watch")
    assert 1 <= subprocess_run.call_count <= 2


def test_watch_output_of_first_run(capsys: CaptureFixture[str]):
    call_command("tailwind", "watch")
    captured = capsys.readouterr()
    assert "Tailwind CSS CLI not found." in captured.out
    assert "Downloading Tailwind CSS CLI from " in captured.out


def test_watch_output_of_second_run(capsys: CaptureFixture[str]):
    call_command("tailwind", "watch")
    capsys.readouterr()
    call_command("tailwind", "watch")
    captured = capsys.readouterr()
    assert "Tailwind CSS CLI not found." not in captured.out
    assert "Downloading Tailwind CSS CLI from " not in captured.out


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="The capturing of KeyboardInterupt fails with pytest every other time.",
)
def test_watch_keyboard_interrupt(capsys: CaptureFixture[str], mocker: MockerFixture):
    subprocess_run = mocker.patch("subprocess.run")
    subprocess_run.side_effect = KeyboardInterrupt
    call_command("tailwind", "watch")
    captured = capsys.readouterr()
    assert "Stopped watching for changes." in captured.out


def test_watch_without_input_file(settings: LazySettings, mocker: MockerFixture):
    if settings.TAILWIND_CLI_VERSION == "4.0.0":
        pytest.skip("Tailwind CSS CLI 4.0.0 does not work without a source file.")
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "watch")
    _name, args, _kwargs = subprocess_run.mock_calls[0]
    assert "--input" not in args[0]


def test_watch_with_input_file(settings: LazySettings, mocker: MockerFixture):
    settings.TAILWIND_CLI_SRC_CSS = "css/source.css"
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "watch")
    _name, args, _kwargs = subprocess_run.mock_calls[0]
    assert "--input" in args[0]


def test_list_project_templates(capsys: CaptureFixture[str]):
    call_command("tailwind", "list_templates")
    captured = capsys.readouterr()
    assert "templates/tailwind_cli/base.html" in captured.out
    assert "templates/tailwind_cli/tailwind_css.html" in captured.out
    assert "templates/tests/base.html" in captured.out
    assert "templates/admin" not in captured.out


def test_list_projecttest_list_project_all_templates_templates(capsys: CaptureFixture[str], settings: LazySettings):
    settings.INSTALLED_APPS = [
        "django.contrib.contenttypes",
        "django.contrib.messages",
        "django.contrib.auth",
        "django.contrib.admin",
        "django.contrib.staticfiles",
        "django_tailwind_cli",
    ]
    call_command("tailwind", "list_templates")
    captured = capsys.readouterr()
    assert "templates/tailwind_cli/base.html" in captured.out
    assert "templates/tailwind_cli/tailwind_css.html" in captured.out
    assert "templates/tests/base.html" in captured.out
    assert "templates/admin" in captured.out


def test_runserver():
    call_command("tailwind", "runserver")


def test_runserver_plus_without_django_extensions_installed(mocker: MockerFixture):
    mocker.patch.dict(sys.modules, {"django_extensions": None, "werkzeug": None})
    call_command("tailwind", "runserver")
