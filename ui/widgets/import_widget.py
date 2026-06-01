"""
Widget d'importation des relevés bancaires PDF.

Ce widget permet à l'utilisateur de :
1. Choisir l'année de l'exercice
2. Sélectionner un dossier contenant les PDFs La Poste
3. Suivre la progression de l'import
4. Définir le solde initial du compte

Accessibilité NVDA :
    - Barre de progression annoncée dynamiquement
    - Messages d'état lus à chaque étape
    - Focus automatique sur le premier champ à l'ouverture
    - Résultat de l'import annoncé vocalement
"""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QSpinBox, QLineEdit, QPushButton, QProgressBar, QTextEdit,
    QFileDialog, QDoubleSpinBox, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QThread, QObject

from ...core.parser import LaPosteParser, ParseError
from ...core.accounting import Exercice
from ...core.categorizer import MoteurCategorisation
from ..accessibility import (
    configurer_label_champ, configurer_bouton,
    configurer_barre_progression, definir_ordre_tabulation,
)

logger = logging.getLogger(__name__)


class WorkerImport(QObject):
    """Thread de travail pour l'import des PDFs (ne bloque pas l'UI)."""
    progression = Signal(int, str)
    termine = Signal(object, dict)  # (exercice, stats)
    erreur = Signal(str)

    def __init__(self, dossier: str, annee: int, solde_initial: float, config_asso: dict):
        super().__init__()
        self.dossier = dossier
        self.annee = annee
        self.solde_initial = solde_initial
        self.config_asso = config_asso

    def run(self) -> None:
        try:
            from decimal import Decimal
            parser = LaPosteParser(self.config_asso)
            exercice = Exercice(self.annee, "data")
            exercice.solde_initial = Decimal(str(self.solde_initial))

            pdfs = sorted(Path(self.dossier).glob("*.pdf"))
            if not pdfs:
                self.erreur.emit(f"Aucun fichier PDF trouvé dans : {self.dossier}")
                return

            stats = {"importes": 0, "ignores": 0, "erreurs": 0, "total_tx": 0}

            for i, pdf in enumerate(pdfs):
                pct = int((i + 1) / len(pdfs) * 100)
                self.progression.emit(pct, f"Analyse de {pdf.name}…")

                try:
                    releve = parser.parser_fichier(str(pdf))
                    if not releve.valide:
                        stats["ignores"] += 1
                        continue
                    nb = exercice.importer_releve(releve)
                    stats["importes"] += 1
                    stats["total_tx"] += nb
                except (ParseError, Exception) as e:
                    logger.error(f"Erreur parsing {pdf.name}: {e}")
                    stats["erreurs"] += 1

            exercice.sauvegarder()
            self.termine.emit(exercice, stats)

        except Exception as e:
            self.erreur.emit(str(e))


