"""
Génération des graphiques pour les rapports comptables.

Ce module produit des graphiques matplotlib haute résolution, exportés
en PNG temporaires pour intégration dans le document Word.

Améliorations v1.1 :
  - Taille augmentée pour garantir la lisibilité
  - Légendes enrichies avec montants et pourcentages
  - Style épuré avec palette cohérente aux couleurs de l'association
"""

import logging
import tempfile
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

logger = logging.getLogger(__name__)

MOIS_FR = [
    "",
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]


def _formater_euros(x, pos):
    """Formateur d'axe en euros avec séparateurs de milliers."""
    if abs(x) >= 1000:
        return f"{x:,.0f} €".replace(",", " ")
    return f"{x:.0f} €"


class GraphiquesMaker:
    """
    Fabrique les graphiques du rapport comptable.

    Attributes:
        couleur_principale: Couleur principale (#RRGGBB).
        couleur_secondaire: Couleur de fond (#RRGGBB).
        dpi:                Résolution des images (150 = haute qualité impression).
    """

    # Tailles de figure — augmentées pour lisibilité dans le rapport
    TAILLE_CAMEMBERT = (12, 9)
    TAILLE_HISTOGRAMME = (16, 7)
    TAILLE_COURBE = (16, 5)

    def __init__(
        self,
        couleur_principale: str = "#1a3a5c",
        couleur_secondaire: str = "#e8f0f7",
        dpi: int = 150,
    ):
        self.couleur_principale = couleur_principale
        self.couleur_secondaire = couleur_secondaire
        self.dpi = dpi
        self._tmpdir = tempfile.mkdtemp(prefix="commonledger_")
        # Style global matplotlib
        plt.rcParams.update(
            {
                "font.family": "DejaVu Sans",
                "font.size": 10,
                "axes.titlesize": 13,
                "axes.titleweight": "bold",
                "figure.facecolor": "white",
                "axes.facecolor": couleur_secondaire,
                "axes.spines.top": False,
                "axes.spines.right": False,
            }
        )

    # ── Camemberts ────────────────────────────────────────────────────────────

    def camembert_recettes(self, lignes: list) -> tuple[str, str]:
        """Camembert de répartition des recettes."""
        return self._camembert(
            lignes=lignes,
            titre="Répartition des recettes",
            chemin_sortie=str(Path(self._tmpdir) / "camembert_recettes.png"),
        )

    def camembert_depenses(self, lignes: list) -> tuple[str, str]:
        """Camembert de répartition des dépenses."""
        return self._camembert(
            lignes=lignes,
            titre="Répartition des dépenses",
            chemin_sortie=str(Path(self._tmpdir) / "camembert_depenses.png"),
        )

    def _camembert(self, lignes: list, titre: str, chemin_sortie: str) -> tuple[str, str]:
        """Génération interne d'un camembert professionnel."""
        lignes_nz = [l for l in lignes if l.montant > 0]
        if not lignes_nz:
            return "", ""

        labels = [l.label for l in lignes_nz]
        montants = [float(l.montant) for l in lignes_nz]
        couleurs = [l.couleur for l in lignes_nz]
        total = sum(montants)

        fig, (ax_pie, ax_leg) = plt.subplots(
            1,
            2,
            figsize=self.TAILLE_CAMEMBERT,
            gridspec_kw={"width_ratios": [1.3, 1]},
            facecolor="white",
        )

        # ── Camembert ────────────────────────────────────────────────────────
        wedges, texts, autotexts = ax_pie.pie(
            montants,
            colors=couleurs,
            autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
            startangle=90,
            pctdistance=0.72,
            wedgeprops={"edgecolor": "white", "linewidth": 2.5, "antialiased": True},
            textprops={"fontsize": 10},
        )
        for at in autotexts:
            at.set_fontweight("bold")
            at.set_color("white")
            at.set_fontsize(9)

        ax_pie.set_title(
            titre, fontsize=14, fontweight="bold", color=self.couleur_principale, pad=18
        )

        # Cercle central (donut effect)
        centre = plt.Circle((0, 0), 0.45, color="white")
        ax_pie.add_patch(centre)
        ax_pie.text(
            0,
            0,
            f"{total:,.0f} €".replace(",", " "),
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold",
            color=self.couleur_principale,
        )

        # ── Légende détaillée ─────────────────────────────────────────────────
        ax_leg.axis("off")
        legend_items = []
        for i, l in enumerate(lignes_nz):
            pct = float(l.montant) / total * 100
            patch = mpatches.Patch(color=couleurs[i], linewidth=0)
            legend_items.append(patch)

        legend = ax_leg.legend(
            handles=legend_items,
            labels=[
                f"{l.label}\n{float(l.montant):,.2f} €   {float(l.montant) / total * 100:.1f}%".replace(
                    ",", " "
                )
                for l in lignes_nz
            ],
            loc="center left",
            frameon=False,
            fontsize=9.5,
            labelspacing=1.1,
            handlelength=1.2,
            handleheight=1.2,
        )

        plt.tight_layout(pad=1.5)
        plt.savefig(
            chemin_sortie, dpi=self.dpi, bbox_inches="tight", facecolor="white", edgecolor="none"
        )
        plt.close(fig)

        tableau = self._tableau_textuel_camembert(titre, lignes_nz, total)
        return chemin_sortie, tableau

    def _tableau_textuel_camembert(self, titre: str, lignes: list, total: float) -> str:
        lignes_txt = [f"Tableau : {titre}", f"Total : {total:,.2f} €", ""]
        lignes_txt.append(f"{'Catégorie':<40} {'Montant':>12} {'Part':>8}")
        lignes_txt.append("-" * 62)
        for l in lignes:
            pct = float(l.montant) / total * 100 if total else 0
            lignes_txt.append(f"{l.label:<40} {float(l.montant):>10,.2f} € {pct:>6.1f} %")
        return "\n".join(lignes_txt)

    # ── Histogramme mensuel ───────────────────────────────────────────────────

    def histogramme_mensuel(self, evolution: list[dict]) -> tuple[str, str]:
        """Histogramme mensuel recettes vs dépenses."""
        if not evolution:
            return "", ""

        mois_labels = [MOIS_FR[e["mois"]][:4] + "." for e in evolution]
        recettes = [float(e["recettes"]) for e in evolution]
        depenses = [float(e["depenses"]) for e in evolution]

        x = range(len(evolution))
        largeur = 0.38

        fig, ax = plt.subplots(figsize=self.TAILLE_HISTOGRAMME, facecolor="white")

        barres_r = ax.bar(
            [i - largeur / 2 for i in x],
            recettes,
            largeur,
            label="Recettes",
            color="#27AE60",
            alpha=0.88,
            zorder=3,
        )
        barres_d = ax.bar(
            [i + largeur / 2 for i in x],
            depenses,
            largeur,
            label="Dépenses",
            color="#E74C3C",
            alpha=0.88,
            zorder=3,
        )

        # Valeurs sur les barres
        for barre in list(barres_r) + list(barres_d):
            h = barre.get_height()
            if h > 50:
                ax.text(
                    barre.get_x() + barre.get_width() / 2,
                    h + 10,
                    f"{h:,.0f} €".replace(",", " "),
                    ha="center",
                    va="bottom",
                    fontsize=7.5,
                    color="#333333",
                )

        ax.set_xticks(list(x))
        ax.set_xticklabels(mois_labels, fontsize=10)
        ax.set_ylabel("Montant (€)", fontsize=11)
        ax.set_title(
            "Recettes et dépenses par mois",
            fontsize=14,
            fontweight="bold",
            color=self.couleur_principale,
            pad=15,
        )
        ax.yaxis.set_major_formatter(FuncFormatter(_formater_euros))
        ax.grid(axis="y", alpha=0.4, zorder=0)
        ax.set_facecolor(self.couleur_secondaire)
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Légende enrichie avec totaux
        total_r = sum(recettes)
        total_d = sum(depenses)
        ax.legend(
            labels=[
                f"Recettes  (total : {total_r:,.2f} €)".replace(",", " "),
                f"Dépenses (total : {total_d:,.2f} €)".replace(",", " "),
            ],
            fontsize=11,
            loc="upper right",
            framealpha=0.9,
            edgecolor="#cccccc",
        )

        plt.tight_layout()
        chemin = str(Path(self._tmpdir) / "histogramme_mensuel.png")
        plt.savefig(chemin, dpi=self.dpi, bbox_inches="tight", facecolor="white", edgecolor="none")
        plt.close(fig)

        return chemin, self._tableau_textuel_mensuel(evolution)

    def _tableau_textuel_mensuel(self, evolution: list[dict]) -> str:
        lignes = ["Tableau : Recettes et dépenses mensuelles", ""]
        lignes.append(f"{'Mois':<12} {'Recettes':>12} {'Dépenses':>12} {'Résultat':>12}")
        lignes.append("-" * 50)
        for e in evolution:
            nom = MOIS_FR[e["mois"]]
            r, d = float(e["recettes"]), float(e["depenses"])
            res = r - d
            lignes.append(f"{nom:<12} {r:>10,.2f} € {d:>10,.2f} € {res:>+9,.2f} €")
        return "\n".join(lignes)

    # ── Courbe de trésorerie ──────────────────────────────────────────────────

    def courbe_tresorerie(self, evolution: list[dict], solde_initial: Decimal) -> tuple[str, str]:
        """Courbe d'évolution du solde bancaire."""
        if not evolution:
            return "", ""

        soldes = []
        s = float(solde_initial)
        for e in evolution:
            s += float(e["recettes"]) - float(e["depenses"])
            soldes.append(s)

        mois_labels = [MOIS_FR[e["mois"]][:4] + "." for e in evolution]

        fig, ax = plt.subplots(figsize=self.TAILLE_COURBE, facecolor="white")

        # Zone de remplissage
        couleur_ligne = self.couleur_principale
        ax.fill_between(range(len(soldes)), soldes, alpha=0.12, color=couleur_ligne, zorder=2)
        ax.plot(
            range(len(soldes)),
            soldes,
            color=couleur_ligne,
            linewidth=2.5,
            marker="o",
            markersize=7,
            zorder=3,
            label="Solde bancaire",
        )

        # Points de données annotés
        for i, (s_val, label) in enumerate(zip(soldes, mois_labels)):
            if i == 0 or i == len(soldes) - 1 or i % 3 == 0:
                ax.annotate(
                    f"{s_val:,.0f} €".replace(",", " "),
                    xy=(i, s_val),
                    xytext=(0, 12),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8.5,
                    color=couleur_ligne,
                    fontweight="bold",
                )

        ax.axhline(y=0, color="#E74C3C", linestyle="--", alpha=0.5, linewidth=1.2)
        ax.set_xticks(range(len(mois_labels)))
        ax.set_xticklabels(mois_labels, fontsize=10)
        ax.set_ylabel("Solde (€)", fontsize=11)
        ax.set_title(
            "Évolution de la trésorerie",
            fontsize=14,
            fontweight="bold",
            color=self.couleur_principale,
            pad=15,
        )
        ax.yaxis.set_major_formatter(FuncFormatter(_formater_euros))
        ax.grid(alpha=0.35, zorder=0)
        ax.set_facecolor(self.couleur_secondaire)
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Légende avec solde initial et final
        ax.legend(
            labels=[
                f"Solde (départ : {float(solde_initial):,.2f} €  —  "
                f"arrivée : {soldes[-1]:,.2f} €)".replace(",", " ")
            ],
            fontsize=11,
            loc="upper left",
            framealpha=0.9,
            edgecolor="#cccccc",
        )

        plt.tight_layout()
        chemin = str(Path(self._tmpdir) / "courbe_tresorerie.png")
        plt.savefig(chemin, dpi=self.dpi, bbox_inches="tight", facecolor="white", edgecolor="none")
        plt.close(fig)

        return chemin, self._tableau_textuel_tresorerie(evolution, float(solde_initial), soldes)

    def _tableau_textuel_tresorerie(
        self, evolution: list[dict], solde_initial: float, soldes: list[float]
    ) -> str:
        lignes = [
            "Tableau : Évolution de la trésorerie",
            f"Solde initial : {solde_initial:,.2f} €",
            "",
        ]
        lignes.append(f"{'Mois':<12} {'Solde fin de mois':>18}")
        lignes.append("-" * 32)
        for e, s in zip(evolution, soldes):
            lignes.append(f"{MOIS_FR[e['mois']]:<12} {s:>16,.2f} €")
        return "\n".join(lignes)

    def nettoyer(self) -> None:
        """Supprime les fichiers temporaires."""
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)
