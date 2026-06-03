"""
Parseur pour les relevés de compte La Banque Postale (CCP).

Ce module gère l'extraction des transactions depuis les fichiers PDF
de relevés La Banque Postale au format CCP (Compte Chèque Postal).

Format observé sur les relevés 2024 (et similaire depuis ~2019) :
  - En-tête : numéro CCP, IBAN, BIC, "Nouveau solde au JJ/MM/AAAA"
  - Corps : tableau avec colonnes Date | Opération | Débit(€) | Crédit(€)
  - Dates au format DD/MM (sans année — l'année est déduite du nom de fichier)
  - "Ancien solde au JJ/MM/AAAA  X XXX,XX" → solde d'ouverture
  - "Nouveau solde au JJ/MM/AAAA  X XXX,XX" → solde de clôture
  - Nom fichier : releve_6804150W020_YYYY-MM-DD.pdf

Exemple de ligne de transaction extraite du texte brut ::

    03/01 PRELEVEMENT DE PayPal Europe S.a.r.   16,00
    l. et Cie S.C.A REF : 103158...

Utilisation typique::

    parser = LaPosteParser(config_asso)
    releve  = parser.parser_fichier("releve_6804150W020_2024-01-31.pdf")
    for t in releve.transactions:
        print(t.date, t.libelle, t.montant)
"""

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pdfplumber

from .models import ParseError, ReleveInfo, Transaction

logger = logging.getLogger(__name__)

# Marqueur du format ancien avec colonne francs (2013-~2018)
_FORMAT_SOITENFRANCS = "soitenfrancs"

# Noms de mois français → numéro de mois
# Les clés sont normalisées (Ø→e, ß→u, accents supprimés)
_MOIS_FR = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}


def _normaliser_pdf_texte(texte: str) -> str:
    """
    Normalise le texte extrait d'un PDF La Banque Postale.

    Supprime les références CID (ex: (cid:160) = espace insécable) et
    corrige les artefacts d'encodage courants observés sur ces relevés :
      - Ø (0xF8) → e  : pour fØvrier→fevrier, dØcembre→decembre
      - ß (0xDF) → u  : pour aoßt→aout
      - Œ (0x8C) → oe : pour ArrŒté

    Args:
        texte: Texte brut extrait par pdfplumber.

    Returns:
        Texte normalisé en minuscules.
    """
    t = texte.lower()
    t = re.sub(r"\(cid:\d+\)", " ", t)  # supprimer (cid:NNN)
    t = re.sub(r"\(cid:[0-9]+\)", " ", t)
    import re as _re

    t = _re.sub(r"\(cid:\d+\)", " ", t)
    t = t.replace("\xf8", "e").replace("\xdf", "u").replace("\x8c", "oe")
    t = t.replace("\u00f8", "e").replace("\u00df", "u")
    # Remplacement direct des caractères
    t = t.replace("ø", "e")  # Ø → e
    t = t.replace("ß", "u")  # ß → u
    t = t.replace("", "oe")  # Œ → oe
    return t


def _parse_mois_fr(mot: str) -> "int | None":
    """Convertit un nom de mois français (encodage toléré) en numéro."""
    t = _normaliser_pdf_texte(mot).strip()
    for nom, num in _MOIS_FR.items():
        if nom in t:
            return num
    return None


# ── Expressions régulières ────────────────────────────────────────────────────

# Date DD/MM en début de ligne de transaction (pas d'année sur le relevé)
_RE_DATE_TX = re.compile(r"^(\d{2})/(\d{2})$")

# Date complète DD/MM/YYYY pour les soldes
_RE_DATE_COMPLETE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

# Montant français : "1 234,56" ou "1234,56" (espaces insécables possibles)
_RE_MONTANT = re.compile(r"^\+?\s*\d[\d\s ]*,\d{2}$")

# Ancien solde au JJ/MM/AAAA  XXXX,XX
_RE_ANCIEN_SOLDE = re.compile(
    r"ancien\s+solde\s+au\s+\d{2}/\d{2}/\d{4}\s+([\d\s ]+,\d{2})",
    re.IGNORECASE,
)
# Nouveau solde au JJ/MM/AAAA  +XXXX,XX ou  XXXX,XX
_RE_NOUVEAU_SOLDE = re.compile(
    r"nouveau\s+solde\s+au\s+\d{2}/\d{2}/\d{4}\s+\+?\s*([\d\s ]+,\d{2})",
    re.IGNORECASE,
)
# _RE_PERIODE ancienne supprimée : l'extraction se fait via _extraire_periode_pdf()
# qui gère tous les formats (dates numériques ET noms de mois français encodés).
# Numéro de compte dans le texte
_RE_NUMERO_COMPTE = re.compile(r"(\d{7}[A-Z]\d{3})")


