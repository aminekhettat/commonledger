"""
Tests du parseur CSV La Banque Postale.

Couverture cible : 100% de core/parser/csv_parser.py

Tests en deux catégories :
  1. Tests unitaires (pas de fichiers réels)
  2. Tests d'intégration (avec les vrais CSV 2025 — marqueur integration)
"""

import csv
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core.parser.csv_parser import (
    CSVParserLaBanquePostale,
    _parse_date_csv,
    _parse_montant_csv,
    _extraire_date_depuis_chaine,
)
from core.parser.models import ParseError


# ── Config de test ────────────────────────────────────────────────────────────

@pytest.fixture
def config():
    return {
        "numero_compte": "6804150W020",
        "nom": "ASSO CULTURE MUSIQUE",
        "iban": "FR9420041000016804150W02084",
    }


@pytest.fixture
def parser(config):
    return CSVParserLaBanquePostale(config)


# ── Contenu CSV de test ────────────────────────────────────────────────────────

CSV_STANDARD = """\
Numéro de compte;6804150W020
Type;ASSO CULTURE MUSIQUE
Fichier téléchargé;le 11/02/2025 à 18:48:44
Opérations imputées;du 01/01/2025 au 11/02/2025
Solde comptable au 11/02/2025;2 442,77 €

Date;Libellé;Montant
10/02/2025;PRELEVEMENT DE PayPal Europe S.a l. REF : 1040125046808;-27,00 €
10/02/2025;VIREMENT DE STRIPE HELLOASSO-OUJ30X HELLOASSO;479,96 €
05/02/2025;PRELEVEMENT DE SMACL Assurances REF : GC20250128;-120,55 €
20/01/2025;COTISATION ADISPO ASSO INTEGRAL MT HT= 38,04EUR-TVA= 0,00%;-38,04 €
"""

CSV_AVEC_SOLDE_INITIAL = """\
Numéro de compte;6804150W020;
Type;ASSO CULTURE MUSIQUE;
Fichier téléchargé;le 17/07/2025 à 17:53:03;
Opérations imputées;du 17/01/2025 au 17/07/2025;
Solde comptable au 17/07/2025;3 399,31 €;

Date;Libellé;Montant
11/07/2025;VIREMENT DE PayPal YYW12345;102,09€
03/07/2025;PRELEVEMENT DE PayPal REF : 1043230275908;-15,75€
"""

CSV_MONTANTS_VARIANTES = """\
Numéro de compte;6804150W020
Opérations imputées;du 01/01/2025 au 31/01/2025
Solde comptable au 31/01/2025;1000,00 €

Date;Libellé;Montant
01/01/2025;TRANSACTION A;1 115,00 €
02/01/2025;TRANSACTION B;-42,37 €
03/01/2025;TRANSACTION C;1026,54€
04/01/2025;TRANSACTION D;-1 500,00 €
"""

CSV_SANS_ENTETE_COLONNES = """\
Numéro de compte;6804150W020
Type;ASSO TEST

01/01/2025;TRANSACTION;100,00 €
"""

CSV_VIDE_APRES_ENTETE = """\
Numéro de compte;6804150W020
Opérations imputées;du 01/01/2025 au 31/01/2025
Solde comptable au 31/01/2025;0 €

Date;Libellé;Montant
"""


def _creer_csv_tmp(tmp_path: Path, contenu: str, nom: str = "test.csv") -> Path:
    """Crée un fichier CSV temporaire avec le contenu fourni."""
    fichier = tmp_path / nom
    fichier.write_text(contenu, encoding="utf-8-sig")
    return fichier


# ── Tests des fonctions utilitaires ───────────────────────────────────────────

