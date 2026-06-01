"""
Générateur de rapports Word (.docx).

Ce module construit le document Word du rapport comptable :
- Page de garde avec logo et informations de l'association
- Compte de résultat avec totaux et pourcentages
- Graphiques intégrés (camemberts, histogramme, courbe trésorerie)
- Tableaux alternatifs textuels pour chaque graphique (accessibilité)
- Détail des transactions par catégorie
- Section analytique par projet (si applicable)
- Alertes de cohérence (si des écarts détectés)

Dépendances : python-docx, matplotlib (via graphiques.py)
"""

from __future__ import annotations
import logging
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from ..accounting.compte_resultat import CompteResultat, LigneResultat
from ..accounting.analytique import BilanProjet
from .graphiques import GraphiquesMaker, MOIS_FR

logger = logging.getLogger(__name__)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convertit une couleur hexadécimale en tuple RGB."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _couleur_docx(hex_color: str) -> RGBColor:
    r, g, b = _hex_to_rgb(hex_color)
    return RGBColor(r, g, b)


class DocxReporter:
    """
    Génère le rapport comptable au format Word (.docx).

    Le rapport suit une structure standardisée adaptée aux associations
    loi 1901. Il peut être personnalisé avec le logo et les couleurs
    de l'association.

    Exemple::

        reporter = DocxReporter(config_asso, "config/categories.json")
        reporter.generer(compte_resultat, "rapport_2024.docx")
    """

    def __init__(self, config_association: dict, moteur_categorisation):
        """
        Initialise le générateur de rapports.

        Args:
            config_association:   Dictionnaire chargé depuis association.json.
            moteur_categorisation: MoteurCategorisation (pour les libellés).
        """
        self.config = config_association
        self.moteur = moteur_categorisation
        self.couleur_principale = config_association.get("couleur_principale", "#1a3a5c")
        self.couleur_secondaire = config_association.get("couleur_secondaire", "#e8f0f7")
        self.graphiques = GraphiquesMaker(
            couleur_principale=self.couleur_principale,
            couleur_secondaire=self.couleur_secondaire,
        )

    def generer(
        self,
        compte_resultat: CompteResultat,
        chemin_sortie: str,
        bilans_projets: Optional[list[BilanProjet]] = None,
        titre_rapport: Optional[str] = None,
    ) -> str:
        """
        Génère le rapport Word complet et le sauvegarde.

        Args:
            compte_resultat: Résultat calculé par CompteResultat.
            chemin_sortie:   Chemin du fichier .docx à créer.
            bilans_projets:  Liste des bilans analytiques par projet (optionnel).
            titre_rapport:   Titre personnalisé du rapport (optionnel).

        Returns:
            Chemin absolu du fichier généré.
        """
        doc = Document()
        self._configurer_marges(doc)

        # Titre du rapport
        if not titre_rapport:
            debut = compte_resultat.date_debut
            fin = compte_resultat.date_fin
            if debut.month == 1 and fin.month == 12 and debut.year == fin.year:
                titre_rapport = f"Rapport annuel {debut.year}"
            else:
                titre_rapport = (
                    f"Rapport du {debut.strftime('%d/%m/%Y')} "
                    f"au {fin.strftime('%d/%m/%Y')}"
                )

        # ── Sections du rapport ──────────────────────────────────────────────
        self._page_de_garde(doc, titre_rapport, compte_resultat)
        doc.add_page_break()

        self._section_infos_association(doc)
        doc.add_page_break()

        self._section_compte_resultat(doc, compte_resultat)
        doc.add_page_break()

        self._section_graphiques(doc, compte_resultat)
        doc.add_page_break()

        self._section_tresorerie(doc, compte_resultat)
        doc.add_page_break()

        self._section_detail_transactions(doc, compte_resultat)

        if bilans_projets:
            doc.add_page_break()
            self._section_analytique(doc, bilans_projets)

        if compte_resultat.alertes_coherence:
            doc.add_page_break()
            self._section_alertes(doc, compte_resultat)

        self._section_signature(doc, compte_resultat)

        # ── Sauvegarde ──────────────────────────────────────────────────────
        Path(chemin_sortie).parent.mkdir(parents=True, exist_ok=True)
        doc.save(chemin_sortie)
        self.graphiques.nettoyer()

        logger.info(f"Rapport généré : {chemin_sortie}")
        return str(Path(chemin_sortie).resolve())

    def _configurer_marges(self, doc: Document) -> None:
        """Définit les marges du document (2 cm de chaque côté)."""
        for section in doc.sections:
            section.top_margin = Cm(2)
            section.bottom_margin = Cm(2)
            section.left_margin = Cm(2.5)
            section.right_margin = Cm(2.5)

    def _page_de_garde(
        self, doc: Document, titre: str, cr: CompteResultat
    ) -> None:
        """Construit la page de garde."""
        # Logo
        logo = self.config.get("logo_chemin", "")
        if logo and Path(logo).exists():
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            run.add_picture(logo, width=Inches(2))
            doc.add_paragraph()

        # Nom de l'association
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(self.config.get("nom", ""))
        run.font.size = Pt(20)
        run.font.bold = True
        run.font.color.rgb = _couleur_docx(self.couleur_principale)

        # Sigle
        sigle = self.config.get("sigle", "")
        if sigle:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(f"({sigle})")
            run.font.size = Pt(14)
            run.font.color.rgb = _couleur_docx(self.couleur_principale)

        doc.add_paragraph()

        # Titre du rapport
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(titre)
        run.font.size = Pt(26)
        run.font.bold = True
        run.font.color.rgb = _couleur_docx(self.couleur_principale)

        doc.add_paragraph()
        doc.add_paragraph()

        # Récapitulatif
        self._ligne_info_garde(doc, "Période", (
            f"{cr.date_debut.strftime('%d %B %Y')} → {cr.date_fin.strftime('%d %B %Y')}"
        ))
        self._ligne_info_garde(doc, "Total recettes", f"{cr.total_recettes:,.2f} €")
        self._ligne_info_garde(doc, "Total dépenses", f"{cr.total_depenses:,.2f} €")

        resultat_txt = f"{cr.resultat_net:,.2f} €"
        if cr.est_excedentaire:
            resultat_txt += "  ✓ Excédent"
        else:
            resultat_txt += "  ⚠ Déficit"
        self._ligne_info_garde(doc, "Résultat net", resultat_txt)

        doc.add_paragraph()

        # Informations légales
        for champ, cle in [
            ("SIRET", "siret"), ("Code APE", "code_ape"), ("N° Waldec", "numero_waldec")
        ]:
            valeur = self.config.get(cle, "")
            if valeur:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run(f"{champ} : {valeur}")
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(100, 100, 100)

        # Date de génération
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"Document généré le {date.today().strftime('%d/%m/%Y')} — Comptasso")
        run.font.size = Pt(8)
        run.font.italic = True
        run.font.color.rgb = RGBColor(150, 150, 150)

    def _ligne_info_garde(self, doc: Document, label: str, valeur: str) -> None:
        """Ajoute une ligne label : valeur centrée sur la page de garde."""
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_label = p.add_run(f"{label} : ")
        run_label.font.bold = True
        run_label.font.size = Pt(12)
        run_valeur = p.add_run(valeur)
        run_valeur.font.size = Pt(12)

    def _titre_section(self, doc: Document, texte: str) -> None:
        """Ajoute un titre de section stylé."""
        p = doc.add_paragraph()
        run = p.add_run(texte)
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = _couleur_docx(self.couleur_principale)
        # Bordure inférieure simulée par espacement
        p.space_after = Pt(6)
        p.space_before = Pt(12)

    def _titre_sous_section(self, doc: Document, texte: str) -> None:
        """Ajoute un sous-titre de section."""
        p = doc.add_paragraph()
        run = p.add_run(texte)
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = _couleur_docx(self.couleur_principale)
        p.space_before = Pt(8)
        p.space_after = Pt(4)

    def _section_infos_association(self, doc: Document) -> None:
        """Ajoute la section informations de l'association."""
        self._titre_section(doc, "1. Informations de l'association")

        champs = [
            ("Nom", "nom"), ("Sigle", "sigle"), ("Adresse", "adresse"),
            ("Code postal", "code_postal"), ("Ville", "ville"),
            ("Email", "email"), ("Téléphone", "telephone"),
            ("Site web", "site_web"), ("SIRET", "siret"),
            ("Code APE/NAF", "code_ape"), ("N° Waldec (RNA)", "numero_waldec"),
            ("IBAN", "iban"), ("BIC", "bic"),
            ("Président(e)", "president"), ("Trésorier(ère)", "tresorier"),
        ]

        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"

        for label, cle in champs:
            valeur = self.config.get(cle, "")
            if not valeur:
                continue
            row = table.add_row()
            cell_label = row.cells[0]
            cell_valeur = row.cells[1]

            run = cell_label.paragraphs[0].add_run(label)
            run.bold = True
            run.font.color.rgb = _couleur_docx(self.couleur_principale)

            cell_valeur.paragraphs[0].add_run(str(valeur))

            # Largeurs colonnes
            cell_label.width = Cm(5)
            cell_valeur.width = Cm(10)

    def _section_compte_resultat(self, doc: Document, cr: CompteResultat) -> None:
        """Ajoute le tableau du compte de résultat."""
        self._titre_section(doc, "2. Compte de résultat")

        periode = (
            f"Période du {cr.date_debut.strftime('%d/%m/%Y')} "
            f"au {cr.date_fin.strftime('%d/%m/%Y')}"
        )
        p = doc.add_paragraph(periode)
        p.runs[0].font.italic = True

        doc.add_paragraph()

        # ── RECETTES ─────────────────────────────────────────────────────────
        self._titre_sous_section(doc, "Recettes")
        self._tableau_postes(doc, cr.lignes_recettes, cr.total_recettes, "recettes")

        doc.add_paragraph()

        # ── DÉPENSES ─────────────────────────────────────────────────────────
        self._titre_sous_section(doc, "Dépenses")
        self._tableau_postes(doc, cr.lignes_depenses, cr.total_depenses, "dépenses")

        doc.add_paragraph()

        # ── RÉSULTAT NET ─────────────────────────────────────────────────────
        table = doc.add_table(rows=1, cols=2)
        row = table.rows[0]
        cell_label = row.cells[0]
        cell_valeur = row.cells[1]

        run = cell_label.paragraphs[0].add_run("RÉSULTAT NET DE L'EXERCICE")
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = _couleur_docx(self.couleur_principale)

        signe = "+" if cr.resultat_net >= 0 else ""
        run_val = cell_valeur.paragraphs[0].add_run(f"{signe}{cr.resultat_net:,.2f} €")
        run_val.bold = True
        run_val.font.size = Pt(13)
        if cr.est_excedentaire:
            run_val.font.color.rgb = RGBColor(0, 128, 0)
        else:
            run_val.font.color.rgb = RGBColor(180, 0, 0)

        cell_valeur.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        if cr.transactions_non_categorisees:
            doc.add_paragraph()
            p = doc.add_paragraph(
                f"⚠ {len(cr.transactions_non_categorisees)} transaction(s) non catégorisée(s) "
                f"ne sont pas incluses dans ce rapport."
            )
            p.runs[0].font.color.rgb = RGBColor(180, 100, 0)
            p.runs[0].font.italic = True

    def _tableau_postes(
        self, doc: Document, lignes: list[LigneResultat], total: Decimal, type_txt: str
    ) -> None:
        """Génère le tableau d'un type de poste (recettes ou dépenses)."""
        if not lignes:
            doc.add_paragraph(f"Aucune {type_txt} enregistrée pour cette période.")
            return

        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"

        # En-tête
        entetes = ["Catégorie", "Montant (€)", "Part (%)", "Nb. opérations"]
        for i, titre in enumerate(entetes):
            cell = table.rows[0].cells[i]
            run = cell.paragraphs[0].add_run(titre)
            run.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            # Fond coloré pour l'en-tête
            self._set_cell_background(cell, self.couleur_principale.lstrip("#"))

        # Lignes de données
        for i, ligne in enumerate(lignes):
            row = table.add_row()
            row.cells[0].paragraphs[0].add_run(ligne.label)
            row.cells[1].paragraphs[0].add_run(f"{ligne.montant:,.2f} €")
            row.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            row.cells[2].paragraphs[0].add_run(f"{ligne.pourcentage:.1f} %")
            row.cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            row.cells[3].paragraphs[0].add_run(str(ligne.nb_transactions))
            row.cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

            # Alternance de fond
            if i % 2 == 0:
                bg = self.couleur_secondaire.lstrip("#")
                for cell in row.cells:
                    self._set_cell_background(cell, bg)

        # Ligne total
        row_total = table.add_row()
        run = row_total.cells[0].paragraphs[0].add_run(f"TOTAL {type_txt.upper()}")
        run.bold = True
        run_val = row_total.cells[1].paragraphs[0].add_run(f"{total:,.2f} €")
        run_val.bold = True
        row_total.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_pct = row_total.cells[2].paragraphs[0].add_run("100,0 %")
        run_pct.bold = True
        row_total.cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        bg_total = "d4e6f1"
        for cell in row_total.cells:
            self._set_cell_background(cell, bg_total)

    def _section_graphiques(self, doc: Document, cr: CompteResultat) -> None:
        """Insère les camemberts et leur tableau d'accessibilité."""
        self._titre_section(doc, "3. Visualisation graphique")

        # Camembert recettes
        if cr.lignes_recettes:
            self._titre_sous_section(doc, "Répartition des recettes")
            chemin_img, tableau_txt = self.graphiques.camembert_recettes(cr.lignes_recettes)
            if chemin_img:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run()
                run.add_picture(chemin_img, width=Inches(5.5))
            if tableau_txt:
                doc.add_paragraph()
                p = doc.add_paragraph("Données du graphique (accessibilité) :")
                p.runs[0].font.italic = True
                p.runs[0].font.size = Pt(9)
                p_data = doc.add_paragraph(tableau_txt)
                p_data.runs[0].font.size = Pt(8)
                p_data.runs[0].font.name = "Courier New"

        doc.add_paragraph()

        # Camembert dépenses
        if cr.lignes_depenses:
            self._titre_sous_section(doc, "Répartition des dépenses")
            chemin_img, tableau_txt = self.graphiques.camembert_depenses(cr.lignes_depenses)
            if chemin_img:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run()
                run.add_picture(chemin_img, width=Inches(5.5))
            if tableau_txt:
                doc.add_paragraph()
                p = doc.add_paragraph("Données du graphique (accessibilité) :")
                p.runs[0].font.italic = True
                p.runs[0].font.size = Pt(9)
                p_data = doc.add_paragraph(tableau_txt)
                p_data.runs[0].font.size = Pt(8)
                p_data.runs[0].font.name = "Courier New"

        # Histogramme mensuel
        evolution = cr.evolution_mensuelle()
        if evolution:
            doc.add_page_break()
            self._titre_sous_section(doc, "Recettes et dépenses mensuelles")
            chemin_img, tableau_txt = self.graphiques.histogramme_mensuel(evolution)
            if chemin_img:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run()
                run.add_picture(chemin_img, width=Inches(6))
            if tableau_txt:
                doc.add_paragraph()
                p_data = doc.add_paragraph(tableau_txt)
                p_data.runs[0].font.size = Pt(8)
                p_data.runs[0].font.name = "Courier New"

    def _section_tresorerie(self, doc: Document, cr: CompteResultat) -> None:
        """Insère la courbe de trésorerie."""
        self._titre_section(doc, "4. Évolution de la trésorerie")

        evolution = cr.evolution_mensuelle()
        if not evolution:
            doc.add_paragraph("Aucune donnée de trésorerie disponible.")
            return

        p = doc.add_paragraph(f"Solde initial : {cr.solde_initial:,.2f} €")
        p.runs[0].font.italic = True

        chemin_img, tableau_txt = self.graphiques.courbe_tresorerie(evolution, cr.solde_initial)
        if chemin_img:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            run.add_picture(chemin_img, width=Inches(6))
        if tableau_txt:
            doc.add_paragraph()
            p_data = doc.add_paragraph(tableau_txt)
            p_data.runs[0].font.size = Pt(8)
            p_data.runs[0].font.name = "Courier New"

        p_final = doc.add_paragraph(f"Solde estimé en fin de période : {cr.solde_final:,.2f} €")
        p_final.runs[0].font.bold = True

    def _section_detail_transactions(self, doc: Document, cr: CompteResultat) -> None:
        """Ajoute le détail des transactions par catégorie."""
        self._titre_section(doc, "5. Détail des opérations par catégorie")

        toutes_lignes = cr.lignes_recettes + cr.lignes_depenses

        for ligne in toutes_lignes:
            if not ligne.transactions:
                continue

            self._titre_sous_section(doc, f"{ligne.label} — {ligne.montant:,.2f} €")

            table = doc.add_table(rows=1, cols=3)
            table.style = "Table Grid"

            entetes = ["Date", "Libellé", "Montant (€)"]
            for i, titre in enumerate(entetes):
                cell = table.rows[0].cells[i]
                run = cell.paragraphs[0].add_run(titre)
                run.bold = True
                self._set_cell_background(cell, self.couleur_principale.lstrip("#"))
                run.font.color.rgb = RGBColor(255, 255, 255)

            for i, t in enumerate(sorted(ligne.transactions, key=lambda x: x.date)):
                row = table.add_row()
                row.cells[0].paragraphs[0].add_run(t.date.strftime("%d/%m/%Y"))
                libelle = t.libelle
                if t.memo:
                    libelle += f" ({t.memo})"
                row.cells[1].paragraphs[0].add_run(libelle)
                row.cells[2].paragraphs[0].add_run(f"{abs(t.montant):,.2f} €")
                row.cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

                if i % 2 == 0:
                    for cell in row.cells:
                        self._set_cell_background(cell, self.couleur_secondaire.lstrip("#"))

            doc.add_paragraph()

    def _section_analytique(self, doc: Document, bilans: list[BilanProjet]) -> None:
        """Ajoute la section comptabilité analytique par projet."""
        self._titre_section(doc, "6. Comptabilité analytique par projet")

        for bilan in bilans:
            self._titre_sous_section(doc, bilan.projet.nom)

            if bilan.projet.description:
                doc.add_paragraph(bilan.projet.description).runs[0].font.italic = True

            table = doc.add_table(rows=4, cols=2)
            table.style = "Table Grid"

            donnees = [
                ("Recettes", f"{bilan.recettes:,.2f} €"),
                ("Dépenses", f"{bilan.depenses:,.2f} €"),
                ("Résultat", f"{'+' if bilan.resultat >= 0 else ''}{bilan.resultat:,.2f} €"),
            ]
            if bilan.taux_realisation_budget is not None:
                donnees.append(
                    ("Réalisation budget", f"{bilan.taux_realisation_budget:.1f} %")
                )

            for i, (label, valeur) in enumerate(donnees):
                if i < len(table.rows):
                    row = table.rows[i]
                else:
                    row = table.add_row()
                row.cells[0].paragraphs[0].add_run(label).bold = True
                row.cells[1].paragraphs[0].add_run(valeur)

            doc.add_paragraph()

    def _section_alertes(self, doc: Document, cr: CompteResultat) -> None:
        """Ajoute les alertes de cohérence des soldes."""
        self._titre_section(doc, "⚠ Alertes de cohérence")

        p = doc.add_paragraph(
            "Les écarts suivants ont été détectés entre les soldes calculés "
            "et les soldes indiqués sur les relevés bancaires :"
        )
        p.runs[0].font.color.rgb = RGBColor(180, 0, 0)

        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"

        for titre_col in ["Date relevé", "Solde calculé", "Solde relevé", "Écart"]:
            cell = table.rows[0].cells[["Date relevé", "Solde calculé", "Solde relevé", "Écart"].index(titre_col)]
            run = cell.paragraphs[0].add_run(titre_col)
            run.bold = True

        for alerte in cr.alertes_coherence:
            row = table.add_row()
            row.cells[0].paragraphs[0].add_run(alerte.date_releve.strftime("%d/%m/%Y"))
            row.cells[1].paragraphs[0].add_run(f"{alerte.solde_calcule:,.2f} €")
            row.cells[2].paragraphs[0].add_run(f"{alerte.solde_releve:,.2f} €")
            ecart_txt = f"{alerte.ecart:,.2f} €"
            run_ecart = row.cells[3].paragraphs[0].add_run(ecart_txt)
            run_ecart.font.color.rgb = RGBColor(180, 0, 0)
            run_ecart.bold = True

    def _section_signature(self, doc: Document, cr: CompteResultat) -> None:
        """Ajoute la section signature du trésorier."""
        doc.add_paragraph()
        p = doc.add_paragraph(
            f"Fait à {self.config.get('ville', '…')}, "
            f"le {date.today().strftime('%d/%m/%Y')}"
        )
        doc.add_paragraph()
        doc.add_paragraph()

        tresorier = self.config.get("tresorier", "Le(la) Trésorier(ère)")
        p_sig = doc.add_paragraph(f"Signature du trésorier : {tresorier}")
        p_sig.runs[0].font.bold = True

        doc.add_paragraph()
        doc.add_paragraph("_" * 40)
        doc.add_paragraph(tresorier)

    @staticmethod
    def _set_cell_background(cell, hex_color: str) -> None:
        """Définit la couleur de fond d'une cellule de tableau Word."""
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), hex_color)
        tcPr.append(shd)

    def convertir_en_pdf(self, chemin_docx: str) -> Optional[str]:
        """
        Convertit le fichier Word en PDF via LibreOffice (silencieux).

        LibreOffice doit être installé sur le système.
        Sur Windows, tente également la conversion via comtypes (Word COM).

        Args:
            chemin_docx: Chemin vers le fichier .docx source.

        Returns:
            Chemin vers le fichier PDF généré, ou None en cas d'échec.
        """
        chemin_docx = Path(chemin_docx)
        chemin_pdf = chemin_docx.with_suffix(".pdf")

        # Tentative 1 : conversion via Word (Windows COM)
        if sys.platform == "win32":
            try:
                return self._convertir_via_word_com(chemin_docx, chemin_pdf)
            except Exception as e:
                logger.warning(f"Conversion Word COM échouée : {e}")

        # Tentative 2 : conversion via LibreOffice
        try:
            return self._convertir_via_libreoffice(chemin_docx, chemin_pdf)
        except Exception as e:
            logger.error(f"Conversion LibreOffice échouée : {e}")
            return None

    def _convertir_via_word_com(self, chemin_docx: Path, chemin_pdf: Path) -> str:
        """Conversion Word → PDF via l'API COM de Microsoft Word (Windows uniquement)."""
        import comtypes.client
        word = comtypes.client.CreateObject("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(str(chemin_docx.resolve()))
            doc.SaveAs(str(chemin_pdf.resolve()), FileFormat=17)  # 17 = PDF
            doc.Close()
        finally:
            word.Quit()
        logger.info(f"PDF généré via Word COM : {chemin_pdf}")
        return str(chemin_pdf)

    def _convertir_via_libreoffice(self, chemin_docx: Path, chemin_pdf: Path) -> str:
        """Conversion Word → PDF via LibreOffice en ligne de commande."""
        commandes = ["libreoffice", "soffice"]
        for cmd in commandes:
            try:
                subprocess.run(
                    [cmd, "--headless", "--convert-to", "pdf", "--outdir",
                     str(chemin_docx.parent), str(chemin_docx)],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
                logger.info(f"PDF généré via LibreOffice : {chemin_pdf}")
                return str(chemin_pdf)
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        raise RuntimeError("LibreOffice introuvable. Installez LibreOffice pour la conversion PDF.")
