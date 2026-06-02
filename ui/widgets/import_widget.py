"""
Widget d'importation des relevés bancaires PDF.

Mise en page responsive :
  - Les zones de formulaire sont fixes en hauteur (leur contenu est connu).
  - Le journal d'import (TextEdit) prend tout l'espace vertical restant grâce
    à une SizePolicy Expanding. Il grandit/rétrécit avec la fenêtre.
  - La barre de progression s'étire horizontalement sur toute la largeur.
  - Aucune taille fixe en pixels dans les layouts (seulement des Pt/Cm pour
    les marges et des stretch factors pour la répartition).
"""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QSpinBox, QLineEdit, QPushButton, QProgressBar, QTextEdit,
    QFileDialog, QDoubleSpinBox, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QThread, QObject

from core.parser import LaPosteParser, ParseError
from core.accounting import Exercice
from core.categorizer import MoteurCategorisation
from ui.accessibility import (
    configurer_label_champ, configurer_bouton,
    configurer_barre_progression, definir_ordre_tabulation,
)

logger = logging.getLogger(__name__)


class WorkerImport(QObject):
    """Thread d'import — ne bloque pas l'UI."""
    progression = Signal(int, str)
    termine = Signal(object, dict)
    erreur = Signal(str)

    def __init__(self, dossier, annee, solde_initial, config_asso):
        super().__init__()
        self.dossier = dossier
        self.annee = annee
        self.solde_initial = solde_initial
        self.config_asso = config_asso

    def run(self):
        try:
            from decimal import Decimal
            parser = LaPosteParser(self.config_asso)
            exercice = Exercice(self.annee, "data")
            exercice.solde_initial = Decimal(str(self.solde_initial))
            pdfs = sorted(Path(self.dossier).glob("*.pdf"))
            if not pdfs:
                self.erreur.emit(f"Aucun PDF trouvé dans : {self.dossier}")
                return
            stats = {"importes": 0, "ignores": 0, "erreurs": 0, "total_tx": 0}
            for i, pdf in enumerate(pdfs):
                self.progression.emit(int((i+1)/len(pdfs)*100), f"Analyse : {pdf.name}")
                try:
                    releve = parser.parser_fichier(str(pdf))
                    if not releve.valide:
                        stats["ignores"] += 1
                        continue
                    nb = exercice.importer_releve(releve)
                    stats["importes"] += 1
                    stats["total_tx"] += nb
                except Exception as e:
                    logger.error(f"{pdf.name}: {e}")
                    stats["erreurs"] += 1
            exercice.sauvegarder()
            self.termine.emit(exercice, stats)
        except Exception as e:
            self.erreur.emit(str(e))


