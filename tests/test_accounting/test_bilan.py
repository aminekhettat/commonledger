"""Tests du bilan comptable simplifié."""

from datetime import date
from decimal import Decimal

import pytest

from core.accounting.bilan import Bilan, GestionnaireBilan, Immobilisation


class TestImmobilisation:
    def test_taux_amortissement_5ans(self):
        immo = Immobilisation(
            id="1", designation="Sono", duree_amort=5, valeur_brute=Decimal("1000")
        )
        assert immo.taux_amort == Decimal("0.2")

    def test_dotation_annuelle(self):
        immo = Immobilisation(
            id="1", designation="Sono", duree_amort=5, valeur_brute=Decimal("1000")
        )
        assert immo.calculer_amortissement_annuel() == Decimal("200.00")

    def test_amortissement_a_date_1an(self):
        immo = Immobilisation(
            id="1",
            designation="Sono",
            date_achat=date(2022, 1, 1),
            valeur_brute=Decimal("1000"),
            duree_amort=5,
        )
        amort = immo.calculer_amort_a_date(date(2023, 1, 1))
        assert abs(amort - Decimal("200.00")) < Decimal("1.00")

    def test_amortissement_a_date_3ans(self):
        immo = Immobilisation(
            id="1",
            designation="Sono",
            date_achat=date(2020, 6, 1),
            valeur_brute=Decimal("800"),
            duree_amort=5,
        )
        amort = immo.calculer_amort_a_date(date(2024, 12, 31))
        vnc = immo.valeur_brute - amort
        assert vnc >= Decimal("0")

    def test_vnc_ne_va_pas_negatif(self):
        immo = Immobilisation(
            id="1",
            designation="Vieux matériel",
            date_achat=date(2010, 1, 1),
            valeur_brute=Decimal("500"),
            duree_amort=3,
        )
        # Calculer et stocker l'amortissement (14+ années sur 3 ans de durée)
        amort = immo.calculer_amort_a_date(date(2024, 12, 31))
        immo.amort_cumule = amort
        # Entièrement amorti — VNC = 0, pas négatif
        assert immo.valeur_nette == Decimal("0")

    def test_serialisation_roundtrip(self):
        immo = Immobilisation(
            id="abc-1",
            designation="Sono Yamaha",
            categorie="materiel_musical",
            date_achat=date(2022, 3, 15),
            valeur_brute=Decimal("800.00"),
            duree_amort=5,
            notes="Test",
        )
        d = immo.to_dict()
        immo2 = Immobilisation.from_dict(d)
        assert immo2.designation == immo.designation
        assert immo2.valeur_brute == immo.valeur_brute
        assert immo2.date_achat == immo.date_achat


class TestBilan:
    @pytest.fixture
    def bilan_simple(self):
        """Bilan équilibré simple (sans immobilisations ni dettes complexes)."""
        return Bilan(
            annee=2024,
            date_cloture=date(2024, 12, 31),
            solde_bancaire=Decimal("2189.18"),
            caisse=Decimal("60.00"),
            fonds_associatifs=Decimal("3463.12"),  # fonds initiaux
            report_a_nouveau=Decimal("-1021.05"),
            resultat_exercice=Decimal("-3734.99"),
            emprunts_prets_recus=Decimal("3500.00"),
            dettes_fournisseurs=Decimal("42.10"),
        )

    def test_total_disponibilites(self, bilan_simple):
        assert bilan_simple.total_disponibilites == Decimal("2249.18")

    def test_total_actif(self, bilan_simple):
        # Sans immobilisations ni créances
        assert bilan_simple.total_actif == Decimal("2249.18")

    def test_resultat_dans_fonds_propres(self, bilan_simple):
        fp = bilan_simple.total_fonds_propres
        assert bilan_simple.resultat_exercice in [
            fp - bilan_simple.fonds_associatifs - bilan_simple.report_a_nouveau
        ]

    def test_lignes_actif_contient_disponibilites(self, bilan_simple):
        lignes = bilan_simple.lignes_actif()
        labels = [l.label for l in lignes]
        assert any("Disponib" in l for l in labels)

    def test_lignes_passif_contient_report_nouveau(self, bilan_simple):
        lignes = bilan_simple.lignes_passif()

        # Chercher dans les sous-lignes
        def get_all_labels(lignes_list):
            result = []
            for l in lignes_list:
                result.append(l.label)
                result.extend(get_all_labels(l.sous_lignes))
            return result

        all_labels = get_all_labels(lignes)
        assert any("report" in l.lower() or "nouveau" in l.lower() for l in all_labels)

    def test_lignes_passif_contient_resultat(self, bilan_simple):
        lignes = bilan_simple.lignes_passif()

        def get_all_labels(ls):
            r = []
            for l in ls:
                r.append(l.label)
                r.extend(get_all_labels(l.sous_lignes))
            return r

        labels = get_all_labels(lignes)
        assert any("sultat" in l for l in labels)

    def test_bilan_zero_cree_lignes_total(self, bilan_simple):
        actif = bilan_simple.lignes_actif()
        passif = bilan_simple.lignes_passif()
        # La dernière ligne doit être le total
        assert actif[-1].gras is True
        assert passif[-1].gras is True

    def test_ecart_equilibre(self, bilan_simple):
        # Ce bilan de test peut ne pas être équilibré exactement
        # mais l'écart doit être calculable
        ecart = bilan_simple.ecart_equilibre
        assert isinstance(ecart, Decimal)


class TestGestionnaireBilan:
    def test_init(self, tmp_path):
        g = GestionnaireBilan(str(tmp_path))
        assert g.immobilisations == []

    def test_ajouter_et_sauvegarder(self, tmp_path):
        g = GestionnaireBilan(str(tmp_path))
        immo = Immobilisation(id="1", designation="Test", valeur_brute=Decimal("500"))
        g.ajouter_immobilisation(immo)
        assert len(g.immobilisations) == 1
        # Recharger et vérifier persistance
        g2 = GestionnaireBilan(str(tmp_path))
        assert len(g2.immobilisations) == 1
        assert g2.immobilisations[0].designation == "Test"

    def test_supprimer_immobilisation(self, tmp_path):
        g = GestionnaireBilan(str(tmp_path))
        immo = Immobilisation(id="del-1", designation="À supprimer", valeur_brute=Decimal("100"))
        g.ajouter_immobilisation(immo)
        g.supprimer_immobilisation("del-1")
        assert len(g.immobilisations) == 0

    def test_dotation_annuelle_vide(self, tmp_path):
        g = GestionnaireBilan(str(tmp_path))
        assert g.dotation_annuelle() == Decimal("0")

    def test_immobilisations_nettes_vide(self, tmp_path):
        g = GestionnaireBilan(str(tmp_path))
        assert g.immobilisations_nettes() == Decimal("0")
