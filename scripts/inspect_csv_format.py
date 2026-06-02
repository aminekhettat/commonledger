"""
Inspecte la structure brute des fichiers CSV La Banque Postale
pour diagnostiquer comment les colonnes sont découpées.
"""
import sys, csv, pathlib

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DOSSIER = pathlib.Path(r"E:\Culture musique\Documents\Compte bancaire\Opérations")

for csv_path in sorted(DOSSIER.glob("*.csv"))[:1]:  # Premier fichier seulement
    print(f"=== FICHIER : {csv_path.name} ===\n")

    # Lignes brutes
    with open(csv_path, encoding='utf-8-sig') as f:
        raw = f.readlines()

    print("--- 20 premières lignes BRUTES (repr) ---")
    for i, ligne in enumerate(raw[:20]):
        print(f"[{i:2d}] {repr(ligne)}")

    print()
    print("--- Parsing CSV (delimiter=';') ---")
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f, delimiter=';')
        for i, row in enumerate(reader):
            print(f"[{i:2d}] ncols={len(row):2d}  {row}")
            if i > 25:
                print("   ...")
                break
