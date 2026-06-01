"""
Widget de catégorisation — responsive.

Le tableau prend tout l'espace vertical disponible grâce à stretch=1.
La barre d'outils (stats + boutons) est fixe en hauteur.
Les dialogues s'adaptent à leur contenu.
"""

import logging
from decimal import Decimal

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QGroupBox, QComboBox,
    QLineEdit, QDialog, QFormLayout, QDialogButtonBox,
    QMessageBox, QDoubleSpinBox, QSizePolicy, QSplitter,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut

from ...core.accounting import Exercice
from ...core.categorizer import MoteurCategorisation
from ...core.parser.models import Transaction, TransactionSplit
from ..accessibility import (
    configurer_tableau, configurer_bouton, configurer_label_champ,
    definir_ordre_tabulation,
)

logger = logging.getLogger(__name__)

_COULEUR_NON_CAT = QColor("#fff3cd")
_COULEUR_CAT     = QColor("#d4edda")
_COULEUR_SPLIT   = QColor("#cce5ff")


class DialogueCategorisation(QDialog):
    def __init__(self, transaction: Transaction, moteur: MoteurCategorisation, parent=None):
        super().__init__(parent)
        self._transaction = transaction
        self._moteur = moteur
        self._splits = []
        self.setWindowTitle(f"Catégoriser : {transaction.libelle[:50]}")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Infos transaction
        grp = QGroupBox("Transaction")
        f = QFormLayout(grp)
        f.addRow("Date :", QLabel(self._transaction.date.strftime("%d/%m/%Y")))
        f.addRow("Libellé :", QLabel(self._transaction.libelle[:80]))
        f.addRow("Montant :", QLabel(f"{self._transaction.montant:,.2f} €"))
        layout.addWidget(grp)

        if self._moteur.est_helloasso(self._transaction):
            lbl = QLabel("ℹ Ce virement semble provenir de HelloAsso. Vous pouvez l'éclater.")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#0d6efd; font-style:italic; padding:4px;")
            layout.addWidget(lbl)

        # Catégorie
        grp_cat = QGroupBox("Catégorie")
        f2 = QFormLayout(grp_cat)
        type_tx = "recettes" if self._transaction.est_credit else "depenses"
        self._combo_cat = QComboBox()
        self._combo_cat.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._combo_cat.addItem("— Choisir une catégorie —", None)
        for cat in self._moteur.categories_par_type(type_tx):
            self._combo_cat.addItem(cat.label, cat.id)
        if self._transaction.categorie_id:
            idx = self._combo_cat.findData(self._transaction.categorie_id)
            if idx >= 0:
                self._combo_cat.setCurrentIndex(idx)
        configurer_label_champ(QLabel("Catégorie"), self._combo_cat, "Catégorie comptable")
        f2.addRow("Catégorie :", self._combo_cat)

        self._edit_memo = QLineEdit()
        self._edit_memo.setPlaceholderText("Note libre optionnelle…")
        if self._transaction.memo:
            self._edit_memo.setText(self._transaction.memo)
        configurer_label_champ(QLabel("Mémo"), self._edit_memo, "Mémo")
        f2.addRow("Mémo :", self._edit_memo)
        layout.addWidget(grp_cat)

        # Bouton split
        self._btn_split = QPushButton("➕ &Éclater cette transaction (split)")
        configurer_bouton(self._btn_split, "Éclater la transaction",
                          "Répartir le montant entre plusieurs catégories.")
        self._btn_split.clicked.connect(self._ouvrir_split)
        layout.addWidget(self._btn_split)

        boutons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        boutons.button(QDialogButtonBox.Ok).setText("&Valider")
        boutons.button(QDialogButtonBox.Cancel).setText("&Annuler")
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        layout.addWidget(boutons)

    def _ouvrir_split(self):
        dlg = DialogueSplit(self._transaction, self._moteur, self)
        if dlg.exec() == QDialog.Accepted:
            self._splits = dlg.get_splits()
            self._combo_cat.setEnabled(False)
            self._btn_split.setText(f"✅ Éclaté en {len(self._splits)} partie(s)")

    def _valider(self):
        if self._splits:
            try:
                self._moteur.creer_split(self._transaction, self._splits)
            except ValueError as e:
                QMessageBox.warning(self, "Erreur", str(e))
                return
        else:
            cat_id = self._combo_cat.currentData()
            if not cat_id:
                QMessageBox.warning(self, "Catégorie manquante",
                                    "Choisissez une catégorie ou éclatez la transaction.")
                return
            self._transaction.categorie_id = cat_id
            self._transaction.verrouille = True
        self._transaction.memo = self._edit_memo.text().strip()
        self.accept()


