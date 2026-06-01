"""
Moteur de catégorisation des transactions bancaires.

Ce module applique des règles basées sur les mots-clés du libellé
pour catégoriser automatiquement les transactions. Il gère également
l'éclatement (split) de transactions multi-catégories comme les
virements HelloAsso.

Architecture des règles :
    Les règles sont définies dans categories.json. Chaque catégorie
    possède une liste de mots-clés. Le moteur teste chaque libellé
    contre les mots-clés de toutes les catégories et retient la
    correspondance avec le score le plus élevé.

Priorité de catégorisation :
    1. Catégorie verrouillée manuellement (intouchable)
    2. Transaction éclatée en splits (prend le dessus)
    3. Catégorisation automatique par mots-clés
    4. Non catégorisé (à traiter manuellement)
"""

import json
import logging
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from ..parser.models import Transaction, TransactionSplit

logger = logging.getLogger(__name__)


def _normaliser(texte: str) -> str:
    """
    Normalise un texte pour la comparaison : majuscules, sans accents, sans ponctuation.

    Args:
        texte: Texte à normaliser.

    Returns:
        Texte normalisé.
    """
    texte = texte.upper()
    # Supprimer les accents
    texte = "".join(
        c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn"
    )
    # Remplacer ponctuation par espace
    texte = "".join(c if c.isalnum() else " " for c in texte)
    return texte


@dataclass
class Categorie:
    """
    Représente une catégorie comptable (recette ou dépense).

    Attributes:
        id:               Identifiant unique (ex: "cotisations").
        label:            Libellé affiché (ex: "Cotisations membres").
        description:      Description longue.
        type:             "recettes" ou "depenses".
        mots_cles:        Liste de mots-clés pour la reconnaissance automatique.
        split_autorise:   True si la transaction peut être éclatée.
        details_requis:   True si des informations complémentaires sont demandées.
        champs_details:   Noms des champs à renseigner si details_requis.
        couleur_graphique:Couleur hexadécimale pour les graphiques.
    """

    id: str
    label: str
    description: str = ""
    type: str = "recettes"
    mots_cles: list[str] = field(default_factory=list)
    split_autorise: bool = False
    details_requis: bool = False
    champs_details: list[str] = field(default_factory=list)
    couleur_graphique: str = "#9E9E9E"

    @property
    def est_recette(self) -> bool:
        return self.type == "recettes"

    @property
    def est_depense(self) -> bool:
        return self.type == "depenses"


@dataclass
class ResultatCategorisation:
    """
    Résultat de la tentative de catégorisation d'une transaction.

    Attributes:
        categorie_id:   Identifiant de la catégorie trouvée (None = aucune).
        score:          Score de confiance entre 0.0 et 1.0.
        mot_cle_match:  Mot-clé qui a déclenché la reconnaissance.
        automatique:    True si catégorisé automatiquement, False si manuel.
    """

    categorie_id: str | None = None
    score: float = 0.0
    mot_cle_match: str = ""
    automatique: bool = True


# Marqueurs spéciaux HelloAsso pour proposer le split automatiquement
_MARQUEURS_HELLOASSO = ["HELLOASSO", "HELLO ASSO", "HA-"]


