# django-tailwind-cli

<p style="display: flex; gap: 4px; flex-wrap: wrap; align-items: flex-start; line-height: 1;">
<img style="height: auto;" alt="GitHub Workflow Status" src="https://img.shields.io/github/actions/workflow/status/django-commons/django-tailwind-cli/test.yml">
<a style="display: inline-block;" href="https://pypi.org/project/django-tailwind-cli/"><img style="height: auto;" alt="PyPI" src="https://img.shields.io/pypi/v/django-tailwind-cli.svg"></a>
<a style="display: inline-block;" href="https://github.com/astral-sh/ruff"><img style="height: auto;" alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json"></a>
<a style="display: inline-block;" href="https://github.com/astral-sh/uv"><img style="height: auto;" alt="uv" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json"></a>
<img style="height: auto;" alt="GitHub" src="https://img.shields.io/github/license/django-commons/django-tailwind-cli">
<img style="height: auto;" alt="Django Versions" src="https://img.shields.io/pypi/frameworkversions/django/django-tailwind-cli">
<img style="height: auto;" alt="Python Versions" src="https://img.shields.io/pypi/pyversions/django-tailwind-cli">
<a style="display: inline-block;" href="https://pepy.tech/project/django-tailwind-cli"><img style="height: auto;" alt="Downloads" src="https://static.pepy.tech/badge/django-tailwind-cli"></a>
<a style="display: inline-block;" href="https://pepy.tech/project/django-tailwind-cli"><img style="height: auto;" alt="Downloads / Month" src="https://pepy.tech/badge/django-tailwind-cli/month"></a>
</p>

