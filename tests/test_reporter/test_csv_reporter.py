"""Tests de l'export CSV."""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core.accounting.compte_resultat import CompteResultat
from core.reporter.csv_reporter import CsvReporter


class TestCsvReporter:
    @pytest.fixture
    def cr_simple(self, moteur, liste_transactions_2024):
        moteur.categoriser_lot(liste_transactions_2024, seuil_auto=0.1)
        return CompteResultat(
            moteur=moteur,
            transactions=liste_transactions_2024,
            date_debut=date(2024, 1, 1),
            date_fin=date(2024, 12, 31),
            solde_initial=Decimal("4424.17"),
        )

    def test_export_cree_fichiers(self, tmp_path, moteur, cr_simple):
        reporter = CsvReporter(moteur, cr_simple)
        synthese, detail = reporter.exporter(str(tmp_path))
        assert Path(synthese).exists()
        assert Path(detail).exists()

    def test_synthese_encoding_utf8(self, tmp_path, moteur, cr_simple):
        reporter = CsvReporter(moteur, cr_simple)
        synthese, _ = reporter.exporter(str(tmp_path))
        with open(synthese, encoding="utf-8-sig") as f:
            contenu = f.read()
        assert "Catégorie" in contenu or "Recette" in contenu

    def test_synthese_contient_total_recettes(self, tmp_path, moteur, cr_simple):
        reporter = CsvReporter(moteur, cr_simple)
        synthese, _ = reporter.exporter(str(tmp_path))
        with open(synthese, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        row_labels = [r[0] for r in rows if r]
        assert any("TOTAL" in lbl.upper() for lbl in row_labels)

    def test_detail_contient_toutes_transactions(self, tmp_path, moteur, cr_simple):
        reporter = CsvReporter(moteur, cr_simple)
        _, detail = reporter.exporter(str(tmp_path))
        with open(detail, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # Au moins les transactions catégorisées
        nb_cat = sum(1 for t in cr_simple._transactions_periode if t.est_categorisee)
        assert len(rows) >= nb_cat

    def test_noms_fichiers_contiennent_annee(self, tmp_path, moteur, cr_simple):
        reporter = CsvReporter(moteur, cr_simple)
        synthese, detail = reporter.exporter(str(tmp_path))
        assert "2024" in Path(synthese).name
        assert "2024" in Path(detail).name

    def test_cree_repertoire_si_absent(self, tmp_path, moteur, cr_simple):
        nouveau_rep = tmp_path / "sous_dossier" / "rapports"
        reporter = CsvReporter(moteur, cr_simple)
        synthese, detail = reporter.exporter(str(nouveau_rep))
        assert Path(synthese).exists()