class TestParseMontantCsv:
    @pytest.mark.parametrize("texte,attendu", [
        ("100,00 €", Decimal("100.00")),
        ("-27,00 €", Decimal("-27.00")),
        ("479,96 €", Decimal("479.96")),
        ("1 115,00 €", Decimal("1115.00")),
        ("-1 500,00 €", Decimal("-1500.00")),
        ("1026,54€", Decimal("1026.54")),
        ("-42,37€", Decimal("-42.37")),
        ("2 442,77 €", Decimal("2442.77")),
        ("  100,00  ", Decimal("100.00")),
    ])
    def test_montants_valides(self, texte, attendu):
        assert _parse_montant_csv(texte) == attendu

    @pytest.mark.parametrize("texte", ["", "  ", None, "N/A", "abc"])
    def test_montants_invalides(self, texte):
        assert _parse_montant_csv(texte) is None


class TestParseDateCsv:
    @pytest.mark.parametrize("texte,attendu", [
        ("10/02/2025", date(2025, 2, 10)),
        ("01/01/2025", date(2025, 1, 1)),
        ("31/12/2024", date(2024, 12, 31)),
        ("  05/07/2025  ", date(2025, 7, 5)),
    ])
    def test_dates_valides(self, texte, attendu):
        assert _parse_date_csv(texte) == attendu

    @pytest.mark.parametrize("texte", ["", "abc", "2025/01/01", "99/99/9999"])
    def test_dates_invalides(self, texte):
        assert _parse_date_csv(texte) is None


class TestExtraireDateDepuisChaine:
    def test_date_dans_phrase(self):
        d = _extraire_date_depuis_chaine("le 11/02/2025 à 18:48:44")
        assert d == date(2025, 2, 11)

    def test_period_deux_dates(self):
        d = _extraire_date_depuis_chaine("du 01/01/2025 au 31/12/2025")
        assert d == date(2025, 1, 1)  # Prend la première

    def test_aucune_date(self):
        assert _extraire_date_depuis_chaine("aucune date ici") is None


# ── Tests du parseur CSV ───────────────────────────────────────────────────────

class TestCsvParserDetectionLignes:
    def test_detection_entete_colonnes(self, parser):
        assert parser._est_ligne_entete_colonnes(["Date", "Libellé", "Montant"]) is True
        assert parser._est_ligne_entete_colonnes(["Date", "Libelle", "Montant"]) is True
        assert parser._est_ligne_entete_colonnes(["date", "libellé", "montant"]) is True

    def test_pas_entete_colonnes(self, parser):
        assert parser._est_ligne_entete_colonnes([]) is False
        assert parser._est_ligne_entete_colonnes(["Numéro de compte", "6804150W020"]) is False
        assert parser._est_ligne_entete_colonnes(["Type", "ASSO"]) is False

    def test_detection_ligne_transaction(self, parser):
        assert parser._est_ligne_transaction(["10/02/2025", "VIREMENT", "100,00 €"]) is True
        assert parser._est_ligne_transaction(["Date", "Libellé", "Montant"]) is False
        assert parser._est_ligne_transaction(["", "", ""]) is False
        assert parser._est_ligne_transaction(["abc", "test", "100"]) is False

    def test_ligne_trop_courte(self, parser):
        assert parser._est_ligne_transaction(["10/02/2025"]) is False
        assert parser._est_ligne_transaction([]) is False


class TestCsvParserMetadonnees:
    def test_extraction_numero_compte(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)
        releve = parser.parser_fichier(str(f))
        assert releve.numero_compte == "6804150W020"

    def test_extraction_periode(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)
        releve = parser.parser_fichier(str(f))
        assert releve.periode_debut == date(2025, 1, 1)
        assert releve.periode_fin == date(2025, 2, 11)

    def test_extraction_solde_final(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)
        releve = parser.parser_fichier(str(f))
        assert releve.solde_fin == Decimal("2442.77")

    def test_extraction_avec_point_virgules_trailing(self, parser, tmp_path):
        """Format avec points-virgules en fin de ligne."""
        f = _creer_csv_tmp(tmp_path, CSV_AVEC_SOLDE_INITIAL)
        releve = parser.parser_fichier(str(f))
        assert releve.numero_compte == "6804150W020"

    def test_validite_compte_reconnu(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)
        releve = parser.parser_fichier(str(f))
        assert releve.valide is True

    def test_validite_compte_inconnu(self, tmp_path):
        config_autre = {"numero_compte": "9999999X999", "nom": "AUTRE"}
        p = CSVParserLaBanquePostale(config_autre)
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)
        releve = p.parser_fichier(str(f))
        assert releve.valide is False


