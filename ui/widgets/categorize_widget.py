"""
Widget de catégorisation — responsive avec colonne Projet et split universel.

Nouveautés :
  - Colonne "Projet" dans le tableau : combo inline pour affecter un projet
  - Split disponible pour TOUTES les transactions (pas seulement HelloAsso)
  - Bandeau HelloAsso informatif (mais split toujours accessible)
  - Dialogue de catégorisation enrichi avec sélecteur de projet
"""

import logging
from decimal import Decimal

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QGroupBox, QComboBox,
    QLineEdit, QDialog, QFormLayout, QDialogButtonBox,
    QMessageBox, QDoubleSpinBox, QSizePolicy, QScrollArea,
    QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut

from core.accounting import Exercice, ComptaAnalytique
from core.categorizer import MoteurCategorisation
from core.parser.models import Transaction, TransactionSplit
from ui.accessibility import (
    configurer_tableau, configurer_bouton, configurer_label_champ,
    definir_ordre_tabulation,
)

logger = logging.getLogger(__name__)

_COULEUR_NON_CAT = QColor("#fff3cd")
_COULEUR_CAT     = QColor("#d4edda")
_COULEUR_SPLIT   = QColor("#cce5ff")

# Colonnes du tableau
COL_DATE     = 0
COL_LIBELLE  = 1
COL_MONTANT  = 2
COL_TYPE     = 3
COL_CATEGORIE= 4
COL_PROJET   = 5
COL_MEMO     = 6


class DialogueCategorisation(QDialog):
    """
    Dialogue de catégorisation / split d'une transaction.

    Le split est disponible pour TOUTES les transactions,
    avec un bandeau informatif si HelloAsso est détecté.
    """

    def __init__(self, transaction: Transaction, moteur: MoteurCategorisation,
                 analytique: ComptaAnalytique, parent=None):
        super().__init__(parent)
        self._transaction = transaction
        self._moteur = moteur
        self._analytique = analytique
        self._splits = []
        self.setWindowTitle(f"Catégoriser : {transaction.libelle[:50]}")
        self.setMinimumWidth(540)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Infos transaction
        grp_info = QGroupBox("Transaction")
        f = QFormLayout(grp_info)
        f.addRow("Date :", QLabel(self._transaction.date.strftime("%d/%m/%Y")))
        lbl_lib = QLabel(self._transaction.libelle[:100])
        lbl_lib.setWordWrap(True)
        f.addRow("Libellé :", lbl_lib)
        f.addRow("Montant :", QLabel(f"{self._transaction.montant:,.2f} €"))
        layout.addWidget(grp_info)

        # Bandeau HelloAsso (informatif seulement)
        if self._moteur.est_helloasso(self._transaction):
            lbl = QLabel(
                "ℹ Virement HelloAsso détecté — pensez à éclater entre "
                "Cotisations et Dons si nécessaire."
            )
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                "background:#e8f4fd;color:#0d6efd;border:1px solid #bee5eb;"
                "border-radius:4px;padding:6px;font-style:italic;"
            )
            layout.addWidget(lbl)

        # Catégorie + Projet
        grp_cat = QGroupBox("Catégorie et projet")
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
        configurer_label_champ(QLabel("Catégorie"), self._combo_cat,
                               "Catégorie comptable",
                               "Choisissez la catégorie correspondant à cette transaction.")
        f2.addRow("Catégorie :", self._combo_cat)

        # Sélecteur de projet
        self._combo_projet = QComboBox()
        self._combo_projet.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._combo_projet.addItem("— Aucun projet —", None)
        for projet in self._analytique.projets_actifs():
            self._combo_projet.addItem(projet.nom, projet.id)
        if self._transaction.projet_id:
            idx = self._combo_projet.findData(self._transaction.projet_id)
            if idx >= 0:
                self._combo_projet.setCurrentIndex(idx)
        configurer_label_champ(QLabel("Projet"), self._combo_projet,
                               "Projet analytique",
                               "Rattachez cette transaction à un projet (optionnel).")
        f2.addRow("Projet :", self._combo_projet)

        self._edit_memo = QLineEdit()
        self._edit_memo.setPlaceholderText("Note libre optionnelle…")
        if self._transaction.memo:
            self._edit_memo.setText(self._transaction.memo)
        configurer_label_champ(QLabel("Mémo"), self._edit_memo, "Mémo libre")
        f2.addRow("Mémo :", self._edit_memo)

        layout.addWidget(grp_cat)

        # Bouton split — toujours visible
        self._btn_split = QPushButton("✂ &Éclater cette transaction en plusieurs catégories")
        self._btn_split.setStyleSheet(
            "QPushButton{border:1px solid #1a3a5c;color:#1a3a5c;padding:6px;"
            "border-radius:4px;}"
            "QPushButton:hover{background:#e8f0f7;}"
        )
        configurer_bouton(self._btn_split, "Éclater la transaction",
                          "Répartir le montant entre plusieurs catégories et/ou projets.")
        self._btn_split.clicked.connect(self._ouvrir_split)
        layout.addWidget(self._btn_split)

        boutons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        boutons.button(QDialogButtonBox.Ok).setText("&Valider")
        boutons.button(QDialogButtonBox.Cancel).setText("&Annuler")
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        layout.addWidget(boutons)

    def _ouvrir_split(self):
        dlg = DialogueSplit(self._transaction, self._moteur, self._analytique, self)
        if dlg.exec() == QDialog.Accepted:
            self._splits = dlg.get_splits()
            self._combo_cat.setEnabled(False)
            self._combo_projet.setEnabled(False)
            nb = len(self._splits)
            self._btn_split.setText(f"✅ Éclaté en {nb} partie(s) — cliquer pour modifier")

    def _valider(self):
        if self._splits:
            try:
                self._moteur.creer_split(self._transaction, self._splits)
            except ValueError as e:
                QMessageBox.warning(self, "Erreur de split", str(e))
                return
        else:
            cat_id = self._combo_cat.currentData()
            if not cat_id:
                QMessageBox.warning(self, "Catégorie manquante",
                                    "Choisissez une catégorie ou éclatez la transaction.")
                return
            self._transaction.categorie_id = cat_id
            self._transaction.projet_id = self._combo_projet.currentData()
            self._transaction.verrouille = True

        self._transaction.memo = self._edit_memo.text().strip()
        self.accept()


