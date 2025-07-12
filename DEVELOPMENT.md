# Development Workflow & Debugging Guide

This guide provides comprehensive debugging strategies and development workflows for django-tailwind-cli.

## 🚀 Development Workflow

### 1. Initial Setup Workflow

```bash
# Step 1: Install and configure
pip install django-tailwind-cli
python manage.py tailwind setup  # Interactive setup

# Step 2: Verify configuration
python manage.py tailwind config

# Step 3: Start development
python manage.py tailwind runserver
```

### 2. Daily Development Routine

```bash
# Morning startup
python manage.py tailwind runserver  # Starts both Django and Tailwind

# Alternative: Separate terminals
python manage.py tailwind watch     # Terminal 1: CSS watching
python manage.py runserver          # Terminal 2: Django server
```

### 3. Template Development Pattern

1. **Create/Edit Template**
   ```html
   <!-- templates/myapp/page.html -->
   {% extends "base.html" %}

   {% block content %}
   <div class="max-w-4xl mx-auto p-6">
     <h1 class="text-3xl font-bold text-gray-900">New Page</h1>
   </div>
   {% endblock %}
   ```

2. **Verify Template Scanning**
   ```bash
   python manage.py tailwind list_templates --verbose
   ```

3. **Build and Test**
   ```bash
   # CSS rebuilds automatically with watch mode
   # Or manually: python manage.py tailwind build
   ```

## 🔍 Debugging Guide

### Common Issues and Solutions

#### Issue 1: CSS Not Updating

**Symptoms:**
- Changes to templates don't reflect in CSS
- New Tailwind classes not appearing

**Debugging Steps:**
```bash
# 1. Check if templates are being scanned
python manage.py tailwind list_templates --verbose

# 2. Force rebuild CSS
python manage.py tailwind build --force

# 3. Check file modification times
python manage.py tailwind config

# 4. Verify file watching
python manage.py tailwind watch --verbose
```

**Common Causes:**
- Template not in scanned directories
- File permission issues
- Cache not being cleared
- Browser cache holding old CSS

#### Issue 2: Build Failures

**Symptoms:**
- Build command fails with errors
- CLI download issues

**Debugging Steps:**
```bash
# 1. Check configuration
python manage.py tailwind config

# 2. Download CLI manually
python manage.py tailwind download_cli

# 3. Check CLI permissions
ls -la .django_tailwind_cli/

# 4. Verbose build output
python manage.py tailwind build --verbose
```

#### Issue 3: Performance Issues

**Symptoms:**
- Slow build times
- High CPU usage during development

**Debugging Steps:**
```bash
# 1. Check what's being scanned
python manage.py tailwind list_templates --verbose

# 2. Monitor build performance
python manage.py tailwind build --verbose

# 3. Get optimization tips
python manage.py tailwind optimize

# 4. Profile template scanning
time python manage.py tailwind list_templates
```

### Advanced Debugging Techniques

#### 1. Verbose Logging

Enable detailed logging for troubleshooting:

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django_tailwind_cli': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

#### 2. CLI Process Debugging

Monitor the Tailwind CLI process:

```bash
# Check running processes
ps aux | grep tailwind

# Monitor file system events
# macOS
sudo fs_usage -w -f filesystem | grep tailwind

# Linux
sudo inotifywait -m -r --format '%T %w %f %e' --timefmt '%H:%M:%S' assets/
```

#### 3. Template Scanning Analysis

Analyze what templates are being scanned:

```bash
# List all templates with details
python manage.py tailwind list_templates --verbose > templates.log

# Check for permission issues
find . -name "*.html" -not -readable

# Verify template directories
python manage.py shell
>>> from django.template.utils import get_app_template_dirs
>>> list(get_app_template_dirs('templates'))
```

## 🛠️ IDE Integration

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
       "**/node_modules/**",
       "**/.django_tailwind_cli/**"
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
         "label": "Tailwind Watch",
         "type": "shell",
         "command": "python",
         "args": ["manage.py", "tailwind", "watch"],
         "group": "build",
         "isBackground": true
       },
       {
         "label": "Tailwind Build",
         "type": "shell",
         "command": "python",
         "args": ["manage.py", "tailwind", "build"],
         "group": "build"
       }
     ]
   }
   ```

### PyCharm Setup

1. **Run Configurations:**
   - Name: Tailwind Watch
   - Script: manage.py
   - Parameters: tailwind watch
   - Environment: Development

2. **File Watchers:**
   - File type: Django Template
   - Scope: Project Files
   - Program: python
   - Arguments: manage.py tailwind build

## 🔧 Development Scripts

### Custom Management Commands

Create project-specific helper commands:

```python
# management/commands/dev_setup.py
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = "Complete development environment setup"

    def handle(self, *args, **options):
        self.stdout.write("Setting up development environment...")

        # Run Tailwind setup
        call_command('tailwind', 'setup')

        # Build initial CSS
        call_command('tailwind', 'build')

        # Run migrations
        call_command('migrate')

        # Create superuser if needed
        call_command('createsuperuser', '--noinput',
                    username='admin', email='admin@example.com')

        self.stdout.write(
            self.style.SUCCESS("Development environment ready!")
        )