class DialogueSplit(QDialog):
    def __init__(self, transaction: Transaction, moteur: MoteurCategorisation, parent=None):
        super().__init__(parent)
        self._transaction = transaction
        self._moteur = moteur
        self._lignes = []
        montant_abs = abs(transaction.montant)
        self.setWindowTitle(f"Éclater {montant_abs:,.2f} € en plusieurs catégories")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._montant_total = montant_abs
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        lbl = QLabel(
            f"Répartissez {self._montant_total:,.2f} € entre plusieurs catégories.\n"
            f"La somme doit être égale au total."
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        # Zone scrollable pour les lignes de split
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        conteneur = QWidget()
        self._lay_splits = QVBoxLayout(conteneur)
        self._lay_splits.setSpacing(6)
        scroll.setWidget(conteneur)
        layout.addWidget(scroll, stretch=1)

        self._ajouter_ligne()
        self._ajouter_ligne()

        btn_ajouter = QPushButton("&Ajouter une ligne")
        btn_ajouter.clicked.connect(self._ajouter_ligne)
        layout.addWidget(btn_ajouter, alignment=Qt.AlignLeft)

        boutons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        boutons.button(QDialogButtonBox.Ok).setText("&Valider le split")
        boutons.button(QDialogButtonBox.Cancel).setText("&Annuler")
        boutons.accepted.connect(self.accept)
        boutons.rejected.connect(self.reject)
        layout.addWidget(boutons)

    def _ajouter_ligne(self):
        type_tx = "recettes" if self._transaction.est_credit else "depenses"
        row = QWidget()
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(0, 0, 0, 0)
        combo = QComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.addItem("— Catégorie —", None)
        for cat in self._moteur.categories_par_type(type_tx):
            combo.addItem(cat.label, cat.id)
        spin = QDoubleSpinBox()
        spin.setRange(0.01, float(abs(self._transaction.montant)))
        spin.setDecimals(2)
        spin.setSuffix(" €")
        spin.setFixedWidth(130)
        row_lay.addWidget(combo, stretch=3)
        row_lay.addWidget(spin, stretch=1)
        self._lay_splits.addWidget(row)
        self._lignes.append({"combo": combo, "spin": spin})

    def get_splits(self):
        return [
            (l["combo"].currentData(), Decimal(str(l["spin"].value())), None)
            for l in self._lignes
            if l["combo"].currentData() and l["spin"].value() > 0
        ]


class CategorizeWidget(QWidget):
    message_status = Signal(str)

    def __init__(self, moteur: MoteurCategorisation):
        super().__init__()
        self._moteur = moteur
        self._exercice = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Titre
        titre = QLabel("Catégorisation des transactions")
        titre.setStyleSheet("font-size:18px;font-weight:bold;color:#1a3a5c;")
        titre.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(titre)

        # Barre d'outils — hauteur fixe
        barre = QHBoxLayout()
        barre.setSpacing(8)

        self._lbl_stats = QLabel("Aucun exercice chargé.")
        self._lbl_stats.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._lbl_stats.setAccessibleName("Statistiques de catégorisation")
        barre.addWidget(self._lbl_stats, stretch=1)

        self._btn_cat_auto = QPushButton("⚡ &Catégorisation auto")
        self._btn_cat_auto.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        configurer_bouton(self._btn_cat_auto, "Catégorisation automatique")
        self._btn_cat_auto.clicked.connect(self._categ_auto)
        barre.addWidget(self._btn_cat_auto)

        self._btn_filtrer = QPushButton("🔍 &Non catégorisées seulement")
        self._btn_filtrer.setCheckable(True)
        self._btn_filtrer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        configurer_bouton(self._btn_filtrer, "Filtrer transactions non catégorisées")
        self._btn_filtrer.toggled.connect(self._actualiser_tableau)
        barre.addWidget(self._btn_filtrer)

        layout.addLayout(barre)

        # Tableau — prend TOUT l'espace vertical restant
        self._tableau = QTableWidget(0, 6)
        self._tableau.setHorizontalHeaderLabels(
            ["Date", "Libellé", "Montant (€)", "Type", "Catégorie", "Mémo"]
        )
        self._tableau.horizontalHeader().setStretchLastSection(True)
        self._tableau.horizontalHeader().setSectionResizeMode(
            1, self._tableau.horizontalHeader().Stretch
        )
        self._tableau.setSelectionBehavior(QTableWidget.SelectRows)
        self._tableau.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tableau.setAlternatingRowColors(True)
        self._tableau.verticalHeader().setVisible(False)
        self._tableau.setSortingEnabled(True)
        self._tableau.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tableau.itemDoubleClicked.connect(self._ouvrir_categorisation)
        configurer_tableau(
            self._tableau, "Tableau des transactions",
            "Double-cliquez ou Entrée pour catégoriser la ligne sélectionnée.",
            ["Date", "Libellé", "Montant", "Type", "Catégorie", "Mémo"],
        )

        sc = QShortcut(QKeySequence(Qt.Key_Return), self._tableau)
        sc.activated.connect(self._ouvrir_categorisation_selectionnee)

        # stretch=1 → le tableau s'étire verticalement avec la fenêtre
        layout.addWidget(self._tableau, stretch=1)

        # Bouton sauvegarde — hauteur fixe en bas
        self._btn_sauv = QPushButton("💾 &Sauvegarder les catégorisations")
        self._btn_sauv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        configurer_bouton(self._btn_sauv, "Sauvegarder")
        self._btn_sauv.clicked.connect(self._sauvegarder)
        layout.addWidget(self._btn_sauv)

    def set_exercice(self, exercice: Exercice):
        self._exercice = exercice
        self._actualiser_tableau()

    def _actualiser_tableau(self):
        if not self._exercice:
            return
        filtrer = self._btn_filtrer.isChecked()
        transactions = (
            self._exercice.transactions_non_categorisees()
            if filtrer else self._exercice.transactions
        )
        self._tableau.setSortingEnabled(False)
        self._tableau.setRowCount(0)
        for t in transactions:
            row = self._tableau.rowCount()
            self._tableau.insertRow(row)
            items = [
                QTableWidgetItem(t.date.strftime("%d/%m/%Y")),
                QTableWidgetItem(t.libelle[:80]),
                QTableWidgetItem(f"{t.montant:+,.2f} €"),
                QTableWidgetItem("Recette" if t.est_credit else "Dépense"),
                QTableWidgetItem(self._label_categorie(t)),
                QTableWidgetItem(t.memo),
            ]
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setData(Qt.UserRole, t)
                self._tableau.setItem(row, col, item)
            couleur = (_COULEUR_SPLIT if t.est_splittee else
                       _COULEUR_CAT   if t.est_categorisee else
                       _COULEUR_NON_CAT)
            for col in range(6):
                self._tableau.item(row, col).setBackground(couleur)
        self._tableau.setSortingEnabled(True)
        self._tableau.resizeColumnToContents(0)
        self._tableau.resizeColumnToContents(2)
        self._tableau.resizeColumnToContents(3)

        total = len(self._exercice.transactions)
        nc = len(self._exercice.transactions_non_categorisees())
        self._lbl_stats.setText(
            f"Total : {total}  |  Catégorisées : {total-nc} ✅  |  À traiter : {nc} ⚠"
        )

    def _label_categorie(self, t):
        if t.est_splittee:
            parts = []
            for s in t.splits:
                cat = self._moteur.get_categorie(s.categorie_id)
                parts.append(f"{cat.label if cat else s.categorie_id} ({s.montant}€)")
            return " + ".join(parts)
        if t.categorie_id:
            cat = self._moteur.get_categorie(t.categorie_id)
            return cat.label if cat else t.categorie_id
        return "— Non catégorisée —"

    def _ouvrir_categorisation(self, item=None):
        row = self._tableau.currentRow() if item is None else item.row()
        it = self._tableau.item(row, 0)
        if not it:
            return
        t: Transaction = it.data(Qt.UserRole)
        dlg = DialogueCategorisation(t, self._moteur, self)
        if dlg.exec() == QDialog.Accepted:
            self._actualiser_tableau()
            nc = len(self._exercice.transactions_non_categorisees())
            self.message_status.emit(f"Catégorisation enregistrée. {nc} restante(s).")

    def _ouvrir_categorisation_selectionnee(self):
        self._ouvrir_categorisation()

    def _categ_auto(self):
        if not self._exercice:
            return
        stats = self._moteur.categoriser_lot(self._exercice.transactions)
        self._actualiser_tableau()
        QMessageBox.information(self, "Catégorisation automatique",
            f"Terminé !\n\n"
            f"  Catégorisées auto : {stats['auto']}\n"
            f"  À traiter manuellement : {stats['a_traiter']}\n"
            f"  Déjà catégorisées : {stats['deja_faites']}")

    def _sauvegarder(self):
        if self._exercice:
            self._exercice.sauvegarder()
            self.message_status.emit("Catégorisations sauvegardées.")
