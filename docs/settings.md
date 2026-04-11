# Settings & Configuration

## Settings

The package can be configured by a few settings, which can be overwritten in the `settings.py` of
your project.

### TAILWIND_CLI_VERSION

**Default**: `"latest"`

This defines the version of the CLI and of Tailwind CSS you want to use in your project.

If it is set to `latest`, the management commands try to determine the most recent version of Tailwind CSS by placing a request to GitHub and parse the location header of the redirect. If this is not possible a fallback version is used. This version is defined in the module `django_tailwind_cli.config`.

If you want to pinpoint your setup to certain version of Tailwind CSS, then you can set `TAILWIND_CLI_VERSION`to a fixed version number.

For example:
```python
TAILWIND_CLI_VERSION = "4.1.0"
```

### TAILWIND_CLI_PATH

**Default**: `.django_tailwind_cli`

This allows you to override the default of the library where to store the CLI binary.

The default behaviour is to store the CLI binary in the hidden directory `.django_tailwind_cli` within the project.

But if you want to store it elsewhere or plan to use a custom build binary stored locally, change this setting either to a path to a directory or the full path to the binary. If it points to a directory, this is the download destination otherwise it directly tries to use the referenced binary.

:::{warning}
If you use the new option from **2.7.0** but haven't installed a binary before running any of the management commands, these commands will treat the configured path as a directory and create it, if it is missing. Afterwards the official CLI will be downloaded to this path.

In case you want to use the new behaviour, it is highly recommended to also set the new setting `TAILWIND_CLI_AUTOMATIC_DOWNLOAD` to `False`.
:::

### TAILWIND_CLI_AUTOMATIC_DOWNLOAD

**Default**: `True`

Enable or disable the automatic downloading of the official CLI to your machine.

### TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS

**Default**: `False` (opt-in)

When enabled, the auto-generated default source CSS file gains one `@source` directive per installed Django app whose path lives **outside** `BASE_DIR` **and** outside every known site-packages directory. This covers exactly one real-world case: editable-installed packages that ship with their own templates, e.g. `pip install -e ../my-ui-library`.

Why it matters: Tailwind CSS 4.x discovers source files by walking the current working directory tree. Apps installed as editable packages from a sibling repository sit outside that tree and are therefore invisible to Tailwind unless declared explicitly. Turning this setting on makes `django-tailwind-cli` emit the declarations for you, using absolute paths that Tailwind can follow.

```python
# settings.py
TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS = True
```

With the setting enabled and an editable package `extra` installed, the auto-generated `source.css` looks like:

```css
@import "tailwindcss";

/* Auto-generated: installed apps outside BASE_DIR and site-packages. */
@source "/absolute/path/to/editable/extra";
```

:::{note}
The directive points at the app base dir, not at a glob. Tailwind CSS 4.x walks the directory and applies its own exclusions (`.gitignore`, binaries, etc.) — this also means class names embedded in Python files (e.g. form widget `attrs={"class": "..."}` strings) are picked up automatically.
:::

:::{warning}
This setting only affects the **auto-generated** default source CSS. If you set `TAILWIND_CLI_SRC_CSS` to point at a hand-written CSS file, that file is left untouched — add the `@source` directives yourself if you need them.
:::

The list of external apps is re-evaluated whenever the source CSS is written. When combined with the `tailwind watch` auto-reloader, installing a new app or editing `INSTALLED_APPS` automatically regenerates the declarations and triggers a Tailwind rebuild.

### TAILWIND_CLI_USE_SYSTEM_BINARY

**Default**: `False`

If set to `True`, the library uses a Tailwind CSS CLI that is already installed on your system's `PATH` (for example via [Homebrew](https://formulae.brew.sh/formula/tailwindcss) or a system package manager) instead of downloading its own copy. The binary is resolved with Python's `shutil.which()`, so it works on any platform as long as the executable is reachable via `PATH`.

When enabled:

- The automatic download is skipped entirely — no network calls, no files created under `TAILWIND_CLI_PATH`.
- `python manage.py tailwind remove_cli` refuses to delete the binary (since the library did not install it).
- If `TAILWIND_CLI_VERSION` is pinned to a specific version and the system binary reports a different version, a warning is emitted so you can reconcile the discrepancy. No warning is issued when `TAILWIND_CLI_VERSION = "latest"`.

