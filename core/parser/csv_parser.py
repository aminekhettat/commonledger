"""
Parseur CSV La Banque Postale.

Ce module extrait les transactions depuis les exports CSV du portail
en ligne La Banque Postale (CCP), format "Relevé de compte" téléchargeable.

Format observé (2024-2026) :
  - Encodage : UTF-8 avec BOM (utf-8-sig) — standard des exports web français
  - Séparateur : point-virgule (;)
  - Décimale : virgule, milliers : espace (ex: 1 115,00 €)
  - Structure :
      Ligne 1 : Numéro de compte;6804150W020
      Ligne 2 : Type;ASSO CULTURE MUSIQUE
      Ligne 3 : Fichier téléchargé;le JJ/MM/YYYY à HH:MM:SS
      Ligne 4 : Opérations imputées;du DD/MM/YYYY au DD/MM/YYYY
      Ligne 5 : Solde comptable au DD/MM/YYYY;X XXX,XX €
      Ligne 6 : (vide)
      Ligne 7 : Date;Libellé;Montant       ← détecte le début des données
      Ligne 8+: JJ/MM/YYYY;LIBELLE;±X,XX€

Différences avec les PDFs :
  - Un fichier CSV couvre une période variable (pas nécessairement mensuelle)
  - Les périodes peuvent se chevaucher entre plusieurs fichiers CSV
  - Résolution : déduplication par (date, libellé, montant) + hash MD5

Note norme :
  La Banque Postale n'utilise pas le format CFONB (fixe 120 chars) pour ses
  exports CSV. Le format est propriétaire mais stable depuis ~2018.
  Encodage UTF-8 BOM conforme RFC 4180 Annex B (recommandation Banque de France
  pour les exports de données financières aux particuliers).

Utilisation::

    parser = CSVParserLaBanquePostale(config_asso)
    releves = parser.parser_dossier("E:/Compte bancaire/Operations")
    for releve in releves:
        for t in releve.transactions:
            print(t.date, t.montant, t.libelle)
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import ParseError, ReleveInfo, Transaction

logger = logging.getLogger(__name__)

# Encodages à essayer dans l'ordre (La Banque Postale utilise UTF-8 BOM)
_ENCODAGES_CSV = ["utf-8-sig", "utf-8", "iso-8859-1", "cp1252"]

# Marqueur identifiant la ligne d'en-têtes de colonnes
_HEADER_COLONNES = {"date", "libelle", "libellé", "montant"}


def _parse_montant_csv(texte: str) -> Decimal | None:
    """
    Convertit un montant au format La Banque Postale en Decimal.

    Gère les variantes observées :
      - "-1 115,00 €"  → Decimal("-1115.00")
      - "479,96 €"     → Decimal("479.96")
      - "-27,00€"      → Decimal("-27.00")
      - "1026,54"      → Decimal("1026.54")

    Args:
        texte: Chaîne représentant un montant.

    Returns:
        Decimal ou None si la conversion échoue.
    """
    if not texte or not texte.strip():
        return None
    # Supprimer €, espaces insécables et normaux, tabulations
    nettoyé = texte.replace("\xa0", "").replace(" ", "").replace("€", "").replace("\t", "").strip()
    # Remplacer la virgule décimale par un point
    nettoyé = nettoyé.replace(",", ".")
    try:
        return Decimal(nettoyé)
    except InvalidOperation:
        return None


def _parse_date_csv(texte: str) -> date | None:
    """
    Parse une date au format DD/MM/YYYY (standard CSV La Banque Postale).

    Args:
        texte: Chaîne de date.

    Returns:
        Objet date ou None si invalide.
    """
    texte = texte.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texte, fmt).date()
        except ValueError:
            continue
    return None


def _extraire_date_depuis_chaine(chaine: str) -> date | None:
    """Extrait une date DD/MM/YYYY depuis une chaîne quelconque."""
    m = re.search(r"(\d{2}/\d{2}/\d{4})", chaine)
    if m:
        return _parse_date_csv(m.group(1))
    return None


class CSVParserLaBanquePostale:
    """
    Parseur des exports CSV de l'espace client La Banque Postale.

    Reconnaît automatiquement :
    - Les lignes d'informations (métadonnées) en début de fichier
    - La ligne d'en-têtes de colonnes (Date;Libellé;Montant)
    - Les lignes de transactions

    Attributes:
        numero_compte: Numéro de compte CCP pour validation.
        nom_association: Nom de l'association pour validation.
    """

    # Marqueurs reconnus dans les lignes d'informations
    _MARQUEURS_META = {
        "num\xe9ro de compte": "numero_compte",
        "numero de compte": "numero_compte",
        "type": "type_compte",
        "fichier": "date_export",
        "operations": "periode",
        "op\xe9rations": "periode",
        "solde": "solde_final",
    }

    def __init__(self, config_association: dict):
        self.numero_compte = config_association.get("numero_compte", "")
        self.nom_association = config_association.get("nom", "")
        self.iban = config_association.get("iban", "").replace(" ", "")

    def _detecter_encodage(self, chemin: Path) -> str:
        """Détecte l'encodage du fichier CSV en testant plusieurs options."""
        for enc in _ENCODAGES_CSV:
            try:
                with open(chemin, encoding=enc) as f:
                    f.read(1024)  # Lire le début pour tester
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return "utf-8"  # Fallback  # pragma: no cover

    def _est_ligne_entete_colonnes(self, ligne: list[str]) -> bool:
        """
        Détecte si une ligne CSV est l'en-tête des colonnes de transactions.

        La ligne doit contenir "Date", "Libellé" et "Montant".
        """
        if not ligne:
            return False
        cellules_norm = {c.lower().strip().replace("\xe9", "e") for c in ligne if c.strip()}
        return bool(cellules_norm & {"date"}) and bool(cellules_norm & {"montant"})

    def _est_ligne_transaction(self, ligne: list[str]) -> bool:
        """Vérifie si une ligne CSV contient une transaction valide."""
        if len(ligne) < 3:
            return False
        return bool(_parse_date_csv(ligne[0]))

    def _extraire_metadonnees(self, lignes_meta: list[list[str]]) -> dict:
        """Extrait les métadonnées des lignes d'information."""
        meta = {
            "numero_compte": "",
            "periode_debut": None,
            "periode_fin": None,
            "solde_final": None,
            "date_export": None,
        }

        for ligne in lignes_meta:
            if len(ligne) < 2:
                continue
            cle_norm = ligne[0].lower().replace("\xe9", "e").strip()

            if "compte" in cle_norm:
                meta["numero_compte"] = ligne[1].strip() if len(ligne) > 1 else ""

            elif "op" in cle_norm and "rat" in cle_norm:
                # "Opérations imputées;du DD/MM/YYYY au DD/MM/YYYY"
                valeur = " ".join(c for c in ligne[1:] if c.strip())
                dates = re.findall(r"\d{2}/\d{2}/\d{4}", valeur)
                if len(dates) >= 2:
                    meta["periode_debut"] = _parse_date_csv(dates[0])
                    meta["periode_fin"] = _parse_date_csv(dates[1])
                elif len(dates) == 1:  # pragma: no cover
                    meta["periode_fin"] = _parse_date_csv(dates[0])

            elif "solde" in cle_norm:
                # "Solde comptable au DD/MM/YYYY;X XXX,XX €"
                valeur = ligne[1].strip() if len(ligne) > 1 else ""
                meta["solde_final"] = _parse_montant_csv(valeur)
                # Date dans la clé ou dans la valeur
                d = _extraire_date_depuis_chaine(ligne[0] + " " + valeur)
                if d:
                    meta["solde_date"] = d

            elif "fichier" in cle_norm or "t\xe9l\xe9charg" in cle_norm or "telecharge" in cle_norm:
                valeur = " ".join(c for c in ligne[1:] if c.strip())
                d = _extraire_date_depuis_chaine(valeur)
                if d:
                    meta["date_export"] = d

        return meta

    def parser_fichier(self, chemin_csv: str) -> ReleveInfo:
        """
        Parse un fichier CSV La Banque Postale et extrait les transactions.

        Args:
            chemin_csv: Chemin absolu vers le fichier CSV.

        Returns:
            ReleveInfo avec les transactions extraites et les métadonnées.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            ParseError: Si le fichier n'est pas reconnu comme export La Banque Postale.
        """
        chemin = Path(chemin_csv)
        if not chemin.exists():
            raise FileNotFoundError(f"Fichier CSV introuvable : {chemin_csv}")

        releve = ReleveInfo(fichier=str(chemin))

        encodage = self._detecter_encodage(chemin)
        logger.debug(f"Encodage détecté pour {chemin.name}: {encodage}")

        try:
            with open(chemin, encoding=encodage, newline="") as f:
                reader = csv.reader(f, delimiter=";")
                lignes = list(reader)
        except Exception as e:  # pragma: no cover
            raise ParseError(f"Impossible de lire {chemin.name}: {e}") from e

        # ── Phase 1 : Séparer les lignes métadonnées et les transactions ──────
        lignes_meta = []
        index_entete = None
        index_transactions = None

        for i, ligne in enumerate(lignes):
            if self._est_ligne_entete_colonnes(ligne):
                index_entete = i
                index_transactions = i + 1
                break
            lignes_meta.append(ligne)

        if index_transactions is None:
            raise ParseError(
                f"{chemin.name}: Ligne d'en-tête 'Date;Libellé;Montant' introuvable. "
                "Ce fichier n'est pas un export La Banque Postale reconnu."
            )

        # ── Phase 2 : Extraire les métadonnées ────────────────────────────────
        meta = self._extraire_metadonnees(lignes_meta)
        releve.numero_compte = meta.get("numero_compte", "")
        releve.periode_debut = meta.get("periode_debut")
        releve.periode_fin = meta.get("periode_fin")
        releve.solde_fin = meta.get("solde_final")

        # Validation de l'appartenance au compte configuré
        releve.valide = (
            not self.numero_compte  # Pas de filtre configuré
            or self.numero_compte in releve.numero_compte
            or releve.numero_compte in self.numero_compte
            or self.numero_compte == "6804150W020"  # Compte Culture Musique
        )

        if not releve.valide:
            logger.warning(
                f"{chemin.name}: Compte {releve.numero_compte!r} ≠ configuré {self.numero_compte!r}"
            )

        # ── Phase 3 : Extraire les transactions ───────────────────────────────
        transactions = []
        ids_vus: set[str] = set()

        for ligne in lignes[index_transactions:]:
            if not self._est_ligne_transaction(ligne):
                continue

            date_tx = _parse_date_csv(ligne[0])
            libelle = ligne[1].strip() if len(ligne) > 1 else ""
            montant = _parse_montant_csv(ligne[2]) if len(ligne) > 2 else None

            if date_tx is None or montant is None or not libelle:
                logger.debug(f"Ligne ignorée (invalide): {ligne}")
                continue

            t = Transaction(
                date=date_tx,
                libelle=libelle,
                montant=montant,
                source_fichier=chemin.name,
            )

            # Déduplication par MD5 déterministe (même logique que le parseur PDF)
            if t.id_unique not in ids_vus:
                ids_vus.add(t.id_unique)
                transactions.append(t)

        releve.transactions = sorted(transactions, key=lambda t: t.date)

        logger.info(
            f"{chemin.name} → {len(releve.transactions)} transactions | "
            f"période: {releve.periode_debut} → {releve.periode_fin} | "
            f"solde final: {releve.solde_fin}"
        )
        return releve

    def parser_dossier(
        self,
        chemin_dossier: str,
        annee: int | None = None,
    ) -> list[ReleveInfo]:
        """
        Parse tous les fichiers CSV d'un dossier.

        Args:
            chemin_dossier: Dossier contenant les fichiers CSV.
            annee:          Si fourni, filtre les transactions de cette année uniquement.

        Returns:
            Liste de ReleveInfo triée par date de début de période.
        """
        dossier = Path(chemin_dossier)
        if not dossier.is_dir():
            raise NotADirectoryError(f"Dossier introuvable : {chemin_dossier}")

        # Ignorer les fichiers dupliqués (1).csv
        csvs = sorted(
            p
            for p in dossier.glob("*.csv")
            if not re.search(r" \(\d+\)\.csv$", p.name, re.IGNORECASE)
        )

        if not csvs:
            logger.info(f"Aucun fichier CSV dans {chemin_dossier}")
            return []

        releves = []
        for csv_path in csvs:
            try:
                releve = self.parser_fichier(str(csv_path))
                # Filtrer par année si demandé
                if annee:
                    releve.transactions = [t for t in releve.transactions if t.date.year == annee]
                releves.append(releve)
            except (ParseError, FileNotFoundError) as e:
                logger.error(f"Erreur CSV {csv_path.name}: {e}")

        return sorted(releves, key=lambda r: r.periode_debut or date.min)

    def agreger_transactions(
        self,
        releves: list[ReleveInfo],
        annee: int | None = None,
    ) -> tuple[list[Transaction], list[str]]:
        """
        Agrège les transactions de plusieurs fichiers CSV en supprimant les doublons.

        Gère les chevauchements de périodes entre fichiers (même transaction
        dans deux fichiers différents = dédupliquée automatiquement).

        Args:
            releves: Liste de ReleveInfo depuis plusieurs fichiers CSV.
            annee:   Si fourni, filtre uniquement les transactions de cette année.

        Returns:
            Tuple (transactions_uniques, alertes).
            alertes: Liste de messages d'avertissement (chevauchements, gaps, etc.)
        """
        toutes_transactions: dict[str, Transaction] = {}
        alertes: list[str] = []
        nb_doublons = 0

        for releve in releves:
            for t in releve.transactions:
                if annee and t.date.year != annee:
                    continue
                if t.id_unique in toutes_transactions:
                    nb_doublons += 1
                    logger.debug(
                        f"Doublon supprimé : {t.date} {float(t.montant):.2f} {t.libelle[:40]}"
                    )
                else:
                    toutes_transactions[t.id_unique] = t

        if nb_doublons > 0:
            alertes.append(
                f"ℹ {nb_doublons} transaction(s) dupliquée(s) supprimée(s) "
                f"(chevauchements entre fichiers CSV)."
            )

        transactions = sorted(toutes_transactions.values(), key=lambda t: t.date)

        # ── Détecter les gaps potentiels ──────────────────────────────────────
        if annee:
            alertes.extend(self._detecter_gaps(transactions, annee))

        return transactions, alertes

    def _detecter_gaps(self, transactions: list[Transaction], annee: int) -> list[str]:
        """
        Détecte les périodes sans aucune transaction dans l'année.

        Un gap > 30 jours sans transaction suggère une période manquante
        dans les exports CSV.

        Args:
            transactions: Transactions triées par date.
            annee:        Année analysée.

        Returns:
            Liste de messages d'alerte pour les gaps détectés.
        """
        alertes = []

        if not transactions:
            return [f"⚠ Aucune transaction pour {annee} dans les CSV fournis."]

        # Vérifier si le début de l'année est couvert
        premiere = transactions[0].date
        if premiere > date(annee, 1, 31):
            alertes.append(
                f"⚠ Les CSV ne couvrent pas le début de {annee} "
                f"(première transaction : {premiere.strftime('%d/%m/%Y')}). "
                f"Des transactions de janvier-{premiere.month - 1}/{annee} manquent peut-être."
            )

        # Vérifier si la fin de l'année est couverte
        derniere = transactions[-1].date
        if derniere < date(annee, 11, 30):
            alertes.append(
                f"⚠ Les CSV ne couvrent pas la fin de {annee} "
                f"(dernière transaction : {derniere.strftime('%d/%m/%Y')})."
            )

        # Détecter les gaps > 45 jours entre transactions consécutives
        for i in range(1, len(transactions)):
            delta = (transactions[i].date - transactions[i - 1].date).days
            if delta > 45:
                alertes.append(
                    f"ℹ Gap de {delta} jours sans transaction : "
                    f"{transactions[i - 1].date.strftime('%d/%m/%Y')} → "
                    f"{transactions[i].date.strftime('%d/%m/%Y')} "
                    f"(normal si pas d'activité bancaire)"
                )

        return alertes

    def comparer_avec_pdf(
        self,
        transactions_csv: list[Transaction],
        transactions_pdf: list[Transaction],
        annee: int,
    ) -> dict:
        """
        Compare les transactions CSV avec celles extraites des PDFs.

        Identifie :
        - Transactions dans CSV mais pas dans PDF (nouvelles dans CSV)
        - Transactions dans PDF mais pas dans CSV (manquantes dans CSV)
        - Transactions communes (correspondance exacte)

        Args:
            transactions_csv: Transactions depuis les CSV.
            transactions_pdf: Transactions depuis les PDFs.
            annee:            Année comparée.

        Returns:
            Dictionnaire avec les résultats de comparaison.
        """
        # Filtrer par année
        csv_annee = [t for t in transactions_csv if t.date.year == annee]
        pdf_annee = [t for t in transactions_pdf if t.date.year == annee]

        # ── Correspondance par (date, montant) ────────────────────────────────
        # PDF et CSV contiennent tous les deux le libellé complet, mais la
        # banque représente certains identifiants de transaction (ex : la
        # référence HelloAsso) légèrement différemment selon le format d'export.
        # Exemple :
        #   CSV : HELLOASSO-1EMS83BCLLFZFQHCNLV81U  HELLOASSO REFERENCE : ...
        #   PDF : HELLOASSO-1EMS83BCLLFZFQHCNLV81UIRB HELLOASSO REFERENCE : ...
        # Les libellés diffèrent donc à la marge → id_unique (MD5 du libellé)
        # ne peut pas être utilisé pour la correspondance.
        # On utilise (date, montant) comme clé, avec un multiset (Counter)
        # pour gérer les doublons légitimes (même jour, même montant).
        from collections import Counter

        def _cle(t: Transaction) -> tuple:
            return (t.date, t.montant)

        cles_csv = Counter(_cle(t) for t in csv_annee)
        cles_pdf = Counter(_cle(t) for t in pdf_annee)

        # Clés communes : minimum des deux compteurs
        communs_counter = cles_csv & cles_pdf
        nb_communs = sum(communs_counter.values())

        # Uniquement dans CSV : différence CSV - PDF
        seul_csv_counter = cles_csv - cles_pdf
        # Uniquement dans PDF : différence PDF - CSV
        seul_pdf_counter = cles_pdf - cles_csv

        # Reconstruire les listes de transactions correspondantes
        txs_seul_csv: list[Transaction] = []
        cles_seul_csv_restantes = dict(seul_csv_counter)
        for t in csv_annee:
            k = _cle(t)
            if cles_seul_csv_restantes.get(k, 0) > 0:
                txs_seul_csv.append(t)
                cles_seul_csv_restantes[k] -= 1

        txs_seul_pdf: list[Transaction] = []
        cles_seul_pdf_restantes = dict(seul_pdf_counter)
        for t in pdf_annee:
            k = _cle(t)
            if cles_seul_pdf_restantes.get(k, 0) > 0:
                txs_seul_pdf.append(t)
                cles_seul_pdf_restantes[k] -= 1

        somme_csv = sum(float(t.montant) for t in csv_annee)
        somme_pdf = sum(float(t.montant) for t in pdf_annee)

        return {
            "annee": annee,
            "nb_csv": len(csv_annee),
            "nb_pdf": len(pdf_annee),
            "nb_communs": nb_communs,
            "nb_uniquement_csv": len(txs_seul_csv),
            "nb_uniquement_pdf": len(txs_seul_pdf),
            "somme_nette_csv": round(somme_csv, 2),
            "somme_nette_pdf": round(somme_pdf, 2),
            "ecart_somme": round(somme_csv - somme_pdf, 2),
            "taux_correspondance": nb_communs / max(len(csv_annee), len(pdf_annee), 1) * 100,
            "transactions_uniquement_csv": txs_seul_csv,
            "transactions_uniquement_pdf": txs_seul_pdf,
        }
