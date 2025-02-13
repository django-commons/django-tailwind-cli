---
hide:
  - navigation
---

# Settings & Configuration

## Settings

The package can be configured by a few settings, which can be overwritten in the `settings.py` of
your project.

`TAILWIND_CLI_VERSION`
: **Default**: `"latest"`

    This defines the version of the CLI and of Tailwind CSS you want to use in your project.

    If it is set to `latest`, the management commands try to determine the most recent version of Tailwind CSS by placing a request to GitHub and parse the location header of the redirect. If this is not possible a fallback version is used. This version is defined in the module `django_tailwind_cli.config`.

    If you want to pinpoint your setup to certain version of Tailwind CSS, then you can set `TAILWIND_CLI_VERSION`to a fixed version number.

    For example:
    ```python
    TAILWIND_CLI_VERSION = "3.4.17"
    ```

`TAILWIND_CLI_PATH`
: **Default**: `"~/.local/bin/"`

    The path where to store CLI binary on your machine or the path to an manually installed binary.

    The default behaviour is, that `TAILWIND_CLI_PATH` should point to a directory, where
    `django-tailwind-cli` is allowed to download the official CLI to. Normally, this library tries
    to manage the tailwind CLI by itself and don't rely on externally installed versions of it.

    Starting with version **2.7.0** TAILWIND_CLI_PATH can also point to an existing binary, in case
    you want to install it using some package manager or if you have installed `tailwindcss`
    globally with `npm` along with some plugins you want to use.

    !!! warning

        If you use the new option from **2.7.0** but haven't installed a binary before running any of the management commands, these commands will treat the configured path as a directory and create it, if it is missing. Afterwards the official CLI will be downloaded to this path.

        In case you want to use the new behaviour, it is highly recommended to also set the new setting `TAILWIND_CLI_AUTOMATIC_DOWNLOAD` to `False`.

`TAILWIND_CLI_SRC_REPO`
: **Default**: `"tailwindlabs/tailwindcss"`

    Specifies the repository from which the CLI is downloaded. This is useful if you are using a customized version of the CLI, such as [tailwind-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra).

    !!! warning

        If you use this option, ensure that you update the `TAILWIND_CLI_VERSION` to match the version of the customized CLI you are using. Additionally, you may need to update the `TAILWIND_CLI_ASSET_NAME` if the asset name is different. See the example below.

`TAILWIND_CLI_ASSET_NAME`:
: **Default**: `"tailwindcss"`

    Specifies the name of the asset to download from the repository. This option is particularly useful if the customized repository you are using has a different name for the Tailwind CLI asset. For example, the asset name for [tailwind-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/) is `tailwindcss-extra`.

    !!! Note

        Here is a full example of using a custom repository and asset name:

        ```python
        TAILWIND_CLI_SRC_REPO = "dobicinaitis/tailwind-cli-extra"
        TAILWIND_CLI_ASSET_NAME = "tailwindcss-extra"
        TAILWIND_CLI_VERSION = "1.7.12"
        ```

`TAILWIND_CLI_AUTOMATIC_DOWNLOAD`
: **Default**: `True`

    Enable or disable the automatic downloading of the official CLI to your machine.

`TAILWIND_CLI_SRC_CSS`
: **Default** (for Tailwind 3.x): `None`<br>**Default** (for Tailwind 4.x): `css/source.css`

    !!! warning
        This setting is optional for Tailwind CSS 3.x. For Tailwind CSS 4.x it must not be empty.

    For **Tailwind CSS 3.x** this optional file is used to define addition CSS rules for your project.

    For **Tailwind CSS 4.x** this required file is used to configure Tailwind CSS and also add
    additional CSS rules for your project. This file is stored relative to the first element of
    the `STATICFILES_DIRS` array.

`TAILWIND_CLI_DIST_CSS`
: **Default**: `"css/tailwind.css"`

    The name of the output file. This file is stored relative to the first element of the
    `STATICFILES_DIRS` array.

`TAILWIND_CLI_CONFIG_FILE`
: **Default**: `"tailwind.config.js"`

    !!! danger

        Is only required for Tailwind CSS 3.x. If you use it with Tailwind CSS 4.x, it is ignored
        and also raises an exception to force you to remove it.

    The name of the Tailwind CLI config file. The file is stored relative to the `BASE_DIR` defined
    in your settings.

## `tailwind.config.js` (Tailwind CSS 3.x only)

If you don't create a `tailwind.config.js` file yourself, the management commands will create a sane default for you inside the `BASE_DIR` of your project. The default activates all the official plugins for Tailwind CSS and adds a minimal plugin to support some variants for [HTMX](https://htmx.org/).

### Default version

```javascript title="tailwind.config.js"
/** @type {import('tailwindcss').Config} */
const plugin = require("tailwindcss/plugin");

module.exports = {
  content: ["./templates/**/*.html", "**/templates/**/*.html", '**/*.py'],
  theme: {
    extend: {},
  },
  plugins: [
    require("@tailwindcss/typography"),
    require("@tailwindcss/forms"),
    require("@tailwindcss/aspect-ratio"),
    require("@tailwindcss/container-queries"),
    plugin(function ({ addVariant }) {
      addVariant("htmx-settling", ["&.htmx-settling", ".htmx-settling &"]);
      addVariant("htmx-request", ["&.htmx-request", ".htmx-request &"]);
      addVariant("htmx-swapping", ["&.htmx-swapping", ".htmx-swapping &"]);
      addVariant("htmx-added", ["&.htmx-added", ".htmx-added &"]);
    }),
  ],
};
```
