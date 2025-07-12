"""`tailwind` management command."""

import importlib.util
import os
import subprocess
import sys
from multiprocessing import Process
from pathlib import Path

import requests
import typer
from django.conf import settings
from django.core.management.base import CommandError
from django.template.utils import get_app_template_dirs
from django_typer.management import Typer

from django_tailwind_cli.config import get_config

app = Typer(name="tailwind", help="Create and manage a Tailwind CSS theme.")  # type: ignore


@app.command()
def build() -> None:
    """Build a minified production ready CSS file."""
    config = get_config()
    _download_cli()
    _create_standard_config()

    try:
        subprocess.run(config.build_cmd, cwd=settings.BASE_DIR, check=True, capture_output=True, text=True)
        typer.secho(f"Built production stylesheet '{config.dist_css}'.", fg=typer.colors.GREEN)
    except KeyboardInterrupt:
        typer.secho("Canceled building production stylesheet.", fg=typer.colors.RED)
    except subprocess.CalledProcessError as e:  # pragma: no cover
        error_message = e.stderr if e.stderr else "An unknown error occurred."
        typer.secho(f"Failed to build production stylesheet: {error_message}", fg=typer.colors.RED)
        sys.exit(1)


@app.command()
def watch():
    """Start Tailwind CLI in watch mode during development."""
    c = get_config()
    _download_cli()
    _create_standard_config()

    try:
        subprocess.run(c.watch_cmd, cwd=settings.BASE_DIR, check=True, capture_output=True)
    except KeyboardInterrupt:
        typer.secho("Stopped watching for changes.", fg=typer.colors.RED)
    except subprocess.CalledProcessError as e:  # pragma: no cover
        typer.secho(f"Failed to start in watch mode: {e.stderr.decode()}", fg=typer.colors.RED)
        sys.exit(1)


@app.command(name="list_templates")
def list_templates():
    """List the templates of your django project."""
    template_files: list[str] = []

    def _list_template_files(td: str | Path) -> None:
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
    _download_cli(force_download=True)


@app.command(name="remove_cli")
def remove_cli():
    """Remove the Tailwind CSS CLI."""
    c = get_config()

    if c.cli_path.exists():
        c.cli_path.unlink()
        typer.secho(f"Removed Tailwind CSS CLI at '{c.cli_path}'.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Tailwind CSS CLI not found at '{c.cli_path}'.", fg=typer.colors.RED)


@app.command()
def runserver(
    addrport: str | None = typer.Argument(
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
        help="Drop into pdb shell at the start of any view. (Requires django-extensions.)",
    ),
    ipdb: bool = typer.Option(
        False,
        "--ipdb",
        help="Drop into ipdb shell at the start of any view. (Requires django-extensions.)",
    ),
    pm: bool = typer.Option(
        False,
        "--pm",
        help="Drop into (i)pdb shell if an exception is raised in a view. (Requires django-extensions.)",
    ),
    print_sql: bool = typer.Option(
        False,
        "--print-sql",
        help="Print SQL queries as they're executed. (Requires django-extensions.)",
    ),
    print_sql_location: bool = typer.Option(
        False,
        "--print-sql-location",
        help="Show location in code where SQL query generated from. (Requires django-extensions.)",
    ),
    cert_file: str | None = typer.Option(
        None,
        help=(
            "SSL .crt file path. If not provided path from --key-file will be selected. "
            "Either --cert-file or --key-file must be provided to use SSL. "
            "(Requires django-extensions.)"
        ),
    ),
    key_file: str | None = typer.Option(
        None,
        help=(
            "SSL .key file path. If not provided path from --cert-file will be "
            "selected. Either --cert-file or --key-file must be provided to use SSL. "
            "(Requires django-extensions.)"
        ),
    ),
    force_default_runserver: bool = typer.Option(
        False,
        help=("Force the use of the default runserver command even if django-extensions is installed. "),
    ),
):
    """Run the development server with Tailwind CSS CLI in watch mode.

    If django-extensions is installed along with this library, this command runs the runserver_plus
    command from django-extensions. Otherwise it runs the default runserver command.
    """
    if (
        importlib.util.find_spec("django_extensions")
        and importlib.util.find_spec("werkzeug")
        and not force_default_runserver
    ):
        server_command = "runserver_plus"
        runserver_options = get_runserver_options(
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
    else:
        server_command = "runserver"
        runserver_options = get_runserver_options(
            addrport=addrport,
            use_ipv6=use_ipv6,
            no_threading=no_threading,
            no_static=no_static,
            no_reloader=no_reloader,
            skip_checks=skip_checks,
        )

    watch_cmd = [sys.executable, "manage.py", "tailwind", "watch"]
    watch_process = Process(
        target=subprocess.run,
        args=(watch_cmd,),
        kwargs={
            "cwd": settings.BASE_DIR,
            "check": True,
        },
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


# UTILITY FUNCTIONS -------------------------------------------------------------------------------


def _download_cli(*, force_download: bool = False) -> None:
    """Assure that the CLI is loaded if automatic downloads are activated."""
    c = get_config()

    if not force_download and not c.automatic_download:
        if not c.cli_path.exists():
            raise CommandError(
                "Automatic download of Tailwind CSS CLI is deactivated. Please download the Tailwind CSS CLI manually."
            )
        return

    if c.cli_path.exists():
        typer.secho(
            f"Tailwind CSS CLI already exists at '{c.cli_path}'.",
            fg=typer.colors.GREEN,
        )
        return

    typer.secho("Tailwind CSS CLI not found.", fg=typer.colors.RED)
    typer.secho(f"Downloading Tailwind CSS CLI from '{c.download_url}'.", fg=typer.colors.YELLOW)

    # Download and store the tailwind cli binary
    c.cli_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(c.download_url)
    c.cli_path.write_bytes(response.content)

    # make cli executable
    c.cli_path.chmod(0o755)
    typer.secho(f"Downloaded Tailwind CSS CLI to '{c.cli_path}'.", fg=typer.colors.GREEN)


DEFAULT_SOURCE_CSS = '@import "tailwindcss";\n'
DAISY_UI_SOURCE_CSS = '@import "tailwindcss";\n@plugin "daisyui";\n'


def _create_standard_config() -> None:
    """Create a standard Tailwind CSS config file."""
    c = get_config()

    if c.src_css and (c.overwrite_default_config or not c.src_css.exists()):
        c.src_css.parent.mkdir(parents=True, exist_ok=True)
        if c.use_daisy_ui:
            c.src_css.write_text(DAISY_UI_SOURCE_CSS)
        else:
            c.src_css.write_text(DEFAULT_SOURCE_CSS)
        typer.secho(
            f"Created Tailwind Source CSS at '{c.src_css}'",
            fg=typer.colors.GREEN,
        )


def get_runserver_options(
    *,
    addrport: str | None = None,
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
    cert_file: str | None = None,
    key_file: str | None = None,
) -> list[str]:
    options: list[str] = []

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
