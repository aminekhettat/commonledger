"""
Générateur de rapports Word (.docx) — CommonLedger v1.1

Améliorations de mise en page :
  - Page de garde professionnelle avec bandeau couleur et logo
  - Sommaire automatique (TOC Word) en page 2
  - En-tête sur toutes les pages (sauf p.1) : logo + nom asso + numéro de page
  - Numérotation « Page X sur Y » à partir de la page 2
  - Sections structurées avec titres hiérarchiques Word (Titre 1 / Titre 2)
  - Graphiques agrandis avec légendes complètes
  - Tableaux accessibles sous chaque graphique
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

from ..accounting.analytique import BilanProjet
from ..accounting.compte_resultat import CompteResultat
from .graphiques import GraphiquesMaker

logger = logging.getLogger(__name__)


# ── Dates en français ────────────────────────────────────────────────────────

_MOIS_LONGS = [
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


def _date_fr(d) -> str:
    """Formate une date en français : '31 janvier 2024'."""
    return f"{d.day} {_MOIS_LONGS[d.month]} {d.year}"


# ── Helpers couleurs ──────────────────────────────────────────────────────────


def _rgb(hex_color: str) -> RGBColor:
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _hex_fill(hex_color: str) -> str:
    return hex_color.lstrip("#")


# ── Helpers OxmlElement ───────────────────────────────────────────────────────


def _cell_background(cell, hex_color: str) -> None:
    """Définit la couleur de fond d'une cellule."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color.lstrip("#"))
    tcPr.append(shd)


def _add_field(run, field_code: str) -> None:
    """Insère un champ Word (PAGE, NUMPAGES, TOC…) dans un run."""
    fldChar_begin = OxmlElement("w:fldChar")
    fldChar_begin.set(qn("w:fldCharType"), "begin")
    instrText = OxmlElement("w:instrText")
    instrText.set(qn("xml:space"), "preserve")
    instrText.text = field_code
    fldChar_sep = OxmlElement("w:fldChar")
    fldChar_sep.set(qn("w:fldCharType"), "separate")
    fldChar_end = OxmlElement("w:fldChar")
    fldChar_end.set(qn("w:fldCharType"), "end")
    run._r.extend([fldChar_begin, instrText, fldChar_sep, fldChar_end])


def _add_toc_field(doc: Document) -> None:
    """Insère le champ TOC de Word (se met à jour à l'ouverture du document)."""
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = para.add_run()
    # Champ TOC : génère un sommaire des titres niveaux 1-3 avec hyperliens
    fldChar_begin = OxmlElement("w:fldChar")
    fldChar_begin.set(qn("w:fldCharType"), "begin")
    instrText = OxmlElement("w:instrText")
    instrText.set(qn("xml:space"), "preserve")
    instrText.text = r'TOC \o "1-3" \h \z \u'
    fldChar_end = OxmlElement("w:fldChar")
    fldChar_end.set(qn("w:fldCharType"), "end")
    run._r.extend([fldChar_begin, instrText, fldChar_end])


def _add_page_number_field(para) -> None:
    """Ajoute 'Page X sur Y' dans un paragraphe de pied/en-tête."""
    run_pre = para.add_run("Page ")
    run_pre.font.size = Pt(9)

    run_page = para.add_run()
    _add_field(run_page, "PAGE")
    run_page.font.size = Pt(9)

    run_sep = para.add_run(" sur ")
    run_sep.font.size = Pt(9)

    run_total = para.add_run()
    _add_field(run_total, "NUMPAGES")
    run_total.font.size = Pt(9)


# ── Classe principale ─────────────────────────────────────────────────────────


