---
hide:
  - navigation
---

# Installation

## Install `django-tailwind-cli`

1. Install the library.

   ```shell
   python -m pip install django-tailwind-cli
   ```

   with optional `django-extensions` and `Werkezeug` libraries to use the `runserver_plus` command.

   ```shell
   python -m pip install django-tailwind-cli[django-extensions]
   ```

2. Add `django_tailwind_cli` to `INSTALLED_APPS` in `settings.py`.

   ```python
   INSTALLED_APPS = [
       # other Django apps
       "django_tailwind_cli",
   ]
   ```

   If you plan to use the `runserver_plus` command, the changes to `INSTALLED_APPS` looks like that.

   ```python
   INSTALLED_APPS = [
       # other Django apps
       "django_tailwind_cli",
       "django_extensions,
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

5. Start the debug server or start the Tailwind CLI in watch mode.

   ```shell
   python manage.py tailwind runserver
   ```

   Or

   ```shell
   python manage.py tailwind runserver_plus
   ```

   Or

   ```shell
   python manage.py tailwind watch
   ```

   If you only start the Tailwind CLI in watch mode, you have to start the debug server with the standard command `python manage.py runserver` seperately.

## Optional steps

### Install PyCharm workaround

In order [to use Tailwind CLI with PyCharm](/usage/#use-with-pycharm) you have to install a workaround.

```shell
python manage.py tailwind install_pycharm_workaround
```

### Install `django-browser-reload`

If you enjoy automatic reloading during development. Install the [django-browser-reload](https://github.com/adamchainz/django-browser-reload) app. The following installation steps are taken from the README of the project.

1. Install `django-browser-reload` inside your Django project.

   ```shell
   python -m pip install django-browser-reload
   ```

2. Ensure you have `django.contrib.staticfiles` in your `INSTALLED_APPS`.

3. Add `django_browser_reload` app to your `INSTALLED_APPS`.

   ```python
   INSTALLED_APPS = [
       ...,
       "django_browser_reload",
       ...,
   ]
   ```

4. Include the app URL’s in your root URLconf(s).

   ```python
   from django.urls import include, path

   urlpatterns = [
       ...,
       path("__reload__/", include("django_browser_reload.urls")),
   ]
   ```

5. Add the middleware.

   ```python
   MIDDLEWARE = [
       # ...
       "django_browser_reload.middleware.BrowserReloadMiddleware",
       # ...
   ]
   ```

   The middleware should be listed after any that encodes the response, such as Django’s GZipMiddleware.

   The middleware automatically inserts the required script tag on HTML responses before </body> when DEBUG is True. It does so to every HTML response, meaning it will be included on Django’s debug pages, admin pages, etc. If you want more control, you can instead insert the script tag in your templates—see below.