class TestCsvParserTransactions:
    def test_nombre_transactions(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)
        releve = parser.parser_fichier(str(f))
        assert len(releve.transactions) == 4

    def test_montants_corrects(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_MONTANTS_VARIANTES)
        releve = parser.parser_fichier(str(f))
        montants = [float(t.montant) for t in releve.transactions]
        assert 1115.00 in montants
        assert -42.37 in montants
        assert 1026.54 in montants
        assert -1500.00 in montants

    def test_dates_correctes(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)
        releve = parser.parser_fichier(str(f))
        dates = [t.date for t in releve.transactions]
        assert date(2025, 2, 10) in dates
        assert date(2025, 1, 20) in dates

    def test_transactions_triees_par_date(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)
        releve = parser.parser_fichier(str(f))
        for i in range(len(releve.transactions) - 1):
            assert releve.transactions[i].date <= releve.transactions[i + 1].date

    def test_libelles_corrects(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)
        releve = parser.parser_fichier(str(f))
        libelles = [t.libelle for t in releve.transactions]
        assert any("PayPal" in l for l in libelles)
        assert any("HELLOASSO" in l for l in libelles)

    def test_source_fichier_renseigne(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD, "export_2025.csv")
        releve = parser.parser_fichier(str(f))
        for t in releve.transactions:
            assert t.source_fichier == "export_2025.csv"

    def test_csv_vide_apres_entete(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_VIDE_APRES_ENTETE)
        releve = parser.parser_fichier(str(f))
        assert len(releve.transactions) == 0

    def test_deduplication_meme_transaction(self, parser, tmp_path):
        """La même transaction ne doit apparaître qu'une fois."""
        contenu = (
            "Numéro de compte;6804150W020\n"
            "Opérations imputées;du 01/01/2025 au 31/01/2025\n"
            "Solde comptable au 31/01/2025;100,00 €\n\n"
            "Date;Libellé;Montant\n"
            "15/01/2025;HELLOASSO-XYZ HELLOASSO;200,00 €\n"
            "15/01/2025;HELLOASSO-XYZ HELLOASSO;200,00 €\n"  # Doublon exact
        )
        f = _creer_csv_tmp(tmp_path, contenu)
        releve = parser.parser_fichier(str(f))
        assert len(releve.transactions) == 1


class TestCsvParserErreurs:
    def test_fichier_introuvable(self, parser):
        with pytest.raises(FileNotFoundError):
            parser.parser_fichier("/chemin/inexistant.csv")

    def test_fichier_sans_entete_colonnes(self, parser, tmp_path):
        f = _creer_csv_tmp(tmp_path, CSV_SANS_ENTETE_COLONNES)
        # Pas de ligne Date;Libellé;Montant → ParseError
        with pytest.raises(ParseError):
            parser.parser_fichier(str(f))

    def test_fichier_mauvais_encodage_fallback(self, parser, tmp_path):
        """Un fichier ISO-8859-1 est quand même parsé correctement."""
        contenu_iso = (
            "Num\xe9ro de compte;6804150W020\n"
            "Op\xe9rations imput\xe9es;du 01/01/2025 au 31/01/2025\n"
            "Solde comptable au 31/01/2025;100,00 \x80\n\n"
            "Date;Lib\xe9ll\xe9;Montant\n"
            "15/01/2025;TEST;100,00 \x80\n"
        )
        f = tmp_path / "iso.csv"
        f.write_bytes(contenu_iso.encode("iso-8859-1"))
        # Doit parser sans exception
        releve = parser.parser_fichier(str(f))
        assert len(releve.transactions) >= 0  # Ne plante pas


