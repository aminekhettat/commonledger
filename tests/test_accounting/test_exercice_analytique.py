"""Tests de Exercice et ComptaAnalytique."""

from datetime import date
from decimal import Decimal

import pytest

from core.accounting.analytique import ComptaAnalytique, Projet
from core.accounting.exercice import Exercice
from core.parser.models import Transaction


class TestExercice:
    def test_creation_nouveau(self, tmp_path):
        ex = Exercice(2024, str(tmp_path))
        assert ex.annee == 2024
        assert ex.transactions == []
        assert ex.solde_initial == Decimal("0")

    def test_date_debut_fin(self, tmp_path):
        ex = Exercice(2024, str(tmp_path))
        assert ex.date_debut == date(2024, 1, 1)
        assert ex.date_fin == date(2024, 12, 31)

    def test_sauvegarder_et_recharger(self, tmp_path):
        ex = Exercice(2024, str(tmp_path))
        ex.solde_initial = Decimal("4424.17")
        t = Transaction(date=date(2024, 1, 1), libelle="TEST", montant=Decimal("100"))
        t.categorie_id = "cotisations"
        ex.transactions = [t]
        ex.sauvegarder()

        ex2 = Exercice(2024, str(tmp_path))
        assert ex2.solde_initial == Decimal("4424.17")
        assert len(ex2.transactions) == 1
        assert ex2.transactions[0].libelle == "TEST"

    def test_importer_releve(self, tmp_path, config_asso):
        from core.parser.models import ReleveInfo

        ex = Exercice(2024, str(tmp_path))
        ex.solde_initial = Decimal("4424.17")

        releve = ReleveInfo(fichier="test.pdf", valide=True)
        releve.periode_debut = date(2024, 1, 1)
        releve.periode_fin = date(2024, 1, 31)
        releve.solde_debut = Decimal("4424.17")
        releve.solde_fin = Decimal("4972.13")
        releve.transactions = [
            Transaction(date=date(2024, 1, 8), libelle="HELLOASSO", montant=Decimal("300")),
            Transaction(date=date(2024, 1, 3), libelle="PAYPAL", montant=Decimal("-16")),
        ]

        nb = ex.importer_releve(releve, copier_pdf=False)
        assert nb == 2
        assert len(ex.transactions) == 2

    def test_deduplication_import_double(self, tmp_path):
        from core.parser.models import ReleveInfo

        ex = Exercice(2024, str(tmp_path))

        releve = ReleveInfo(fichier="test.pdf", valide=True)
        releve.transactions = [
            Transaction(date=date(2024, 1, 8), libelle="HELLOASSO", montant=Decimal("300")),
        ]

        ex.importer_releve(releve, copier_pdf=False)
        nb2 = ex.importer_releve(releve, copier_pdf=False)  # Second import
        assert nb2 == 0  # Toutes déjà présentes
        assert len(ex.transactions) == 1  # Pas de doublon

    def test_transactions_non_categorisees(self, tmp_path):
        ex = Exercice(2024, str(tmp_path))
        t1 = Transaction(date=date(2024, 1, 1), libelle="A", montant=Decimal("100"))
        t2 = Transaction(date=date(2024, 1, 2), libelle="B", montant=Decimal("200"))
        t2.categorie_id = "cotisations"
        ex.transactions = [t1, t2]
        nc = ex.transactions_non_categorisees()
        assert len(nc) == 1
        assert nc[0].libelle == "A"

    def test_transactions_periode(self, tmp_path):
        ex = Exercice(2024, str(tmp_path))
        ex.transactions = [
            Transaction(date=date(2024, 1, 1), libelle="A", montant=Decimal("100")),
            Transaction(date=date(2024, 6, 1), libelle="B", montant=Decimal("200")),
            Transaction(date=date(2024, 12, 1), libelle="C", montant=Decimal("300")),
        ]
        t = ex.transactions_periode(date(2024, 1, 1), date(2024, 6, 30))
        assert len(t) == 2

    def test_definir_budget(self, tmp_path):
        ex = Exercice(2024, str(tmp_path))
        ex.definir_budget("cotisations", Decimal("5000"))
        assert ex.budget["cotisations"] == Decimal("5000")

    def test_ecart_budget(self, tmp_path):
        ex = Exercice(2024, str(tmp_path))
        ex.definir_budget("cotisations", Decimal("5000"))
        ecart = ex.ecart_budget("cotisations", Decimal("4000"))
        assert ecart == Decimal("-1000")

    def test_ecart_budget_categorie_sans_budget(self, tmp_path):
        ex = Exercice(2024, str(tmp_path))
        assert ex.ecart_budget("cotisations", Decimal("1000")) is None

    def test_resume(self, tmp_path):
        ex = Exercice(2024, str(tmp_path))
        ex.transactions = [
            Transaction(date=date(2024, 1, 1), libelle="A", montant=Decimal("100")),
        ]
        resume = ex.resume()
        assert resume["annee"] == 2024
        assert resume["nb_transactions"] == 1
        assert "taux_categorisation" in resume

    def test_calculer_compte_resultat(self, tmp_path, moteur):
        ex = Exercice(2024, str(tmp_path))
        ex.solde_initial = Decimal("4424.17")
        t = Transaction(date=date(2024, 1, 1), libelle="HELLOASSO", montant=Decimal("300"))
        t.categorie_id = "cotisations"
        ex.transactions = [t]
        cr = ex.calculer_compte_resultat(moteur)
        assert cr.total_recettes == Decimal("300")


