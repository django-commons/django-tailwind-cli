"""`tailwind` management command."""

import importlib.util
import os
import shutil
import ssl
import subprocess
import sys
import urllib.request
from multiprocessing import Process
from pathlib import Path
from typing import Optional, Union

import certifi
import typer
from django.core.management.base import CommandError
from django.template.utils import get_app_template_dirs
from django_typer.management import TyperCommand, command, initialize

from django_tailwind_cli import utils
from django_tailwind_cli.conf import DEFAULT_SRC_REPO, settings


class Command(TyperCommand):
    help = """Create and manage a Tailwind CSS theme."""

    @initialize()
    def init(self):
        # Get the config from the settings and validate it.
        try:
            utils.validate_settings()
        except Exception as e:
            msg = "Configuration error"
            raise CommandError(msg) from e

        # Before running the actual subcommand, we need to make sure that the CLI is installed and
        # the config file exists.
        if settings.TAILWIND_CLI_AUTOMATIC_DOWNLOAD:
            self.download_cli()
        self._create_tailwind_config_if_not_exists()

    @command(help="Build a minified production ready CSS file.")
    def build(self):
        if not utils.get_full_cli_path().exists():
            raise CommandError("Tailwind CSS CLI not found.")

        build_cmd = [
            str(utils.get_full_cli_path()),
            "--output",
            str(utils.get_full_dist_css_path()),
            "--minify",
        ]
        if settings.TAILWIND_CLI_SRC_CSS is not None:
            build_cmd.extend(
                [
                    "--input",
                    str(utils.get_full_src_css_path()),
                ]
            )
        try:
            subprocess.run(build_cmd, cwd=settings.BASE_DIR, check=True)  # noqa: S603
        except KeyboardInterrupt:
            self._write_error("Canceled building production stylesheet.")
        else:
            self._write_success(f"Built production stylesheet '{utils.get_full_dist_css_path()}'.")

    @command(help="Start Tailwind CLI in watch mode during development.")
    def watch(self):
        if not utils.get_full_cli_path().exists():
            raise CommandError("Tailwind CSS CLI not found.")

        watch_cmd = [
            str(utils.get_full_cli_path()),
            "--output",
            str(utils.get_full_dist_css_path()),
            "--watch",
        ]
        if settings.TAILWIND_CLI_SRC_CSS is not None:
            watch_cmd.extend(
                [
                    "--input",
                    str(utils.get_full_src_css_path()),
                ]
            )

        try:
            subprocess.run(watch_cmd, cwd=settings.BASE_DIR, check=True)  # noqa: S603
        except KeyboardInterrupt:
            self._write_success("Stopped watching for changes.")

    @command(name="list_templates", help="List the templates of your django project.")
    def list_templates(self):
        template_files: list[str] = []
        app_template_dirs = get_app_template_dirs("templates")
        for app_template_dir in app_template_dirs:
            template_files += self._list_template_files(app_template_dir)

        for template_dir in settings.TEMPLATES[0]["DIRS"]:
            template_files += self._list_template_files(template_dir)

        self.stdout.write("\n".join(template_files))

    @command(help="Start the Django development server and the Tailwind CLI in watch mode.")
    def runserver(
        self,
        addrport: Optional[str] = typer.Argument(None, help="Optional port number, or ipaddr:port"),
        *,
        use_ipv6: bool = typer.Option(
            False, "--ipv6", "-6", help="Tells Django to use an IPv6 address."
        ),
        no_threading: bool = typer.Option(
            False, "--nothreading", help="Tells Django to NOT use threading."
        ),
        no_static: bool = typer.Option(
            False,
            "--nostatic",
            help="Tells Django to NOT automatically serve static files at STATIC_URL.",
        ),
        no_reloader: bool = typer.Option(
            False, "--noreload", help="Tells Django to NOT use the auto-reloader."
        ),
        skip_checks: bool = typer.Option(False, "--skip-checks", help="Skip system checks."),
    ):
        debug_server_cmd = [sys.executable, "manage.py", "runserver"]

        if use_ipv6:
            debug_server_cmd.append("--ipv6")
        if no_threading:
            debug_server_cmd.append("--nothreading")
        if no_static:
            debug_server_cmd.append("--nostatic")
        if no_reloader:
            debug_server_cmd.append("--noreload")
        if skip_checks:
            debug_server_cmd.append("--skip-checks")
        if addrport:
            debug_server_cmd.append(addrport)

        self._runserver(debug_server_cmd)

    @command(
        name="runserver_plus",
        help=(
            "Start the django-extensions runserver_plus development "
            "server and the Tailwind CLI in watch mode."
        ),
    )
    def runserver_plus(
        self,
        addrport: Optional[str] = typer.Argument(None, help="Optional port number, or ipaddr:port"),
        *,
        use_ipv6: bool = typer.Option(
            False, "--ipv6", "-6", help="Tells Django to use an IPv6 address."
        ),
        no_threading: bool = typer.Option(
            False, "--nothreading", help="Tells Django to NOT use threading."
        ),
        no_static: bool = typer.Option(
            False,
            "--nostatic",
            help="Tells Django to NOT automatically serve static files at STATIC_URL.",
        ),
        no_reloader: bool = typer.Option(
            False, "--noreload", help="Tells Django to NOT use the auto-reloader."
        ),
        skip_checks: bool = typer.Option(False, "--skip-checks", help="Skip system checks."),
        pdb: bool = typer.Option(
            False, "--pdb", help="Drop into pdb shell at the start of any view."
        ),
        ipdb: bool = typer.Option(
            False, "--ipdb", help="Drop into ipdb shell at the start of any view."
        ),
        pm: bool = typer.Option(
            False, "--pm", help="Drop into (i)pdb shell if an exception is raised in a view."
        ),
        print_sql: bool = typer.Option(
            False, "--print-sql", help="Print SQL queries as they're executed."
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
        if not importlib.util.find_spec("django_extensions") and not importlib.util.find_spec(
            "werkzeug"
        ):
            msg = (
                "Missing dependencies. Follow the instructions found on "
                "https://django-tailwind-cli.rtfd.io/installation/."
            )
            raise CommandError(msg)

        debug_server_cmd = [sys.executable, "manage.py", "runserver_plus"]

        if use_ipv6:
            debug_server_cmd.append("--ipv6")
        if no_threading:
            debug_server_cmd.append("--nothreading")
        if no_static:
            debug_server_cmd.append("--nostatic")
        if no_reloader:
            debug_server_cmd.append("--noreload")
        if skip_checks:
            debug_server_cmd.append("--skip-checks")
        if pdb:
            debug_server_cmd.append("--pdb")
        if ipdb:
            debug_server_cmd.append("--ipdb")
        if pm:
            debug_server_cmd.append("--pm")
        if print_sql:
            debug_server_cmd.append("--print-sql")
        if print_sql_location:
            debug_server_cmd.append("--print-sql-location")
        if cert_file:
            debug_server_cmd.append(f"--cert-file={cert_file}")
        if key_file:
            debug_server_cmd.append(f"--key-file={key_file}")
        if addrport:
            debug_server_cmd.append(addrport)

        self._runserver(debug_server_cmd)

    def _runserver(self, debug_server_cmd: list[str]) -> None:
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

    @command(name="download_cli", help="Download the Tailwind CSS CLI to .")
    def download_cli(self) -> None:
        dest_file = utils.get_full_cli_path()
        extra_msg = (
            ""
            if settings.TAILWIND_CLI_SRC_REPO == DEFAULT_SRC_REPO
            else f" from '{settings.TAILWIND_CLI_SRC_REPO}'"
        )

        if dest_file.exists():
            self._write_success(f"Tailwind CSS CLI already exists at '{dest_file}'{extra_msg}")
            return

        download_url = utils.get_download_url()
        self._write_error("Tailwind CSS CLI not found.")
        self._write_success(f"Downloading Tailwind CSS CLI from '{download_url}'")
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        certifi_context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(download_url, context=certifi_context) as source:
            with dest_file.open(mode="wb") as dest:
                shutil.copyfileobj(source, dest)
        # make cli executable
        dest_file.chmod(0o755)
        self._write_success(f"Downloaded Tailwind CSS CLI to '{dest_file}'{extra_msg}")

    def _create_tailwind_config_if_not_exists(self) -> None:
        tailwind_config_file = utils.get_full_config_file_path()

        if not tailwind_config_file.exists():
            self.stdout.write(self.style.ERROR("Tailwind CSS config not found."))
            tailwind_config_file.write_text(DEFAULT_TAILWIND_CONFIG)
            self.stdout.write(
                self.style.SUCCESS(f"Created Tailwind CSS config at '{tailwind_config_file}'")
            )

    @staticmethod
    def _list_template_files(template_dir: Union[str, Path]) -> list[str]:
        template_files: list[str] = []
        for d, _, filenames in os.walk(str(template_dir)):
            for filename in filenames:
                if filename.endswith(".html") or filename.endswith(".txt"):
                    template_files.append(os.path.join(d, filename))
        return template_files

    def _write_error(self, message: str) -> None:
        self.stdout.write(self.style.ERROR(message))

    def _write_success(self, message: str) -> None:
        self.stdout.write(self.style.SUCCESS(message))


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
