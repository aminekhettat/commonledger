"""
Installe les hooks git pour CommonLedger.

Hooks installés :
  - pre-push : vérifie que la doc Sphinx est à jour avant tout push
  - commit-msg : vérifie le format Conventional Commits

Usage : python scripts/install_hooks.py
"""

import os
import stat
from pathlib import Path

ROOT = Path(__file__).parent.parent
HOOKS_DIR = ROOT / ".git" / "hooks"


def installer_hook_pre_push() -> None:
    """Installe le hook pre-push."""
    hook = HOOKS_DIR / "pre-push"
    contenu = """#!/bin/sh
# CommonLedger — Hook pre-push
# Vérifie que la documentation Sphinx est à jour avant le push.

echo "Vérification de la documentation Sphinx..."
python scripts/check_docs.py
if [ $? -ne 0 ]; then
    echo ""
    echo "PUSH BLOQUÉ : Régénérez la documentation avant de pusher."
    echo "  Windows : docs\\\\sphinx\\\\Makefile.bat html"
    echo "  Linux   : make -C docs/sphinx html"
    exit 1
fi

echo "Documentation OK — push autorisé."
exit 0
"""
    hook.write_text(contenu, encoding="utf-8")
    # Rendre exécutable
    mode = hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    hook.chmod(mode)
    print(f"✅ Hook pre-push installé : {hook}")


def installer_hook_commit_msg() -> None:
    """Installe le hook commit-msg (Conventional Commits)."""
    hook = HOOKS_DIR / "commit-msg"
    contenu = r"""#!/bin/sh
# CommonLedger — Hook commit-msg
# Vérifie le format Conventional Commits.

MSG=$(cat "$1")
PATTERN="^(feat|fix|chore|docs|style|refactor|test|perf|ci|build|revert)(\(.+\))?(!)?: .{1,100}"

if ! echo "$MSG" | grep -qE "$PATTERN"; then
    echo "COMMIT REJETÉ : Message non conforme au format Conventional Commits."
    echo ""
    echo "Format attendu : <type>(<scope>): <description>"
    echo "Types valides  : feat, fix, chore, docs, style, refactor, test, perf, ci, build"
    echo ""
    echo "Exemples :"
    echo "  feat(parser): add Crédit Agricole support"
    echo "  fix(bilan): correct amortissement calculation"
    echo "  docs: update README with new features"
    exit 1
fi
exit 0
"""
    hook.write_text(contenu, encoding="utf-8")
    mode = hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    hook.chmod(mode)
    print(f"✅ Hook commit-msg installé : {hook}")


if __name__ == "__main__":
    print("Installation des hooks git CommonLedger...")
    if not HOOKS_DIR.exists():
        print(f"ERREUR : Répertoire git introuvable : {HOOKS_DIR}")
        print("Lancez ce script depuis la racine du dépôt.")
        exit(1)

    installer_hook_pre_push()
    installer_hook_commit_msg()
    print("\nHooks installés. Pour tester : git push --dry-run")