def _parse_montant(texte: str) -> Decimal | None:
    """
    Convertit une chaîne montant français en Decimal.

    Gère les espaces insécables (\\u00a0), les espaces normaux
    et la virgule décimale.

    Args:
        texte: Chaîne brute du montant (ex: "1 234,56", "16,00").

    Returns:
        Decimal ou None si conversion impossible.
    """
    if not texte:
        return None
    # Supprimer €, espaces (normaux et insécables), signe +
    nettoyé = texte.replace("€", "").replace(" ", "").replace(" ", "").replace("+", "").strip()
    nettoyé = nettoyé.replace(",", ".")
    try:
        return Decimal(nettoyé)
    except InvalidOperation:
        return None


def _parse_date_complete(texte: str) -> date | None:
    """Parse une date DD/MM/YYYY."""
    m = _RE_DATE_COMPLETE.search(texte)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


class LaPosteParser:
    """
    Parseur de relevés La Banque Postale au format PDF (CCP).

    Vérifie l'appartenance du fichier à l'association grâce au
    numéro de compte CCP ou à l'IBAN, puis extrait les transactions.

    Attributes:
        iban:            IBAN de l'association (sans espaces, majuscules).
        bic:             BIC de l'association.
        numero_compte:   Numéro CCP court (ex: "6804150W020").
        nom_association: Nom de l'association pour validation.
    """

    def __init__(self, config_association: dict[str, Any]) -> None:
        """
        Initialise le parseur avec la configuration de l'association.

        Args:
            config_association: Dictionnaire chargé depuis association.json.
        """
        self.iban = config_association.get("iban", "").replace(" ", "").upper()
        self.bic = config_association.get("bic", "").upper()
        self.numero_compte = config_association.get("numero_compte", "")
        self.nom_association = config_association.get("nom", "")
        # Extraire le numéro court depuis l'IBAN si non fourni explicitement
        if not self.numero_compte and len(self.iban) >= 25:
            self.numero_compte = self._extraire_numero_compte(self.iban)

    def _extraire_numero_compte(self, iban: str) -> str:
        """
        Extrait le numéro CCP lisible depuis l'IBAN La Banque Postale.

        Format IBAN LBP : FR94 2004 1000 0168 0415 0W02 084
        Le numéro CCP (11 chars) commence à la position 14 de l'IBAN sans espaces.
        """
        iban_clean = iban.replace(" ", "")
        if len(iban_clean) >= 25 and iban_clean.startswith("FR"):
            candidat = iban_clean[14:25]
            # Doit ressembler à 7 chiffres + 1 lettre + 3 chiffres
            if re.match(r"\d{7}[A-Z]\d{3}", candidat):
                return candidat
        return ""  # pragma: no cover

    @staticmethod
    def _normaliser_pour_recherche(texte: str) -> str:
        """
        Normalise un texte pour la recherche dans le PDF.

        Supprime les accents (unicodedata NFD), les artefacts d'encodage PDF
        connus (Ø→e, ß→u) et met en minuscules avec espaces réduits.

        Exemples :
            "Culture Musique"           → "culture musique"
            "Société des Amis"          → "societe des amis"
            "ASSO CULTURE MUSIQUE"      → "asso culture musique"

        Grâce à cette normalisation, l'utilisateur peut saisir "Culture Musique"
        et la recherche trouvera "ASSO CULTURE MUSIQUE" dans le PDF (substring).
        """
        import unicodedata

        nfd = unicodedata.normalize("NFD", texte)
        sans_accent = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
        # Artefacts d'encodage spécifiques aux PDFs LBP
        sans_accent = (
            sans_accent.replace("ø", "e")
            .replace("Ø", "e")
            .replace("ß", "u")
            .replace("œ", "oe")
            .replace("Œ", "oe")
        )
        return " ".join(sans_accent.lower().split())

    # Gardé pour compatibilité avec les tests existants
    @staticmethod
    def _normaliser_nom(texte: str) -> str:
        """Normalise un nom (sans accents, majuscules, espaces réduits)."""
        import unicodedata

        nfd = unicodedata.normalize("NFD", texte)
        sans_accent = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
        return " ".join(sans_accent.upper().split())

    def _valider_releve(self, releve: ReleveInfo, texte_pdf: str = "") -> None:
        """
        Valide le relevé extrait contre la configuration de l'association.

        Vérifie dans l'ordre :
        1. Nom de l'association — recherche directe de la chaîne normalisée
           (sans accents, minuscules) dans le texte brut du PDF. Aucune
           extraction préalable ni gestion de préfixes légaux n'est nécessaire :
           "culture musique" est une sous-chaîne de "asso culture musique". ✓
        2. IBAN (correspondance stricte, sans espaces)
        3. BIC (correspondance stricte)
        4. Numéro de compte (correspondance stricte)

        Args:
            releve:    ReleveInfo à valider (modifié en place).
            texte_pdf: Texte brut de la première page du PDF (pour la recherche
                       du nom). Si vide, la vérification du nom est ignorée.

        Les raisons de rejet sont stockées dans releve.raisons_rejet.
        releve.valide est True uniquement si aucune règle configurée n'est violée.
        """
        raisons: list[str] = []

        # 1. Nom de l'association — recherche directe dans le texte PDF
        if self.nom_association and texte_pdf:
            nom_conf = self._normaliser_pour_recherche(self.nom_association)
            texte_norm = self._normaliser_pour_recherche(texte_pdf)
            if nom_conf not in texte_norm:
                raisons.append(
                    f"Nom de la structure : '{self.nom_association}' introuvable dans le PDF"
                )
        elif self.nom_association and not texte_pdf:
            logger.info(
                f"{Path(releve.fichier).name} : texte PDF absent, verification du nom ignoree"
            )

        # 2. IBAN
        if self.iban:
            iban_conf = self.iban.replace(" ", "").upper()
            iban_pdf = releve.iban_pdf.replace(" ", "").upper()
            if iban_pdf and iban_conf != iban_pdf:
                raisons.append(f"IBAN : config='{self.iban}' != PDF='{releve.iban_pdf}'")
            elif not iban_pdf:
                logger.info(
                    f"{Path(releve.fichier).name} : IBAN non extrait du PDF, "
                    "verification IBAN ignoree"
                )

        # 3. BIC
        if self.bic:
            bic_conf = self.bic.replace(" ", "").upper()
            bic_pdf = releve.bic_pdf.replace(" ", "").upper()
            if bic_pdf and bic_conf != bic_pdf:
                raisons.append(f"BIC : config='{self.bic}' != PDF='{releve.bic_pdf}'")
            elif not bic_pdf:
                logger.info(
                    f"{Path(releve.fichier).name} : BIC non extrait du PDF, "
                    "verification BIC ignoree"
                )

        # 4. Numéro de compte
        if self.numero_compte and releve.numero_compte:
            nc_conf = self.numero_compte.replace(" ", "").upper()
            nc_pdf = releve.numero_compte.replace(" ", "").upper()
            if nc_conf != nc_pdf:
                raisons.append(
                    f"Numero de compte : config='{self.numero_compte}' "
                    f"!= PDF='{releve.numero_compte}'"
                )

        releve.raisons_rejet = raisons
        releve.valide = len(raisons) == 0

        if raisons:
            logger.warning(f"{Path(releve.fichier).name} rejete : " + " | ".join(raisons))

    def parser_fichier(self, chemin_pdf: str) -> ReleveInfo:
        """
        Parse un fichier PDF de relevé et extrait toutes les transactions.

        Args:
            chemin_pdf: Chemin absolu vers le fichier PDF.

        Returns:
            ReleveInfo avec les transactions et métadonnées extraites.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            ParseError: Si le fichier est illisible.
        """
        chemin = Path(chemin_pdf)
        if not chemin.exists():
            raise FileNotFoundError(f"Fichier introuvable : {chemin_pdf}")

        releve = ReleveInfo(fichier=str(chemin))

        # Déduire l'année depuis le nom de fichier (ex: releve_6804150W020_2024-01-31.pdf)
        annee_fichier = self._annee_depuis_nom(chemin.name)
        mois_fichier = self._mois_depuis_nom(chemin.name)

        try:
            with pdfplumber.open(chemin_pdf) as pdf:
                texte_complet = ""
                texte_page_0 = ""
                toutes_lignes: list[dict[str, Any]] = []

                for num_page, page in enumerate(pdf.pages):
                    texte_page = page.extract_text() or ""
                    texte_complet += "\n" + texte_page

                    if num_page == 0:
                        texte_page_0 = texte_page
                        self._extraire_metadonnees(texte_page, releve)

                    lignes = self._extraire_lignes_page(texte_page, annee_fichier, mois_fichier)
                    toutes_lignes.extend(lignes)

                # Extraire les soldes depuis le texte complet
                self._extraire_soldes(texte_complet, releve)

                # Valider le relevé — le nom est recherché directement dans
                # le texte brut de la première page (approche robuste et simple)
                self._valider_releve(releve, texte_pdf=texte_page_0)

                # Convertir en objets Transaction
                releve.transactions = self._construire_transactions(toutes_lignes, chemin.name)

        except ParseError:
            raise  # pragma: no cover
        except Exception as e:
            raise ParseError(f"Erreur lors du parsing de {chemin.name}: {e}") from e

        logger.info(
            f"{chemin.name} → {len(releve.transactions)} transactions | "
            f"solde début={releve.solde_debut} fin={releve.solde_fin}"
        )
        return releve

    # ── Extraction des métadonnées ────────────────────────────────────────────

    def _extraire_periode_pdf(self, texte: str) -> tuple[date | None, date | None]:
        """
        Extrait la période de couverture depuis le texte brut du PDF.

        Analyse la ligne "Arrêté mensuel du ... au ..." présente sur chaque
        relevé La Banque Postale, en gérant toutes les variantes observées
        de 2013 à 2025 (dates numériques DD/MM/YYYY ou noms de mois français
        avec artefacts d'encodage).

        Formats observés :
          - "ArrŒtØ mensuel du 30 dØcembre 2023(cid:160)au(cid:160)31 janvier 2024"
          - "ArrŒtØmensuel du1(cid:160)au(cid:160)31 janvier 2025"
          - "ArrŒtØ mensuel du 1 fØvrier(cid:160)au(cid:160)30 avril 2014"
          - "> ArrŒtØmensuel du 31 dØcembre 2022(cid:160)au(cid:160)31 janvier 2023"

        Returns:
            Tuple (periode_debut, periode_fin) — l'un ou les deux peuvent être None.
        """
        texte_norm = _normaliser_pdf_texte(texte)

        for ligne in texte_norm.split("\n"):
            if "mensuel" not in ligne:
                continue

            # ── Tenter d'abord le format numérique DD/MM/YYYY ──────────────
            # (anciens relevés)
            m_num = re.search(r"du\s+(\d{2}/\d{2}/\d{4})\s+(?:au|a)\s+(\d{2}/\d{2}/\d{4})", ligne)
            if m_num:
                d1 = _parse_date_complete(m_num.group(1))
                d2 = _parse_date_complete(m_num.group(2))
                if d1 and d2:
                    return d1, d2

            # ── Format texte avec noms de mois français ────────────────────
            # Chercher la date de FIN (après "au") — toujours complète
            m_fin = re.search(r"au\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})", ligne)
            if not m_fin:
                continue

            try:
                jour_fin = int(m_fin.group(1))
                mois_fin = _parse_mois_fr(m_fin.group(2))
                annee_fin = int(m_fin.group(3))
                if not mois_fin:
                    continue
                periode_fin = date(annee_fin, mois_fin, jour_fin)
            except (ValueError, TypeError):
                continue

            # Chercher la date de DÉBUT (après "du")
            # Cas 1 : "du DD MOIS AAAA" — début dans un mois/année différent
            m_debut_complet = re.search(r"du\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})", ligne)
            if m_debut_complet:
                try:
                    j = int(m_debut_complet.group(1))
                    mo = _parse_mois_fr(m_debut_complet.group(2))
                    aa = int(m_debut_complet.group(3))
                    if mo:
                        return date(aa, mo, j), periode_fin
                except (ValueError, TypeError):  # pragma: no cover
                    pass  # pragma: no cover

            # Cas 2 : "du D" ou "du DD" — même mois que la fin
            m_debut_simple = re.search(r"du\s*(\d{1,2})\b", ligne)
            if m_debut_simple:
                try:
                    j = int(m_debut_simple.group(1))
                    return date(annee_fin, mois_fin, j), periode_fin
                except ValueError:  # pragma: no cover
                    pass  # pragma: no cover

            # Cas 3 : début non trouvé — on prend le 1er du mois de fin
            return date(annee_fin, mois_fin, 1), periode_fin  # pragma: no cover

        return None, None

    def _annee_depuis_nom(self, nom: str) -> int:
        """Extrait l'année depuis le nom de fichier (YYYY dans YYYY-MM-DD ou YYYYMMDD)."""
        # Format : releve_6804150W020_2024-01-31.pdf
        m = re.search(r"(\d{4})-\d{2}-\d{2}", nom)
        if m:
            return int(m.group(1))
        # Format ancien : releve_CCP6804150W020_20241031.pdf
        m = re.search(r"(\d{4})\d{4}\.", nom)
        if m:
            return int(m.group(1))
        return datetime.now().year

    def _mois_depuis_nom(self, nom: str) -> int | None:
        """
        Extrait le mois depuis le nom de fichier.

        Formats supportés :
          - YYYY-MM-DD : releve_6804150W020_2023-09-29.pdf → 9
          - YYYYMMDD   : releve_CCP6804150W020_20230131.pdf → 1
        """
        # Format YYYY-MM-DD (nouveau)
        m = re.search(r"\d{4}-(\d{2})-\d{2}", nom)
        if m:
            return int(m.group(1))
        # Format YYYYMMDD (ancien) — 8 chiffres consécutifs suivis d'un point
        m = re.search(r"\d{4}(\d{2})\d{2}\.", nom)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 12:
                return val
        return None

    def _extraire_metadonnees(self, texte: str, releve: ReleveInfo) -> None:
        """
        Extrait le numéro de compte et la période depuis la première page.

        La période est extraite UNIQUEMENT depuis le corps du PDF, jamais
        depuis le nom de fichier (qui peut être modifié par l'utilisateur).

        Formats de la ligne d'arrêté mensuel observés :
          - "ArrŒtØ mensuel du 30 dØcembre 2023 au 31 janvier 2024"
          - "ArrŒtØmensuel du1(cid:160)au(cid:160)31 janvier 2025"
          - "ArrŒtØ mensuel du 1 fØvrier(cid:160)au(cid:160)30 avril 2014"
        """
        # Numéro de compte
        m = _RE_NUMERO_COMPTE.search(texte)
        if m:
            releve.numero_compte = m.group(1)  # pragma: no cover

        # Période — extraction depuis le texte PDF uniquement
        debut, fin = self._extraire_periode_pdf(texte)
        if debut:
            releve.periode_debut = debut
        if fin:
            releve.periode_fin = fin

        # IBAN et BIC — ligne format : "IBAN : FR94 2004 1000 0168 0415 0W02 084 | BIC : PSST..."
        # L'IBAN La Banque Postale contient des lettres (ex : 0W02) — le regex
        # doit accepter des groupes alphanumériques, pas seulement numériques.
        m_iban = re.search(
            r"IBAN\s*:\s*([A-Z]{2}\d{2}(?:\s*[A-Z0-9]{4})*\s*[A-Z0-9]{1,4})", texte, re.IGNORECASE
        )
        if m_iban:
            releve.iban_pdf = m_iban.group(1).replace(" ", "").upper()

        m_bic = re.search(r"BIC\s*:\s*([A-Z0-9]{8,11})", texte, re.IGNORECASE)
        if m_bic:
            releve.bic_pdf = m_bic.group(1).strip().upper()

        # Nom de l'association — apparaît sur la même ligne que l'adresse du centre
        # financier ou sur une ligne dédiée après l'adresse. Chercher sur les lignes
        # qui contiennent des mots-clés d'association.
        # Exemples observés :
        #   "75900 PARIS CEDEX 15 ASSO CULTURE MUSIQUE"
        #   "ASSO CULTURE MUSIQUE"
        #   "ASSOCIATION DES..."
        for ligne in texte.split("\n"):
            ligne_norm = _normaliser_pdf_texte(ligne).upper()
            # Chercher le numéro de compte dans la ligne pour exclure les lignes sans rapport
            # ── Stratégie d'extraction du nom ────────────────────────────────
            # Extraction du nom pour le logging et le champ nom_asso_pdf.
            # Note : la VALIDATION du nom utilise _normaliser_pour_recherche()
            # sur le texte brut complet — cette extraction n'est pas utilisée
            # pour accepter/rejeter le relevé, uniquement pour information.

            # Ligne avec code postal : "75900 PARIS CEDEX 15 ASSO CULTURE MUSIQUE"
            m_nom = re.search(
                r"\d{5}\b.+?((?:ASSO|ASSOCIATION|UNION|LIGUE|FEDERATION|CLUB"
                r"|COMITE|GROUPE|FONDATION|SYNDICAT|AMICALE|COLLECTIF)[A-Z\s]{3,60})",
                ligne_norm,
            )
            if m_nom:
                releve.nom_asso_pdf = m_nom.group(1).strip()
                break
            # Ligne débutant par un préfixe légal non ambigu
            if re.match(
                r"^(?:ASSO|ASSOCIATION|UNION|LIGUE|FEDERATION|CLUB|COMITE"
                r"|GROUPE|FONDATION|SYNDICAT|AMICALE|COLLECTIF)\b",
                ligne_norm,
            ):
                releve.nom_asso_pdf = ligne_norm.strip()
                break
            # Ligne contenant directement le nom de la config (sans préfixe légal)
            # Utilise la même normalisation que _valider_releve (minuscules)
            if self.nom_association:
                nom_conf_norm = self._normaliser_pour_recherche(self.nom_association)
                ligne_rech = self._normaliser_pour_recherche(ligne)
                if nom_conf_norm and nom_conf_norm in ligne_rech:
                    releve.nom_asso_pdf = ligne_norm.strip()
                    break

    def _extraire_soldes(self, texte: str, releve: ReleveInfo) -> None:
        """
        Extrait les soldes d'ouverture et de clôture.

        Format observé sur les relevés 2024 :
          - Nouveau solde : sur une seule ligne
              "Nouveau solde au 31/01/2024 + 4 972,13 €"
          - Ancien solde  : montant sur la ligne PRÉCÉDENTE, label sur la suivante
              "4 424,17"
              "Ancien solde au 29/12/2023"
        """
        # Nouveau solde (une seule ligne)
        m = _RE_NOUVEAU_SOLDE.search(texte.lower())
        if m:
            releve.solde_fin = _parse_montant(m.group(1))

        # Ancien solde : chercher le montant sur la ligne précédente
        lignes = texte.split("\n")
        for i, ligne in enumerate(lignes):
            if "ancien solde" in ligne.lower() and i > 0:
                # Le montant est sur la ligne précédente
                montant = _parse_montant(lignes[i - 1].strip())
                if montant is not None:
                    releve.solde_debut = montant
                    break
                # Ou bien sur la même ligne (certains formats)
                m2 = _RE_ANCIEN_SOLDE.search(ligne.lower())
                if m2:
                    releve.solde_debut = _parse_montant(m2.group(1))
                    break

        # Format 2013-2018 : "Solde au DD/MM/YYYY    X XXX,XX" (sans le mot "Ancien")
        if releve.solde_debut is None:
            m_solde = re.search(
                r"(?<![a-zA-Z])solde\s+au\s+\d{2}/\d{2}/\d{4}\s+([\d\s\xa0]+,\d{2})",
                texte,
                re.IGNORECASE,
            )
            if m_solde:
                releve.solde_debut = _parse_montant(m_solde.group(1))

    # ── Extraction des transactions ────────────────────────────────────────────

    def _extraire_lignes_page(self, texte: str, annee: int, mois_fichier: int | None) -> list[dict[str, Any]]:
        """
        Extrait les lignes de transaction depuis le texte brut d'une page.

        Format La Banque Postale observé en 2024 ::

            03/01 PRELEVEMENT DE PayPal Europe S.a.r. 16,00   ← date + début libellé + MONTANT
            l. et Cie S.C.A REF : 103158...                  ← suite libellé (pas de montant)
            IDENT : LU96ZZZ...                                ← suite libellé (pas de montant)
            08/01 REMISE DE CHEQUES DU 04/01/2024 50,00       ← transaction suivante

        Règle clé : **le montant est toujours à la fin de la ligne qui porte la date**.
        Les lignes de continuation (sans date) n'ont jamais de montant.

        Args:
            texte:        Texte brut de la page.
            annee:        Année déduite du nom de fichier.
            mois_fichier: Mois déduit du nom de fichier.

        Returns:
            Liste de dicts {date, libelle, debit, credit}.
        """
        lignes = texte.split("\n")
        resultats = []
        i = 0

        while i < len(lignes):
            ligne = lignes[i].strip()

            if not ligne or self._est_ligne_ignoree(ligne):
                i += 1
                continue

            # Une transaction commence par DD/MM suivi d'un espace et du libellé
            m_date = re.match(r"^(\d{2})/(\d{2})\s+(.+)", ligne)
            if not m_date:
                i += 1
                continue

            jour = int(m_date.group(1))
            mois = int(m_date.group(2))
            premiere_ligne_contenu = m_date.group(3).strip()

            # Format Soitenfrancs (2013-~2018): strip valeur en francs
            # Ex: "31,80 - 208,59" -> "31,80"  (208,59 = 31,80 x 6.55957 FRF)
            if _FORMAT_SOITENFRANCS in texte.lower().replace(" ", ""):
                premiere_ligne_contenu = re.sub(
                    r"\s+[-+]\s+[\d\s\xa0 ]+,\d{2}\s*$", "", premiere_ligne_contenu
                ).strip()

            try:
                tx_date = date(annee, mois, jour)
            except ValueError:
                i += 1
                continue

            # ── Extraire le montant depuis la FIN de la première ligne ──────────
            # Le montant est TOUJOURS sur la même ligne que la date.
            debit, credit, libelle_debut = self._extraire_montants(premiere_ligne_contenu)

            # ── Accumuler les lignes de continuation (suite du libellé) ─────────
            libelle_parts = [libelle_debut]
            j = i + 1
            while j < len(lignes):
                suite = lignes[j].strip()
                if not suite:
                    j += 1
                    break
                # Nouvelle transaction ou ligne ignorée → arrêt
                if re.match(r"^\d{2}/\d{2}\s", suite) or self._est_ligne_ignoree(suite):
                    break
                libelle_parts.append(suite)
                j += 1

            libelle_final = " ".join(p for p in libelle_parts if p).strip()
            # Nettoyer les artefacts de numéro de page collés au début du libellé.
            # pdfplumber peut fusionner un numéro de page (ex: "4") avec le premier
            # mot de la ligne suivante → "4COTISATION" au lieu de "COTISATION".
            # On supprime les chiffres initiaux si immédiatement suivis d'une
            # lettre majuscule (signe que c'est un artefact, pas un vrai libellé).
            libelle_final = re.sub(r"^\d+([A-ZÀÂÉÈÊÎÔÙÛÜ])", r"\1", libelle_final)

            if debit is not None or credit is not None:
                resultats.append(
                    {
                        "date": tx_date,
                        "libelle": libelle_final,
                        "debit": debit,
                        "credit": credit,
                    }
                )

            i = j

        return resultats

    def _est_ligne_ignoree(self, ligne: str) -> bool:
        """Retourne True pour les lignes à ignorer (en-têtes, totaux, pieds de page)."""
        mots_cles_ignore = [
            "TOTAL DES OPERATIONS",
            "TOTALDESOP",
            "Date Opération Débit",
            "Date Op",
            "DØbit",
            "CrØdit",
            "Page ",
            "LA BANQUE POSTALE",
            "Ancien solde",
            "Nouveau solde",
            "ArrŒtØ",
            "TVA sur",
            "Pour faire opposition",
            "Garantie de vos",
            "Vos opérations CCP",
            "Vos opérations",
        ]
        # Ligne contenant uniquement un numéro de page (ex: "4", "12")
        if re.match(r"^\d+$", ligne.strip()):
            return True

        # Note de bas de page : chiffre(s) immédiatement suivis d'une lettre
        # sans espace intermédiaire.
        # Exemples à ignorer :
        #   "4Fraisetcotisationsperçusouremboursés."  (note pied de page)
        # Exemples à NE PAS ignorer (lignes de continuation légitimes) :
        #   "6121209 Billetterie Weezevent..."         (référence numérique + espace)
        #   "l. et Cie S.C.A REF : ..."               (suite libellé)
        if re.match(r"^\d+[A-Za-zÀ-ÿ]", ligne.strip()):
            return True

        ligne_upper = ligne.upper()
        return any(mot.upper() in ligne_upper for mot in mots_cles_ignore)

    def _extraire_montants(self, texte: str) -> tuple[Decimal | None, Decimal | None, str]:
        """
        Extrait le montant débit et/ou crédit depuis la fin d'une ligne de transaction.

        Les relevés La Banque Postale ont deux colonnes numériques en fin de ligne :
        soit un débit seul, soit un crédit seul (l'autre colonne étant vide).

        Returns:
            Tuple (debit, credit, libelle_sans_montants).
            debit et credit sont mutuellement exclusifs (l'un est None).
        """
        # Pattern : un ou deux montants en fin de chaîne
        # Montant = chiffres avec espaces optionnels + virgule + 2 chiffres
        pattern = re.compile(r"\s+(\d{1,3}(?:[\s \xa0]\d{3}){0,3},\d{2})\s*$")

        montants_trouves: list[Decimal] = []
        texte_restant = texte

        # Extraire jusqu'à 2 montants depuis la droite
        for _ in range(2):
            m = pattern.search(texte_restant)
            if not m:
                break
            val = _parse_montant(m.group(1))
            if val is not None and val > 0:
                montants_trouves.insert(0, val)
                texte_restant = texte_restant[: m.start()]
            else:
                break  # pragma: no cover

        if not montants_trouves:
            return None, None, texte

        # Sur le relevé La Banque Postale, la position détermine débit/crédit :
        # - Si 1 seul montant : besoin du contexte (libellé) pour décider
        # - Si 2 montants : premier = débit, deuxième = crédit (mais l'un vaut 0)

        if len(montants_trouves) == 2:
            # Cas peu fréquent : les deux colonnes remplies → prendre la non-nulle
            if montants_trouves[0] > 0 and montants_trouves[1] == 0:  # pragma: no cover
                return montants_trouves[0], None, texte_restant  # pragma: no cover
            elif montants_trouves[1] > 0 and montants_trouves[0] == 0:  # pragma: no cover
                return None, montants_trouves[1], texte_restant  # pragma: no cover
            else:
                # Les deux non nulles (rare) : heuristique par libellé
                return montants_trouves[0], None, texte_restant  # pragma: no cover

        # 1 seul montant — déduire débit/crédit depuis le libellé
        montant = montants_trouves[0]
        if self._est_credit(texte_restant):
            return None, montant, texte_restant
        else:
            return montant, None, texte_restant

    def _est_credit(self, libelle: str) -> bool:
        """
        Détermine si une transaction est un crédit d'après son libellé.

        Utilise des marqueurs sémantiques connus des relevés La Banque Postale.
        """
        libelle_upper = libelle.upper()
        marqueurs_credit = [
            # Tester les plus spécifiques EN PREMIER (éviter "VIREMENT DE"
            # de matcher "VIREMENT INSTANTANE A" via sous-chaîne)
            "ANNULATION PRELEVEMENT",  # Annulation d'un prelevement = remboursement
            "CREDIT CARTE BANCAIRE",  # Remboursement sur carte bancaire
            "AVOIR",  # Avoir ou remboursement
            "VIREMENT INSTANTANE DE",  # Virement reçu d'une personne physique
            "VIREMENT DE",  # "VIREMENT DE STRIPE", "VIREMENT DE MME..."
            "VIREMENT RECU",
            "REMISE DE CHEQUES",
            "VERSEMENT CARTE",
            "VERSEMENT DAB",
            "VERSEMENT ESPECES",
            "VERSEMENT EFFECTUE",
            "STRIPE",
            "HELLOASSO",
            "WEEZEVENT",
            "WOOPAYMENTS",
        ]
        marqueurs_debit = [
            "VIREMENT INSTANTANE A",  # Virement envoyé à une personne/société
            "PRELEVEMENT DE",
            "PRELEVEMENT SEPA",
            "VIREMENT POUR",  # "VIREMENT POUR REGIE DE LA MAIRIE..."
            "VIREMENT EMIS",
            "ACHAT CB",
            "PAIEMENT CB",
            "COTISATION ADISPO",
            "FRAIS",
        ]
        for m in marqueurs_credit:
            if m in libelle_upper:
                return True
        for m in marqueurs_debit:
            if m in libelle_upper:
                return False
        # Par défaut : débit (plus fréquent pour les opérations ambiguës)
        return False

    def _construire_transactions(self, lignes: list[dict[str, Any]], nom_fichier: str) -> list[Transaction]:
        """
        Convertit les lignes extraites en objets Transaction dédupliqués.

        Args:
            lignes:      Lignes brutes extraites.
            nom_fichier: Nom du fichier PDF source.

        Returns:
            Liste de Transaction triée par date.
        """
        transactions = []
        ids_vus: set[str] = set()

        for ligne in lignes:
            d = ligne["date"]
            debit = ligne.get("debit")
            credit = ligne.get("credit")
            libelle = ligne.get("libelle", "").strip()

            if not libelle:
                continue  # pragma: no cover

            if debit is not None:
                montant = -abs(debit)
            elif credit is not None:
                montant = abs(credit)
            else:
                continue  # pragma: no cover

            t = Transaction(
                date=d,
                libelle=libelle,
                montant=montant,
                source_fichier=nom_fichier,
            )

            # Permettre de vrais doublons (ex: 2 cheques meme montant meme jour)
            # On ajoute un suffixe numerique pour les distinguer
            original_id = t.id_unique
            counter = 0
            while t.id_unique in ids_vus:
                counter += 1
                t.id_unique = f"{original_id}_{counter}"
            ids_vus.add(t.id_unique)
            transactions.append(t)

        return sorted(transactions, key=lambda x: x.date)

    def parser_dossier(self, chemin_dossier: str) -> list[ReleveInfo]:
        """
        Parse tous les PDF d'un dossier.

        Args:
            chemin_dossier: Chemin vers le dossier.

        Returns:
            Liste de ReleveInfo triée par date de début de période.
        """
        dossier = Path(chemin_dossier)
        if not dossier.is_dir():
            raise NotADirectoryError(f"Dossier introuvable : {chemin_dossier}")

        releves = []
        # Ignorer les fichiers dupliques comme "releve_2025-05-30 (1).pdf"
        pdfs_uniques = sorted(
            p
            for p in dossier.glob("*.pdf")
            if not re.search(r" \(\d+\)\.pdf$", p.name, re.IGNORECASE)
        )
        for pdf in pdfs_uniques:
            try:
                releve = self.parser_fichier(str(pdf))
                releves.append(releve)
            except (ParseError, FileNotFoundError) as e:
                logger.error(f"Erreur sur {pdf.name} : {e}")

        releves.sort(key=lambda r: r.periode_debut or date.min)
        return releves
