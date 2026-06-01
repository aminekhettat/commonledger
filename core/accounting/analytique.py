"""
Comptabilité analytique par projet.

Ce module permet de rattacher des transactions à des projets
et de produire un compte de résultat par projet (concert,
tournée, atelier, etc.).

Un même exercice peut avoir plusieurs projets actifs simultanément.
Une transaction peut être rattachée à un seul projet (ou aucun).
Une transaction éclatée (split) peut répartir ses parts entre
différents projets.
"""

from __future__ import annotations
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from ..parser.models import Transaction

logger = logging.getLogger(__name__)


@dataclass
class Projet:
    """
    Représente un projet analytique (concert, atelier, tournée...).

    Attributes:
        id:           Identifiant unique (UUID généré automatiquement).
        nom:          Nom du projet.
        description:  Description courte.
        date_debut:   Date de début du projet.
        date_fin:     Date de fin du projet (None = en cours).
        budget:       Budget prévisionnel du projet.
        actif:        True si le projet est actif (accepte de nouvelles transactions).
        couleur:      Couleur hexadécimale pour l'affichage.
    """
    nom: str
    description: str = ""
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    budget: Decimal = Decimal("0")
    actif: bool = True
    couleur: str = "#1565C0"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nom": self.nom,
            "description": self.description,
            "date_debut": self.date_debut.isoformat() if self.date_debut else None,
            "date_fin": self.date_fin.isoformat() if self.date_fin else None,
            "budget": str(self.budget),
            "actif": self.actif,
            "couleur": self.couleur,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Projet:
        return cls(
            id=d["id"],
            nom=d["nom"],
            description=d.get("description", ""),
            date_debut=date.fromisoformat(d["date_debut"]) if d.get("date_debut") else None,
            date_fin=date.fromisoformat(d["date_fin"]) if d.get("date_fin") else None,
            budget=Decimal(d.get("budget", "0")),
            actif=d.get("actif", True),
            couleur=d.get("couleur", "#1565C0"),
        )


@dataclass
class BilanProjet:
    """
    Résumé comptable d'un projet.

    Attributes:
        projet:      Le projet concerné.
        recettes:    Total des recettes affectées au projet.
        depenses:    Total des dépenses affectées au projet.
        transactions:Toutes les transactions (ou parts de splits) du projet.
    """
    projet: Projet
    recettes: Decimal = Decimal("0")
    depenses: Decimal = Decimal("0")
    transactions: list[Transaction] = field(default_factory=list)

    @property
    def resultat(self) -> Decimal:
        return self.recettes - self.depenses

    @property
    def taux_realisation_budget(self) -> Optional[float]:
        """Taux de réalisation du budget (dépenses / budget) en %."""
        if self.projet.budget and self.projet.budget > 0:
            return float(self.depenses / self.projet.budget * 100)
        return None


