"""
CommonLedger — Point d'entrée principal.

Lance l'application de comptabilité simplifiée pour associations loi 1901.

Usage::

    python main.py

Options d'accessibilité :
    L'application active automatiquement le support UIA de Windows
    pour une compatibilité optimale avec NVDA et JAWS.
    Aucune configuration supplémentaire n'est requise.

Configuration :
    Toute la configuration est dans config/association.json
    et config/categories.json. Ces fichiers sont modifiables
    depuis l'interface ou directement dans un éditeur de texte.
"""

import logging
import sys
from pathlib import Path

# Ajouter le répertoire racine au path pour les imports relatifs
sys.path.insert(0, str(Path(__file__).parent))


def configurer_logging() -> None:
    """Configure le système de journalisation."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s : %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("comptasso.log", encoding="utf-8"),
        ],
    )


def creer_structure_repertoires() -> None:
    """Crée les répertoires nécessaires s'ils n'existent pas."""
    for dossier in ["config", "data", "data/exercices", "data/rapports"]:
        Path(dossier).mkdir(parents=True, exist_ok=True)

    # Créer les fichiers de config par défaut s'ils manquent
    config_asso = Path("config/association.json")
    if not config_asso.exists():
        import shutil
        template = Path(__file__).parent / "config" / "association.json"
        if template.exists():
            shutil.copy(template, config_asso)

    config_cat = Path("config/categories.json")
    if not config_cat.exists():
        import shutil
        template = Path(__file__).parent / "config" / "categories.json"
        if template.exists():
            shutil.copy(template, config_cat)


def main() -> None:
    """Point d'entrée principal de l'application."""
    configurer_logging()
    logger = logging.getLogger("comptasso")
    logger.info("Démarrage de CommonLedger")

    creer_structure_repertoires()

    # Import PySide6 après la configuration du path
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QCoreApplication

    # Métadonnées de l'application (utilisées par certains lecteurs d'écran)
    QCoreApplication.setApplicationName("CommonLedger")
    QCoreApplication.setApplicationVersion("0.1.0")
    QCoreApplication.setOrganizationName("Association Culture Musique")

    app = QApplication(sys.argv)

    # Activer le support d'accessibilité UIA sur Windows
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Style global
    app.setStyle("Fusion")

    # Icône de l'application (barre des tâches + Alt+Tab + barre de titre)
    from PySide6.QtGui import QIcon
    # Icône canvas (v2) en priorité, fallback sur v1
    for icon_name in [
        "config/assets/icon_commonledger_canvas.ico",
        "config/assets/icon_commonledger.ico",
        "config/assets/icon_commonledger_canvas.png",
        "config/assets/icon_commonledger.png",
    ]:
        icon_path = Path(icon_name)
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            break

    # Lancer la fenêtre principale
    from ui.main_window import MainWindow
    fenetre = MainWindow()
    fenetre.show()

    logger.info("Interface démarrée.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
