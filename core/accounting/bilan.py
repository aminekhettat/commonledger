"""
Bilan comptable simplifié — associations loi 1901.

Conforme au Plan Comptable des Associations (règlement ANC 2018-06)
et aux exigences de la comptabilité simplifiée pour petites structures.

Structure du bilan simplifié :

ACTIF                              PASSIF
─────────────────────────────      ─────────────────────────────
Immobilisations nettes             Fonds propres :
  + Matériel (valeur résiduelle)     + Fonds associatifs (capital)
  + Incorporel                       + Report à nouveau N-1
                                     + Résultat de l'exercice
Actif circulant :                  Fonds dédiés (subventions affectées)
  + Créances adhérents/clients     Dettes :
  + Autres créances                  + Emprunts & prêts reçus
                                     + Dettes fournisseurs
Disponibilités :                     + Autres dettes
  + Solde bancaire
  + Caisse
─────────────────────────────      ─────────────────────────────
TOTAL ACTIF                        TOTAL PASSIF

Équation fondamentale : Total Actif = Total Passif

Pour une petite association sans immobilisations ni dettes significatives,
le bilan se résume souvent à :
  Actif = Disponibilités (solde bancaire + caisse)
  Passif = Fonds associatifs + Report à nouveau + Résultat

Les classes Immobilisation et LigneBilan permettent d'étendre au besoin.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Immobilisations ───────────────────────────────────────────────────────────


@dataclass
class Immobilisation:
    """
    Une ligne de la table des immobilisations.

    Attributes:
        id:            Identifiant unique.
        designation:   Description du bien (ex: "Sono Yamaha MSR400").
        categorie:     Type (matériel_musical, matériel_informatique, mobilier…).
        date_achat:    Date d'acquisition.
        valeur_brute:  Coût d'acquisition hors taxes (€).
        duree_amort:   Durée d'amortissement en années (linéaire).
        taux_amort:    Taux annuel calculé = 1 / durée (ex: 0.20 pour 5 ans).
        amort_cumule:  Amortissement cumulé à la date de clôture.
        valeur_nette:  Valeur brute - amortissement cumulé.
        actif:         False si le bien a été cédé ou mis au rebut.
        notes:         Remarques libres.
    """

    id: str
    designation: str
    categorie: str = "matériel"
    date_achat: date | None = None
    valeur_brute: Decimal = Decimal("0")
    duree_amort: int = 5  # années — durée standard matériel associatif
    amort_cumule: Decimal = Decimal("0")
    actif: bool = True
    notes: str = ""

    @property
    def taux_amort(self) -> Decimal:
        """Taux d'amortissement linéaire annuel."""
        return Decimal("1") / Decimal(str(self.duree_amort)) if self.duree_amort else Decimal("0")

    @property
    def valeur_nette(self) -> Decimal:
        """Valeur nette comptable (VNC) = brut - amortissements cumulés."""
        return max(Decimal("0"), self.valeur_brute - self.amort_cumule)

    def calculer_amortissement_annuel(self) -> Decimal:
        """Dotation aux amortissements pour un exercice complet."""
        return (self.valeur_brute * self.taux_amort).quantize(Decimal("0.01"))

    def calculer_amort_a_date(self, date_cloture: date) -> Decimal:
        """
        Calcule l'amortissement cumulé à une date donnée.

        Méthode linéaire proratisée au mois de mise en service.
        """
        if not self.date_achat or self.valeur_brute == 0:
            return Decimal("0")
        annees_ecoulees = (date_cloture.year - self.date_achat.year) + (
            date_cloture.month - self.date_achat.month
        ) / 12
        amort = min(
            self.valeur_brute,
            (
                self.valeur_brute * Decimal(str(annees_ecoulees)) / Decimal(str(self.duree_amort))
            ).quantize(Decimal("0.01")),
        )
        return amort

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "designation": self.designation,
            "categorie": self.categorie,
            "date_achat": self.date_achat.isoformat() if self.date_achat else None,
            "valeur_brute": str(self.valeur_brute),
            "duree_amort": self.duree_amort,
            "amort_cumule": str(self.amort_cumule),
            "actif": self.actif,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Immobilisation:
        import uuid

        return cls(
            id=d.get("id", str(uuid.uuid4())[:8]),
            designation=d["designation"],
            categorie=d.get("categorie", "matériel"),
            date_achat=date.fromisoformat(d["date_achat"]) if d.get("date_achat") else None,
            valeur_brute=Decimal(d.get("valeur_brute", "0")),
            duree_amort=int(d.get("duree_amort", 5)),
            amort_cumule=Decimal(d.get("amort_cumule", "0")),
            actif=d.get("actif", True),
            notes=d.get("notes", ""),
        )


# ── Bilan simplifié ───────────────────────────────────────────────────────────