class ComptaAnalytique:
    """
    Gestion de la comptabilité analytique par projet.

    Charge, sauvegarde et calcule les bilans par projet.

    Exemple::

        ana = ComptaAnalytique("data/projets.json")
        concert = ana.creer_projet("Concert du 15 mars", date(2024,3,15))
        ana.affecter_transaction(transaction, concert.id)
        bilan = ana.calculer_bilan(concert.id, transactions)
    """

    def __init__(self, chemin_projets: str):
        """
        Initialise le module analytique.

        Args:
            chemin_projets: Chemin vers le fichier JSON des projets.
        """
        self.chemin = Path(chemin_projets)
        self.projets: dict[str, Projet] = {}
        self._charger()

    def _charger(self) -> None:
        """Charge les projets depuis le fichier JSON."""
        if not self.chemin.exists():
            return

        with open(self.chemin, encoding="utf-8") as f:
            data = json.load(f)

        self.projets = {
            p["id"]: Projet.from_dict(p)
            for p in data.get("projets", [])
        }

    def sauvegarder(self) -> None:
        """Persiste les projets dans le fichier JSON."""
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        data = {"projets": [p.to_dict() for p in self.projets.values()]}
        with open(self.chemin, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def creer_projet(
        self,
        nom: str,
        date_debut: Optional[date] = None,
        description: str = "",
        budget: Decimal = Decimal("0"),
    ) -> Projet:
        """
        Crée un nouveau projet et le sauvegarde.

        Args:
            nom:         Nom du projet.
            date_debut:  Date de début (aujourd'hui par défaut).
            description: Description courte.
            budget:      Budget prévisionnel.

        Returns:
            Le projet créé.
        """
        projet = Projet(
            nom=nom,
            description=description,
            date_debut=date_debut or date.today(),
            budget=budget,
        )
        self.projets[projet.id] = projet
        self.sauvegarder()
        return projet

    def modifier_projet(self, projet_id: str, **kwargs) -> Projet:
        """
        Modifie les attributs d'un projet existant.

        Args:
            projet_id: Identifiant du projet.
            **kwargs:  Attributs à modifier (nom, description, date_fin, budget, actif).

        Returns:
            Le projet modifié.

        Raises:
            KeyError: Si le projet n'existe pas.
        """
        if projet_id not in self.projets:
            raise KeyError(f"Projet inconnu : {projet_id}")

        projet = self.projets[projet_id]
        for cle, valeur in kwargs.items():
            if hasattr(projet, cle):
                setattr(projet, cle, valeur)

        self.sauvegarder()
        return projet

    def supprimer_projet(self, projet_id: str) -> None:
        """
        Supprime un projet.

        Les transactions affectées à ce projet perdent leur projet_id.
        Cette opération est irréversible.

        Args:
            projet_id: Identifiant du projet à supprimer.
        """
        if projet_id not in self.projets:
            raise KeyError(f"Projet inconnu : {projet_id}")
        del self.projets[projet_id]
        self.sauvegarder()

    def get_projet(self, projet_id: str) -> Optional[Projet]:
        """Retourne un projet par son id, ou None s'il est inconnu."""
        return self.projets.get(projet_id)

    def projets_actifs(self) -> list[Projet]:
        """Retourne la liste des projets actifs, triés par date de début."""
        return sorted(
            [p for p in self.projets.values() if p.actif],
            key=lambda p: p.date_debut or date.min,
        )

    def calculer_bilan(
        self,
        projet_id: str,
        transactions: list[Transaction],
        moteur,
    ) -> BilanProjet:
        """
        Calcule le bilan comptable d'un projet.

        Parcourt les transactions et leurs splits pour cumuler
        recettes et dépenses affectées au projet.

        Args:
            projet_id:    Identifiant du projet.
            transactions: Toutes les transactions de l'exercice.
            moteur:       MoteurCategorisation (pour déterminer recette/dépense).

        Returns:
            BilanProjet avec recettes, dépenses et liste des transactions.

        Raises:
            KeyError: Si le projet n'existe pas.
        """
        if projet_id not in self.projets:
            raise KeyError(f"Projet inconnu : {projet_id}")

        projet = self.projets[projet_id]
        bilan = BilanProjet(projet=projet)

        for t in transactions:
            if t.est_splittee:
                for split in t.splits:
                    if split.projet_id != projet_id:
                        continue

                    cat = moteur.get_categorie(split.categorie_id)
                    if cat and cat.est_recette:
                        bilan.recettes += split.montant
                    else:
                        bilan.depenses += split.montant

                    if t not in bilan.transactions:
                        bilan.transactions.append(t)

            elif t.projet_id == projet_id and t.categorie_id:
                cat = moteur.get_categorie(t.categorie_id)
                if cat and cat.est_recette:
                    bilan.recettes += abs(t.montant)
                elif cat and cat.est_depense:
                    bilan.depenses += abs(t.montant)
                bilan.transactions.append(t)

        return bilan

    def calculer_tous_bilans(
        self, transactions: list[Transaction], moteur
    ) -> list[BilanProjet]:
        """
        Calcule le bilan de tous les projets actifs.

        Args:
            transactions: Toutes les transactions de l'exercice.
            moteur:       MoteurCategorisation.

        Returns:
            Liste de BilanProjet, triée par résultat décroissant.
        """
        bilans = [
            self.calculer_bilan(p.id, transactions, moteur)
            for p in self.projets.values()
        ]
        return sorted(bilans, key=lambda b: b.resultat, reverse=True)
