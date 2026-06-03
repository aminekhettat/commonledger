"""
Widget de génération des rapports avec panel graphique interactif.

Disposition (QSplitter horizontal) :
  ┌─────────────────────────┬─────────────────────────────────────┐
  │  PANNEAU GAUCHE         │  PANNEAU DROIT                      │
  │  Contrôles graphique    │  Aperçu textuel du compte de résult.│
  │  + Canvas matplotlib    │  + Options export + Bouton générer  │
  └─────────────────────────┴─────────────────────────────────────┘

Le graphique se met à jour en temps réel quand l'utilisateur change :
  - Le type de graphique (camembert recettes, dépenses, histogramme, courbe)
  - La période (annuelle ou personnalisée)
  - Le projet (tous ou un projet spécifique)
"""

import logging
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import matplotlib
matplotlib.use("QtAgg")   # Backend Qt — intégration native PySide6
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as mpatches
import matplotlib.lines

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QDateEdit, QPushButton, QFileDialog, QProgressBar,
    QTextEdit, QRadioButton, QCheckBox, QMessageBox,
    QSizePolicy, QSplitter, QComboBox, QScrollArea, QLineEdit,
)
from PySide6.QtCore import Qt, Signal, QDate, QThread, QObject

from core.accounting import Exercice, ComptaAnalytique
from core.accounting.compte_resultat import CompteResultat
from core.categorizer import MoteurCategorisation
from core.reporter import DocxReporter, CsvReporter
from ui.accessibility import configurer_bouton, configurer_label_champ

logger = logging.getLogger(__name__)

MOIS_COURTS = ["", "Jan.", "Fév.", "Mar.", "Avr.", "Mai", "Jun.",
               "Jul.", "Aoû.", "Sep.", "Oct.", "Nov.", "Déc."]

TYPES_GRAPHIQUE = [
    ("camembert_recettes",  "Camembert — Recettes"),
    ("camembert_depenses",  "Camembert — Dépenses"),
    ("histogramme",         "Histogramme mensuel"),
    ("courbe_tresorerie",   "Courbe de trésorerie"),
]


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


