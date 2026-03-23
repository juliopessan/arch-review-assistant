"""Orange DNA — Enterprise PDF Report Generator v2.

Full parity with the Markdown export. Every field the squad generates
appears in the PDF — no data left behind.

Sections:
  1. Cover            — diamond logo, title, date, model, severity stats
  2. Executive Summary — overall assessment + top recommendations + stats table
                         + domain distribution table
  3. Opening Questions — all questions numbered
  4. Findings by Domain — grouped by category, ordered by severity within domain
                           each card: #N, severity pill, title, description,
                           affected components, recommendation, ALL questions,
                           references
  5. Recommended ADRs  — numbered list
  6. Appendix Index    — compact table all findings (ref# + title + sev + domain)
"""
from __future__ import annotations

import io
from collections import defaultdict
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, KeepTogether,
    NextPageTemplate, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.flowables import Flowable

# ── Orange DNA palette ────────────────────────────────────────────────────────
ORANGE  = colors.HexColor("#F04E37")
DARK    = colors.HexColor("#2E2E2E")
TINT    = colors.HexColor("#FFF3F1")
MUTED   = colors.HexColor("#666666")
ROW_ALT = colors.HexColor("#F5F5F5")
WHITE   = colors.white
BORDER  = colors.HexColor("#E0E0E0")

SEV_COLORS = {
    "critical": colors.HexColor("#DC2626"),
    "high":     colors.HexColor("#EA580C"),
    "medium":   colors.HexColor("#D97706"),
    "low":      colors.HexColor("#2563EB"),
    "info":     colors.HexColor("#6B7280"),
}
SEV_BG = {
    "critical": colors.HexColor("#FEF2F2"),
    "high":     colors.HexColor("#FFF7ED"),
    "medium":   colors.HexColor("#FFFBEB"),
    "low":      colors.HexColor("#EFF6FF"),
    "info":     colors.HexColor("#F9FAFB"),
}

DOMAIN_ICONS = {
    "security": "SEC", "reliability": "REL", "cost": "COST",
    "observability": "OBS", "scalability": "SCALE",
    "performance": "PERF", "maintainability": "MAINT",
    "missing_adr": "ADR", "trade_off": "TRADE", "risk": "RISK",
}
DOMAIN_ORDER = [
    "security", "reliability", "cost", "observability",
    "scalability", "performance", "maintainability",
    "missing_adr", "trade_off", "risk",
]

