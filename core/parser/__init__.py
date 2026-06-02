"""
Sous-package parser — Extraction des relevés bancaires.

Classes exportées:
    Transaction:                Dataclass représentant une transaction.
    ReleveInfo:                 Métadonnées d'un relevé bancaire.
    TransactionSplit:           Sous-ventilation d'une transaction.
    ParseError:                 Exception levée en cas d'échec.
    LaPosteParser:              Parseur PDF La Banque Postale (CCP).
    CSVParserLaBanquePostale:   Parseur CSV La Banque Postale (export portail).
"""

from .models import Transaction, ParseError, ReleveInfo, TransactionSplit
from .la_poste_parser import LaPosteParser
from .csv_parser import CSVParserLaBanquePostale

__all__ = [
    "Transaction", "ParseError", "ReleveInfo", "TransactionSplit",
    "LaPosteParser", "CSVParserLaBanquePostale",
]