class GraphiqueCanvas(FigureCanvas):
    """Canvas matplotlib intégré dans Qt — se redimensionne avec le widget."""

    def __init__(self, parent=None):
        self._fig = Figure(facecolor="white", tight_layout=True)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()
        self._ax = None
        self._vide = True   # True tant qu'aucun graphe n'a été tracé
        self._afficher_vide()

    @property
    def est_vide(self) -> bool:
        """True si aucun graphique n'a encore été tracé."""
        return self._vide

    def _afficher_vide(self):
        self._fig.clear()
        self._vide = True
        ax = self._fig.add_subplot(111)
        ax.set_axis_off()
        ax.text(0.5, 0.5, "Cliquez sur\n« Calculer l'aperçu »\npour afficher le graphique",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=11, color="#888888",
                bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", alpha=0.8))
        self.draw()

    def _marquer_non_vide(self):
        self._vide = False

    def tracer_camembert(self, lignes: list, titre: str, couleur_titre: str = "#1a3a5c"):
        """Trace un camembert donut avec légende détaillée."""
        self._fig.clear()

        lignes_nz = [l for l in lignes if l.montant > 0]
        if not lignes_nz:
            self._afficher_vide()
            return

        montants = [float(l.montant) for l in lignes_nz]
        couleurs  = [l.couleur for l in lignes_nz]
        total     = sum(montants)

        ax = self._fig.add_subplot(111)

        wedges, _, autotexts = ax.pie(
            montants, colors=couleurs,
            autopct=lambda p: f"{p:.1f}%" if p > 4 else "",
            startangle=90, pctdistance=0.75,
            wedgeprops={"edgecolor": "white", "linewidth": 2, "antialiased": True},
        )
        for at in autotexts:
            at.set_fontsize(8)
            at.set_fontweight("bold")
            at.set_color("white")

        # Cercle central (effet donut)
        centre = matplotlib.patches.Circle((0, 0), 0.45, color="white")
        ax.add_patch(centre)
        ax.text(0, 0.05, f"{total:,.0f} €".replace(",", " "),
                ha="center", va="center", fontsize=9,
                fontweight="bold", color=couleur_titre)
        ax.text(0, -0.15, "TOTAL", ha="center", va="center",
                fontsize=7, color="#888888")

        ax.set_title(titre, fontsize=11, fontweight="bold",
                     color=couleur_titre, pad=8)

        # Légende en bas
        patches = [mpatches.Patch(color=c, label=(
            f"{l.label[:22]}\n{float(l.montant):,.0f} € ({float(l.montant)/total*100:.1f}%)"
            .replace(",", " ")
        )) for c, l in zip(couleurs, lignes_nz)]
        ax.legend(handles=patches, loc="lower center",
                  bbox_to_anchor=(0.5, -0.35),
                  ncol=max(1, len(patches)//3),
                  fontsize=7.5, frameon=False,
                  labelspacing=0.4)

        self._fig.tight_layout()
        self._marquer_non_vide()
        self.draw()

    def tracer_histogramme(self, evolution: list, couleur: str = "#1a3a5c",
                           couleur_fond: str = "#e8f0f7"):
        """Trace l'histogramme mensuel recettes vs dépenses."""
        self._fig.clear()
        if not evolution:
            self._afficher_vide()
            return

        ax = self._fig.add_subplot(111)
        labels  = [MOIS_COURTS[e["mois"]] for e in evolution]
        rects   = [float(e["recettes"])  for e in evolution]
        depens  = [float(e["depenses"])  for e in evolution]
        x = range(len(evolution))
        w = 0.38

        bars_r = ax.bar([i - w/2 for i in x], rects,  w, label="Recettes",
                        color="#27AE60", alpha=0.85, zorder=3)
        bars_d = ax.bar([i + w/2 for i in x], depens, w, label="Dépenses",
                        color="#E74C3C", alpha=0.85, zorder=3)

        for b in list(bars_r) + list(bars_d):
            h = b.get_height()
            if h > 30:
                ax.text(b.get_x() + b.get_width()/2, h + 5,
                        f"{h:,.0f}".replace(",", " "),
                        ha="center", va="bottom", fontsize=6.5)

        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_title("Recettes et dépenses mensuelles", fontsize=10,
                     fontweight="bold", color=couleur)
        ax.legend(fontsize=9, loc="upper right")
        ax.set_facecolor(couleur_fond)
        ax.grid(axis="y", alpha=0.4, zorder=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

        self._fig.tight_layout()
        self._marquer_non_vide()
        self.draw()

    def tracer_courbe(self, evolution: list, solde_initial: Decimal,
                      couleur: str = "#1a3a5c", couleur_fond: str = "#e8f0f7"):
        """Trace la courbe d'évolution du solde."""
        self._fig.clear()
        if not evolution:
            self._afficher_vide()
            return

        ax = self._fig.add_subplot(111)
        soldes = []
        s = float(solde_initial)
        for e in evolution:
            s += float(e["recettes"]) - float(e["depenses"])
            soldes.append(s)

        labels = [MOIS_COURTS[e["mois"]] for e in evolution]
        ax.fill_between(range(len(soldes)), soldes, alpha=0.12, color=couleur)
        ax.plot(range(len(soldes)), soldes, color=couleur,
                linewidth=2, marker="o", markersize=5, label="Solde bancaire")
        ax.axhline(y=0, color="#E74C3C", linestyle="--", alpha=0.5, linewidth=1)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_title("Évolution de la trésorerie", fontsize=10,
                     fontweight="bold", color=couleur)
        ax.legend(fontsize=9)
        ax.set_facecolor(couleur_fond)
        ax.grid(alpha=0.3)
        for spine in ax.spines.values():
            spine.set_visible(False)

        self._fig.tight_layout()
        self._marquer_non_vide()
        self.draw()

    def sauvegarder_vers(
        self,
        chemin: str,
        nom_asso: str,
        libelle_exercice: str,
        periode: str,
        titre_graph: str,
        version_app: str = "",
        dpi: int = 300,
    ) -> None:
        """
        Sauvegarde le graphique courant en PNG avec en-tête et pied de page.

        L'opération est non-destructive : les textes ajoutés pour la sauvegarde
        sont supprimés et la figure restaurée à son état d'affichage d'origine.

        Args:
            chemin:           Chemin complet du fichier PNG de sortie.
            nom_asso:         Nom de l'association (en-tête).
            libelle_exercice: Ex : "2025" ou "2025-2026".
            periode:          Ex : "01/01/2025 → 31/12/2025".
            titre_graph:      Type de graphique (ex : "Camembert — Recettes").
            version_app:      Version de l'application (pied de page).
            dpi:              Résolution PNG (défaut 300 dpi — qualité impression).
        """
        from datetime import date as dt_date

        today = dt_date.today().strftime("%d/%m/%Y")
        couleur_primaire = "#1a3a5c"
        couleur_secondaire = "#888888"

        # ── Ajuster les marges pour l'en-tête et le pied ─────────────────
        self._fig.subplots_adjust(top=0.84, bottom=0.12)

        # ── En-tête : ligne 1 — nom + exercice ───────────────────────────
        t_nom = self._fig.text(
            0.5, 0.96,
            nom_asso,
            ha="center", va="top",
            fontsize=10, fontweight="bold", color=couleur_primaire,
        )
        t_ex = self._fig.text(
            0.5, 0.92,
            f"Exercice {libelle_exercice}   •   {periode}",
            ha="center", va="top",
            fontsize=8.5, color=couleur_primaire,
        )
        t_type = self._fig.text(
            0.5, 0.88,
            titre_graph,
            ha="center", va="top",
            fontsize=8, color=couleur_secondaire, style="italic",
        )
        # Ligne de séparation en-tête / graphe
        ligne_haut = self._fig.add_artist(
            matplotlib.lines.Line2D(
                [0.05, 0.95], [0.855, 0.855],
                transform=self._fig.transFigure,
                color="#cccccc", linewidth=0.8,
            )
        )
        # ── Pied de page ─────────────────────────────────────────────────
        pied_gauche = self._fig.text(
            0.05, 0.03,
            f"Généré le {today}",
            ha="left", va="bottom",
            fontsize=7, color=couleur_secondaire,
        )
        pied_droit = self._fig.text(
            0.95, 0.03,
            f"CommonLedger{(' ' + version_app) if version_app else ''}",
            ha="right", va="bottom",
            fontsize=7, color=couleur_secondaire,
        )
        ligne_bas = self._fig.add_artist(
            matplotlib.lines.Line2D(
                [0.05, 0.95], [0.07, 0.07],
                transform=self._fig.transFigure,
                color="#cccccc", linewidth=0.8,
            )
        )

        # ── Sauvegarder ──────────────────────────────────────────────────
        try:
            self._fig.savefig(chemin, dpi=dpi, bbox_inches="tight",
                              facecolor="white", edgecolor="none")
        finally:
            # ── Restaurer l'état d'origine ───────────────────────────────
            for artiste in [t_nom, t_ex, t_type, pied_gauche, pied_droit,
                            ligne_haut, ligne_bas]:
                try:
                    artiste.remove()
                except Exception:  # pragma: no cover
                    pass
            self._fig.tight_layout()
            self.draw()


class ReportWidget(QWidget):
    """Widget rapport avec graphique interactif et aperçu textuel."""

    message_status = Signal(str)

    #: Clé dans config/association.json pour le dossier de sortie des rapports
    _CLE_DOSSIER = "dossier_rapports"

    def __init__(self, config_asso: dict, moteur: MoteurCategorisation,
                 analytique: ComptaAnalytique):
        super().__init__()
        self._config = config_asso
        self._moteur = moteur
        self._analytique = analytique
        self._exercice = None
        self._cr_cache = None
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

        # ── Barre de contrôles (période + projet) ─────────────────────────
        grp_ctrl = QGroupBox("Filtres")
        grp_ctrl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay_ctrl = QHBoxLayout(grp_ctrl)
        lay_ctrl.setSpacing(12)

        self._radio_annuel = QRadioButton("&Annuel")
        self._radio_annuel.setChecked(True)
        lay_ctrl.addWidget(self._radio_annuel)

        self._radio_inter = QRadioButton("&Personnalisé")
        lay_ctrl.addWidget(self._radio_inter)

        lbl_d = QLabel("Du :")
        self._date_debut = QDateEdit()
        self._date_debut.setDisplayFormat("dd/MM/yyyy")
        self._date_debut.setCalendarPopup(True)
        self._date_debut.setDate(QDate(date.today().year, 1, 1))
        self._date_debut.setEnabled(False)
        lay_ctrl.addWidget(lbl_d)
        lay_ctrl.addWidget(self._date_debut)

        lbl_f = QLabel("Au :")
        self._date_fin = QDateEdit()
        self._date_fin.setDisplayFormat("dd/MM/yyyy")
        self._date_fin.setCalendarPopup(True)
        self._date_fin.setDate(QDate(date.today().year, 12, 31))
        self._date_fin.setEnabled(False)
        lay_ctrl.addWidget(lbl_f)
        lay_ctrl.addWidget(self._date_fin)

        self._radio_inter.toggled.connect(self._date_debut.setEnabled)
        self._radio_inter.toggled.connect(self._date_fin.setEnabled)

        lay_ctrl.addSpacing(20)

        lbl_proj = QLabel("Projet :")
        self._combo_projet = QComboBox()
        self._combo_projet.setMinimumWidth(150)
        self._combo_projet.addItem("Tous les projets", None)
        for projet in self._analytique.projets_actifs():
            self._combo_projet.addItem(projet.nom, projet.id)
        lay_ctrl.addWidget(lbl_proj)
        lay_ctrl.addWidget(self._combo_projet)

        self._btn_calculer = QPushButton("🔄 &Calculer")
        self._btn_calculer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        configurer_bouton(self._btn_calculer, "Calculer l'aperçu et le graphique")
        self._btn_calculer.clicked.connect(self._calculer)
        lay_ctrl.addWidget(self._btn_calculer)
        lay_ctrl.addStretch()
        layout.addWidget(grp_ctrl)

        # ── Splitter principal : gauche (graphique) | droite (texte+export) ─
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ── Panneau gauche : sélecteur graphique + canvas ──────────────────
        panneau_gauche = QWidget()
        lay_g = QVBoxLayout(panneau_gauche)
        lay_g.setContentsMargins(0, 0, 6, 0)
        lay_g.setSpacing(6)

        # Sélecteur type de graphique
        lbl_type = QLabel("Type de graphique :")
        lbl_type.setStyleSheet("font-weight:bold; color:#1a3a5c;")
        lay_g.addWidget(lbl_type)

        self._combo_type_graph = QComboBox()
        self._combo_type_graph.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for key, label in TYPES_GRAPHIQUE:
            self._combo_type_graph.addItem(label, key)
        self._combo_type_graph.currentIndexChanged.connect(self._mettre_a_jour_graphique)
        lay_g.addWidget(self._combo_type_graph)

        # Canvas matplotlib — occupe tout l'espace restant
        self._canvas = GraphiqueCanvas(panneau_gauche)
        self._canvas.setAccessibleName("Graphique du compte de résultat")
        self._canvas.setAccessibleDescription(
            "Graphique matplotlib interactif. Sélectionnez le type avec le combo ci-dessus."
        )
        lay_g.addWidget(self._canvas, stretch=1)

        # Bouton de sauvegarde du graphique
        self._btn_sauvegarder_graph = QPushButton("💾 Sauvegarder le &graphique (PNG)")
        self._btn_sauvegarder_graph.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn_sauvegarder_graph.setMinimumHeight(36)
        self._btn_sauvegarder_graph.setStyleSheet(
            "QPushButton{background:#2c7a3a;color:white;font-size:12px;"
            "border-radius:5px;padding:6px;}"
            "QPushButton:hover{background:#3a9e4d;}"
            "QPushButton:disabled{background:#aaa;}"
        )
        configurer_bouton(
            self._btn_sauvegarder_graph,
            "Sauvegarder le graphique en PNG",
            "Enregistre le graphique affiché en image PNG haute résolution "
            "avec en-tête identifiant l'exercice et le type de graphique."
        )
        self._btn_sauvegarder_graph.clicked.connect(self._sauvegarder_graphique)
        lay_g.addWidget(self._btn_sauvegarder_graph)

        self._splitter.addWidget(panneau_gauche)

        # ── Panneau droit : aperçu + options + bouton ─────────────────────
        panneau_droit = QWidget()
        lay_d = QVBoxLayout(panneau_droit)
        lay_d.setContentsMargins(6, 0, 0, 0)
        lay_d.setSpacing(8)

        lbl_apercu = QLabel("Aperçu du compte de résultat :")
        lbl_apercu.setStyleSheet("font-weight:bold; color:#1a3a5c;")
        lay_d.addWidget(lbl_apercu)

        self._lbl_apercu = QTextEdit()
        self._lbl_apercu.setReadOnly(True)
        self._lbl_apercu.setFontFamily("Courier New")
        self._lbl_apercu.setFontPointSize(9)
        self._lbl_apercu.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._lbl_apercu.setAccessibleName("Aperçu textuel du compte de résultat")
        lay_d.addWidget(self._lbl_apercu, stretch=1)

        # ── Dossier de sortie des rapports ────────────────────────────────
        grp_sortie = QGroupBox("Dossier de sortie des rapports")
        grp_sortie.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grp_sortie.setAccessibleDescription(
            "Choisissez le dossier où les rapports Word et PDF seront enregistrés. "
            "Ce choix est mémorisé pour les prochaines générations."
        )
        lay_sortie = QHBoxLayout(grp_sortie)
        lay_sortie.setContentsMargins(10, 8, 10, 8)
        lay_sortie.setSpacing(8)

        self._edit_dossier_sortie = QLineEdit()
        self._edit_dossier_sortie.setPlaceholderText(
            "Ex : C:\\Mes documents\\Rapports Culture Musique"
        )
        self._edit_dossier_sortie.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._edit_dossier_sortie.setAccessibleName("Dossier de sortie des rapports")
        self._edit_dossier_sortie.setAccessibleDescription(
            "Chemin du dossier où seront enregistrés les rapports générés."
        )
        # Charger la valeur persistée
        self._edit_dossier_sortie.setText(
            self._config.get(self._CLE_DOSSIER, str(Path.home()))
        )
        self._edit_dossier_sortie.textChanged.connect(self._on_dossier_sortie_change)
        lay_sortie.addWidget(self._edit_dossier_sortie, stretch=1)

        btn_parcourir_sortie = QPushButton("&Parcourir…")
        btn_parcourir_sortie.setFixedWidth(110)
        configurer_bouton(btn_parcourir_sortie, "Parcourir pour le dossier de sortie",
                          "Ouvre un sélecteur de dossier pour choisir la destination des rapports.")
        btn_parcourir_sortie.clicked.connect(self._choisir_dossier_sortie)
        lay_sortie.addWidget(btn_parcourir_sortie)

        lay_d.addWidget(grp_sortie)

        # Options export
        grp_opt = QGroupBox("Export")
        grp_opt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay_opt = QVBoxLayout(grp_opt)
        self._chk_pdf = QCheckBox("&Convertir automatiquement en PDF")
        self._chk_pdf.setChecked(True)
        lay_opt.addWidget(self._chk_pdf)
        lay_d.addWidget(grp_opt)

        self._btn_generer = QPushButton("📄 &Générer le rapport complet")
        self._btn_generer.setMinimumHeight(44)
        self._btn_generer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn_generer.setStyleSheet(
            "QPushButton{background:#1a3a5c;color:white;font-size:13px;"
            "border-radius:6px;padding:8px;}"
            "QPushButton:hover{background:#2a5a8c;}"
            "QPushButton:disabled{background:#aaa;}"
        )
        configurer_bouton(self._btn_generer, "Générer le rapport Word et PDF")
        self._btn_generer.clicked.connect(self._generer_rapport)
        lay_d.addWidget(self._btn_generer)

        self._barre_prog = QProgressBar()
        self._barre_prog.setVisible(False)
        self._barre_prog.setRange(0, 0)
        self._barre_prog.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay_d.addWidget(self._barre_prog)

        self._lbl_status = QLabel("")
        self._lbl_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay_d.addWidget(self._lbl_status)

        self._splitter.addWidget(panneau_droit)

        # Proportions initiales : 45% / 55%
        self._splitter.setStretchFactor(0, 45)
        self._splitter.setStretchFactor(1, 55)
        self._splitter.setSizes([440, 540])

        layout.addWidget(self._splitter, stretch=1)

    # ── Slots ─────────────────────────────────────────────────────────────

    def set_exercice(self, exercice: Exercice):
        self._exercice = exercice
        self._date_debut.setDate(QDate(exercice.annee, 1, 1))
        self._date_fin.setDate(QDate(exercice.annee, 12, 31))
        # Mettre à jour la liste des projets
        self._combo_projet.clear()
        self._combo_projet.addItem("Tous les projets", None)
        for projet in self._analytique.projets_actifs():
            self._combo_projet.addItem(projet.nom, projet.id)

    def set_config(self, config: dict):
        self._config = config
        # Recharger le dossier de sortie si modifié dans les paramètres
        nouveau_dossier = config.get(self._CLE_DOSSIER, "")
        if nouveau_dossier and nouveau_dossier != self._edit_dossier_sortie.text():
            self._edit_dossier_sortie.blockSignals(True)
            self._edit_dossier_sortie.setText(nouveau_dossier)
            self._edit_dossier_sortie.blockSignals(False)

    def _get_periode(self):
        if self._radio_annuel.isChecked() and self._exercice:
            return self._exercice.date_debut, self._exercice.date_fin
        d = self._date_debut.date()
        f = self._date_fin.date()
        return date(d.year(), d.month(), d.day()), date(f.year(), f.month(), f.day())

    def _calculer(self):
        """Calcule le compte de résultat et met à jour aperçu + graphique."""
        if not self._exercice:
            self._lbl_apercu.setPlainText("Aucun exercice chargé. Importez des relevés (Alt+1).")
            return

        debut, fin = self._get_periode()
        projet_id = self._combo_projet.currentData()

        # Exclure les prêts du compte de résultat
        tx_cr = [t for t in self._exercice.transactions
                 if t.categorie_id != "pret_recu"]

        self._cr_cache = CompteResultat(
            self._moteur, tx_cr, debut, fin,
            projet_id=projet_id,
            solde_initial=self._exercice.solde_initial,
        )
        cr = self._cr_cache

        # Aperçu textuel
        lignes = [
            f"Période : {debut.strftime('%d/%m/%Y')} → {fin.strftime('%d/%m/%Y')}",
            f"Transactions : {len(cr._transactions_periode)}  "
            f"|  Non cat. : {len(cr.transactions_non_categorisees)}",
            "",
            "RECETTES :",
        ]
        for l in cr.lignes_recettes:
            lignes.append(
                f"  {l.label:<40} {float(l.montant):>10,.2f} €  ({l.pourcentage:.1f}%)"
            )
        lignes.append(f"  {'TOTAL RECETTES':<40} {float(cr.total_recettes):>10,.2f} €")
        lignes.extend(["", "DÉPENSES :"])
        for l in cr.lignes_depenses:
            lignes.append(
                f"  {l.label:<40} {float(l.montant):>10,.2f} €  ({l.pourcentage:.1f}%)"
            )
        lignes.append(f"  {'TOTAL DÉPENSES':<40} {float(cr.total_depenses):>10,.2f} €")
        signe = "+" if cr.est_excedentaire else ""
        lignes.extend([
            "",
            f"  {'RÉSULTAT NET':<40} {signe}{float(cr.resultat_net):>10,.2f} €",
            f"  {'Solde estimé fin de période':<40} {float(cr.solde_final):>10,.2f} €",
        ])
        self._lbl_apercu.setPlainText("\n".join(lignes))

        # Mettre à jour le graphique
        self._mettre_a_jour_graphique()

    def _mettre_a_jour_graphique(self):
        """Redessine le graphique selon le type sélectionné et le compte de résultat en cache."""
        if not self._cr_cache:
            return

        cr = self._cr_cache
        cp = self._config.get("couleur_principale", "#1a3a5c")
        cs = self._config.get("couleur_secondaire", "#e8f0f7")
        type_key = self._combo_type_graph.currentData()

        if type_key == "camembert_recettes":
            self._canvas.tracer_camembert(
                cr.lignes_recettes, "Répartition des recettes", cp
            )
        elif type_key == "camembert_depenses":
            self._canvas.tracer_camembert(
                cr.lignes_depenses, "Répartition des dépenses", cp
            )
        elif type_key == "histogramme":
            self._canvas.tracer_histogramme(cr.evolution_mensuelle(), cp, cs)
        elif type_key == "courbe_tresorerie":
            self._canvas.tracer_courbe(
                cr.evolution_mensuelle(), cr.solde_initial, cp, cs
            )

    def _sauvegarder_graphique(self) -> None:
        """Sauvegarde le graphique courant en PNG avec métadonnées d'identification."""
        if not self._exercice:
            QMessageBox.warning(self, "Aucun exercice",
                                "Importez d'abord un exercice (Alt+1).")
            return
        if self._canvas.est_vide:
            QMessageBox.information(self, "Graphique vide",
                                    "Calculez d'abord l'aperçu (bouton « Calculer »).")
            return

        from datetime import date as dt_date
        # ── Construire le nom de fichier ──────────────────────────────────
        label = getattr(self._exercice, "libelle", str(self._exercice.annee))
        type_graph = self._combo_type_graph.currentData() or "graphique"
        today = dt_date.today().strftime("%Y%m%d")
        nom_defaut = f"Graphique_{label}_{type_graph}_{today}.png"

        dossier_sortie = self._edit_dossier_sortie.text().strip()
        if not dossier_sortie or not Path(dossier_sortie).is_dir():
            dossier_sortie = str(Path.home())

        chemin_defaut = str(Path(dossier_sortie) / nom_defaut)

        # ── Demander confirmation de l'emplacement ────────────────────────
        chemin, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder le graphique",
            chemin_defaut, "Images PNG (*.png);;Images SVG (*.svg)"
        )
        if not chemin:
            return

        # ── Récupérer les métadonnées d'identification ────────────────────
        nom_asso = self._config.get("nom", "Association")
        libelle_ex = getattr(self._exercice, "libelle", str(self._exercice.annee))
        periode = (
            f"{self._exercice.date_debut:%d/%m/%Y}"
            f" → {self._exercice.date_fin:%d/%m/%Y}"
        )
        titre_graph = self._combo_type_graph.currentText()

        # Version de l'application depuis pyproject.toml si disponible
        try:
            import importlib.metadata
            version = importlib.metadata.version("commonledger")
        except Exception:
            version = ""

        # ── Sauvegarder ──────────────────────────────────────────────────
        try:
            dpi = 300 if chemin.lower().endswith(".png") else 150
            self._canvas.sauvegarder_vers(
                chemin=chemin,
                nom_asso=nom_asso,
                libelle_exercice=libelle_ex,
                periode=periode,
                titre_graph=titre_graph,
                version_app=version,
                dpi=dpi,
            )
            self.message_status.emit(f"Graphique sauvegardé : {Path(chemin).name}")
            # Proposer d'ouvrir le fichier
            rep = QMessageBox.question(
                self, "Graphique sauvegardé",
                f"Graphique enregistré :\n{chemin}\n\nOuvrir le fichier ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if rep == QMessageBox.Yes:
                import os
                os.startfile(chemin)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de sauvegarder le graphique :\n{e}")

    def _choisir_dossier_sortie(self) -> None:
        """Ouvre un sélecteur de dossier pour la destination des rapports."""
        dossier_actuel = self._edit_dossier_sortie.text().strip() or str(Path.home())
        d = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier de sortie des rapports", dossier_actuel,
        )
        if d:
            self._edit_dossier_sortie.setText(d)

    def _on_dossier_sortie_change(self, texte: str) -> None:
        """Persiste le dossier de sortie dans config/association.json dès sa modification."""
        import json
        chemin_config = Path("config/association.json")
        if chemin_config.exists():
            try:
                with open(chemin_config, encoding="utf-8") as f:
                    data = json.load(f)
                data[self._CLE_DOSSIER] = texte.strip()
                with open(chemin_config, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self._config[self._CLE_DOSSIER] = texte.strip()
            except Exception:
                pass  # Silencieux — ne pas bloquer l'UI pour une erreur de config

    def _generer_rapport(self):
        if not self._exercice:
            QMessageBox.warning(self, "Aucun exercice",
                                "Importez d'abord un exercice (Alt+1).")
            return
        if not self._cr_cache:
            self._calculer()

        # ── Déterminer le dossier de sortie ───────────────────────────────
        dossier_sortie = self._edit_dossier_sortie.text().strip()
        if not dossier_sortie or not Path(dossier_sortie).is_dir():
            # Dossier invalide ou non défini → demander à l'utilisateur
            QMessageBox.warning(
                self, "Dossier de sortie invalide",
                "Le dossier de sortie des rapports est invalide ou inexistant.\n\n"
                "Veuillez en choisir un valide via le bouton « Parcourir »."
            )
            return

        # ── Construire le nom de fichier automatiquement ──────────────────
        from datetime import date as dt_date
        label = getattr(self._exercice, "libelle", str(self._exercice.annee))
        suffixe = "annuel" if self._radio_annuel.isChecked() else "intermediaire"
        today = dt_date.today().strftime("%Y%m%d")
        nom = f"Rapport_{label}_{suffixe}_{today}.docx"
        chemin = str(Path(dossier_sortie) / nom)

        # Demander confirmation si le fichier existe déjà
        if Path(chemin).exists():
            rep = QMessageBox.question(
                self, "Fichier existant",
                f"Le fichier « {nom} » existe déjà dans ce dossier.\n\n"
                "Voulez-vous le remplacer ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if rep != QMessageBox.Yes:
                return

        reporter = DocxReporter(self._config, self._moteur)
        self._btn_generer.setEnabled(False)
        self._barre_prog.setVisible(True)
        self._lbl_status.setText("Génération en cours…")

        self._thread = QThread()
        self._worker = WorkerRapport(
            reporter, self._cr_cache, chemin,
            self._chk_pdf.isChecked(), self._analytique, self._exercice,
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
        self._lbl_status.setText(f"Rapport : {Path(chemin).name}")
        self.message_status.emit(f"Rapport généré : {Path(chemin).name}")
        QMessageBox.information(self, "Rapport généré",
                                f"Rapport généré avec succès :\n\n{chemin}")
        os.startfile(chemin)

    def _on_erreur(self, erreur):
        self._btn_generer.setEnabled(True)
        self._barre_prog.setVisible(False)
        self._lbl_status.setText(f"Erreur : {erreur}")
        QMessageBox.critical(self, "Erreur", f"Erreur :\n\n{erreur}")