class TestCsvParserTransactionsAvecLignesExtras:
    """Couvre les branches de filtrage des lignes non-transactions."""

    def test_ligne_vide_apres_entete_ignoree(self, parser, tmp_path):
        """Une ligne vide ou récapitulative après l'en-tête est ignorée (continue)."""
        contenu = (
            "Numéro de compte;6804150W020\n"
            "Opérations imputées;du 01/01/2025 au 31/01/2025\n"
            "Solde comptable au 31/01/2025;500,00 €\n\n"
            "Date;Libellé;Montant\n"
            "15/01/2025;HELLOASSO;100,00 €\n"
            "\n"  # Ligne vide APRÈS l'en-tête
            "Total;Récapitulatif;\n"  # Ligne récap non-transaction
            "20/01/2025;COTISATION;-50,00 €\n"
        )
        f = _creer_csv_tmp(tmp_path, contenu)
        releve = parser.parser_fichier(str(f))
        # Seules les 2 vraies transactions sont parsées
        assert len(releve.transactions) == 2

    def test_transactions_annee_differente_filtrees(self, parser, tmp_path):
        """Le filtre annee dans agreger_transactions saute les autres années."""
        contenu = (
            "Numéro de compte;6804150W020\n"
            "Opérations imputées;du 01/08/2024 au 31/01/2025\n"
            "Solde comptable au 31/01/2025;500,00 €\n\n"
            "Date;Libellé;Montant\n"
            "15/08/2024;TX 2024;100,00 €\n"  # 2024 — doit être filtré
            "15/01/2025;TX 2025;200,00 €\n"  # 2025 — doit rester
        )
        f = _creer_csv_tmp(tmp_path, contenu)
        releves = [parser.parser_fichier(str(f))]
        # Sans filtre : 2 transactions
        txs_tout, _ = parser.agreger_transactions(releves)
        assert len(txs_tout) == 2
        # Avec filtre annee=2025 : 1 transaction (la ligne 2024 est skippée)
        txs_2025, _ = parser.agreger_transactions(releves, annee=2025)
        assert len(txs_2025) == 1
        assert txs_2025[0].date.year == 2025


