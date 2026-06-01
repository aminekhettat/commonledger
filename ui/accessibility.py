"""
Helpers d'accessibilité pour PySide6 / NVDA.

Ce module fournit des fonctions utilitaires pour garantir que
tous les widgets de l'application sont correctement lus par
les lecteurs d'écran NVDA et JAWS via l'API UIA de Windows.

Règles appliquées systématiquement :
    1. setAccessibleName()        → Nom court lu par le lecteur d'écran
    2. setAccessibleDescription() → Description longue (F1 dans NVDA)
    3. setTabOrder()              → Ordre de focus logique haut→bas, gauche→droite
    4. Raccourcis clavier Alt+X   → Toutes les actions accessibles au clavier

Notes NVDA :
    - NVDA lit le nom accessible des QLabel associés aux QLineEdit
      uniquement si on utilise QLabel.setBuddy(widget).
    - Les QTableWidget nécessitent des headers explicites pour être
      correctement annoncés ligne par ligne.
    - Les QProgressBar doivent avoir setAccessibleName() sinon NVDA
      annonce seulement le pourcentage sans contexte.

Notes JAWS :
    - JAWS lit les mêmes propriétés UIA que NVDA pour les widgets Qt.
    - La différence principale concerne les formulaires : JAWS active
      le "mode formulaire" automatiquement sur les QLineEdit et QComboBox.
    - Les QGroupBox avec titre sont bien annoncés par les deux lecteurs.
"""

from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QTableWidget, QGroupBox, QProgressBar, QCheckBox, QRadioButton,
)
from PySide6.QtCore import Qt


def configurer_label_champ(label: QLabel, widget: QWidget, nom: str, description: str = "") -> None:
    """
    Associe un QLabel à son champ pour l'accessibilité clavier et lecteur d'écran.

    Le QLabel devient le "buddy" du widget : Tab le met en focus, et NVDA
    annonce le texte du label avant la valeur du champ.

    Args:
        label:       Le QLabel descriptif.
        widget:      Le champ associé (QLineEdit, QComboBox, etc.).
        nom:         Nom accessible court (lu en premier par NVDA).
        description: Description longue optionnelle (Alt+F4 dans NVDA).
    """
    label.setBuddy(widget)
    widget.setAccessibleName(nom)
    if description:
        widget.setAccessibleDescription(description)


def configurer_bouton(bouton: QPushButton, nom: str, description: str = "") -> None:
    """
    Configure l'accessibilité d'un bouton.

    Args:
        bouton:      Le QPushButton à configurer.
        nom:         Nom accessible (annoncé par NVDA + rôle "bouton").
        description: Description de l'action (optionnel).
    """
    bouton.setAccessibleName(nom)
    if description:
        bouton.setAccessibleDescription(description)


def configurer_tableau(
    tableau: QTableWidget,
    nom: str,
    description: str = "",
    headers_colonnes: list[str] = None,
) -> None:
    """
    Configure l'accessibilité d'un tableau.

    NVDA annonce "tableau, N lignes, M colonnes, [nom]" à l'entrée.
    Chaque cellule est annoncée avec son contenu + l'en-tête de colonne.

    Args:
        tableau:           QTableWidget à configurer.
        nom:               Nom du tableau (ex: "Transactions non catégorisées").
        description:       Description plus longue.
        headers_colonnes:  Textes d'en-têtes (renforce l'annonce NVDA par colonne).
    """
    tableau.setAccessibleName(nom)
    if description:
        tableau.setAccessibleDescription(description)

    # S'assurer que les en-têtes sont visibles et textuels
    if headers_colonnes and tableau.horizontalHeader():
        tableau.horizontalHeader().setVisible(True)
        for i, header in enumerate(headers_colonnes):
            if i < tableau.columnCount() and tableau.horizontalHeaderItem(i):
                tableau.horizontalHeaderItem(i).setToolTip(header)


def configurer_groupe(groupe: QGroupBox, description: str = "") -> None:
    """
    Configure l'accessibilité d'un QGroupBox.

    Le titre du QGroupBox est automatiquement annoncé par NVDA
    à l'entrée du groupe. Cette fonction ajoute la description longue.

    Args:
        groupe:      QGroupBox à configurer.
        description: Description du groupe (annoncée avec Alt+F4 dans NVDA).
    """
    if description:
        groupe.setAccessibleDescription(description)


def configurer_barre_progression(barre: QProgressBar, nom: str) -> None:
    """
    Configure l'accessibilité d'une barre de progression.

    Sans nom accessible, NVDA annonce seulement "50 %". Avec le nom,
    il annonce "Importation des relevés : 50 %".

    Args:
        barre: QProgressBar à configurer.
        nom:   Contexte de la progression.
    """
    barre.setAccessibleName(nom)


def definir_ordre_tabulation(widgets: list[QWidget]) -> None:
    """
    Définit l'ordre de tabulation logique entre les widgets.

    L'ordre donné est l'ordre dans lequel Tab naviguera.

    Args:
        widgets: Liste de widgets dans l'ordre de navigation souhaité.
    """
    for i in range(len(widgets) - 1):
        QWidget.setTabOrder(widgets[i], widgets[i + 1])


def annonce_status(widget: QWidget, message: str) -> None:
    """
    Met à jour le texte accessible d'un widget pour forcer une annonce NVDA.

    Utilisé pour annoncer dynamiquement des changements d'état
    (ex: "Import terminé : 45 transactions chargées").

    Args:
        widget:  Widget portant l'annonce (typiquement un QLabel de status).
        message: Message à annoncer.
    """
    widget.setAccessibleDescription(message)
    # Déclencher l'événement d'accessibilité "valeur changée"
    from PySide6.QtGui import QAccessibleEvent
    from PySide6.QtCore import QEvent
    # L'update du texte du label suffit pour que NVDA en "live region" le lise
    if hasattr(widget, "setText"):
        widget.setText(message)
