# Daily Workflow

How to work with django-tailwind-cli day to day: starting the server, editing templates, wiring up your editor, and what to check when something looks wrong. For contributing to the package itself, see [Contributing](contributing.md).

## Initial Setup

```bash
# Step 1: Install and configure
pip install django-tailwind-cli
python manage.py tailwind setup  # Guided setup

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

`tailwind watch` (and the inner watcher spawned by `tailwind runserver`) runs under Django's auto-reloader by default. Any change to a Python file — including `settings.py` — restarts the watcher, regenerates the source CSS file, and respawns the Tailwind CLI subprocess. Pass `--noreload` to disable.

`tailwind runserver` is a transparent wrapper around the underlying Django `runserver` / `runserver_plus` command: every runserver flag except `--force-default-runserver` is forwarded verbatim. Consult `python manage.py runserver --help` (or `runserver_plus --help` with `django-extensions` installed) for the full list of available options.

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

2. **Declare template sources**

   Make sure your Tailwind CSS input file contains `@source` directives for the
   template directories you want scanned. Tailwind CSS 4.x relies on these
   directives exclusively — there is no external template-listing command.

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

2. **Verify Template Sources:**

   Open your Tailwind CSS input file and confirm that every template directory
   you expect to be scanned is referenced by an `@source` directive.

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

### Filing the Report

If the checklist above does not explain the behaviour, open an issue. What to include and what makes
a report easy to act on is described in
[CONTRIBUTING.md](https://github.com/django-commons/django-tailwind-cli/blob/main/CONTRIBUTING.md).
