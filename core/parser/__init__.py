"""
Sous-package parser — Extraction des relevés bancaires.

Classes exportées:
    Transaction:     Dataclass représentant une transaction bancaire.
    LaPosteParser:   Parseur pour les relevés PDF La Poste (CCP).
    ParseError:      Exception levée en cas d'échec d'extraction.
"""

from .la_poste_parser import LaPosteParser
from .models import ParseError, Transaction

__all__ = ["Transaction", "ParseError", "LaPosteParser"]
