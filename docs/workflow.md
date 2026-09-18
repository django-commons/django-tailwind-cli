# Development workflow

After [installation](installation.md), use this page for running the watcher, editing styles and
investigating missing CSS. For work on the package itself, see [Contributing](contributing.md).

## Running the development server

```bash
python manage.py tailwind runserver
```

This starts Django and Tailwind together. If your IDE already runs Django, or `manage.py` lives
outside `BASE_DIR`, start the watcher separately:

```bash
python manage.py tailwind watch     # Terminal 1
python manage.py runserver          # Terminal 2, unless your IDE runs it
```

The watcher runs under Django's auto-reloader. Python changes, including changes to `settings.py`,
restart it with fresh configuration. Pass `--noreload` to disable this behavior.

Server arguments are forwarded to Django's `runserver` or `runserver_plus`, for example:

```bash
python manage.py tailwind runserver 8080
```

See [runserver](usage.md#runserver) for server selection and additional options, and
[Docker Compose](usage.md#use-with-docker-compose) if you run the watcher in a container.

## Editing templates and CSS

Extend the base template that loads your stylesheet:

```htmldjango
<!-- templates/myapp/page.html -->
{% extends "base.html" %}

{% block content %}
<div class="max-w-4xl mx-auto p-6">
    <h1 class="text-3xl font-bold text-gray-900">New Page</h1>
</div>
{% endblock %}
```

Save the template while the watcher is running, then refresh the page. For automatic browser
refreshes, configure [browser reload](installation.md#browser-reload).

For custom CSS, create a file outside your static directories and point Django at it:

```python
TAILWIND_CLI_SRC_CSS = "styles/main.css"
```

```css
/* styles/main.css */
@import "tailwindcss";

@theme {
    --color-brand: #2563eb;
}
```

The managed `.django_tailwind_cli/source.css` is regenerated during builds, so keep your edits in
this custom file. See [`TAILWIND_CLI_SRC_CSS`](settings.md#tailwind_cli_src_css) for path handling.

The default import enables automatic source detection from `BASE_DIR`. To include external or
ignored paths, add `@source` directives to your custom CSS; paths are relative to that CSS file.
For editable-installed external apps with the managed source CSS, enable
[`TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS`](settings.md#tailwind_cli_auto_source_external_apps).
For separate stylesheets with explicitly limited sources, see the
[multiple stylesheet examples](settings.md#tailwind_cli_css_map).

## Building for deployment

Build the CSS before collecting static files:

```bash
python manage.py tailwind build
python manage.py collectstatic --noinput
```

Every build regenerates all configured stylesheets. With manifest storage, reversing this order
can leave the stylesheet missing from the manifest and cause template rendering to fail. See
[WhiteNoise](whitenoise.md#build-the-css-before-collectstatic) for the complete deployment example.

## IDE Integration

### VS Code Setup

1. **Install Extensions:**
   - Tailwind CSS IntelliSense
   - Django Template
   - Python

2. **Workspace Settings:**

   ```json
   // .vscode/settings.json
   {
     "tailwindCSS.includeLanguages": {
       "django-html": "html"
     },
     "tailwindCSS.files.exclude": [
       "**/.git/**",
       "**/node_modules/**"
     ],
     "files.associations": {
       "*.html": "django-html"
     }
   }
   ```

3. **Tasks Configuration:**

   ```json
   // .vscode/tasks.json
   {
     "version": "2.0.0",
     "tasks": [
       {
         "label": "Tailwind Runserver",
         "type": "shell",
         "command": "python",
         "args": ["manage.py", "tailwind", "runserver"],
         "group": "build",
         "isBackground": true
       }
     ]
   }
   ```

### PyCharm Setup

Create a Python run configuration:

- Name: Tailwind Watch
- Script: `manage.py`
- Parameters: `tailwind watch`

Use the project's Python environment and working directory. The running watcher handles template
changes; a separate file watcher that runs a production build on every save is unnecessary.

## Troubleshooting

### A class is missing from the stylesheet

Check whether the template is outside `BASE_DIR` or excluded by `.gitignore`. Add missing paths
with `@source` in custom CSS, or enable the external-app setting described above. Explicit
`@source` directives add to automatic detection; `source(none)` disables automatic detection.
See [Tailwind's source detection guide](https://tailwindcss.com/docs/detecting-classes-in-source-files)
for exclusions and class-name detection rules.

### CSS is not updating in the browser

Run a build with diagnostics:

```bash
python manage.py tailwind build --verbose
```

If the build fails, address the reported error. If it succeeds, check that your page includes the
stylesheet through `{% tailwind_css %}` and that the browser loads the updated file. During
development, keep the watcher running to rebuild after subsequent edits.

### Configuration or CLI problems

```bash
python manage.py tailwind config
python manage.py tailwind troubleshoot
```

`config` shows the resolved binary and stylesheet paths. Check those paths against your project
layout. If the binary is missing, `python manage.py tailwind download_cli` downloads it separately
from a build; managed downloads require network access. If using a system binary, check the
[system binary setting](settings.md#tailwind_cli_use_system_binary).

If these checks do not explain the behavior, include the diagnostics, versions and reproduction
steps in a report as described in [Contributing](contributing.md#reporting-a-bug).
