# Politique de sécurité — CommonLedger

## Versions supportées

| Version | Supportée |
|---|---|
| 0.1.x (dernière) | ✅ Oui |
| < 0.1.0 | ❌ Non |

## Données sensibles

CommonLedger traite des données financières sensibles :
- Numéros IBAN / BIC
- Historiques bancaires
- Numéros SIRET / Waldec

**Ces données ne quittent jamais votre machine.** Elles sont stockées
uniquement dans `config/association.json` et `data/` — tous deux
exclus de git par `.gitignore`.

## Signaler une vulnérabilité

**Ne pas créer d'Issue publique pour les vulnérabilités de sécurité.**

Envoyer un email à **[contact@blindsystems.org](mailto:contact@blindsystems.org)**
avec :
- Description de la vulnérabilité
- Étapes pour la reproduire
- Impact potentiel
- Suggestion de correction (optionnel)

Réponse sous **48h**, correction sous **7 jours** pour les critiques.

## Bonnes pratiques de déploiement

1. Ne jamais committer `config/association.json` (IBAN inclus)
2. Ne jamais committer `data/` (transactions financières)
3. Vérifier que `.gitignore` contient bien ces chemins
4. Utiliser des permissions fichiers restrictives sur `config/association.json`

## Analyse de sécurité automatisée

Le pipeline CI/CD inclut **Bandit** qui analyse le code Python à chaque push
et bloque les merges en cas de vulnérabilité de niveau MEDIUM ou supérieur.
