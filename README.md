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

**The simplest way to integrate Tailwind CSS with Django** ⚡

No Node.js required! This library provides seamless [Tailwind CSS](https://tailwindcss.com) integration for Django using the standalone [Tailwind CSS CLI](https://tailwindcss.com/blog/standalone-cli). Inspired by the [Tailwind integration for Phoenix](https://github.com/phoenixframework/tailwind), it eliminates the need for Node.js in your Django development workflow.

## ✨ Why django-tailwind-cli?

- **🚀 Zero Node.js dependency** - No npm, webpack, or build tools required
- **⚡ Instant setup** - Get Tailwind running in under 5 minutes
- **🔄 Hot reload** - Watch mode with automatic CSS rebuilding
- **📦 Production ready** - Optimized builds with automatic purging
- **🎨 DaisyUI support** - Built-in component library integration
- **🛠️ Developer friendly** - Rich CLI with helpful error messages and debugging tools

## 🚀 Quick Start

### 1. Install the package

```bash
# Using pip
pip install django-tailwind-cli

# Using uv (recommended)
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

# Configure static files directory
STATICFILES_DIRS = [BASE_DIR / "assets"]
```

### 3. Set up your base template

Create or update your base template (e.g., `templates/base.html`):

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

### 4. Interactive setup (recommended for first-time users)

```bash
python manage.py tailwind setup
```

This will guide you through the complete setup process!

### 5. Start developing

```bash
# Start development server with hot reload
python manage.py tailwind runserver

# Or run build and watch separately
python manage.py tailwind watch  # In one terminal
python manage.py runserver       # In another terminal
```

### 🎉 You're ready to go!

Start adding Tailwind classes to your templates:

```html
{% extends "base.html" %}

{% block content %}
<div class="max-w-4xl mx-auto py-12">
    <h1 class="text-4xl font-bold text-gray-900 mb-8">
        Welcome to Django + Tailwind!
    </h1>
    <p class="text-lg text-gray-600">
        This text is styled with Tailwind CSS.
    </p>
    <button class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded mt-4">
        Click me!
    </button>
</div>
{% endblock %}
```

📚 **Next Steps:** Check out the [full documentation](https://django-tailwind-cli.rtfd.io/) for advanced configuration and usage patterns.

## 🎯 Core Features

### 🏗️ Build System
- **Automatic CLI download** - No manual setup required
- **Smart caching** - Faster rebuilds with file change detection
- **Production optimization** - Automatic CSS purging and minification
- **Force rebuild** - `--force` flag for clean builds

### 🔧 Development Tools
- **Interactive setup** - `python manage.py tailwind setup`
- **Configuration viewer** - `python manage.py tailwind config`
- **Template scanner** - `python manage.py tailwind list_templates`
- **Troubleshooting guide** - `python manage.py tailwind troubleshoot`

### 🎨 Styling Features
- **Tailwind CSS 4.x** - Latest features and performance improvements
- **DaisyUI integration** - Pre-built components via [tailwindcss-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra)
- **Custom CSS support** - Bring your own styles and configurations
- **Template tag** - Simple `{% tailwind_css %}` inclusion

### ⚡ Performance
- **File change detection** - Only rebuild when necessary
- **Concurrent processing** - Parallel build and server processes
- **Progress indicators** - Visual feedback during downloads and builds
- **Verbose logging** - Detailed diagnostics with `--verbose`

### 🛠️ Management Commands

| Command        | Purpose                    | Example                                  |
| -------------- | -------------------------- | ---------------------------------------- |
| `setup`        | Interactive setup guide    | `python manage.py tailwind setup`        |
| `build`        | Production CSS build       | `python manage.py tailwind build`        |
| `watch`        | Development file watcher   | `python manage.py tailwind watch`        |
| `runserver`    | Combined server + watcher  | `python manage.py tailwind runserver`    |
| `config`       | Show current configuration | `python manage.py tailwind config`       |
| `troubleshoot` | Debug common issues        | `python manage.py tailwind troubleshoot` |

## 📋 Requirements

- **Python:** 3.10+
- **Django:** 4.0-6.0+
- **Platform:** Windows, macOS, Linux (automatic platform detection)

## ⚙️ Configuration Examples

### Basic Configuration
```python
# settings.py
STATICFILES_DIRS = [BASE_DIR / "assets"]
```

### Advanced Configuration
```python
# Pin specific Tailwind version
TAILWIND_CLI_VERSION = "4.1.3"

# Custom CSS paths
TAILWIND_CLI_SRC_CSS = "src/styles/main.css"
TAILWIND_CLI_DIST_CSS = "css/app.css"

# Enable DaisyUI
TAILWIND_CLI_USE_DAISY_UI = True

# Custom CLI path (for CI/CD)
TAILWIND_CLI_PATH = "/usr/local/bin/tailwindcss"
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
```

### Production Settings
```python
# Optimized for production
TAILWIND_CLI_VERSION = "4.1.3"  # Pin version
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False  # Use pre-installed CLI
TAILWIND_CLI_DIST_CSS = "css/tailwind.min.css"
```

## 🔍 Troubleshooting

### Common Issues

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

**Missing templates?**
```bash
python manage.py tailwind list_templates --verbose
```

### Performance Tips

1. **Use file watching:** `python manage.py tailwind runserver` for automatic rebuilds
2. **Check template scanning:** Ensure all template directories are included
3. **Optimize builds:** Use `--force` only when necessary
4. **Monitor file changes:** Use `--verbose` for detailed logging

## 🎨 DaisyUI Integration

Enable beautiful pre-built components:

```python
# settings.py
TAILWIND_CLI_USE_DAISY_UI = True
```

```html
<!-- Use DaisyUI components -->
<button class="btn btn-primary">Primary Button</button>
<div class="card bg-base-100 shadow-xl">
    <div class="card-body">
        <h2 class="card-title">Card Title</h2>
        <p>Card content goes here.</p>
    </div>
</div>
```

## 📚 Documentation & Resources

- **📖 Full Documentation:** [django-tailwind-cli.rtfd.io](https://django-tailwind-cli.rtfd.io/)
- **🎯 Tailwind CSS Docs:** [tailwindcss.com](https://tailwindcss.com)
- **🧩 DaisyUI Components:** [daisyui.com](https://daisyui.com)
- **💬 Django Commons:** [github.com/django-commons](https://github.com/django-commons)

## 🔗 Related Projects

- **tailwindcss-cli-extra:** [DaisyUI-enabled CLI](https://github.com/dobicinaitis/tailwind-cli-extra)
- **Django Extensions:** [Extended runserver features](https://django-extensions.readthedocs.io/)
- **Tailwind CSS IntelliSense:** [VS Code extension](https://marketplace.visualstudio.com/items?itemName=bradlc.vscode-tailwindcss)

## 🤝 Contributing

We welcome contributions! This project uses modern Python tooling for development.

### Prerequisites

- **[uv](https://docs.astral.sh/uv/)** - Fast Python package manager
- **[just](https://github.com/casey/just)** - Command runner (optional but recommended)

### Quick Development Setup

```bash
# Clone the repository
git clone https://github.com/django-commons/django-tailwind-cli.git
cd django-tailwind-cli

# Setup development environment (with just)
just bootstrap

# Or setup manually with uv
uv venv
uv sync --all-extras
```

### Development Commands

```bash
# With just (recommended)
just upgrade          # Update dependencies
just lint             # Run linting and formatting
just test             # Run test suite
just test-all         # Run tests across Python/Django versions

# Without just
uv sync --all-extras  # Update dependencies
uvx pre-commit run --all-files  # Run linting
uv run pytest        # Run tests
uvx --with tox-uv tox # Run full test matrix
```

### Contribution Guidelines

1. **🍴 Fork** the repository
2. **🌿 Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **✅ Test** your changes (`just test`)
4. **📝 Commit** with conventional commits (`feat:`, `fix:`, `docs:`, etc.)
5. **📤 Push** to your branch (`git push origin feature/amazing-feature`)
6. **🔄 Create** a Pull Request

### Code Quality

- **Type hints** for all new code
- **Tests** for new features and bug fixes
- **Documentation** updates for user-facing changes
- **Conventional commits** for clear history

## License

This software is licensed under [MIT license](https://github.com/django-commons/django-tailwind-cli/blob/main/LICENSE).
