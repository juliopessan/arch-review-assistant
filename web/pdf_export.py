"""Orange DNA — Enterprise PDF Report Generator.

Generates a fully branded PDF architecture review report using
the Orange DNA design system (primary #F04E37, dark #2E2E2E).

Sections:
  1. Cover page — diamond logo + title + metadata
  2. Executive Summary — severity stats + overall assessment
  3. Opening Questions — senior architect questions
  4. Findings — per-finding cards with severity pill + recommendation
  5. Recommended ADRs — list of decision records to create
  6. Footer — page numbers with Orange DNA bar
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

# ── Orange DNA palette ────────────────────────────────────────────────────────
ORANGE   = colors.HexColor("#F04E37")
DARK     = colors.HexColor("#2E2E2E")
TINT     = colors.HexColor("#FFF3F1")
WARN_BG  = colors.HexColor("#FFE5DF")
MUTED    = colors.HexColor("#666666")
ROW_ALT  = colors.HexColor("#F5F5F5")
SOFT     = colors.HexColor("#FF7A59")
WHITE    = colors.white
BLACK    = colors.black

SEV_COLORS = {
    "critical": colors.HexColor("#DC2626"),
    "high":     colors.HexColor("#EA580C"),
    "medium":   colors.HexColor("#D97706"),
    "low":      colors.HexColor("#2563EB"),
    "info":     colors.HexColor("#6B7280"),
}

SEV_LABELS = {
    "critical": "CRITICAL",
    "high":     "HIGH",
    "medium":   "MEDIUM",
    "low":      "LOW",
    "info":     "INFO",
}

PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm


# ── Diamond logo flowable ─────────────────────────────────────────────────────

class DiamondLogo(Flowable):
    """Orange DNA diamond (AR) — SVG-inspired drawn via ReportLab canvas."""

    def __init__(self, size: float = 80):
        super().__init__()
        self.size = size
        self.width  = size
        self.height = size

    def draw(self):
        c = self.canv
        s = self.size
        cx, cy = s / 2, s / 2

        def diamond_path(pts_flat):
            p = c.beginPath()
            p.moveTo(pts_flat[0], pts_flat[1])
            for i in range(2, len(pts_flat), 2):
                p.lineTo(pts_flat[i], pts_flat[i+1])
            p.close()
            return p

        # Diamond base
        c.setFillColor(ORANGE)
        c.setStrokeColor(ORANGE)
        base = diamond_path([cx, s-2, s-2, cy, cx, 2, 2, cy])
        c.drawPath(base, fill=1, stroke=0)

        # Top-right highlight
        c.setFillColor(colors.HexColor("#FF7A59"))
        c.setFillAlpha(0.35)
        hi = diamond_path([cx, s-2, s-2, cy, cx, cy])
        c.drawPath(hi, fill=1, stroke=0)
        c.setFillAlpha(1.0)

        # Top-left shadow
        c.setFillColor(colors.HexColor("#C03020"))
        c.setFillAlpha(0.25)
        sh = diamond_path([cx, s-2, 2, cy, cx, cy])
        c.drawPath(sh, fill=1, stroke=0)
        c.setFillAlpha(1.0)

        # "AR" text
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", s * 0.28)
        c.drawCentredString(cx, cy - s * 0.09, "AR")


# ── Page templates ────────────────────────────────────────────────────────────

def _draw_cover(canvas, doc):
    """Cover page: full orange top bar + bottom bar."""
    canvas.saveState()
    # Top orange bar
    canvas.setFillColor(ORANGE)
    canvas.rect(0, PAGE_H - 14 * mm, PAGE_W, 14 * mm, fill=1, stroke=0)
    # Bottom orange bar
    canvas.setFillColor(ORANGE)
    canvas.rect(0, 0, PAGE_W, 10 * mm, fill=1, stroke=0)
    canvas.restoreState()


def _draw_page(canvas, doc):
    """Normal page header + footer with Orange DNA lines."""
    canvas.saveState()
    y_header = PAGE_H - MARGIN + 4 * mm

    # Header line
    canvas.setStrokeColor(ORANGE)
    canvas.setLineWidth(1.5)
    canvas.line(MARGIN, y_header, PAGE_W - MARGIN, y_header)

    # Header text
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(DARK)
    canvas.drawString(MARGIN, y_header + 3 * mm, "Architecture Review Report")
    canvas.setFillColor(MUTED)
    ts = datetime.now().strftime("%B %Y")
    canvas.drawRightString(PAGE_W - MARGIN, y_header + 3 * mm, ts)

    # Footer line
    y_footer = MARGIN - 8 * mm
    canvas.setStrokeColor(ORANGE)
    canvas.line(MARGIN, y_footer + 4 * mm, PAGE_W - MARGIN, y_footer + 4 * mm)

    # Footer text
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, y_footer, "Orange DNA — Architecture Review")
    canvas.drawRightString(PAGE_W - MARGIN, y_footer,
                           f"Page {doc.page}")
    canvas.restoreState()


# ── Style helpers ─────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()

    def s(name, **kw):
        defaults = dict(fontName="Helvetica", fontSize=10, leading=14,
                        textColor=DARK, spaceAfter=4)
        defaults.update(kw)
        return ParagraphStyle(name=name, **defaults)

    return {
        "cover_title":   s("ct", fontName="Helvetica-Bold", fontSize=28,
                           textColor=DARK, leading=34, spaceAfter=8),
        "cover_sub":     s("cs", fontName="Helvetica", fontSize=13,
                           textColor=MUTED, leading=18, spaceAfter=6),
        "cover_meta":    s("cm", fontName="Helvetica", fontSize=10,
                           textColor=MUTED, leading=14, spaceAfter=4),
        "h1":            s("h1", fontName="Helvetica-Bold", fontSize=16,
                           textColor=ORANGE, leading=20, spaceBefore=14, spaceAfter=6),
        "h2":            s("h2", fontName="Helvetica-Bold", fontSize=12,
                           textColor=DARK, leading=16, spaceBefore=10, spaceAfter=4),
        "body":          s("body", fontSize=10, leading=15, spaceAfter=6),
        "body_muted":    s("bm", fontSize=9, textColor=MUTED, leading=13, spaceAfter=3),
        "finding_title": s("ft", fontName="Helvetica-Bold", fontSize=11,
                           textColor=DARK, leading=15, spaceAfter=3),
        "label":         s("lb", fontName="Helvetica-Bold", fontSize=9,
                           textColor=ORANGE, leading=12, spaceAfter=2),
        "rec":           s("rc", fontName="Helvetica-Oblique", fontSize=10,
                           textColor=DARK, leading=14, spaceAfter=4),
        "question":      s("q", fontSize=9, textColor=MUTED, leading=13,
                           leftIndent=12, spaceAfter=2),
        "toc_h":         s("th", fontName="Helvetica-Bold", fontSize=9,
                           textColor=WHITE, leading=12),
        "table_cell":    s("tc", fontSize=9, leading=13, spaceAfter=2),
        "table_cell_c":  s("tcc", fontSize=9, leading=13, alignment=TA_CENTER),
    }


def _rule():
    return HRFlowable(width="100%", thickness=1.5, color=ORANGE, spaceAfter=8, spaceBefore=4)


def _sev_pill(severity: str) -> str:
    col = SEV_COLORS.get(severity, DARK)
    label = SEV_LABELS.get(severity, severity.upper())
    hex_col = col.hexval() if hasattr(col, 'hexval') else "#666666"
    return f'<font color="{hex_col}"><b>[{label}]</b></font>'


# ── Main builder ──────────────────────────────────────────────────────────────

def build_pdf(review_result, lang: str = "en") -> bytes:
    """Build Orange DNA enterprise PDF. Returns bytes ready for st.download_button."""
    buf = io.BytesIO()
    st = _styles()

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 6 * mm,
        bottomMargin=MARGIN + 6 * mm,
        title="Architecture Review Report",
        author="Orange DNA — Architecture Review",
    )

    cover_frame  = Frame(0, 0, PAGE_W, PAGE_H, leftPadding=3*cm,
                         rightPadding=3*cm, topPadding=5*cm, bottomPadding=3*cm, id="cover")
    normal_frame = Frame(MARGIN, MARGIN + 8*mm, PAGE_W - 2*MARGIN,
                         PAGE_H - 2*MARGIN - 16*mm, id="normal")

    doc.addPageTemplates([
        PageTemplate(id="Cover",  frames=[cover_frame],  onPage=_draw_cover),
        PageTemplate(id="Normal", frames=[normal_frame], onPage=_draw_page),
    ])

    r   = review_result
    s   = r.summary
    now = datetime.now().strftime("%B %d, %Y")
    story = []

    # ── COVER ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5 * cm))
    story.append(DiamondLogo(size=90))
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("Architecture", st["cover_title"]))
    story.append(Paragraph("Review Report", ParagraphStyle(
        "cth", fontName="Helvetica-Bold", fontSize=28, textColor=ORANGE,
        leading=34, spaceAfter=20)))
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(f"Generated {now}", st["cover_sub"]))
    story.append(Paragraph(f"Model: {r.model_used}", st["cover_meta"]))
    story.append(Spacer(1, 0.8 * cm))

    # Stats bar on cover
    sev_data = [
        ["🔴 Critical", "🟠 High", "🟡 Medium", "🔵 Low", "⚪ Info", "Total"],
        [str(s.critical_count), str(s.high_count), str(s.medium_count),
         str(s.low_count), str(s.info_count), str(s.total_findings)],
    ]
    col_w = (PAGE_W - 6*cm) / 6
    cover_table = Table(sev_data, colWidths=[col_w] * 6, rowHeights=[18, 22])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 8),
        ("BACKGROUND",  (0, 1), (-1, 1), TINT),
        ("TEXTCOLOR",   (0, 1), (-1, 1), DARK),
        ("FONTNAME",    (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 1), (-1, 1), 12),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(cover_table)
    story.append(NextPageTemplate("Normal"))
    story.append(PageBreak())

    # ── EXECUTIVE SUMMARY ─────────────────────────────────────────────────────
    story.append(Paragraph("EXECUTIVE SUMMARY", st["h1"]))
    story.append(_rule())

    if s.overall_assessment:
        story.append(Paragraph(s.overall_assessment, st["body"]))
        story.append(Spacer(1, 0.4 * cm))

    # Severity breakdown table
    sev_rows = [
        [Paragraph("Severity", st["toc_h"]),
         Paragraph("Count", st["toc_h"]),
         Paragraph("% of Total", st["toc_h"])],
    ]
    total = s.total_findings or 1
    for sev, count in [
        ("Critical", s.critical_count), ("High", s.high_count),
        ("Medium", s.medium_count),     ("Low",  s.low_count),
        ("Info",   s.info_count),
    ]:
        pct = f"{count / total * 100:.0f}%"
        col = SEV_COLORS.get(sev.lower(), DARK)
        sev_rows.append([
            Paragraph(f'<font color="{col.hexval()}"><b>{sev}</b></font>', st["table_cell"]),
            Paragraph(f"<b>{count}</b>", ParagraphStyle("", alignment=TA_CENTER, fontSize=9, leading=13)),
            Paragraph(pct, ParagraphStyle("", alignment=TA_CENTER, fontSize=9, leading=13)),
        ])
    sev_rows.append([
        Paragraph("<b>Total</b>", st["table_cell"]),
        Paragraph(f"<b>{s.total_findings}</b>", ParagraphStyle("", alignment=TA_CENTER, fontSize=9, leading=13, fontName="Helvetica-Bold")),
        Paragraph("100%", ParagraphStyle("", alignment=TA_CENTER, fontSize=9, leading=13)),
    ])

    sev_table = Table(sev_rows, colWidths=[9*cm, 3*cm, 3*cm], rowHeights=18)
    sev_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("BACKGROUND", (0, -1), (-1, -1), TINT),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, ROW_ALT]),
    ]))
    story.append(sev_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── OPENING QUESTIONS ─────────────────────────────────────────────────────
    if r.senior_architect_questions:
        story.append(Paragraph("OPENING QUESTIONS", st["h1"]))
        story.append(_rule())
        story.append(Paragraph(
            "Questions a senior architect should ask before proceeding:",
            st["body_muted"]))
        story.append(Spacer(1, 0.2 * cm))
        for i, q in enumerate(r.senior_architect_questions, 1):
            story.append(Paragraph(f"{i}.  {q}", st["body"]))
        story.append(Spacer(1, 0.3 * cm))

    # ── FINDINGS ──────────────────────────────────────────────────────────────
    story.append(Paragraph("FINDINGS", st["h1"]))
    story.append(_rule())
    story.append(Paragraph(
        f"{s.total_findings} findings across {len(set(f.category for f in r.findings))} "
        f"domains — ordered by severity.",
        st["body_muted"]))
    story.append(Spacer(1, 0.3 * cm))

    sev_order = ["critical", "high", "medium", "low", "info"]
    sorted_findings = sorted(r.findings,
                             key=lambda f: sev_order.index(f.severity.value)
                             if f.severity.value in sev_order else 99)

    for idx, finding in enumerate(sorted_findings):
        sev   = finding.severity.value
        col   = SEV_COLORS.get(sev, DARK)
        cat   = finding.category.value.replace("_", " ").upper()

        # Finding card — inner table with orange left accent
        card_rows = []

        # Title row
        card_rows.append([
            Paragraph(
                f'<font color="{col.hexval()}"><b>[{sev.upper()}]</b></font>'
                f'  <b>{finding.title}</b>  '
                f'<font color="#666666" size="8">{cat}</font>',
                st["finding_title"]
            )
        ])

        # Description
        card_rows.append([Paragraph(finding.description, st["body"])])

        if finding.affected_components:
            comps = ", ".join(finding.affected_components)
            card_rows.append([
                Paragraph(f'<font color="{ORANGE.hexval()}"><b>Affected:</b></font>  {comps}',
                          st["body_muted"])
            ])

        # Recommendation
        card_rows.append([
            Paragraph(f'<font color="{ORANGE.hexval()}"><b>Recommendation:</b></font>  '
                      f'{finding.recommendation}', st["body"])
        ])

        if finding.questions_to_ask:
            qs = "  ·  ".join(finding.questions_to_ask[:3])
            card_rows.append([Paragraph(f"<i>Q: {qs}</i>", st["question"])])

        card_table = Table(card_rows, colWidths=[PAGE_W - 2*MARGIN - 8*mm])
        bg = WARN_BG if sev == "critical" else (TINT if sev == "high" else WHITE)
        card_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), bg),
            ("LEFTPADDING",  (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (0, 0),   8),
            ("BOTTOMPADDING",(0, -1),(0, -1),  8),
            ("LINEBEFORE",   (0, 0), (-1, -1), 4, col),
            ("ROUNDEDCORNERS", [3]),
        ]))
        story.append(card_table)
        story.append(Spacer(1, 0.25 * cm))

    # ── RECOMMENDED ADRs ──────────────────────────────────────────────────────
    if r.recommended_adrs:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("RECOMMENDED ADRs", st["h1"]))
        story.append(_rule())
        story.append(Paragraph(
            "These decisions should be documented as Architecture Decision Records:",
            st["body_muted"]))
        story.append(Spacer(1, 0.2 * cm))
        for i, adr in enumerate(r.recommended_adrs, 1):
            story.append(Paragraph(f"<b>{i}.</b>  {adr}", st["body"]))
        story.append(Spacer(1, 0.3 * cm))

    # ── BACK COVER STRIP ──────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(_rule())
    story.append(Paragraph(
        f"Generated by Orange DNA Architecture Review  ·  {now}  ·  {r.model_used}",
        ParagraphStyle("footer_note", fontName="Helvetica", fontSize=8,
                       textColor=MUTED, alignment=TA_CENTER, leading=12)
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()
