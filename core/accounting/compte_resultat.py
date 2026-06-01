"""
Calcul du compte de résultat.

Le compte de résultat présente pour une période donnée :
  - Le total des recettes par catégorie
  - Le total des dépenses par catégorie
  - Le résultat net (excédent ou déficit)
  - La répartition en pourcentage de chaque poste

Il prend en compte les transactions directement catégorisées
ET les transactions éclatées (splits).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ..categorizer.rules_engine import Categorie, MoteurCategorisation
from ..parser.models import Transaction


@dataclass
class LigneResultat:
    """
    Une ligne dans le compte de résultat (une catégorie).

    Attributes:
        categorie:      La catégorie correspondante.
        montant:        Montant total (toujours positif).
        pourcentage:    Part en % du total recettes ou dépenses.
        nb_transactions:Nombre de transactions ou splits concernés.
        transactions:   Liste des transactions contribuant à cette ligne.
    """

    categorie: Categorie
    montant: Decimal = Decimal("0")
    pourcentage: float = 0.0
    nb_transactions: int = 0
    transactions: list[Transaction] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.categorie.label

    @property
    def couleur(self) -> str:
        return self.categorie.couleur_graphique


@dataclass
class AlerteCoherence:
    """
    Alerte signalant une incohérence entre le solde calculé et le solde réel.

    Attributes:
        date_releve:   Date du relevé concerné.
        solde_calcule: Solde calculé par cumul des transactions.
        solde_releve:  Solde indiqué sur le relevé bancaire.
        ecart:         Différence (solde_calcule - solde_releve).
    """

    date_releve: date
    solde_calcule: Decimal
    solde_releve: Decimal
    ecart: Decimal


class CompteResultat:
    """
    Calcule le compte de résultat pour une liste de transactions et une période.

    Prend en charge :
    - Les transactions simples (catégorie unique)
    - Les transactions éclatées (splits multi-catégories)
    - La comptabilité analytique par projet (si projet_id fourni)
    - La génération d'alertes de cohérence avec les soldes bancaires

    Exemple::

        cr = CompteResultat(moteur_cat, transactions, date(2024,1,1), date(2024,12,31))
        print(f"Résultat : {cr.resultat_net}€")
        for ligne in cr.lignes_recettes:
            print(f"  {ligne.label}: {ligne.montant}€ ({ligne.pourcentage:.1f}%)")
    """

    def __init__(
        self,
        moteur: MoteurCategorisation,
        transactions: list[Transaction],
        date_debut: date,
        date_fin: date,
        projet_id: str | None = None,
        solde_initial: Decimal | None = None,
    ):
        """
        Initialise et calcule le compte de résultat.

        Args:
            moteur:        Moteur de catégorisation (pour accéder aux libellés).
            transactions:  Toutes les transactions de l'exercice.
            date_debut:    Premier jour de la période analysée.
            date_fin:      Dernier jour de la période analysée.
            projet_id:     Si fourni, filtre uniquement les transactions de ce projet.
            solde_initial: Solde bancaire au premier jour de la période (pour la trésorerie).
        """
        self.moteur = moteur
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.projet_id = projet_id
        self.solde_initial = solde_initial or Decimal("0")

        # Filtrer par période et projet
        self._transactions_periode = self._filtrer(transactions)

        # Calculer
        self.lignes_recettes: list[LigneResultat] = []
        self.lignes_depenses: list[LigneResultat] = []
        self.transactions_non_categorisees: list[Transaction] = []
        self.alertes_coherence: list[AlerteCoherence] = []

        self._calculer()

    def _filtrer(self, transactions: list[Transaction]) -> list[Transaction]:
        """Filtre les transactions par période et optionnellement par projet."""
        result = []
        for t in transactions:
            if not (self.date_debut <= t.date <= self.date_fin):
                continue

            if self.projet_id:
                # Inclure si la transaction ou l'un de ses splits correspond au projet
                if t.projet_id == self.projet_id or any(
                    s.projet_id == self.projet_id for s in t.splits
                ):
                    result.append(t)
            else:
                result.append(t)

        return sorted(result, key=lambda t: t.date)

    def _calculer(self) -> None:
        """Effectue tous les calculs du compte de résultat."""
        # Accumulateurs par catégorie
        recettes_par_cat: dict[str, list[tuple[Decimal, Transaction]]] = {}
        depenses_par_cat: dict[str, list[tuple[Decimal, Transaction]]] = {}

        for transaction in self._transactions_periode:
            if not transaction.est_categorisee:
                self.transactions_non_categorisees.append(transaction)
                continue

            if transaction.est_splittee:
                self._traiter_transaction_splittee(transaction, recettes_par_cat, depenses_par_cat)
            else:
                self._traiter_transaction_simple(transaction, recettes_par_cat, depenses_par_cat)

        # Construire les lignes du compte de résultat
        self.lignes_recettes = self._construire_lignes(recettes_par_cat, "recettes")
        self.lignes_depenses = self._construire_lignes(depenses_par_cat, "depenses")

        # Calculer les pourcentages
        self._calculer_pourcentages()

    def _traiter_transaction_simple(
        self,
        transaction: Transaction,
        recettes: dict,
        depenses: dict,
    ) -> None:
        """Ajoute une transaction simple (non éclatée) aux accumulateurs."""
        cat_id = transaction.categorie_id
        montant = abs(transaction.montant)

        if transaction.est_credit:
            recettes.setdefault(cat_id, []).append((montant, transaction))
        else:
            depenses.setdefault(cat_id, []).append((montant, transaction))

    def _traiter_transaction_splittee(
        self,
        transaction: Transaction,
        recettes: dict,
        depenses: dict,
    ) -> None:
        """Répartit les splits d'une transaction dans les accumulateurs."""
        for split in transaction.splits:
            # Filtrer par projet si demandé
            if self.projet_id and split.projet_id != self.projet_id:
                continue

            cat_id = split.categorie_id
            montant = abs(split.montant)

            cat = self.moteur.get_categorie(cat_id)
            if cat and cat.est_recette:
                recettes.setdefault(cat_id, []).append((montant, transaction))
            else:
                depenses.setdefault(cat_id, []).append((montant, transaction))

    def _construire_lignes(
        self,
        accumulateurs: dict[str, list[tuple[Decimal, Transaction]]],
        type_cat: str,
    ) -> list[LigneResultat]:
        """Construit la liste des LigneResultat triées par montant décroissant."""
        lignes = []
        for cat_id, items in accumulateurs.items():
            cat = self.moteur.get_categorie(cat_id)
            if not cat:
                # Catégorie inconnue (supprimée depuis la config) : créer une entrée générique
                from ..categorizer.rules_engine import Categorie

                cat = Categorie(id=cat_id, label=f"[{cat_id}]", type=type_cat)

            total = sum(m for m, _ in items)
            transactions = [t for _, t in items]

            # Dédupliquer les transactions (une transaction splittée peut apparaître plusieurs fois)
            vues = set()
            transactions_uniques = []
            for t in transactions:
                if t.id_unique not in vues:
                    vues.add(t.id_unique)
                    transactions_uniques.append(t)

            lignes.append(
                LigneResultat(
                    categorie=cat,
                    montant=total,
                    nb_transactions=len(transactions),
                    transactions=transactions_uniques,
                )
            )

        return sorted(lignes, key=lambda l: l.montant, reverse=True)

    def _calculer_pourcentages(self) -> None:
        """Calcule les pourcentages pour chaque ligne."""
        total_r = self.total_recettes
        total_d = self.total_depenses

        for ligne in self.lignes_recettes:
            ligne.pourcentage = float(ligne.montant / total_r * 100) if total_r else 0.0
        for ligne in self.lignes_depenses:
            ligne.pourcentage = float(ligne.montant / total_d * 100) if total_d else 0.0

    @property
    def total_recettes(self) -> Decimal:
        """Total des recettes de la période."""
        return sum((l.montant for l in self.lignes_recettes), Decimal("0"))

    @property
    def total_depenses(self) -> Decimal:
        """Total des dépenses de la période."""
        return sum((l.montant for l in self.lignes_depenses), Decimal("0"))

    @property
    def resultat_net(self) -> Decimal:
        """Résultat net = Recettes - Dépenses. Positif = excédent, négatif = déficit."""
        return self.total_recettes - self.total_depenses

    @property
    def est_excedentaire(self) -> bool:
        """True si le résultat est positif (excédent)."""
        return self.resultat_net >= 0

    @property
    def solde_final(self) -> Decimal:
        """Solde bancaire estimé en fin de période (solde initial + résultat)."""
        return self.solde_initial + self.resultat_net

    def evolution_mensuelle(self) -> list[dict]:
        """
        Calcule les totaux recettes/dépenses mois par mois sur la période.

        Returns:
            Liste de dictionnaires : [{mois, annee, recettes, depenses, resultat}]
        """
        from collections import defaultdict

        mois_recettes: dict[tuple, Decimal] = defaultdict(Decimal)
        mois_depenses: dict[tuple, Decimal] = defaultdict(Decimal)

        for t in self._transactions_periode:
            cle = (t.date.year, t.date.month)

            if t.est_splittee:
                for split in t.splits:
                    cat = self.moteur.get_categorie(split.categorie_id)
                    if cat and cat.est_recette:
                        mois_recettes[cle] += split.montant
                    else:
                        mois_depenses[cle] += split.montant
            elif t.categorie_id:
                cat = self.moteur.get_categorie(t.categorie_id)
                if cat and cat.est_recette:
                    mois_recettes[cle] += abs(t.montant)
                elif cat and cat.est_depense:
                    mois_depenses[cle] += abs(t.montant)

        # Construire la série complète mois par mois
        resultats = []
        annee = self.date_debut.year
        mois_debut = self.date_debut.month
        mois_fin = self.date_fin.month if self.date_fin.year == annee else 12

        for mois in range(mois_debut, mois_fin + 1):
            cle = (annee, mois)
            r = mois_recettes.get(cle, Decimal("0"))
            d = mois_depenses.get(cle, Decimal("0"))
            resultats.append(
                {
                    "annee": annee,
                    "mois": mois,
                    "recettes": r,
                    "depenses": d,
                    "resultat": r - d,
                }
            )

        return resultats

    def verifier_coherence_soldes(self, releves_info: list) -> list[AlerteCoherence]:
        """
        Vérifie que les soldes calculés correspondent aux soldes des relevés.

        Args:
            releves_info: Liste de ReleveInfo avec solde_fin renseigné.

        Returns:
            Liste d'alertes pour chaque écart détecté.
        """
        alertes = []
        solde_courant = self.solde_initial

        transactions_triees = sorted(self._transactions_periode, key=lambda t: t.date)

        for releve in releves_info:
            if not releve.solde_fin or not releve.periode_fin:
                continue

            # Cumuler les transactions jusqu'à la fin de ce relevé
            for t in transactions_triees:
                if t.date <= releve.periode_fin:
                    solde_courant += t.montant

            ecart = solde_courant - releve.solde_fin
            if abs(ecart) > Decimal("0.01"):
                alertes.append(
                    AlerteCoherence(
                        date_releve=releve.periode_fin,
                        solde_calcule=solde_courant,
                        solde_releve=releve.solde_fin,
                        ecart=ecart,
                    )
                )

        self.alertes_coherence = alertes
        return alertes
