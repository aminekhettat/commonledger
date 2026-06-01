"""
Widget de génération des rapports — responsive.

L'aperçu textuel (QTextEdit) prend tout l'espace vertical disponible.
Les options et boutons restent fixes en hauteur.
"""

import logging
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QDateEdit, QPushButton, QFileDialog, QProgressBar,
    QTextEdit, QRadioButton, QCheckBox, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QDate, QThread, QObject

from ...core.accounting import Exercice, ComptaAnalytique
from ...core.accounting.compte_resultat import CompteResultat
from ...core.categorizer import MoteurCategorisation
from ...core.reporter import DocxReporter, CsvReporter
from ..accessibility import configurer_bouton, configurer_label_champ

logger = logging.getLogger(__name__)


class WorkerRapport(QObject):
    progression = Signal(str)
    termine = Signal(str)
    erreur = Signal(str)

    def __init__(self, reporter, cr, chemin, convertir_pdf, analytique, exercice):
        super().__init__()
        self.reporter = reporter
        self.cr = cr
        self.chemin = chemin
        self.convertir_pdf = convertir_pdf
        self.analytique = analytique
        self.exercice = exercice

    def run(self):
        try:
            self.progression.emit("Génération des graphiques…")
            bilans = (self.analytique.calculer_tous_bilans(
                self.exercice.transactions, self.reporter.moteur
            ) if self.analytique.projets else [])
            self.progression.emit("Construction du document Word…")
            docx = self.reporter.generer(
                self.cr, self.chemin, bilans_projets=bilans or None,
            )
            if self.convertir_pdf:
                self.progression.emit("Conversion en PDF…")
                pdf = self.reporter.convertir_en_pdf(docx)
                if pdf:
                    self.termine.emit(pdf)
                    return
            self.termine.emit(docx)
        except Exception as e:
            self.erreur.emit(str(e))


