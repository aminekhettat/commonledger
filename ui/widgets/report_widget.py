"""
Widget de génération du rapport comptable.

Permet de choisir la période du rapport (annuel ou intermédiaire),
d'en afficher un aperçu synthétique, puis de lancer la génération
du fichier Word et optionnellement sa conversion en PDF.
"""

import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QDateEdit, QPushButton, QFileDialog, QProgressBar,
    QTextEdit, QRadioButton, QButtonGroup, QComboBox,
    QDoubleSpinBox, QCheckBox, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QDate, QThread, QObject

from ...core.accounting import Exercice, ComptaAnalytique
from ...core.accounting.compte_resultat import CompteResultat
from ...core.categorizer import MoteurCategorisation
from ...core.reporter import DocxReporter
from ..accessibility import configurer_bouton, configurer_label_champ, definir_ordre_tabulation

logger = logging.getLogger(__name__)


class WorkerRapport(QObject):
    """Thread de génération du rapport (ne bloque pas l'UI)."""
    progression = Signal(str)
    termine = Signal(str)
    erreur = Signal(str)

    def __init__(
        self, reporter: DocxReporter, compte_resultat: CompteResultat,
        chemin: str, convertir_pdf: bool, analytique: ComptaAnalytique,
        exercice: Exercice,
    ):
        super().__init__()
        self.reporter = reporter
        self.compte_resultat = compte_resultat
        self.chemin = chemin
        self.convertir_pdf = convertir_pdf
        self.analytique = analytique
        self.exercice = exercice

    def run(self) -> None:
        try:
            self.progression.emit("Génération des graphiques…")
            bilans = self.analytique.calculer_tous_bilans(
                self.exercice.transactions, self.reporter.moteur
            ) if self.analytique.projets else []

            self.progression.emit("Construction du document Word…")
            chemin_docx = self.reporter.generer(
                self.compte_resultat,
                self.chemin,
                bilans_projets=bilans if bilans else None,
            )

            if self.convertir_pdf:
                self.progression.emit("Conversion en PDF…")
                chemin_pdf = self.reporter.convertir_en_pdf(chemin_docx)
                if chemin_pdf:
                    self.termine.emit(chemin_pdf)
                    return

            self.termine.emit(chemin_docx)

        except Exception as e:
            self.erreur.emit(str(e))


