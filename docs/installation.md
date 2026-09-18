# Installation

For a minimal working setup, see the [quickstart](index.md#quickstart). This page covers the
setup details and optional integrations for an existing Django project. Supported Python,
Django and operating system versions are listed in [Requirements](index.md#requirements).

## Install the package

Use your project's package manager:

```shell
python -m pip install django-tailwind-cli
# Or:
uv add django-tailwind-cli
# Or:
poetry add django-tailwind-cli
```

## Configure Django

Add `django_tailwind_cli` to `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # other Django apps
    "django_tailwind_cli",
]
```

Configure `STATICFILES_DIRS` if you have not already done so. The compiled stylesheet is written
relative to its first entry; the default output is `css/tailwind.css`.

```python
STATICFILES_DIRS = [BASE_DIR / "assets"]
```

Create the directory on disk before running Django commands:

```shell
mkdir -p assets
```

Load `tailwind_cli` in your base template and add `{% tailwind_css %}` inside `<head>`:

```htmldjango
{% load tailwind_cli %}
<head>
    {% tailwind_css %}
</head>
```

The tag uses Django's static file storage to resolve the compiled stylesheet. See the
[template tag reference](template_tags.md) for options, or use the provided
[base template](base_template.md).

## Check the setup

```shell
python manage.py tailwind setup
```

The command checks the configuration and stops at the first blocker with instructions. Once the
configuration is ready, it downloads the CLI if needed and builds the CSS. It can be run again
after fixing a reported problem; see [setup](usage.md#setup) for the full sequence.

The first build creates `<BASE_DIR>/.django_tailwind_cli/` for the downloaded binary and generated
`source.css`. A `.gitignore` inside that directory keeps both out of Git. The compiled stylesheet
is outside that directory: add `assets/css/tailwind.css` to your project's `.gitignore` if you use
the defaults.

The default source CSS is regenerated on builds. For hand-written styles, configure a separate
file using [`TAILWIND_CLI_SRC_CSS`](settings.md#tailwind_cli_src_css); keep it outside your static
files directories. See [Editing templates and CSS](workflow.md#editing-templates-and-css).

Continue with [Running the development server](workflow.md#running-the-development-server).

## Optional integrations

### Django Extensions

Install the extra to use `runserver_plus` and its Werkzeug debugger:

```shell
python -m pip install "django-tailwind-cli[django-extensions]"
```

Add `django_extensions` to `INSTALLED_APPS`. `tailwind runserver` then selects `runserver_plus`
automatically. Pass `--force-default-runserver` when you want Django's standard server instead;
see [runserver](usage.md#runserver) for forwarded options.

### A system-installed Tailwind CSS CLI

If you already have `tailwindcss` on your `PATH`, enable:

```python
TAILWIND_CLI_USE_SYSTEM_BINARY = True
```

This skips the managed download. See
[`TAILWIND_CLI_USE_SYSTEM_BINARY`](settings.md#tailwind_cli_use_system_binary) for binary selection
and error handling, and the [production configuration](settings.md#production-environment)
for a pinned, explicitly provisioned binary.

### DaisyUI

To use the DaisyUI-enabled CLI build, set:

```python
TAILWIND_CLI_USE_DAISY_UI = True
```

See the [DaisyUI settings](settings.md#tailwind_cli_use_daisy_ui) for how the CLI and generated
source CSS change, and the [DaisyUI configuration examples](settings.md#daisyui) for custom CSS.
You can then use component classes in templates:

```html
<button class="btn btn-primary">Primary Button</button>
<div class="card bg-base-100 shadow-xl">
    <div class="card-body">
        <h2 class="card-title">Card Title</h2>
        <p>Card content goes here.</p>
    </div>
</div>
```

### Browser reload

The Tailwind watcher rebuilds CSS on disk. To also reload browser pages automatically, install
and configure [django-browser-reload](https://github.com/adamchainz/django-browser-reload#installation).
Its installation guide covers the app, URL route and middleware, including middleware ordering
and manual script insertion. No additional `django-tailwind-cli` setting is required.
