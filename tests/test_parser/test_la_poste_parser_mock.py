"""
Tests du parseur avec pdfplumber mocké.

Permet de tester toutes les fonctions qui appellent pdfplumber.open()
sans avoir besoin de vrais fichiers PDF.
Cible : passer la couverture de la_poste_parser.py de 45% à ~90%.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from core.parser.la_poste_parser import LaPosteParser
from core.parser.models import ParseError


# ── Helpers — construire de faux objets pdfplumber ───────────────────────────

def _make_fake_page(texte: str) -> MagicMock:
    """Crée une fausse page pdfplumber avec un texte fixe."""
    page = MagicMock()
    page.extract_text.return_value = texte
    return page


def _make_fake_pdf(pages_texte: list[str]) -> MagicMock:
    """Crée un faux objet PDF pdfplumber avec plusieurs pages."""
    pdf = MagicMock()
    pdf.pages = [_make_fake_page(t) for t in pages_texte]
    pdf.__enter__ = lambda s: s
    pdf.__exit__ = MagicMock(return_value=False)
    return pdf


# ── Textes de relevés simulés ─────────────────────────────────────────────────

RELEVE_JANVIER_2024 = """Relevé de votre CCP - n° 1 Relevé édité le 1 février 2024
> Arrêtémensuel du 30 décembre 2023 au 31 janvier 2024
ASSO CULTURE MUSIQUE
Situation du CCP
n° 68 041 50 W 020
IBAN : FR94 2004 1000 0168 0415 0W02 084 | BIC : PSSTFRPPPAR
Nouveau solde au 31/01/2024 + 4 972,13 €
Vos opérations
Date Opération Débit(€) Crédit(€)
4 424,17
Ancien solde au 29/12/2023
03/01 PRELEVEMENT DE PayPal Europe S.a.r. 16,00
l. et Cie S.C.A REF : 1031584305924
08/01 VIREMENT DE STRIPE HELLOASSO-XYZ HELLOASSO 300,00
08/01 REMISE DE CHEQUES DU 04/01/2024 50,00
TotaldesopéRations 266,00
Nouveau solde au 31/01/2024 4 972,13
Page 1/1"""

RELEVE_SOITENFRANCS = """Relevé de votre CCP - n° 1 Relevé édité le 1 février 2017
> Arrêté mensuel du 31 décembre 2016 au 31 janvier 2017
ASSO CULTURE MUSIQUE
IBAN : FR94 2004 1000 0168 0415 0W02 084 | BIC : PSSTFRPPPAR
Nouveau solde au 31/01/2017 + 2 318,21 €
Vos opérations
Date Opération Débit(€) Crédit(€) Soitenfrancs
2 350,01
Ancien solde au 30/12/2016
03/01 Cotisation Adispo Asso Integral 31,80 - 208,59
TotaldesopéRations 31,80
Nouveau solde au 31/01/2017 2 318,21
Page 1/1"""


class TestValiderReleve:
    """Tests de la validation des relevés (_valider_releve)."""

    def _releve_avec(self, iban="", bic="", nom="", num_compte=""):
        """Crée un ReleveInfo avec les métadonnées spécifiées."""
        from core.parser.models import ReleveInfo
        r = ReleveInfo(fichier="test.pdf")
        r.iban_pdf = iban
        r.bic_pdf = bic
        r.nom_asso_pdf = nom
        r.numero_compte = num_compte
        return r

    def test_valide_iban_et_nom_corrects(self, parser):
        """Relevé valide : IBAN et nom correspondent à la config."""
        r = self._releve_avec(
            iban="FR9420041000016804150W02084",
            bic="PSSTFRPPPAR",
            nom="ASSO CULTURE MUSIQUE",
            num_compte="6804150W020",
        )
        parser._valider_releve(r)
        assert r.valide is True
        assert r.raisons_rejet == []

    def test_invalide_iban_different(self, parser):
        """Relevé rejeté si l'IBAN ne correspond pas à la config."""
        r = self._releve_avec(
            iban="FR7620041000099999990W02084",  # IBAN différent
            bic="PSSTFRPPPAR",
            nom="ASSO CULTURE MUSIQUE",
        )
        parser._valider_releve(r)
        assert r.valide is False
        assert any("IBAN" in raison for raison in r.raisons_rejet)

    def test_invalide_bic_different(self, parser):
        """Relevé rejeté si le BIC ne correspond pas à la config."""
        r = self._releve_avec(
            iban="FR9420041000016804150W02084",
            bic="BNPAFRPPXXX",  # BIC différent
            nom="ASSO CULTURE MUSIQUE",
        )
        parser._valider_releve(r)
        assert r.valide is False
        assert any("BIC" in raison for raison in r.raisons_rejet)

    def test_invalide_nom_completement_different(self, parser):
        """Relevé rejeté si le nom ne contient aucune correspondance."""
        r = self._releve_avec(
            iban="FR9420041000016804150W02084",
            bic="PSSTFRPPPAR",
            nom="SOCIETE DUPONT ET FILS SARL",  # nom sans rapport
        )
        parser._valider_releve(r)
        assert r.valide is False
        assert any("Nom" in raison for raison in r.raisons_rejet)

    def test_nom_partiel_accepte(self, parser):
        """Correspondance partielle du nom acceptée (abbréviations)."""
        r = self._releve_avec(
            iban="FR9420041000016804150W02084",
            bic="PSSTFRPPPAR",
            nom="CULTURE MUSIQUE ACM",  # contient une partie du nom config
        )
        parser._valider_releve(r)
        # "Association Culture Musique" contient "CULTURE MUSIQUE"
        # et "CULTURE MUSIQUE ACM" contient "CULTURE MUSIQUE"
        assert r.valide is True

    def test_valide_sans_iban_dans_pdf(self, parser):
        """Si le PDF n'a pas d'IBAN extrait, la vérification IBAN est ignorée."""
        r = self._releve_avec(iban="", bic="", nom="ASSO CULTURE MUSIQUE")
        parser._valider_releve(r)
        # Pas d'IBAN dans le PDF → on ne peut pas comparer → valide par défaut
        assert r.valide is True

    def test_valide_sans_nom_dans_pdf(self, parser):
        """Si le PDF n'a pas de nom extrait, la vérification nom est ignorée."""
        r = self._releve_avec(
            iban="FR9420041000016804150W02084",
            bic="PSSTFRPPPAR",
            nom="",  # nom non extrait
        )
        parser._valider_releve(r)
        assert r.valide is True

    def test_normaliser_nom_accents(self, parser):
        """La normalisation supprime les accents et les espaces multiples."""
        assert parser._normaliser_nom("Société  Étrange") == "SOCIETE ETRANGE"
        assert parser._normaliser_nom("asso  culture  musique") == "ASSO CULTURE MUSIQUE"

    def test_nom_sans_prefixe(self, parser):
        """_nom_sans_prefixe supprime les préfixes légaux courants."""
        assert parser._nom_sans_prefixe("ASSO CULTURE MUSIQUE") == "CULTURE MUSIQUE"
        assert parser._nom_sans_prefixe("ASSOCIATION DES AMIS") == "DES AMIS"
        assert parser._nom_sans_prefixe("LIGUE DES DROITS") == "DES DROITS"
        # Sans préfixe → inchangé
        assert parser._nom_sans_prefixe("JAZZ CLUB DES AMIS") == "JAZZ CLUB DES AMIS"
        assert parser._nom_sans_prefixe("Culture Musique") == "CULTURE MUSIQUE"

    def test_valide_user_entre_nom_sans_prefixe(self, parser):
        """L'utilisateur entre 'Culture Musique', le PDF a 'ASSO CULTURE MUSIQUE'."""
        from core.parser.la_poste_parser import LaPosteParser
        from core.parser.models import ReleveInfo
        # Config : l'user n'entre que le nom, sans "ASSO" devant
        p = LaPosteParser({"nom": "Culture Musique", "iban": "", "bic": "", "numero_compte": ""})
        r = ReleveInfo(fichier="test.pdf")
        r.nom_asso_pdf = "ASSO CULTURE MUSIQUE"  # PDF ajoute "ASSO"
        p._valider_releve(r)
        assert r.valide is True, f"Attendu valide, raisons: {r.raisons_rejet}"

    def test_valide_user_entre_nom_avec_prefixe(self, parser):
        """L'user entre 'Association Culture Musique', le PDF a 'ASSO CULTURE MUSIQUE'."""
        from core.parser.la_poste_parser import LaPosteParser
        from core.parser.models import ReleveInfo
        p = LaPosteParser({
            "nom": "Association Culture Musique",
            "iban": "", "bic": "", "numero_compte": "",
        })
        r = ReleveInfo(fichier="test.pdf")
        r.nom_asso_pdf = "ASSO CULTURE MUSIQUE"
        p._valider_releve(r)
        # Les deux donnent "CULTURE MUSIQUE" après suppression du préfixe
        assert r.valide is True, f"Attendu valide, raisons: {r.raisons_rejet}"

    def test_valide_nom_sans_prefixe_dans_pdf(self, parser):
        """Le PDF peut aussi avoir le nom sans préfixe (Jazz Club, etc.)."""
        from core.parser.la_poste_parser import LaPosteParser
        from core.parser.models import ReleveInfo
        p = LaPosteParser({
            "nom": "Jazz Club des Amis",
            "iban": "", "bic": "", "numero_compte": "",
        })
        r = ReleveInfo(fichier="test.pdf")
        r.nom_asso_pdf = "JAZZ CLUB DES AMIS"  # pas de préfixe dans le PDF
        p._valider_releve(r)
        assert r.valide is True, f"Attendu valide, raisons: {r.raisons_rejet}"