class ReportWidget(QWidget):
    message_status = Signal(str)

    def __init__(self, config_asso, moteur: MoteurCategorisation,
                 analytique: ComptaAnalytique):
        super().__init__()
        self._config = config_asso
        self._moteur = moteur
        self._analytique = analytique
        self._exercice = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Titre
        titre = QLabel("Génération du rapport comptable")
        titre.setStyleSheet("font-size:18px;font-weight:bold;color:#1a3a5c;")
        titre.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(titre)

        # ── Période ────────────────────────────────────────────────────────
        grp_p = QGroupBox("Période du rapport")
        grp_p.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay_p = QVBoxLayout(grp_p)

        self._radio_annuel = QRadioButton("&Rapport annuel complet")
        self._radio_annuel.setChecked(True)
        lay_p.addWidget(self._radio_annuel)

        self._radio_inter = QRadioButton("&Rapport intermédiaire (période personnalisée)")
        lay_p.addWidget(self._radio_inter)

        grp_dates = QGroupBox("Dates de la période")
        grp_dates.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay_d = QHBoxLayout(grp_dates)
        lbl_d = QLabel("Du :")
        self._date_debut = QDateEdit()
        self._date_debut.setDisplayFormat("dd/MM/yyyy")
        self._date_debut.setCalendarPopup(True)
        self._date_debut.setDate(QDate(date.today().year, 1, 1))
        configurer_label_champ(lbl_d, self._date_debut, "Date de début")
        lay_d.addWidget(lbl_d)
        lay_d.addWidget(self._date_debut)
        lbl_f = QLabel("Au :")
        self._date_fin = QDateEdit()
        self._date_fin.setDisplayFormat("dd/MM/yyyy")
        self._date_fin.setCalendarPopup(True)
        self._date_fin.setDate(QDate(date.today().year, 6, 30))
        configurer_label_champ(lbl_f, self._date_fin, "Date de fin")
        lay_d.addWidget(lbl_f)
        lay_d.addWidget(self._date_fin)
        lay_d.addStretch()
        grp_dates.setEnabled(False)
        self._radio_inter.toggled.connect(grp_dates.setEnabled)
        lay_p.addWidget(grp_dates)
        layout.addWidget(grp_p)

        # ── Aperçu — prend tout l'espace vertical restant ──────────────────
        grp_apercu = QGroupBox("Aperçu du résultat")
        grp_apercu.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay_apercu = QVBoxLayout(grp_apercu)

        btn_bar = QHBoxLayout()
        self._btn_apercu = QPushButton("🔄 &Calculer l'aperçu")
        self._btn_apercu.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        configurer_bouton(self._btn_apercu, "Calculer l'aperçu")
        self._btn_apercu.clicked.connect(self._calculer_apercu)
        btn_bar.addWidget(self._btn_apercu)
        btn_bar.addStretch()
        lay_apercu.addLayout(btn_bar)

        self._lbl_apercu = QTextEdit()
        self._lbl_apercu.setReadOnly(True)
        self._lbl_apercu.setFontFamily("Courier New")
        self._lbl_apercu.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._lbl_apercu.setAccessibleName("Aperçu du compte de résultat")
        lay_apercu.addWidget(self._lbl_apercu, stretch=1)

        layout.addWidget(grp_apercu, stretch=1)

        # ── Options export ─────────────────────────────────────────────────
        grp_opt = QGroupBox("Options d'export")
        grp_opt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay_opt = QVBoxLayout(grp_opt)
        self._chk_pdf = QCheckBox("&Convertir automatiquement en PDF")
        self._chk_pdf.setChecked(True)
        lay_opt.addWidget(self._chk_pdf)
        layout.addWidget(grp_opt)

        # ── Bouton + progression ───────────────────────────────────────────
        self._btn_generer = QPushButton("📄 &Générer le rapport")
        self._btn_generer.setMinimumHeight(44)
        self._btn_generer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn_generer.setStyleSheet(
            "QPushButton{background:#1a3a5c;color:white;font-size:14px;"
            "border-radius:6px;padding:8px 24px;}"
            "QPushButton:hover{background:#2a5a8c;}"
            "QPushButton:disabled{background:#aaa;}"
        )
        configurer_bouton(self._btn_generer, "Générer le rapport Word")
        self._btn_generer.clicked.connect(self._generer_rapport)
        layout.addWidget(self._btn_generer)

        self._barre_prog = QProgressBar()
        self._barre_prog.setVisible(False)
        self._barre_prog.setRange(0, 0)
        self._barre_prog.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self._barre_prog)

        self._lbl_status = QLabel("")
        self._lbl_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self._lbl_status)

    def set_exercice(self, exercice: Exercice):
        self._exercice = exercice
        d = self._date_debut.date()
        self._date_debut.setDate(QDate(exercice.annee, 1, 1))
        self._date_fin.setDate(QDate(exercice.annee, 12, 31))

    def set_config(self, config):
        self._config = config

    def _get_periode(self):
        if self._radio_annuel.isChecked() and self._exercice:
            return self._exercice.date_debut, self._exercice.date_fin
        d = self._date_debut.date()
        f = self._date_fin.date()
        return date(d.year(), d.month(), d.day()), date(f.year(), f.month(), f.day())

    def _calculer_apercu(self):
        if not self._exercice:
            self._lbl_apercu.setPlainText("Aucun exercice chargé.")
            return
        debut, fin = self._get_periode()
        cr = self._exercice.calculer_compte_resultat(self._moteur, debut, fin)
        lignes = [
            f"Période : {debut.strftime('%d/%m/%Y')} → {fin.strftime('%d/%m/%Y')}",
            f"Transactions analysées : {len(cr._transactions_periode)}",
            f"Non catégorisées : {len(cr.transactions_non_categorisees)}",
            "",
            "RECETTES :",
        ]
        for l in cr.lignes_recettes:
            lignes.append(
                f"  {l.label:<42} {float(l.montant):>10,.2f} €  ({l.pourcentage:.1f}%)"
            )
        lignes.append(f"  {'TOTAL RECETTES':<42} {float(cr.total_recettes):>10,.2f} €")
        lignes.extend(["", "DÉPENSES :"])
        for l in cr.lignes_depenses:
            lignes.append(
                f"  {l.label:<42} {float(l.montant):>10,.2f} €  ({l.pourcentage:.1f}%)"
            )
        lignes.append(f"  {'TOTAL DÉPENSES':<42} {float(cr.total_depenses):>10,.2f} €")
        signe = "+" if cr.est_excedentaire else ""
        lignes.extend(["", f"  {'RÉSULTAT NET':<42} {signe}{float(cr.resultat_net):>10,.2f} €"])
        self._lbl_apercu.setPlainText("\n".join(lignes))

    def _generer_rapport(self):
        if not self._exercice:
            QMessageBox.warning(self, "Aucun exercice", "Importez d'abord un exercice (Alt+1).")
            return
        debut, fin = self._get_periode()
        nom = (f"Rapport_{self._exercice.annee}.docx" if self._radio_annuel.isChecked()
               else f"Rapport_{debut.strftime('%Y%m%d')}_{fin.strftime('%Y%m%d')}.docx")
        chemin, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le rapport",
            str(Path.home() / nom), "Documents Word (*.docx)",
        )
        if not chemin:
            return
        cr = self._exercice.calculer_compte_resultat(self._moteur, debut, fin)
        reporter = DocxReporter(self._config, self._moteur)
        self._btn_generer.setEnabled(False)
        self._barre_prog.setVisible(True)
        self._lbl_status.setText("Génération en cours…")
        self._thread = QThread()
        self._worker = WorkerRapport(
            reporter, cr, chemin, self._chk_pdf.isChecked(),
            self._analytique, self._exercice,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progression.connect(self._lbl_status.setText)
        self._worker.termine.connect(self._on_termine)
        self._worker.erreur.connect(self._on_erreur)
        self._worker.termine.connect(self._thread.quit)
        self._worker.erreur.connect(self._thread.quit)
        self._thread.start()

    def _on_termine(self, chemin):
        self._btn_generer.setEnabled(True)
        self._barre_prog.setVisible(False)
        self._lbl_status.setText(f"Rapport généré : {Path(chemin).name}")
        self.message_status.emit(f"Rapport généré : {Path(chemin).name}")
        QMessageBox.information(self, "Rapport généré",
            f"Rapport généré avec succès :\n\n{chemin}")
        os.startfile(chemin)

    def _on_erreur(self, erreur):
        self._btn_generer.setEnabled(True)
        self._barre_prog.setVisible(False)
        self._lbl_status.setText(f"Erreur : {erreur}")
        QMessageBox.critical(self, "Erreur", f"Erreur lors de la génération :\n\n{erreur}")
