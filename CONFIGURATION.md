# Advanced Configuration Guide

This guide covers advanced configuration patterns and real-world deployment scenarios for django-tailwind-cli.

## 🏗️ Configuration Patterns

### Development Environment

Optimized for fast iteration and debugging:

```python
# settings/development.py
TAILWIND_CLI_VERSION = "latest"  # Auto-update to newest version
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True  # Auto-download CLI
TAILWIND_CLI_SRC_CSS = "src/styles/main.css"  # Custom source
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"  # Standard output
```

### Staging Environment

Balanced between dev flexibility and prod stability:

```python
# settings/staging.py
TAILWIND_CLI_VERSION = "4.1.3"  # Pin to stable version
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = True  # Allow downloads
TAILWIND_CLI_DIST_CSS = "css/tailwind.min.css"  # Minified output
```

### Production Environment

Maximum performance and reliability:

```python
# settings/production.py
TAILWIND_CLI_VERSION = "4.1.3"  # Pin exact version
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False  # Disable downloads
TAILWIND_CLI_PATH = "/usr/local/bin/tailwindcss"  # Pre-installed CLI
TAILWIND_CLI_DIST_CSS = "css/tailwind.min.css"  # Optimized output
```

## 🐳 Docker Integration

### Multi-stage Dockerfile

Build CSS during image creation:

```dockerfile
# Build stage
FROM python:3.12-slim as builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Copy application code
COPY . .

# Install django-tailwind-cli
RUN uv add django-tailwind-cli

# Build Tailwind CSS
RUN uv run python manage.py tailwind download_cli
RUN uv run python manage.py tailwind build

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Copy built application and static files
COPY --from=builder /app .

# Set environment
ENV TAILWIND_CLI_AUTOMATIC_DOWNLOAD=False

# Run application
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

### Docker Compose Development

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - tailwind_cache:/app/.django_tailwind_cli
    environment:
      - TAILWIND_CLI_VERSION=latest
      - TAILWIND_CLI_AUTOMATIC_DOWNLOAD=true
    command: python manage.py tailwind runserver 0.0.0.0:8000

volumes:
  tailwind_cache:
```

## 🔧 CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install uv
        uses: astral-sh/setup-uv@v1

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Download Tailwind CLI
        run: uv run python manage.py tailwind download_cli

      - name: Build CSS
        run: uv run python manage.py tailwind build

      - name: Run tests
        run: uv run pytest
```

### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

variables:
  TAILWIND_CLI_VERSION: "4.1.3"
  TAILWIND_CLI_AUTOMATIC_DOWNLOAD: "false"

build_css:
  stage: build
  image: python:3.12-slim
  before_script:
    - pip install uv
    - uv sync --all-extras
  script:
    - uv run python manage.py tailwind download_cli
    - uv run python manage.py tailwind build
  artifacts:
    paths:
      - assets/css/
    expire_in: 1 hour
```

## ⚙️ Advanced Settings

### Custom CSS Processing

```python
# settings.py
TAILWIND_CLI_SRC_CSS = "src/styles/main.css"

# Content of src/styles/main.css
"""
@import 'tailwindcss';

/* Custom base styles */
@layer base {
  html {
    scroll-behavior: smooth;
  }

  body {
    @apply font-sans antialiased;
  }
}

/* Custom components */
@layer components {
  .btn-primary {
    @apply bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded;
  }
}

/* Custom utilities */
@layer utilities {
  .text-shadow {
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
  }
}
"""
```

### DaisyUI with Custom Theme

```python
# settings.py
TAILWIND_CLI_USE_DAISY_UI = True
TAILWIND_CLI_SRC_CSS = "src/styles/daisyui.css"

# Content of src/styles/daisyui.css
"""
@import 'tailwindcss';

:root {
  --primary: #3b82f6;
  --primary-content: #ffffff;
  --secondary: #1f2937;
  --accent: #10b981;
  --neutral: #374151;
  --base-100: #ffffff;
  --base-200: #f3f4f6;
  --base-300: #e5e7eb;
}

/* Custom DaisyUI theme overrides */
[data-theme="custom"] {
  --primary: #7c3aed;
  --secondary: #ec4899;
}
"""
```

### Multiple CSS Outputs

For complex applications with multiple sections:

```python
# settings/base.py
STATICFILES_DIRS = [
    BASE_DIR / "assets",
    BASE_DIR / "admin_assets",
]

# Main application CSS
TAILWIND_CLI_DIST_CSS = "css/app.css"

# For admin customization, use separate management command
# python manage.py tailwind build --output admin_assets/css/admin.css
```

## 🎯 Framework Integration

### Django Rest Framework

```python
# settings.py for DRF projects
INSTALLED_APPS = [
    'rest_framework',
    'django_tailwind_cli',
    # ... other apps
]

# Separate CSS for API documentation
TAILWIND_CLI_SRC_CSS = "src/styles/api.css"
TAILWIND_CLI_DIST_CSS = "css/api.css"
```

### Django CMS

```python
# settings.py for Django CMS
CMS_TEMPLATES = [
    ('cms/base.html', 'Base Template'),
    ('cms/content.html', 'Content Template'),
]

# Include Tailwind in CMS templates
TAILWIND_CLI_DIST_CSS = "css/cms.css"

# cms/base.html
"""
{% load tailwind_cli cms_tags %}
<!DOCTYPE html>
<html>
<head>
    {% tailwind_css %}
    {% render_block "css" %}
</head>
<body class="bg-gray-50">
    {% cms_toolbar %}
    <main class="container mx-auto">
        {% placeholder "content" %}
    </main>
</body>
</html>
"""
```

## 📊 Monitoring and Debugging

### Performance Monitoring

```python
# settings.py
import logging

# Enable verbose logging for Tailwind
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'tailwind.log',
        },
    },
    'loggers': {
        'django_tailwind_cli': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

### Development Debug Commands

```bash
# Check current configuration
python manage.py tailwind config

# List all scanned templates
python manage.py tailwind list_templates --verbose

# Build with detailed output
python manage.py tailwind build --verbose

# Performance optimization tips
python manage.py tailwind optimize

# Troubleshoot common issues
python manage.py tailwind troubleshoot
```

## 🌐 Multi-tenant Applications

### Tenant-specific CSS

```python
# settings.py for multi-tenant apps
def get_tenant_css_path():
    from django.db import connection
    tenant = getattr(connection, 'tenant', None)
    if tenant:
        return f"css/{tenant.schema_name}.css"
    return "css/default.css"

TAILWIND_CLI_DIST_CSS = get_tenant_css_path()
```

### Shared Base + Tenant Customization

```python
# Base CSS for all tenants
TAILWIND_CLI_SRC_CSS = "src/styles/base.css"

# Tenant-specific overrides in separate files
# Load order: base.css -> tenant-specific.css
```

## 🔒 Security Considerations

### Content Security Policy

```python
# settings.py
CSP_STYLE_SRC = [
    "'self'",
    "'unsafe-inline'",  # Required for Tailwind's utility classes
]

# Better: Use nonce for inline styles
CSP_STYLE_SRC = ["'self'", "'nonce-{nonce}'"]
```

### Static File Security

```python
# settings.py
# Ensure static files are served securely
SECURE_STATIC_URL = True
STATIC_URL = '/static/'

# Use CDN for production
if not DEBUG:
    STATIC_URL = 'https://cdn.example.com/static/'
```

This configuration guide covers the most common advanced scenarios you'll encounter when deploying django-tailwind-cli in production environments.
