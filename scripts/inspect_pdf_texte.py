"""
Inspecte le texte brut extrait par pdfplumber d'un relevé La Banque Postale
pour diagnostiquer si les libellés sont tronqués dans le PDF ou par le parseur.
"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent))

import pdfplumber

DOSSIER = Path(r"E:\Culture musique\Documents\Compte bancaire\Releves\2025")

# Prendre le relevé de juillet (contient les transactions du 17/07 qui nous intéressent)
pdfs = sorted(DOSSIER.glob("*.pdf"))
pdf_juillet = next((p for p in pdfs if "07" in p.name or "2025-07" in p.name), pdfs[6] if len(pdfs) > 6 else pdfs[0])

print(f"=== FICHIER : {pdf_juillet.name} ===\n")

with pdfplumber.open(pdf_juillet) as pdf:
    for num_page, page in enumerate(pdf.pages, 1):
        texte = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
        lignes = texte.split("\n")

        print(f"--- PAGE {num_page} ({len(lignes)} lignes) ---")
        for i, ligne in enumerate(lignes):
            # Afficher toutes les lignes contenant une date DD/MM ou un libellé bancaire
            if ligne.strip():
                print(f"  [{i:3d}] {repr(ligne)}")
        print()

        if num_page >= 3:  # Limiter à 3 pages pour ne pas surcharger
            print("  (pages suivantes non affichées)")
            break