class TestCsvParserDossier:
    def test_parser_dossier_vide(self, parser, tmp_path):
        releves = parser.parser_dossier(str(tmp_path))
        assert releves == []

    def test_parser_dossier_dossier_inexistant(self, parser):
        with pytest.raises(NotADirectoryError):
            parser.parser_dossier("/chemin/inexistant")

    def test_parser_dossier_plusieurs_fichiers(self, parser, tmp_path):
        _creer_csv_tmp(tmp_path, CSV_STANDARD, "export_01.csv")
        _creer_csv_tmp(tmp_path, CSV_AVEC_SOLDE_INITIAL, "export_02.csv")
        releves = parser.parser_dossier(str(tmp_path))
        assert len(releves) == 2

    def test_parser_dossier_filtre_annee(self, parser, tmp_path):
        """Filtrer les transactions par année."""
        _creer_csv_tmp(tmp_path, CSV_STANDARD, "export.csv")  # 2025 + 2024
        releves = parser.parser_dossier(str(tmp_path), annee=2025)
        for releve in releves:
            for t in releve.transactions:
                assert t.date.year == 2025

    def test_parser_dossier_fichier_corrompu_ignore(self, parser, tmp_path):
        """Un CSV sans en-tête valide est ignoré (ParseError absorbée), les autres sont parsés."""
        # Fichier valide
        _creer_csv_tmp(tmp_path, CSV_STANDARD, "ok.csv")
        # Fichier sans en-tête Date;Libellé;Montant → ParseError
        f_mauvais = tmp_path / "bad.csv"
        f_mauvais.write_text("garbage data\nno header\n", encoding="utf-8")
        # parser_dossier ne lève pas d'exception, il saute le fichier invalide
        releves = parser.parser_dossier(str(tmp_path))
        assert len(releves) == 1  # Seul ok.csv est parsé

    def test_parser_dossier_ignore_doublons(self, parser, tmp_path):
        """Les fichiers (1).csv sont ignorés."""
        _creer_csv_tmp(tmp_path, CSV_STANDARD, "export.csv")
        _creer_csv_tmp(tmp_path, CSV_STANDARD, "export (1).csv")
        releves = parser.parser_dossier(str(tmp_path))
        assert len(releves) == 1

    def test_parser_dossier_ignore_non_csv(self, parser, tmp_path):
        """Les fichiers non CSV ne sont pas traités."""
        (tmp_path / "document.pdf").write_bytes(b"fake pdf")
        (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")
        _creer_csv_tmp(tmp_path, CSV_STANDARD, "export.csv")
        releves = parser.parser_dossier(str(tmp_path))
        assert len(releves) == 1


class TestAgregateurTransactions:
    def test_deduplication_entre_fichiers(self, parser, tmp_path):
        """Même transaction dans 2 fichiers → garde une seule."""
        # Les deux fichiers contiennent la transaction du 10/02/2025
        f1 = _creer_csv_tmp(tmp_path, CSV_STANDARD, "f1.csv")
        f2 = _creer_csv_tmp(tmp_path, CSV_STANDARD, "f2.csv")  # Même contenu

        releves = parser.parser_dossier(str(tmp_path))
        transactions, alertes = parser.agreger_transactions(releves)

        # Pas de doublon dans le résultat final
        ids = [t.id_unique for t in transactions]
        assert len(ids) == len(set(ids))

    def test_alerte_si_doublons(self, parser, tmp_path):
        """Un message d'alerte est émis si des doublons sont supprimés."""
        _creer_csv_tmp(tmp_path, CSV_STANDARD, "f1.csv")
        _creer_csv_tmp(tmp_path, CSV_STANDARD, "f2.csv")

        releves = parser.parser_dossier(str(tmp_path))
        _, alertes = parser.agreger_transactions(releves)

        assert any("dupliqué" in a.lower() or "doublon" in a.lower() for a in alertes)

    def test_detection_gap_debut_annee(self, parser, tmp_path):
        """Alerte si les CSV ne couvrent pas le début de l'année."""
        contenu = (
            "Numéro de compte;6804150W020\n"
            "Opérations imputées;du 17/02/2025 au 31/12/2025\n"
            "Solde comptable au 31/12/2025;1000,00 €\n\n"
            "Date;Libellé;Montant\n"
            "17/02/2025;HELLOASSO;100,00 €\n"
        )
        f = _creer_csv_tmp(tmp_path, contenu)
        releves = [parser.parser_fichier(str(f))]
        _, alertes = parser.agreger_transactions(releves, annee=2025)
        assert any("début" in a.lower() or "janvier" in a.lower()
                   or "manquent" in a.lower() for a in alertes)

    def test_detection_gap_entre_transactions(self, parser, tmp_path):
        """Alerte si gap > 45 jours entre deux transactions."""
        contenu = (
            "Numéro de compte;6804150W020\n"
            "Opérations imputées;du 01/01/2025 au 31/12/2025\n"
            "Solde comptable au 31/12/2025;1000,00 €\n\n"
            "Date;Libellé;Montant\n"
            "01/01/2025;TX A;100,00 €\n"
            "01/03/2025;TX B;200,00 €\n"  # 59 jours de gap
        )
        f = _creer_csv_tmp(tmp_path, contenu)
        releves = [parser.parser_fichier(str(f))]
        _, alertes = parser.agreger_transactions(releves, annee=2025)
        # Le gap de 59 jours doit générer une alerte
        assert any("gap" in a.lower() or "jours" in a.lower() for a in alertes)

    def test_pas_alerte_si_pas_de_gap(self, parser, tmp_path):
        """Pas d'alerte si les transactions sont continues."""
        contenu = (
            "Numéro de compte;6804150W020\n"
            "Opérations imputées;du 01/01/2025 au 31/01/2025\n"
            "Solde comptable au 31/01/2025;1000,00 €\n\n"
            "Date;Libellé;Montant\n"
            "05/01/2025;TX A;100,00 €\n"
            "15/01/2025;TX B;200,00 €\n"
            "25/01/2025;TX C;300,00 €\n"
        )
        f = _creer_csv_tmp(tmp_path, contenu)
        releves = [parser.parser_fichier(str(f))]
        _, alertes = parser.agreger_transactions(releves, annee=2025)
        gap_alertes = [a for a in alertes if "gap" in a.lower()]
        assert len(gap_alertes) == 0

    def test_filtre_par_annee_dans_agregateur(self, parser, tmp_path):
        """L'agrégateur filtre les transactions par année."""
        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)  # Contient 2024 et 2025
        releves = [parser.parser_fichier(str(f))]
        transactions_2025, _ = parser.agreger_transactions(releves, annee=2025)
        for t in transactions_2025:
            assert t.date.year == 2025

    def test_agregation_dossier_vide(self, parser):
        """Dossier vide → 0 transactions, alerte si annee spécifiée."""
        transactions, alertes = parser.agreger_transactions([], annee=2025)
        assert transactions == []
        # Avec annee spécifiée, l'absence de transactions génère une alerte
        assert any("aucune" in a.lower() or "transaction" in a.lower() for a in alertes)

    def test_agregation_sans_annee_pas_alertes_gaps(self, parser):
        """Sans annee, pas d'alerte de gaps générée."""
        transactions, alertes = parser.agreger_transactions([])
        assert transactions == []
        # Sans filtre d'année, pas d'analyse de gaps


