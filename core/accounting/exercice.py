"""
Exercice comptable — Conteneur principal de l'année comptable.

Un Exercice regroupe :
- Les transactions importées pour l'année
- Les relevés source (pour les vérifications de cohérence)
- Le budget prévisionnel
- Les projets analytiques

Il assure également la persistance des données dans le répertoire
data/exercices/<annee>/.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..categorizer.rules_engine import MoteurCategorisation
from ..parser.models import ReleveInfo, Transaction
from .compte_resultat import CompteResultat

logger = logging.getLogger(__name__)


class Exercice:
    """
    Représente un exercice comptable complet.

    Gère l'import, la persistance et le calcul pour une année fiscale.

    Attributes:
        annee:           Année de l'exercice.
        repertoire:      Répertoire de stockage (data/exercices/YYYY/).
        transactions:    Toutes les transactions importées.
        releves:         Métadonnées des relevés importés.
        solde_initial:   Solde bancaire au 1er janvier.
        budget:          Budget prévisionnel par catégorie.
    """

    def __init__(self, annee: int, repertoire_data: str):
        """
        Initialise l'exercice et charge les données persistées si elles existent.

        Args:
            annee:           Année de début de l'exercice (ex: 2024).
                             Sert d'identifiant et de nom de répertoire.
                             Pour un exercice septembre 2025 → août 2026,
                             passer annee=2025.
            repertoire_data: Répertoire racine des données (ex: "data").
        """
        self.annee = annee
        self.repertoire = Path(repertoire_data) / "exercices" / str(annee)
        self.repertoire.mkdir(parents=True, exist_ok=True)

        self.transactions: list[Transaction] = []
        self.releves: list[dict[str, Any]] = []
        self.solde_initial: Decimal = Decimal("0")
        self.budget: dict[str, Decimal] = {}

        # Période de l'exercice — par défaut l'année civile complète.
        # Configurable pour :
        #   • exercices partiels      (ex : 01/06/2025 – 30/06/2025)
        #   • exercices à cheval      (ex : 01/09/2025 – 31/08/2026)
        self._date_debut: date = date(annee, 1, 1)
        self._date_fin: date = date(annee, 12, 31)

        self._charger()

    # ── Propriété libellé ──────────────────────────────────────────────────

    @property
    def libelle(self) -> str:
        """
        Libellé lisible de l'exercice.

        Examples:
            "2025"        pour un exercice civique (jan–déc 2025)
            "2025-2026"   pour un exercice à cheval (sept 2025 – août 2026)
        """
        if self._date_debut.year == self._date_fin.year:
            return str(self._date_debut.year)
        return f"{self._date_debut.year}-{self._date_fin.year}"

    # ── Propriétés dates avec validation ──────────────────────────────────

    @property
    def date_debut(self) -> date:
        """Début de la période de l'exercice."""
        return self._date_debut

    @date_debut.setter
    def date_debut(self, valeur: date) -> None:
        """
        Définit la date de début.

        Contraintes :
        - Doit appartenir à l'année ``annee`` (identifiant de l'exercice).
        - Doit être antérieure ou égale à ``date_fin``.
        """
        if valeur.year != self.annee:
            raise ValueError(
                f"date_debut {valeur} doit appartenir à l'année de début "
                f"de l'exercice ({self.annee}). "
                f"Pour un exercice démarrant en {valeur.year}, "
                f"créez Exercice({valeur.year}, ...)."
            )
        if valeur > self._date_fin:
            raise ValueError(
                f"date_debut {valeur} doit être antérieure à date_fin {self._date_fin}."
            )
        self._date_debut = valeur

    @property
    def date_fin(self) -> date:
        """Fin de la période de l'exercice."""
        return self._date_fin

    @date_fin.setter
    def date_fin(self, valeur: date) -> None:
        """
        Définit la date de fin.

        Contraintes :
        - Doit être postérieure ou égale à ``date_debut``.
        - Peut appartenir à l'année ``annee`` (exercice civique ou partiel)
          ou à l'année suivante ``annee + 1`` (exercice à cheval).
        - Ne peut pas dépasser 18 mois après ``date_debut``
          (garde-fou contre les saisies aberrantes).
        """
        if valeur < self._date_debut:
            raise ValueError(
                f"date_fin {valeur} doit être postérieure à date_debut {self._date_debut}."
            )
        max_fin = date(self.annee + 1, 12, 31)
        if valeur > max_fin:
            raise ValueError(
                f"date_fin {valeur} ne peut pas dépasser le 31/12/{self.annee + 1}. "
                f"Un exercice peut s'étendre au maximum sur deux années civiles."
            )
        self._date_fin = valeur

    def _charger(self) -> None:
        """Charge les transactions et métadonnées persistées."""
        fichier_tx = self.repertoire / "transactions.json"
        if fichier_tx.exists():
            with open(fichier_tx, encoding="utf-8") as f:
                data = json.load(f)
            self.transactions = [Transaction.from_dict(d) for d in data.get("transactions", [])]
            self.solde_initial = Decimal(data.get("solde_initial", "0"))
            self.releves = data.get("releves", [])
            self.budget = {k: Decimal(v) for k, v in data.get("budget", {}).items()}
            # Charger la période si elle a été configurée (rétrocompatibilité :
            # les anciens exercices n'ont pas ces champs → on garde les défauts)
            if "date_debut" in data:
                self._date_debut = date.fromisoformat(data["date_debut"])
            if "date_fin" in data:
                self._date_fin = date.fromisoformat(data["date_fin"])
            logger.info(
                f"Exercice {self.libelle} : {len(self.transactions)} transactions chargées."
            )

    def sauvegarder(self) -> None:
        """Persiste toutes les données de l'exercice."""
        fichier_tx = self.repertoire / "transactions.json"
        data = {
            "annee": self.annee,
            "date_debut": self._date_debut.isoformat(),
            "date_fin": self._date_fin.isoformat(),
            "solde_initial": str(self.solde_initial),
            "releves": self.releves,
            "budget": {k: str(v) for k, v in self.budget.items()},
            "transactions": [t.to_dict() for t in self.transactions],
        }
        with open(fichier_tx, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Exercice {self.libelle} sauvegardé : {len(self.transactions)} transactions.")

    def importer_releve(
        self,
        releve: ReleveInfo,
        copier_pdf: bool = True,
    ) -> int:
        """
        Intègre les transactions d'un relevé dans l'exercice.

        Filtre les transactions hors de l'année de l'exercice et déduplique
        les transactions déjà présentes (même id_unique).

        Un relevé peut couvrir plusieurs années (ex : août 2024 → février 2025
        importé dans l'exercice 2025). Seules les transactions de l'année
        correcte sont conservées ; les autres sont ignorées avec un log.

        Args:
            releve:      ReleveInfo issu du parseur.
            copier_pdf:  Si True, copie le PDF dans releves_importes/.

        Returns:
            Nombre de nouvelles transactions ajoutées (hors doublons et hors année).
        """
        # ── Filtrer par période de l'exercice ────────────────────────────────
        # La période est self.date_debut → self.date_fin (peut être inférieure
        # à une année complète pour les exercices partiels).
        dans_periode = [
            t for t in releve.transactions if self._date_debut <= t.date <= self._date_fin
        ]
        hors_periode = [
            t for t in releve.transactions if not (self._date_debut <= t.date <= self._date_fin)
        ]

        if hors_periode:
            logger.warning(
                f"{Path(releve.fichier).name if releve.fichier else 'relevé'} : "
                f"{len(hors_periode)} transaction(s) hors période "
                f"{self._date_debut} → {self._date_fin} ignorée(s)."
            )

        ids_existants = {t.id_unique for t in self.transactions}
        nouvelles = [t for t in dans_periode if t.id_unique not in ids_existants]

        self.transactions.extend(nouvelles)
        self.transactions.sort(key=lambda t: t.date)

        # Enregistrer la métadonnée du relevé
        meta = {
            "fichier": Path(releve.fichier).name,
            "periode_debut": releve.periode_debut.isoformat() if releve.periode_debut else None,
            "periode_fin": releve.periode_fin.isoformat() if releve.periode_fin else None,
            "solde_debut": str(releve.solde_debut) if releve.solde_debut else None,
            "solde_fin": str(releve.solde_fin) if releve.solde_fin else None,
            "nb_transactions": len(releve.transactions),
        }
        # Éviter les doublons de relevés
        noms_existants = {r["fichier"] for r in self.releves}
        if meta["fichier"] not in noms_existants:
            self.releves.append(meta)

        # Copier le PDF source
        if copier_pdf and releve.fichier:
            dossier_releves = self.repertoire / "releves_importes"
            dossier_releves.mkdir(exist_ok=True)
            dest = dossier_releves / Path(releve.fichier).name
            if not dest.exists():
                shutil.copy2(releve.fichier, dest)

        return len(nouvelles)

    def calculer_compte_resultat(
        self,
        moteur: MoteurCategorisation,
        date_debut: date | None = None,
        date_fin: date | None = None,
        projet_id: str | None = None,
    ) -> CompteResultat:
        """
        Calcule le compte de résultat pour tout ou partie de l'exercice.

        Args:
            moteur:      Moteur de catégorisation.
            date_debut:  Début de la période (1er janvier par défaut).
            date_fin:    Fin de la période (31 décembre par défaut).
            projet_id:   Si fourni, filtre par projet analytique.

        Returns:
            CompteResultat calculé.
        """
        return CompteResultat(
            moteur=moteur,
            transactions=self.transactions,
            date_debut=date_debut or self.date_debut,
            date_fin=date_fin or self.date_fin,
            projet_id=projet_id,
            solde_initial=self.solde_initial,
        )

    def transactions_non_categorisees(self) -> list[Transaction]:
        """Retourne les transactions sans catégorie ni splits."""
        return [t for t in self.transactions if not t.est_categorisee]

    def transactions_periode(self, debut: date, fin: date) -> list[Transaction]:
        """Retourne les transactions dans une période donnée."""
        return [t for t in self.transactions if debut <= t.date <= fin]

    def definir_budget(self, cat_id: str, montant: Decimal) -> None:
        """
        Définit le budget prévisionnel pour une catégorie.

        Args:
            cat_id:  Identifiant de la catégorie.
            montant: Montant budgété (toujours positif).
        """
        self.budget[cat_id] = abs(montant)

    def ecart_budget(self, cat_id: str, montant_reel: Decimal) -> Decimal | None:
        """
        Calcule l'écart entre le réalisé et le budgété.

        Args:
            cat_id:        Identifiant de la catégorie.
            montant_reel:  Montant réalisé.

        Returns:
            Écart (réel - budget), ou None si aucun budget défini.
        """
        if cat_id not in self.budget:
            return None
        return montant_reel - self.budget[cat_id]

    def resume(self) -> dict[str, Any]:
        """Retourne un résumé rapide de l'état de l'exercice."""
        non_cat = len(self.transactions_non_categorisees())
        return {
            "annee": self.annee,
            "nb_transactions": len(self.transactions),
            "nb_non_categorisees": non_cat,
            "nb_releves_importes": len(self.releves),
            "solde_initial": self.solde_initial,
            "taux_categorisation": (
                round((1 - non_cat / len(self.transactions)) * 100, 1) if self.transactions else 0.0
            ),
        }