class ReportWidget(QWidget):
    """
    Widget de génération des rapports.

    Signals:
        message_status (str): Émis pour mettre à jour la barre de statut.
    """
    message_status = Signal(str)

    def __init__(self, config_asso: dict, moteur: MoteurCategorisation, analytique: ComptaAnalytique):
        super().__init__()
        self._config = config_asso
        self._moteur = moteur
        self._analytique = analytique
        self._exercice: Exercice | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        titre = QLabel("Génération du rapport comptable")
        titre.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a3a5c;")
        layout.addWidget(titre)

        # ── Groupe : Période ─────────────────────────────────────────────────
        grp_periode = QGroupBox("Période du rapport")
        grp_periode.setAccessibleDescription(
            "Choisissez si vous souhaitez un rapport annuel ou pour une période personnalisée."
        )
        lay_p = QVBoxLayout(grp_periode)

        self._radio_annuel = QRadioButton("&Rapport annuel complet")
        self._radio_annuel.setChecked(True)
        self._radio_annuel.setAccessibleDescription("Rapport du 1er janvier au 31 décembre.")
        lay_p.addWidget(self._radio_annuel)

        self._radio_intermediaire = QRadioButton("&Rapport intermédiaire (période personnalisée)")
        self._radio_intermediaire.setAccessibleDescription(
            "Définissez manuellement la date de début et de fin du rapport."
        )
        lay_p.addWidget(self._radio_intermediaire)

        grp_dates = QGroupBox("Dates de la période")
        lay_dates = QHBoxLayout(grp_dates)

        lbl_debut = QLabel("Du :")
        self._date_debut = QDateEdit()
        self._date_debut.setDisplayFormat("dd/MM/yyyy")
        self._date_debut.setCalendarPopup(True)
        self._date_debut.setDate(QDate(date.today().year, 1, 1))
        configurer_label_champ(lbl_debut, self._date_debut, "Date de début du rapport")
        lay_dates.addWidget(lbl_debut)
        lay_dates.addWidget(self._date_debut)

        lbl_fin = QLabel("Au :")
        self._date_fin = QDateEdit()
        self._date_fin.setDisplayFormat("dd/MM/yyyy")
        self._date_fin.setCalendarPopup(True)
        self._date_fin.setDate(QDate(date.today().year, 6, 30))
        configurer_label_champ(lbl_fin, self._date_fin, "Date de fin du rapport")
        lay_dates.addWidget(lbl_fin)
        lay_dates.addWidget(self._date_fin)
        lay_dates.addStretch()

        grp_dates.setEnabled(False)
        lay_p.addWidget(grp_dates)

        # Activation/désactivation des dates selon le type de rapport
        self._radio_intermediaire.toggled.connect(grp_dates.setEnabled)

        layout.addWidget(grp_periode)

        # ── Aperçu synthétique ────────────────────────────────────────────────
        grp_apercu = QGroupBox("Aperçu du résultat")
        lay_apercu = QVBoxLayout(grp_apercu)

        self._btn_apercu = QPushButton("🔄 &Calculer l'aperçu")
        configurer_bouton(self._btn_apercu, "Calculer l'aperçu du compte de résultat")
        self._btn_apercu.clicked.connect(self._calculer_apercu)
        lay_apercu.addWidget(self._btn_apercu, alignment=Qt.AlignLeft)

        self._lbl_apercu = QTextEdit()
        self._lbl_apercu.setReadOnly(True)
        self._lbl_apercu.setMaximumHeight(200)
        self._lbl_apercu.setAccessibleName("Aperçu du compte de résultat")
        self._lbl_apercu.setAccessibleDescription(
            "Affiche le résumé des recettes, dépenses et résultat net pour la période sélectionnée."
        )
        lay_apercu.addWidget(self._lbl_apercu)

        layout.addWidget(grp_apercu)

        # ── Options de génération ─────────────────────────────────────────────
        grp_options = QGroupBox("Options d'export")
        lay_opt = QVBoxLayout(grp_options)

        self._chk_pdf = QCheckBox("&Convertir automatiquement en PDF après génération")
        self._chk_pdf.setChecked(True)
        self._chk_pdf.setAccessibleDescription(
            "Nécessite que Microsoft Word ou LibreOffice soit installé."
        )
        lay_opt.addWidget(self._chk_pdf)

        layout.addWidget(grp_options)

        # ── Bouton Générer ────────────────────────────────────────────────────
        self._btn_generer = QPushButton("📄 &Générer le rapport")
        self._btn_generer.setMinimumHeight(44)
        self._btn_generer.setStyleSheet(
            "QPushButton { background: #1a3a5c; color: white; font-size: 14px; "
            "border-radius: 6px; padding: 8px 24px; }"
            "QPushButton:hover { background: #2a5a8c; }"
            "QPushButton:disabled { background: #aaa; }"
        )
        configurer_bouton(
            self._btn_generer,
            "Générer le rapport Word",
            "Lance la génération du fichier Word avec graphiques et tableaux.",
        )
        self._btn_generer.clicked.connect(self._generer_rapport)
        layout.addWidget(self._btn_generer, alignment=Qt.AlignLeft)

        self._barre_prog = QProgressBar()
        self._barre_prog.setVisible(False)
        self._barre_prog.setRange(0, 0)  # Mode indéterminé
        layout.addWidget(self._barre_prog)

        self._lbl_status = QLabel("")
        layout.addWidget(self._lbl_status)

        layout.addStretch()

    def set_exercice(self, exercice: Exercice) -> None:
        """Charge un exercice."""
        self._exercice = exercice
        annee = exercice.annee
        self._date_debut.setDate(QDate(annee, 1, 1))
        self._date_fin.setDate(QDate(annee, 12, 31))

    def set_config(self, config: dict) -> None:
        """Met à jour la configuration de l'association."""
        self._config = config

    def _get_periode(self) -> tuple[date, date]:
        """Retourne la période sélectionnée."""
        if self._radio_annuel.isChecked() and self._exercice:
            return self._exercice.date_debut, self._exercice.date_fin
        else:
            d = self._date_debut.date()
            f = self._date_fin.date()
            return date(d.year(), d.month(), d.day()), date(f.year(), f.month(), f.day())

    def _calculer_apercu(self) -> None:
        """Calcule et affiche l'aperçu du compte de résultat."""
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
            lignes.append(f"  {l.label:<40} {l.montant:>10,.2f} €  ({l.pourcentage:.1f}%)")
        lignes.append(f"  {'TOTAL RECETTES':<40} {cr.total_recettes:>10,.2f} €")
        lignes.append("")
        lignes.append("DÉPENSES :")
        for l in cr.lignes_depenses:
            lignes.append(f"  {l.label:<40} {l.montant:>10,.2f} €  ({l.pourcentage:.1f}%)")
        lignes.append(f"  {'TOTAL DÉPENSES':<40} {cr.total_depenses:>10,.2f} €")
        lignes.append("")
        signe = "+" if cr.est_excedentaire else ""
        lignes.append(f"  {'RÉSULTAT NET':<40} {signe}{cr.resultat_net:>10,.2f} €")

        self._lbl_apercu.setPlainText("\n".join(lignes))

    def _generer_rapport(self) -> None:
        """Lance la génération du rapport Word en arrière-plan."""
        if not self._exercice:
            QMessageBox.warning(self, "Aucun exercice", "Importez d'abord un exercice (Alt+1).")
            return

        debut, fin = self._get_periode()

        # Choisir le fichier de sortie
        nom_defaut = (
            f"Rapport_{self._exercice.annee}.docx"
            if self._radio_annuel.isChecked()
            else f"Rapport_{debut.strftime('%Y%m%d')}_{fin.strftime('%Y%m%d')}.docx"
        )

        chemin, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le rapport",
            str(Path.home() / nom_defaut),
            "Documents Word (*.docx)",
        )
        if not chemin:
            return

        cr = self._exercice.calculer_compte_resultat(self._moteur, debut, fin)

        reporter = DocxReporter(self._config, self._moteur)
        convertir_pdf = self._chk_pdf.isChecked()

        self._btn_generer.setEnabled(False)
        self._barre_prog.setVisible(True)
        self._lbl_status.setText("Génération en cours…")

        self._thread = QThread()
        self._worker = WorkerRapport(
            reporter, cr, chemin, convertir_pdf, self._analytique, self._exercice
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progression.connect(self._lbl_status.setText)
        self._worker.termine.connect(self._on_rapport_termine)
        self._worker.erreur.connect(self._on_rapport_erreur)
        self._worker.termine.connect(self._thread.quit)
        self._worker.erreur.connect(self._thread.quit)

        self._thread.start()

    def _on_rapport_termine(self, chemin: str) -> None:
        self._btn_generer.setEnabled(True)
        self._barre_prog.setVisible(False)
        self._lbl_status.setText(f"Rapport généré : {chemin}")
        self.message_status.emit(f"Rapport généré avec succès : {Path(chemin).name}")
        QMessageBox.information(
            self,
            "Rapport généré",
            f"Le rapport a été généré avec succès :\n\n{chemin}\n\n"
            "Voulez-vous l'ouvrir maintenant ?",
        )
        import subprocess
        import sys
        if sys.platform == "win32":
            import os
            os.startfile(chemin)

    def _on_rapport_erreur(self, erreur: str) -> None:
        self._btn_generer.setEnabled(True)
        self._barre_prog.setVisible(False)
        self._lbl_status.setText(f"Erreur : {erreur}")
        QMessageBox.critical(self, "Erreur de génération", f"Erreur lors de la génération :\n\n{erreur}")