class DocxReporter:
    """
    Génère le rapport comptable au format Word (.docx).

    Structure du document :
      1. Page de garde  (section sans en-tête)
      2. Sommaire       (TOC automatique Word)
      3. Informations de l'association
      4. Compte de résultat
      5. Visualisation graphique
      6. Évolution de la trésorerie
      7. Détail des opérations
      [8. Comptabilité analytique par projet]
      [9. Alertes de cohérence]
      10. Signature

    En-tête (pages 2+) :
      Logo | Nom association — Rapport AAAA | Page X sur Y
    """

    def __init__(self, config_association: dict, moteur_categorisation):
        self.config = config_association
        self.moteur = moteur_categorisation
        self.cp = config_association.get("couleur_principale", "#1a3a5c")
        self.cs = config_association.get("couleur_secondaire", "#e8f0f7")
        self.graphiques = GraphiquesMaker(
            couleur_principale=self.cp,
            couleur_secondaire=self.cs,
            dpi=150,
        )

    # ── Point d'entrée ────────────────────────────────────────────────────────

    def generer(
        self,
        compte_resultat: CompteResultat,
        chemin_sortie: str,
        bilans_projets: list[BilanProjet] | None = None,
        titre_rapport: str | None = None,
        bilan=None,  # objet Bilan (core.accounting.bilan.Bilan)
    ) -> str:
        cr = compte_resultat
        if not titre_rapport:
            d, f = cr.date_debut, cr.date_fin
            if d.month == 1 and f.month == 12 and d.year == f.year:
                titre_rapport = f"Rapport annuel {d.year}"
            else:
                titre_rapport = f"Rapport du {d.strftime('%d/%m/%Y')} au {f.strftime('%d/%m/%Y')}"

        doc = Document()
        self._definir_styles(doc)

        # Stocker le bilan pour utilisation dans les sections
        self._bilan_data = bilan

        # ── Section 1 : Page de garde (première page différente) ──────────────
        section1 = doc.sections[0]
        section1.different_first_page_header_footer = True
        section1.top_margin = Cm(0)
        section1.bottom_margin = Cm(2)
        section1.left_margin = Cm(2.5)
        section1.right_margin = Cm(2.5)
        self._page_de_garde(doc, titre_rapport, cr)

        # ── Section 2 : Corps du document (en-tête actif) ─────────────────────
        doc.add_section(WD_SECTION.NEW_PAGE)
        section2 = doc.sections[-1]
        section2.top_margin = Cm(3.5)  # Espace pour l'en-tête
        section2.bottom_margin = Cm(2.5)
        section2.left_margin = Cm(2.5)
        section2.right_margin = Cm(2.5)

        # Configurer l'en-tête de la section 2
        self._configurer_entete(section2, titre_rapport)

        # ── Sommaire ──────────────────────────────────────────────────────────
        self._sommaire(doc)

        # ── Sections de contenu ───────────────────────────────────────────────
        self._section_infos(doc)
        doc.add_page_break()

        self._section_compte_resultat(doc, cr)
        doc.add_page_break()

        self._section_graphiques(doc, cr)
        doc.add_page_break()

        self._section_tresorerie(doc, cr)
        doc.add_page_break()

        self._section_detail(doc, cr)

        # Bilan si les données sont disponibles (passé via kwargs)
        if hasattr(self, "_bilan_data") and self._bilan_data:
            doc.add_page_break()
            self._section_bilan(doc, self._bilan_data)

        if bilans_projets:
            doc.add_page_break()
            self._section_analytique(doc, bilans_projets)

        if cr.alertes_coherence:
            doc.add_page_break()
            self._section_alertes(doc, cr)

        self._section_signature(doc, cr)

        # ── Sauvegarde ────────────────────────────────────────────────────────
        Path(chemin_sortie).parent.mkdir(parents=True, exist_ok=True)
        doc.save(chemin_sortie)
        self.graphiques.nettoyer()

        logger.info(f"Rapport généré : {chemin_sortie}")
        return str(Path(chemin_sortie).resolve())

    # ── Styles globaux ────────────────────────────────────────────────────────

    def _definir_styles(self, doc: Document) -> None:
        """Configure les styles de titre Word pour le TOC."""

        styles = doc.styles
        # Titre 1 — sections principales
        try:
            s1 = styles["Heading 1"]
            s1.font.size = Pt(15)
            s1.font.bold = True
            s1.font.color.rgb = _rgb(self.cp)
            s1.paragraph_format.space_before = Pt(14)
            s1.paragraph_format.space_after = Pt(6)
        except KeyError:
            pass
        # Titre 2 — sous-sections
        try:
            s2 = styles["Heading 2"]
            s2.font.size = Pt(12)
            s2.font.bold = True
            s2.font.color.rgb = _rgb(self.cp)
            s2.paragraph_format.space_before = Pt(10)
            s2.paragraph_format.space_after = Pt(4)
        except KeyError:
            pass

    # ── En-tête ───────────────────────────────────────────────────────────────

    def _configurer_entete(self, section, titre_rapport: str) -> None:
        """
        Configure l'en-tête et le pied de page pour les pages courantes (2+).

        En-tête : logo à gauche + nom de l'association au centre
        Pied de page : numérotation 'Page X sur Y' en bas à gauche
        """
        # ── En-tête ───────────────────────────────────────────────────────────
        header = section.header
        header.is_linked_to_previous = False

        for para in header.paragraphs:
            para.clear()

        # Ligne 1 : logo (gauche) + nom asso (centre)
        p_h = header.paragraphs[0]
        p_h.paragraph_format.space_before = Pt(0)
        p_h.paragraph_format.space_after = Pt(2)

        logo = self.config.get("logo_chemin", "")
        if logo and Path(logo).exists():
            run_logo = p_h.add_run()
            run_logo.add_picture(logo, height=Cm(1.1))
            p_h.add_run("    ")  # espace horizontal

        run_nom = p_h.add_run(self.config.get("nom", ""))
        run_nom.font.bold = True
        run_nom.font.size = Pt(9)
        run_nom.font.color.rgb = _rgb(self.cp)

        run_sep_h = p_h.add_run(f"  —  {titre_rapport}")
        run_sep_h.font.size = Pt(8)
        run_sep_h.font.color.rgb = RGBColor(100, 100, 100)

        # Ligne séparatrice colorée sous l'en-tête
        p_sep = header.add_paragraph()
        p_sep.paragraph_format.space_before = Pt(2)
        p_sep.paragraph_format.space_after = Pt(0)
        pPr = p_sep._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "8")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), _hex_fill(self.cp))
        pBdr.append(bottom)
        pPr.append(pBdr)

        # ── Pied de page : numérotation bas-gauche ────────────────────────────
        footer = section.footer
        footer.is_linked_to_previous = False

        for para in footer.paragraphs:
            para.clear()

        # Ligne séparatrice au-dessus du pied
        p_fsep = footer.paragraphs[0]
        p_fsep.paragraph_format.space_before = Pt(0)
        p_fsep.paragraph_format.space_after = Pt(3)
        pPr2 = p_fsep._p.get_or_add_pPr()
        pBdr2 = OxmlElement("w:pBdr")
        top_b = OxmlElement("w:top")
        top_b.set(qn("w:val"), "single")
        top_b.set(qn("w:sz"), "4")
        top_b.set(qn("w:space"), "1")
        top_b.set(qn("w:color"), _hex_fill(self.cp))
        pBdr2.append(top_b)
        pPr2.append(pBdr2)

        # Numérotation bas-gauche
        p_num = footer.add_paragraph()
        p_num.alignment = WD_ALIGN_PARAGRAPH.LEFT
        _add_page_number_field(p_num)

        # Nom asso en bas-droite (même ligne via tabulation)
        # Utiliser une tabulation droite
        nom_court = self.config.get("sigle") or self.config.get("nom", "")[:20]
        run_asso = p_num.add_run(f"\t{nom_court}")
        run_asso.font.size = Pt(8)
        run_asso.font.color.rgb = RGBColor(150, 150, 150)

        # Tab stop droite à 15,5 cm
        from docx.oxml import OxmlElement as oxe

        pPr_num = p_num._p.get_or_add_pPr()
        tabs = oxe("w:tabs")
        tab = oxe("w:tab")
        tab.set(qn("w:val"), "right")
        tab.set(qn("w:pos"), "8800")
        tabs.append(tab)
        pPr_num.append(tabs)

    # ── Page de garde ─────────────────────────────────────────────────────────

    def _page_de_garde(self, doc: Document, titre: str, cr: CompteResultat) -> None:
        """Page de garde professionnelle avec bandeau couleur."""

        # Bandeau supérieur coloré
        table_top = doc.add_table(rows=1, cols=1)
        table_top.style = "Table Grid"
        cell_top = table_top.rows[0].cells[0]
        _cell_background(cell_top, self.cp)

        # Logo centré dans le bandeau — dans un paragraphe simple (pas de tableau imbriqué)
        p_logo = cell_top.paragraphs[0]
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_logo.paragraph_format.space_before = Pt(20)
        p_logo.paragraph_format.space_after = Pt(20)
        logo = self.config.get("logo_chemin", "")
        if logo and Path(logo).exists():
            p_logo.add_run().add_picture(logo, height=Cm(3.5))
        else:
            run_s = p_logo.add_run(self.config.get("sigle", "ACM"))
            run_s.font.size = Pt(36)
            run_s.font.bold = True
            run_s.font.color.rgb = RGBColor(255, 255, 255)

        doc.add_paragraph()  # espace

        # Type de structure + Nom de l'association
        type_struct = self.config.get("type_structure", "")
        if type_struct:
            p_type = doc.add_paragraph()
            p_type.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_type = p_type.add_run(type_struct.upper())
            run_type.font.size = Pt(10)
            run_type.font.color.rgb = RGBColor(200, 160, 50)
            run_type.font.bold = True
            run_type.font.color.rgb = _rgb(self.cs)

        p_nom = doc.add_paragraph()
        p_nom.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_nom = p_nom.add_run(self.config.get("nom", ""))
        run_nom.font.size = Pt(22)
        run_nom.font.bold = True
        run_nom.font.color.rgb = _rgb(self.cp)

        # Titre du rapport
        doc.add_paragraph()
        p_titre = doc.add_paragraph()
        p_titre.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Bandeau titre avec fond secondaire
        table_titre = doc.add_table(rows=1, cols=1)
        table_titre.style = "Table Grid"
        cell_titre = table_titre.rows[0].cells[0]
        _cell_background(cell_titre, self.cs)
        p_t = cell_titre.paragraphs[0]
        p_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_t.paragraph_format.space_before = Pt(14)
        p_t.paragraph_format.space_after = Pt(14)
        run_t = p_t.add_run(titre)
        run_t.font.size = Pt(24)
        run_t.font.bold = True
        run_t.font.color.rgb = _rgb(self.cp)

        doc.add_paragraph()

        # Récapitulatif financier (tableau centré)
        table_kpi = doc.add_table(rows=3, cols=2)
        table_kpi.style = "Table Grid"
        table_kpi.alignment = (
            WD_TABLE_ALIGNMENT.CENTER
            if hasattr(__import__("docx").enum.table, "WD_TABLE_ALIGNMENT")
            else 1
        )

        kpis = [
            (
                "Période analysée",
                f"{cr.date_debut.strftime('%d/%m/%Y')} → {cr.date_fin.strftime('%d/%m/%Y')}",
            ),
            ("Total recettes", f"{cr.total_recettes:,.2f} €"),
            ("Total dépenses", f"{cr.total_depenses:,.2f} €"),
        ]
        # Supprimer la 3e ligne si on en a que 3 KPIs
        for i, (label, valeur) in enumerate(kpis):
            row = table_kpi.rows[i]
            cell_l = row.cells[0]
            cell_v = row.cells[1]
            _cell_background(cell_l, self.cp)
            run_l = cell_l.paragraphs[0].add_run(label)
            run_l.font.bold = True
            run_l.font.color.rgb = RGBColor(255, 255, 255)
            run_l.font.size = Pt(11)
            run_v = cell_v.paragraphs[0].add_run(valeur)
            run_v.font.size = Pt(11)
            run_v.font.bold = True
            cell_v.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Résultat avec couleur
        row_res = table_kpi.add_row()
        _cell_background(row_res.cells[0], self.cp)
        run_res_l = row_res.cells[0].paragraphs[0].add_run("Résultat net")
        run_res_l.font.bold = True
        run_res_l.font.color.rgb = RGBColor(255, 255, 255)
        run_res_l.font.size = Pt(12)

        signe = "+" if cr.est_excedentaire else ""
        run_res_v = (
            row_res.cells[1]
            .paragraphs[0]
            .add_run(
                f"{signe}{cr.resultat_net:,.2f} €  "
                + ("✓ Excédent" if cr.est_excedentaire else "⚠ Déficit")
            )
        )
        run_res_v.font.size = Pt(12)
        run_res_v.font.bold = True
        run_res_v.font.color.rgb = (
            RGBColor(0, 128, 0) if cr.est_excedentaire else RGBColor(180, 0, 0)
        )
        row_res.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        doc.add_paragraph()

        # Informations légales
        p_legal = doc.add_paragraph()
        p_legal.alignment = WD_ALIGN_PARAGRAPH.CENTER
        infos_legales = []
        for label, cle in [
            ("SIRET", "siret"),
            ("APE", "code_ape"),
            ("Waldec", "numero_waldec"),
            ("Site", "site_web"),
        ]:
            val = self.config.get(cle, "")
            if val:
                infos_legales.append(f"{label} : {val}")
        run_legal = p_legal.add_run("  |  ".join(infos_legales))
        run_legal.font.size = Pt(8)
        run_legal.font.color.rgb = RGBColor(100, 100, 100)

        # Pied de page de garde
        doc.add_paragraph()
        p_gen = doc.add_paragraph()
        p_gen.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_gen = p_gen.add_run(f"Document généré le {_date_fr(date.today())} — CommonLedger")
        run_gen.font.size = Pt(8)
        run_gen.font.italic = True
        run_gen.font.color.rgb = RGBColor(150, 150, 150)

    # ── Sommaire ──────────────────────────────────────────────────────────────

    def _sommaire(self, doc: Document) -> None:
        """Insère le sommaire (TOC Word automatique)."""
        h = doc.add_heading("Sommaire", level=1)
        h.style = doc.styles["Heading 1"]

        p_note = doc.add_paragraph(
            "Ce sommaire se génère automatiquement à l'ouverture du document. "
            "Si les numéros de page n'apparaissent pas, appuyez sur Ctrl+A puis F9 "
            "pour mettre à jour tous les champs."
        )
        p_note.runs[0].font.size = Pt(8)
        p_note.runs[0].font.italic = True
        p_note.runs[0].font.color.rgb = RGBColor(130, 130, 130)

        _add_toc_field(doc)
        doc.add_page_break()

    # ── Section 1 : Informations ──────────────────────────────────────────────

    def _section_infos(self, doc: Document) -> None:
        doc.add_heading("1. Informations de l'association", level=1)

        champs = [
            ("Type de structure", "type_structure"),
            ("Nom complet", "nom"),
            ("Sigle", "sigle"),
            ("Adresse", "adresse"),
            ("Code postal", "code_postal"),
            ("Ville", "ville"),
            ("Email", "email"),
            ("Téléphone", "telephone"),
            ("Site web", "site_web"),
            ("SIRET", "siret"),
            ("Code APE/NAF", "code_ape"),
            ("N° Waldec (RNA)", "numero_waldec"),
            ("Banque", "banque"),
            ("IBAN", "iban"),
            ("BIC", "bic"),
            ("Président(e)", "president"),
            ("Trésorier(ère)", "tresorier"),
        ]

        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        for label, cle in champs:
            valeur = self.config.get(cle, "")
            if not valeur:
                continue
            row = table.add_row()
            _cell_background(row.cells[0], self.cs)
            run_l = row.cells[0].paragraphs[0].add_run(label)
            run_l.font.bold = True
            run_l.font.size = Pt(10)
            run_l.font.color.rgb = _rgb(self.cp)
            row.cells[1].paragraphs[0].add_run(str(valeur)).font.size = Pt(10)
            row.cells[0].width = Cm(5)
            row.cells[1].width = Cm(10)

    # ── Section 2 : Compte de résultat ───────────────────────────────────────

    def _section_compte_resultat(self, doc: Document, cr: CompteResultat) -> None:
        doc.add_heading("2. Compte de résultat", level=1)

        p_periode = doc.add_paragraph(
            f"Période : {_date_fr(cr.date_debut)} au {_date_fr(cr.date_fin)}"
        )
        p_periode.runs[0].font.italic = True
        p_periode.runs[0].font.size = Pt(10)

        # Recettes
        doc.add_heading("Recettes", level=2)
        self._tableau_postes(doc, cr.lignes_recettes, cr.total_recettes, "recettes")
        doc.add_paragraph()

        # Dépenses
        doc.add_heading("Dépenses", level=2)
        self._tableau_postes(doc, cr.lignes_depenses, cr.total_depenses, "dépenses")
        doc.add_paragraph()

        # Résultat net
        table_res = doc.add_table(rows=1, cols=2)
        table_res.style = "Table Grid"
        _cell_background(table_res.rows[0].cells[0], self.cp)
        run_l = table_res.rows[0].cells[0].paragraphs[0].add_run("RÉSULTAT NET DE L'EXERCICE")
        run_l.font.bold = True
        run_l.font.size = Pt(13)
        run_l.font.color.rgb = RGBColor(255, 255, 255)

        signe = "+" if cr.est_excedentaire else ""
        run_v = table_res.rows[0].cells[1].paragraphs[0].add_run(f"{signe}{cr.resultat_net:,.2f} €")
        run_v.font.bold = True
        run_v.font.size = Pt(13)
        run_v.font.color.rgb = RGBColor(0, 128, 0) if cr.est_excedentaire else RGBColor(180, 0, 0)
        table_res.rows[0].cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        if cr.transactions_non_categorisees:
            p_warn = doc.add_paragraph(
                f"⚠ {len(cr.transactions_non_categorisees)} transaction(s) "
                f"non catégorisée(s) exclue(s) de ce rapport."
            )
            p_warn.runs[0].font.color.rgb = RGBColor(180, 100, 0)
            p_warn.runs[0].font.size = Pt(9)

    def _tableau_postes(self, doc, lignes, total, type_txt: str) -> None:
        if not lignes:
            doc.add_paragraph(f"Aucune {type_txt} pour cette période.")
            return

        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"

        entetes = ["Catégorie", "Montant (€)", "Part (%)", "Nb. opérations"]
        for i, titre in enumerate(entetes):
            cell = table.rows[0].cells[i]
            _cell_background(cell, self.cp)
            run = cell.paragraphs[0].add_run(titre)
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(10)

        for idx, ligne in enumerate(lignes):
            row = table.add_row()
            if idx % 2 == 0:
                for cell in row.cells:
                    _cell_background(cell, self.cs)
            row.cells[0].paragraphs[0].add_run(ligne.label).font.size = Pt(10)
            r1 = row.cells[1].paragraphs[0].add_run(f"{float(ligne.montant):,.2f} €")
            r1.font.size = Pt(10)
            row.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            r2 = row.cells[2].paragraphs[0].add_run(f"{ligne.pourcentage:.1f} %")
            r2.font.size = Pt(10)
            row.cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            r3 = row.cells[3].paragraphs[0].add_run(str(ligne.nb_transactions))
            r3.font.size = Pt(10)
            row.cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Ligne total
        row_tot = table.add_row()
        _cell_background(row_tot.cells[0], "#d4e6f1")
        r_tl = row_tot.cells[0].paragraphs[0].add_run(f"TOTAL {type_txt.upper()}")
        r_tl.font.bold = True
        r_tl.font.size = Pt(11)
        r_tv = row_tot.cells[1].paragraphs[0].add_run(f"{float(total):,.2f} €")
        r_tv.font.bold = True
        r_tv.font.size = Pt(11)
        row_tot.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        row_tot.cells[2].paragraphs[0].add_run("100,0 %").font.bold = True
        for c in row_tot.cells:
            _cell_background(c, "#d4e6f1")

    # ── Section 3 : Graphiques ────────────────────────────────────────────────

    def _section_graphiques(self, doc: Document, cr: CompteResultat) -> None:
        doc.add_heading("3. Visualisation graphique", level=1)

        # Camembert recettes
        if cr.lignes_recettes:
            doc.add_heading("Répartition des recettes", level=2)
            img, tableau = self.graphiques.camembert_recettes(cr.lignes_recettes)
            self._inserer_graphique(doc, img, tableau)

        # Camembert dépenses
        if cr.lignes_depenses:
            doc.add_heading("Répartition des dépenses", level=2)
            img, tableau = self.graphiques.camembert_depenses(cr.lignes_depenses)
            self._inserer_graphique(doc, img, tableau)

        # Histogramme mensuel
        evolution = cr.evolution_mensuelle()
        if evolution:
            doc.add_page_break()
            doc.add_heading("Recettes et dépenses mensuelles", level=2)
            img, tableau = self.graphiques.histogramme_mensuel(evolution)
            self._inserer_graphique(doc, img, tableau)

    def _inserer_graphique(self, doc: Document, chemin_img: str, tableau: str) -> None:
        """Insère une image de graphique et son tableau d'accessibilité."""
        if chemin_img and Path(chemin_img).exists():
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(chemin_img, width=Inches(6.2))

        if tableau:
            doc.add_paragraph()
            p_acc = doc.add_paragraph("Données du graphique (accessibilité) :")
            p_acc.runs[0].font.size = Pt(8)
            p_acc.runs[0].font.italic = True
            p_acc.runs[0].font.color.rgb = RGBColor(100, 100, 100)
            p_data = doc.add_paragraph(tableau)
            p_data.runs[0].font.name = "Courier New"
            p_data.runs[0].font.size = Pt(8)

        doc.add_paragraph()

    # ── Section 4 : Trésorerie ────────────────────────────────────────────────

    def _section_tresorerie(self, doc: Document, cr: CompteResultat) -> None:
        doc.add_heading("4. Évolution de la trésorerie", level=1)

        p_init = doc.add_paragraph(f"Solde initial : {float(cr.solde_initial):,.2f} €")
        p_init.runs[0].font.italic = True
        p_init.runs[0].font.size = Pt(10)

        evolution = cr.evolution_mensuelle()
        if evolution:
            img, tableau = self.graphiques.courbe_tresorerie(evolution, cr.solde_initial)
            self._inserer_graphique(doc, img, tableau)

        p_final = doc.add_paragraph(
            f"Solde estimé en fin de période : {float(cr.solde_final):,.2f} €"
        )
        p_final.runs[0].font.bold = True
        p_final.runs[0].font.size = Pt(11)

    # ── Section 5 : Détail ────────────────────────────────────────────────────

    def _section_detail(self, doc: Document, cr: CompteResultat) -> None:
        doc.add_heading("5. Détail des opérations par catégorie", level=1)

        toutes = cr.lignes_recettes + cr.lignes_depenses
        for ligne in toutes:
            if not ligne.transactions:
                continue
            doc.add_heading(f"{ligne.label} — {float(ligne.montant):,.2f} €", level=2)
            table = doc.add_table(rows=1, cols=3)
            table.style = "Table Grid"
            for j, titre in enumerate(["Date", "Libellé", "Montant (€)"]):
                cell = table.rows[0].cells[j]
                _cell_background(cell, self.cp)
                run = cell.paragraphs[0].add_run(titre)
                run.font.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.size = Pt(10)

            for idx, t in enumerate(sorted(ligne.transactions, key=lambda x: x.date)):
                row = table.add_row()
                if idx % 2 == 0:
                    for c in row.cells:
                        _cell_background(c, self.cs)
                row.cells[0].paragraphs[0].add_run(t.date.strftime("%d/%m/%Y")).font.size = Pt(9)
                libelle = t.libelle[:80] + ("…" if len(t.libelle) > 80 else "")
                if t.memo:
                    libelle += f" ({t.memo})"
                row.cells[1].paragraphs[0].add_run(libelle).font.size = Pt(9)
                row.cells[2].paragraphs[0].add_run(
                    f"{abs(float(t.montant)):,.2f} €"
                ).font.size = Pt(9)
                row.cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            doc.add_paragraph()

    # ── Section Bilan ─────────────────────────────────────────────────────────

    def _section_bilan(self, doc: Document, bilan) -> None:
        """
        Tableau du bilan comptable simplifié.

        Conforme aux exigences du Plan Comptable des Associations (ANC 2018-06)
        pour la comptabilité simplifiée (structures de moins de 3 M€ de produits).
        """

        doc.add_heading("6. Bilan comptable simplifié", level=1)

        type_struct = self.config.get("type_structure", "Association loi 1901")
        p_info = doc.add_paragraph(f"{type_struct} — Bilan au {_date_fr(bilan.date_cloture)}")
        p_info.runs[0].font.italic = True
        p_info.runs[0].font.size = Pt(10)
        doc.add_paragraph()

        # Tableau à deux colonnes : Actif | Passif
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"

        # En-têtes
        hdrs = ["ACTIF", "Montant (€)", "PASSIF", "Montant (€)"]
        for i, h in enumerate(hdrs):
            cell = table.rows[0].cells[i]
            _cell_background(cell, self.cp)
            run = cell.paragraphs[0].add_run(h)
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(10)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        lignes_actif = bilan.lignes_actif()
        lignes_passif = bilan.lignes_passif()
        nb_rows = max(len(lignes_actif), len(lignes_passif))

        def _fmt(d) -> str:
            return f"{float(d):,.2f} €" if d is not None else ""

        for idx in range(nb_rows):
            row = table.add_row()

            # Fond alterné
            if idx % 2 == 0:
                for c in row.cells:
                    _cell_background(c, self.cs)

            # Colonne actif
            if idx < len(lignes_actif):
                la = lignes_actif[idx]
                run_a = row.cells[0].paragraphs[0].add_run(la.label)
                run_a.font.size = Pt(10)
                run_a.font.bold = la.gras
                if la.gras:
                    _cell_background(row.cells[0], "#d4e6f1")
                    _cell_background(row.cells[1], "#d4e6f1")
                run_av = row.cells[1].paragraphs[0].add_run(_fmt(la.montant))
                run_av.font.size = Pt(10)
                run_av.font.bold = la.gras
                row.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

            # Colonne passif
            if idx < len(lignes_passif):
                lp = lignes_passif[idx]
                run_p = row.cells[2].paragraphs[0].add_run(lp.label)
                run_p.font.size = Pt(10)
                run_p.font.bold = lp.gras
                if lp.gras:
                    _cell_background(row.cells[2], "#d4e6f1")
                    _cell_background(row.cells[3], "#d4e6f1")
                run_pv = row.cells[3].paragraphs[0].add_run(_fmt(lp.montant))
                run_pv.font.size = Pt(10)
                run_pv.font.bold = lp.gras
                row.cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Vérification d'équilibre
        doc.add_paragraph()
        if bilan.est_equilibre:
            p_eq = doc.add_paragraph("✓ Bilan équilibré — Total Actif = Total Passif")
            p_eq.runs[0].font.color.rgb = RGBColor(0, 128, 0)
            p_eq.runs[0].font.size = Pt(9)
        else:
            p_eq = doc.add_paragraph(
                f"⚠ Écart de {float(bilan.ecart_equilibre):+.2f} € — vérifiez les données saisies."
            )
            p_eq.runs[0].font.color.rgb = RGBColor(180, 0, 0)
            p_eq.runs[0].font.size = Pt(9)

        doc.add_paragraph()
        p_note = doc.add_paragraph(
            "Note : Bilan établi conformément au Plan Comptable des Associations "
            f"(règlement ANC 2018-06), comptabilité simplifiée. "
            f"Dotation aux amortissements de l'exercice : "
            f"{float(bilan.immobilisations_nettes) if hasattr(bilan, 'immobilisations_nettes') else 0:.2f} €."
        )
        p_note.runs[0].font.size = Pt(8)
        p_note.runs[0].font.italic = True
        p_note.runs[0].font.color.rgb = RGBColor(100, 100, 100)

    # ── Section 6 : Analytique ────────────────────────────────────────────────

    def _section_analytique(self, doc: Document, bilans: list) -> None:
        doc.add_heading("6. Comptabilité analytique par projet", level=1)
        for bilan in bilans:
            doc.add_heading(bilan.projet.nom, level=2)
            if bilan.projet.description:
                p = doc.add_paragraph(bilan.projet.description)
                p.runs[0].font.italic = True
            table = doc.add_table(rows=0, cols=2)
            table.style = "Table Grid"
            for label, valeur in [
                ("Recettes", f"{float(bilan.recettes):,.2f} €"),
                ("Dépenses", f"{float(bilan.depenses):,.2f} €"),
                ("Résultat", f"{'+' if bilan.resultat >= 0 else ''}{float(bilan.resultat):,.2f} €"),
            ]:
                row = table.add_row()
                row.cells[0].paragraphs[0].add_run(label).font.bold = True
                row.cells[1].paragraphs[0].add_run(valeur)
            doc.add_paragraph()

    # ── Section 7 : Alertes ───────────────────────────────────────────────────

    def _section_alertes(self, doc: Document, cr: CompteResultat) -> None:
        doc.add_heading("⚠ Alertes de cohérence des soldes", level=1)
        p = doc.add_paragraph(
            "Écarts détectés entre les soldes calculés et les soldes des relevés :"
        )
        p.runs[0].font.color.rgb = RGBColor(180, 0, 0)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        for j, t in enumerate(["Date relevé", "Solde calculé", "Solde relevé", "Écart"]):
            run = table.rows[0].cells[j].paragraphs[0].add_run(t)
            run.font.bold = True
        for alerte in cr.alertes_coherence:
            row = table.add_row()
            row.cells[0].paragraphs[0].add_run(alerte.date_releve.strftime("%d/%m/%Y"))
            row.cells[1].paragraphs[0].add_run(f"{float(alerte.solde_calcule):,.2f} €")
            row.cells[2].paragraphs[0].add_run(f"{float(alerte.solde_releve):,.2f} €")
            run_e = row.cells[3].paragraphs[0].add_run(f"{float(alerte.ecart):,.2f} €")
            run_e.font.color.rgb = RGBColor(180, 0, 0)
            run_e.font.bold = True

    # ── Signature ─────────────────────────────────────────────────────────────

    def _section_signature(self, doc: Document, cr: CompteResultat) -> None:
        doc.add_paragraph()
        p_lieu = doc.add_paragraph(
            f"Fait à {self.config.get('ville', '…')}, le {_date_fr(date.today())}"
        )
        p_lieu.runs[0].font.size = Pt(10)
        doc.add_paragraph()
        doc.add_paragraph()
        tresorier = self.config.get("tresorier", "Le(la) Trésorier(ère)")
        p_sig = doc.add_paragraph(f"Signature du trésorier : {tresorier}")
        p_sig.runs[0].font.bold = True
        doc.add_paragraph()
        doc.add_paragraph("_" * 45)
        doc.add_paragraph(tresorier).runs[0].font.italic = True

    # ── Conversion PDF ────────────────────────────────────────────────────────

    def convertir_en_pdf(self, chemin_docx: str) -> str | None:
        """Convertit le Word en PDF via Word COM (Windows) ou LibreOffice."""
        chemin_docx = Path(chemin_docx)
        chemin_pdf = chemin_docx.with_suffix(".pdf")
        if sys.platform == "win32":
            try:
                return self._convertir_word_com(chemin_docx, chemin_pdf)
            except Exception as e:
                logger.warning(f"Word COM: {e}")
        try:
            return self._convertir_libreoffice(chemin_docx, chemin_pdf)
        except Exception as e:
            logger.error(f"LibreOffice: {e}")
        return None

    def _convertir_word_com(self, src: Path, dst: Path) -> str:  # pragma: no cover
        import comtypes.client

        word = comtypes.client.CreateObject("Word.Application")
        word.Visible = False
        try:
            # Mettre à jour les champs (TOC, numéros de page) avant export
            doc = word.Documents.Open(str(src.resolve()))
            doc.Fields.Update()
            for section in doc.Sections:
                try:
                    section.Headers(1).Range.Fields.Update()
                    section.Footers(1).Range.Fields.Update()
                except Exception:
                    pass
            doc.SaveAs(str(dst.resolve()), FileFormat=17)
            doc.Close()
        finally:
            word.Quit()
        return str(dst)

    def _convertir_libreoffice(self, src: Path, dst: Path) -> str:  # pragma: no cover
        for cmd in ["libreoffice", "soffice"]:
            try:
                subprocess.run(
                    [
                        cmd,
                        "--headless",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        str(src.parent),
                        str(src),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
                return str(dst)
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        raise RuntimeError("LibreOffice introuvable.")


# Import manquant pour WD_TABLE_ALIGNMENT
try:
    from docx.enum.table import WD_TABLE_ALIGNMENT
except ImportError:
    pass
