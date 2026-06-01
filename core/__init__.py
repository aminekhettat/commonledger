"""
CommonLedger — Module principal du noyau métier.

Ce package contient toute la logique métier de l'application,
sans aucune dépendance à l'interface graphique.

Packages:
    parser:      Extraction des transactions depuis les relevés PDF La Banque Postale.
    categorizer: Catégorisation automatique et manuelle des transactions.
    accounting:  Calculs comptables (compte de résultat, analytique).
    reporter:    Génération des rapports Word, CSV et PDF.
"""

__version__ = "0.1.0"
__app_name__ = "CommonLedger"
