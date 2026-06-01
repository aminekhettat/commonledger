"""
Script de verification que la documentation Sphinx est a jour.

Utilise par :
  - Le hook git pre-push (bloque le push si la doc est obsolete)
  - Le pipeline CI (job docs dans ci.yml)

Exit codes :
  0 -- Documentation a jour, push autorise
  1 -- Documentation obsolete ou absente, push bloque
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone
import subprocess

# Encodage UTF-8 pour eviter les erreurs sur Windows (cp1252 ne supporte pas les emojis)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent


def date_dernier_commit_core():
    """Retourne la date du dernier commit touchant core/."""
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", "core/"],
            capture_output=True, text=True, cwd=ROOT
        )
        ts = r.stdout.strip()
        if ts:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except Exception:
        pass
    return None


def date_dernier_build_sphinx():
    """Retourne la date du dernier build Sphinx depuis .buildinfo."""
    buildinfo = ROOT / "docs" / "sphinx" / "_build" / "html" / ".buildinfo"
    if buildinfo.exists():
        mtime = buildinfo.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    return None


def main():
    print("Verification de la documentation Sphinx...")

    date_code = date_dernier_commit_core()
    date_doc = date_dernier_build_sphinx()

    if date_doc is None:
        print("ERREUR : La documentation n'a pas encore ete generee.")
        print("  Executez : docs\\sphinx\\Makefile.bat html")
        return 1

    if date_code and date_doc < date_code:
        print("ERREUR : La documentation est obsolete.")
        print(f"  Derniere modif core/ : {date_code.strftime('%d/%m/%Y %H:%M')}")
        print(f"  Dernier build Sphinx : {date_doc.strftime('%d/%m/%Y %H:%M')}")
        print("  Executez : docs\\sphinx\\Makefile.bat html")
        return 1

    print(f"OK : Documentation a jour (build : {date_doc.strftime('%d/%m/%Y %H:%M')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
