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
    TAILWIND_CLI_VERSION = "4.1.0"
    ```

`TAILWIND_CLI_PATH`
: **Default**: `.django_tailwind_cli`

    This allows you to override the default of the library where to store the CLI binary.

    The default behaviour is to store the CLI binary in the hidden directory `.django_tailwind_cli` within the project.

    But if you want to store it elsewhere or plan to use a custom build binary stored locally, change this setting either to a path to a directory or the full path to the binary. If it points to a directory, this is the download destination otherwise it directly tries to use the referenced binary.

    > [!Warning]
    > If you use the new option from **2.7.0** but haven't installed a binary before running any of the management commands, these commands will treat the configured path as a directory and create it, if it is missing. Afterwards the official CLI will be downloaded to this path.
    >
    > In case you want to use the new behaviour, it is highly recommended to also set the new setting `TAILWIND_CLI_AUTOMATIC_DOWNLOAD` to `False`.

`TAILWIND_CLI_AUTOMATIC_DOWNLOAD`
: **Default**: `True`

    Enable or disable the automatic downloading of the official CLI to your machine.

`TAILWIND_CLI_SRC_REPO`
: **Default**: `"tailwindlabs/tailwindcss"`

    Specifies the repository from which the CLI is downloaded. This is useful if you are using a customized version of the CLI, such as [tailwind-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra).

    > [!Warning]
    > If you use this option, ensure that you update the `TAILWIND_CLI_VERSION` to match the version of the customized CLI you are using. Additionally, you may need to update the `TAILWIND_CLI_ASSET_NAME` if the asset name is different. See the example below.

`TAILWIND_CLI_ASSET_NAME`:
: **Default**: `"tailwindcss"`

    Specifies the name of the asset to download from the repository.

    This option is particularly useful if the customized repository you are using has a different name for the Tailwind CLI asset. For example, the asset name for [tailwind-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/) is `tailwindcss-extra`.

    > [!Note]
    > Here is a full example of using a custom repository and asset name:
    >    ```python
    >    TAILWIND_CLI_SRC_REPO = "dobicinaitis/tailwind-cli-extra"
    >    TAILWIND_CLI_ASSET_NAME = "tailwindcss-extra"
    >    ```

`TAILWIND_CLI_SRC_CSS`
: **Default**: `".django_tailwind_cli/source.css"`

    This variable can be set to a relative path and an absolute path.

    If it is a relative path it is assumed to be relative to `settings.BASE_DIR`. If `settings.BASE_DIR` is not defined or the file doesn't exist a `ValueError` is raised.

    If it is an absolute path, this path is used as the input file for Tailwind CSS CLI. If the path doesn't exist, a `ValueError` is raised.

`TAILWIND_CLI_DIST_CSS`
: **Default**: `"css/tailwind.css"`

    The name of the output file. This file is stored relative to the first element of the
    `STATICFILES_DIRS` array.

`TAILWIND_CLI_USE_DAISY_UI`:
: **Default**: `False`

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
