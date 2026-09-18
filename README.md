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
- Produces minified production builds containing only the classes you use
- Includes the CSS via a `{% tailwind_css %}` template tag
- Supports [DaisyUI](https://daisyui.com) through [tailwindcss-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra)
- Targets Tailwind CSS 4.x

## Quickstart

In an existing Django project, install the package:

```bash
python -m pip install django-tailwind-cli
```

Add the app and a static files directory to `settings.py`:

```python
INSTALLED_APPS = [
    # ... your other apps
    "django_tailwind_cli",
]

STATICFILES_DIRS = [BASE_DIR / "assets"]
```

Create that directory before starting Django:

```bash
mkdir -p assets
```

Load the template tag in your base template and place it inside `<head>`:

```htmldjango
{% load tailwind_cli %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Django App</title>
    {% tailwind_css %}
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
```

Start Django and the Tailwind watcher together:

```bash
python manage.py tailwind runserver
```

The first run downloads the CLI and creates the default source CSS. Add Tailwind classes to your
templates; the watcher rebuilds the stylesheet when you save them.

For a production build, run Tailwind before collecting static files:

```bash
python manage.py tailwind build
python manage.py collectstatic --noinput
```

See the [installation guide](https://django-tailwind-cli.readthedocs.io/latest/installation.html)
for setup checks and optional integrations, and the
[workflow guide](https://django-tailwind-cli.readthedocs.io/latest/workflow.html)
for custom CSS, editor setup and troubleshooting.

## Requirements

- **Python:** 3.10+
- **Django:** 4.2 LTS, 5.2, 6.0, or 6.1
- **Platform:** Windows, macOS, Linux (automatic platform detection)

## Configuration and commands

The defaults work with the setup above. Optional settings let you pin the Tailwind version,
use a system binary, add custom CSS, enable DaisyUI, or include editable-installed external apps.
See the [settings reference](https://django-tailwind-cli.readthedocs.io/latest/settings.html).

The [command reference](https://django-tailwind-cli.readthedocs.io/latest/usage.html) covers all
commands and options. To inspect your setup or investigate a build problem, start with:

```bash
python manage.py tailwind config
python manage.py tailwind build --verbose
python manage.py tailwind troubleshoot
```

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
[CONTRIBUTING.md](https://github.com/django-commons/django-tailwind-cli/blob/main/CONTRIBUTING.md)
covers the development setup ([mise](https://mise.jdx.dev/) provisions Python, `uv`, and
`pre-commit`), how to run the tests, and what a pull request should look like. Please read the short
section at the top of it before opening an issue or a pull request — it explains what makes one easy
to act on.

## License

This software is licensed under [MIT license](https://github.com/django-commons/django-tailwind-cli/blob/main/LICENSE).
