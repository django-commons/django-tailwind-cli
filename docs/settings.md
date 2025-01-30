---
hide:
  - navigation
---

# Settings & Configuration

## Settings

The package can be configured by a few settings, which can be overwritten in the `settings.py` of
your project.

`TAILWIND_CLI_VERSION`
: **Default**: `"3.4.13"`

    This defines the version of the CLI and of Tailwind CSS you want to use in your project.

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
: **Default**: `None`

    The name of the optional input file for the Tailwind CLI, where all the directivces and custom styles are defined. This is where you add your own definitions for the different layers.

    If you don't define this setting, the default of the Tailwind CLI is used.

`TAILWIND_CLI_DIST_CSS`
: **Default**: `"css/tailwind.css"`

    The name of the output file. This file is stored relative to the first element of the `STATICFILES_DIRS` array.

`TAILWIND_CLI_CONFIG_FILE`
: **Default**: `"tailwind.config.js"`

    The name of the Tailwind CLI config file. The file is stored relative to the `BASE_DIR` defined in your settings.

## `tailwind.config.js`

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

### Fancier version of `tailwind.config.js`

This configuration also embraces the nice trick authored by Carlton Gibson in his post [Using Django’s template loaders to configure Tailwind¶](https://noumenal.es/notes/tailwind/django-integration/). The implementation adopts Carlton's implementation to honor the conventions of this project. If you put your `tailwind.config.js` in a different location than your `BASE_DIR`, you have to change this file too.

This configuration uses the management command `tailwind list_templates`, which list all the templates files inside your project.

!!! warning "Editor Integration besides VS Code"

    The following default configuration tries to be as smart as possible to find all the templates inside your project and installed dependencies. This works like a charm when you run the debug server using `python manage.py tailwind runserver`. It also works if you start VSCode with `code .` from within the active virtual environment.

    But it does not work with Sublime Text and the lsp-tailwindcss package or with the various LSP packages for (neo)vim. The reason is, that these intergrations not honoring the active virtual environment when being started. If you have an idea to solve this, patches are welcome.

    **With editors besides VS Code please use the default config.**

```javascript title="tailwind.config.js"
/** @type {import('tailwindcss').Config} */
const plugin = require("tailwindcss/plugin");
const { spawnSync } = require("child_process");

// Calls Django to fetch template files
const getTemplateFiles = () => {
  const command = "python3";
  const args = ["manage.py", "tailwind", "list_templates"];
  // Assumes tailwind.config.js is located in the BASE_DIR of your Django project.
  const options = { cwd: __dirname };

  const result = spawnSync(command, args, options);

  if (result.error) {
    throw result.error;
  }

  if (result.status !== 0) {
    console.log(result.stdout.toString(), result.stderr.toString());
    throw new Error(
      `Django management command exited with code ${result.status}`
    );
  }

  const templateFiles = result.stdout
    .toString()
    .split("\n")
    .map((file) => file.trim())
    .filter(function (e) {
      return e;
    }); // Remove empty strings, including last empty line.
  return templateFiles;
};

module.exports = {
  content: [].concat(getTemplateFiles()),
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
