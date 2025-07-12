"""`tailwind` management command."""

import importlib.util
import os
import shutil
import subprocess
import sys
from multiprocessing import Process
from pathlib import Path
from typing import Optional, Union

import requests
import typer
from django.conf import settings
from django.core.management.base import CommandError
from django.template.utils import get_app_template_dirs
from django_typer.management import Typer

from django_tailwind_cli import conf, utils

app = Typer(name="tailwind", help="Create and manage a Tailwind CSS theme.")


@app.command()
def build() -> None:
    """Build a minified production ready CSS file."""
    _validate_config()
    _download_cli()
    _create_tailwind_config()

    try:
        subprocess.run(_get_build_cmd(minify=True), cwd=settings.BASE_DIR, check=True)
    except KeyboardInterrupt:
        typer.secho("Canceled building production stylesheet.", fg=typer.colors.RED)
    else:
        typer.secho(
            f"Built production stylesheet '{utils.get_full_dist_css_path()}'.",
            fg=typer.colors.GREEN,
        )


@app.command()
def watch():
    """Start Tailwind CLI in watch mode during development."""
    _validate_config()
    _download_cli()
    _create_tailwind_config()

    try:
        subprocess.run(_get_build_cmd(minify=False, watch=True), cwd=settings.BASE_DIR, check=True)
    except KeyboardInterrupt:
        typer.secho("Stopped watching for changes.", fg=typer.colors.RED)


@app.command(name="list_templates")
def list_templates():
    """List the templates of your django project."""
    _validate_config()

    template_files: list[str] = []

    def _list_template_files(td: Union[str, Path]) -> None:
        for d, _, filenames in os.walk(str(td)):
            for filename in filenames:
                if filename.endswith(".html") or filename.endswith(".txt"):
                    template_files.append(os.path.join(d, filename))

    app_template_dirs = get_app_template_dirs("templates")
    for app_template_dir in app_template_dirs:
        _list_template_files(app_template_dir)

    for template_dir in settings.TEMPLATES[0]["DIRS"]:
        _list_template_files(template_dir)

    typer.echo("\n".join(template_files))


@app.command(name="download_cli")
def download_cli():
    """Download the Tailwind CSS CLI."""
    _validate_config()
    _download_cli(force_download=True)


@app.command(name="remove_cli")
def remove_cli():
    """Remove the Tailwind CSS CLI."""
    _validate_config()
    if utils.get_full_cli_path().exists():
        utils.get_full_cli_path().unlink()
        typer.secho(
            f"Removed Tailwind CSS CLI at '{utils.get_full_cli_path()}'.", fg=typer.colors.GREEN
        )
    else:
        typer.secho(
            f"Tailwind CSS CLI not found at '{utils.get_full_cli_path()}'.", fg=typer.colors.RED
        )


@app.command()
def runserver(
    addrport: Optional[str] = typer.Argument(
        None,
        help="Optional port number, or ipaddr:port",
    ),
    *,
    use_ipv6: bool = typer.Option(
        False,
        "--ipv6",
        "-6",
        help="Tells Django to use an IPv6 address.",
    ),
    no_threading: bool = typer.Option(
        False,
        "--nothreading",
        help="Tells Django to NOT use threading.",
    ),
    no_static: bool = typer.Option(
        False,
        "--nostatic",
        help="Tells Django to NOT automatically serve static files at STATIC_URL.",
    ),
    no_reloader: bool = typer.Option(
        False,
        "--noreload",
        help="Tells Django to NOT use the auto-reloader.",
    ),
    skip_checks: bool = typer.Option(
        False,
        "--skip-checks",
        help="Skip system checks.",
    ),
):
    """Start the Django development server and the Tailwind CLI in watch mode."""
    _validate_config()
    _download_cli()
    _create_tailwind_config()
    _runserver(
        addrport=addrport,
        use_ipv6=use_ipv6,
        no_threading=no_threading,
        no_static=no_static,
        no_reloader=no_reloader,
        skip_checks=skip_checks,
    )


