"""
Package UI — Interface graphique PySide6.

Architecture de l'interface :
    MainWindow       : Fenêtre principale avec navigation par onglets.
    ImportWidget     : Import des relevés PDF.
    CategorizeWidget : Révision et catégorisation manuelle.
    ReportWidget     : Génération et export des rapports.
    SettingsWidget   : Paramètres de l'association et des catégories.
    ProjetWidget     : Gestion des projets analytiques.

Accessibilité :
    Tous les widgets définissent setAccessibleName() et
    setAccessibleDescription() pour une lecture NVDA correcte.
    La navigation clavier est assurée par un ordre de tabulation
    logique et des raccourcis Alt+lettre sur toutes les actions.
"""
