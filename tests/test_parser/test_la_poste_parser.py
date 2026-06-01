"""Tests du parseur La Banque Postale."""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.parser.la_poste_parser import LaPosteParser, _normaliser_pdf_texte, _parse_montant
from core.parser.models import ParseError


class TestParseMontant:
    """Tests de la fonction utilitaire _parse_montant."""

    @pytest.mark.parametrize(
        "texte,attendu",
        [
            ("100,00", Decimal("100.00")),
            ("1 234,56", Decimal("1234.56")),
            ("38,04", Decimal("38.04")),
            ("4 972,13", Decimal("4972.13")),
            ("+ 4 972,13", Decimal("4972.13")),
            ("  16,00  ", Decimal("16.00")),
        ],
    )
    def test_montants_valides(self, texte, attendu):
        assert _parse_montant(texte) == attendu

    @pytest.mark.parametrize("texte", ["", "abc", "N/A", None])
    def test_montants_invalides(self, texte):
        assert _parse_montant(texte) is None


class TestNormalisePdfTexte:
    """Tests de normalisation du texte PDF."""

    def test_suppression_cid(self):
        texte = "ArrŒtØ mensuel du1(cid:160)au(cid:160)31 janvier 2024"
        result = _normaliser_pdf_texte(texte)
        assert "(cid:" not in result

    def test_remplacement_o_tilde(self):
        texte = "fØvrier dØcembre"
        result = _normaliser_pdf_texte(texte)
        assert "fevrier" in result
        assert "decembre" in result

    def test_remplacement_beta(self):
        texte = "aoßt"
        result = _normaliser_pdf_texte(texte)
        assert "aout" in result

    def test_minuscules(self):
        result = _normaliser_pdf_texte("JANVIER FEVRIER")
        assert result == "janvier fevrier"


