"""
Modèles de données pour le module parser.

Ce module définit les structures de données partagées entre le parseur,
le moteur de catégorisation et les modules comptables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


class ParseError(Exception):
    """Levée quand un fichier PDF ne peut pas être parsé correctement."""

    pass


@dataclass
class Transaction:
    """
    Représente une transaction bancaire extraite d'un relevé.

    Attributes:
        date:            Date de la transaction.
        libelle:         Libellé brut tel qu'il apparaît sur le relevé.
        montant:         Montant en euros. Positif = crédit, négatif = débit.
        solde_apres:     Solde du compte après cette transaction (si disponible).
        source_fichier:  Nom du fichier PDF d'origine.
        id_unique:       Identifiant unique généré pour éviter les doublons.
        categorie_id:    Identifiant de la catégorie assignée (None = non catégorisé).
        projet_id:       Identifiant du projet analytique associé (None = aucun).
        memo:            Note libre saisie par l'utilisateur.
        splits:          Liste de sous-ventilations si la transaction est éclatée.
        details:         Informations complémentaires (ex. nom du prestataire).
        verrouille:      True si la catégorisation a été validée manuellement.
    """

    date: date
    libelle: str
    montant: Decimal
    solde_apres: Decimal | None = None
    source_fichier: str = ""
    id_unique: str = ""
    categorie_id: str | None = None
    projet_id: str | None = None
    memo: str = ""
    splits: list[TransactionSplit] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    verrouille: bool = False

    def __post_init__(self):
        """
        Génère l'id_unique si absent.

        Utilise MD5 (déterministe entre sessions Python) du libellé complet
        pour distinguer deux transactions de même date/montant mais libellés
        différents (ex : deux prélèvements PayPal le même jour, REF distincts).

        Note : hash() Python n'est PAS utilisé car il change à chaque session
        (PYTHONHASHSEED aléatoire depuis Python 3.3).
        """
        if not self.id_unique:
            import hashlib

            # MD5 utilisé uniquement pour la déduplication (pas de sécurité) — nosec B324
            h = hashlib.md5(  # nosec B324
                self.libelle.encode("utf-8", errors="replace"),
                usedforsecurity=False,
            ).hexdigest()[:12]
            self.id_unique = f"{self.date.isoformat()}_{self.montant}_{h}"

    @property
    def est_credit(self) -> bool:
        """Retourne True si la transaction est un crédit (recette)."""
        return self.montant > 0

    @property
    def est_debit(self) -> bool:
        """Retourne True si la transaction est un débit (dépense)."""
        return self.montant < 0

    @property
    def est_splittee(self) -> bool:
        """Retourne True si la transaction a été éclatée en sous-catégories."""
        return len(self.splits) > 0

    @property
    def est_categorisee(self) -> bool:
        """Retourne True si la transaction a une catégorie ou des splits."""
        return self.categorie_id is not None or self.est_splittee

    def to_dict(self) -> dict:
        """Sérialise la transaction en dictionnaire pour la persistance JSON."""
        return {
            "date": self.date.isoformat(),
            "libelle": self.libelle,
            "montant": str(self.montant),
            "solde_apres": str(self.solde_apres) if self.solde_apres else None,
            "source_fichier": self.source_fichier,
            "id_unique": self.id_unique,
            "categorie_id": self.categorie_id,
            "projet_id": self.projet_id,
            "memo": self.memo,
            "splits": [s.to_dict() for s in self.splits],
            "details": self.details,
            "verrouille": self.verrouille,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Transaction:
        """Recrée une Transaction depuis un dictionnaire JSON."""
        from datetime import date as date_type

        t = cls(
            date=date_type.fromisoformat(d["date"]),
            libelle=d["libelle"],
            montant=Decimal(d["montant"]),
            solde_apres=Decimal(d["solde_apres"]) if d.get("solde_apres") else None,
            source_fichier=d.get("source_fichier", ""),
            id_unique=d.get("id_unique", ""),
            categorie_id=d.get("categorie_id"),
            projet_id=d.get("projet_id"),
            memo=d.get("memo", ""),
            splits=[TransactionSplit.from_dict(s) for s in d.get("splits", [])],
            details=d.get("details", {}),
            verrouille=d.get("verrouille", False),
        )
        return t


@dataclass
class TransactionSplit:
    """
    Sous-ventilation d'une transaction éclatée.

    Exemple : un virement HelloAsso de 350€ peut être éclaté en
    - 280€ → cotisations
    - 70€  → dons

    Attributes:
        montant:      Montant de cette part (toujours positif, le signe
                      vient de la transaction parente).
        categorie_id: Catégorie affectée à cette part.
        projet_id:    Projet analytique optionnel.
        memo:         Note libre sur cette part.
        details:      Informations complémentaires (ex. nom prestataire).
    """

    montant: Decimal
    categorie_id: str
    projet_id: str | None = None
    memo: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "montant": str(self.montant),
            "categorie_id": self.categorie_id,
            "projet_id": self.projet_id,
            "memo": self.memo,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TransactionSplit:
        return cls(
            montant=Decimal(d["montant"]),
            categorie_id=d["categorie_id"],
            projet_id=d.get("projet_id"),
            memo=d.get("memo", ""),
            details=d.get("details", {}),
        )


@dataclass
class ReleveInfo:
    """
    Métadonnées extraites d'un relevé bancaire.

    Attributes:
        fichier:          Chemin vers le fichier PDF source.
        periode_debut:    Premier jour de la période couverte par ce relevé.
        periode_fin:      Dernier jour de la période couverte par ce relevé.
        solde_debut:      Solde d'ouverture (« Ancien solde »).
        solde_fin:        Solde de clôture (« Nouveau solde »).
        numero_compte:    Numéro de compte bancaire court (ex : 6804150W020).
        iban_pdf:         IBAN tel qu'il apparaît dans le PDF (normalisé sans espaces).
        bic_pdf:          BIC tel qu'il apparaît dans le PDF.
        nom_asso_pdf:     Nom de la structure tel qu'il apparaît dans le PDF.
        transactions:     Liste des transactions extraites.
        valide:           True si le relevé a passé toutes les validations.
        raisons_rejet:    Liste des motifs de rejet (si valide=False).
    """

    fichier: str
    periode_debut: date | None = None
    periode_fin: date | None = None
    solde_debut: Decimal | None = None
    solde_fin: Decimal | None = None
    numero_compte: str = ""
    iban_pdf: str = ""
    bic_pdf: str = ""
    nom_asso_pdf: str = ""
    transactions: list[Transaction] = field(default_factory=list)
    valide: bool = False
    raisons_rejet: list[str] = field(default_factory=list)
