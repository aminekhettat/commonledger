"""
Script de vérification pré-push — CommonLedger.

Exécuté par le hook git pre-push avant chaque push vers le dépôt distant.
Bloque le push si l'un des outils signale une erreur.

Outils vérifiés (dans l'ordre) :
    1. pytest       — tests unitaires, couverture 100 % obligatoire
    2. ruff check   — linting PEP8, imports, sécurité basique
    3. mypy         — vérification statique des types (core/ uniquement)
    4. bandit       — audit de sécurité (core/ uniquement)
    5. sphinx       — documentation à jour (buildinfo récent)

Chaque outil est exécuté avec les paramètres définis dans pyproject.toml
(aucun seuil dégradé ici — tout est configuré à la source).
"""

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Forcer UTF-8 sur les terminaux Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
PYTHON = sys.executable

# ── Couleurs ANSI (désactivées sur Windows sans support) ─────────────────────
_COLOR = sys.stdout.isatty()
VERT  = "\033[32m" if _COLOR else ""
ROUGE = "\033[31m" if _COLOR else ""
JAUNE = "\033[33m" if _COLOR else ""
BLEU  = "\033[36m" if _COLOR else ""
RESET = "\033[0m"  if _COLOR else ""


def titre(msg: str) -> None:
    print(f"\n{BLEU}{'='*60}{RESET}")
    print(f"{BLEU}  {msg}{RESET}")
    print(f"{BLEU}{'='*60}{RESET}")


def ok(msg: str) -> None:
    print(f"  {VERT}OK{RESET}  {msg}")


def erreur(msg: str) -> None:
    print(f"  {ROUGE}ECHEC{RESET}  {msg}")


def info(msg: str) -> None:
    print(f"  {JAUNE}INFO{RESET}  {msg}")


def run(
    commande: list[str],
    description: str,
    *,
    afficher_sortie: bool = True,
) -> bool:
    """
    Exécute une commande et retourne True si elle réussit (code retour 0).

    Args:
        commande:       Liste des arguments de la commande.
        description:    Description courte pour les messages.
        afficher_sortie: Si True, affiche stdout/stderr en cas d'échec.

    Returns:
        True si succès, False si échec.
    """
    result = subprocess.run(
        commande,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )
    if result.returncode == 0:
        ok(description)
        return True

    erreur(description)
    if afficher_sortie:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
    return False


def verifier_pytest() -> bool:
    """Exécute pytest avec couverture 100 % (paramètres dans pyproject.toml)."""
    titre("1/5  PYTEST — Tests unitaires + couverture")
    return run(
        [
            PYTHON, "-m", "pytest",
            "tests/",
            "--ignore=tests/test_integration.py",
            "-q",
            "--tb=short",
        ],
        "pytest : tous les tests passent, couverture >= 100 %",
    )


def verifier_ruff() -> bool:
    """Vérifie le style et les problèmes de code avec ruff."""
    titre("2/5  RUFF — Linting et style")
    # ruff check : lint
    ok_lint = run(
        [PYTHON, "-m", "ruff", "check", "core/", "ui/", "tests/"],
        "ruff check : aucune infraction de style ou de sécurité",
    )
    # ruff format --check : formatage
    ok_fmt = run(
        [PYTHON, "-m", "ruff", "format", "--check", "core/", "ui/"],
        "ruff format : formatage conforme",
    )
    return ok_lint and ok_fmt


def verifier_mypy() -> bool:
    """Vérifie les types statiques sur core/ avec mypy (config dans pyproject.toml)."""
    titre("3/5  MYPY — Vérification statique des types")
    return run(
        [PYTHON, "-m", "mypy", "core/"],
        "mypy : aucune erreur de typage dans core/",
    )


def verifier_bandit() -> bool:
    """Audit de sécurité du code avec bandit."""
    titre("4/5  BANDIT — Audit de sécurité")
    return run(
        [
            PYTHON, "-m", "bandit",
            "-r", "core/",
            "-c", "pyproject.toml",
            "-q",
        ],
        "bandit : aucun problème de sécurité dans core/",
    )


def verifier_docs() -> bool:
    """Vérifie que la documentation Sphinx est à jour."""
    titre("5/5  SPHINX — Documentation à jour")

    # Importer et réutiliser le script existant
    check_docs = ROOT / "scripts" / "check_docs.py"
    if not check_docs.exists():
        info("scripts/check_docs.py introuvable — vérification docs ignorée")
        return True

    result = subprocess.run(
        [PYTHON, str(check_docs)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )
    if result.returncode == 0:
        ok(result.stdout.strip() or "Sphinx : documentation à jour")
        return True

    erreur("Sphinx : documentation obsolète ou absente")
    print(result.stdout.strip())
    print(
        f"\n  {JAUNE}Commande pour regénérer :{RESET}"
        "\n    docs\\sphinx\\make.bat html"
    )
    return False


def main() -> int:
    """Point d'entrée principal — retourne 0 si tout est OK, 1 sinon."""
    print(f"\n{BLEU}CommonLedger — Vérification pré-push{RESET}")
    print(f"Répertoire : {ROOT}")
    print(f"Python     : {PYTHON}")

    resultats: dict[str, bool] = {
        "pytest":  verifier_pytest(),
        "ruff":    verifier_ruff(),
        "mypy":    verifier_mypy(),
        "bandit":  verifier_bandit(),
        "sphinx":  verifier_docs(),
    }

    # ── Résumé final ─────────────────────────────────────────────────────────
    print(f"\n{BLEU}{'='*60}{RESET}")
    print(f"{BLEU}  RÉSUMÉ{RESET}")
    print(f"{BLEU}{'='*60}{RESET}")

    tous_ok = True
    for outil, succes in resultats.items():
        symbole = f"{VERT}PASS{RESET}" if succes else f"{ROUGE}FAIL{RESET}"
        print(f"  {symbole}  {outil}")
        if not succes:
            tous_ok = False

    if tous_ok:
        print(f"\n{VERT}Toutes les vérifications sont passées — push autorisé.{RESET}\n")
        return 0

    print(
        f"\n{ROUGE}PUSH BLOQUÉ.{RESET}"
        "\nCorrigez les erreurs ci-dessus avant de pousser.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