class TestLaPosteParser:
    """Tests du parseur PDF La Banque Postale."""

    def test_init(self, config_asso):
        p = LaPosteParser(config_asso)
        assert p.numero_compte == "6804150W020"
        assert "FR" in p.iban

    def test_annee_depuis_nom_nouveau_format(self, parser):
        assert parser._annee_depuis_nom("releve_6804150W020_2024-01-31.pdf") == 2024
        assert parser._annee_depuis_nom("releve_6804150W020_2025-12-31.pdf") == 2025

    def test_annee_depuis_nom_ancien_format(self, parser):
        assert parser._annee_depuis_nom("releve_CCP6804150W020_20240131.pdf") == 2024

    def test_annee_depuis_nom_fallback(self, parser):
        from datetime import datetime

        annee_courante = datetime.now().year
        assert parser._annee_depuis_nom("releve_sans_date.pdf") == annee_courante

    def test_mois_depuis_nom_nouveau_format(self, parser):
        assert parser._mois_depuis_nom("releve_6804150W020_2024-09-29.pdf") == 9
        assert parser._mois_depuis_nom("releve_6804150W020_2024-12-31.pdf") == 12

    def test_mois_depuis_nom_ancien_format(self, parser):
        assert parser._mois_depuis_nom("releve_CCP6804150W020_20240131.pdf") == 1
        assert parser._mois_depuis_nom("releve_CCP6804150W020_20231030.pdf") == 10

    def test_mois_depuis_nom_inconnu(self, parser):
        assert parser._mois_depuis_nom("releve_sans_date.pdf") is None

    def test_est_credit_virement_de(self, parser):
        assert parser._est_credit("VIREMENT DE STRIPE HELLOASSO") is True

    def test_est_credit_virement_instantane_de(self, parser):
        assert parser._est_credit("VIREMENT INSTANTANE DE M NADJIB BEN EL KADI") is True

    def test_est_debit_prelevement(self, parser):
        assert parser._est_credit("PRELEVEMENT DE PayPal Europe") is False

    def test_est_debit_virement_pour(self, parser):
        assert parser._est_credit("VIREMENT POUR REGIE DE LA MAIRIE PARIS") is False

    def test_est_debit_virement_instantane_a(self, parser):
        assert parser._est_credit("VIREMENT INSTANTANE A REVERB TECHNIC") is False

    def test_est_credit_versement_effectue(self, parser):
        assert parser._est_credit("789310 VERSEMENT EFFECTUE LE 090725 A VERSAILLES") is True

    def test_est_credit_annulation_prelevement(self, parser):
        assert parser._est_credit("ANNULATION PRELEVEMENT DE SMACL Assurances") is True

    def test_est_credit_remise_cheques(self, parser):
        assert parser._est_credit("REMISE DE CHEQUES DU 04/01/2024") is True

    def test_est_debit_cotisation_adispo(self, parser):
        assert parser._est_credit("COTISATION ADISPO ASSO INTEGRAL") is False

    def test_extraction_montant_simple(self, parser):
        debit, credit, libelle = parser._extraire_montants("PRELEVEMENT DE PayPal 16,00")
        assert debit == Decimal("16.00")
        assert credit is None
        assert "16,00" not in libelle

    def test_extraction_montant_credit(self, parser):
        debit, credit, libelle = parser._extraire_montants("VIREMENT DE STRIPE HELLOASSO 300,00")
        assert credit == Decimal("300.00")
        assert debit is None

    def test_extraction_montant_grand(self, parser):
        debit, credit, libelle = parser._extraire_montants(
            "REMISE DE CHEQUES DU 13/01/2024 1 500,00"
        )
        assert credit == Decimal("1500.00")

    def test_pas_extraction_numero_cheque(self, parser):
        """Le numéro de chèque 8740001 ne doit pas être extrait comme montant."""
        debit, credit, libelle = parser._extraire_montants("CHEQUE N(cid:176) 8740001 500,00")
        # Doit extraire 500,00 et non 8740001500,00
        assert debit == Decimal("500.00") or credit == Decimal("500.00")
        if debit:
            assert debit < Decimal("1000")
        if credit:
            assert credit < Decimal("1000")

    def test_est_ligne_ignoree(self, parser):
        assert parser._est_ligne_ignoree("TotaldesopØrations 21,00") is True
        assert parser._est_ligne_ignoree("Ancien solde au 31/12/2023") is True
        assert parser._est_ligne_ignoree("LA BANQUE POSTALE") is True

    def test_est_ligne_non_ignoree(self, parser):
        assert parser._est_ligne_ignoree("03/01 PRELEVEMENT DE PayPal 16,00") is False

    def test_fichier_introuvable(self, parser):
        with pytest.raises(FileNotFoundError):
            parser.parser_fichier("/chemin/inexistant.pdf")

    @pytest.mark.integration
    def test_parser_pdf_reel(self, parser, pdf_test_path):
        """Test d'intégration sur un vrai PDF (nécessite le disque E)."""
        releve = parser.parser_fichier(str(pdf_test_path))
        assert releve.valide is True
        assert len(releve.transactions) > 0
        assert releve.solde_fin is not None
        # Vérification que les montants sont raisonnables
        for t in releve.transactions:
            assert abs(float(t.montant)) < 50_000, f"Montant aberrant : {t.montant} — {t.libelle}"


class TestExtractLignesPage:
    """Tests de l'extraction de lignes de transactions."""

    def test_extraction_transaction_simple(self, parser):
        texte = (
            "Vos opérations\n"
            "Date OpØration DØbit CrØdit\n"
            "03/01 PRELEVEMENT DE PayPal 16,00\n"
            "l. et Cie S.C.A REF : 12345 PAYPAL\n"
            "08/01 REMISE DE CHEQUES DU 04/01/2024 50,00\n"
        )
        lignes = parser._extraire_lignes_page(texte, 2024, 1)
        assert len(lignes) == 2
        assert lignes[0]["debit"] == Decimal("16.00")
        assert lignes[1]["credit"] == Decimal("50.00")

    def test_libelle_multilignes(self, parser):
        texte = (
            "03/01 PRELEVEMENT DE PayPal Europe S.a.r. 16,00\n"
            "l. et Cie S.C.A REF : 103158 103158/PAYPAL\n"
            "IDENT : LU96ZZZ MANDAT : 5G82224\n"
        )
        lignes = parser._extraire_lignes_page(texte, 2024, 1)
        assert len(lignes) == 1
        assert "l. et Cie" in lignes[0]["libelle"]

    def test_date_correcte(self, parser):
        texte = "15/06 VIREMENT DE STRIPE HELLOASSO 300,00\n"
        lignes = parser._extraire_lignes_page(texte, 2024, 6)
        assert len(lignes) == 1
        assert lignes[0]["date"] == date(2024, 6, 15)
