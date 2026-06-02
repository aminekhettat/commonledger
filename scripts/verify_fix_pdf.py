"""Vérifie que le bug '4COTISATION' est corrigé dans les PDFs."""
import sys, json, pathlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.parser.la_poste_parser import LaPosteParser
config = json.load(open("config/association.json", encoding="utf-8"))
DOSSIER_PDF = r"E:\Culture musique\Documents\Compte bancaire\Releves\2025"

parser = LaPosteParser(config)
releves = parser.parser_dossier(DOSSIER_PDF)

print("=== Recherche artefacts '4...' dans les libellés 2025 ===")
nb_artefacts = 0
for r in releves:
    for t in r.transactions:
        if t.libelle and t.libelle[0].isdigit():
            print(f"  ARTEFACT : {t.date}  {float(t.montant):>10.2f}€  {t.libelle!r}")
            nb_artefacts += 1

if nb_artefacts == 0:
    print("  Aucun artefact trouvé — le fix fonctionne !")
else:
    print(f"\n  {nb_artefacts} artefact(s) restant(s)")

# Vérifier que la cotisation ADISPO du 17/07 est correcte maintenant
print("\n=== Transactions ADISPO en juillet 2025 ===")
for r in releves:
    for t in r.transactions:
        if "ADISPO" in t.libelle and t.date.year == 2025 and t.date.month == 7:
            print(f"  {t.date}  {float(t.montant):>10.2f}€  {t.libelle!r}")
