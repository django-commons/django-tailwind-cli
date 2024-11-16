# django-tailwind-cli

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/django-commons/django-tailwind-cli/test.yml?style=flat-square)
[![PyPI](https://img.shields.io/pypi/v/django-tailwind-cli.svg?style=flat-square)](https://pypi.org/project/django-tailwind-cli/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
![GitHub](https://img.shields.io/github/license/django-commons/django-tailwind-cli?style=flat-square)
![Django Versions](https://img.shields.io/pypi/frameworkversions/django/django-tailwind-cli)
![Python Versions](https://img.shields.io/pypi/pyversions/django-tailwind-cli)
[![Downloads](https://static.pepy.tech/badge/django-tailwind-cli)](https://pepy.tech/project/django-tailwind-cli)
[![Downloads / Month](https://pepy.tech/badge/django-tailwind-cli/month)](<https://pepy.tech/project/django-tailwind-cli>)

This library provides an integration of [Tailwind CSS](https://tailwindcss.com) for Django that is using on the precompiled versions of the [Tailwind CSS CLI](https://tailwindcss.com/blog/standalone-cli).

The goal of this library is to provided the simplest possible Tailwind integration for your Django project. It took its inspiration from the [Tailwind integration for Phoenix](https://github.com/phoenixframework/tailwind) which completely skips the neccesity of a node installation.

## Installation

1. Install the library.

   ```shell
   python -m pip install django-tailwind-cli
   ```

2. Add `django_tailwind_cli` to `INSTALLED_APPS` in `settings.py`.

   ```python
   INSTALLED_APPS = [
       # other Django apps
       "django_tailwind_cli",
   ]
   ```

3. Configure the `STATICFILES_DIRS` parameter in your `settings.py` if not already configured.

   ```python
   STATICFILES_DIRS = [BASE_DIR / "assets"]
   ```

4. Add template code.

   ```htmldjango
   {% load tailwind_cli %}
   ...
   <head>
     ...
     {% tailwind_css %}
     ...
   </head>
   ```

5. Start the debug server.

   ```shell
   python manage.py tailwind runserver
   ```

Enjoy!

Checkout the detailed [installation guide](https://django-tailwind-cli.rtfd.io/latest/installation/) if you want to activate browser reload or the `runserver_plus` management command known from `django-extensions`.

## Features

- Simplest possible integration.
- Management commands:
  - To start the Tailwind CLI in watch mode during development.
  - To build the production grade CSS file for your project.
  - To start a debug server along with the Tailwind CLI in watch mode in a single session.
- Necessary configuration to adapt the library to your project, when the defaults don't fit you.
- A template tag to include the Tailwind CSS file in your project.
- A base template for your project.
- A sane tailwind.config.js that activates all the official plugins and includes a simple HTMX plugin.

## Requirements

Python 3.9 or newer with Django >= 4.2.

## Documentation

The documentation can be found at [https://django-tailwind-cli.rtfd.io/](https://django-tailwind-cli.rtfd.io/)

## Contributing

This package requires [uv](https://docs.astral.sh/uv/) for dependency management and tooling. So you have to [install it](https://docs.astral.sh/uv/getting-started/installation/) first. [just](https://github.com/casey/just) is used as a handy command runner to save some typing on the command line. Do yourself a favor and install it too.

```shell
# Setup development environment
just bootstrap

# Upgrade/install all dependencies defined in pyproject.toml
just upgrade

# Run pre-commit rules on all files
just lint

# Run test suite
just test
```

### Without just, but using uv

```bash
# Create venv
uv venv

# Install dependencies
uv sync --all-extras

# Run tox testrunner
uvx --with tox-uv tox
```

## License

This software is licensed under [MIT license](https://github.com/django-commons/django-tailwind-cli/blob/main/LICENSE).
