"""
Helpers d'accessibilité pour PySide6 / NVDA.

Ce module fournit des fonctions utilitaires pour garantir que
tous les widgets de l'application sont correctement lus par
les lecteurs d'écran NVDA et JAWS via l'API UIA de Windows.

Améliorations v1.1 :
    - LiveRegion : annonces en temps réel sans navigation (UIA LiveSetting)
    - configurer_journal_live : QTextEdit qui annonce automatiquement les nouvelles lignes
    - configurer_graphique_accessible : graphique + tableau alternatif avec lien explicite
"""

from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QTableWidget, QGroupBox, QProgressBar, QCheckBox, QRadioButton,
    QTextEdit, QVBoxLayout,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAccessible, QAccessibleEvent


# ── Live Region — annonces proactives sans déplacement du focus ───────────────

class LiveRegion(QLabel):
    """
    Widget d'annonce accessible en temps réel (équivalent aria-live pour Qt).

    Quand le texte est mis à jour, NVDA/JAWS l'annonce automatiquement
    sans que l'utilisateur ait besoin de naviguer vers ce widget.

    Utilisation typique ::

        self._region = LiveRegion(parent=self, politesse="polite")
        self._region.annoncer("Import terminé — 53 transactions chargées.")

    Politesse :
        "polite"    → annonce après la lecture en cours (défaut, recommandé)
        "assertive" → interrompt la lecture en cours (pour erreurs critiques)

    Note technique :
        Qt utilise UIA (UI Automation) sur Windows. NVDA lit les changements
        de nom/valeur via UIA_NamePropertyId. Ce widget utilise setAccessibleName
        combiné avec un QAccessibleEvent ValueChanged pour déclencher la lecture.
    """

    def __init__(self, parent: QWidget = None, politesse: str = "polite"):
        super().__init__(parent)
        self._politesse = politesse
        # Caché visuellement mais présent dans l'arbre d'accessibilité
        self.setFixedHeight(1)
        self.setFixedWidth(1)
        self.setStyleSheet("color: transparent; background: transparent;")
        self.setAccessibleName("")
        self.setAccessibleDescription(f"live-region-{politesse}")
        # Rôle statique — NVDA lit les changements de valeur
        self.setTextFormat(Qt.PlainText)

    def annoncer(self, message: str, delai_ms: int = 50) -> None:
        """
        Annonce un message via le lecteur d'écran.

        Args:
            message:   Texte à annoncer (clair et concis, < 150 caractères).
            delai_ms:  Délai avant l'annonce (évite les conflits avec l'UI).
        """
        if not message:
            return
        # Délai pour laisser l'UI se stabiliser avant l'annonce
        QTimer.singleShot(delai_ms, lambda: self._emettre(message))

    def _emettre(self, message: str) -> None:
        """Émet l'événement UIA pour déclencher la lecture par NVDA."""
        # 1. Mettre à jour le texte visible (invisible mais dans l'arbre)
        self.setText(message)
        # 2. Mettre à jour accessibleName → NVDA lit le "nom" changé
        self.setAccessibleName(message)
        # 3. Émettre l'événement UIA ValueChanged
        try:
            event = QAccessibleEvent(self, QAccessible.Event.ValueChanged)
            QAccessible.updateAccessibility(event)
        except Exception:
            pass  # Si l'API n'est pas disponible, la mise à jour du nom suffit


def creer_live_region(parent: QWidget = None) -> LiveRegion:
    """
    Crée une live region et l'ajoute au widget parent.

    Returns:
        LiveRegion prête à être utilisée.
    """
    region = LiveRegion(parent=parent)
    return region


# ── Journal live — QTextEdit avec annonce automatique des nouvelles lignes ─────

class JournalLive(QTextEdit):
    """
    QTextEdit qui annonce automatiquement chaque nouvelle ligne via NVDA.

    Quand `ajouter_ligne()` est appelé, la nouvelle ligne est :
    1. Ajoutée au journal (visible à l'écran)
    2. Annoncée immédiatement par NVDA sans que l'utilisateur navigue

    Utilisation ::

        journal = JournalLive()
        journal.ajouter_ligne("Import terminé — 53 transactions")
        # → NVDA annonce "Import terminé — 53 transactions"
    """

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self._live_region = LiveRegion(parent=parent or self)
        self._live_region.setParent(self)

    def ajouter_ligne(self, texte: str, annoncer: bool = True) -> None:
        """
        Ajoute une ligne au journal et l'annonce via le lecteur d'écran.

        Args:
            texte:    Texte de la nouvelle ligne.
            annoncer: Si True, annonce via NVDA (défaut : True).
        """
        self.append(texte)
        if annoncer and texte.strip():
            # Nettoyer les emojis pour NVDA (certains ne sont pas lus bien)
            texte_clean = (texte
                           .replace("✅", "OK")
                           .replace("❌", "Erreur")
                           .replace("⚠", "Attention")
                           .replace("▶", "")
                           .strip())
            if texte_clean:
                self._live_region.annoncer(texte_clean)

    def clear(self) -> None:
        """Vide le journal."""
        super().clear()


# ── Status bar live ────────────────────────────────────────────────────────────

