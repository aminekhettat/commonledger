"""
Génération des graphiques pour les rapports comptables.

Ce module produit des graphiques matplotlib sauvegardés en PNG
temporaires, qui sont ensuite intégrés dans le document Word.

Graphiques disponibles :
- Camembert des recettes par catégorie
- Camembert des dépenses par catégorie
- Histogramme mensuel recettes vs dépenses
- Courbe d'évolution du solde

Chaque graphique génère aussi des données tabulaires textuelles
pour l'accessibilité (NVDA/JAWS).
"""

import io
import logging
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Backend sans fenêtre (génération fichier seulement)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

logger = logging.getLogger(__name__)

# Noms des mois en français
MOIS_FR = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]


class GraphiquesMaker:
    """
    Fabrique les graphiques du rapport comptable.

    Tous les graphiques sont exportés en PNG haute résolution dans
    un répertoire temporaire, et accompagnés d'un tableau textuel
    pour l'accessibilité.

    Attributes:
        couleur_principale: Couleur principale de l'association (#RRGGBB).
        couleur_secondaire: Couleur secondaire de l'association (#RRGGBB).
        dpi:                Résolution des images générées.
    """

    def __init__(
        self,
        couleur_principale: str = "#1a3a5c",
        couleur_secondaire: str = "#e8f0f7",
        dpi: int = 150,
    ):
        self.couleur_principale = couleur_principale
        self.couleur_secondaire = couleur_secondaire
        self.dpi = dpi
        self._tmpdir = tempfile.mkdtemp(prefix="comptasso_")

    def camembert_recettes(self, lignes_recettes: list) -> tuple[str, str]:
        """
        Génère le camembert de répartition des recettes.

        Args:
            lignes_recettes: Liste de LigneResultat pour les recettes.

        Returns:
            Tuple (chemin_image_png, tableau_textuel_accessibilite).
        """
        return self._camembert(
            lignes=lignes_recettes,
            titre="Répartition des recettes",
            chemin_sortie=str(Path(self._tmpdir) / "camembert_recettes.png"),
        )

    def camembert_depenses(self, lignes_depenses: list) -> tuple[str, str]:
        """
        Génère le camembert de répartition des dépenses.

        Args:
            lignes_depenses: Liste de LigneResultat pour les dépenses.

        Returns:
            Tuple (chemin_image_png, tableau_textuel_accessibilite).
        """
        return self._camembert(
            lignes=lignes_depenses,
            titre="Répartition des dépenses",
            chemin_sortie=str(Path(self._tmpdir) / "camembert_depenses.png"),
        )

    def _camembert(self, lignes: list, titre: str, chemin_sortie: str) -> tuple[str, str]:
        """Génération interne d'un camembert."""
        if not lignes:
            return "", ""

        # Filtrer les catégories vides
        lignes_non_nulles = [l for l in lignes if l.montant > 0]
        if not lignes_non_nulles:
            return "", ""

        labels = [l.label for l in lignes_non_nulles]
        montants = [float(l.montant) for l in lignes_non_nulles]
        couleurs = [l.couleur for l in lignes_non_nulles]

        fig, ax = plt.subplots(figsize=(8, 6), facecolor="white")

        wedges, texts, autotexts = ax.pie(
            montants,
            labels=None,  # Légende séparée pour lisibilité
            colors=couleurs,
            autopct=lambda pct: f"{pct:.1f}%" if pct > 3 else "",
            startangle=90,
            pctdistance=0.75,
            wedgeprops={"edgecolor": "white", "linewidth": 2},
        )

        for autotext in autotexts:
            autotext.set_fontsize(9)
            autotext.set_color("white")
            autotext.set_fontweight("bold")

        # Légende avec montants
        total = sum(montants)
        legend_labels = [
            f"{l.label} : {l.montant:,.2f} € ({float(l.montant/total*100):.1f}%)"
            for l in lignes_non_nulles
        ]
        patches = [
            mpatches.Patch(color=c, label=lbl)
            for c, lbl in zip(couleurs, legend_labels)
        ]
        ax.legend(
            handles=patches,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.25),
            ncol=1,
            fontsize=8,
            frameon=False,
        )

        ax.set_title(titre, fontsize=13, fontweight="bold", color=self.couleur_principale, pad=15)
        ax.axis("equal")

        plt.tight_layout()
        plt.savefig(chemin_sortie, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        # Tableau textuel pour l'accessibilité
        tableau = self._tableau_textuel_camembert(titre, lignes_non_nulles, total)

        return chemin_sortie, tableau

    def _tableau_textuel_camembert(self, titre: str, lignes: list, total: float) -> str:
        """Génère la description textuelle équivalente au camembert (accessibilité)."""
        lignes_txt = [f"Tableau : {titre}", f"Total : {total:,.2f} €", ""]
        lignes_txt.append(f"{'Catégorie':<40} {'Montant':>12} {'Part':>8}")
        lignes_txt.append("-" * 62)
        for l in lignes:
            pct = float(l.montant) / total * 100 if total else 0
            lignes_txt.append(
                f"{l.label:<40} {float(l.montant):>10,.2f} € {pct:>6.1f} %"
            )
        return "\n".join(lignes_txt)

    def histogramme_mensuel(
        self,
        evolution: list[dict],
    ) -> tuple[str, str]:
        """
        Génère l'histogramme mensuel recettes vs dépenses.

        Args:
            evolution: Liste de dicts issus de CompteResultat.evolution_mensuelle().

        Returns:
            Tuple (chemin_image_png, tableau_textuel_accessibilite).
        """
        if not evolution:
            return "", ""

        mois_labels = [MOIS_FR[e["mois"]][:3] for e in evolution]
        recettes = [float(e["recettes"]) for e in evolution]
        depenses = [float(e["depenses"]) for e in evolution]

        x = range(len(evolution))
        largeur = 0.35

        fig, ax = plt.subplots(figsize=(12, 5), facecolor="white")

        barres_r = ax.bar(
            [i - largeur / 2 for i in x],
            recettes,
            largeur,
            label="Recettes",
            color="#4CAF50",
            alpha=0.85,
        )
        barres_d = ax.bar(
            [i + largeur / 2 for i in x],
            depenses,
            largeur,
            label="Dépenses",
            color="#F44336",
            alpha=0.85,
        )

        # Valeurs sur les barres
        for barre in list(barres_r) + list(barres_d):
            hauteur = barre.get_height()
            if hauteur > 0:
                ax.annotate(
                    f"{hauteur:,.0f}€",
                    xy=(barre.get_x() + barre.get_width() / 2, hauteur),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=7,
                )

        ax.set_xticks(list(x))
        ax.set_xticklabels(mois_labels, fontsize=9)
        ax.set_ylabel("Montant (€)", fontsize=10)
        ax.set_title(
            "Recettes et dépenses mensuelles",
            fontsize=13,
            fontweight="bold",
            color=self.couleur_principale,
        )
        ax.legend(fontsize=10)
        ax.grid(axis="y", alpha=0.3)
        ax.set_facecolor(self.couleur_secondaire)

        for spine in ax.spines.values():
            spine.set_visible(False)

        plt.tight_layout()
        chemin = str(Path(self._tmpdir) / "histogramme_mensuel.png")
        plt.savefig(chemin, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        tableau = self._tableau_textuel_mensuel(evolution)
        return chemin, tableau

    def _tableau_textuel_mensuel(self, evolution: list[dict]) -> str:
        """Génère le tableau textuel de l'évolution mensuelle (accessibilité)."""
        lignes = ["Tableau : Recettes et dépenses mensuelles", ""]
        lignes.append(f"{'Mois':<12} {'Recettes':>12} {'Dépenses':>12} {'Résultat':>12}")
        lignes.append("-" * 50)
        for e in evolution:
            nom_mois = MOIS_FR[e["mois"]]
            r = float(e["recettes"])
            d = float(e["depenses"])
            res = r - d
            signe = "+" if res >= 0 else ""
            lignes.append(
                f"{nom_mois:<12} {r:>10,.2f} € {d:>10,.2f} € {signe}{res:>9,.2f} €"
            )
        return "\n".join(lignes)

    def courbe_tresorerie(
        self,
        evolution: list[dict],
        solde_initial: Decimal,
    ) -> tuple[str, str]:
        """
        Génère la courbe d'évolution du solde bancaire.

        Args:
            evolution:     Liste issue de CompteResultat.evolution_mensuelle().
            solde_initial: Solde au 1er janvier.

        Returns:
            Tuple (chemin_image_png, tableau_textuel_accessibilite).
        """
        if not evolution:
            return "", ""

        soldes = []
        solde_courant = float(solde_initial)
        for e in evolution:
            solde_courant += float(e["recettes"]) - float(e["depenses"])
            soldes.append(solde_courant)

        mois_labels = [MOIS_FR[e["mois"]][:3] for e in evolution]

        fig, ax = plt.subplots(figsize=(12, 4), facecolor="white")

        couleur_ligne = self.couleur_principale
        ax.plot(mois_labels, soldes, color=couleur_ligne, linewidth=2.5, marker="o", markersize=6)
        ax.fill_between(
            range(len(soldes)),
            soldes,
            alpha=0.1,
            color=couleur_ligne,
        )
        ax.set_xticks(range(len(mois_labels)))
        ax.set_xticklabels(mois_labels, fontsize=9)
        ax.set_ylabel("Solde (€)", fontsize=10)
        ax.set_title(
            "Évolution de la trésorerie",
            fontsize=13,
            fontweight="bold",
            color=self.couleur_principale,
        )
        ax.axhline(y=0, color="red", linestyle="--", alpha=0.4, linewidth=1)
        ax.grid(alpha=0.3)
        ax.set_facecolor(self.couleur_secondaire)

        for spine in ax.spines.values():
            spine.set_visible(False)

        # Annoter le dernier solde
        ax.annotate(
            f"{soldes[-1]:,.2f} €",
            xy=(len(soldes) - 1, soldes[-1]),
            xytext=(-40, 10),
            textcoords="offset points",
            fontsize=9,
            color=couleur_ligne,
            fontweight="bold",
        )

        plt.tight_layout()
        chemin = str(Path(self._tmpdir) / "courbe_tresorerie.png")
        plt.savefig(chemin, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        tableau = self._tableau_textuel_tresorerie(evolution, float(solde_initial), soldes)
        return chemin, tableau

    def _tableau_textuel_tresorerie(
        self, evolution: list[dict], solde_initial: float, soldes: list[float]
    ) -> str:
        lignes = ["Tableau : Évolution de la trésorerie", f"Solde initial : {solde_initial:,.2f} €", ""]
        lignes.append(f"{'Mois':<12} {'Solde fin de mois':>18}")
        lignes.append("-" * 32)
        for e, solde in zip(evolution, soldes):
            lignes.append(f"{MOIS_FR[e['mois']]:<12} {solde:>16,.2f} €")
        return "\n".join(lignes)

    def nettoyer(self) -> None:
        """Supprime les fichiers temporaires générés."""
        import shutil
        try:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Nettoyage des graphiques temporaires : {e}")