class ImportWidget(QWidget):
    exercice_importe = Signal(object)
    message_status = Signal(str)

    def __init__(self, config_asso: dict, moteur: MoteurCategorisation):
        super().__init__()
        self._config_asso = config_asso
        self._moteur = moteur
        self._thread = None
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        # Layout principal vertical — utilise tout l'espace disponible
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # ── Titre ─────────────────────────────────────────────────────────
        titre = QLabel("Import des relevés bancaires")
        titre.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a3a5c;")
        titre.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        titre.setAccessibleName("Titre : Import des relevés bancaires")
        layout.addWidget(titre)

        # ── Groupe exercice ────────────────────────────────────────────────
        grp_ex = QGroupBox("Exercice comptable")
        grp_ex.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grp_ex.setAccessibleDescription(
            "Sélectionnez l'année et le solde bancaire au 1er janvier."
        )
        lay_ex = QHBoxLayout(grp_ex)
        lay_ex.setContentsMargins(10, 8, 10, 8)
        lay_ex.setSpacing(12)

        lbl_annee = QLabel("Année :")
        self._spin_annee = QSpinBox()
        self._spin_annee.setRange(2010, 2099)
        from datetime import date
        self._spin_annee.setValue(date.today().year)
        self._spin_annee.setFixedWidth(90)
        configurer_label_champ(lbl_annee, self._spin_annee,
                               "Année de l'exercice",
                               "Sélectionnez l'année fiscale, par exemple 2024.")
        lay_ex.addWidget(lbl_annee)
        lay_ex.addWidget(self._spin_annee)
        lay_ex.addSpacing(20)

        lbl_solde = QLabel("Solde initial au 1er janvier :")
        self._spin_solde = QDoubleSpinBox()
        self._spin_solde.setRange(-999999.99, 999999.99)
        self._spin_solde.setDecimals(2)
        self._spin_solde.setSuffix(" €")
        self._spin_solde.setMinimumWidth(140)
        self._spin_solde.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        configurer_label_champ(lbl_solde, self._spin_solde,
                               "Solde bancaire initial",
                               "Solde du compte au 1er janvier de l'exercice.")
        lay_ex.addWidget(lbl_solde)
        lay_ex.addWidget(self._spin_solde)
        lay_ex.addStretch(1)

        layout.addWidget(grp_ex)

        # ── Groupe dossier ─────────────────────────────────────────────────
        grp_dos = QGroupBox("Dossier des relevés PDF")
        grp_dos.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay_dos = QHBoxLayout(grp_dos)
        lay_dos.setContentsMargins(10, 8, 10, 8)
        lay_dos.setSpacing(8)

        self._edit_dossier = QLineEdit()
        self._edit_dossier.setPlaceholderText(
            "Ex : E:\\Culture musique\\Documents\\Compte bancaire\\Releves\\2024"
        )
        self._edit_dossier.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        configurer_label_champ(QLabel("Dossier"), self._edit_dossier,
                               "Chemin du dossier des relevés PDF",
                               "Entrez le chemin ou utilisez le bouton Parcourir.")
        lay_dos.addWidget(self._edit_dossier, stretch=1)

        self._btn_parcourir = QPushButton("&Parcourir…")
        self._btn_parcourir.setFixedWidth(110)
        configurer_bouton(self._btn_parcourir, "Parcourir les dossiers",
                          "Ouvre un sélecteur de dossier système.")
        self._btn_parcourir.clicked.connect(self._choisir_dossier)
        lay_dos.addWidget(self._btn_parcourir)

        layout.addWidget(grp_dos)

        # ── Bouton import ──────────────────────────────────────────────────
        self._btn_importer = QPushButton("&Importer les relevés")
        self._btn_importer.setMinimumHeight(44)
        self._btn_importer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn_importer.setStyleSheet(
            "QPushButton{background:#1a3a5c;color:white;font-size:14px;"
            "border-radius:6px;padding:8px 24px;}"
            "QPushButton:hover{background:#2a5a8c;}"
            "QPushButton:disabled{background:#aaa;}"
        )
        configurer_bouton(self._btn_importer, "Importer les relevés",
                          "Lance l'extraction depuis tous les PDFs du dossier sélectionné.")
        self._btn_importer.clicked.connect(self._lancer_import)
        layout.addWidget(self._btn_importer)

        # ── Progression ────────────────────────────────────────────────────
        self._barre_prog = QProgressBar()
        self._barre_prog.setVisible(False)
        self._barre_prog.setMinimumHeight(22)
        self._barre_prog.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        configurer_barre_progression(self._barre_prog, "Importation des relevés PDF")
        layout.addWidget(self._barre_prog)

        self._lbl_prog = QLabel("")
        self._lbl_prog.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._lbl_prog.setAccessibleName("État de l'importation")
        layout.addWidget(self._lbl_prog)

        # ── Journal — s'étire pour remplir l'espace restant ───────────────
        grp_journal = QGroupBox("Journal d'import")
        grp_journal.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay_j = QVBoxLayout(grp_journal)
        lay_j.setContentsMargins(8, 6, 8, 6)

        self._journal = QTextEdit()
        self._journal.setReadOnly(True)
        self._journal.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._journal.setAccessibleName("Journal d'importation")
        self._journal.setAccessibleDescription(
            "Affiche le détail des opérations : fichiers traités, erreurs, statistiques."
        )
        lay_j.addWidget(self._journal)

        # Le groupe journal prend tout l'espace vertical restant (stretch=1)
        layout.addWidget(grp_journal, stretch=1)

        # Ordre de tabulation
        definir_ordre_tabulation([
            self._spin_annee, self._spin_solde,
            self._edit_dossier, self._btn_parcourir, self._btn_importer,
        ])

    def demander_annee(self):
        self._spin_annee.setFocus()

    def _choisir_dossier(self):
        d = QFileDialog.getExistingDirectory(
            self, "Sélectionner le dossier des relevés PDF",
            self._edit_dossier.text() or str(Path.home()),
        )
        if d:
            self._edit_dossier.setText(d)

    def _lancer_import(self):
        dossier = self._edit_dossier.text().strip()
        if not dossier or not Path(dossier).is_dir():
            self._journal.append("❌ Dossier invalide ou introuvable.")
            return
        annee = self._spin_annee.value()
        solde = self._spin_solde.value()
        self._btn_importer.setEnabled(False)
        self._barre_prog.setVisible(True)
        self._barre_prog.setValue(0)
        self._journal.clear()
        self._journal.append(f"▶ Import exercice {annee}  —  solde initial : {solde:,.2f} €")
        self._journal.append(f"  Dossier : {dossier}\n")

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

    def _on_progression(self, pct, message):
        self._barre_prog.setValue(pct)
        self._lbl_prog.setText(message)

    def _on_termine(self, exercice, stats):
        self._btn_importer.setEnabled(True)
        self._barre_prog.setValue(100)
        msg = (
            f"✅ Import terminé !\n"
            f"  Relevés traités  : {stats['importes']}\n"
            f"  Relevés ignorés  : {stats['ignores']}\n"
            f"  Erreurs          : {stats['erreurs']}\n"
            f"  Nouvelles tx     : {stats['total_tx']}\n"
            f"  Total tx         : {len(exercice.transactions)}"
        )
        nc = len(exercice.transactions_non_categorisees())
        if nc:
            msg += f"\n  ⚠ {nc} transaction(s) à catégoriser manuellement."
        self._journal.append(msg)
        self._lbl_prog.setText(f"Import terminé — {stats['total_tx']} nouvelles transactions.")
        stats_cat = self._moteur.categoriser_lot(exercice.transactions)
        self._journal.append(
            f"  Catégorisation auto : {stats_cat['auto']} ✅  |  "
            f"{stats_cat['a_traiter']} à traiter ⚠"
        )
        exercice.sauvegarder()
        self.message_status.emit(
            f"Exercice {exercice.annee} importé. Passez à la catégorisation (Alt+2)."
        )
        self.exercice_importe.emit(exercice)

    def _on_erreur(self, message):
        self._btn_importer.setEnabled(True)
        self._barre_prog.setVisible(False)
        self._journal.append(f"❌ Erreur : {message}")
        self._lbl_prog.setText(f"Erreur : {message}")
        self.message_status.emit(f"Erreur d'import : {message}")