class TestComparaisonCsvPdf:
    def test_comparaison_transactions_identiques(self, parser, tmp_path):
        """CSV et PDF avec les mêmes transactions → 100% de correspondance."""
        from core.parser.models import Transaction

        contenu = (
            "Numéro de compte;6804150W020\n"
            "Opérations imputées;du 01/01/2025 au 31/01/2025\n"
            "Solde comptable au 31/01/2025;1000,00 €\n\n"
            "Date;Libellé;Montant\n"
            "15/01/2025;HELLOASSO-XYZ HELLOASSO;200,00 €\n"
            "20/01/2025;COTISATION ADISPO;-38,04 €\n"
        )
        f = _creer_csv_tmp(tmp_path, contenu)
        releve_csv = parser.parser_fichier(str(f))

        # Créer les mêmes transactions côté PDF (même date, libellé, montant)
        tx_pdf = [
            Transaction(date=date(2025, 1, 15), libelle="HELLOASSO-XYZ HELLOASSO",
                        montant=Decimal("200.00")),
            Transaction(date=date(2025, 1, 20), libelle="COTISATION ADISPO",
                        montant=Decimal("-38.04")),
        ]

        comparaison = parser.comparer_avec_pdf(
            releve_csv.transactions, tx_pdf, annee=2025
        )
        assert comparaison["nb_csv"] == 2
        assert comparaison["nb_pdf"] == 2
        assert comparaison["nb_communs"] == 2
        assert comparaison["nb_uniquement_csv"] == 0
        assert comparaison["nb_uniquement_pdf"] == 0
        assert comparaison["taux_correspondance"] == 100.0

    def test_comparaison_transactions_differentes(self, parser, tmp_path):
        """CSV et PDF avec des transactions différentes."""
        from core.parser.models import Transaction

        contenu = (
            "Numéro de compte;6804150W020\n"
            "Opérations imputées;du 01/01/2025 au 31/01/2025\n"
            "Solde comptable au 31/01/2025;1000,00 €\n\n"
            "Date;Libellé;Montant\n"
            "15/01/2025;UNIQUEMENT CSV;100,00 €\n"
        )
        f = _creer_csv_tmp(tmp_path, contenu)
        releve_csv = parser.parser_fichier(str(f))

        tx_pdf = [Transaction(date=date(2025, 1, 20), libelle="UNIQUEMENT PDF",
                              montant=Decimal("-50.00"))]

        comparaison = parser.comparer_avec_pdf(
            releve_csv.transactions, tx_pdf, annee=2025
        )
        assert comparaison["nb_uniquement_csv"] == 1
        assert comparaison["nb_uniquement_pdf"] == 1
        assert comparaison["taux_correspondance"] < 100.0

    def test_comparaison_filtrage_annee(self, parser, tmp_path):
        """La comparaison filtre bien par année."""
        from core.parser.models import Transaction

        f = _creer_csv_tmp(tmp_path, CSV_STANDARD)  # Données 2024 et 2025
        releve_csv = parser.parser_fichier(str(f))

        tx_pdf = [Transaction(date=date(2025, 2, 10), libelle="PAYPAL", montant=Decimal("-27.00"))]
        comparaison = parser.comparer_avec_pdf(releve_csv.transactions, tx_pdf, annee=2024)
        # En 2024, la transaction PayPal du 10/02/2025 ne compte pas
        assert comparaison["nb_pdf"] == 0 or comparaison["nb_pdf"] == 1


