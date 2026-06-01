"""
Sous-package accounting — Calculs comptables.

Classes exportées:
    CompteResultat:  Calcule le compte de résultat pour une période donnée.
    ComptaAnalytique: Ventilation des recettes/dépenses par projet.
    Exercice:        Conteneur principal d'un exercice comptable.
"""

from .analytique import ComptaAnalytique, Projet
from .compte_resultat import CompteResultat, LigneResultat
from .exercice import Exercice

__all__ = ["CompteResultat", "LigneResultat", "ComptaAnalytique", "Projet", "Exercice"]
