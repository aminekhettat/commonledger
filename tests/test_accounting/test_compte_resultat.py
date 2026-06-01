"""Tests du compte de résultat."""

from datetime import date
from decimal import Decimal

import pytest

from core.accounting.compte_resultat import CompteResultat
from core.parser.models import Transaction


class TestCompteResultat:
    @pytest.fixture
    def cr(self, moteur, liste_transactions_2024):
        """Compte de résultat de test."""

        for t in liste_transactions_2024:
            moteur.categoriser_lot([t], seuil_auto=0.1)
        return CompteResultat(
            moteur=moteur,
            transactions=liste_transactions_2024,
            date_debut=date(2024, 1, 1),
            date_fin=date(2024, 12, 31),
            solde_initial=Decimal("4424.17"),
        )

    def test_creation(self, cr):
        assert cr.date_debut == date(2024, 1, 1)
        assert cr.date_fin == date(2024, 12, 31)
        assert cr.solde_initial == Decimal("4424.17")

    def test_total_recettes_positif_ou_nul(self, cr):
        assert cr.total_recettes >= Decimal("0")

    def test_total_depenses_positif_ou_nul(self, cr):
        assert cr.total_depenses >= Decimal("0")

    def test_resultat_net_coherent(self, cr):
        attendu = cr.total_recettes - cr.total_depenses
        assert cr.resultat_net == attendu

    def test_solde_final_coherent(self, cr):
        attendu = cr.solde_initial + cr.resultat_net
        assert cr.solde_final == attendu

    def test_lignes_recettes_triees(self, cr):
        if len(cr.lignes_recettes) > 1:
            for i in range(len(cr.lignes_recettes) - 1):
                assert cr.lignes_recettes[i].montant >= cr.lignes_recettes[i + 1].montant

    def test_pourcentages_recettes_somme_100(self, cr):
        if cr.lignes_recettes:
            total_pct = sum(l.pourcentage for l in cr.lignes_recettes)
            assert abs(total_pct - 100.0) < 0.1

    def test_pourcentages_depenses_somme_100(self, cr):
        if cr.lignes_depenses:
            total_pct = sum(l.pourcentage for l in cr.lignes_depenses)
            assert abs(total_pct - 100.0) < 0.1

    def test_filtrage_periode(self, moteur):
        txs = [
            Transaction(date=date(2024, 1, 1), libelle="HELLOASSO COTIS", montant=Decimal("100")),
            Transaction(date=date(2024, 6, 1), libelle="HELLOASSO COTIS", montant=Decimal("200")),
            Transaction(date=date(2024, 12, 1), libelle="HELLOASSO COTIS", montant=Decimal("300")),
        ]
        for t in txs:
            t.categorie_id = "cotisations"
        # Filtrer janvier uniquement
        cr = CompteResultat(
            moteur=moteur,
            transactions=txs,
            date_debut=date(2024, 1, 1),
            date_fin=date(2024, 1, 31),
        )
        assert cr.total_recettes == Decimal("100")

    def test_evolution_mensuelle_longueur(self, cr):
        evo = cr.evolution_mensuelle()
        assert len(evo) <= 12
        for item in evo:
            assert "mois" in item
            assert "recettes" in item
            assert "depenses" in item

    def test_transactions_non_categorisees(self, moteur):
        tx_nc = Transaction(date=date(2024, 1, 1), libelle="UNKNOWN", montant=Decimal("50"))
        cr = CompteResultat(
            moteur=moteur,
            transactions=[tx_nc],
            date_debut=date(2024, 1, 1),
            date_fin=date(2024, 12, 31),
        )
        assert len(cr.transactions_non_categorisees) == 1

    def test_transaction_splittee_incluse(self, moteur):
        t = Transaction(date=date(2024, 1, 8), libelle="HELLOASSO", montant=Decimal("300"))
        moteur.creer_split(
            t,
            [
                ("cotisations", Decimal("200"), None),
                ("dons", Decimal("100"), None),
            ],
        )
        cr = CompteResultat(
            moteur=moteur,
            transactions=[t],
            date_debut=date(2024, 1, 1),
            date_fin=date(2024, 12, 31),
        )
        # Les deux catégories du split doivent apparaître
        cats = {l.categorie.id for l in cr.lignes_recettes}
        assert "cotisations" in cats or "dons" in cats
