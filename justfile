set export
set dotenv-load

VENV_DIRNAME := ".venv"

@_default:
    just --list

[private]
@check_uv:
    if ! command -v uv &> /dev/null; then \
        echo "uv could not be found. Exiting."; \
        exit; \
    fi

# setup development environment
@bootstrap: check_uv
    if [ -x $VENV_DIRNAME ]; then \
        echo "Already bootstraped. Exiting."; \
        exit; \
    fi

    echo "Installing dependencies"
    just upgrade

# upgrade/install all dependencies defined in pyproject.toml
@upgrade: check_uv
    uv sync --all-extras --upgrade

# run pre-commit rules on all files
@lint: check_uv
    uvx --with pre-commit-uv pre-commit run --all-files

# run test suite
@test: check_uv
    uv run pytest --cov --cov-report=html --cov-report=term

# run test suite
@test-all: check_uv
    uvx --with tox-uv tox

# serve docs during development
@serve-docs: check_uv
    uvx  --with markdown-callouts --with mkdocs-material mkdocs serve
