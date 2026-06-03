"""
Inspecte le PDF de janvier 2025 et compare ce que le parseur produit
vs le texte brut pdfplumber pour les transactions HELLOASSO / PayPal.
"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent))

import pdfplumber, json
from core.parser.la_poste_parser import LaPosteParser

DOSSIER = Path(r"E:\Culture musique\Documents\Compte bancaire\Releves\2025")
config = json.load(open("config/association.json", encoding="utf-8"))

pdf_jan = next(p for p in sorted(DOSSIER.glob("*.pdf")) if "2025-01" in p.name)
print(f"=== FICHIER : {pdf_jan.name} ===\n")

# ── 1. Texte brut pdfplumber ─────────────────────────────────────────────────
print("=== TEXTE BRUT (lignes non vides) ===")
with pdfplumber.open(pdf_jan) as pdf:
    for num_page, page in enumerate(pdf.pages, 1):
        texte = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
        for i, ligne in enumerate(texte.split("\n")):
            if ligne.strip():
                print(f"  P{num_page}[{i:3d}] {repr(ligne)}")

# ── 2. Ce que le parseur produit ─────────────────────────────────────────────
print("\n=== TRANSACTIONS PARSÉES ===")
parser = LaPosteParser(config)
releve = parser.parser_fichier(str(pdf_jan))
for t in releve.transactions:
    print(f"  {t.date}  {float(t.montant):>10.2f}€  {t.libelle!r}")