@dataclass
class LigneBilan:
    """Une ligne du tableau du bilan avec label, montant et éventuelle sous-décomposition."""

    label: str
    montant: Decimal = Decimal("0")
    sous_lignes: list[LigneBilan] = field(default_factory=list)
    gras: bool = False


@dataclass
class Bilan:
    """
    Bilan comptable simplifié de l'association.

    Toutes les données sont en Decimal pour éviter les erreurs d'arrondi.
    L'équilibre (total_actif == total_passif) est vérifié par la propriété
    `est_equilibre`.
    """

    # ── ACTIF ─────────────────────────────────────────────────────────────
    # Immobilisations nettes (calculées depuis la table des immobilisations)
    immobilisations_nettes: Decimal = Decimal("0")

    # Actif circulant
    creances_adherents: Decimal = Decimal("0")  # cotisations dues non encaissées
    autres_creances: Decimal = Decimal("0")  # autres créances

    # Disponibilités
    solde_bancaire: Decimal = Decimal("0")  # solde compte(s) bancaire(s)
    caisse: Decimal = Decimal("0")  # fonds de caisse

    # ── PASSIF ────────────────────────────────────────────────────────────
    # Fonds propres
    fonds_associatifs: Decimal = Decimal("0")  # capital social / fonds initiaux
    report_a_nouveau: Decimal = Decimal("0")  # résultat(s) exercice(s) antérieur(s)
    resultat_exercice: Decimal = Decimal("0")  # résultat net de l'exercice courant

    # Fonds dédiés
    subventions_affectees: Decimal = Decimal("0")  # subventions avec obligation d'emploi

    # Dettes
    emprunts_prets_recus: Decimal = Decimal("0")  # prêts reçus non remboursés
    dettes_fournisseurs: Decimal = Decimal("0")  # factures à payer
    autres_dettes: Decimal = Decimal("0")  # autres dettes

    # Métadonnées
    date_cloture: date | None = None
    annee: int = 0

    # ── Calculs ──────────────────────────────────────────────────────────

    @property
    def total_immobilisations(self) -> Decimal:
        return self.immobilisations_nettes

    @property
    def total_actif_circulant(self) -> Decimal:
        return self.creances_adherents + self.autres_creances

    @property
    def total_disponibilites(self) -> Decimal:
        return self.solde_bancaire + self.caisse

    @property
    def total_actif(self) -> Decimal:
        return self.total_immobilisations + self.total_actif_circulant + self.total_disponibilites

    @property
    def total_fonds_propres(self) -> Decimal:
        return self.fonds_associatifs + self.report_a_nouveau + self.resultat_exercice

    @property
    def total_dettes(self) -> Decimal:
        return self.emprunts_prets_recus + self.dettes_fournisseurs + self.autres_dettes

    @property
    def total_passif(self) -> Decimal:
        return self.total_fonds_propres + self.subventions_affectees + self.total_dettes

    @property
    def ecart_equilibre(self) -> Decimal:
        """Écart entre total actif et passif. Doit être 0,00 €."""
        return self.total_actif - self.total_passif

    @property
    def est_equilibre(self) -> bool:
        return abs(self.ecart_equilibre) < Decimal("0.02")

    # ── Lignes structurées pour le rapport ───────────────────────────────

    def lignes_actif(self) -> list[LigneBilan]:
        """Retourne la structure hiérarchique de l'actif pour le rapport."""
        lignes = []

        # Immobilisations
        if self.immobilisations_nettes > 0:
            lignes.append(
                LigneBilan("Immobilisations nettes", self.immobilisations_nettes, gras=False)
            )

        # Actif circulant
        if self.total_actif_circulant > 0:
            sous = []
            if self.creances_adherents > 0:
                sous.append(LigneBilan("Cotisations dues", self.creances_adherents))
            if self.autres_creances > 0:
                sous.append(LigneBilan("Autres créances", self.autres_creances))
            lignes.append(
                LigneBilan("Actif circulant", self.total_actif_circulant, sous_lignes=sous)
            )

        # Disponibilités
        sous_dispo = []
        sous_dispo.append(LigneBilan("Compte bancaire", self.solde_bancaire))
        if self.caisse > 0:
            sous_dispo.append(LigneBilan("Caisse", self.caisse))
        lignes.append(
            LigneBilan("Disponibilités", self.total_disponibilites, sous_lignes=sous_dispo)
        )

        lignes.append(LigneBilan("TOTAL ACTIF", self.total_actif, gras=True))
        return lignes

    def lignes_passif(self) -> list[LigneBilan]:
        """Retourne la structure hiérarchique du passif pour le rapport."""
        lignes = []

        # Fonds propres
        sous_fp = [
            LigneBilan("Fonds associatifs", self.fonds_associatifs),
            LigneBilan("Report à nouveau", self.report_a_nouveau),
            LigneBilan(
                f"Résultat de l'exercice {self.annee}",
                self.resultat_exercice,
            ),
        ]
        lignes.append(LigneBilan("Fonds propres", self.total_fonds_propres, sous_lignes=sous_fp))

        # Fonds dédiés
        if self.subventions_affectees > 0:
            lignes.append(
                LigneBilan("Subventions affectées (fonds dédiés)", self.subventions_affectees)
            )

        # Dettes
        if self.total_dettes > 0:
            sous_det = []
            if self.emprunts_prets_recus > 0:
                sous_det.append(LigneBilan("Emprunts / prêts reçus", self.emprunts_prets_recus))
            if self.dettes_fournisseurs > 0:
                sous_det.append(LigneBilan("Dettes fournisseurs", self.dettes_fournisseurs))
            if self.autres_dettes > 0:
                sous_det.append(LigneBilan("Autres dettes", self.autres_dettes))
            lignes.append(LigneBilan("Dettes", self.total_dettes, sous_lignes=sous_det))

        lignes.append(LigneBilan("TOTAL PASSIF", self.total_passif, gras=True))
        return lignes


