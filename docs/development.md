# Development Workflow

This guide covers development workflows for django-tailwind-cli.

## Initial Setup

```bash
# Step 1: Install and configure
pip install django-tailwind-cli
python manage.py tailwind setup  # Interactive setup

# Step 2: Verify configuration
python manage.py tailwind config

# Step 3: Start development
python manage.py tailwind runserver
```

## Daily Development

```bash
# Morning startup
python manage.py tailwind runserver  # Starts both Django and Tailwind

# Alternative: Separate terminals
python manage.py tailwind watch     # Terminal 1: CSS watching
python manage.py runserver          # Terminal 2: Django server
```

## Template Development

1. **Create/Edit Template**

   ```htmldjango
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

## Troubleshooting Checklist

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
   - Django 4.2+
   - Sufficient disk space
   - Network access for CLI download

### Information to Include in Bug Reports

```text
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
