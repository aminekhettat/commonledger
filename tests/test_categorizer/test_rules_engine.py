"""Tests du moteur de catégorisation."""

from decimal import Decimal
from datetime import date

import pytest

from core.categorizer.rules_engine import MoteurCategorisation, _normaliser
from core.parser.models import Transaction, TransactionSplit


class TestNormaliser:
    @pytest.mark.parametrize(
        "texte,attendu",
        [
            ("Héllo WORLD!", "HELLO WORLD "),
            ("café", "CAFE"),
            ("PayPal Europe", "PAYPAL EUROPE"),
            ("HELLOASSO-XYZ", "HELLOASSO XYZ"),
        ],
    )
    def test_normalisation(self, texte, attendu):
        assert _normaliser(texte) == attendu


class TestMoteurCategorisation:
    def test_chargement(self, moteur):
        assert len(moteur.categories) > 0
        assert "cotisations" in moteur.categories
        assert "frais_bancaires" in moteur.categories

    def test_categories_par_type_recettes(self, moteur):
        cats = moteur.categories_par_type("recettes")
        assert all(c.est_recette for c in cats)
        assert any(c.id == "cotisations" for c in cats)

    def test_categories_par_type_depenses(self, moteur):
        cats = moteur.categories_par_type("depenses")
        assert all(c.est_depense for c in cats)
        assert any(c.id == "frais_bancaires" for c in cats)

    def test_categorisation_helloasso(self, moteur, transaction_credit):
        result = moteur.categoriser(transaction_credit)
        assert result.categorie_id == "cotisations"
        assert result.score > 0

    def test_categorisation_adispo(self, moteur, transaction_adispo):
        result = moteur.categoriser(transaction_adispo)
        assert result.categorie_id == "frais_bancaires"
        assert result.score > 0

    def test_categorisation_paypal(self, moteur, transaction_debit):
        result = moteur.categoriser(transaction_debit)
        assert result.categorie_id == "autres_depenses"

    def test_transaction_verrouilee_non_modifiee(self, moteur):
        t = Transaction(date=date(2024, 1, 1), libelle="HELLOASSO", montant=Decimal("100"))
        t.categorie_id = "dons"
        t.verrouille = True
        result = moteur.categoriser(t)
        assert result.categorie_id == "dons"
        assert result.automatique is False

    def test_categorisation_lot(self, moteur, liste_transactions_2024):
        stats = moteur.categoriser_lot(liste_transactions_2024, seuil_auto=0.1)
        assert stats["auto"] + stats["a_traiter"] + stats["deja_faites"] == len(
            liste_transactions_2024
        )
        assert stats["auto"] > 0

    def test_est_helloasso(self, moteur, transaction_credit):
        assert moteur.est_helloasso(transaction_credit) is True

    def test_est_pas_helloasso(self, moteur, transaction_debit):
        assert moteur.est_helloasso(transaction_debit) is False

    def test_creer_split_valide(self, moteur):
        t = Transaction(date=date(2024, 1, 8), libelle="HELLOASSO", montant=Decimal("300.00"))
        moteur.creer_split(
            t,
            [
                ("cotisations", Decimal("200.00"), None),
                ("dons", Decimal("100.00"), None),
            ],
        )
        assert t.est_splittee is True
        assert len(t.splits) == 2
        assert t.splits[0].montant == Decimal("200.00")
        assert t.categorie_id is None  # effacé car splitté

    def test_creer_split_somme_incorrecte(self, moteur):
        t = Transaction(date=date(2024, 1, 8), libelle="HELLOASSO", montant=Decimal("300.00"))
        with pytest.raises(ValueError, match="Somme des splits"):
            moteur.creer_split(t, [("cotisations", Decimal("200.00"), None)])

    def test_get_categorie_existante(self, moteur):
        cat = moteur.get_categorie("cotisations")
        assert cat is not None
        assert cat.label == "Cotisations"

    def test_get_categorie_inconnue(self, moteur):
        assert moteur.get_categorie("inexistante") is None

    def test_ajouter_categorie(self, moteur):
        from core.categorizer.rules_engine import Categorie

        cat = Categorie(id="test_cat", label="Catégorie test", type="recettes")
        moteur.ajouter_categorie(cat)
        assert moteur.get_categorie("test_cat") is not None
        # Nettoyage
        del moteur.categories["test_cat"]

    def test_supprimer_categorie_inexistante(self, moteur):
        with pytest.raises(KeyError):
            moteur.supprimer_categorie("categorie_absente")
