"""
Inspecte les transactions du 17 juillet 2025 dans les CSV et PDF
pour comprendre les 2 transactions «absentes du CSV».
"""
import sys, json, pathlib
from decimal import Decimal

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.parser.csv_parser import CSVParserLaBanquePostale
from core.accounting.exercice import Exercice

config = json.load(open("config/association.json", encoding="utf-8"))
DOSSIER_CSV = r"E:\Culture musique\Documents\Compte bancaire\Opérations"

# ── Transactions PDF du 17 juillet 2025 ─────────────────────────────────────
exercice = Exercice(2025, "data")
txs_pdf_17 = [t for t in exercice.transactions
              if t.date.month == 7 and t.date.day == 17]

print("=== PDF — transactions du 17/07/2025 ===")
for t in sorted(txs_pdf_17, key=lambda x: float(x.montant)):
    print(f"  {float(t.montant):>10.2f} €  |  {t.libelle!r}")

# ── Transactions CSV du 17 juillet 2025 ─────────────────────────────────────
parser = CSVParserLaBanquePostale(config)
releves = parser.parser_dossier(DOSSIER_CSV)
txs_csv_17 = [t for r in releves for t in r.transactions
              if t.date.month == 7 and t.date.day == 17]

print("\n=== CSV — transactions du 17/07/2025 ===")
for t in sorted(txs_csv_17, key=lambda x: float(x.montant)):
    print(f"  {float(t.montant):>10.2f} €  |  {t.libelle!r}")

# ── Contexte : transactions 15-20 juillet dans le CSV ───────────────────────
from datetime import date
txs_csv_juillet = [t for r in releves for t in r.transactions
                   if t.date.year == 2025 and t.date.month == 7
                   and 15 <= t.date.day <= 20]

print("\n=== CSV — transactions 15-20 juillet 2025 ===")
for t in sorted(txs_csv_juillet, key=lambda x: x.date):
    print(f"  {t.date}  {float(t.montant):>10.2f} €  |  {t.libelle!r}")