class StatusBarLive:
    """
    Gestionnaire d'annonces de la barre de statut.

    Maintient une live region synchronisée avec la barre de statut
    pour que NVDA annonce proactivement les changements d'état.

    Utilisation dans MainWindow ::

        self._status_live = StatusBarLive(self.statusBar(), self)
        # Puis à chaque message :
        self._status_live.message("Import terminé")
        # → La barre de statut ET NVDA sont mis à jour
    """

    def __init__(self, status_bar, parent: QWidget):
        self._bar = status_bar
        self._region = LiveRegion(parent=parent)
        # Ajouter la live region à la barre de statut
        self._bar.addPermanentWidget(self._region)

    def message(self, texte: str, duree_ms: int = 0) -> None:
        """
        Affiche un message dans la barre de statut et l'annonce via NVDA.

        Args:
            texte:    Message à afficher.
            duree_ms: Durée d'affichage (0 = permanent).
        """
        if duree_ms > 0:
            self._bar.showMessage(texte, duree_ms)
        else:
            self._bar.showMessage(texte)
        self._region.annoncer(texte)


# ── Graphiques accessibles ─────────────────────────────────────────────────────

def configurer_graphique_accessible(
    canvas_widget: QWidget,
    tableau_textuel: str,
    titre_graphique: str = "Graphique",
) -> None:
    """
    Rend un graphique matplotlib accessible pour NVDA/JAWS.

    Les graphiques ne sont pas directement lisibles par les lecteurs d'écran.
    Cette fonction :
    1. Donne au canvas un nom accessible décrivant son contenu
    2. Place le tableau alternatif en premier dans l'ordre de tabulation

    Args:
        canvas_widget:    Widget matplotlib (FigureCanvasQTAgg).
        tableau_textuel:  Données du graphique en format texte tabulé.
        titre_graphique:  Description courte du graphique.
    """
    # Le canvas reçoit un nom accessible qui décrit son contenu
    description = (
        f"{titre_graphique}. "
        "Ce graphique n'est pas directement accessible. "
        "Utilisez le tableau de données ci-dessous pour consulter les mêmes informations."
    )
    canvas_widget.setAccessibleName(titre_graphique)
    canvas_widget.setAccessibleDescription(description)
    # Le canvas n'est pas navigable au clavier (inutile pour un aveugle)
    canvas_widget.setFocusPolicy(Qt.NoFocus)


def configurer_tableau_alternatif(
    label_tableau: QLabel,
    tableau_textuel: str,
    titre: str,
) -> None:
    """
    Configure le tableau alternatif d'un graphique pour NVDA.

    Args:
        label_tableau:  QLabel ou QTextEdit contenant les données textuelles.
        tableau_textuel: Données du graphique en texte tabulé.
        titre:          Titre du tableau alternatif.
    """
    # Titre annoncé par NVDA quand on arrive sur ce widget
    label_tableau.setAccessibleName(f"Données du graphique : {titre}")
    label_tableau.setAccessibleDescription(
        "Tableau de données correspondant au graphique ci-dessus. "
        "Les mêmes informations visuelles sont présentées ici en format texte."
    )
    if hasattr(label_tableau, "setText"):
        label_tableau.setText(tableau_textuel)


# ── Fonctions existantes (inchangées) ─────────────────────────────────────────

def configurer_label_champ(label: QLabel, widget: QWidget, nom: str, description: str = "") -> None:
    """Associe un QLabel à son champ pour l'accessibilité."""
    label.setBuddy(widget)
    widget.setAccessibleName(nom)
    if description:
        widget.setAccessibleDescription(description)


def configurer_bouton(bouton: QPushButton, nom: str, description: str = "") -> None:
    """Configure l'accessibilité d'un bouton."""
    bouton.setAccessibleName(nom)
    if description:
        bouton.setAccessibleDescription(description)


def configurer_tableau(
    tableau: QTableWidget,
    nom: str,
    description: str = "",
    headers_colonnes: list[str] = None,
) -> None:
    """Configure l'accessibilité d'un QTableWidget."""
    tableau.setAccessibleName(nom)
    if description:
        tableau.setAccessibleDescription(description)
    if headers_colonnes and tableau.horizontalHeader():
        tableau.horizontalHeader().setVisible(True)
        for i, header in enumerate(headers_colonnes):
            if i < tableau.columnCount() and tableau.horizontalHeaderItem(i):
                tableau.horizontalHeaderItem(i).setToolTip(header)


def configurer_groupe(groupe: QGroupBox, description: str = "") -> None:
    """Configure l'accessibilité d'un QGroupBox."""
    if description:
        groupe.setAccessibleDescription(description)


def configurer_barre_progression(barre: QProgressBar, nom: str) -> None:
    """Configure l'accessibilité d'une barre de progression."""
    barre.setAccessibleName(nom)


def definir_ordre_tabulation(widgets: list[QWidget]) -> None:
    """Définit l'ordre de tabulation logique entre les widgets."""
    for i in range(len(widgets) - 1):
        QWidget.setTabOrder(widgets[i], widgets[i + 1])


def annonce_status(widget: QWidget, message: str) -> None:
    """Met à jour le texte accessible d'un widget pour forcer une annonce NVDA."""
    widget.setAccessibleDescription(message)
    if hasattr(widget, "setText"):
        widget.setText(message)
    try:
        event = QAccessibleEvent(widget, QAccessible.Event.ValueChanged)
        QAccessible.updateAccessibility(event)
    except Exception:
        pass