class TestComptaAnalytique:
    def test_creation(self, tmp_path):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        assert ana.projets == {}

    def test_creer_projet(self, tmp_path):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        p = ana.creer_projet("Concert test", date(2024, 3, 15))
        assert p.nom == "Concert test"
        assert p.id in ana.projets

    def test_persistence(self, tmp_path):
        chemin = str(tmp_path / "projets.json")
        ana = ComptaAnalytique(chemin)
        ana.creer_projet("Tournée été")

        ana2 = ComptaAnalytique(chemin)
        assert len(ana2.projets) == 1
        assert any(p.nom == "Tournée été" for p in ana2.projets.values())

    def test_modifier_projet(self, tmp_path):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        p = ana.creer_projet("Avant modif")
        ana.modifier_projet(p.id, nom="Après modif")
        assert ana.get_projet(p.id).nom == "Après modif"

    def test_modifier_projet_inconnu(self, tmp_path):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        with pytest.raises(KeyError):
            ana.modifier_projet("inconnu", nom="Test")

    def test_supprimer_projet(self, tmp_path):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        p = ana.creer_projet("À supprimer")
        ana.supprimer_projet(p.id)
        assert p.id not in ana.projets

    def test_supprimer_projet_inconnu(self, tmp_path):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        with pytest.raises(KeyError):
            ana.supprimer_projet("inexistant")

    def test_get_projet_existant(self, tmp_path):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        p = ana.creer_projet("Test")
        assert ana.get_projet(p.id) is not None
        assert ana.get_projet(p.id).nom == "Test"

    def test_get_projet_inconnu(self, tmp_path):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        assert ana.get_projet("inconnu") is None

    def test_projets_actifs(self, tmp_path):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        p1 = ana.creer_projet("Actif")
        p2 = ana.creer_projet("Inactif")
        ana.modifier_projet(p2.id, actif=False)
        actifs = ana.projets_actifs()
        assert len(actifs) == 1
        assert actifs[0].id == p1.id

    def test_calculer_bilan_projet_sans_transactions(self, tmp_path, moteur):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        p = ana.creer_projet("Vide")
        bilan = ana.calculer_bilan(p.id, [], moteur)
        assert bilan.recettes == Decimal("0")
        assert bilan.depenses == Decimal("0")

    def test_calculer_bilan_avec_transactions(self, tmp_path, moteur):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        p = ana.creer_projet("Concert")

        t1 = Transaction(date=date(2024, 3, 1), libelle="BILLET", montant=Decimal("500"))
        t1.categorie_id = "cotisations"
        t1.projet_id = p.id

        t2 = Transaction(date=date(2024, 3, 2), libelle="SONO", montant=Decimal("-200"))
        t2.categorie_id = "autres_depenses"
        t2.projet_id = p.id

        bilan = ana.calculer_bilan(p.id, [t1, t2], moteur)
        assert bilan.recettes == Decimal("500")
        assert bilan.depenses == Decimal("200")
        assert bilan.resultat == Decimal("300")

    def test_taux_realisation_budget(self, tmp_path, moteur):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        p = ana.creer_projet("Budget test", budget=Decimal("1000"))
        t = Transaction(date=date(2024, 1, 1), libelle="SONO", montant=Decimal("-600"))
        t.categorie_id = "autres_depenses"
        t.projet_id = p.id
        bilan = ana.calculer_bilan(p.id, [t], moteur)
        assert bilan.taux_realisation_budget == pytest.approx(60.0, abs=0.1)

    def test_calculer_bilan_projet_inconnu(self, tmp_path, moteur):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        with pytest.raises(KeyError):
            ana.calculer_bilan("inexistant", [], moteur)

    def test_calculer_tous_bilans(self, tmp_path, moteur):
        ana = ComptaAnalytique(str(tmp_path / "projets.json"))
        ana.creer_projet("P1")
        ana.creer_projet("P2")
        bilans = ana.calculer_tous_bilans([], moteur)
        assert len(bilans) == 2


class TestProjet:
    def test_creation(self):
        p = Projet(nom="Concert")
        assert p.nom == "Concert"
        assert p.actif is True
        assert p.id != ""

    def test_serialisation_roundtrip(self):
        p = Projet(
            nom="Tournée",
            description="Tournée 2024",
            date_debut=date(2024, 7, 1),
            budget=Decimal("5000"),
        )
        d = p.to_dict()
        p2 = Projet.from_dict(d)
        assert p2.nom == p.nom
        assert p2.budget == p.budget
        assert p2.date_debut == p.date_debut
        assert p2.id == p.id
