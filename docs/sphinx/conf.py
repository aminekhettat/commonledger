# Configuration file for the Sphinx documentation builder.
# CommonLedger — API Reference
#
# Build : sphinx-build -b html docs/sphinx docs/sphinx/_build/html
# Auto  : sphinx-autobuild docs/sphinx docs/sphinx/_build/html

import os
import sys

# Ajouter le répertoire racine du projet au path
sys.path.insert(0, os.path.abspath("../.."))

# ── Informations du projet ────────────────────────────────────────────────────
project = "CommonLedger"
copyright = "2026, Amine Khettat — BLIND SYSTEMS"
author = "Amine Khettat"

# Lire la version depuis pyproject.toml pour rester synchronisé
try:
    import tomllib
    with open(os.path.join(os.path.dirname(__file__), "../../pyproject.toml"), "rb") as f:
        _pyproject = tomllib.load(f)
    release = _pyproject["project"]["version"]
    version = ".".join(release.split(".")[:2])
except Exception:
    version = "0.1"
    release = "0.1.3"

# ── Extensions ────────────────────────────────────────────────────────────────
extensions = [
    "sphinx.ext.autodoc",          # Extraction automatique des docstrings
    "sphinx.ext.napoleon",         # Support docstrings Google & NumPy
    "sphinx.ext.viewcode",         # Lien vers le code source
    "sphinx.ext.autosummary",      # Résumés automatiques des modules
    "sphinx.ext.intersphinx",      # Liens vers la doc Python standard
    "sphinx.ext.todo",             # Marques TODO dans la doc
    "sphinx_autodoc_typehints",    # Annotations de types dans la doc
    "sphinx_copybutton",           # Bouton copier sur les blocs de code
    "myst_parser",                 # Support Markdown en plus de RST
]

# ── Configuration autodoc ─────────────────────────────────────────────────────
autodoc_default_options = {
    "members": True,               # Documenter tous les membres publics
    "undoc-members": True,         # Y compris ceux sans docstring
    "private-members": False,      # Pas les membres privés (_xxx)
    "special-members": "__init__, __post_init__",
    "inherited-members": False,
    "show-inheritance": True,      # Afficher la hiérarchie de classes
    "member-order": "bysource",    # Ordre du code source (pas alphabétique)
}
autodoc_typehints = "description"  # Types dans la description, pas la signature
autodoc_type_aliases = {
    "Optional[str]": "str | None",
    "Optional[int]": "int | None",
    "Optional[Decimal]": "Decimal | None",
    "Optional[date]": "date | None",
}

# ── Configuration napoleon (docstrings Google) ─────────────────────────────────
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True
napoleon_attr_annotations = True

# ── Configuration autosummary ─────────────────────────────────────────────────
autosummary_generate = True
autosummary_generate_overwrite = True

# ── Intersphinx ───────────────────────────────────────────────────────────────
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# ── HTML ──────────────────────────────────────────────────────────────────────
html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "logo_only": False,
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": False,
    "style_nav_header_background": "#1a3a5c",
}
html_static_path = ["_static"]
html_css_files = ["custom.css"]

# Titre de la barre latérale
html_title = f"CommonLedger {release} — Documentation API"
html_short_title = "CommonLedger"

# Favicon et logo
html_logo = None  # Sera rempli si le logo est disponible

# ── Options diverses ──────────────────────────────────────────────────────────
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
language = "fr"
todo_include_todos = True

# Ordre d'affichage des modules
modindex_common_prefix = ["core."]