PAGE_W, PAGE_H = A4
MARGIN    = 2.0 * cm
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Diamond logo ──────────────────────────────────────────────────────────────
class DiamondLogo(Flowable):
    def __init__(self, size=80):
        super().__init__()
        self.size = size
        self.width = self.height = size

    def draw(self):
        c = self.canv
        s = self.size
        cx, cy = s / 2, s / 2

        def poly(pts):
            p = c.beginPath()
            p.moveTo(pts[0], pts[1])
            for i in range(2, len(pts), 2):
                p.lineTo(pts[i], pts[i+1])
            p.close()
            return p

        c.setFillColor(ORANGE)
        c.drawPath(poly([cx, s-2, s-2, cy, cx, 2, 2, cy]), fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#FF7A59"))
        c.setFillAlpha(0.35)
        c.drawPath(poly([cx, s-2, s-2, cy, cx, cy]), fill=1, stroke=0)
        c.setFillAlpha(1.0)
        c.setFillColor(colors.HexColor("#C03020"))
        c.setFillAlpha(0.25)
        c.drawPath(poly([cx, s-2, 2, cy, cx, cy]), fill=1, stroke=0)
        c.setFillAlpha(1.0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", s * 0.28)
        c.drawCentredString(cx, cy - s * 0.09, "AR")


# ── Page decorators ───────────────────────────────────────────────────────────
def _draw_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(ORANGE)
    canvas.rect(0, PAGE_H - 14*mm, PAGE_W, 14*mm, fill=1, stroke=0)
    canvas.setFillColor(DARK)
    canvas.rect(0, 0, PAGE_W, 10*mm, fill=1, stroke=0)
    canvas.restoreState()


def _draw_page(canvas, doc):
    canvas.saveState()
    yt = PAGE_H - MARGIN + 3*mm
    canvas.setStrokeColor(ORANGE)
    canvas.setLineWidth(1.5)
    canvas.line(MARGIN, yt, PAGE_W - MARGIN, yt)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(ORANGE)
    canvas.drawString(MARGIN, yt + 3*mm, "ARCHITECTURE REVIEW")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN + 4.2*cm, yt + 3*mm, "— Orange DNA")
    canvas.drawRightString(PAGE_W - MARGIN, yt + 3*mm,
                           datetime.now().strftime("%B %Y"))
    yb = MARGIN - 6*mm
    canvas.setStrokeColor(ORANGE)
    canvas.line(MARGIN, yb + 4*mm, PAGE_W - MARGIN, yb + 4*mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, yb, "Confidential — Architecture Review Report")
    canvas.drawRightString(PAGE_W - MARGIN, yb, f"Page {doc.page}")
    canvas.restoreState()


# ── Styles ────────────────────────────────────────────────────────────────────
def _S():
    def ps(name, **kw):
        d = dict(fontName="Helvetica", fontSize=10, leading=14,
                 textColor=DARK, spaceAfter=4)
        d.update(kw)
        return ParagraphStyle(name=name, **d)

    return {
        "cover_title": ps("ct", fontName="Helvetica-Bold", fontSize=30,
                          textColor=DARK, leading=36, spaceAfter=4),
        "cover_orange": ps("co", fontName="Helvetica-Bold", fontSize=30,
                           textColor=ORANGE, leading=36, spaceAfter=14),
        "cover_sub":   ps("cs", fontSize=13, textColor=MUTED, leading=18, spaceAfter=4),
        "cover_meta":  ps("cm", fontSize=10, textColor=MUTED, leading=14),
        "h1":          ps("h1", fontName="Helvetica-Bold", fontSize=15,
                          textColor=ORANGE, leading=19, spaceBefore=14, spaceAfter=4),
        "h2":          ps("h2", fontName="Helvetica-Bold", fontSize=12,
                          textColor=DARK, leading=16, spaceBefore=10, spaceAfter=4),
        "body":        ps("body", fontSize=10, leading=15, spaceAfter=4),
        "muted":       ps("muted", fontSize=9, textColor=MUTED, leading=13, spaceAfter=2),
        "ft":          ps("ft", fontName="Helvetica-Bold", fontSize=11,
                          textColor=DARK, leading=15, spaceAfter=3),
        "label":       ps("lbl", fontName="Helvetica-Bold", fontSize=9,
                          textColor=ORANGE, leading=12, spaceAfter=1),
        "rec":         ps("rec", fontSize=10, textColor=DARK, leading=15, spaceAfter=4),
        "q":           ps("q", fontSize=9, textColor=MUTED, leading=13,
                          leftIndent=8, spaceAfter=1),
        "ref":         ps("ref", fontName="Helvetica-Oblique", fontSize=8,
                          textColor=MUTED, leading=11, leftIndent=8, spaceAfter=1),
        "toc_h":       ps("toch", fontName="Helvetica-Bold", fontSize=9,
                          textColor=WHITE, leading=12, alignment=TA_CENTER),
        "toc":         ps("toc", fontSize=8, leading=12, spaceAfter=0),
        "toc_c":       ps("tocc", fontSize=8, leading=12, spaceAfter=0,
                          alignment=TA_CENTER),
        "footer":      ps("fn", fontSize=8, textColor=MUTED,
                          alignment=TA_CENTER, leading=12),
    }


def _rule():
    return HRFlowable(width="100%", thickness=1.5, color=ORANGE,
                      spaceAfter=6, spaceBefore=2)


# ── Main ─────────────────────────────────────────────────────────────────────
def build_pdf(review_result, lang: str = "en") -> bytes:
    buf  = io.BytesIO()
    ST   = _S()
    r    = review_result
    s    = r.summary
    now  = datetime.now().strftime("%B %d, %Y")
    total = s.total_findings or 1

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN + 8*mm, bottomMargin=MARGIN + 8*mm,
        title="Architecture Review Report",
        author="Orange DNA — Architecture Review",
    )
    cover_frame  = Frame(0, 0, PAGE_W, PAGE_H,
                         leftPadding=3*cm, rightPadding=3*cm,
                         topPadding=5*cm, bottomPadding=3*cm, id="cover")
    normal_frame = Frame(MARGIN, MARGIN + 10*mm,
                         CONTENT_W, PAGE_H - 2*MARGIN - 20*mm, id="normal")
    doc.addPageTemplates([
        PageTemplate(id="Cover",  frames=[cover_frame],  onPage=_draw_cover),
        PageTemplate(id="Normal", frames=[normal_frame], onPage=_draw_page),
    ])

    story = []

    # ── COVER ─────────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 1.4*cm), DiamondLogo(88), Spacer(1, 1*cm),
        Paragraph("Architecture", ST["cover_title"]),
        Paragraph("Review Report", ST["cover_orange"]),
        Paragraph(f"Generated {now}", ST["cover_sub"]),
        Paragraph(f"Model: {r.model_used}", ST["cover_meta"]),
        Spacer(1, 0.7*cm),
    ]

    cw = (PAGE_W - 6*cm) / 6
    def _ch(t): return Paragraph(t, ParagraphStyle("", fontName="Helvetica-Bold",
        fontSize=8, textColor=WHITE, alignment=TA_CENTER, leading=11))
    def _cv(v): return Paragraph(str(v), ParagraphStyle("", fontName="Helvetica-Bold",
        fontSize=14, textColor=DARK, alignment=TA_CENTER, leading=17))
    cover_tbl = Table(
        [[_ch("🔴 Critical"), _ch("🟠 High"), _ch("🟡 Medium"),
          _ch("🔵 Low"), _ch("⚪ Info"), _ch("Total")],
         [_cv(s.critical_count), _cv(s.high_count), _cv(s.medium_count),
          _cv(s.low_count), _cv(s.info_count), _cv(s.total_findings)]],
        colWidths=[cw]*6, rowHeights=[16, 24],
    )
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("BACKGROUND", (0, 1), (-1, 1), TINT),
        ("GRID",       (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [cover_tbl, NextPageTemplate("Normal"), PageBreak()]

    # ── EXECUTIVE SUMMARY ─────────────────────────────────────────────────────
    story += [Paragraph("EXECUTIVE SUMMARY", ST["h1"]), _rule()]

    if s.overall_assessment:
        story += [Paragraph(s.overall_assessment, ST["body"]), Spacer(1, 0.3*cm)]

    if getattr(s, "top_recommendations", None):
        story.append(Paragraph("Top Recommendations" if lang=="en"
                                else "Principais Recomendações", ST["h2"]))
        for i, rec in enumerate(s.top_recommendations, 1):
            story.append(Paragraph(f"<b>{i}.</b>  {rec}", ST["body"]))
        story.append(Spacer(1, 0.3*cm))

    # Severity table
    sev_rows = [[Paragraph("Severity", ST["toc_h"]),
                 Paragraph("Count", ST["toc_h"]),
                 Paragraph("% of Total", ST["toc_h"])]]
    for name, count in [("Critical", s.critical_count), ("High", s.high_count),
                         ("Medium", s.medium_count), ("Low", s.low_count),
                         ("Info", s.info_count)]:
        col = SEV_COLORS.get(name.lower(), DARK)
        sev_rows.append([
            Paragraph(f'<font color="{col.hexval()}"><b>{name}</b></font>', ST["toc"]),
            Paragraph(f"<b>{count}</b>",
                      ParagraphStyle("", fontName="Helvetica-Bold", fontSize=9,
                                     leading=12, alignment=TA_CENTER)),
            Paragraph(f"{count/total*100:.0f}%",
                      ParagraphStyle("", fontSize=9, leading=12, alignment=TA_CENTER)),
        ])
    sev_rows.append([
        Paragraph("<b>Total</b>", ST["toc"]),
        Paragraph(f'<font color="{ORANGE.hexval()}"><b>{s.total_findings}</b></font>',
                  ParagraphStyle("", fontName="Helvetica-Bold", fontSize=9,
                                 leading=12, alignment=TA_CENTER)),
        Paragraph("100%", ParagraphStyle("", fontSize=9, leading=12, alignment=TA_CENTER)),
    ])
    sev_tbl = Table(sev_rows, colWidths=[9*cm, 3*cm, 3*cm], rowHeights=18)
    sev_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK),
        ("BACKGROUND",    (0, -1), (-1, -1), TINT),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2), [WHITE, ROW_ALT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(sev_tbl)

    # Domain distribution
    domain_counts: dict[str, int] = defaultdict(int)
    for f in r.findings:
        domain_counts[f.category.value] += 1

    story += [Spacer(1, 0.4*cm),
              Paragraph("Findings by Domain" if lang=="en"
                         else "Findings por Domínio", ST["h2"])]
    dom_rows = [[Paragraph("Domain", ST["toc_h"]),
                 Paragraph("Count", ST["toc_h"]),
                 Paragraph("Critical + High", ST["toc_h"])]]
    for dom in DOMAIN_ORDER:
        cnt = domain_counts.get(dom, 0)
        if not cnt:
            continue
        ch = sum(1 for f in r.findings
                 if f.category.value == dom and f.severity.value in ("critical","high"))
        icon = DOMAIN_ICONS.get(dom, "•")
        dom_rows.append([
            Paragraph(f"{icon}  {dom.replace('_',' ').title()}", ST["toc"]),
            Paragraph(str(cnt), ParagraphStyle("", fontSize=9, leading=12, alignment=TA_CENTER)),
            Paragraph(f'<font color="{SEV_COLORS["high"].hexval()}"><b>{ch}</b></font>'
                      if ch else "0",
                      ParagraphStyle("", fontSize=9, leading=12, alignment=TA_CENTER)),
        ])
    dom_tbl = Table(dom_rows, colWidths=[9*cm, 3*cm, 3*cm], rowHeights=18)
    dom_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [dom_tbl, Spacer(1, 0.4*cm)]

    # ── OPENING QUESTIONS ─────────────────────────────────────────────────────
    if r.senior_architect_questions:
        story += [
            Paragraph("OPENING QUESTIONS" if lang=="en"
                       else "PERGUNTAS DE ABERTURA", ST["h1"]),
            _rule(),
            Paragraph("Questions a senior architect should ask before proceeding:"
                       if lang=="en"
                       else "Perguntas que um arquiteto sênior deve fazer antes de prosseguir:",
                       ST["muted"]),
            Spacer(1, 0.2*cm),
        ]
        for i, q in enumerate(r.senior_architect_questions, 1):
            story.append(Paragraph(f"<b>{i}.</b>  {q}", ST["body"]))
        story.append(Spacer(1, 0.3*cm))

    # ── FINDINGS BY DOMAIN ────────────────────────────────────────────────────
    story += [Paragraph("FINDINGS", ST["h1"]), _rule()]

    domains_present = [d for d in DOMAIN_ORDER if d in domain_counts]
    for d in domain_counts:
        if d not in domains_present:
            domains_present.append(d)

    sev_order  = ["critical", "high", "medium", "low", "info"]
    finding_no = 0

    for domain in domains_present:
        dom_findings = sorted(
            [f for f in r.findings if f.category.value == domain],
            key=lambda f: sev_order.index(f.severity.value)
            if f.severity.value in sev_order else 99
        )
        if not dom_findings:
            continue

        crit_high = sum(1 for f in dom_findings
                        if f.severity.value in ("critical","high"))
        label     = domain.replace("_", " ").upper()
        badge     = DOMAIN_ICONS.get(domain, "•")

        # Domain section header
        hdr_tbl = Table([[
            Paragraph(f"{badge}  {label}",
                      ParagraphStyle("dh", fontName="Helvetica-Bold", fontSize=11,
                                     textColor=WHITE, leading=15)),
            Paragraph(f"{len(dom_findings)} findings"
                       + (f"  ·  {crit_high} critical/high" if crit_high else ""),
                       ParagraphStyle("dc", fontSize=9, textColor=WHITE,
                                      leading=13, alignment=TA_RIGHT)),
        ]], colWidths=[CONTENT_W*0.62, CONTENT_W*0.38], rowHeights=22)
        hdr_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), DARK),
            ("LEFTPADDING", (0,0), (0,-1), 10),
            ("RIGHTPADDING", (-1,0), (-1,-1), 10),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LINEBEFORE", (0,0), (0,-1), 4, ORANGE),
        ]))
        story += [Spacer(1, 0.3*cm), hdr_tbl, Spacer(1, 0.12*cm)]

        for finding in dom_findings:
            finding_no += 1
            sev = finding.severity.value
            col = SEV_COLORS.get(sev, DARK)
            bg  = SEV_BG.get(sev, WHITE)

            rows = []

            # Title
            rows.append([Paragraph(
                f'<font color="{MUTED.hexval()}" size="8"><b>#{finding_no:02d}</b></font>  '
                f'<font color="{col.hexval()}"><b>[{sev.upper()}]</b></font>  '
                f'<b>{finding.title}</b>',
                ST["ft"]
            )])

            # Description
            rows.append([Paragraph(finding.description, ST["body"])])

            # Affected
            if finding.affected_components:
                rows.append([Paragraph(
                    f'<font color="{ORANGE.hexval()}"><b>Affected:</b></font>  '
                    + "  ·  ".join(finding.affected_components),
                    ST["muted"]
                )])

            # Recommendation
            rows.append([Paragraph(
                f'<font color="{ORANGE.hexval()}"><b>Recommendation:</b></font>',
                ST["label"])])
            rows.append([Paragraph(finding.recommendation, ST["rec"])])

            # All questions
            if finding.questions_to_ask:
                rows.append([Paragraph(
                    '<b>Questions to ask:</b>',
                    ParagraphStyle("", fontName="Helvetica-Bold", fontSize=9,
                                   textColor=DARK, leading=12, spaceAfter=2)
                )])
                for q in finding.questions_to_ask:
                    rows.append([Paragraph(f"→  {q}", ST["q"])])

            # References
            if finding.references:
                rows.append([Paragraph(
                    '<b>References:</b>',
                    ParagraphStyle("", fontName="Helvetica-Bold", fontSize=8,
                                   textColor=MUTED, leading=11, spaceAfter=1)
                )])
                for ref in finding.references:
                    rows.append([Paragraph(f"• {ref}", ST["ref"])])

            card = Table(rows, colWidths=[CONTENT_W - 6*mm])
            card.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), bg),
                ("LEFTPADDING",   (0,0), (-1,-1), 10),
                ("RIGHTPADDING",  (0,0), (-1,-1), 8),
                ("TOPPADDING",    (0,0), (0,0),   8),
                ("BOTTOMPADDING", (0,-1),(0,-1),  8),
                ("TOPPADDING",    (0,1), (-1,-1), 2),
                ("BOTTOMPADDING", (0,0), (-1,-2), 2),
                ("LINEBEFORE",    (0,0), (-1,-1), 4, col),
            ]))
            story.append(KeepTogether([card, Spacer(1, 0.18*cm)]))

    # ── RECOMMENDED ADRs ──────────────────────────────────────────────────────
    if r.recommended_adrs:
        story += [
            Spacer(1, 0.3*cm),
            Paragraph("RECOMMENDED ADRs" if lang=="en" else "ADRs RECOMENDADOS", ST["h1"]),
            _rule(),
            Paragraph("These architectural decisions should be documented as ADRs:"
                       if lang=="en"
                       else "Estas decisões devem ser documentadas como ADRs:",
                       ST["muted"]),
            Spacer(1, 0.2*cm),
        ]
        for i, adr in enumerate(r.recommended_adrs, 1):
            story.append(Paragraph(f"<b>{i}.</b>  {adr}", ST["body"]))

    # ── APPENDIX: FINDING INDEX ───────────────────────────────────────────────
    story += [
        PageBreak(),
        Paragraph("APPENDIX — FINDINGS INDEX" if lang=="en"
                   else "APÊNDICE — ÍNDICE DE FINDINGS", ST["h1"]),
        _rule(),
        Paragraph("Quick reference for all findings in this report."
                   if lang=="en"
                   else "Referência rápida de todos os findings neste relatório.",
                   ST["muted"]),
        Spacer(1, 0.3*cm),
    ]

    idx_rows = [[
        Paragraph("#",        ST["toc_h"]),
        Paragraph("Finding",  ST["toc_h"]),
        Paragraph("Severity", ST["toc_h"]),
        Paragraph("Domain",   ST["toc_h"]),
    ]]
    n = 0
    for domain in domains_present:
        for finding in sorted(
            [f for f in r.findings if f.category.value == domain],
            key=lambda f: sev_order.index(f.severity.value)
            if f.severity.value in sev_order else 99
        ):
            n += 1
            col = SEV_COLORS.get(finding.severity.value, DARK)
            idx_rows.append([
                Paragraph(f"#{n:02d}",
                          ParagraphStyle("", fontSize=8, leading=11, alignment=TA_CENTER)),
                Paragraph(finding.title,
                          ParagraphStyle("", fontSize=8, leading=11)),
                Paragraph(f'<font color="{col.hexval()}"><b>{finding.severity.value.upper()}</b></font>',
                          ParagraphStyle("", fontSize=8, leading=11, alignment=TA_CENTER)),
                Paragraph(domain.replace("_"," ").title(),
                          ParagraphStyle("", fontSize=8, leading=11)),
            ])

    idx_tbl = Table(idx_rows,
                    colWidths=[1.2*cm, CONTENT_W - 7.2*cm, 2.5*cm, 3.5*cm],
                    repeatRows=1)
    idx_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, ROW_ALT]),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
    ]))
    story.append(idx_tbl)

    # Closing strip
    story += [
        Spacer(1, 0.5*cm), _rule(),
        Paragraph(
            f"Orange DNA Architecture Review  ·  {now}  ·  {r.model_used}  ·  "
            f"{s.total_findings} findings",
            ST["footer"]
        )
    ]

    doc.build(story)
    buf.seek(0)
    return buf.read()
