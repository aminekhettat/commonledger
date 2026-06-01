"""
Fenêtre principale de CommonLedger.

Architecture :
    La fenêtre principale utilise un QTabWidget pour organiser les
    5 sections fonctionnelles. La navigation entre onglets est
    accessible via Ctrl+Tab / Ctrl+Shift+Tab et les raccourcis
    Alt+1 à Alt+5.

Accessibilité NVDA :
    - Titre de fenêtre mis à jour selon l'onglet actif
    - Barre de statut lue automatiquement par NVDA
    - Messages d'erreur dans des QMessageBox (correctement lues)
    - Navigation complète au clavier (pas de dépendance souris)
"""

import json
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMessageBox,
    QMenuBar, QMenu, QApplication, QWidget,
)
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtCore import Qt, QSize

from .widgets.import_widget import ImportWidget
from .widgets.categorize_widget import CategorizeWidget
from .widgets.report_widget import ReportWidget
from .widgets.settings_widget import SettingsWidget
from .widgets.projet_widget import ProjetWidget
from .accessibility import configurer_bouton

from ..core.categorizer import MoteurCategorisation
from ..core.accounting import Exercice, ComptaAnalytique

logger = logging.getLogger(__name__)

# Chemins relatifs depuis la racine du projet
_CONFIG_ASSO = "config/association.json"
_CONFIG_CAT = "config/categories.json"
_DATA_DIR = "data"