class MoteurCategorisation:
    """
    Moteur de catégorisation automatique et manuelle des transactions.

    Charge les catégories depuis le fichier JSON de configuration
    et applique les règles de correspondance par mots-clés.

    Exemple d'utilisation::

        moteur = MoteurCategorisation("config/categories.json")
        resultat = moteur.categoriser(transaction)
        if resultat.score > 0.7:
            transaction.categorie_id = resultat.categorie_id
        else:
            # Demander confirmation à l'utilisateur
            pass
    """

    def __init__(self, chemin_config: str):
        """
        Charge les catégories depuis le fichier de configuration.

        Args:
            chemin_config: Chemin vers categories.json.

        Raises:
            FileNotFoundError: Si le fichier de configuration est absent.
            json.JSONDecodeError: Si le fichier JSON est malformé.
        """
        self.chemin_config = Path(chemin_config)
        self.categories: dict[str, Categorie] = {}
        self._charger()

    def _charger(self) -> None:
        """Charge et indexe les catégories depuis le fichier JSON."""
        if not self.chemin_config.exists():
            raise FileNotFoundError(f"Config catégories introuvable : {self.chemin_config}")

        with open(self.chemin_config, encoding="utf-8") as f:
            data = json.load(f)

        self.categories.clear()

        for type_cat in ("recettes", "depenses"):
            for cat_data in data.get(type_cat, []):
                cat = Categorie(
                    id=cat_data["id"],
                    label=cat_data["label"],
                    description=cat_data.get("description", ""),
                    type=type_cat,
                    mots_cles=[_normaliser(mk) for mk in cat_data.get("mots_cles", [])],
                    split_autorise=cat_data.get("split_autorise", False),
                    details_requis=cat_data.get("details_requis", False),
                    champs_details=cat_data.get("champs_details", []),
                    couleur_graphique=cat_data.get("couleur_graphique", "#9E9E9E"),
                )
                self.categories[cat.id] = cat

        logger.info(f"Chargé {len(self.categories)} catégories depuis {self.chemin_config.name}")

    def recharger(self) -> None:
        """Recharge les catégories (utile après modification dans l'UI)."""
        self._charger()

    def sauvegarder(self) -> None:
        """Sauvegarde les catégories modifiées dans le fichier JSON."""
        data = {"recettes": [], "depenses": []}

        for cat in self.categories.values():
            cat_dict = {
                "id": cat.id,
                "label": cat.label,
                "description": cat.description,
                "mots_cles": cat.mots_cles,
                "split_autorise": cat.split_autorise,
                "couleur_graphique": cat.couleur_graphique,
            }
            if cat.details_requis:
                cat_dict["details_requis"] = True
                cat_dict["champs_details"] = cat.champs_details

            data[cat.type].append(cat_dict)

        with open(self.chemin_config, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def categoriser(self, transaction: Transaction) -> ResultatCategorisation:
        """
        Tente de catégoriser automatiquement une transaction.

        L'algorithme cherche les mots-clés de chaque catégorie dans le
        libellé normalisé. Il favorise les correspondances les plus longues
        (mots-clés plus spécifiques ont priorité).

        Args:
            transaction: La transaction à catégoriser.

        Returns:
            ResultatCategorisation avec la meilleure correspondance trouvée.
        """
        # Respecter les catégorisations verrouillées
        if transaction.verrouille and transaction.categorie_id:
            return ResultatCategorisation(
                categorie_id=transaction.categorie_id,
                score=1.0,
                automatique=False,
            )

        libelle_norm = _normaliser(transaction.libelle)
        est_credit = transaction.montant > 0

        meilleur_score = 0.0
        meilleure_cat = None
        meilleur_mot = ""

        for cat_id, cat in self.categories.items():
            # Filtrer par type : recettes pour les crédits, dépenses pour les débits
            if est_credit and not cat.est_recette:
                continue
            if not est_credit and not cat.est_depense:
                continue

            for mot_cle in cat.mots_cles:
                if mot_cle in libelle_norm:
                    # Score proportionnel à la longueur du mot-clé (plus spécifique = meilleur)
                    score = len(mot_cle) / max(len(libelle_norm), 1)
                    score = min(score * 3, 0.95)  # Plafonner à 0.95 (jamais 1.0 pour auto)

                    if score > meilleur_score:
                        meilleur_score = score
                        meilleure_cat = cat_id
                        meilleur_mot = mot_cle

        return ResultatCategorisation(
            categorie_id=meilleure_cat,
            score=meilleur_score,
            mot_cle_match=meilleur_mot,
            automatique=True,
        )

    def categoriser_lot(self, transactions: list[Transaction], seuil_auto: float = 0.3) -> dict:
        """
        Catégorise un lot de transactions.

        Les transactions avec un score supérieur au seuil reçoivent
        automatiquement leur catégorie. Les autres sont marquées
        comme "à traiter".

        Args:
            transactions:  Liste de transactions à catégoriser.
            seuil_auto:    Score minimum pour accepter la catégorisation auto.

        Returns:
            Dictionnaire avec statistiques : {
                "auto": int,       # Catégorisées automatiquement
                "a_traiter": int,  # À traiter manuellement
                "deja_faites": int # Déjà catégorisées (non modifiées)
            }
        """
        stats = {"auto": 0, "a_traiter": 0, "deja_faites": 0}

        for t in transactions:
            if t.verrouille or t.est_categorisee:
                stats["deja_faites"] += 1
                continue

            resultat = self.categoriser(t)

            if resultat.categorie_id and resultat.score >= seuil_auto:
                t.categorie_id = resultat.categorie_id
                stats["auto"] += 1
            else:
                stats["a_traiter"] += 1

        return stats

    def est_helloasso(self, transaction: Transaction) -> bool:
        """
        Détecte si une transaction provient de HelloAsso.

        Ces transactions méritent souvent un split cotisations/dons.

        Args:
            transaction: La transaction à tester.

        Returns:
            True si le libellé indique un virement HelloAsso.
        """
        libelle_norm = _normaliser(transaction.libelle)
        return any(m in libelle_norm for m in [_normaliser(m) for m in _MARQUEURS_HELLOASSO])

    def creer_split(
        self,
        transaction: Transaction,
        ventilations: list[tuple[str, Decimal, str | None]],
    ) -> None:
        """
        Éclate une transaction en sous-ventilations.

        Args:
            transaction:  La transaction à éclater.
            ventilations: Liste de tuples (categorie_id, montant, projet_id).
                          La somme des montants doit égaler abs(transaction.montant).

        Raises:
            ValueError: Si la somme des ventilations ne correspond pas au total.
        """
        total_splits = sum(abs(m) for _, m, _ in ventilations)
        total_transaction = abs(transaction.montant)

        # Tolérance de 1 centime pour les arrondis
        if abs(total_splits - total_transaction) > Decimal("0.01"):
            raise ValueError(
                f"Somme des splits ({total_splits}€) ≠ montant transaction ({total_transaction}€)"
            )

        transaction.splits = [
            TransactionSplit(
                montant=abs(montant),
                categorie_id=cat_id,
                projet_id=projet_id,
            )
            for cat_id, montant, projet_id in ventilations
        ]
        # Retirer la catégorie directe puisque la transaction est éclatée
        transaction.categorie_id = None
        transaction.verrouille = True

    def categories_par_type(self, type_cat: str) -> list[Categorie]:
        """
        Retourne les catégories d'un type donné.

        Args:
            type_cat: "recettes" ou "depenses".

        Returns:
            Liste de Categorie triée par label.
        """
        return sorted(
            [c for c in self.categories.values() if c.type == type_cat],
            key=lambda c: c.label,
        )

    def ajouter_categorie(self, categorie: Categorie) -> None:
        """
        Ajoute ou met à jour une catégorie dans le catalogue.

        Args:
            categorie: La catégorie à ajouter/modifier.

        Raises:
            ValueError: Si l'id est vide ou déjà utilisé avec un type différent.
        """
        if not categorie.id:
            raise ValueError("L'identifiant de catégorie ne peut pas être vide.")

        if categorie.id in self.categories:
            existante = self.categories[categorie.id]
            if existante.type != categorie.type:
                raise ValueError(
                    f"La catégorie '{categorie.id}' existe déjà avec le type '{existante.type}'."
                )

        self.categories[categorie.id] = categorie
        self.sauvegarder()

    def supprimer_categorie(self, cat_id: str) -> None:
        """
        Supprime une catégorie du catalogue.

        Attention : les transactions existantes avec cette catégorie
        deviennent non catégorisées. À appeler avec précaution.

        Args:
            cat_id: Identifiant de la catégorie à supprimer.

        Raises:
            KeyError: Si la catégorie n'existe pas.
        """
        if cat_id not in self.categories:
            raise KeyError(f"Catégorie inconnue : {cat_id}")
        del self.categories[cat_id]
        self.sauvegarder()

    def get_categorie(self, cat_id: str) -> Categorie | None:
        """Retourne une catégorie par son id, ou None si inconnue."""
        return self.categories.get(cat_id)