class DialogueSplit(QDialog):
    """
    Dialogue d'éclatement d'une transaction en plusieurs parts.

    Chaque part peut avoir sa propre catégorie ET son propre projet.
    Disponible pour toutes les transactions.
    """

    def __init__(self, transaction: Transaction, moteur: MoteurCategorisation,
                 analytique: ComptaAnalytique, parent=None):
        super().__init__(parent)
        self._transaction = transaction
        self._moteur = moteur
        self._analytique = analytique
        self._lignes = []
        montant_abs = abs(transaction.montant)
        self.setWindowTitle(f"Éclater {montant_abs:,.2f} €")
        self.setModal(True)
        self.setMinimumWidth(640)
        self.setMinimumHeight(400)
        self._montant_total = montant_abs
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # En-tête
        lbl_info = QLabel(
            f"Répartissez <b>{self._montant_total:,.2f} €</b> entre plusieurs "
            f"catégories. La somme doit être égale au total.\n"
            f"Chaque ligne peut avoir sa propre catégorie et son propre projet."
        )
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        # Solde restant
        self._lbl_restant = QLabel()
        self._lbl_restant.setStyleSheet("font-weight:bold; color:#1a3a5c; padding:4px;")
        self._maj_restant()
        layout.addWidget(self._lbl_restant)

        # En-têtes des colonnes
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Catégorie"), 3)
        hdr.addWidget(QLabel("Montant (€)"), 1)
        hdr.addWidget(QLabel("Projet (optionnel)"), 2)
        layout.addLayout(hdr)

        # Zone scrollable pour les lignes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        conteneur = QWidget()
        self._lay_splits = QVBoxLayout(conteneur)
        self._lay_splits.setSpacing(4)
        scroll.setWidget(conteneur)
        layout.addWidget(scroll, stretch=1)

        # Pré-remplir 2 lignes
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
        row_lay.setSpacing(6)

        combo_cat = QComboBox()
        combo_cat.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo_cat.addItem("— Catégorie —", None)
        for cat in self._moteur.categories_par_type(type_tx):
            combo_cat.addItem(cat.label, cat.id)

        spin = QDoubleSpinBox()
        spin.setRange(0.01, float(abs(self._transaction.montant)))
        spin.setDecimals(2)
        spin.setSuffix(" €")
        spin.setFixedWidth(120)
        spin.valueChanged.connect(self._maj_restant)

        combo_proj = QComboBox()
        combo_proj.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo_proj.addItem("— Aucun projet —", None)
        for projet in self._analytique.projets_actifs():
            combo_proj.addItem(projet.nom, projet.id)

        row_lay.addWidget(combo_cat, 3)
        row_lay.addWidget(spin, 1)
        row_lay.addWidget(combo_proj, 2)
        self._lay_splits.addWidget(row)
        self._lignes.append({"combo": combo_cat, "spin": spin, "projet": combo_proj})

    def _maj_restant(self):
        """Met à jour le label du montant restant à ventiler."""
        deja = sum(Decimal(str(l["spin"].value())) for l in self._lignes)
        restant = self._montant_total - deja
        couleur = "#27AE60" if abs(restant) < Decimal("0.01") else (
            "#E74C3C" if restant < 0 else "#E67E22"
        )
        self._lbl_restant.setText(
            f"Restant à ventiler : <span style='color:{couleur}'>"
            f"{restant:,.2f} €</span>"
            f"  (alloué : {deja:,.2f} € / {self._montant_total:,.2f} €)"
        )

    def get_splits(self) -> list:
        return [
            (l["combo"].currentData(), Decimal(str(l["spin"].value())), l["projet"].currentData())
            for l in self._lignes
            if l["combo"].currentData() and l["spin"].value() > 0
        ]


