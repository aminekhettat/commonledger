"""
Tests du générateur de rapports Word.

Utilise python-docx directement (pas besoin de Word installé).
Teste la structure du document, pas l'apparence visuelle.
La conversion PDF (Windows COM / LibreOffice) est testée avec mocks.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import matplotlib
import pytest

matplotlib.use("Agg")

from core.accounting.bilan import Bilan
from core.accounting.compte_resultat import CompteResultat
from core.reporter.docx_reporter import DocxReporter, _date_fr, _hex_fill, _rgb

# ── Helpers ───────────────────────────────────────────────────────────────────


class TestHelpers:
    def test_date_fr_format(self):
        assert _date_fr(date(2024, 1, 31)) == "31 janvier 2024"
        assert _date_fr(date(2024, 12, 1)) == "1 décembre 2024"
        assert _date_fr(date(2024, 6, 15)) == "15 juin 2024"

    def test_rgb_conversion(self):
        c = _rgb("#1a3a5c")
        from docx.shared import RGBColor

        assert isinstance(c, RGBColor)

    def test_hex_fill(self):
        assert _hex_fill("#1a3a5c") == "1a3a5c"
        assert _hex_fill("1a3a5c") == "1a3a5c"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def reporter(config_asso, moteur):
    return DocxReporter(config_asso, moteur)


@pytest.fixture
def cr_test(moteur, liste_transactions_2024):
    moteur.categoriser_lot(liste_transactions_2024, seuil_auto=0.1)
    return CompteResultat(
        moteur=moteur,
        transactions=liste_transactions_2024,
        date_debut=date(2024, 1, 1),
        date_fin=date(2024, 12, 31),
        solde_initial=Decimal("4424.17"),
    )


@pytest.fixture
def bilan_test():
    return Bilan(
        annee=2024,
        date_cloture=date(2024, 12, 31),
        solde_bancaire=Decimal("2189.18"),
        caisse=Decimal("60.00"),
        fonds_associatifs=Decimal("3463.12"),
        report_a_nouveau=Decimal("-1021.05"),
        resultat_exercice=Decimal("-3734.99"),
        emprunts_prets_recus=Decimal("3500.00"),
    )


# ── Tests de génération ───────────────────────────────────────────────────────


class TestDocxReporterGeneration:
    def test_generer_cree_fichier(self, reporter, cr_test, tmp_path):
        chemin = str(tmp_path / "rapport_test.docx")
        result = reporter.generer(cr_test, chemin)
        assert Path(result).exists()
        assert Path(result).suffix == ".docx"
        assert Path(result).stat().st_size > 0

    def test_generer_fichier_non_vide(self, reporter, cr_test, tmp_path):
        chemin = str(tmp_path / "rapport.docx")
        reporter.generer(cr_test, chemin)
        # Un rapport Word avec contenu fait au moins 50KB
        assert Path(chemin).stat().st_size > 5_000

    def test_generer_avec_titre_personnalise(self, reporter, cr_test, tmp_path):
        chemin = str(tmp_path / "rapport.docx")
        reporter.generer(cr_test, chemin, titre_rapport="Mon Titre Test")
        assert Path(chemin).exists()

    def test_generer_titre_annuel_auto(self, reporter, cr_test, tmp_path):
        chemin = str(tmp_path / "rapport.docx")
        reporter.generer(cr_test, chemin)  # titre auto = "Rapport annuel 2024"
        assert Path(chemin).exists()

    def test_generer_avec_bilan(self, reporter, cr_test, bilan_test, tmp_path):
        chemin = str(tmp_path / "rapport_bilan.docx")
        reporter._bilan_data = bilan_test
        reporter.generer(cr_test, chemin, bilan=bilan_test)
        assert Path(chemin).exists()
        reporter._bilan_data = None

    def test_generer_cree_repertoire_si_absent(self, reporter, cr_test, tmp_path):
        chemin = str(tmp_path / "sous_dossier" / "rapport.docx")
        reporter.generer(cr_test, chemin)
        assert Path(chemin).exists()

    def test_generer_avec_logo(self, reporter, cr_test, tmp_path):
        """Test avec un logo factice (1x1 pixel PNG)."""
        from PIL import Image

        logo = tmp_path / "logo.png"
        img = Image.new("RGBA", (100, 100), (26, 58, 92, 255))
        img.save(str(logo))
        reporter.config["logo_chemin"] = str(logo)
        chemin = str(tmp_path / "rapport_logo.docx")
        try:
            reporter.generer(cr_test, chemin)
            assert Path(chemin).exists()
        finally:
            reporter.config["logo_chemin"] = ""

    def test_generer_avec_bilans_projets_vide(self, reporter, cr_test, tmp_path):
        chemin = str(tmp_path / "rapport.docx")
        reporter.generer(cr_test, chemin, bilans_projets=[])
        assert Path(chemin).exists()


class TestDocxReporterSections:
    """Tests des sections individuelles du rapport."""

    @pytest.fixture
    def doc(self):
        from docx import Document

        return Document()

    def test_section_infos(self, reporter, doc):
        reporter._section_infos(doc)
        # Doit avoir ajouté du contenu
        assert len(doc.paragraphs) > 0 or len(doc.tables) > 0

    def test_section_compte_resultat(self, reporter, doc, cr_test):
        reporter._section_compte_resultat(doc, cr_test)
        assert len(doc.paragraphs) > 0

    def test_section_graphiques(self, reporter, doc, cr_test):
        reporter._section_graphiques(doc, cr_test)
        assert len(doc.paragraphs) > 0

    def test_section_tresorerie(self, reporter, doc, cr_test):
        reporter._section_tresorerie(doc, cr_test)
        assert len(doc.paragraphs) > 0

    def test_section_detail(self, reporter, doc, cr_test):
        reporter._section_detail(doc, cr_test)
        assert len(doc.paragraphs) > 0

    def test_section_bilan(self, reporter, doc, bilan_test):
        reporter._section_bilan(doc, bilan_test)
        assert len(doc.tables) > 0

    def test_section_signature(self, reporter, doc, cr_test):
        reporter._section_signature(doc, cr_test)
        assert len(doc.paragraphs) > 0

    def test_section_analytique_vide(self, reporter, doc):
        reporter._section_analytique(doc, [])
        # Ne plante pas avec liste vide

    def test_section_alertes(self, reporter, doc, cr_test, moteur):
        from core.accounting.compte_resultat import AlerteCoherence

        # Injecter une alerte de test
        cr_test.alertes_coherence = [
            AlerteCoherence(
                date_releve=date(2024, 1, 31),
                solde_calcule=Decimal("4972.13"),
                solde_releve=Decimal("4970.00"),
                ecart=Decimal("2.13"),
            )
        ]
        reporter._section_alertes(doc, cr_test)
        assert len(doc.tables) > 0


class TestDocxReporterTableaux:
    """Tests des méthodes utilitaires de tableaux."""

    def test_tableau_postes_recettes(self, reporter, cr_test):
        from docx import Document

        doc = Document()
        reporter._tableau_postes(doc, cr_test.lignes_recettes, cr_test.total_recettes, "recettes")
        assert len(doc.tables) > 0

    def test_tableau_postes_depenses(self, reporter, cr_test):
        from docx import Document

        doc = Document()
        reporter._tableau_postes(doc, cr_test.lignes_depenses, cr_test.total_depenses, "dépenses")
        assert len(doc.tables) > 0

    def test_tableau_postes_vide(self, reporter):
        from docx import Document

        doc = Document()
        reporter._tableau_postes(doc, [], Decimal("0"), "recettes")
        # Doit afficher un message "Aucune recette" sans planter


class TestDocxReporterConversionPDF:
    """Tests de conversion PDF avec mocks (Windows COM et LibreOffice)."""

    def test_convertir_en_pdf_word_com_succes(self, reporter, tmp_path):
        """Test conversion via Word COM mockée."""
        docx_path = str(tmp_path / "test.docx")
        pdf_path = str(tmp_path / "test.pdf")
        Path(docx_path).write_bytes(b"fake docx")
        Path(pdf_path).write_bytes(b"fake pdf")

        with patch.object(reporter, "_convertir_word_com", return_value=pdf_path):
            result = reporter.convertir_en_pdf(docx_path)
            assert result == pdf_path

    def test_convertir_en_pdf_fallback_libreoffice(self, reporter, tmp_path):
        """Si Word COM échoue, tente LibreOffice."""
        docx_path = str(tmp_path / "test.docx")
        pdf_path = str(tmp_path / "test.pdf")
        Path(docx_path).write_bytes(b"fake docx")
        Path(pdf_path).write_bytes(b"fake pdf")

        with patch.object(reporter, "_convertir_word_com", side_effect=Exception("No Word")):
            with patch.object(reporter, "_convertir_libreoffice", return_value=pdf_path):
                result = reporter.convertir_en_pdf(docx_path)
                assert result == pdf_path

    def test_convertir_en_pdf_echec_total(self, reporter, tmp_path):
        """Si les deux échouent, retourne None."""
        docx_path = str(tmp_path / "test.docx")
        Path(docx_path).write_bytes(b"fake docx")

        with patch.object(reporter, "_convertir_word_com", side_effect=Exception("No Word")):
            with patch.object(reporter, "_convertir_libreoffice", side_effect=Exception("No LO")):
                result = reporter.convertir_en_pdf(docx_path)
                assert result is None
