# Usage

:::{admonition} Do I have to install the Tailwind CLI?
:class: tip

**No.** The management commands of this library handle the download and installation of the Tailwind CLI. You don't have to deal with this. But you can configure the installation location and the version of the CLI you want to use. Take a look at the [settings](settings.md) section.
:::

:::{admonition} Do I have to create my own `source.css` for Tailwind 4.x?
:class: tip

**No.** The management commands also take care of this step. If no source CSS file is present yet, one with sane defaults is created at `<BASE_DIR>/.django_tailwind_cli/source.css`. You can point at a hand-written file instead by setting [`TAILWIND_CLI_SRC_CSS`](settings.md#tailwind_cli_src_css) in your Django settings — the library leaves your file alone in that case.
:::

:::{admonition} Is `.django_tailwind_cli/` safe to commit?
:class: tip

**No, and you don't have to do anything.** On first use the library writes a `.gitignore` containing `*` into the managed directory, so the downloaded CLI binary and the auto-generated `source.css` are silently ignored by Git — no entry in your project-level `.gitignore` needed.
:::

## Management commands

### build

Run `python manage.py tailwind build` to create an optimized production build of the stylesheet. Afterwards you are ready to deploy. Make sure this command runs before `python manage.py collectstatic` in your build process.

### watch

Run `python manage.py tailwind watch` to start a Tailwind watcher process on its own — useful if you prefer to run your debug server in a separate shell or use a workflow other than `runserver` / `runserver_plus`.

By default the watch command runs under Django's own auto-reloader (the same one `runserver` uses). Whenever you change a Python file — including `settings.py` — the watcher restarts its Python process, regenerates the default source CSS file (picking up freshly added `INSTALLED_APPS`), and respawns the Tailwind CLI subprocess. This pairs nicely with [`TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS`](settings.md#tailwind_cli_auto_source_external_apps): adding an editable-installed app and updating `INSTALLED_APPS` is enough — no manual restart needed.

Pass `--noreload` if you want a single-process watch loop (e.g. in CI or when debugging the watcher itself):

```bash
python manage.py tailwind watch --noreload
```

### runserver

Run `python manage.py tailwind runserver` to start the Django debug server in parallel to a tailwind watcher process. If `django-extensions` plus `werkzeug` are installed, `runserver_plus` is used automatically; otherwise the vanilla `runserver` command runs.

This command is a transparent passthrough wrapper: **every** positional argument and option other than the tailwind-specific `--force-default-runserver` is forwarded verbatim to the underlying server command. That includes flags the wrapper itself does not know about (e.g. `runserver_plus`'s `--extra-file`, `--reloader-interval`, `--browser`, `--exclude-pattern`, …).

For the exhaustive list of forwarded flags, run:

```bash
python manage.py runserver --help
python manage.py runserver_plus --help   # with django-extensions
```

Examples:

```bash
# Default port (8000)
python manage.py tailwind runserver

# Custom port
python manage.py tailwind runserver 8080

# Forward arbitrary runserver / runserver_plus flags
python manage.py tailwind runserver 0.0.0.0:8000 --noreload
python manage.py tailwind runserver --print-sql --ipdb

# Pin to vanilla runserver even with django-extensions installed
python manage.py tailwind runserver --force-default-runserver
```

### download_cli

Run `python manage.py tailwind download_cli` to just download the CLI. This commands downloads the correct version of the CLI for your platform and stores it in the path configured by the `TAILWIND_CLI_PATH` setting.

### config

Run `python manage.py tailwind config` to show current Tailwind CSS configuration. This command displays the current configuration settings and their values, helping you understand how django-tailwind-cli is configured in your project.

The command shows:
- All configuration paths (CLI, CSS input/output)
- Version information
- Django settings values
- File existence status
- Platform information

### setup

Run `python manage.py tailwind setup` to launch the interactive setup guide for django-tailwind-cli. This command provides step-by-step guidance for setting up Tailwind CSS in your Django project, from installation to first build.

The guide covers:
1. Installation verification
2. Django settings configuration
3. CLI binary download
4. First CSS build
5. Template integration
6. Development workflow

This is perfect for first-time setup, troubleshooting configuration issues, or learning the development workflow.

### troubleshoot

Run `python manage.py tailwind troubleshoot` to access the troubleshooting guide for common issues. This command provides solutions for the most common issues encountered when using django-tailwind-cli, with step-by-step debugging guidance.

Common issues covered:
- CSS not updating in browser
- Build failures and errors
- Missing or incorrect configuration
- Permission and download issues
- Template integration problems

### optimize

Run `python manage.py tailwind optimize` to view performance optimization tips and best practices. This command provides detailed guidance on optimizing your Tailwind CSS build performance and development workflow for the best possible experience.

Areas covered:
- Build performance optimization
- File watching efficiency
- Template scanning optimization
- Production deployment best practices
- Development workflow improvements
- Common performance pitfalls

### remove_cli

Run `python manage.py tailwind remove_cli` to remove the installed CLI binary. This only works with the managed download; system binaries (`TAILWIND_CLI_USE_SYSTEM_BINARY = True`) are refused.

## Use with Docker Compose

When used in the `watch` mode, the Tailwind CLI requires a TTY-enabled environment to function correctly. In a Docker Compose setup, ensure that the container executing the Tailwind style rebuild command (either `python manage.py tailwind runserver` or `python manage.py tailwind watch`, as noted above) is configured with the `tty: true` setting in your `docker-compose.yml`.

```yaml
web:
  command: python manage.py tailwind runserver
  tty: true

# or

tailwind-sidecar:
  command: python manage.py tailwind watch
  tty: true
```

## Use with WhiteNoise

If you are using [WhiteNoise](https://whitenoise.readthedocs.io/en/latest/) to serve your static assets, you must not put your custom Tailwind configuration file inside any of the directories for static files. WhiteNoise stumbles across the `@import "tailwindcss";` statement, because it can't resolve it.

If you want to use a custom configuration for Tailwind CSS, put it somewhere else in the project.
