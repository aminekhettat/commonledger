"""
Sous-package parser — Extraction des relevés bancaires.

Classes exportées:
    Transaction:     Dataclass représentant une transaction bancaire.
    LaPosteParser:   Parseur pour les relevés PDF La Poste (CCP).
    ParseError:      Exception levée en cas d'échec d'extraction.
"""
from .models import Transaction, ParseError
from .la_poste_parser import LaPosteParser

__all__ = ["Transaction", "ParseError", "LaPosteParser"]