class CategorizeWidget(QWidget):
    """Widget de catégorisation avec colonne Projet et split universel."""

    message_status = Signal(str)

    def __init__(self, moteur: MoteurCategorisation, analytique: ComptaAnalytique = None):
        super().__init__()
        self._moteur = moteur
        self._analytique = analytique or ComptaAnalytique("data/projets.json")
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

        # Barre d'outils
        barre = QHBoxLayout()
        self._lbl_stats = QLabel("Aucun exercice chargé.")
        self._lbl_stats.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._lbl_stats.setAccessibleName("Statistiques de catégorisation")
        barre.addWidget(self._lbl_stats, stretch=1)

        self._btn_cat_auto = QPushButton("⚡ &Catégorisation auto")
        self._btn_cat_auto.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        configurer_bouton(self._btn_cat_auto, "Catégorisation automatique")
        self._btn_cat_auto.clicked.connect(self._categ_auto)
        barre.addWidget(self._btn_cat_auto)

        self._btn_filtrer = QPushButton("🔍 &Non catégorisées")
        self._btn_filtrer.setCheckable(True)
        self._btn_filtrer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        configurer_bouton(self._btn_filtrer, "Afficher uniquement les non catégorisées")
        self._btn_filtrer.toggled.connect(self._actualiser_tableau)
        barre.addWidget(self._btn_filtrer)
        layout.addLayout(barre)

        # Tableau — 7 colonnes dont Projet
        self._tableau = QTableWidget(0, 7)
        self._tableau.setHorizontalHeaderLabels(
            ["Date", "Libellé", "Montant (€)", "Type", "Catégorie", "Projet", "Mémo"]
        )
        hdr = self._tableau.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)       # Libellé s'étire
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.Interactive)
        hdr.setSectionResizeMode(5, QHeaderView.Interactive)   # Projet
        hdr.setSectionResizeMode(6, QHeaderView.Interactive)
        hdr.setDefaultSectionSize(140)
        self._tableau.setSelectionBehavior(QTableWidget.SelectRows)
        self._tableau.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tableau.setAlternatingRowColors(True)
        self._tableau.verticalHeader().setVisible(False)
        self._tableau.setSortingEnabled(True)
        self._tableau.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tableau.itemDoubleClicked.connect(self._ouvrir_categorisation)
        configurer_tableau(
            self._tableau, "Tableau des transactions",
            "Double-cliquez ou Entrée pour catégoriser. Colonnes : Date, Libellé, "
            "Montant, Type, Catégorie, Projet, Mémo.",
            ["Date", "Libellé", "Montant", "Type", "Catégorie", "Projet", "Mémo"],
        )
        sc = QShortcut(QKeySequence(Qt.Key_Return), self._tableau)
        sc.activated.connect(self._ouvrir_categorisation_selectionnee)
        layout.addWidget(self._tableau, stretch=1)

        # Bouton sauvegarder
        self._btn_sauv = QPushButton("💾 &Sauvegarder les catégorisations")
        self._btn_sauv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        configurer_bouton(self._btn_sauv, "Sauvegarder toutes les catégorisations")
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

            # Libellé de projet
            projet_label = ""
            if t.projet_id:
                proj = self._analytique.get_projet(t.projet_id)
                projet_label = proj.nom if proj else t.projet_id
            elif t.est_splittee:
                projets_splits = set(
                    s.projet_id for s in t.splits if s.projet_id
                )
                if projets_splits:
                    noms = []
                    for pid in projets_splits:
                        pr = self._analytique.get_projet(pid)
                        noms.append(pr.nom if pr else pid)
                    projet_label = ", ".join(noms)

            items = [
                QTableWidgetItem(t.date.strftime("%d/%m/%Y")),
                QTableWidgetItem(t.libelle[:100]),
                QTableWidgetItem(f"{t.montant:+,.2f} €"),
                QTableWidgetItem("Recette" if t.est_credit else "Dépense"),
                QTableWidgetItem(self._label_categorie(t)),
                QTableWidgetItem(projet_label),
                QTableWidgetItem(t.memo),
            ]
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setData(Qt.UserRole, t)
                self._tableau.setItem(row, col, item)

            couleur = (_COULEUR_SPLIT   if t.est_splittee else
                       _COULEUR_CAT     if t.est_categorisee else
                       _COULEUR_NON_CAT)
            for col in range(7):
                self._tableau.item(row, col).setBackground(couleur)

        self._tableau.setSortingEnabled(True)
        total = len(self._exercice.transactions)
        nc = len(self._exercice.transactions_non_categorisees())
        self._lbl_stats.setText(
            f"Total : {total}  |  Catégorisées : {total - nc} ✅  |  À traiter : {nc} ⚠"
        )

    def _label_categorie(self, t):
        if t.est_splittee:
            parts = []
            for s in t.splits:
                cat = self._moteur.get_categorie(s.categorie_id)
                parts.append(f"{cat.label if cat else s.categorie_id}")
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
        dlg = DialogueCategorisation(t, self._moteur, self._analytique, self)
        if dlg.exec() == QDialog.Accepted:
            self._actualiser_tableau()
            nc = len(self._exercice.transactions_non_categorisees())
            self.message_status.emit(
                f"Catégorisation enregistrée. {nc} transaction(s) restante(s)."
            )

    def _ouvrir_categorisation_selectionnee(self):
        self._ouvrir_categorisation()

    def _categ_auto(self):
        if not self._exercice:
            return
        stats = self._moteur.categoriser_lot(self._exercice.transactions)
        self._actualiser_tableau()
        QMessageBox.information(
            self, "Catégorisation automatique",
            f"Terminé !\n\nCatégorisées auto : {stats['auto']}\n"
            f"À traiter : {stats['a_traiter']}\nDéjà faites : {stats['deja_faites']}",
        )

    def _sauvegarder(self):
        if self._exercice:
            self._exercice.sauvegarder()
            self.message_status.emit("Catégorisations sauvegardées.")