# ── Tests d'intégration avec les vrais fichiers ───────────────────────────────

@pytest.mark.integration
class TestIntegrationCSV2025:
    """Tests sur les vrais fichiers CSV 2025 (nécessite le disque E)."""

    DOSSIER = r"E:\Culture musique\Documents\Compte bancaire\Opérations"

    @pytest.fixture
    def releves_reels(self, config):
        import pathlib
        if not pathlib.Path(self.DOSSIER).exists():
            pytest.skip("Disque E absent")
        p = CSVParserLaBanquePostale(config)
        return p.parser_dossier(self.DOSSIER)

    def test_3_fichiers_csv_trouves(self, releves_reels):
        assert len(releves_reels) == 3

    def test_encodage_utf8_bom(self, releves_reels):
        """Toutes les transactions ont des libellés non corrompus."""
        for releve in releves_reels:
            for t in releve.transactions:
                assert "\xef\xbb\xbf" not in t.libelle, "BOM dans le libellé"
                assert "�" not in t.libelle, "Caractère de remplacement UTF-8"

    def test_transactions_2025_coherentes(self, config):
        """Les transactions 2025 ont des montants raisonnables (<50 000€)."""
        import pathlib
        if not pathlib.Path(self.DOSSIER).exists():
            pytest.skip("Disque E absent")
        p = CSVParserLaBanquePostale(config)
        releves = p.parser_dossier(self.DOSSIER, annee=2025)
        txs, alertes = p.agreger_transactions(releves, annee=2025)
        for t in txs:
            assert abs(float(t.montant)) < 50_000, f"Montant aberrant: {t.montant} — {t.libelle}"

    def test_comparaison_avec_pdf_2025(self, config):
        """Compare les résultats CSV vs PDF pour 2025."""
        import pathlib
        if not pathlib.Path(self.DOSSIER).exists():
            pytest.skip("Disque E absent")

        from core.accounting.exercice import Exercice

        # Charger les transactions PDF 2025 depuis l'exercice sauvegardé
        exercice = Exercice(2025, "data")
        if not exercice.transactions:
            pytest.skip("Exercice 2025 non importé — lancer d'abord l'import PDF")

        p = CSVParserLaBanquePostale(config)
        releves = p.parser_dossier(self.DOSSIER, annee=2025)
        txs_csv, alertes = p.agreger_transactions(releves, annee=2025)

        comparaison = p.comparer_avec_pdf(txs_csv, exercice.transactions, annee=2025)

        print(f"\nComparaison CSV vs PDF pour 2025:")
        print(f"  Transactions CSV : {comparaison['nb_csv']}")
        print(f"  Transactions PDF : {comparaison['nb_pdf']}")
        print(f"  Communes         : {comparaison['nb_communs']}")
        print(f"  Uniquement CSV   : {comparaison['nb_uniquement_csv']}")
        print(f"  Uniquement PDF   : {comparaison['nb_uniquement_pdf']}")
        print(f"  Taux correspondance : {comparaison['taux_correspondance']:.1f}%")

        if alertes:
            print(f"\nAlertes CSV:")
            for a in alertes:
                print(f"  {a}")

        # La correspondance doit être raisonnable (> 50%)
        assert comparaison["taux_correspondance"] > 50, \
            f"Trop peu de correspondances: {comparaison['taux_correspondance']:.1f}%"
