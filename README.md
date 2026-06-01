# CommonLedger 📊

> Comptabilité simplifiée pour associations loi 1901 — open source, accessible, gratuit.

[![CI](https://github.com/aminekhettat/commonledger/actions/workflows/ci.yml/badge.svg)](https://github.com/aminekhettat/commonledger/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-68%25-yellowgreen.svg)](htmlcov/index.html)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/UI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Accessibilité](https://img.shields.io/badge/Accessibilité-NVDA%20%2F%20JAWS-orange.svg)](#accessibilité)
[![Licence](https://img.shields.io/badge/Licence-PolyForm%20NonCommercial-red.svg)](LICENSE)
[![Windows](https://img.shields.io/badge/Plateforme-Windows-blue.svg)](#installation)

---

## Présentation

**CommonLedger** est une application de bureau Windows qui automatise la comptabilité annuelle d'une petite association à partir des **relevés bancaires PDF La Banque Postale (CCP)**.

Elle génère automatiquement un **compte de résultat complet** avec graphiques, prêt à présenter en assemblée générale.

Conçue dès le départ pour être **totalement accessible aux personnes non voyantes** (NVDA, JAWS), elle a été développée par et pour des bénévoles associatifs.

---

## Fonctionnalités

### 📥 Import automatique
- Extraction des transactions depuis les relevés PDF La Banque Postale (formats 2013–2025)
- Détection automatique des doublons et vérification des soldes
- Support des virements instantanés, prélèvements SEPA, HelloAsso/Stripe

### 🏷️ Catégorisation intelligente
- Classification automatique par mots-clés (cotisations, locations, communication…)
- **Éclatement de transactions** : un virement HelloAsso → cotisations + dons
- Interface de révision manuelle pour les cas ambigus
- Catalogue de catégories entièrement personnalisable

### 📊 Rapports professionnels
- **Compte de résultat** annuel ou intermédiaire (mi-année, avant AG…)
- **Graphiques** : camembert recettes, camembert dépenses, histogramme mensuel, courbe de trésorerie
- **Tableaux alternatifs** pour chaque graphique (accessibilité)
- Export **Word (.docx)**, **PDF** (via Microsoft Word ou LibreOffice) et **CSV** (audit, tableur)
- En-tête personnalisé : logo, couleurs, SIRET, Waldec, site web

### 📁 Comptabilité analytique
- Création de **projets** (concerts, tournées, ateliers…)
- Ventilation recettes/dépenses par projet
- Budget prévisionnel par catégorie avec suivi écart réel/prévu

### ♿ Accessibilité totale
- Navigation 100% clavier (pas de dépendance à la souris)
- Compatible **NVDA** (priorité) et **JAWS** via API UIA Windows
- Labels accessibles sur tous les widgets
- Tableaux textuels pour tous les graphiques
- Raccourcis Alt+1 à Alt+5 pour la navigation entre onglets

---

## Captures d'écran

> *(À venir)*

---

## Installation

### Prérequis
- Windows 10/11 (64 bits)
- Python 3.11 ou supérieur
- Microsoft Word ou LibreOffice (pour l'export PDF, optionnel)

### Depuis les sources

```bash
# 1. Cloner le dépôt
git clone https://github.com/aminekhettat/commonledger.git
cd commonledger

# 2. Créer un environnement virtuel
python -m venv venv
venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer votre association
copy config\association.example.json config\association.json
# Éditer config\association.json avec vos informations

# 5. Lancer l'application
python main.py
```

### Configuration initiale

Au premier lancement, allez dans **Paramètres (Alt+5)** pour renseigner :
- Nom, adresse, SIRET, Waldec de votre association
- IBAN de votre compte bancaire
- Logo et couleurs (personnalisation des rapports)

---

## Guide d'utilisation rapide

1. **Alt+1 — Import** : sélectionner le dossier contenant vos relevés PDF, saisir le solde au 1er janvier, cliquer sur "Importer"
2. **Alt+2 — Catégorisation** : réviser les transactions non reconnues automatiquement
3. **Alt+3 — Rapport** : choisir la période, aperçu, puis générer le Word/PDF
4. **Alt+4 — Projets** : créer vos projets analytiques (concerts, etc.)
5. **Alt+5 — Paramètres** : configuration de l'association et des catégories

---

## Structure du projet

```
commonledger/
├── main.py                       # Point d'entrée
├── pyproject.toml                # Métadonnées + config bump-my-version
├── requirements.txt              # Dépendances Python
├── config/
│   ├── association.example.json  # Template configuration (à copier)
│   ├── categories.json           # Catalogue des catégories comptables
│   └── assets/                   # Logo de l'association
├── core/
│   ├── parser/                   # Extraction PDF La Banque Postale (2013–2025)
│   ├── categorizer/              # Moteur de catégorisation + split HelloAsso
│   ├── accounting/               # Compte de résultat, analytique par projet
│   └── reporter/                 # Word, PDF, CSV avec graphiques matplotlib
├── ui/
│   ├── main_window.py            # Fenêtre principale PySide6
│   ├── accessibility.py          # Helpers NVDA/JAWS (labels, tab order)
│   └── widgets/                  # Import, Catégorisation, Rapport, Projets, Paramètres
└── data/                         # Données locales (gitignorées)
```

---

## Compatibilité bancaire

| Banque | Format | Statut |
|---|---|---|
| La Banque Postale (CCP) | PDF | ✅ Supporté (2013–2025) |
| Autres banques | — | 🔜 Contributions bienvenues |

---

## Contribuer

Les contributions sont les bienvenues ! Avant de soumettre une Pull Request :

1. Forker le dépôt
2. Créer une branche : `git checkout -b feature/nom-de-la-feature`
3. Committer vos changements
4. Ouvrir une Pull Request sur `develop`

**Domaines prioritaires :**
- Parseurs pour d'autres banques françaises (Crédit Agricole, BNP, Société Générale…)
- Tests unitaires
- Documentation (Sphinx)
- Traductions

---

## Licence

Ce projet est distribué sous licence **PolyForm Noncommercial License 1.0.0**.

✅ Utilisation personnelle et associative libre  
✅ Modification et fork pour usage non commercial  
✅ Attribution requise  
❌ Redistribution commerciale interdite  
❌ Vente du logiciel interdite  

Voir [LICENSE](LICENSE) pour le texte complet.

---

## Crédits

Développé par **Amine Khettat** ([@aminekhettat](https://github.com/aminekhettat))  
Inspiré par les besoins réels de l'[Association Culture Musique](https://www.sabamusic.fr) — Paris

---

---

## Versioning

Ce projet utilise [bump-my-version](https://github.com/callowayproject/bump-my-version) et le versionnage sémantique :

```bash
bump-my-version bump patch   # 0.1.0 → 0.1.1  correctif
bump-my-version bump minor   # 0.1.0 → 0.2.0  nouvelle fonctionnalité
bump-my-version bump major   # 0.1.0 → 1.0.0  rupture de compatibilité
```

---

*CommonLedger — Because managing your association's finances shouldn't be a burden.*
