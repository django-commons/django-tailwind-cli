import sys

import pytest
from django.core.management import CommandError, call_command

from django_tailwind_cli import utils
from django_tailwind_cli.management.commands.tailwind import (
    DEFAULT_TAILWIND_CONFIG,
    _get_runserver_options,
)


@pytest.fixture(autouse=True)
def configure_settings(mocker):
    mocker.resetall()
    mocker.patch("multiprocessing.Process.start")
    mocker.patch("multiprocessing.Process.join")
    mocker.patch("subprocess.run")
    request_get = mocker.patch("requests.get")
    request_get.return_value.content = b""


def test_calling_unknown_subcommand():
    with pytest.raises(CommandError, match="No such command 'not_a_valid_command'"):
        call_command("tailwind", "not_a_valid_command")


def test_invalid_configuration(settings):
    settings.STATICFILES_DIRS = None
    with pytest.raises(CommandError, match="Configuration error"):
        call_command("tailwind", "build")

    settings.STATICFILES_DIRS = []
    with pytest.raises(CommandError, match="Configuration error"):
        call_command("tailwind", "build")


def test_download_cli(settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    assert not utils.get_full_cli_path().exists()
    call_command("tailwind", "download_cli")
    assert utils.get_full_cli_path().exists()


def test_download_cli_without_tailwind_cli_path(settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = None
    assert not utils.get_full_cli_path().exists()
    call_command("tailwind", "download_cli")
    assert utils.get_full_cli_path().exists()


def test_automatic_download_enabled(settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True
    assert not utils.get_full_cli_path().exists()
    call_command("tailwind", "build")
    assert utils.get_full_cli_path().exists()


def test_automatic_download_disabled(settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
    assert not utils.get_full_cli_path().exists()
    with pytest.raises(
        CommandError, match="Automatic download of Tailwind CSS CLI is deactivated."
    ):
        call_command("tailwind", "build")
    with pytest.raises(
        CommandError, match="Automatic download of Tailwind CSS CLI is deactivated."
    ):
        call_command("tailwind", "watch")
    assert not utils.get_full_cli_path().exists()


def test_manual_download_and_build(settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
    call_command("tailwind", "download_cli")
    call_command("tailwind", "build")


def test_download_from_another_repo(settings, tmp_path, capsys):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
    settings.TAILWIND_CLI_SRC_REPO = "oliverandrich/mytailwind"
    call_command("tailwind", "download_cli")
    captured = capsys.readouterr()
    assert "from 'oliverandrich/mytailwind'" in captured.out


def test_remove_cli_with_existing_cli(settings, tmp_path, capsys):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True
    call_command("tailwind", "download_cli")
    assert utils.get_full_cli_path().exists()
    call_command("tailwind", "remove_cli")
    assert not utils.get_full_cli_path().exists()
    captured = capsys.readouterr()
    assert "Removed Tailwind CSS CLI at " in captured.out


def test_remove_cli_without_existing_cli(settings, tmp_path, capsys):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True
    call_command("tailwind", "remove_cli")
    captured = capsys.readouterr()
    assert "Tailwind CSS CLI not found at " in captured.out


def test_create_tailwind_config_if_non_exists(settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    assert not utils.get_full_config_file_path().exists()
    call_command("tailwind", "build")
    assert utils.get_full_cli_path().exists()
    assert DEFAULT_TAILWIND_CONFIG == utils.get_full_config_file_path().read_text()


def test_with_existing_tailwind_config(settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    utils.get_full_config_file_path().write_text("module.exports = {}")
    call_command("tailwind", "build")
    assert utils.get_full_config_file_path().exists()
    assert "module.exports = {}" == utils.get_full_config_file_path().read_text()
    assert DEFAULT_TAILWIND_CONFIG != utils.get_full_config_file_path().read_text()


def test_build_subprocess_run_called(settings, tmp_path, mocker):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "build")
    assert 1 <= subprocess_run.call_count <= 2


def test_build_output_of_first_run(settings, tmp_path, capsys):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    call_command("tailwind", "build")
    captured = capsys.readouterr()
    assert "Tailwind CSS CLI not found." in captured.out
    assert "Tailwind CSS CLI already exists at" not in captured.out
    assert "Downloading Tailwind CSS CLI from " in captured.out
    assert "Built production stylesheet" in captured.out


def test_build_output_of_second_run(settings, tmp_path, capsys):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
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
def test_build_keyboard_interrupt(settings, tmp_path, mocker, capsys):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    subprocess_run = mocker.patch("subprocess.run")
    subprocess_run.side_effect = KeyboardInterrupt
    call_command("tailwind", "build")
    captured = capsys.readouterr()
    assert "Canceled building production stylesheet." in captured.out


def test_build_without_input_file(settings, tmp_path, mocker):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "build")
    name, args, kwargs = subprocess_run.mock_calls[0]
    assert "--input" not in args[0]


def test_build_with_input_file(settings, tmp_path, mocker):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    settings.TAILWIND_CLI_SRC_CSS = "css/source.css"
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "build")
    name, args, kwargs = subprocess_run.mock_calls[0]
    assert "--input" in args[0]


def test_watch_subprocess_run_called(settings, tmp_path, mocker):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "watch")
    assert 1 <= subprocess_run.call_count <= 2


def test_watch_output_of_first_run(settings, tmp_path, capsys):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    call_command("tailwind", "watch")
    captured = capsys.readouterr()
    assert "Tailwind CSS CLI not found." in captured.out
    assert "Downloading Tailwind CSS CLI from " in captured.out


def test_watch_output_of_second_run(settings, tmp_path, capsys):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
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
def test_watch_keyboard_interrupt(settings, tmp_path, mocker, capsys):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    subprocess_run = mocker.patch("subprocess.run")
    subprocess_run.side_effect = KeyboardInterrupt
    call_command("tailwind", "watch")
    captured = capsys.readouterr()
    assert "Stopped watching for changes." in captured.out


def test_watch_without_input_file(settings, tmp_path, mocker):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "watch")
    name, args, kwargs = subprocess_run.mock_calls[0]
    assert "--input" not in args[0]


def test_watch_with_input_file(settings, tmp_path, mocker):
    settings.BASE_DIR = tmp_path
    settings.TAILWIND_CLI_PATH = str(tmp_path)
    settings.TAILWIND_CLI_SRC_CSS = "css/source.css"
    subprocess_run = mocker.patch("subprocess.run")
    call_command("tailwind", "watch")
    name, args, kwargs = subprocess_run.mock_calls[0]
    assert "--input" in args[0]


def test_runserver():
    call_command("tailwind", "runserver")


def test_runserver_plus_with_django_extensions_installed():
    call_command("tailwind", "runserver_plus")


def test_runserver_plus_without_django_extensions_installed(mocker):
    mocker.patch.dict(sys.modules, {"django_extensions": None, "werkzeug": None})
    with pytest.raises(CommandError, match="Missing dependencies."):
        call_command("tailwind", "runserver_plus")


def test_get_runserver_options():
    assert _get_runserver_options(use_ipv6=True) == ["--ipv6"]
    assert _get_runserver_options(no_threading=True) == ["--nothreading"]
    assert _get_runserver_options(no_static=True) == ["--nostatic"]
    assert _get_runserver_options(no_reloader=True) == ["--noreload"]
    assert _get_runserver_options(skip_checks=True) == ["--skip-checks"]
    assert _get_runserver_options(pdb=True) == ["--pdb"]
    assert _get_runserver_options(ipdb=True) == ["--ipdb"]
    assert _get_runserver_options(pm=True) == ["--pm"]
    assert _get_runserver_options(print_sql=True) == ["--print-sql"]
    assert _get_runserver_options(print_sql_location=True) == ["--print-sql-location"]
    assert _get_runserver_options(cert_file="somefile") == ["--cert-file=somefile"]
    assert _get_runserver_options(key_file="somefile") == ["--key-file=somefile"]
    assert _get_runserver_options(addrport="0.0.0.0:9000") == ["0.0.0.0:9000"]


def test_list_project_templates(capsys):
    call_command("tailwind", "list_templates")
    captured = capsys.readouterr()
    assert "templates/tailwind_cli/base.html" in captured.out
    assert "templates/tailwind_cli/tailwind_css.html" in captured.out
    assert "templates/tests/base.html" in captured.out
    assert "templates/admin" not in captured.out


def test_list_projecttest_list_project_all_templates_templates(capsys, settings):
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
