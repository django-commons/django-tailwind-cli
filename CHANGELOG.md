# Changelog

## 4.5.1 (2025-12-29)

### 🐛 Bug Fixes
- **Help output**: Fixed crash when running `tailwind` or `tailwind --help` due to typer/rich markup conflict

## 4.5.0 (2025-12-29)

### 🎯 New Features
- **Multiple CSS entry points**: Added `TAILWIND_CLI_CSS_MAP` setting for compiling multiple CSS files in a single project (e.g., separate admin and frontend styles)
- **Template tag enhancement**: `{% tailwind_css %}` now supports optional name parameter for multi-file mode: `{% tailwind_css "admin" %}`

### 🔧 Technical Improvements
- **Django support**: Dropped support for Django 5.1 (now supporting Django 4.2 LTS, 5.2, and 6.0 only)
- **Pre-commit hooks**: Updated uv-secure (0.15.4) and pyright (1.1.407)
- **Security**: Updated Django and Werkzeug to fix security vulnerabilities
- **Documentation**: Migrated from MkDocs to Sphinx with myst-parser and Furo theme
- **Template tag consistency**: Template tag now uses Config class for consistent validation
- **Test coverage**: Added integration tests for multi-file build and watch commands

### 🛠️ Developer Experience
- **Cleanup command**: Added `just clean` target to remove temporary files and build artifacts

## 4.4.2 (2025-09-23)

### 🐛 Bug Fixes
- **Test isolation**: Fixed cache interference in DaisyUI tests causing failures in Django 4.1 with Python 3.10

## 4.4.1 (2025-09-23)

### 🐛 Bug Fixes
- **DaisyUI version detection**: Fixed incorrect version fetching when `TAILWIND_CLI_USE_DAISY_UI = True` enabled

## 4.4.0 (2025-09-21)

### 🔧 Technical Improvements
- **Type safety**: Fixed all pyright typing errors for better code quality and maintainability
- **Code cleanup**: Removed unused functions and improved type annotations throughout codebase
- **Dependencies**: Removed requests dependency, replaced with custom HTTP implementation
- **Exception handling**: Fixed exception naming to follow Python conventions and avoid builtin shadowing
- **Test coverage**: Added comprehensive HTTP module tests, improving coverage from 82% to 85%
- **Error handling**: Complete test coverage for network timeouts, connection errors, and edge cases
- **VS Code integration**: Added PyLance ignore comments for test files accessing private methods
- **Django 6.0 support**: Added Django 6.0 to testing matrix and version compatibility

## 4.3.0 (2025-07-12)

### 🎯 New Features
- **Interactive setup command**: `python manage.py tailwind setup` for guided configuration
- **Configuration viewer**: `python manage.py tailwind config` to inspect current settings
- **Troubleshooting guide**: `python manage.py tailwind troubleshoot` for common issues
- **Performance tips**: `python manage.py tailwind optimize` for optimization guidance
- **Enhanced verbose mode**: `--verbose` flag for detailed build and watch diagnostics

### ⚡ Performance Improvements
- **Smart rebuilds**: File modification checks prevent unnecessary CSS rebuilds
- **Version caching**: 1-hour cache reduces GitHub API requests
- **Process optimization**: Improved `tailwind runserver` with better signal handling
- **File operations**: Optimized I/O with caching and content comparison

### 🛠️ Developer Experience
- **Better error messages**: Actionable solutions for configuration and system issues
- **Colorized output**: Visual feedback with emojis and progress indicators
- **Help text improvements**: Detailed examples and use cases for all commands
- **Template scanning**: Enhanced discovery with error handling and performance metrics

### 📚 Documentation & Resources
- **Comprehensive README**: Step-by-step quick start and feature overview
- **Advanced guides**: CONFIGURATION.md and DEVELOPMENT.md for production deployments
- **Inline documentation**: Detailed docstrings and usage examples throughout codebase

### 🧪 Quality Assurance
- **Comprehensive testing**: 58+ new tests covering integration workflows and error scenarios
- **Cross-platform support**: Windows, macOS, and Linux compatibility testing
- **89% test coverage**: Robust validation of all major functionality

### 🔧 Technical Improvements
- **Python 3.10+ minimum**: Updated supported Python versions to 3.10-3.14
- **Refactored internals**: Better maintainability with focused, single-responsibility functions
- **Type safety**: Improved with `PlatformInfo` and `VersionCache` data structures

## 4.2.4

