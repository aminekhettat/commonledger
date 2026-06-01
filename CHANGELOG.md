# Changelog

Toutes les modifications notables de CommonLedger sont documentées ici.

Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
versioning selon [Semantic Versioning](https://semver.org/lang/fr/).

Commits suivant la convention [Conventional Commits](https://www.conventionalcommits.org/fr/).

---

## [0.1.0] — 2026-06-01

### Ajouté
- Parseur PDF La Banque Postale (CCP) — formats 2013–2026 validés
- Moteur de catégorisation automatique par mots-clés (JSON configurable)
- Éclatement (split) de transactions multi-catégories (HelloAsso, etc.)
- Comptabilité analytique par projet (concerts, tournées, ateliers)
- Compte de résultat annuel et intermédiaire
- Bilan comptable simplifié (ANC 2018-06 — associations loi 1901)
- Table des immobilisations avec amortissement linéaire
- Report à nouveau inter-exercices
- Génération de rapports Word (.docx) avec graphiques matplotlib
- Conversion automatique PDF via Microsoft Word COM ou LibreOffice
- Export CSV (synthèse + détail des transactions)
- Interface graphique PySide6 — accessible NVDA/JAWS (API UIA Windows)
- Navigation 100% clavier (raccourcis Alt+1 à Alt+5)
- Tableau de catégorisation avec colonne Projet
- Panel graphique interactif (camembert, histogramme, courbe de trésorerie)
- Persistance des paramètres (association.json)
- Manuel d'utilisation HTML (docs/manuel_utilisateur.html)
- Dialogue "À propos" (BLIND SYSTEMS)
- Icône application "Civic Precision" (PNG + ICO multi-résolution)
- Support multi-années 2013–2026 (13/13 avec écart = 0,00€)
- Versioning automatique avec bump-my-version + semantic-release
- Pipeline CI/CD GitHub Actions (lint, typecheck, security, tests, docs)

### Technique
- Python 3.11+ — PySide6 — matplotlib — python-docx — pdfplumber
- Tests unitaires pytest avec couverture ≥75% sur core/
- Ruff (lint + format) — MyPy (types) — Bandit (sécurité)
- Pre-commit hooks
- Conventional Commits

---

*Développé par Amine Khettat — BLIND SYSTEMS — © 2026*