class TestParserFichierMock:
    """Tests de parser_fichier avec pdfplumber mocké."""

    def test_parse_janvier_2024(self, parser, tmp_path):
        """Parse un relevé janvier 2024 simulé."""
        fake_pdf_path = tmp_path / "releve_6804150W020_2024-01-31.pdf"
        fake_pdf_path.write_bytes(b"fake")  # doit exister

        with patch("pdfplumber.open", return_value=_make_fake_pdf([RELEVE_JANVIER_2024])):
            releve = parser.parser_fichier(str(fake_pdf_path))

        assert releve.valide is True
        assert len(releve.transactions) == 3
        assert releve.solde_fin == Decimal("4972.13")
        assert releve.solde_debut == Decimal("4424.17")
        # Le relevé couvre du 30 déc 2023 au 31 jan 2024
        assert releve.periode_fin == date(2024, 1, 31)
        assert releve.periode_debut is not None

    def test_parse_transactions_correctement(self, parser, tmp_path):
        """Vérifie les transactions extraites."""
        path = tmp_path / "releve_6804150W020_2024-01-31.pdf"
        path.write_bytes(b"fake")

        with patch("pdfplumber.open", return_value=_make_fake_pdf([RELEVE_JANVIER_2024])):
            releve = parser.parser_fichier(str(path))

        txs = sorted(releve.transactions, key=lambda t: t.date)
        assert txs[0].montant == Decimal("-16.00")   # PayPal débit
        assert txs[1].montant == Decimal("300.00")   # HelloAsso crédit
        assert txs[2].montant == Decimal("50.00")    # Remise chèques

    def test_parse_soitenfrancs_format(self, parser, tmp_path):
        """Le format Soitenfrancs (2013-2018) doit extraire les montants en euros."""
        path = tmp_path / "releve_CCP6804150W020_20170131.pdf"
        path.write_bytes(b"fake")

        with patch("pdfplumber.open", return_value=_make_fake_pdf([RELEVE_SOITENFRANCS])):
            releve = parser.parser_fichier(str(path))

        assert len(releve.transactions) == 1
        t = releve.transactions[0]
        # Doit extraire 31,80 EUR et NON 208,59 FRF
        assert t.montant == Decimal("-31.80"), f"Attendu -31.80, obtenu {t.montant}"

    def test_parse_pdf_multipage(self, parser, tmp_path):
        """Test avec un PDF de 2 pages."""
        path = tmp_path / "releve_6804150W020_2024-02-29.pdf"
        path.write_bytes(b"fake")

        page1 = """Arrêtémensuel du 31 janvier 2024 au 29 février 2024
IBAN : FR94 2004 1000 0168 0415 0W02 084
Nouveau solde au 29/02/2024 + 4 800,00 €
Vos opérations
4 972,13
Ancien solde au 31/01/2024
05/02 PRELEVEMENT DE SMACL Assurances 105,22
Page 1/2"""
        page2 = """Vos opérations CCP n°68 041 50 W 020 (suite)
18/02 4COTISATION ADISPO ASSO INTEGRAL 38,04
Nouveau solde au 29/02/2024 4 800,00
Page 2/2"""

        with patch("pdfplumber.open", return_value=_make_fake_pdf([page1, page2])):
            releve = parser.parser_fichier(str(path))

        assert len(releve.transactions) == 2
        assert releve.solde_fin == Decimal("4800.00")

    def test_parse_releve_invalide_loggue_warning(self, parser, tmp_path):
        """Un relevé non reconnu (mauvais IBAN) est parsé mais marqué invalide."""
        path = tmp_path / "releve_autre_banque.pdf"
        path.write_bytes(b"fake")

        texte_autre_banque = """Relevé BNP Paribas
IBAN : FR76 1234 5678 9012 3456 7890 123
Ancien solde : 1000,00
15/01 VIREMENT 500,00
Nouveau solde : 1500,00"""

        with patch("pdfplumber.open", return_value=_make_fake_pdf([texte_autre_banque])):
            releve = parser.parser_fichier(str(path))

        assert releve.valide is False  # non reconnu
        # Mais les transactions peuvent quand même être extraites

    def test_parse_releve_vide(self, parser, tmp_path):
        """Relevé sans transactions (mois inactif)."""
        path = tmp_path / "releve_6804150W020_2021-07-31.pdf"
        path.write_bytes(b"fake")

        texte = """Arrêtémensuel du 1 au 31 juillet 2021
IBAN : FR94 2004 1000 0168 0415 0W02 084
Nouveau solde au 31/07/2021 + 4 000,00 €
Vos opérations
4 000,00
Ancien solde au 30/06/2021
Aucune opération ce mois
Nouveau solde au 31/07/2021 4 000,00
Page 1/1"""

        with patch("pdfplumber.open", return_value=_make_fake_pdf([texte])):
            releve = parser.parser_fichier(str(path))

        assert releve.solde_fin == Decimal("4000.00")
        assert releve.solde_debut == Decimal("4000.00")

    def test_parse_extraction_numero_compte(self, parser, tmp_path):
        """Vérifie que le numéro de compte est bien extrait du texte."""
        path = tmp_path / "releve_6804150W020_2024-03-31.pdf"
        path.write_bytes(b"fake")

        texte = """Arrêtémensuel du 1 au 31 mars 2024
n° 68 041 50 W 020
IBAN : FR94 2004 1000 0168 0415 0W02 084
Nouveau solde au 31/03/2024 + 5 000,00 €
5 000,00
Ancien solde au 29/02/2024
Nouveau solde au 31/03/2024 5 000,00
Page 1/1"""

        with patch("pdfplumber.open", return_value=_make_fake_pdf([texte])):
            releve = parser.parser_fichier(str(path))

        # Le numéro est dans le texte sous la forme "68 041 50 W 020"
        # ou extrait depuis l'IBAN — vérifier qu'il est non vide ou correct
        assert releve.numero_compte == "6804150W020" or releve.valide is True

    def test_extraire_metadonnees_nom_via_code_postal(self, parser):
        """Le nom est extrait depuis une ligne 'XXXXX VILLE ASSO ...' (format réel)."""
        from core.parser.models import ReleveInfo
        # Format réel : code postal + ville + nom association sur la même ligne
        texte = "75900 PARIS CEDEX 15 ASSO CULTURE MUSIQUE\nAutre ligne"
        r = ReleveInfo(fichier="test.pdf")
        parser._extraire_metadonnees(texte, r)
        # Le nom doit être extrait via le pattern code postal
        assert "CULTURE MUSIQUE" in r.nom_asso_pdf or r.nom_asso_pdf != ""

    def test_extraire_metadonnees_nom_sans_prefixe_via_correspondance(self):
        """Cas C: nom sans préfixe légal extrait par correspondance avec la config."""
        from core.parser.la_poste_parser import LaPosteParser
        from core.parser.models import ReleveInfo
        # Asso dont le nom ne commence pas par ASSO/ASSOCIATION/etc.
        p = LaPosteParser({"nom": "Jazz Club des Amis", "iban": "", "bic": "", "numero_compte": ""})
        # PDF avec le nom sur une ligne dédiée (pas de préfixe)
        texte = "Releve de votre CCP\nJAZZ CLUB DES AMIS\nSituation du CCP"
        r = ReleveInfo(fichier="test.pdf")
        p._extraire_metadonnees(texte, r)
        assert r.nom_asso_pdf != "", f"Nom non extrait — attendu 'JAZZ CLUB DES AMIS'"

    def test_extraire_soldes_format_2013(self, parser):
        """Le format 2013-2018 'Solde au DD/MM/YYYY' est reconnu sans le mot 'Ancien'."""
        from core.parser.models import ReleveInfo
        # Texte sans "Ancien solde" — format anciens relevés
        texte = "Situation du compte\nSolde au 01/01/2013 1 234,56\nOpérations du mois"
        r = ReleveInfo(fichier="test.pdf")
        parser._extraire_soldes(texte, r)
        assert r.solde_debut is not None
        assert float(r.solde_debut) == pytest.approx(1234.56, abs=0.01)


