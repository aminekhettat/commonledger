"""Tests du module core.parser.models."""

from datetime import date
from decimal import Decimal

from core.parser.models import ReleveInfo, Transaction, TransactionSplit


class TestTransaction:
    """Tests de la dataclass Transaction."""

    def test_creation_basique(self):
        t = Transaction(date=date(2024, 1, 8), libelle="TEST", montant=Decimal("100.00"))
        assert t.montant == Decimal("100.00")
        assert t.libelle == "TEST"
        assert t.date == date(2024, 1, 8)

    def test_id_unique_genere(self):
        t = Transaction(date=date(2024, 1, 8), libelle="TEST", montant=Decimal("100.00"))
        assert t.id_unique != ""
        assert "2024-01-08" in t.id_unique

    def test_id_unique_deterministe(self):
        """Deux transactions identiques = même id_unique (déduplication)."""
        t1 = Transaction(date=date(2024, 1, 8), libelle="ABC", montant=Decimal("50.00"))
        t2 = Transaction(date=date(2024, 1, 8), libelle="ABC", montant=Decimal("50.00"))
        assert t1.id_unique == t2.id_unique

    def test_id_unique_different_libelle(self):
        """Deux transactions même date/montant mais libellés différents = ids différents."""
        t1 = Transaction(date=date(2024, 1, 8), libelle="AAA REF:111", montant=Decimal("50.00"))
        t2 = Transaction(date=date(2024, 1, 8), libelle="AAA REF:222", montant=Decimal("50.00"))
        assert t1.id_unique != t2.id_unique

    def test_est_credit(self):
        t = Transaction(date=date(2024, 1, 1), libelle="X", montant=Decimal("100.00"))
        assert t.est_credit is True
        assert t.est_debit is False

    def test_est_debit(self):
        t = Transaction(date=date(2024, 1, 1), libelle="X", montant=Decimal("-50.00"))
        assert t.est_debit is True
        assert t.est_credit is False

    def test_est_categorisee_avec_categorie(self):
        t = Transaction(date=date(2024, 1, 1), libelle="X", montant=Decimal("10.00"))
        t.categorie_id = "cotisations"
        assert t.est_categorisee is True

    def test_est_categorisee_avec_split(self):
        t = Transaction(date=date(2024, 1, 1), libelle="X", montant=Decimal("10.00"))
        t.splits = [TransactionSplit(montant=Decimal("5.00"), categorie_id="cotisations")]
        assert t.est_categorisee is True
        assert t.est_splittee is True

    def test_est_non_categorisee(self):
        t = Transaction(date=date(2024, 1, 1), libelle="X", montant=Decimal("10.00"))
        assert t.est_categorisee is False

    def test_serialisation_roundtrip(self):
        t = Transaction(
            date=date(2024, 3, 15),
            libelle="VIREMENT HELLOASSO",
            montant=Decimal("300.00"),
            memo="Test mémo",
            categorie_id="cotisations",
        )
        d = t.to_dict()
        t2 = Transaction.from_dict(d)
        assert t2.date == t.date
        assert t2.libelle == t.libelle
        assert t2.montant == t.montant
        assert t2.memo == t.memo
        assert t2.categorie_id == t.categorie_id

    def test_serialisation_avec_splits(self):
        t = Transaction(date=date(2024, 1, 1), libelle="X", montant=Decimal("100.00"))
        t.splits = [
            TransactionSplit(Decimal("60.00"), "cotisations"),
            TransactionSplit(Decimal("40.00"), "dons"),
        ]
        d = t.to_dict()
        t2 = Transaction.from_dict(d)
        assert len(t2.splits) == 2
        assert t2.splits[0].montant == Decimal("60.00")
        assert t2.splits[1].categorie_id == "dons"


class TestTransactionSplit:
    def test_creation(self):
        s = TransactionSplit(montant=Decimal("150.00"), categorie_id="cotisations")
        assert s.montant == Decimal("150.00")
        assert s.categorie_id == "cotisations"
        assert s.projet_id is None

    def test_serialisation(self):
        s = TransactionSplit(Decimal("75.50"), "dons", projet_id="proj-1", memo="test")
        d = s.to_dict()
        s2 = TransactionSplit.from_dict(d)
        assert s2.montant == s.montant
        assert s2.projet_id == s.projet_id
        assert s2.memo == s.memo


class TestReleveInfo:
    def test_creation_vide(self):
        r = ReleveInfo(fichier="test.pdf")
        assert r.transactions == []
        assert r.valide is False
        assert r.solde_debut is None
