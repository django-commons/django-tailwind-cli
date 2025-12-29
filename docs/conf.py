# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "django-tailwind-cli"
copyright = "2023, Oliver Andrich"  # noqa: A001
author = "Oliver Andrich"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_title = "django-tailwind-cli"
html_static_path = []

html_theme_options = {
    "source_repository": "https://github.com/django-commons/django-tailwind-cli",
    "source_branch": "main",
    "source_directory": "docs/",
}

# -- MyST configuration ------------------------------------------------------
# https://myst-parser.readthedocs.io/en/latest/configuration.html

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "substitution",
]

# Allow .md files to be parsed
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