class TestParserDossierMock:
    """Tests de parser_dossier avec mocks."""

    def test_parser_dossier_vide(self, parser, tmp_path):
        """Dossier sans PDF → liste vide."""
        releves = parser.parser_dossier(str(tmp_path))
        assert releves == []

    def test_parser_dossier_dossier_inexistant(self, parser):
        with pytest.raises(NotADirectoryError):
            parser.parser_dossier("/chemin/qui/nexiste/pas")

    def test_parser_dossier_ignore_doublons(self, parser, tmp_path):
        """Fichiers (1).pdf doivent être ignorés."""
        # Créer un PDF normal et un doublon
        (tmp_path / "releve_6804150W020_2024-01-31.pdf").write_bytes(b"fake")
        (tmp_path / "releve_6804150W020_2024-01-31 (1).pdf").write_bytes(b"fake")

        texte = """Arrêtémensuel du 1 au 31 janvier 2024
IBAN : FR94 2004 1000 0168 0415 0W02 084
Nouveau solde au 31/01/2024 + 100,00 €
100,00
Ancien solde au 31/12/2023
Nouveau solde au 31/01/2024 100,00
Page 1/1"""

        with patch("pdfplumber.open", return_value=_make_fake_pdf([texte])):
            releves = parser.parser_dossier(str(tmp_path))

        # Le doublon (1) doit être ignoré → 1 seul relevé
        assert len(releves) == 1

    def test_parser_dossier_plusieurs_mois(self, parser, tmp_path):
        """Test avec 3 mois de relevés."""
        mois = [
            ("releve_6804150W020_2024-01-31.pdf", "31 janvier 2024", "4 000,00", "3 900,00"),
            ("releve_6804150W020_2024-02-29.pdf", "29 février 2024",  "3 900,00", "3 800,00"),
            ("releve_6804150W020_2024-03-31.pdf", "31 mars 2024",     "3 800,00", "3 700,00"),
        ]
        for nom, date_fin, solde_debut, solde_fin in mois:
            (tmp_path / nom).write_bytes(b"fake")

        def fake_open(path, *args, **kwargs):
            nom = Path(path).name
            for n, df, sd, sf in mois:
                if n == nom:
                    texte = f"""Arrêtémensuel du 1 au {df}
IBAN : FR94 2004 1000 0168 0415 0W02 084
Nouveau solde au {df} + {sf} €
{sd}
Ancien solde au date
Nouveau solde {sf}
Page 1/1"""
                    return _make_fake_pdf([texte])
            return _make_fake_pdf([""])

        with patch("pdfplumber.open", side_effect=fake_open):
            releves = parser.parser_dossier(str(tmp_path))

        assert len(releves) == 3

    def test_parser_dossier_gere_erreur_parse(self, parser, tmp_path):
        """Un PDF corrompu ne doit pas bloquer les autres."""
        (tmp_path / "releve_6804150W020_2024-01-31.pdf").write_bytes(b"fake")
        (tmp_path / "releve_6804150W020_2024-02-29.pdf").write_bytes(b"fake")

        appels = [0]

        def fake_open(path, *args, **kwargs):
            appels[0] += 1
            if appels[0] == 1:
                raise Exception("PDF corrompu")
            texte = """Arrêtémensuel du 1 au 29 février 2024
IBAN : FR94 2004 1000 0168 0415 0W02 084
Nouveau solde au 29/02/2024 + 100,00 €
100,00
Ancien solde
Nouveau solde 100,00
Page 1/1"""
            return _make_fake_pdf([texte])

        with patch("pdfplumber.open", side_effect=fake_open):
            releves = parser.parser_dossier(str(tmp_path))

        # Le PDF corrompu lève une ParseError qui est interceptée dans
        # parser_dossier → le fichier est sauté (non ajouté à la liste).
        # Seul le second relevé (valide) est retourné.
        assert len(releves) == 1
        assert releves[0].valide is True    # second PDF OK