class MainWindow(QMainWindow):
    """
    Fenêtre principale de l'application CommonLedger.

    Coordonne les différents widgets et partage l'état global
    (exercice en cours, moteur de catégorisation) entre eux.

    Raccourcis clavier globaux :
        Alt+1 → Onglet Import
        Alt+2 → Onglet Catégorisation
        Alt+3 → Onglet Rapport
        Alt+4 → Onglet Projets
        Alt+5 → Onglet Paramètres
        Ctrl+S → Sauvegarder l'exercice en cours
        F1     → Aide / À propos
    """

    def __init__(self):
        super().__init__()
        self._config_asso = self._charger_config_asso()
        self._moteur = MoteurCategorisation(_CONFIG_CAT)
        self._exercice: Exercice | None = None
        self._analytique = ComptaAnalytique(str(Path(_DATA_DIR) / "projets.json"))

        self._init_ui()
        self._init_menus()
        self._init_raccourcis()
        self._connecter_signaux()

        self.setWindowTitle("CommonLedger — Comptabilité simplifiée pour associations")
        self.resize(1100, 750)
        self.statusBar().showMessage("Bienvenue dans CommonLedger. Commencez par importer vos relevés (Alt+1).")

    def _charger_config_asso(self) -> dict:
        """Charge la configuration de l'association."""
        chemin = Path(_CONFIG_ASSO)
        if chemin.exists():
            with open(chemin, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _init_ui(self) -> None:
        """Construit l'interface principale avec les onglets."""
        self._tabs = QTabWidget()
        self._tabs.setAccessibleName("Navigation principale")
        self._tabs.setAccessibleDescription(
            "5 onglets : Import, Catégorisation, Rapport, Projets, Paramètres. "
            "Naviguez avec Ctrl+Tab ou Alt+1 à Alt+5."
        )
        self._tabs.setDocumentMode(True)

        # Création des widgets de chaque onglet
        self._import_widget = ImportWidget(self._config_asso, self._moteur)
        self._categorize_widget = CategorizeWidget(self._moteur)
        self._report_widget = ReportWidget(self._config_asso, self._moteur, self._analytique)
        self._projet_widget = ProjetWidget(self._analytique)
        self._settings_widget = SettingsWidget(_CONFIG_ASSO, _CONFIG_CAT, self._moteur)

        # Ajout des onglets
        self._tabs.addTab(self._import_widget, "&1 Import")
        self._tabs.addTab(self._categorize_widget, "&2 Catégorisation")
        self._tabs.addTab(self._report_widget, "&3 Rapport")
        self._tabs.addTab(self._projet_widget, "&4 Projets")
        self._tabs.addTab(self._settings_widget, "&5 Paramètres")

        self.setCentralWidget(self._tabs)

        # Barre de statut accessible
        self.statusBar().setAccessibleName("Barre de statut")
        self.statusBar().setAccessibleDescription(
            "Affiche l'état de l'application et les messages d'information."
        )

    def _init_menus(self) -> None:
        """Construit la barre de menus."""
        barre = self.menuBar()
        barre.setAccessibleName("Barre de menus")

        # Menu Fichier
        menu_fichier = barre.addMenu("&Fichier")

        action_nouveau = QAction("&Nouvel exercice...", self)
        action_nouveau.setShortcut(QKeySequence("Ctrl+N"))
        action_nouveau.setStatusTip("Créer ou ouvrir un exercice comptable")
        action_nouveau.triggered.connect(self._ouvrir_exercice)
        menu_fichier.addAction(action_nouveau)

        action_sauv = QAction("&Sauvegarder", self)
        action_sauv.setShortcut(QKeySequence("Ctrl+S"))
        action_sauv.setStatusTip("Sauvegarder l'exercice en cours")
        action_sauv.triggered.connect(self._sauvegarder)
        menu_fichier.addAction(action_sauv)

        menu_fichier.addSeparator()

        action_quitter = QAction("&Quitter", self)
        action_quitter.setShortcut(QKeySequence("Alt+F4"))
        action_quitter.triggered.connect(self.close)
        menu_fichier.addAction(action_quitter)

        # Menu Aide
        menu_aide = barre.addMenu("&Aide")

        action_apropos = QAction("À &propos de CommonLedger", self)
        action_apropos.setShortcut(QKeySequence("F1"))
        action_apropos.triggered.connect(self._afficher_apropos)
        menu_aide.addAction(action_apropos)

        action_raccourcis = QAction("&Raccourcis clavier", self)
        action_raccourcis.triggered.connect(self._afficher_raccourcis)
        menu_aide.addAction(action_raccourcis)

    def _init_raccourcis(self) -> None:
        """Configure les raccourcis clavier globaux Alt+1 à Alt+5."""
        from PySide6.QtGui import QShortcut
        for i in range(5):
            shortcut = QShortcut(QKeySequence(f"Alt+{i+1}"), self)
            shortcut.activated.connect(
                lambda idx=i: self._tabs.setCurrentIndex(idx)
            )

    def _connecter_signaux(self) -> None:
        """Connecte les signaux entre les widgets."""
        # Quand l'import produit un exercice → le transmettre aux autres widgets
        self._import_widget.exercice_importe.connect(self._on_exercice_importe)

        # Mettre à jour la barre de statut depuis tous les widgets
        for widget in [
            self._import_widget,
            self._categorize_widget,
            self._report_widget,
        ]:
            if hasattr(widget, "message_status"):
                widget.message_status.connect(self.statusBar().showMessage)

        # Quand les paramètres changent → recharger la config dans tous les widgets
        self._settings_widget.config_modifiee.connect(self._on_config_modifiee)

        # Navigation automatique : après import → aller à catégorisation
        self._import_widget.exercice_importe.connect(
            lambda: self._tabs.setCurrentIndex(1)
        )

        # Mettre à jour le titre selon l'onglet
        self._tabs.currentChanged.connect(self._on_onglet_change)

    def _on_exercice_importe(self, exercice: Exercice) -> None:
        """Reçoit l'exercice importé et le distribue à tous les widgets."""
        self._exercice = exercice
        self._categorize_widget.set_exercice(exercice)
        self._report_widget.set_exercice(exercice)
        nom = self._config_asso.get("nom", "Association")
        self.statusBar().showMessage(
            f"Exercice {exercice.annee} chargé : {len(exercice.transactions)} transactions."
        )
        self.setWindowTitle(
            f"CommonLedger — {nom} — Exercice {exercice.annee}"
        )

    def _on_config_modifiee(self) -> None:
        """Recharge la configuration après modification dans les paramètres."""
        self._config_asso = self._charger_config_asso()
        self._moteur.recharger()
        self._report_widget.set_config(self._config_asso)
        nom = self._config_asso.get("nom", "Association")
        self.statusBar().showMessage(f"Configuration mise à jour pour : {nom}")

    def _on_onglet_change(self, index: int) -> None:
        """Met à jour le titre de la fenêtre selon l'onglet actif (aide NVDA)."""
        noms_onglets = ["Import", "Catégorisation", "Rapport", "Projets", "Paramètres"]
        if 0 <= index < len(noms_onglets):
            base = self.windowTitle().split(" — ")[0]
            self.setWindowTitle(f"{base} — {noms_onglets[index]}")

    def _ouvrir_exercice(self) -> None:
        """Ouvre la boîte de dialogue pour sélectionner/créer un exercice."""
        self._tabs.setCurrentIndex(0)
        self._import_widget.demander_annee()

    def _sauvegarder(self) -> None:
        """Sauvegarde l'exercice en cours."""
        if self._exercice:
            self._exercice.sauvegarder()
            self.statusBar().showMessage("Exercice sauvegardé.")
        else:
            self.statusBar().showMessage("Aucun exercice en cours à sauvegarder.")

    def _afficher_apropos(self) -> None:
        """Affiche la boîte de dialogue 'À propos'."""
        QMessageBox.about(
            self,
            "À propos de CommonLedger",
            "CommonLedger — Version 1.0\n\n"
            "Application de comptabilité simplifiée pour associations loi 1901.\n\n"
            "Conçue pour être totalement accessible aux personnes non voyantes\n"
            "(compatible NVDA et JAWS via l'API UIA de Windows).\n\n"
            "Projet open source — Python / PySide6\n\n"
            "Raccourcis : F1 = Aide, Ctrl+S = Sauvegarder, Alt+1 à Alt+5 = Onglets",
        )

    def _afficher_raccourcis(self) -> None:
        """Affiche la liste des raccourcis clavier."""
        raccourcis = (
            "Raccourcis clavier globaux :\n\n"
            "  Alt+1       → Onglet Import\n"
            "  Alt+2       → Onglet Catégorisation\n"
            "  Alt+3       → Onglet Rapport\n"
            "  Alt+4       → Onglet Projets\n"
            "  Alt+5       → Onglet Paramètres\n"
            "  Ctrl+N      → Nouvel exercice\n"
            "  Ctrl+S      → Sauvegarder\n"
            "  F1          → À propos\n"
            "  Alt+F4      → Quitter\n\n"
            "Dans les tableaux :\n"
            "  Espace      → Sélectionner/valider\n"
            "  Entrée      → Ouvrir le détail\n"
            "  Flèches     → Naviguer\n\n"
            "Dans les formulaires :\n"
            "  Tab         → Champ suivant\n"
            "  Shift+Tab   → Champ précédent\n"
            "  Alt+lettre  → Activer le bouton souligné"
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Raccourcis clavier")
        msg.setText(raccourcis)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

    def closeEvent(self, event) -> None:
        """Propose de sauvegarder avant de quitter."""
        if self._exercice:
            reponse = QMessageBox.question(
                self,
                "Sauvegarder avant de quitter ?",
                "Voulez-vous sauvegarder l'exercice avant de quitter ?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if reponse == QMessageBox.Cancel:
                event.ignore()
                return
            if reponse == QMessageBox.Yes:
                self._exercice.sauvegarder()
        event.accept()
