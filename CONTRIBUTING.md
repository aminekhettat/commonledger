# Guide de contribution — CommonLedger

Merci de votre intérêt pour CommonLedger ! Ce guide explique comment contribuer
de manière efficace et respectueuse.

## Prérequis

- Python 3.11+
- Git
- Windows 10/11 (l'application est Windows-only pour l'instant)

## Installation de l'environnement de développement

```bash
git clone https://github.com/aminekhettat/commonledger.git
cd commonledger
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pre-commit install
pre-commit install --hook-type commit-msg
```

## Convention de commits (Conventional Commits)

Tous les commits **doivent** suivre ce format :

```
<type>(<scope>): <description courte>

[corps optionnel]

[BREAKING CHANGE: description si rupture de compatibilité]
```

### Types autorisés

| Type | Effet sur la version | Usage |
|---|---|---|
| `feat` | MINOR (0.1.0 → 0.2.0) | Nouvelle fonctionnalité |
| `fix` | PATCH (0.1.0 → 0.1.1) | Correction de bug |
| `chore` | PATCH | Maintenance, deps |
| `docs` | PATCH | Documentation |
| `refactor` | PATCH | Refactorisation sans changement de comportement |
| `test` | PATCH | Ajout ou modification de tests |
| `perf` | PATCH | Amélioration de performance |
| `ci` | PATCH | Changements CI/CD |
| `feat!` ou `BREAKING CHANGE:` | **MAJOR (demande explicite)** | Rupture de compatibilité |

### Exemples valides

```
feat(parser): add support for Crédit Agricole PDF format
fix(bilan): correct amortissement calculation for partial year
docs(readme): update installation instructions
chore(deps): upgrade pdfplumber to 0.12.0
```

## Workflow de développement

```
main          ← releases uniquement (CI/CD + versioning auto)
  └── develop ← intégration
        ├── feat/nom-feature
        ├── fix/nom-bug
        └── chore/nom-tache
```

1. Créer une branche depuis `develop` : `git checkout -b feat/ma-feature develop`
2. Développer et commiter en Conventional Commits
3. Ouvrir une Pull Request vers `develop`
4. Le CI doit passer : lint, types, sécurité, tests, docs
5. Après review, merge dans `develop`
6. Merge `develop` → `main` déclenche le release automatique

## Tests

```bash
# Tous les tests (sauf intégration et UI)
pytest tests/ -m "not integration and not ui"

# Avec couverture
pytest tests/ --cov=core --cov-report=term-missing

# Tests d'intégration (nécessite les PDFs sur le disque E)
pytest tests/ -m integration

# Tests UI (nécessite un affichage)
pytest tests/ -m ui
```

## Accessibilité — critère non négociable

CommonLedger est développé par et pour des personnes déficientes visuelles.
**Tout widget PySide6 doit avoir :**
- `setAccessibleName()` — nom court lu par NVDA/JAWS
- `setAccessibleDescription()` — description longue
- Un ordre de tabulation logique (`setTabOrder`)
- Un raccourci clavier associé si c'est une action importante

Les widgets sans label accessible seront refusés en review.

## Ajouter un parseur bancaire

CommonLedger ne supporte actuellement que La Banque Postale (CCP).
Pour ajouter une nouvelle banque :

1. Créer `core/parser/<nom_banque>_parser.py` héritant de `LaPosteParser`
2. Surcharger `verifier_appartenance()`, `_extraire_lignes_page()`, `_extraire_soldes()`
3. Ajouter des tests dans `tests/test_parser/test_<nom_banque>_parser.py`
4. Mettre à jour le `README.md`

## Code de style

Le projet utilise **ruff** pour le linting et le formatage. Les règles
sont dans `pyproject.toml`. Pour vérifier :

```bash
ruff check core/ tests/
ruff format core/ tests/
```

## Questions ?

- Ouvrir une **Issue** sur GitHub
- Email : [contact@blindsystems.org](mailto:contact@blindsystems.org)