class GestionnaireBilan:
    """
    Construit et persiste le bilan de l'exercice.

    Calcule automatiquement les montants depuis les données disponibles
    (transactions importées, table des immobilisations, paramètres saisis).
    """

    def __init__(self, chemin_data: str):
        self.chemin = Path(chemin_data)
        self.immobilisations: list[Immobilisation] = []
        self._charger()

    def _charger(self) -> None:
        chemin_immo = self.chemin / "immobilisations.json"
        if chemin_immo.exists():
            with open(chemin_immo, encoding="utf-8") as f:
                data = json.load(f)
            self.immobilisations = [
                Immobilisation.from_dict(d) for d in data.get("immobilisations", [])
            ]

    def sauvegarder(self) -> None:
        self.chemin.mkdir(parents=True, exist_ok=True)
        chemin_immo = self.chemin / "immobilisations.json"
        data = {"immobilisations": [i.to_dict() for i in self.immobilisations]}
        with open(chemin_immo, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def ajouter_immobilisation(self, immo: Immobilisation) -> None:
        self.immobilisations.append(immo)
        self.sauvegarder()

    def supprimer_immobilisation(self, immo_id: str) -> None:
        self.immobilisations = [i for i in self.immobilisations if i.id != immo_id]
        self.sauvegarder()

    def dotation_annuelle(self) -> Decimal:
        """Dotation totale aux amortissements de l'exercice."""
        return sum(i.calculer_amortissement_annuel() for i in self.immobilisations if i.actif)

    def immobilisations_nettes(self, date_cloture: date | None = None) -> Decimal:
        """Valeur nette comptable totale des immobilisations."""
        d = date_cloture or date.today()
        total = Decimal("0")
        for immo in self.immobilisations:
            if immo.actif:
                amort = immo.calculer_amort_a_date(d)
                total += max(Decimal("0"), immo.valeur_brute - amort)
        return total.quantize(Decimal("0.01"))

    def construire_bilan(
        self,
        annee: int,
        compte_resultat,  # CompteResultat
        solde_bancaire: Decimal,
        caisse: Decimal = Decimal("0"),
        fonds_associatifs: Decimal = Decimal("0"),
        report_a_nouveau: Decimal = Decimal("0"),
        creances_adherents: Decimal = Decimal("0"),
        autres_creances: Decimal = Decimal("0"),
        subventions_affectees: Decimal = Decimal("0"),
        emprunts_prets_recus: Decimal = Decimal("0"),
        dettes_fournisseurs: Decimal = Decimal("0"),
        autres_dettes: Decimal = Decimal("0"),
    ) -> Bilan:
        """
        Construit le bilan de clôture de l'exercice.

        Args:
            annee:              Année de l'exercice.
            compte_resultat:    CompteResultat calculé.
            solde_bancaire:     Solde bancaire à la clôture (issu des relevés).
            caisse:             Fonds de caisse en espèces.
            fonds_associatifs:  Capital accumulé des exercices antérieurs.
            report_a_nouveau:   Résultat net cumulé des exercices précédents
                                (avant celui-ci).
            …                   Autres postes.

        Returns:
            Bilan équilibré (si les données sont cohérentes).
        """
        date_cloture = date(annee, 12, 31)

        return Bilan(
            annee=annee,
            date_cloture=date_cloture,
            # Actif
            immobilisations_nettes=self.immobilisations_nettes(date_cloture),
            creances_adherents=creances_adherents,
            autres_creances=autres_creances,
            solde_bancaire=solde_bancaire,
            caisse=caisse,
            # Passif
            fonds_associatifs=fonds_associatifs,
            report_a_nouveau=report_a_nouveau,
            resultat_exercice=compte_resultat.resultat_net,
            subventions_affectees=subventions_affectees,
            emprunts_prets_recus=emprunts_prets_recus,
            dettes_fournisseurs=dettes_fournisseurs,
            autres_dettes=autres_dettes,
        )
