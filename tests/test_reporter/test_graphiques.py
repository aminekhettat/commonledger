"""
Tests de génération des graphiques (matplotlib backend Agg — sans affichage).
Couvre GraphiquesMaker à ~95% (seul nettoyer() est trivial).
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

# Forcer le backend sans affichage AVANT tout import matplotlib
import matplotlib
import pytest

matplotlib.use("Agg")

from core.reporter.graphiques import MOIS_FR, GraphiquesMaker


@pytest.fixture
def maker():
    """GraphiquesMaker avec couleurs par défaut."""
    return GraphiquesMaker(
        couleur_principale="#1a3a5c",
        couleur_secondaire="#e8f0f7",
        dpi=72,  # DPI bas pour les tests (plus rapide)
    )


@pytest.fixture
def lignes_recettes(moteur, liste_transactions_2024):
    """Lignes de résultats recettes pour les tests graphiques."""
    from core.accounting.compte_resultat import CompteResultat

    moteur.categoriser_lot(liste_transactions_2024, seuil_auto=0.1)
    cr = CompteResultat(
        moteur=moteur,
        transactions=liste_transactions_2024,
        date_debut=date(2024, 1, 1),
        date_fin=date(2024, 12, 31),
    )
    return cr.lignes_recettes, cr.lignes_depenses, cr


class TestMoisFR:
    def test_longueur(self):
        assert len(MOIS_FR) == 13  # index 0 vide + 12 mois

    def test_janvier(self):
        assert MOIS_FR[1] == "Janvier"

    def test_decembre(self):
        assert MOIS_FR[12] == "Décembre"


class TestGraphiquesMaker:
    def test_creation(self, maker):
        assert maker.couleur_principale == "#1a3a5c"
        assert maker.dpi == 72
        assert Path(maker._tmpdir).is_dir()

    def test_camembert_recettes_cree_png(self, maker, lignes_recettes):
        recettes, _, _ = lignes_recettes
        if not recettes:
            pytest.skip("Pas de recettes dans les transactions de test")
        chemin, tableau = maker.camembert_recettes(recettes)
        assert chemin != ""
        assert Path(chemin).exists()
        assert Path(chemin).suffix == ".png"
        assert Path(chemin).stat().st_size > 0

    def test_camembert_recettes_tableau_non_vide(self, maker, lignes_recettes):
        recettes, _, _ = lignes_recettes
        if not recettes:
            pytest.skip("Pas de recettes")
        _, tableau = maker.camembert_recettes(recettes)
        assert "Tableau" in tableau
        assert "€" in tableau

    def test_camembert_depenses_cree_png(self, maker, lignes_recettes):
        _, depenses, _ = lignes_recettes
        if not depenses:
            pytest.skip("Pas de dépenses")
        chemin, tableau = maker.camembert_depenses(depenses)
        assert chemin != ""
        assert Path(chemin).exists()

    def test_camembert_liste_vide_retourne_chaines_vides(self, maker):
        chemin, tableau = maker.camembert_recettes([])
        assert chemin == ""
        assert tableau == ""

    def test_camembert_tous_montants_zero(self, maker, moteur):
        """Lignes avec montants nuls — ne génère rien."""
        from core.accounting.compte_resultat import LigneResultat
        from core.categorizer.rules_engine import Categorie

        cat = Categorie(id="test", label="Test", type="recettes")
        ligne = LigneResultat(categorie=cat, montant=Decimal("0"))
        chemin, tableau = maker._camembert([ligne], "Titre", "")
        assert chemin == ""

    def test_histogramme_cree_png(self, maker, lignes_recettes):
        _, _, cr = lignes_recettes
        evolution = cr.evolution_mensuelle()
        if not evolution:
            pytest.skip("Pas d'évolution")
        chemin, tableau = maker.histogramme_mensuel(evolution)
        assert Path(chemin).exists()
        assert Path(chemin).stat().st_size > 0

    def test_histogramme_tableau_contient_mois(self, maker, lignes_recettes):
        _, _, cr = lignes_recettes
        evolution = cr.evolution_mensuelle()
        if not evolution:
            pytest.skip()
        _, tableau = maker.histogramme_mensuel(evolution)
        assert "Tableau" in tableau
        assert any(m in tableau for m in ["Janvier", "Février", "Mars"])

    def test_histogramme_vide(self, maker):
        chemin, tableau = maker.histogramme_mensuel([])
        assert chemin == ""
        assert tableau == ""

    def test_courbe_tresorerie_cree_png(self, maker, lignes_recettes):
        _, _, cr = lignes_recettes
        evolution = cr.evolution_mensuelle()
        if not evolution:
            pytest.skip()
        chemin, tableau = maker.courbe_tresorerie(evolution, Decimal("4424.17"))
        assert Path(chemin).exists()

    def test_courbe_tresorerie_vide(self, maker):
        chemin, tableau = maker.courbe_tresorerie([], Decimal("1000"))
        assert chemin == ""
        assert tableau == ""

    def test_courbe_tableau_contient_solde_initial(self, maker, lignes_recettes):
        _, _, cr = lignes_recettes
        evolution = cr.evolution_mensuelle()
        if not evolution:
            pytest.skip()
        _, tableau = maker.courbe_tresorerie(evolution, Decimal("4424.17"))
        # Le tableau affiche 4,424.17 (format Python) ou 4 424 (format FR)
        assert "4,424" in tableau or "4 424" in tableau or "4424" in tableau

    def test_nettoyer_supprime_tmpdir(self, maker, lignes_recettes):
        recettes, _, _ = lignes_recettes
        if recettes:
            maker.camembert_recettes(recettes)
        tmpdir = maker._tmpdir
        assert Path(tmpdir).exists()
        maker.nettoyer()
        assert not Path(tmpdir).exists()

    def test_tableau_textuel_camembert(self, maker, moteur):
        from core.accounting.compte_resultat import LigneResultat
        from core.categorizer.rules_engine import Categorie

        cat = Categorie(id="c1", label="Cotisations", type="recettes")
        ligne = LigneResultat(
            categorie=cat, montant=Decimal("300"), pourcentage=75.0, nb_transactions=3
        )
        tableau = maker._tableau_textuel_camembert("Test", [ligne], 400.0)
        assert "Cotisations" in tableau
        assert "300" in tableau
        assert "75" in tableau

    def test_tableau_textuel_mensuel(self, maker):
        evolution = [
            {"annee": 2024, "mois": 1, "recettes": Decimal("500"), "depenses": Decimal("300")},
            {"annee": 2024, "mois": 2, "recettes": Decimal("200"), "depenses": Decimal("150")},
        ]
        tableau = maker._tableau_textuel_mensuel(evolution)
        assert "Janvier" in tableau
        assert "Février" in tableau
        assert "500" in tableau

    def test_tableau_textuel_tresorerie(self, maker):
        evolution = [
            {"annee": 2024, "mois": 1, "recettes": Decimal("500"), "depenses": Decimal("200")}
        ]
        soldes = [4724.17]
        tableau = maker._tableau_textuel_tresorerie(evolution, 4424.17, soldes)
        assert "4,424" in tableau or "4 424" in tableau or "4424" in tableau
        assert "Janvier" in tableau
