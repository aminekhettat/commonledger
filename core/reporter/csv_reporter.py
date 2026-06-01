"""
Export CSV du compte de résultat et du détail des transactions.

Génère deux fichiers CSV :
  1. ``synthese_YYYY.csv``  — Compte de résultat synthétique (une ligne par catégorie)
  2. ``transactions_YYYY.csv`` — Détail de toutes les transactions catégorisées

Ces fichiers sont utiles pour :
  - Archivage et audit externe
  - Import dans un tableur (Excel, LibreOffice Calc)
  - Transmission au commissaire aux comptes

Format :
    Séparateur virgule, encodage UTF-8 avec BOM (compatible Excel Windows).
"""

import csv
import logging
from pathlib import Path

from ..accounting.compte_resultat import CompteResultat
from ..categorizer.rules_engine import MoteurCategorisation

logger = logging.getLogger(__name__)


class CsvReporter:
    """
    Exporte le compte de résultat et les transactions au format CSV.

    Exemple::

        reporter = CsvReporter(moteur, compte_resultat)
        synthese, detail = reporter.exporter("rapports/2024")
        print(f"Synthèse : {synthese}")
        print(f"Détail   : {detail}")
    """

    def __init__(self, moteur: MoteurCategorisation, compte_resultat: CompteResultat):
        """
        Args:
            moteur:          Moteur de catégorisation (pour les libellés).
            compte_resultat: Résultat calculé.
        """
        self.moteur = moteur
        self.cr = compte_resultat

    def exporter(self, repertoire_sortie: str) -> tuple[str, str]:
        """
        Génère les deux fichiers CSV dans le répertoire indiqué.

        Args:
            repertoire_sortie: Dossier où écrire les fichiers CSV.

        Returns:
            Tuple (chemin_synthese, chemin_detail).
        """
        rep = Path(repertoire_sortie)
        rep.mkdir(parents=True, exist_ok=True)

        annee = self.cr.date_debut.year
        chemin_synthese = rep / f"synthese_{annee}.csv"
        chemin_detail = rep / f"transactions_{annee}.csv"

        self._ecrire_synthese(chemin_synthese)
        self._ecrire_detail(chemin_detail)

        logger.info(f"CSV exportés : {chemin_synthese.name}, {chemin_detail.name}")
        return str(chemin_synthese), str(chemin_detail)

    def _ecrire_synthese(self, chemin: Path) -> None:
        """Écrit le fichier CSV de synthèse du compte de résultat."""
        with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            # En-tête
            writer.writerow(["Type", "Catégorie", "Montant (€)", "Part (%)", "Nb opérations"])

            # Recettes
            for ligne in self.cr.lignes_recettes:
                writer.writerow(
                    [
                        "Recette",
                        ligne.label,
                        f"{float(ligne.montant):.2f}",
                        f"{ligne.pourcentage:.1f}",
                        ligne.nb_transactions,
                    ]
                )

            # Sous-total recettes
            writer.writerow(
                [
                    "TOTAL RECETTES",
                    "",
                    f"{float(self.cr.total_recettes):.2f}",
                    "100.0",
                    "",
                ]
            )

            writer.writerow([])  # ligne vide

            # Dépenses
            for ligne in self.cr.lignes_depenses:
                writer.writerow(
                    [
                        "Dépense",
                        ligne.label,
                        f"{float(ligne.montant):.2f}",
                        f"{ligne.pourcentage:.1f}",
                        ligne.nb_transactions,
                    ]
                )

            # Sous-total dépenses
            writer.writerow(
                [
                    "TOTAL DÉPENSES",
                    "",
                    f"{float(self.cr.total_depenses):.2f}",
                    "100.0",
                    "",
                ]
            )

            writer.writerow([])

            # Résultat net
            signe = "+" if self.cr.est_excedentaire else ""
            writer.writerow(
                [
                    "RÉSULTAT NET",
                    "",
                    f"{signe}{float(self.cr.resultat_net):.2f}",
                    "",
                    "",
                ]
            )

            # Informations de période
            writer.writerow([])
            writer.writerow(["Période début", self.cr.date_debut.strftime("%d/%m/%Y")])
            writer.writerow(["Période fin", self.cr.date_fin.strftime("%d/%m/%Y")])
            writer.writerow(["Solde initial", f"{float(self.cr.solde_initial):.2f}"])
            writer.writerow(["Solde final estimé", f"{float(self.cr.solde_final):.2f}"])
            nc = len(self.cr.transactions_non_categorisees)
            if nc:
                writer.writerow(["Attention", f"{nc} transaction(s) non catégorisée(s) exclue(s)"])

    def _ecrire_detail(self, chemin: Path) -> None:
        """Écrit le fichier CSV de détail de toutes les transactions."""
        with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            # En-tête
            writer.writerow(
                [
                    "Date",
                    "Libellé",
                    "Montant (€)",
                    "Type",
                    "Catégorie",
                    "Projet",
                    "Mémo",
                    "Fichier source",
                ]
            )

            # Toutes les transactions catégorisées de la période
            txs = sorted(self.cr._transactions_periode, key=lambda t: t.date)
            for t in txs:
                if t.est_splittee:
                    # Une ligne par split
                    for split in t.splits:
                        cat = self.moteur.get_categorie(split.categorie_id)
                        writer.writerow(
                            [
                                t.date.strftime("%d/%m/%Y"),
                                t.libelle,
                                f"{float(split.montant):.2f}"
                                if t.est_credit
                                else f"{-float(split.montant):.2f}",
                                "Recette" if t.est_credit else "Dépense",
                                cat.label if cat else split.categorie_id,
                                split.projet_id or "",
                                t.memo,
                                t.source_fichier,
                            ]
                        )
                elif t.categorie_id:
                    cat = self.moteur.get_categorie(t.categorie_id)
                    writer.writerow(
                        [
                            t.date.strftime("%d/%m/%Y"),
                            t.libelle,
                            f"{float(t.montant):.2f}",
                            "Recette" if t.est_credit else "Dépense",
                            cat.label if cat else t.categorie_id,
                            t.projet_id or "",
                            t.memo,
                            t.source_fichier,
                        ]
                    )
                else:
                    # Non catégorisée
                    writer.writerow(
                        [
                            t.date.strftime("%d/%m/%Y"),
                            t.libelle,
                            f"{float(t.montant):.2f}",
                            "Recette" if t.est_credit else "Dépense",
                            "— Non catégorisée —",
                            "",
                            t.memo,
                            t.source_fichier,
                        ]
                    )