@app.command(name="runserver_plus")
def runserver_plus(
    addrport: Optional[str] = typer.Argument(
        None,
        help="Optional port number, or ipaddr:port",
    ),
    *,
    use_ipv6: bool = typer.Option(
        False,
        "--ipv6",
        "-6",
        help="Tells Django to use an IPv6 address.",
    ),
    no_threading: bool = typer.Option(
        False,
        "--nothreading",
        help="Tells Django to NOT use threading.",
    ),
    no_static: bool = typer.Option(
        False,
        "--nostatic",
        help="Tells Django to NOT automatically serve static files at STATIC_URL.",
    ),
    no_reloader: bool = typer.Option(
        False,
        "--noreload",
        help="Tells Django to NOT use the auto-reloader.",
    ),
    skip_checks: bool = typer.Option(
        False,
        "--skip-checks",
        help="Skip system checks.",
    ),
    pdb: bool = typer.Option(
        False,
        "--pdb",
        help="Drop into pdb shell at the start of any view.",
    ),
    ipdb: bool = typer.Option(
        False,
        "--ipdb",
        help="Drop into ipdb shell at the start of any view.",
    ),
    pm: bool = typer.Option(
        False,
        "--pm",
        help="Drop into (i)pdb shell if an exception is raised in a view.",
    ),
    print_sql: bool = typer.Option(
        False,
        "--print-sql",
        help="Print SQL queries as they're executed.",
    ),
    print_sql_location: bool = typer.Option(
        False,
        "--print-sql-location",
        help="Show location in code where SQL query generated from.",
    ),
    cert_file: Optional[str] = typer.Option(
        None,
        help=(
            "SSL .crt file path. If not provided path from --key-file will be selected. "
            "Either --cert-file or --key-file must be provided to use SSL."
        ),
    ),
    key_file: Optional[str] = typer.Option(
        None,
        help=(
            "SSL .key file path. If not provided path from --cert-file will be "
            "selected. Either --cert-file or --key-file must be provided to use SSL."
        ),
    ),
):
    """
    Start the django-extensions runserver_plus development server and the
    Tailwind CLI in watch mode.
    """
    _validate_config()
    _download_cli()
    _create_tailwind_config()
    _runserver(
        server_command="runserver_plus",
        addrport=addrport,
        use_ipv6=use_ipv6,
        no_threading=no_threading,
        no_static=no_static,
        no_reloader=no_reloader,
        skip_checks=skip_checks,
        pdb=pdb,
        ipdb=ipdb,
        pm=pm,
        print_sql=print_sql,
        print_sql_location=print_sql_location,
        cert_file=cert_file,
        key_file=key_file,
    )


@app.command(name="install_pycharm_workaround")
def install_pycharm_workaround():
    """
    Configures the workarounds for PyCharm to get tailwind plugin to work with the tailwind CLI.
    """
    _validate_config()
    _download_cli()

    package_json = settings.BASE_DIR / "package.json"
    package_json_content = '{"devDependencies": {"tailwindcss": "latest"}}'
    cli_js = settings.BASE_DIR / "node_modules" / "tailwindcss" / "lib" / "cli.js"

    if package_json.exists():
        if package_json.read_text() == package_json_content:
            typer.secho(
                f"PyCharm workaround is already installed at '{package_json}'.",
                fg=typer.colors.GREEN,
            )
            return
        else:
            typer.secho(
                f"Found an existing package.json at '{package_json}' that is " "not compatible.",
                fg=typer.colors.YELLOW,
            )
            return
    else:
        package_json.write_text(package_json_content)
        typer.secho(
            f"Created package.json at '{package_json}'",
            fg=typer.colors.GREEN,
        )

        cli_js.parent.mkdir(parents=True, exist_ok=True)
        cli_path = utils.get_full_cli_path()
        cli_js.symlink_to(cli_path)
        typer.secho(
            f"Created link at '{cli_js}' to '{cli_path}'.",
            fg=typer.colors.GREEN,
        )
        typer.secho(
            "\nAssure that you have added package.json and node_modules to your .gitignore file.",
            fg=typer.colors.YELLOW,
        )