```

### Development Helpers

```bash
#!/bin/bash
# scripts/dev.sh - Development helper script

case "$1" in
  "start")
    echo "Starting development environment..."
    python manage.py tailwind runserver
    ;;
  "build")
    echo "Building CSS..."
    python manage.py tailwind build --verbose
    ;;
  "debug")
    echo "Running debug diagnostics..."
    python manage.py tailwind config
    python manage.py tailwind list_templates --verbose
    python manage.py tailwind troubleshoot
    ;;
  "reset")
    echo "Resetting Tailwind environment..."
    rm -rf .django_tailwind_cli/
    python manage.py tailwind download_cli
    python manage.py tailwind build --force
    ;;
  *)
    echo "Usage: $0 {start|build|debug|reset}"
    exit 1
    ;;
esac
```

## 🧪 Testing Strategies

### Unit Testing

Test your templates include Tailwind classes:

```python
# tests/test_templates.py
from django.test import TestCase
from django.template.loader import render_to_string

class TailwindIntegrationTest(TestCase):

    def test_base_template_includes_tailwind(self):
        """Test that base template includes Tailwind CSS."""
        html = render_to_string('base.html')
        self.assertIn('tailwind.css', html)

    def test_tailwind_classes_in_template(self):
        """Test that templates use Tailwind classes."""
        html = render_to_string('myapp/index.html')
        # Check for common Tailwind patterns
        self.assertRegex(html, r'class="[^"]*\b(mx-auto|text-center|bg-\w+)\b[^"]*"')
```

### Integration Testing

Test the full CSS build process:

```python
# tests/test_build_process.py
import subprocess
from django.test import TestCase
from django.conf import settings
from pathlib import Path

class TailwindBuildTest(TestCase):

    def test_css_build_process(self):
        """Test that CSS builds successfully."""
        # Run build command
        result = subprocess.run([
            'python', 'manage.py', 'tailwind', 'build', '--force'
        ], capture_output=True, text=True)

        self.assertEqual(result.returncode, 0)

        # Check that CSS file was created
        css_path = Path(settings.STATICFILES_DIRS[0]) / 'css/tailwind.css'
        self.assertTrue(css_path.exists())

        # Check CSS content
        css_content = css_path.read_text()
        self.assertIn('@media', css_content)  # Should contain media queries
        self.assertGreater(len(css_content), 1000)  # Should have substantial content
```

### Performance Testing

Monitor build performance:

```python
# tests/test_performance.py
import time
import subprocess
from django.test import TestCase

class TailwindPerformanceTest(TestCase):

    def test_build_performance(self):
        """Test that builds complete within reasonable time."""
        start_time = time.time()

        result = subprocess.run([
            'python', 'manage.py', 'tailwind', 'build', '--force'
        ], capture_output=True)

        build_time = time.time() - start_time

        self.assertEqual(result.returncode, 0)
        self.assertLess(build_time, 30)  # Should build in under 30 seconds
```

## 📋 Troubleshooting Checklist

### Before Asking for Help

1. **Check Configuration:**
   ```bash
   python manage.py tailwind config
   ```

2. **Verify Template Scanning:**
   ```bash
   python manage.py tailwind list_templates --verbose
   ```

3. **Test CLI Functionality:**
   ```bash
   python manage.py tailwind download_cli
   python manage.py tailwind build --verbose
   ```

4. **Run Diagnostics:**
   ```bash
   python manage.py tailwind troubleshoot
   ```

5. **Check System Requirements:**
   - Python 3.10+
   - Django 4.0+
   - Sufficient disk space
   - Network access for CLI download

### Information to Include in Bug Reports

```
Environment:
- OS: [macOS/Linux/Windows version]
- Python: [version]
- Django: [version]
- django-tailwind-cli: [version]

Configuration:
- STATICFILES_DIRS: [value]
- TAILWIND_CLI_VERSION: [value]
- Custom settings: [list any custom Tailwind settings]

Command Output:
[Paste output from python manage.py tailwind config]

Error Message:
[Full error message and traceback]

Steps to Reproduce:
1. [First step]
2. [Second step]
3. [etc.]
```

This comprehensive debugging guide should help you resolve most issues and maintain an efficient development workflow with django-tailwind-cli.