```python
# settings.py
TAILWIND_CLI_USE_SYSTEM_BINARY = True
```

:::{warning}
`TAILWIND_CLI_USE_SYSTEM_BINARY` is **mutually exclusive** with `TAILWIND_CLI_PATH`. Use one or the other.
:::

### TAILWIND_CLI_SYSTEM_BINARY_NAME

**Default**: `"tailwindcss"` (or `"tailwindcss-extra"` when `TAILWIND_CLI_USE_DAISY_UI = True`)

Overrides the executable name that is looked up on `PATH` when `TAILWIND_CLI_USE_SYSTEM_BINARY = True`. You rarely need to set this — the default picks the right name automatically.

```python
# settings.py
TAILWIND_CLI_USE_SYSTEM_BINARY = True
TAILWIND_CLI_SYSTEM_BINARY_NAME = "my-tailwindcss"  # optional
```

### TAILWIND_CLI_AUTOMATIC_MINIFY

**Default**: `True`

Controls whether `python manage.py tailwind build` passes `--minify` to the Tailwind CLI. Set to `False` if your asset pipeline already minifies CSS (for example when using `django-compressor` or a CDN transform) so you don't minify twice.

This setting only changes the default; the `build` command also accepts an explicit `--minify` / `--no-minify` flag which takes precedence.

### TAILWIND_CLI_SRC_REPO

**Default**: `"tailwindlabs/tailwindcss"`

Specifies the repository from which the CLI is downloaded. This is useful if you are using a customized version of the CLI, such as [tailwind-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra).

:::{warning}
If you use this option, ensure that you update the `TAILWIND_CLI_VERSION` to match the version of the customized CLI you are using. Additionally, you may need to update the `TAILWIND_CLI_ASSET_NAME` if the asset name is different. See the example below.
:::

### TAILWIND_CLI_ASSET_NAME

**Default**: `"tailwindcss"`

Specifies the name of the asset to download from the repository.

This option is particularly useful if the customized repository you are using has a different name for the Tailwind CLI asset. For example, the asset name for [tailwind-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/) is `tailwindcss-extra`.

:::{note}
Here is a full example of using a custom repository and asset name:
```python
TAILWIND_CLI_SRC_REPO = "dobicinaitis/tailwind-cli-extra"
TAILWIND_CLI_ASSET_NAME = "tailwindcss-extra"
```
:::

### TAILWIND_CLI_SRC_CSS

**Default**: `".django_tailwind_cli/source.css"` (relative to `BASE_DIR`, auto-created on first use)

Path to the Tailwind CSS input file. The library manages the default file itself — it writes a minimal `@import "tailwindcss";` (plus `@plugin "daisyui";` if DaisyUI is enabled) into `<BASE_DIR>/.django_tailwind_cli/source.css` on first run and updates it when the auto-generated content drifts.

Set this to point at a hand-written file if you need custom CSS alongside the Tailwind import. When `TAILWIND_CLI_SRC_CSS` is set, the library only creates the file if it doesn't yet exist and never overwrites it afterwards — you own it. A relative path is resolved against `settings.BASE_DIR`, an absolute path is used as-is.

### TAILWIND_CLI_DIST_CSS

**Default**: `"css/tailwind.css"`

The name of the output file. This file is stored relative to the first element of the
`STATICFILES_DIRS` array.

### TAILWIND_CLI_CSS_MAP

**Default**: `None`

A list of tuples defining multiple CSS source/destination pairs. Each tuple contains:
- Source CSS file path (relative to `BASE_DIR`)
- Destination CSS file path (relative to `STATICFILES_DIRS[0]`)

```python
TAILWIND_CLI_CSS_MAP = [
    ("admin.css", "admin.output.css"),
    ("web.css", "web.output.css"),
]
```

:::{warning}
This setting is **mutually exclusive** with `TAILWIND_CLI_SRC_CSS` and `TAILWIND_CLI_DIST_CSS`.
You cannot use both configuration modes at the same time. If `TAILWIND_CLI_CSS_MAP` is defined,
the single-file settings will be ignored and a warning will be raised.
:::

The entry name is derived from the source filename (without extension). This name can be used
with the `{% tailwind_css %}` template tag to include specific CSS files.