class ImportWidget(QWidget):
    """
    Widget d'import des relevés bancaires.

    Signals:
        exercice_importe (Exercice): Émis quand l'import est terminé avec succès.
        message_status (str):        Émis pour mettre à jour la barre de statut.
    """
    exercice_importe = Signal(object)
    message_status = Signal(str)

    def __init__(self, config_asso: dict, moteur: MoteurCategorisation):
        super().__init__()
        self._config_asso = config_asso
        self._moteur = moteur
        self._thread: QThread | None = None
        self._worker: WorkerImport | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Titre ─────────────────────────────────────────────────────────────
        titre = QLabel("Import des relevés bancaires")
        titre.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a3a5c;")
        titre.setAccessibleName("Titre de section : Import des relevés bancaires")
        layout.addWidget(titre)

        # ── Groupe : Exercice ─────────────────────────────────────────────────
        grp_exercice = QGroupBox("Exercice comptable")
        grp_exercice.setAccessibleDescription(
            "Sélectionnez l'année de l'exercice et le solde bancaire au 1er janvier."
        )
        lay_ex = QHBoxLayout(grp_exercice)

        lbl_annee = QLabel("Année de l'exercice :")
        self._spin_annee = QSpinBox()
        self._spin_annee.setRange(2010, 2099)
        from datetime import date
        self._spin_annee.setValue(date.today().year)
        self._spin_annee.setSuffix("  ")
        configurer_label_champ(
            lbl_annee, self._spin_annee,
            "Année de l'exercice",
            "Sélectionnez l'année fiscale à importer (ex : 2024).",
        )
        lay_ex.addWidget(lbl_annee)
        lay_ex.addWidget(self._spin_annee)

        lay_ex.addSpacing(20)

        lbl_solde = QLabel("Solde initial au 1er janvier (€) :")
        self._spin_solde = QDoubleSpinBox()
        self._spin_solde.setRange(-999999.99, 999999.99)
        self._spin_solde.setDecimals(2)
        self._spin_solde.setSuffix(" €")
        self._spin_solde.setMinimumWidth(140)
        configurer_label_champ(
            lbl_solde, self._spin_solde,
            "Solde bancaire initial",
            "Solde du compte bancaire au 1er janvier de l'exercice.",
        )
        lay_ex.addWidget(lbl_solde)
        lay_ex.addWidget(self._spin_solde)
        lay_ex.addStretch()

        layout.addWidget(grp_exercice)

        # ── Groupe : Dossier des relevés ───────────────────────────────────────
        grp_dossier = QGroupBox("Dossier contenant les relevés PDF")
        grp_dossier.setAccessibleDescription(
            "Choisissez le dossier contenant les fichiers PDF des relevés La Poste."
        )
        lay_dos = QHBoxLayout(grp_dossier)

        self._edit_dossier = QLineEdit()
        self._edit_dossier.setPlaceholderText(
            "Ex : E:\\Culture musique\\Documents\\Compte bancaire\\Releves\\2024"
        )
        configurer_label_champ(
            QLabel("Dossier"), self._edit_dossier,
            "Chemin du dossier des relevés PDF",
            "Entrez ou collez le chemin du dossier, ou cliquez sur Parcourir.",
        )
        lay_dos.addWidget(self._edit_dossier)

        self._btn_parcourir = QPushButton("&Parcourir…")
        configurer_bouton(
            self._btn_parcourir,
            "Parcourir les dossiers",
            "Ouvre un sélecteur de dossier pour choisir l'emplacement des relevés PDF.",
        )
        self._btn_parcourir.clicked.connect(self._choisir_dossier)
        lay_dos.addWidget(self._btn_parcourir)

        layout.addWidget(grp_dossier)

        # ── Bouton Import ─────────────────────────────────────────────────────
        self._btn_importer = QPushButton("&Importer les relevés")
        self._btn_importer.setMinimumHeight(44)
        self._btn_importer.setStyleSheet(
            "QPushButton { background: #1a3a5c; color: white; font-size: 14px; "
            "border-radius: 6px; padding: 8px 24px; }"
            "QPushButton:hover { background: #2a5a8c; }"
            "QPushButton:disabled { background: #aaa; }"
        )
        configurer_bouton(
            self._btn_importer,
            "Importer les relevés",
            "Lance l'extraction des transactions depuis tous les PDFs du dossier sélectionné.",
        )
        self._btn_importer.clicked.connect(self._lancer_import)
        layout.addWidget(self._btn_importer, alignment=Qt.AlignLeft)

        # ── Progression ───────────────────────────────────────────────────────
        self._barre_prog = QProgressBar()
        self._barre_prog.setVisible(False)
        self._barre_prog.setMinimumHeight(24)
        configurer_barre_progression(self._barre_prog, "Importation des relevés PDF")
        layout.addWidget(self._barre_prog)

        self._lbl_prog = QLabel("")
        self._lbl_prog.setAccessibleName("État de l'importation")
        layout.addWidget(self._lbl_prog)

        # ── Journal ───────────────────────────────────────────────────────────
        grp_journal = QGroupBox("Journal d'import")
        lay_j = QVBoxLayout(grp_journal)
        self._journal = QTextEdit()
        self._journal.setReadOnly(True)
        self._journal.setAccessibleName("Journal d'importation")
        self._journal.setAccessibleDescription(
            "Affiche le détail des opérations d'import : fichiers traités, erreurs, statistiques."
        )
        self._journal.setMaximumHeight(200)
        lay_j.addWidget(self._journal)
        layout.addWidget(grp_journal)

        layout.addStretch()

        # Ordre de tabulation
        definir_ordre_tabulation([
            self._spin_annee, self._spin_solde,
            self._edit_dossier, self._btn_parcourir, self._btn_importer,
        ])

    def demander_annee(self) -> None:
        """Met le focus sur le champ Année (appelé depuis MainWindow)."""
        self._spin_annee.setFocus()

    def _choisir_dossier(self) -> None:
        """Ouvre la boîte de dialogue de sélection de dossier."""
        dossier = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner le dossier des relevés PDF",
            self._edit_dossier.text() or str(Path.home()),
        )
        if dossier:
            self._edit_dossier.setText(dossier)

    def _lancer_import(self) -> None:
        """Valide les paramètres et lance l'import en arrière-plan."""
        dossier = self._edit_dossier.text().strip()
        if not dossier or not Path(dossier).is_dir():
            self._journal.append("❌ Dossier invalide ou introuvable.")
            self._lbl_prog.setText("Erreur : dossier invalide.")
            return

        annee = self._spin_annee.value()
        solde = self._spin_solde.value()

        self._btn_importer.setEnabled(False)
        self._barre_prog.setVisible(True)
        self._barre_prog.setValue(0)
        self._journal.clear()
        self._journal.append(f"▶ Démarrage de l'import pour l'exercice {annee}…")
        self._journal.append(f"  Dossier : {dossier}")
        self._journal.append(f"  Solde initial : {solde:,.2f} €\n")

        # Créer le thread d'import
        self._thread = QThread()
        self._worker = WorkerImport(dossier, annee, solde, self._config_asso)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progression.connect(self._on_progression)
        self._worker.termine.connect(self._on_termine)
        self._worker.erreur.connect(self._on_erreur)
        self._worker.termine.connect(self._thread.quit)
        self._worker.erreur.connect(self._thread.quit)

        self._thread.start()

    def _on_progression(self, pct: int, message: str) -> None:
        self._barre_prog.setValue(pct)
        self._lbl_prog.setText(message)

    def _on_termine(self, exercice: Exercice, stats: dict) -> None:
        self._btn_importer.setEnabled(True)
        self._barre_prog.setValue(100)

        msg = (
            f"✅ Import terminé !\n"
            f"  Relevés traités  : {stats['importes']}\n"
            f"  Relevés ignorés  : {stats['ignores']} (non reconnus)\n"
            f"  Erreurs          : {stats['erreurs']}\n"
            f"  Transactions nouvelles : {stats['total_tx']}\n"
            f"  Total transactions : {len(exercice.transactions)}\n"
        )

        non_cat = len(exercice.transactions_non_categorisees())
        if non_cat:
            msg += f"\n  ⚠ {non_cat} transaction(s) à catégoriser manuellement."

        self._journal.append(msg)
        self._lbl_prog.setText(f"Import terminé — {stats['total_tx']} nouvelles transactions.")
        self.message_status.emit(f"Exercice {exercice.annee} importé. Passez à la catégorisation (Alt+2).")

        # Lancer la catégorisation automatique
        stats_cat = self._moteur.categoriser_lot(exercice.transactions)
        self._journal.append(
            f"  Catégorisation auto : {stats_cat['auto']} transaction(s) catégorisée(s), "
            f"{stats_cat['a_traiter']} à traiter."
        )
        exercice.sauvegarder()

        self.exercice_importe.emit(exercice)

    def _on_erreur(self, message: str) -> None:
        self._btn_importer.setEnabled(True)
        self._barre_prog.setVisible(False)
        self._journal.append(f"❌ Erreur : {message}")
        self._lbl_prog.setText(f"Erreur : {message}")
        self.message_status.emit(f"Erreur d'import : {message}")
