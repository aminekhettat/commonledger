@echo off
REM CommonLedger — Génération de la documentation Sphinx
REM Usage : docs\sphinx\Makefile.bat [html|clean|check]
cd /d "C:\Users\khett\OneDrive\Documents\My projects\Projets Python\Comptasso"

if "%1"=="clean" (
    rmdir /s /q docs\sphinx\_build 2>nul
    echo Documentation nettoyée.
    goto :end
)

if "%1"=="check" (
    echo Vérification que la doc est à jour...
    python scripts\check_docs.py
    goto :end
)

echo Génération de la documentation Sphinx...
python -m sphinx -b html docs\sphinx docs\sphinx\_build\html -W --keep-going
if %errorlevel% == 0 (
    echo.
    echo Documentation générée : docs\sphinx\_build\html\index.html
    start docs\sphinx\_build\html\index.html
) else (
    echo ERREUR dans la génération de la documentation.
    exit /b 1
)

:end
