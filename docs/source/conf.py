# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "InstrMCP"
copyright = "2025, Jiaqi Cai"
author = "Jiaqi Cai"
release = "2.3.3"
version = "2.3.3"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx_autodoc_typehints",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = []

# Enable autosummary
autosummary_generate = True

# Napoleon settings for Google/NumPy style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Intersphinx mapping to link to other projects
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "qcodes": ("https://qcodes.github.io/Qcodes/", None),
    "jupyterlab": ("https://jupyterlab.readthedocs.io/en/stable/", None),
}

# MyST parser settings for Markdown support
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "html_image",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

html_theme_options = {
    "logo_only": False,
    "display_version": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": False,
    "style_nav_header_background": "#2980B9",
    # Toc options
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
}

html_context = {
    "display_github": True,
    "github_user": "caidish",
    "github_repo": "instrMCP",
    "github_version": "main",
    "conf_py_path": "/docs/source/",
}

# -- Options for LaTeX output ------------------------------------------------

latex_elements = {
    "papersize": "letterpaper",
    "pointsize": "10pt",
    "preamble": "",
    "figure_align": "htbp",
}

latex_documents = [
    ("index", "instrMCP.tex", "InstrMCP Documentation", "Jiaqi Cai", "manual"),
]

# -- Options for manual page output ------------------------------------------

man_pages = [("index", "instrmcp", "InstrMCP Documentation", [author], 1)]

# -- Options for Texinfo output ----------------------------------------------

texinfo_documents = [
    (
        "index",
        "instrMCP",
        "InstrMCP Documentation",
        author,
        "instrMCP",
        "MCP server suite for physics laboratory instrumentation control",
        "Miscellaneous",
    ),
]

# -- Options for Epub output -------------------------------------------------

epub_title = project
epub_exclude_files = ["search.html"]

# -- Extension configuration -------------------------------------------------

# autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# typehints settings
always_document_param_types = True
typehints_fully_qualified = False