@app.command(name="uninstall_pycharm_workaround")
def uninstall_pycharm_workaround():
    package_json = settings.BASE_DIR / "package.json"
    package_json_content = '{"devDependencies": {"tailwindcss": "latest"}}'
    node_modules = settings.BASE_DIR / "node_modules"

    if package_json.exists() and package_json.read_text() == package_json_content:
        package_json.unlink()
        shutil.rmtree(node_modules)
        typer.secho(
            "Removed package.json and cli.js.",
            fg=typer.colors.GREEN,
        )
    elif package_json.exists() and package_json.read_text() != package_json_content:
        typer.secho(
            f"Found an existing package.json at '{package_json}' was not installed by us.",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.secho(
            "No package.json or cli.js found.",
            fg=typer.colors.YELLOW,
        )


# UTILITY FUNCTIONS -------------------------------------------------------------------------------


def _validate_config():
    """Assert that the configuration is valid for using Tailwind CLI."""
    try:
        utils.validate_settings()
    except Exception as e:
        msg = "Configuration error"
        raise CommandError(msg) from e


def _download_cli(*, force_download: bool = False) -> None:
    """Assure that the CLI is loaded if automatic downloads are activated."""

    if not force_download and not conf.get_tailwind_cli_automatic_download():
        if not utils.get_full_cli_path().exists():
            raise CommandError(
                "Automatic download of Tailwind CSS CLI is deactivated. "
                "Please download the Tailwind CSS CLI manually."
            )
        return

    dest_file = utils.get_full_cli_path()

    extra_msg = ""
    if conf.get_tailwind_cli_src_repo() != conf.DEFAULT_SRC_REPO:
        extra_msg = f" from '{conf.get_tailwind_cli_src_repo()}'"

    if dest_file.exists():
        typer.secho(
            f"Tailwind CSS CLI already exists at '{dest_file}'{extra_msg}",
            fg=typer.colors.GREEN,
        )
        return

    download_url = utils.get_download_url()
    typer.secho("Tailwind CSS CLI not found.", fg=typer.colors.RED)
    typer.secho(f"Downloading Tailwind CSS CLI from '{download_url}'", fg=typer.colors.YELLOW)

    # Download and store the tailwind cli binary
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(download_url)
    dest_file.write_bytes(response.content)

    # make cli executable
    dest_file.chmod(0o755)
    typer.secho(f"Downloaded Tailwind CSS CLI to '{dest_file}'{extra_msg}", fg=typer.colors.GREEN)


DEFAULT_TAILWIND_CONFIG = """/** @type {import('tailwindcss').Config} */
const plugin = require("tailwindcss/plugin");

module.exports = {
  content: ["./templates/**/*.html", "**/templates/**/*.html"],
  theme: {
    extend: {},
  },
  plugins: [
    require("@tailwindcss/typography"),
    require("@tailwindcss/forms"),
    require("@tailwindcss/aspect-ratio"),
    require("@tailwindcss/container-queries"),
    plugin(function ({ addVariant }) {
      addVariant("htmx-settling", ["&.htmx-settling", ".htmx-settling &"]);
      addVariant("htmx-request", ["&.htmx-request", ".htmx-request &"]);
      addVariant("htmx-swapping", ["&.htmx-swapping", ".htmx-swapping &"]);
      addVariant("htmx-added", ["&.htmx-added", ".htmx-added &"]);
    }),
  ],
};
"""


def _create_tailwind_config() -> None:
    tailwind_config_file = utils.get_full_config_file_path()
    if not tailwind_config_file.exists():
        tailwind_config_file.write_text(DEFAULT_TAILWIND_CONFIG)
        typer.secho(
            f"Created Tailwind CSS config at '{tailwind_config_file}'",
            fg=typer.colors.GREEN,
        )


def _get_build_cmd(*, minify: bool = True, watch: bool = False) -> list[str]:
    build_cmd = [
        str(utils.get_full_cli_path()),
        "--config",
        str(utils.get_full_config_file_path()),
        "--output",
        str(utils.get_full_dist_css_path()),
    ]

    if minify:
        build_cmd.append("--minify")

    if watch:
        build_cmd.append("--watch")

    if conf.get_tailwind_cli_src_css() is not None:
        build_cmd.extend(
            [
                "--input",
                str(utils.get_full_src_css_path()),
            ]
        )
    return build_cmd


def _runserver(
    *,
    addrport: Optional[str] = None,
    server_command: str = "runserver",
    use_ipv6: bool = False,
    no_threading: bool = False,
    no_static: bool = False,
    no_reloader: bool = False,
    skip_checks: bool = False,
    pdb: bool = False,
    ipdb: bool = False,
    pm: bool = False,
    print_sql: bool = False,
    print_sql_location: bool = False,
    cert_file: Optional[str] = None,
    key_file: Optional[str] = None,
):
    if (
        server_command == "runserver_plus"
        and not importlib.util.find_spec("django_extensions")
        and not importlib.util.find_spec("werkzeug")
    ):
        msg = (
            "Missing dependencies. Follow the instructions found on "
            "https://django-tailwind-cli.rtfd.io/latest/installation/."
        )
        raise CommandError(msg)

    # Start the watch process in a separate process.
    watch_cmd = [sys.executable, "manage.py", "tailwind", "watch"]
    watch_process = Process(
        target=subprocess.run,
        args=(watch_cmd,),
        kwargs={
            "cwd": settings.BASE_DIR,
            "check": True,
        },
    )

    # Start the runserver process in the current process.
    runserver_options = _get_runserver_options(
        addrport=addrport,
        use_ipv6=use_ipv6,
        no_threading=no_threading,
        no_static=no_static,
        no_reloader=no_reloader,
        skip_checks=skip_checks,
        pdb=pdb,
        ipdb=ipdb,
        pm=pm,
        print_sql=print_sql,
        print_sql_location=print_sql_location,
        cert_file=cert_file,
        key_file=key_file,
    )

    debug_server_cmd = [
        sys.executable,
        "manage.py",
        server_command,
    ] + runserver_options

    debugserver_process = Process(
        target=subprocess.run,
        args=(debug_server_cmd,),
        kwargs={
            "cwd": settings.BASE_DIR,
            "check": True,
        },
    )

    try:
        watch_process.start()
        debugserver_process.start()
        watch_process.join()
        debugserver_process.join()
    except KeyboardInterrupt:  # pragma: no cover
        watch_process.terminate()
        debugserver_process.terminate()


def _get_runserver_options(
    *,
    addrport: Optional[str] = None,
    use_ipv6: bool = False,
    no_threading: bool = False,
    no_static: bool = False,
    no_reloader: bool = False,
    skip_checks: bool = False,
    pdb: bool = False,
    ipdb: bool = False,
    pm: bool = False,
    print_sql: bool = False,
    print_sql_location: bool = False,
    cert_file: Optional[str] = None,
    key_file: Optional[str] = None,
) -> list[str]:
    options = []

    if use_ipv6:
        options.append("--ipv6")
    if no_threading:
        options.append("--nothreading")
    if no_static:
        options.append("--nostatic")
    if no_reloader:
        options.append("--noreload")
    if skip_checks:
        options.append("--skip-checks")
    if pdb:
        options.append("--pdb")
    if ipdb:
        options.append("--ipdb")
    if pm:
        options.append("--pm")
    if print_sql:
        options.append("--print-sql")
    if print_sql_location:
        options.append("--print-sql-location")
    if cert_file:
        options.append(f"--cert-file={cert_file}")
    if key_file:
        options.append(f"--key-file={key_file}")
    if addrport:
        options.append(addrport)

    return options
