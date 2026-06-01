"""
Dialogue "À propos" de CommonLedger.

Affiche les informations sur l'application, son développeur
et la start-up BLIND SYSTEMS.

Accessibilité NVDA :
    - Fenêtre modale avec titre annoncé à l'ouverture
    - Tous les liens sont des QPushButton accessibles (pas de QLabel non focusable)
    - Ordre de tabulation : infos → lien web → lien email → bouton Fermer
"""

import os
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont, QDesktopServices
from PySide6.QtCore import QUrl


class AboutDialog(QDialog):
    """
    Fenêtre "À propos" de CommonLedger.

    Structure :
      - Bandeau couleur avec logo de l'application
      - Nom, version, tagline
      - Séparateur
      - Infos développeur (BLIND SYSTEMS, Amine Khettat)
      - Liens cliquables : site web, email
      - Copyright
      - Bouton Fermer
    """

    # ── Constantes de l'application ───────────────────────────────────────
    APP_NOM      = "CommonLedger"
    APP_VERSION  = "0.1.0"
    APP_TAGLINE  = "Comptabilité simplifiée pour associations loi 1901"
    APP_GITHUB   = "https://github.com/aminekhettat/commonledger"

    # ── Constantes de l'éditeur ───────────────────────────────────────────
    EDITEUR_NOM      = "BLIND SYSTEMS"
    EDITEUR_TAGLINE  = "L'inclusion en action, l'innovation par passion !"
    EDITEUR_SITE     = "https://www.blindsystems.org"
    EDITEUR_EMAIL    = "contact@blindsystems.org"
    DEVELOPPEUR      = "Amine Khettat"
    COPYRIGHT_ANNEE  = "2026"

    # Couleur principale (bleu marine)
    COULEUR = "#1a3a5c"

    def __init__(self, config_asso: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"À propos de {self.APP_NOM}")
        self.setModal(True)
        self.setFixedWidth(480)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._config = config_asso or {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 20)
        layout.setSpacing(0)

        # ── Bandeau supérieur coloré ───────────────────────────────────────
        bandeau = QFrame()
        bandeau.setStyleSheet(f"background:{self.COULEUR};")
        bandeau.setFixedHeight(120)
        lay_b = QVBoxLayout(bandeau)
        lay_b.setContentsMargins(24, 20, 24, 16)
        lay_b.setSpacing(4)

        lbl_nom = QLabel(self.APP_NOM)
        lbl_nom.setStyleSheet(
            "color:white; font-size:28px; font-weight:bold; background:transparent;"
        )
        lbl_nom.setAccessibleName(f"Nom de l'application : {self.APP_NOM}")
        lay_b.addWidget(lbl_nom)

        lbl_ver = QLabel(f"Version {self.APP_VERSION}")
        lbl_ver.setStyleSheet(
            "color:rgba(255,255,255,0.75); font-size:13px; background:transparent;"
        )
        lbl_ver.setAccessibleName(f"Version {self.APP_VERSION}")
        lay_b.addWidget(lbl_ver)

        lbl_tag = QLabel(self.APP_TAGLINE)
        lbl_tag.setStyleSheet(
            "color:rgba(255,255,255,0.6); font-size:11px; background:transparent;"
        )
        lbl_tag.setWordWrap(True)
        lay_b.addWidget(lbl_tag)

        layout.addWidget(bandeau)

        # ── Corps du dialogue ──────────────────────────────────────────────
        corps = QFrame()
        corps.setStyleSheet("background:white;")
        lay_c = QVBoxLayout(corps)
        lay_c.setContentsMargins(24, 18, 24, 4)
        lay_c.setSpacing(12)

        # Description courte
        desc = QLabel(
            "Application open source de comptabilité simplifiée pour petites associations "
            "loi 1901, conçue pour être totalement accessible aux personnes déficientes visuelles."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size:13px; color:#444;")
        lay_c.addWidget(desc)

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{self.COULEUR}; background:{self.COULEUR};")
        sep.setFixedHeight(2)
        lay_c.addWidget(sep)

        # ── Section éditeur ────────────────────────────────────────────────
        lbl_titre_edit = QLabel("Développé par")
        lbl_titre_edit.setStyleSheet(
            f"font-size:11px; font-weight:bold; color:{self.COULEUR}; "
            "text-transform:uppercase; letter-spacing:1px;"
        )
        lay_c.addWidget(lbl_titre_edit)

        # Logo Blind Systems (si disponible)
        logo_bs = Path("config/assets/blind_systems_logo.png")
        if logo_bs.exists():
            lbl_logo = QLabel()
            pixmap = QPixmap(str(logo_bs))
            lbl_logo.setPixmap(
                pixmap.scaledToHeight(50, Qt.SmoothTransformation)
            )
            lbl_logo.setAccessibleName("Logo BLIND SYSTEMS")
            lay_c.addWidget(lbl_logo)

        lbl_editeur = QLabel(f"<b>{self.EDITEUR_NOM}</b> — {self.EDITEUR_TAGLINE}")
        lbl_editeur.setWordWrap(True)
        lbl_editeur.setStyleSheet(f"font-size:14px; color:{self.COULEUR};")
        lbl_editeur.setAccessibleName(
            f"Éditeur : {self.EDITEUR_NOM}. {self.EDITEUR_TAGLINE}"
        )
        lay_c.addWidget(lbl_editeur)

        lbl_dev = QLabel(f"Fondateur & développeur principal : {self.DEVELOPPEUR}")
        lbl_dev.setStyleSheet("font-size:13px; color:#333;")
        lbl_dev.setAccessibleName(f"Développeur : {self.DEVELOPPEUR}")
        lay_c.addWidget(lbl_dev)

        # Liens cliquables accessibles (QPushButton au lieu de QLabel)
        lay_liens = QHBoxLayout()
        lay_liens.setSpacing(10)

        btn_site = self._creer_lien_bouton(
            "🌐  www.blindsystems.org",
            self.EDITEUR_SITE,
            "Ouvrir le site web de BLIND SYSTEMS dans le navigateur",
        )
        lay_liens.addWidget(btn_site)

        btn_email = self._creer_lien_bouton(
            "✉  contact@blindsystems.org",
            f"mailto:{self.EDITEUR_EMAIL}",
            "Envoyer un email à BLIND SYSTEMS",
        )
        lay_liens.addWidget(btn_email)
        lay_liens.addStretch()
        lay_c.addLayout(lay_liens)

        # Lien GitHub
        btn_github = self._creer_lien_bouton(
            "⚙  Code source sur GitHub",
            self.APP_GITHUB,
            "Ouvrir le dépôt GitHub de CommonLedger",
        )
        btn_github.setStyleSheet(
            "QPushButton{border:none; background:transparent; "
            "color:#666; text-align:left; font-size:12px;}"
            "QPushButton:hover{color:#1a3a5c;}"
        )
        lay_c.addWidget(btn_github)

        # Séparateur
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color:#e0e0e0; background:#e0e0e0;")
        sep2.setFixedHeight(1)
        lay_c.addWidget(sep2)

        # Copyright et licence
        lbl_copy = QLabel(
            f"© {self.COPYRIGHT_ANNEE} {self.DEVELOPPEUR} — {self.EDITEUR_NOM}\n"
            "Distribué sous licence PolyForm Noncommercial 1.0\n"
            "Usage personnel et associatif libre — redistribution commerciale interdite."
        )
        lbl_copy.setWordWrap(True)
        lbl_copy.setStyleSheet("font-size:11px; color:#888; line-height:1.6;")
        lbl_copy.setAccessibleName(
            f"Copyright {self.COPYRIGHT_ANNEE} {self.DEVELOPPEUR}, {self.EDITEUR_NOM}. "
            "Licence PolyForm Noncommercial."
        )
        lay_c.addWidget(lbl_copy)

        layout.addWidget(corps)

        # ── Bouton Fermer ─────────────────────────────────────────────────
        lay_btn = QHBoxLayout()
        lay_btn.setContentsMargins(24, 8, 24, 0)
        lay_btn.addStretch()
        btn_fermer = QPushButton("&Fermer")
        btn_fermer.setFixedWidth(100)
        btn_fermer.setMinimumHeight(36)
        btn_fermer.setDefault(True)
        btn_fermer.setStyleSheet(
            f"QPushButton{{background:{self.COULEUR};color:white;"
            "border-radius:4px;font-size:13px;}}"
            f"QPushButton:hover{{background:#2a5a8c;}}"
        )
        btn_fermer.setAccessibleName("Fermer la fenêtre À propos")
        btn_fermer.clicked.connect(self.accept)
        lay_btn.addWidget(btn_fermer)
        layout.addLayout(lay_btn)

    def _creer_lien_bouton(self, texte: str, url: str, description: str) -> QPushButton:
        """Crée un bouton qui s'affiche comme un lien et ouvre une URL."""
        btn = QPushButton(texte)
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton{{border:none; background:transparent; "
            f"color:{self.COULEUR}; text-align:left; font-size:13px; padding:2px;}}"
            "QPushButton:hover{text-decoration:underline;}"
        )
        btn.setAccessibleName(description)
        btn.setAccessibleDescription(f"Lien vers : {url}")
        _url = url  # capture pour la lambda
        btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(_url)))
        return btn
