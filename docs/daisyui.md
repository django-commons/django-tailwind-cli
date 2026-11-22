# Migrating daisyUI to the official Tailwind CLI

`TAILWIND_CLI_USE_DAISY_UI = True` downloads [tailwind-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra) by default.
tailwind-cli-extra is a Tailwind CLI build with daisyUI bundled.
This source is deprecated and will be removed.

The replacement uses the official Tailwind CLI.
daisyUI comes from its own plugin bundles, `daisyui.mjs` and `daisyui-theme.mjs`.
The library downloads them from the [daisyUI releases](https://github.com/saadeghi/daisyui/releases).
Neither setup needs Node.js.

## What you need to change

| Your setup | Changes |
|---|---|
| No `TAILWIND_CLI_SRC_CSS` and no `TAILWIND_CLI_CSS_MAP` | [Settings](#1-change-the-settings) only |
| `TAILWIND_CLI_SRC_CSS` or `TAILWIND_CLI_CSS_MAP` | [Settings](#1-change-the-settings) and [your source CSS](#3-update-your-own-source-css) |
| `TAILWIND_CLI_SRC_REPO` or `TAILWIND_CLI_ASSET_NAME` set for tailwind-cli-extra | Remove both settings |
| `TAILWIND_CLI_USE_SYSTEM_BINARY = True` | Install the official `tailwindcss` binary on `PATH`, then [run `download_cli`](#2-download-the-cli-and-the-plugin) |

`python manage.py check` reports the deprecated setup as `django_tailwind_cli.W002`.

## 1. Change the settings

```python
# settings.py
TAILWIND_CLI_USE_DAISY_UI = True
TAILWIND_CLI_DAISY_UI_SOURCE = "plugin"
```

Remove these settings if you set them for tailwind-cli-extra:

```python
TAILWIND_CLI_SRC_REPO = "dobicinaitis/tailwind-cli-extra"
TAILWIND_CLI_ASSET_NAME = "tailwindcss-extra"
TAILWIND_CLI_SYSTEM_BINARY_NAME = "tailwindcss-extra"
```

`TAILWIND_CLI_VERSION` names a tailwind-cli-extra release in the old setup.
After the switch, it names a Tailwind CSS release.
Check a pinned value before you build.

`TAILWIND_CLI_DAISY_UI_VERSION` pins the daisyUI version.
Its default, `"latest"`, resolves the newest daisyUI release.

```python
TAILWIND_CLI_VERSION = "4.3.5"
TAILWIND_CLI_DAISY_UI_VERSION = "5.8.2"
```

## 2. Download the CLI and the plugin

```bash
python manage.py tailwind download_cli
```

The command downloads the official CLI and both plugin bundles.
The bundles land in `BASE_DIR/.django_tailwind_cli/`.
That directory does not move with `TAILWIND_CLI_PATH`.

`build` and `watch` download missing files too.
They fail instead with `TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False` or `TAILWIND_CLI_USE_SYSTEM_BINARY = True`.
Run `download_cli` in that case, for example in your deployment.

The library puts a `.gitignore` into that directory, so `git add .` skips the bundles.
An offline build keeps the installed bundles when `TAILWIND_CLI_DAISY_UI_VERSION = "latest"`.

## 3. Update your own source CSS

Skip this step if the library writes your source CSS.
It rewrites the managed file on the next build.

A source CSS that the library seeds in plugin mode already uses relative paths.

The official CLI cannot resolve `@plugin "daisyui";` or `@plugin "daisyui/theme";`.
The build fails with this message:

```text
Error: Can't resolve 'daisyui' in '/path/to/project/src/styles'
```

`python manage.py check` reports such a file as `django_tailwind_cli.W003`.
The hint names the replacement lines for that file.

Load the bundle by its path instead.
Use a path relative to the CSS file, so the file works on every machine.
This example is `BASE_DIR/src/styles/main.css`.

Before:

```css
@import "tailwindcss";

@plugin "daisyui" {
  themes: nord --default, abyss --prefersdark;
}
```

After:

```css
@import "tailwindcss";

@source not "../../.django_tailwind_cli/daisyui{,*}.mjs";

@plugin "../../.django_tailwind_cli/daisyui.mjs" {
  themes: nord --default, abyss --prefersdark;
}
```

The plugin options stay the same.
The `@source not` line keeps Tailwind from scanning the bundles.
Without it, the output contains every daisyUI class.

A custom theme loads the second bundle.
It replaces `@plugin "daisyui/theme"`.

Before:

```css
@plugin "daisyui/theme" {
  name: "brand";
  default: true;
  --color-primary: oklch(55% 0.2 260);
}
```

After:

```css
@plugin "../../.django_tailwind_cli/daisyui-theme.mjs" {
  name: "brand";
  default: true;
  --color-primary: oklch(55% 0.2 260);
}
```

`python manage.py tailwind config` prints the absolute path of `daisyui.mjs`.
The file names stay the same across daisyUI versions.
A version change needs no edit of your source CSS.

With `TAILWIND_CLI_CSS_MAP`, update every source file that loads daisyUI.

## 4. Verify

```bash
python manage.py check
python manage.py tailwind build
```

`check` reports neither `W002` nor `W003` after a complete migration.

## Going back

Set `TAILWIND_CLI_DAISY_UI_SOURCE = "extra"` or remove the setting.
Restore `@plugin "daisyui";` in your own source CSS.
The managed source CSS is rewritten on the next build.
