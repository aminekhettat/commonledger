"""
Sous-package categorizer — Catégorisation des transactions.

Classes exportées:
    MoteurCategorisation: Moteur principal de catégorisation automatique et manuelle.
    Categorie:            Dataclass représentant une catégorie comptable.
"""

from .rules_engine import Categorie, MoteurCategorisation

__all__ = ["MoteurCategorisation", "Categorie"]
