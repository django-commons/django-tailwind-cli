# Use with WhiteNoise

[WhiteNoise](https://whitenoise.readthedocs.io/) and `django-tailwind-cli` need no special
configuration to work together — the defaults of both packages already fit. What follows is a
working setup plus the places where the two packages surprise people.

## Sample configuration

```python
# settings.py

INSTALLED_APPS = [
    # ...
    "whitenoise.runserver_nostatic",  # before django.contrib.staticfiles
    "django.contrib.staticfiles",
    "django_tailwind_cli",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # directly after SecurityMiddleware
    # ...
]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"  # collectstatic target, not a source directory
STATICFILES_DIRS = [BASE_DIR / "assets"]  # where the CLI writes css/tailwind.css

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

No `TAILWIND_CLI_*` setting is required. The defaults put the source CSS in
`<BASE_DIR>/.django_tailwind_cli/source.css`, outside the static directories, and the build output
in `<STATICFILES_DIRS[0]>/css/tailwind.css` — exactly what the manifest storage expects to collect.
If you override [`TAILWIND_CLI_DIST_CSS`](settings.md#tailwind_cli_dist_css), that path is the one
the rest of this page refers to.

## Build the CSS before `collectstatic`

```shell
python manage.py tailwind build
python manage.py collectstatic --noinput
```

Getting this order wrong does not fail the build. `collectstatic` succeeds, writes a manifest
without an entry for the stylesheet, and the site breaks on the first request that renders
`{% tailwind_css %}`:

```
ValueError: Missing staticfiles manifest entry for 'css/tailwind.css'
```

The quoted path is whatever `TAILWIND_CLI_DIST_CSS` resolves to.

## Keep the source CSS out of the static directories

If [`TAILWIND_CLI_SRC_CSS`](settings.md#tailwind_cli_src_css) points at a file inside
`STATICFILES_DIRS`, `collectstatic` fails:

```
whitenoise.storage.MissingFileError: The file 'css/tailwindcss' could not be found with
<whitenoise.storage.CompressedManifestStaticFilesStorage object at 0x…>.

The CSS file 'css/source.css' references a file which could not be found:
  css/tailwindcss
```

Django's `ManifestStaticFilesStorage`, which WhiteNoise's storage backend extends, rewrites every
`@import "…"` statement in every collected CSS file and expects the target to be another static
file. `@import "tailwindcss";` names a package, not a file, so the lookup fails. The missing name
is reported relative to the source file, so it reads `tailwindcss` for a source CSS at the root of a
static directory and `css/tailwindcss` for one in a `css/` subdirectory.

Put a hand-written source CSS anywhere outside the static directories — the default location already
is. The same applies to every source file listed in
[`TAILWIND_CLI_CSS_MAP`](settings.md#tailwind_cli_css_map).

A Django system check reports this as `django_tailwind_cli.W001`, so you do not have to wait for a
deploy to find out — it runs on `manage.py check`, on `runserver`, and on every `manage.py tailwind`
subcommand. It is a warning rather than an error because without a manifest storage backend the only
consequence is that the source file gets published alongside the build output; silence it through
`SILENCED_SYSTEM_CHECKS` if that is what you want.

## Development

`whitenoise.runserver_nostatic` hands static files to `WhiteNoiseMiddleware` during development.
`WHITENOISE_AUTOREFRESH` and `WHITENOISE_USE_FINDERS` both default to `settings.DEBUG`, so a
stylesheet rebuilt by `tailwind runserver` or `tailwind watch` is picked up on the next request
without restarting the server. Pinning `WHITENOISE_AUTOREFRESH = False` during development serves
the stale file instead.

[django-project-starter](https://github.com/oliverandrich/django-project-starter) is a working
example of this setup.