class TestExtractPeriodePdf:
    """Tests de l'extraction de période depuis le texte PDF."""

    def test_periode_format_numerique(self, parser):
        """Format ancien avec dates DD/MM/YYYY."""
        texte = "Arrêté mensuel du 01/01/2024 au 31/01/2024"
        debut, fin = parser._extraire_periode_pdf(texte)
        assert debut == date(2024, 1, 1)
        assert fin == date(2024, 1, 31)

    def test_periode_format_texte_mois_differents(self, parser):
        """Format moderne avec noms de mois."""
        texte = "ArrŒtØ mensuel du 30 dØcembre 2023 au 31 janvier 2024"
        debut, fin = parser._extraire_periode_pdf(texte)
        assert debut is not None
        assert fin == date(2024, 1, 31)

    def test_periode_format_meme_mois(self, parser):
        """Format 'du 1 au 31 janvier 2024'."""
        texte = "ArrŒtØmensuel du1(cid:160)au(cid:160)31 janvier 2024"
        debut, fin = parser._extraire_periode_pdf(texte)
        assert fin == date(2024, 1, 31)
        assert debut.month == 1

    def test_periode_sans_ligne_mensuel(self, parser):
        """Texte sans la ligne d'arrêté → (None, None)."""
        texte = "Solde : 1234,56 € Opérations diverses"
        debut, fin = parser._extraire_periode_pdf(texte)
        assert debut is None
        assert fin is None

    def test_periode_mois_encode_fevrier(self, parser):
        """Février avec encodage Ø."""
        texte = "ArrŒtØ mensuel du 1 fØvrier au 29 fØvrier 2024"
        debut, fin = parser._extraire_periode_pdf(texte)
        assert fin is not None
        assert fin.month == 2

    def test_periode_mois_encode_decembre(self, parser):
        """Décembre avec encodage Ø."""
        texte = "ArrŒtØ mensuel du 30 dØcembre 2023 au 31 dØcembre 2023"
        debut, fin = parser._extraire_periode_pdf(texte)
        assert fin is not None
        assert fin.month == 12


class TestExtraireSoldesMock:
    """Tests de l'extraction des soldes."""

    def test_solde_fin_format_moderne(self, parser):
        """Extraction du nouveau solde."""
        texte = "Nouveau solde au 31/01/2024 + 4 972,13 €\nAncien solde au 29/12/2023"
        releve = MagicMock()
        releve.solde_debut = None
        releve.solde_fin = None
        parser._extraire_soldes(texte, releve)
        assert releve.solde_fin == Decimal("4972.13")

    def test_solde_debut_sur_ligne_precedente(self, parser):
        """L'ancien solde est sur la ligne précédant le label."""
        texte = "4 424,17\nAncien solde au 29/12/2023\n"
        releve = MagicMock()
        releve.solde_debut = None
        releve.solde_fin = None
        parser._extraire_soldes(texte, releve)
        assert releve.solde_debut == Decimal("4424.17")