- Merged pull request [#161](https://github.com/django-commons/django-tailwind-cli/pull/161) by [@adamghill](https://github.com/adamghill) which fixed the [prefix handling for staticfiles diretories](https://docs.djangoproject.com/en/5.2/ref/settings/#prefixes-optional).

## 4.2.3

- Reverted the decision to store the CLI and the default config file in proper platform dirs.

  * Windows has issues with the paths or sometimes it is not possible to create them.
  * VSCode Tailwind Plugin relies on the the existance of the config within the current project.
  * Decision: Create a folder named `.django_tailwind_cli` within the project and store the files there.

## 4.2.2

- Default configuration stored in the user cache directory is overwritten on every start of the debug server or other management command.

## 4.2.1

- Bugfix for determining the latest release of the used version of Tailwind CSS.

## 4.2.0

> [!CAUTION]
> Version 4.2.x and onward only support Tailwind CSS 4.x. If you are using Tailwind CSS 3.x,
> please use version 2.21.1 of this library. Version 4.0.x or 4.1.x still support Tailwind CSS 3.x, but
> these versions are not recommended to use for new projects.

> [!CAUTION]
> This version includes changes to the handling of `TAILWIND_CLI_PATH` and `TAILWIND_CLI_SRC_CSS`.

- Default fallback version is now 4.1.3.
- Removed support for Tailwind CSS 3.x. The main reason is that this makes the library easier to maintain and also add better support for custom CLI builds which support DaisyUI and other plugins.
- django-tailwind-cli now uses proper platform directories to store the CLI binary.

    * The proper directories are powered by [platformdirs](https://pypi.org/project/platformdirs/).
    * `TAILWIND_CLI_PATH` is now optional by default.
    * If `TAILWIND_CLI_PATH` is None, the binary is stored in `user_data_dir("django-tailwind-cli", "django-commons")`.
    * The library doesn't rely anylonger on a properly set `settings.BASE_DIR`.

- `TAILWIND_CLI_ASSET_NAME` is also used for the downloaded CLI to distinguish between `tailwindcss` and `tailwindcss-extra`.
- The behaviour of `TAILWIND_CLI_SRC_CSS` has been changed. The reasoning behind this change was, less default code inside the project and whitenoise had issues with a CSS file inside an asset folder referencing non-existing imports.

    * It defaults to `None`.
    * If it is `None` the default input file is created in the user cache directory.
    * If it is a relative path, this path is considered relative to `settings.BASE_DIR`.
    * The last option is an absolute path.

- Proper daisyUI support using [tailwind-cli-extra](https://github.com/dobicinaitis/tailwind-cli-extra).

## 4.1.0

- TAILWIND_CLI_VERSION defaults to "latest" now. In case it is set to this value,
  django-tailwind-cli tries to determine which version is the latest version of Tailwind CSS. If it is not able to access the internet, it uses a fallback version defined in django_tailwind_cli.config.FALLBACK_VERSION. Currently,
  it is set to 4.0.6.

## 4.0.1

- Various fixes for the documentation.
- Added Django 5.2 to the testing matrix.

## 4.0.0

- Added support for Tailwind CSS 4.0.0.
- Default version is Tailwind CSS 4.0.0.
- The versioning is now aligned with Tailwind CSS. That means the major number of this packages
  follows the major number of Tailwind CSS to document the most recent supported version of Tailwind.
- Removed the management commands `install_pycharm_workaround` and `uninstall_pycharm_workaround`.
  This feature broke too often.
- Removed `runserver_plus` subcommand. The management subcommand `runserver` now starts either the
  debug server from django-extensions if this package is installed. Otherwise it starts the standard
  debug server.
- The management subcommand `runserver` got an option `--force-default-runserver` to enforce the
  usage of the standard debug server from Django.
- `TAILWIND_CLI_CONFIG_FILE` isn't necessary for Tailwind CSS 4.x only for 3.x.
  [Read the documentaiton about it.](https://django-tailwind-cli.rtfd.io/latest/installation/settings)
- Removed the documentation for the fancier `tailwind.config.js` as it is not recommended to use
  and Tailwind CSS 4.x has a way better strategy to find the used Tailwind classes.

## 2.21.1

- Relaxed the minimum Django version to >=4.0.

## 2.21.0

- Added `install_pycharm_workaround` and `remove_pycharm_workaround` management commands.
  [#142](https://github.com/django-commons/django-tailwind-cli/issues/142)
- Added `remove_cli` subcommand to remove the CLI.
  [#132](https://github.com/django-commons/django-tailwind-cli/issues/132)
- Refactored all the class based management command into simpler function based commands.
- Refactored the process to build the runserver command.

## 2.20.2

- Added testpypi release workflow.

## 2.20.1

- Fixed a critical issue of 2.20.0.

## 2.20.0

- Removed django-appconf again.
- Switched from pyright to mypy for type checking.
- Fixed broken links in the documentation.
- Bumped default version of Tailwind CSS to 3.4.13.
- Bumped minimum version of certifi to 2024.8.30. Removed the upper boundary of the version number.

## 2.19.0

- Transfered the project to django-commons.

## 2.18.1

- Fixed the URLs for PyPI.

## 2.18.0

- Added Python 3.13 support.
- Moved documentation from django-tailwind-cli.andrich.me -> django-tailwind-cli.rtfd.io
- Documentation fixes.

## 2.17.0

- Internal refactoring. Config class has been replaced with django-appconfig and some function in
  the django_tailwind_cli.utils package.
- uv is used for publishing too.
- Updated tooling configuration.

## 2.16.0

- Set the minimum supported version of Python to 3.9.
- Set the minimum supported version of Django to 4.2.
- Switched the tooling completely to [uv](https://docs.astral.sh/uv/).
- Bumped the default version of Tailwind CSS to 3.4.11.

## 2.15.0

- [#130](https://github.com/oliverandrich/django-tailwind-cli/pull/130) by
  [@Tobi-De](https://github.com/Tobi-De) extended the support for custom tailwind cli builds. See
  `TAILWIND_CLI_SRC_REPO` and `TAILWIND_CLI_ASSET_NAME` in the documentation.

## 2.14.0

- [#129](https://github.com/oliverandrich/django-tailwind-cli/pull/129) by
  [@Tobi-De](https://github.com/Tobi-De) add a setting to allow for custom tailwind source repo
- Bumped default version of tailwindcss to 3.4.10.

## 2.13.0

- [#127](https://github.com/oliverandrich/django-tailwind-cli/pull/127) by
  [@bckohan](https://github.com/bckohan) upgrade django-typer and fixed future incompatibilities
  with django-typer 3.0.
- moved to tox for testing.
- Added Python 3.13 to the test matrix.
- Added Django 5.1a1 to the test matrix.
- Bumped default version of tailwindcss to 3.4.4.

## 2.12.0

- Reintroduced support for Python 3.8. Seems as I have to support than I want to.
- Added justfile to ease management of package and dev environment.

## 2.11.1

- Changed project tooling to uv, nox and flit.
- Bumped default version of tailwindcss to 3.4.3.

## 2.11.0

- Switched default configuration for tailwind to the less opinionated default version.

## 2.10.0

- Added `download_cli` management command.

## 2.9.0

- Bumped default Tailwind CLI version to 3.4.1.
- Reimplemented the management command using
  [django_typer](https://django-typer.readthedocs.io/en/stable/)
- Removed Python 3.8 from the list of supported versions.

## 2.8.1

- [#83](https://github.com/oliverandrich/django-tailwind-cli/pull/83)
  by [@lgp171188](https://github.com/lgp171188) fixed some documentation errors.

## 2.8.0

- Bumped default Tailwind CLI version to 3.4.0.

## 2.7.3

- [#80](https://github.com/oliverandrich/django-tailwind-cli/pull/80)
  by [@joshuadavidthomas](https://github.com/joshuadavidthomas) added document for using the
  management commands inside a docker container.
- [#81](https://github.com/oliverandrich/django-tailwind-cli/pull/81)
  by [@joshuadavidthomas](https://github.com/joshuadavidthomas) fixed typos in the documentation.

## 2.7.2

- Fixed broken commit for 2.7.1. Sorry guys.

## 2.7.1

- Bumped default Tailwind CLI version to 3.3.6.

## 2.7.0

- Added more command line arguments to `tailwind runserver` and `tailwind runserver_plus`.
  - `tailwind runserver`
    - `--skip-checks` [#69](https://github.com/oliverandrich/django-tailwind-cli/issues/69)
    - `--noreload`
    - `--nothreading`
    - `--ipv6`
  - `tailwind runserver_plus`
    - `--noreload`
    - `--nothreading`
    - `--ipv6`
    - `--pdb`
    - `--ipdb`
    - `--pm`
    - `--print-sql`
- Fixed [#67](https://github.com/oliverandrich/django-tailwind-cli/issues/67) to fetch the correct
  CLI on the Windows platform.
- `TAILWIND_CLI_PATH` can also point to a pre-installed binary from a package manager.
- Added a new setting `TAILWIND_CLI_AUTOMATIC_DOWNLOAD` to steer if you want the library to download
  the CLI binary or not. This comes in handy with the additional option for `TAILWIND_CLI_PATH` to
  point to a pre-installed binary.

## 2.6.0

- Added 'support' for Django 5.0.
  - Extended the tox configuration to include Django 5.0b1 and beyond.
  - Added the trove classifiert.
  - Removed the upper boundary of the django version.

## 2.5.0

- Bumped default version of Tailwind CSS CLI to 3.3.5.

## 2.4.5

- Moved coverage to the dev depencies. Somehow it ended up in the package dependencies.

## 2.4.4

- [#59](https://github.com/oliverandrich/django-tailwind-cli/pull/59)
  by [@killianarts](https://github.com/killianarts) fixed a regression from 2.4.3 that used the
  wrong runserver for the runserver_plus command.

## 2.4.3

- Code and project cleanup.
- Switched back to `unittest` for testing purposes.

## 2.4.2

- Correctly map aarch64 machine architecture to arm64 for downloading the CLI.

## 2.4.1

- Added checks for `runserver_plus` management command to give a nice error message,
  when `django-extensions` and `Werkzeug` are not properly installed.

## 2.4.0

- Back to Poetry for project management.
- [#57](https://github.com/oliverandrich/django-tailwind-cli/pull/57)
  by [@wshayes](https://github.com/wshayes) added optional django-extensions for the runserver_plus
  command.

## 2.3.0

- Changed default config to support lsp-tailwindcss

  "python3 -m django" was replaced with "python manage.py" so that the dynamic
  configuration of the content selector in tailwind.config.js also works inside
  the language server for Tailwind CSS in VSCode, Sublime, etc.

## 2.2.3

- Fixed a copy&paste error introduced by pasting the tailwind.config.js without proper escaping.

## 2.2.2

- Fixed an error locating templates from the global template directories configured
  via `settings.TEMPLATES[0]["DIRS"]`.

## 2.2.1

- Fixed a bug introduced by refactoring the changes
  from [#49](https://github.com/oliverandrich/django-tailwind-cli/pull/49).

## 2.2.0

- [#49](https://github.com/oliverandrich/django-tailwind-cli/pull/49)
  by [@andrlik](https://github.com/andrlik) added a new management
  command `tailwind list_templates`.
- The new default config uses this command to implent the idea of Calton Gibson outlined in his blog
  post [Using Django’s template loaders to configure Tailwind](https://noumenal.es/notes/tailwind/django-integration/).

## 2.1.1

- Switched from poetry to hatch for package management.

## 2.0.6

- Bugfix for default tailwind.config.js.

## 2.0.5

- Fixed a regression with the default path for the Tailwind CLI.

## 2.0.4

- The reworked testing setup broke the package. Had to pull 2.0.3 from PyPI.

## 2.0.3

- Readded support for Python 3.8.
- Added Python 3.12 to the testing matrix.

## 2.0.2

- Bugfixes for typing errors.
- Added missing test code.

## 2.0.0

- Version 2.0.0 is major refactoring compared to version 1.4.3.
- No more theme app required.
- Easier to install.
- Better out-of-the-box DX.
- A custom runserver that starts the Tailwind CLI watcher and the debug server in a single terminal
  session.
- Less dependencies.

## 1.4.3

- Fixed broken links in the documentation and README.

## 1.4.0

- Refactored the project for future extensions.
- Added proper documetation which is hosted
  at <https://oliverandrich.github.io/django-tailwind-cli/>.
- Swichted from django-click to django-rich to implement the management commands.

## 1.3.1

- Switched back to poetry after a long discussion.

## 1.3.0

- Switched from poetry to pdm.

## 1.2.2

- Fixed docstrings.
- Extended ruff configuration.

## 1.2.1

- Bumped default tailwind version to 3.2.7.

## 1.2.0

- Added support for Django 4.2.

## 1.1.0

- Fixes for documentation.
- Bumped Tailwind CSS default version to 3.2.4.
- Updated dependencies.

## 1.0.0

- Introduced django-click to the project.
- Refactored the management commands to use [django-click](https://pypi.org/project/django-click/).
- Renamed the `startwatcher` command to `watch`. I'm a lazy guy. :smile:
- Switched to tox for local and CI testing.

## 0.9.2

- Removed `httpx` as a dependency. Downloading the cli is done with `urllib.request.urlopen` once
  again. Fixes [\#4](https://github.com/oliverandrich/django-tailwind-cli/issues/4)
- Removed rich-styling information from error strings.
  Fixes [\#5](https://github.com/oliverandrich/django-tailwind-cli/issues/5)
- Fixing more typos in the README.md.

## 0.9.1

- Fixing some typos in the documentation.

## 0.9.0

- Inital public release.
