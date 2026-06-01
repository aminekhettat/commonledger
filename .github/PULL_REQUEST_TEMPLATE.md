## Description

*Décrivez les changements apportés par cette PR.*

## Type de changement

- [ ] 🐛 `fix:` Bug fix (patch)
- [ ] ✨ `feat:` Nouvelle fonctionnalité (minor)
- [ ] 📚 `docs:` Documentation (patch)
- [ ] ♻️ `refactor:` Refactorisation (patch)
- [ ] 🧪 `test:` Tests (patch)
- [ ] ⚙️ `chore:` Maintenance (patch)
- [ ] 💥 `feat!:` Breaking change (major — demande explicite uniquement)

## Issues liées

Closes #(numéro)

## Checklist

### Code
- [ ] Le code suit les conventions du projet (ruff, mypy)
- [ ] Aucun `print()` laissé dans le code de production
- [ ] Les fonctions complexes sont documentées (docstring)
- [ ] Les types sont annotés pour les fonctions publiques

### Tests
- [ ] Les tests unitaires couvrent les nouveaux comportements
- [ ] `pytest tests/ -m "not integration and not ui"` passe en vert
- [ ] La couverture ne diminue pas (`--cov-fail-under=75`)

### Accessibilité (si UI modifiée)
- [ ] Tous les nouveaux widgets ont `setAccessibleName()`
- [ ] L'ordre de tabulation est logique
- [ ] Les actions principales ont un raccourci clavier
- [ ] Le comportement a été vérifié avec NVDA en mode offscreen

### Documentation
- [ ] `CHANGELOG.md` mis à jour si fonctionnalité significative
- [ ] Le `README.md` mis à jour si nécessaire
- [ ] Le manuel `docs/manuel_utilisateur.html` mis à jour

## Tests effectués

Décrivez les tests manuels et automatiques réalisés.