### TAILWIND_CLI_USE_DAISY_UI

**Default**: `False`

This switch determines what content is written to `TAILWIND_CLI_SRC_CSS` if it is automatically created by the library.

The default is:
```css
@import "tailwindcss";
```

If `TAILWIND_CLI_USE_DAISY_UI = True` is put into the `settings.py` of your project, this is the output:
```css
@import "tailwindcss";
@plugin "daisyui";
```

This switch can also be used as a shortcut to activate daisyUI and change `TAILWIND_CLI_SRC_REPO` and `TAILWIND_CLI_ASSET_NAME` as described above to fetch [tailwind-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/).

## Configuration Patterns

### Default

The library works out of the box with sensible defaults. No configuration is required:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "django_tailwind_cli",
]

STATICFILES_DIRS = [BASE_DIR / "assets"]
```

### Custom Source CSS

Using a custom source CSS file for additional Tailwind configuration:

```python
# settings.py
TAILWIND_CLI_SRC_CSS = "src/styles/main.css"
```

Example content of `src/styles/main.css`:

```css
@import "tailwindcss";

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
```

### DaisyUI

If you plan to use [daisyUI](https://daisyui.com), there is an easy way to solve this with this library.

```python
TAILWIND_CLI_USE_DAISY_UI = True
```

Setting this, the library switches from using the default TailwindCSS CLI to the one provided by [Andris Dobičinaitis](https://github.com/dobicinaitis) and his [tailwind-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra) project. It also causes the library to create a proper default config that activates the daisyUI plugin.

But of course you can do it manually, too. Just configure a repository where the library should pull the CLI from and activate the daisyUI support.

```python
TAILWIND_CLI_SRC_REPO = "dobicinaitis/tailwind-cli-extra"
TAILWIND_CLI_ASSET_NAME = "tailwindcss-extra"
TAILWIND_CLI_USE_DAISY_UI = True
```

Or provide your custom configuration, too.

```python
TAILWIND_CLI_SRC_REPO = "dobicinaitis/tailwind-cli-extra"
TAILWIND_CLI_ASSET_NAME = "tailwindcss-extra"
TAILWIND_CLI_SRC_CSS = "src/styles/daisyui.css"
```

Example content of `src/styles/daisyui.css` with theme configuration:

```css
@import "tailwindcss";

@plugin "daisyui" {
  themes: nord --default, abyss --prefersdark, cupcake, dracula;
}
```

For more configuration options, see the [DaisyUI Configuration Documentation](https://daisyui.com/docs/config/).

### Multiple CSS Entry Points

For projects that need separate CSS files for different parts of the application (e.g., admin panel and public website):

```python
# settings.py
TAILWIND_CLI_CSS_MAP = [
    ("styles/admin.css", "css/admin.css"),
    ("styles/web.css", "css/web.css"),
]
```

Example source files:

`styles/admin.css`:
```css
@import "tailwindcss";

@source "../templates/admin/**/*.html";

@layer components {
  .admin-panel {
    @apply bg-gray-100 p-4 rounded-lg;
  }
}
```

`styles/web.css`:
```css
@import "tailwindcss";

@source "../templates/web/**/*.html";

@layer components {
  .hero-section {
    @apply bg-gradient-to-r from-blue-500 to-purple-600;
  }
}
```

In your templates, include all CSS files or filter by name:

```htmldjango
{# Include all CSS files #}
{% tailwind_css %}

{# Include only admin CSS #}
{% tailwind_css "admin" %}

{# Include only web CSS #}
{% tailwind_css "web" %}
```

The `build` command processes all entries, and the `watch` command monitors all source files simultaneously.

### Using a Homebrew-installed Tailwind CSS CLI

If you have already installed `tailwindcss` through [Homebrew](https://formulae.brew.sh/formula/tailwindcss) (or any other package manager that puts it on your `PATH`), you can skip the automatic download entirely:

```bash
brew install tailwindcss
```

```python
# settings.py
TAILWIND_CLI_USE_SYSTEM_BINARY = True
```

That's it — the library resolves `tailwindcss` via `PATH` on every invocation and runs your builds against that binary. Pairs well with `TAILWIND_CLI_VERSION = "latest"` so you don't have to update two places when Homebrew bumps the version.

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
