"""
Widget de configuration de l'association et des catégories.

Permet de modifier toutes les informations de l'association,
gérer le logo, les couleurs, et éditer le catalogue de catégories.
"""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QFileDialog, QListWidget,
    QListWidgetItem, QHBoxLayout, QMessageBox, QDialog,
    QDialogButtonBox, QComboBox, QCheckBox, QColorDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette

from ...core.categorizer import MoteurCategorisation
from ...core.categorizer.rules_engine import Categorie
from ..accessibility import configurer_label_champ, configurer_bouton


class SettingsWidget(QWidget):
    """
    Widget de paramètres.

    Signals:
        config_modifiee (): Émis quand la configuration est sauvegardée.
    """
    config_modifiee = Signal()

    def __init__(self, chemin_asso: str, chemin_cat: str, moteur: MoteurCategorisation):
        super().__init__()
        self._chemin_asso = chemin_asso
        self._chemin_cat = chemin_cat
        self._moteur = moteur
        self._config = self._charger()
        self._init_ui()
        self._remplir_champs()

    def _charger(self) -> dict:
        chemin = Path(self._chemin_asso)
        if chemin.exists():
            with open(chemin, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        titre = QLabel("Paramètres")
        titre.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a3a5c;")
        layout.addWidget(titre)

        tabs = QTabWidget()
        tabs.setAccessibleName("Onglets des paramètres")

        tabs.addTab(self._onglet_association(), "&Association")
        tabs.addTab(self._onglet_categories(), "&Catégories")

        layout.addWidget(tabs)

        # Bouton Sauvegarder
        self._btn_sauv = QPushButton("💾 &Sauvegarder les paramètres")
        self._btn_sauv.setMinimumHeight(40)
        self._btn_sauv.setStyleSheet(
            "QPushButton { background: #1a3a5c; color: white; font-size: 13px; "
            "border-radius: 5px; padding: 6px 20px; }"
        )
        configurer_bouton(self._btn_sauv, "Sauvegarder tous les paramètres")
        self._btn_sauv.clicked.connect(self._sauvegarder)
        layout.addWidget(self._btn_sauv, alignment=Qt.AlignLeft)

    def _onglet_association(self) -> QWidget:
        """Construit l'onglet des informations de l'association."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        champs_def = [
            ("type_structure", "Type de structure", "Association loi 1901"),
            ("nom", "Nom complet de l'association", ""),
            ("sigle", "Sigle / Acronyme", ""),
            ("adresse", "Adresse", ""),
            ("code_postal", "Code postal", ""),
            ("ville", "Ville", ""),
            ("email", "Email de contact", ""),
            ("telephone", "Téléphone", ""),
            ("site_web", "Site web", ""),
            ("siret", "Numéro SIRET", ""),
            ("code_ape", "Code APE / NAF", ""),
            ("numero_waldec", "Numéro Waldec (RNA)", ""),
            ("iban", "IBAN", ""),
            ("bic", "BIC", ""),
            ("president", "Président(e)", ""),
            ("tresorier", "Trésorier(ère)", ""),
        ]

        self._champs: dict[str, QLineEdit] = {}
        form = QFormLayout()

        for cle, label, placeholder in champs_def:
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            lbl = QLabel(f"{label} :")
            configurer_label_champ(lbl, edit, label)
            form.addRow(lbl, edit)
            self._champs[cle] = edit

        layout.addLayout(form)

        # Logo
        grp_logo = QGroupBox("Logo de l'association")
        lay_logo = QHBoxLayout(grp_logo)
        self._edit_logo = QLineEdit()
        self._edit_logo.setPlaceholderText("Chemin vers le fichier logo (PNG, JPG)…")
        configurer_label_champ(QLabel("Logo"), self._edit_logo, "Chemin du fichier logo")
        lay_logo.addWidget(self._edit_logo)
        btn_logo = QPushButton("&Choisir…")
        btn_logo.clicked.connect(self._choisir_logo)
        lay_logo.addWidget(btn_logo)
        layout.addWidget(grp_logo)

        # Couleurs
        grp_couleurs = QGroupBox("Couleurs de l'association")
        lay_coul = QHBoxLayout(grp_couleurs)

        self._btn_couleur_principale = QPushButton("  Couleur principale")
        self._btn_couleur_principale.clicked.connect(
            lambda: self._choisir_couleur("couleur_principale", self._btn_couleur_principale)
        )
        configurer_bouton(self._btn_couleur_principale, "Choisir la couleur principale")
        lay_coul.addWidget(self._btn_couleur_principale)

        self._btn_couleur_secondaire = QPushButton("  Couleur secondaire")
        self._btn_couleur_secondaire.clicked.connect(
            lambda: self._choisir_couleur("couleur_secondaire", self._btn_couleur_secondaire)
        )
        configurer_bouton(self._btn_couleur_secondaire, "Choisir la couleur secondaire (fond)")
        lay_coul.addWidget(self._btn_couleur_secondaire)
        lay_coul.addStretch()

        layout.addWidget(grp_couleurs)
        layout.addStretch()

        return widget

    def _onglet_categories(self) -> QWidget:
        """Construit l'onglet de gestion des catégories."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        explication = QLabel(
            "Gérez ici vos catégories de recettes et dépenses. "
            "Vous pouvez ajouter, modifier ou supprimer des catégories."
        )
        explication.setWordWrap(True)
        layout.addWidget(explication)

        for type_cat, titre in [("recettes", "Catégories Recettes"), ("depenses", "Catégories Dépenses")]:
            grp = QGroupBox(titre)
            lay = QVBoxLayout(grp)

            liste = QListWidget()
            liste.setAccessibleName(f"Liste des catégories {type_cat}")
            for cat in self._moteur.categories_par_type(type_cat):
                item = QListWidgetItem(cat.label)
                item.setData(Qt.UserRole, cat.id)
                liste.addItem(item)
            lay.addWidget(liste)

            barre = QHBoxLayout()
            btn_ajouter = QPushButton(f"➕ Ajouter ({type_cat[:3]})")
            btn_ajouter.clicked.connect(lambda _, t=type_cat, l=liste: self._ajouter_categorie(t, l))
            barre.addWidget(btn_ajouter)

            btn_suppr = QPushButton("🗑 Supprimer")
            btn_suppr.clicked.connect(lambda _, l=liste: self._supprimer_categorie(l))
            barre.addWidget(btn_suppr)
            barre.addStretch()

            lay.addLayout(barre)
            layout.addWidget(grp)

        return widget

    def _remplir_champs(self) -> None:
        """Remplit les champs avec les valeurs de la configuration."""
        for cle, edit in self._champs.items():
            edit.setText(str(self._config.get(cle, "")))

        logo = self._config.get("logo_chemin", "")
        self._edit_logo.setText(logo)

        # Couleurs des boutons
        for cle, btn in [
            ("couleur_principale", self._btn_couleur_principale),
            ("couleur_secondaire", self._btn_couleur_secondaire),
        ]:
            couleur = self._config.get(cle, "#ffffff")
            btn.setStyleSheet(f"background-color: {couleur};")
            self._config.setdefault(cle, couleur)

    def _choisir_logo(self) -> None:
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Choisir un logo", str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.svg)"
        )
        if chemin:
            self._edit_logo.setText(chemin)

    def _choisir_couleur(self, cle: str, bouton: QPushButton) -> None:
        couleur_actuelle = QColor(self._config.get(cle, "#1a3a5c"))
        couleur = QColorDialog.getColor(couleur_actuelle, self, f"Choisir la {cle.replace('_', ' ')}")
        if couleur.isValid():
            hex_col = couleur.name()
            self._config[cle] = hex_col
            bouton.setStyleSheet(f"background-color: {hex_col};")

    def _ajouter_categorie(self, type_cat: str, liste: QListWidget) -> None:
        """Demande le nom d'une nouvelle catégorie et l'ajoute."""
        from PySide6.QtWidgets import QInputDialog
        nom, ok = QInputDialog.getText(
            self, "Nouvelle catégorie", f"Nom de la catégorie ({type_cat}) :"
        )
        if ok and nom.strip():
            import re
            cat_id = re.sub(r"[^a-z0-9_]", "_", nom.lower().strip())
            cat = Categorie(id=cat_id, label=nom.strip(), type=type_cat)
            try:
                self._moteur.ajouter_categorie(cat)
                item = QListWidgetItem(nom.strip())
                item.setData(Qt.UserRole, cat_id)
                liste.addItem(item)
            except ValueError as e:
                QMessageBox.warning(self, "Erreur", str(e))

    def _supprimer_categorie(self, liste: QListWidget) -> None:
        item = liste.currentItem()
        if not item:
            return
        reponse = QMessageBox.question(
            self, "Confirmer",
            f"Supprimer la catégorie '{item.text()}' ?\n"
            "Les transactions utilisant cette catégorie deviennent non catégorisées.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reponse == QMessageBox.Yes:
            try:
                self._moteur.supprimer_categorie(item.data(Qt.UserRole))
                liste.takeItem(liste.row(item))
            except KeyError as e:
                QMessageBox.warning(self, "Erreur", str(e))

    def _sauvegarder(self) -> None:
        """Sauvegarde la configuration."""
        for cle, edit in self._champs.items():
            self._config[cle] = edit.text().strip()
        self._config["logo_chemin"] = self._edit_logo.text().strip()

        chemin = Path(self._chemin_asso)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

        QMessageBox.information(self, "Sauvegardé", "Paramètres sauvegardés avec succès.")
        self.config_modifiee.emit()
