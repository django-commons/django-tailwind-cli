set export
set dotenv-load

VENV_DIRNAME := ".venv"

@_default:
    just --list

# setup development environment
@bootstrap:
    if [ -x $VENV_DIRNAME ]; then \
        echo "Already bootstraped. Exiting."; \
        exit; \
    fi

    echo "Creating virtual env in .venv"
    just create_venv

    echo "Installing dependencies"
    just upgrade

# create a virtual environment
@create_venv:
    [ -d $VENV_DIRNAME ] || uv venv $VENV_DIRNAME

# build release
@build:
    uv build

# publish release
@publish: build
    uv publish

# upgrade/install all dependencies defined in pyproject.toml
@upgrade: create_venv
    uv sync --all-extras

# run pre-commit rules on all files
@lint: create_venv
    uvx --with pre-commit-uv pre-commit run --all-files

# run test suite
@test: create_venv
    uv run pytest --cov --cov-report=html --cov-report=term

# run test suite
@test-all: create_venv
    uvx --with tox-uv tox

# serve docs during development
@serve-docs:
    uvx --with mkdocs-material mkdocs serve
