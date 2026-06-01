"""Widget de gestion des projets analytiques."""
from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QGroupBox, QFormLayout, QLineEdit, QDateEdit,
    QDoubleSpinBox, QDialog, QDialogButtonBox, QListWidgetItem,
    QMessageBox,
)
from PySide6.QtCore import Qt, QDate

from ...core.accounting import ComptaAnalytique
from ...core.accounting.analytique import Projet
from ..accessibility import configurer_bouton, configurer_label_champ


class DialogueProjet(QDialog):
    """Formulaire de création/modification d'un projet."""

    def __init__(self, projet: Projet = None, parent=None):
        super().__init__(parent)
        self._projet = projet
        self.setWindowTitle("Nouveau projet" if not projet else f"Modifier : {projet.nom}")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._edit_nom = QLineEdit(self._projet.nom if self._projet else "")
        configurer_label_champ(QLabel("Nom"), self._edit_nom, "Nom du projet")
        form.addRow("Nom :", self._edit_nom)

        self._edit_desc = QLineEdit(self._projet.description if self._projet else "")
        configurer_label_champ(QLabel("Description"), self._edit_desc, "Description courte")
        form.addRow("Description :", self._edit_desc)

        self._date_debut = QDateEdit()
        self._date_debut.setDisplayFormat("dd/MM/yyyy")
        self._date_debut.setCalendarPopup(True)
        if self._projet and self._projet.date_debut:
            d = self._projet.date_debut
            self._date_debut.setDate(QDate(d.year, d.month, d.day))
        else:
            self._date_debut.setDate(QDate.currentDate())
        form.addRow("Date de début :", self._date_debut)

        self._spin_budget = QDoubleSpinBox()
        self._spin_budget.setRange(0, 9999999)
        self._spin_budget.setDecimals(2)
        self._spin_budget.setSuffix(" €")
        if self._projet:
            self._spin_budget.setValue(float(self._projet.budget))
        form.addRow("Budget prévisionnel :", self._spin_budget)

        layout.addLayout(form)

        boutons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        boutons.button(QDialogButtonBox.Ok).setText("&Créer" if not self._projet else "&Modifier")
        boutons.button(QDialogButtonBox.Cancel).setText("&Annuler")
        boutons.accepted.connect(self.accept)
        boutons.rejected.connect(self.reject)
        layout.addWidget(boutons)

    def get_donnees(self) -> dict:
        d = self._date_debut.date()
        return {
            "nom": self._edit_nom.text().strip(),
            "description": self._edit_desc.text().strip(),
            "date_debut": date(d.year(), d.month(), d.day()),
            "budget": Decimal(str(self._spin_budget.value())),
        }


class ProjetWidget(QWidget):
    """Widget de gestion des projets analytiques."""

    def __init__(self, analytique: ComptaAnalytique):
        super().__init__()
        self._analytique = analytique
        self._init_ui()
        self._actualiser_liste()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        titre = QLabel("Projets analytiques")
        titre.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a3a5c;")
        layout.addWidget(titre)

        explication = QLabel(
            "Les projets permettent de chiffrer recettes et dépenses par événement "
            "(concert, tournée, atelier...). Rattachez des transactions à un projet "
            "lors de la catégorisation."
        )
        explication.setWordWrap(True)
        layout.addWidget(explication)

        # Liste des projets
        self._liste = QListWidget()
        self._liste.setAccessibleName("Liste des projets analytiques")
        self._liste.setAccessibleDescription(
            "Sélectionnez un projet pour le modifier ou le supprimer."
        )
        layout.addWidget(self._liste)

        # Boutons
        barre = QHBoxLayout()
        self._btn_nouveau = QPushButton("➕ &Nouveau projet")
        configurer_bouton(self._btn_nouveau, "Créer un nouveau projet analytique")
        self._btn_nouveau.clicked.connect(self._creer_projet)
        barre.addWidget(self._btn_nouveau)

        self._btn_modifier = QPushButton("✏ &Modifier")
        configurer_bouton(self._btn_modifier, "Modifier le projet sélectionné")
        self._btn_modifier.clicked.connect(self._modifier_projet)
        barre.addWidget(self._btn_modifier)

        self._btn_supprimer = QPushButton("🗑 &Supprimer")
        configurer_bouton(self._btn_supprimer, "Supprimer le projet sélectionné")
        self._btn_supprimer.clicked.connect(self._supprimer_projet)
        barre.addWidget(self._btn_supprimer)

        barre.addStretch()
        layout.addLayout(barre)

    def _actualiser_liste(self) -> None:
        self._liste.clear()
        for projet in self._analytique.projets.values():
            label = f"{projet.nom}"
            if projet.date_debut:
                label += f" — depuis {projet.date_debut.strftime('%d/%m/%Y')}"
            if projet.budget > 0:
                label += f" — Budget : {projet.budget:,.2f} €"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, projet.id)
            self._liste.addItem(item)

    def _creer_projet(self) -> None:
        dlg = DialogueProjet(parent=self)
        if dlg.exec() == QDialog.Accepted:
            donnees = dlg.get_donnees()
            if not donnees["nom"]:
                QMessageBox.warning(self, "Nom manquant", "Le nom du projet est obligatoire.")
                return
            self._analytique.creer_projet(**donnees)
            self._actualiser_liste()

    def _modifier_projet(self) -> None:
        item = self._liste.currentItem()
        if not item:
            return
        projet_id = item.data(Qt.UserRole)
        projet = self._analytique.get_projet(projet_id)
        if not projet:
            return
        dlg = DialogueProjet(projet, parent=self)
        if dlg.exec() == QDialog.Accepted:
            donnees = dlg.get_donnees()
            self._analytique.modifier_projet(projet_id, **donnees)
            self._actualiser_liste()

    def _supprimer_projet(self) -> None:
        item = self._liste.currentItem()
        if not item:
            return
        reponse = QMessageBox.question(
            self, "Confirmer la suppression",
            f"Supprimer le projet '{item.text().split(' — ')[0]}' ?\n"
            "Les transactions affectées à ce projet perdront leur affectation.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reponse == QMessageBox.Yes:
            self._analytique.supprimer_projet(item.data(Qt.UserRole))
            self._actualiser_liste()