[Tailwind CSS](https://tailwindcss.com) for Django without Node.js. The library downloads the
standalone [Tailwind CSS CLI](https://tailwindcss.com/blog/standalone-cli) and wires it into Django
management commands, so there is no npm, no webpack, and no separate build tool to configure. It
follows the approach of the [Tailwind integration for Phoenix](https://github.com/phoenixframework/tailwind).

## What it does

- Downloads and manages the Tailwind CLI binary for your platform
- Rebuilds CSS on change, running under Django's own auto-reloader
- Produces minified production builds containing only the classes you use, and skips work when
  nothing changed
- Includes the CSS via a `{% tailwind_css %}` template tag
- Supports [DaisyUI](https://daisyui.com) through [tailwindcss-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra)
- Targets Tailwind CSS 4.x

## Installation

### 1. Install the package

```bash
# Using pip
pip install django-tailwind-cli

# Using uv
uv add django-tailwind-cli

# Using poetry
poetry add django-tailwind-cli
```

### 2. Configure Django settings

Add to your `settings.py`:

```python
INSTALLED_APPS = [
    # ... your other apps
    "django_tailwind_cli",
]

# Configure static files directory — make sure it exists on disk,
# Django raises an error at startup if it does not.
STATICFILES_DIRS = [BASE_DIR / "assets"]
```

```bash
mkdir -p assets
```

### 3. Set up your base template

Create or update your base template (e.g. `templates/base.html`):

```html
<!DOCTYPE html>
{% load tailwind_cli %}
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Django App</title>
    {% tailwind_css %}
</head>
<body class="bg-gray-50">
    <div class="container mx-auto px-4">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
```

### 4. Start developing

```bash
# Start Django's dev server with a parallel Tailwind watcher
python manage.py tailwind runserver

# Or run build and watch separately
python manage.py tailwind watch  # In one terminal
python manage.py runserver       # In another terminal
```

The watcher runs under Django's own auto-reloader, so editing `settings.py` (e.g. adding a new app)
restarts it automatically and picks up the new configuration on the fly. Pass `--noreload` to opt
out.

First run creates a managed `<BASE_DIR>/.django_tailwind_cli/` directory for the CLI binary and an
auto-generated `source.css`. The directory is automatically git-ignored — no entry in your
project-level `.gitignore` needed.

`python manage.py tailwind setup` walks the same ground: it checks each piece in order, stops at
the first one that is missing with instructions, and performs the download and first build when
they are needed.

## Management commands

| Command        | Purpose                                              | Example                                  |
| -------------- | ---------------------------------------------------- | ---------------------------------------- |
| `setup`        | Guided first-time setup and checks                   | `python manage.py tailwind setup`        |
| `build`        | Production CSS build                                 | `python manage.py tailwind build`        |
| `watch`        | Development file watcher (Django autoreload by default) | `python manage.py tailwind watch`    |
| `runserver`    | Django dev server + watcher (forwards any runserver flag) | `python manage.py tailwind runserver` |
| `config`       | Show current configuration                           | `python manage.py tailwind config`       |
| `troubleshoot` | Debug common issues                                  | `python manage.py tailwind troubleshoot` |

`build` takes `--force` to rebuild regardless of change detection; `build` and `watch` both take
`--verbose` for detailed diagnostics.

`tailwind runserver` is a transparent passthrough: every positional argument and option (apart from
`--force-default-runserver`) is forwarded verbatim to the underlying `runserver` or
`runserver_plus`. Every flag those commands accept works — including `runserver_plus`-only ones like
`--extra-file`, `--reloader-interval`, and `--print-sql`.

## Requirements

- **Python:** 3.10+
- **Django:** 4.2 LTS, 5.2, 6.0, or 6.1
- **Platform:** Windows, macOS, Linux (automatic platform detection)

## Configuration

Beyond adding the app to `INSTALLED_APPS`, `STATICFILES_DIRS` is the only setting you have to
configure. Everything below is optional; see the
[settings reference](https://django-tailwind-cli.readthedocs.io/latest/settings.html) for the full
list.

```python
# Pin a specific Tailwind version instead of tracking the latest release
TAILWIND_CLI_VERSION = "4.1.3"

# Custom CSS paths
TAILWIND_CLI_SRC_CSS = "src/styles/main.css"
TAILWIND_CLI_DIST_CSS = "css/app.css"

# Enable DaisyUI
TAILWIND_CLI_USE_DAISY_UI = True

# Use an already-installed Tailwind binary (e.g. `brew install tailwindcss`)
TAILWIND_CLI_USE_SYSTEM_BINARY = True

# Auto-inject @source directives for editable-installed external apps (opt-in)
TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS = True
```

For production, pin the version and provide the binary yourself rather than downloading it during a
build:

```python
TAILWIND_CLI_VERSION = "4.1.3"
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
TAILWIND_CLI_PATH = "/usr/local/bin/tailwindcss"  # where your binary actually is
TAILWIND_CLI_DIST_CSS = "css/tailwind.min.css"
```

## DaisyUI

Setting `TAILWIND_CLI_USE_DAISY_UI = True` switches to the DaisyUI-enabled CLI build, which makes
its component classes available:

```html
<button class="btn btn-primary">Primary Button</button>
<div class="card bg-base-100 shadow-xl">
    <div class="card-body">
        <h2 class="card-title">Card Title</h2>
        <p>Card content goes here.</p>
    </div>
</div>
```

## Troubleshooting

**CSS not updating?**

```bash
python manage.py tailwind build --force
python manage.py tailwind troubleshoot
```

**Configuration problems?**

```bash
python manage.py tailwind config
python manage.py tailwind setup
```

**Classes from some templates are missing?**

Make sure every template directory is covered by an `@source` directive in your Tailwind CSS input
file — Tailwind CSS 4.x discovers templates exclusively through those directives. Declaring them
explicitly also keeps builds fast, because Tailwind only scans what you list.

## Documentation and related projects

- [Full documentation](https://django-tailwind-cli.rtfd.io/)
- [Tailwind CSS documentation](https://tailwindcss.com)
- [DaisyUI components](https://daisyui.com)
- [tailwindcss-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra) — the DaisyUI-enabled CLI build
- [Django Extensions](https://django-extensions.readthedocs.io/) — provides `runserver_plus`
- [Tailwind CSS IntelliSense](https://marketplace.visualstudio.com/items?itemName=bradlc.vscode-tailwindcss) — VS Code extension
- [Django Commons](https://github.com/django-commons)

## Contributing

Contributions are welcome.

### Prerequisites

- **[mise](https://mise.jdx.dev/)** — provisions Python 3.10–3.15, `uv`, and `pre-commit` from `mise.toml`

### Development setup

```bash
git clone https://github.com/django-commons/django-tailwind-cli.git
cd django-tailwind-cli

mise install
mise run bootstrap
```

### Development commands

```bash
mise run upgrade      # Update dependencies
mise run lint         # Run linting and formatting
mise run test         # Run test suite
mise run test-all     # Run tests across Python/Django versions
```

### Guidelines

Fork the repository and work on a feature branch. Please add type hints and tests for new code,
update the documentation for user-facing changes, and use
[conventional commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, …) so the
history stays readable. Run `mise run test` before opening a pull request.

## License

This software is licensed under [MIT license](https://github.com/django-commons/django-tailwind-cli/blob/main/LICENSE).
