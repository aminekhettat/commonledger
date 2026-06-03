"""
Fixtures pytest partagées pour tous les tests CommonLedger.

Organisation :
  - Fixtures de données : transactions, relevés, config
  - Fixtures de moteurs : parseur, moteur de catégorisation
  - Fixtures de fichiers temporaires
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

# ── Fixtures de configuration ─────────────────────────────────────────────────


@pytest.fixture(scope="session")
def config_asso() -> dict:
    """
    Configuration minimale d'association pour les tests.

    Les valeurs IBAN/BIC/num_compte doivent correspondre à celles présentes
    dans les PDFs mockés (RELEVE_JANVIER_2024, etc.) pour que la validation
    _valider_releve() passe. L'IBAN utilisé dans les fixtures mock est :
    'FR94 2004 1000 0168 0415 0W02 084' → normalisé : 'FR942004100001680415W02084'.
    """
    return {
        "nom": "Culture Musique",  # "ASSO CULTURE MUSIQUE" contient "CULTURE MUSIQUE"
        "sigle": "ACM",
        "type_structure": "Association loi 1901",
        "iban": "FR94 2004 1000 0168 0415 0W02 084",  # normalisé: FR9420041000016804150W02084
        "bic": "PSSTFRPPPAR",
        "numero_compte": "6804150W020",
        "banque": "La Banque Postale",
        "siret": "123 456 789 00012",
        "couleur_principale": "#1a3a5c",
        "couleur_secondaire": "#e8f0f7",
        "tresorier": "Test Trésorier",
    }


@pytest.fixture(scope="session")
def config_categories_path(tmp_path_factory) -> Path:
    """Fichier categories.json minimal pour les tests."""
    data = {
        "recettes": [
            {
                "id": "cotisations",
                "label": "Cotisations",
                "mots_cles": ["COTIS", "HELLOASSO"],
                "split_autorise": True,
                "couleur_graphique": "#2196F3",
            },
            {
                "id": "dons",
                "label": "Dons",
                "mots_cles": ["DON"],
                "split_autorise": True,
                "couleur_graphique": "#4CAF50",
            },
            {
                "id": "autres_recettes",
                "label": "Autres recettes",
                "mots_cles": [],
                "split_autorise": True,
                "couleur_graphique": "#9E9E9E",
            },
        ],
        "depenses": [
            {
                "id": "locations",
                "label": "Locations",
                "mots_cles": ["LOYER", "LOCATION"],
                "details_requis": False,
                "couleur_graphique": "#E91E63",
            },
            {
                "id": "frais_bancaires",
                "label": "Frais bancaires",
                "mots_cles": ["ADISPO", "COTISATION ADISPO"],
                "details_requis": False,
                "couleur_graphique": "#9E9E9E",
            },
            {
                "id": "autres_depenses",
                "label": "Autres dépenses",
                "mots_cles": ["PAYPAL"],
                "details_requis": False,
                "couleur_graphique": "#757575",
            },
        ],
    }
    tmpdir = tmp_path_factory.mktemp("config")
    chemin = tmpdir / "categories.json"
    chemin.write_text(json.dumps(data), encoding="utf-8")
    return chemin


# ── Fixtures de transactions ──────────────────────────────────────────────────


@pytest.fixture
def transaction_credit():
    """Transaction de crédit simple (cotisation HelloAsso)."""
    from core.parser.models import Transaction

    return Transaction(
        date=date(2024, 1, 8),
        libelle="VIREMENT DE STRIPE HELLOASSO-XYZ HELLOASSO",
        montant=Decimal("300.00"),
        source_fichier="releve_test.pdf",
    )


@pytest.fixture
def transaction_debit():
    """Transaction de débit simple (prélèvement PayPal)."""
    from core.parser.models import Transaction

    return Transaction(
        date=date(2024, 1, 3),
        libelle="PRELEVEMENT DE PayPal Europe S.a.r.l REF 12345 PAYPAL",
        montant=Decimal("-16.00"),
        source_fichier="releve_test.pdf",
    )


@pytest.fixture
def transaction_adispo():
    """Transaction de débit Adispo (frais bancaires)."""
    from core.parser.models import Transaction

    return Transaction(
        date=date(2024, 1, 17),
        libelle="4COTISATION ADISPO ASSO INTEGRAL MT HT= 38,04EUR-TVA= 0,00%",
        montant=Decimal("-38.04"),
        source_fichier="releve_test.pdf",
    )


@pytest.fixture
def liste_transactions_2024(transaction_credit, transaction_debit, transaction_adispo):
    """Liste représentative de transactions 2024."""
    from core.parser.models import Transaction

    txs = [
        transaction_credit,
        transaction_debit,
        transaction_adispo,
        Transaction(
            date=date(2024, 1, 3),
            libelle="VIREMENT POUR REGIE DE LA MAIRIE PARIS LOYER 2024",
            montant=Decimal("-144.00"),
            source_fichier="releve_test.pdf",
        ),
        Transaction(
            date=date(2024, 1, 16),
            libelle="REMISE DE CHEQUES DU 13/01/2024",
            montant=Decimal("350.00"),
            source_fichier="releve_test.pdf",
        ),
    ]
    return txs


# ── Fixtures de moteurs ───────────────────────────────────────────────────────


@pytest.fixture
def moteur(config_categories_path):
    """Moteur de catégorisation avec config de test."""
    from core.categorizer.rules_engine import MoteurCategorisation

    return MoteurCategorisation(str(config_categories_path))


@pytest.fixture
def parser(config_asso):
    """Parseur La Banque Postale configuré pour les tests."""
    from core.parser.la_poste_parser import LaPosteParser

    return LaPosteParser(config_asso)


# ── Fixtures d'exercice ───────────────────────────────────────────────────────


@pytest.fixture
def exercice_tmp(tmp_path, liste_transactions_2024, moteur):
    """Exercice 2024 avec transactions pré-catégorisées en répertoire temporaire."""
    from core.accounting.exercice import Exercice

    ex = Exercice(2024, str(tmp_path))
    ex.solde_initial = Decimal("4424.17")
    ex.transactions = liste_transactions_2024[:]
    moteur.categoriser_lot(ex.transactions, seuil_auto=0.1)
    return ex


# ── Fixtures de fichiers PDF de test ─────────────────────────────────────────


@pytest.fixture(scope="session")
def pdf_test_path() -> Path:
    """
    Retourne le chemin vers un PDF de test réel si disponible,
    sinon marque le test comme skippé.
    Utilise un des relevés 2024 de Culture Musique si le disque E est accessible.
    """
    chemins = [
        Path(
            r"E:\Culture musique\Documents\Compte bancaire\Releves\2024\releve_6804150W020_2024-01-31.pdf"
        ),
        Path("tests/fixtures/releve_test.pdf"),
    ]
    for chemin in chemins:
        if chemin.exists():
            return chemin
    pytest.skip("Aucun PDF de test disponible (disque E absent ou fixtures manquantes)")
