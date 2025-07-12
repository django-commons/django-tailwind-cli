# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`django-tailwind-cli` is a Django package that provides seamless integration between Django and Tailwind CSS 4.x using the precompiled Tailwind CSS CLI, eliminating the need for Node.js.

## Development Setup and Commands

### Required Tools
- Python 3.10-3.14
- [uv](https://docs.astral.sh/uv/) - Modern Python package manager
- [just](https://github.com/casey/just) - Command runner (optional but recommended)

### Common Development Commands

```bash
# Setup development environment
just bootstrap

# Install/upgrade dependencies
just upgrade

# Run linting and formatting
just lint

# Run tests
just test          # Run pytest with coverage
just test-all      # Run full test matrix with tox

# Documentation
just serve-docs    # Serve docs locally with mkdocs
```

### Without `just` (using uv directly)
```bash
# Create virtual environment
uv venv

# Install all dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run tox test matrix
uvx --with tox-uv tox

# Run linting
uvx --with pre-commit-uv pre-commit run --all-files
```

## Code Architecture

### Package Structure
```
src/django_tailwind_cli/
├── apps.py                     # Django app configuration
├── config.py                   # Central configuration (Config class)
├── management/commands/        # Django management commands
│   └── tailwind.py            # Main command: build, watch, runserver
├── templates/tailwind_cli/     # Template files
├── templatetags/              # Template tags ({% tailwind_css %})
└── utils/                     # Utility modules for CLI download, etc.
```

### Key Components

1. **Configuration System** (`config.py`):
   - `Config` class centralizes all settings
   - Reads from Django settings with sensible defaults
   - Handles CLI paths, CSS paths, and command configurations

2. **Management Commands** (`management/commands/tailwind.py`):
   - `tailwind build`: Production CSS build
   - `tailwind watch`: Development mode with auto-rebuild
   - `tailwind runserver`: Combined Django runserver + Tailwind watch

3. **Template Integration**:
   - `{% load tailwind_cli %}` - Load template tags
   - `{% tailwind_css %}` - Include CSS in templates
   - Base template provided at `tailwind_cli/base.html`

4. **CLI Management**:
   - Automatic download of Tailwind CSS CLI binaries
   - Support for custom CLI paths
   - Platform-specific binary selection

## Testing

The project uses pytest with Django integration:
- Test files in `tests/` directory
- Configuration in `tests/settings.py`
- Run with coverage: `uv run pytest --cov`
- Full matrix testing: `uvx --with tox-uv tox`

## Important Settings

Key Django settings for configuration:
- `TAILWIND_CLI_PATH`: Custom path to Tailwind CLI
- `TAILWIND_CSS_PATH`: Output CSS file location
- `TAILWIND_CONFIG_FILE`: Path to tailwind.config.js
- `STATICFILES_DIRS`: Must be configured for asset collection

## Development Workflow

1. Make changes to the code
2. Run `just lint` to check formatting and linting
3. Run `just test` to ensure tests pass
4. For multi-version testing, run `just test-all`
5. Update documentation if needed

## Version Support

- Python: 3.10-3.14
- Django: 4.0-5.2
- Tailwind CSS: 4.x only (use v2.21.1 for Tailwind 3.x)

## Commit Message Guidelines

Use conventional commit format with the following structure:

```
type(scope): brief description

- Bullet point describing key change
- Another bullet point for significant addition
- Additional points as needed
```

### Commit Types
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code refactoring without changing functionality
- **test**: Adding or modifying tests
- **chore**: Maintenance tasks (deps updates, build changes, etc.)
- **ci**: CI/CD configuration changes
- **perf**: Performance improvements

### Project Scopes
- **config**: Configuration handling (config.py)
- **management**: Management commands
- **templatetags**: Template tags functionality
- **templates**: HTML template files
- **build**: Build command functionality
- **watch**: Watch mode functionality
- **runserver**: Development server integration
- **download**: CLI download functionality
- **deps**: Dependencies
- **ci**: Continuous integration
- **docs**: Documentation
- **tests**: Test suite
- **daisyui**: DaisyUI integration
- **staticfiles**: Static files handling

### Example Commits
```
feat(management): add purge command for cleaning CSS

- Add new purge subcommand to remove unused styles
- Support custom purge configuration
- Integrate with existing build process

fix(config): handle prefixed staticfile directories

- Correctly resolve paths when STATIC_URL has prefix
- Add validation for malformed configurations

chore(deps): bump django-typer to 2.1.2

- Update minimum version for security fix
- Adjust type hints for new API
```

### Important Notes
- **NEVER include Claude Code references in commit messages** - This is strictly prohibited
- **NEVER add "Generated with Claude Code" or "Co-Authored-By: Claude" lines** - Commit messages must be clean
- Keep commit messages focused on the technical changes made
- Use bullet points to describe key modifications and their impact
