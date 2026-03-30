"""Enterprise PDF export for architecture reviews."""

from __future__ import annotations

import html
import io
import re
from collections import Counter, defaultdict
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

ORANGE = colors.HexColor("#F04E37")
ORANGE_DARK = colors.HexColor("#C03020")
ORANGE_SOFT = colors.HexColor("#FF7A59")
DARK = colors.HexColor("#2E2E2E")
TINT = colors.HexColor("#FFF3F1")
WHITE = colors.white
MUTED = colors.HexColor("#666666")
ROW_ALT = colors.HexColor("#F5F5F5")
BORDER = colors.HexColor("#E0E0E0")

SEV_COLORS = {
    "critical": colors.HexColor("#DC2626"),
    "high": colors.HexColor("#EA580C"),
    "medium": colors.HexColor("#D97706"),
    "low": colors.HexColor("#2563EB"),
    "info": colors.HexColor("#6B7280"),
}

SEV_BG = {
    "critical": colors.HexColor("#FEF2F2"),
    "high": colors.HexColor("#FFF7ED"),
    "medium": colors.HexColor("#FFFBEB"),
    "low": colors.HexColor("#EFF6FF"),
    "info": colors.HexColor("#F9FAFB"),
}

DOMAIN_LABELS = {
    "security": "Security",
    "reliability": "Reliability",
    "cost": "Cost",
    "observability": "Observability",
    "scalability": "Scalability",
    "performance": "Performance",
    "maintainability": "Maintainability",
    "missing_adr": "ADR Gaps",
    "trade_off": "Trade-offs",
    "risk": "Risk",
}

DOMAIN_ORDER = [
    "security",
    "reliability",
    "cost",
    "observability",
    "scalability",
    "performance",
    "maintainability",
    "missing_adr",
    "trade_off",
    "risk",
]

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


class DiamondLogo(Flowable):
    """Simple vector logo for the report cover."""

    def __init__(self, size: float = 80) -> None:
        super().__init__()
        self.size = size
        self.width = size
        self.height = size

    def draw(self) -> None:
        canv = self.canv
        size = self.size
        cx, cy = size / 2, size / 2

        def polygon(points: list[float]):
            path = canv.beginPath()
            path.moveTo(points[0], points[1])
            for idx in range(2, len(points), 2):
                path.lineTo(points[idx], points[idx + 1])
            path.close()
            return path

        canv.setFillColor(ORANGE)
        canv.drawPath(polygon([cx, size - 2, size - 2, cy, cx, 2, 2, cy]), fill=1, stroke=0)
        canv.setFillColor(ORANGE_SOFT)
        canv.setFillAlpha(0.35)
        canv.drawPath(polygon([cx, size - 2, size - 2, cy, cx, cy]), fill=1, stroke=0)
        canv.setFillAlpha(1)
        canv.setFillColor(ORANGE_DARK)
        canv.setFillAlpha(0.25)
        canv.drawPath(polygon([cx, size - 2, 2, cy, cx, cy]), fill=1, stroke=0)
        canv.setFillAlpha(1)
        canv.setFillColor(WHITE)
        canv.setFont("Helvetica-Bold", size * 0.28)
        canv.drawCentredString(cx, cy - size * 0.09, "AR")


def _styles() -> dict[str, ParagraphStyle]:
    def style(name: str, **kwargs: object) -> ParagraphStyle:
        base = {
            "fontName": "Helvetica",
            "fontSize": 9.5,
            "leading": 13.5,
            "textColor": DARK,
            "spaceAfter": 4,
        }
        base.update(kwargs)
        return ParagraphStyle(name=name, **base)

    return {
        "cover_kicker": style("cover_kicker", fontName="Helvetica-Bold", fontSize=11, textColor=ORANGE, leading=14, spaceAfter=8),
        "cover_title": style("cover_title", fontName="Helvetica-Bold", fontSize=28, leading=32, spaceAfter=6),
        "cover_subtitle": style("cover_subtitle", fontSize=12, textColor=MUTED, leading=17, spaceAfter=4),
        "cover_meta": style("cover_meta", fontSize=9, textColor=MUTED, leading=13, spaceAfter=2),
        "section": style("section", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=ORANGE, spaceBefore=14, spaceAfter=5),
        "subsection": style("subsection", fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=4),
        "body": style("body"),
        "body_small": style("body_small", fontSize=8.5, leading=12, spaceAfter=3),
        "muted": style("muted", fontSize=8.5, textColor=MUTED, leading=12, spaceAfter=2),
        "label": style("label", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=ORANGE, spaceAfter=2),
        "card_title": style("card_title", fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceAfter=3),
        "metric_label": style("metric_label", fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=MUTED, alignment=TA_CENTER, spaceAfter=1),
        "metric_value": style("metric_value", fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=DARK, alignment=TA_CENTER, spaceAfter=0),
        "table_header": style("table_header", fontName="Helvetica-Bold", fontSize=8, textColor=WHITE, alignment=TA_CENTER, leading=11, spaceAfter=0),
        "table": style("table", fontSize=8.3, leading=11.2, spaceAfter=0),
        "table_center": style("table_center", fontSize=8.3, leading=11.2, alignment=TA_CENTER, spaceAfter=0),
        "footer": style("footer", fontSize=7.5, textColor=MUTED, alignment=TA_CENTER, leading=10, spaceAfter=0),
    }


def _rule() -> HRFlowable:
    return HRFlowable(width="100%", thickness=1.4, color=ORANGE, spaceBefore=2, spaceAfter=7)


def _safe_text(value: object) -> str:
    text = str(value or "")
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u2026": "...",
        "\u2192": "->",
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A1-\u00FF]", "", text)
    text = html.escape(text, quote=False)
    text = text.replace("\n", "<br/>")
    return text


def _paragraph(text: object, style: ParagraphStyle) -> Paragraph:
    safe = _safe_text(text).strip() or "-"
    return Paragraph(safe, style)


def _truncate(text: object, limit: int = 900) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    clipped = raw[:limit].rsplit(" ", 1)[0].strip()
    return f"{clipped}..."


def _metric_card(label: str, value: object, styles: dict[str, ParagraphStyle], bg: colors.Color = WHITE) -> Table:
    table = Table(
        [[_paragraph(label, styles["metric_label"])], [_paragraph(value, styles["metric_value"])]],
        colWidths=[CONTENT_W / 4 - 4 * mm],
        rowHeights=[14, 24],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _color_hex(color: colors.Color) -> str:
    return f"#{color.hexval()[2:]}"


def _kv_table(rows: list[tuple[str, object]], styles: dict[str, ParagraphStyle], col_widths: list[float] | None = None) -> Table:
    data = [[_paragraph(key, styles["label"]), _paragraph(value, styles["body"])] for key, value in rows if str(value or "").strip()]
    if not data:
        data = [[_paragraph("Status", styles["label"]), _paragraph("Not available", styles["body"])]]
    widths = col_widths or [4.2 * cm, CONTENT_W - 4.2 * cm]
    table = Table(data, colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, ROW_ALT]),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _bullet_lines(items: list[str], styles: dict[str, ParagraphStyle], prefix: str = "- ") -> list[Paragraph]:
    return [_paragraph(f"{prefix}{item}", styles["body"]) for item in items if str(item).strip()]


def _severity_order(value: str) -> int:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return order.get(value, 99)


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    rem = int(seconds % 60)
    return f"{minutes}m {rem}s"


def _format_started_at(iso_value: str) -> str:
    if not iso_value:
        return "-"
    try:
        return datetime.fromisoformat(iso_value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso_value


def _draw_cover(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(ORANGE)
    canvas.rect(0, PAGE_H - 14 * mm, PAGE_W, 14 * mm, fill=1, stroke=0)
    canvas.setFillColor(DARK)
    canvas.rect(0, 0, PAGE_W, 10 * mm, fill=1, stroke=0)
    canvas.restoreState()


def _draw_page(canvas, doc) -> None:
    canvas.saveState()
    header_y = PAGE_H - MARGIN + 4 * mm
    canvas.setStrokeColor(ORANGE)
    canvas.setLineWidth(1.2)
    canvas.line(MARGIN, header_y, PAGE_W - MARGIN, header_y)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(ORANGE)
    canvas.drawString(MARGIN, header_y + 3 * mm, "ARCHITECTURE REVIEW")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - MARGIN, header_y + 3 * mm, datetime.now().strftime("%Y-%m"))

    footer_y = MARGIN - 5 * mm
    canvas.setStrokeColor(ORANGE)
    canvas.line(MARGIN, footer_y + 4 * mm, PAGE_W - MARGIN, footer_y + 4 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, footer_y, "Confidential - Enterprise Architecture Review")
    canvas.drawRightString(PAGE_W - MARGIN, footer_y, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(review_result, lang: str = "en") -> bytes:
    """Build a branded enterprise PDF for a review result."""
    styles = _styles()
    buffer = io.BytesIO()
    review = review_result
    summary = review.summary
    now = datetime.now()
    generated_label = now.strftime("%B %d, %Y")
    report_mode = "Squad Review" if str(review.model_used).startswith("squad:") else "Quick Review"

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 8 * mm,
        bottomMargin=MARGIN + 8 * mm,
        title="Architecture Review Report",
        author="Architecture Review Assistant",
    )
    cover_frame = Frame(0, 0, PAGE_W, PAGE_H, leftPadding=3 * cm, rightPadding=3 * cm, topPadding=5 * cm, bottomPadding=3 * cm, id="cover")
    normal_frame = Frame(MARGIN, MARGIN + 10 * mm, CONTENT_W, PAGE_H - 2 * MARGIN - 20 * mm, id="normal")
    doc.addPageTemplates(
        [
            PageTemplate(id="Cover", frames=[cover_frame], onPage=_draw_cover),
            PageTemplate(id="Normal", frames=[normal_frame], onPage=_draw_page),
        ]
    )

    story: list[object] = []

    findings_by_domain: dict[str, list] = defaultdict(list)
    for finding in review.findings:
        findings_by_domain[finding.category.value].append(finding)

    active_agents = len(review.orchestration_plan.active_agents) if review.orchestration_plan else 0
    run_metrics = review.run_metrics
    roi = run_metrics.roi_label(lang) if run_metrics else "-"

    story.extend(
        [
            Spacer(1, 1.1 * cm),
            DiamondLogo(86),
            Spacer(1, 0.8 * cm),
            _paragraph("Enterprise Architecture Review", styles["cover_kicker"]),
            _paragraph("Architecture Review Report", styles["cover_title"]),
            _paragraph(f"Executive export generated {generated_label}", styles["cover_subtitle"]),
            _paragraph(f"Mode: {report_mode}", styles["cover_meta"]),
            _paragraph(f"Model: {review.model_used}", styles["cover_meta"]),
            _paragraph(f"Review version: {review.review_version}", styles["cover_meta"]),
            Spacer(1, 0.55 * cm),
        ]
    )

    metric_row = Table(
        [[
            _metric_card("Critical", summary.critical_count, styles, SEV_BG["critical"]),
            _metric_card("High", summary.high_count, styles, SEV_BG["high"]),
            _metric_card("Total Findings", summary.total_findings, styles, TINT),
            _metric_card("Active Agents", active_agents or "-", styles, WHITE),
        ]],
        colWidths=[CONTENT_W / 4] * 4,
    )
    metric_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.extend([metric_row, Spacer(1, 0.35 * cm)])

    cover_rows = [
        ("Top Risk", summary.top_risk or "No critical finding flagged"),
        ("Business Context", review.input.context or "Not provided"),
        ("Architecture Snapshot", _truncate(review.input.description, 420)),
    ]
    story.extend([_kv_table(cover_rows, styles), NextPageTemplate("Normal"), PageBreak()])

    story.extend([_paragraph("EXECUTIVE SUMMARY", styles["section"]), _rule()])
    if summary.overall_assessment:
        story.append(_paragraph(summary.overall_assessment, styles["body"]))
        story.append(Spacer(1, 0.12 * cm))

    story.append(_paragraph("Review Snapshot", styles["subsection"]))
    snapshot_rows = [
        ("Review Mode", report_mode),
        ("Generated On", generated_label),
        ("Model", review.model_used),
        ("Findings", summary.total_findings),
        ("Critical / High", f"{summary.critical_count} / {summary.high_count}"),
        ("ADR Candidates", len(review.recommended_adrs)),
        ("Business Context", review.input.context or "Not provided"),
    ]
    story.append(_kv_table(snapshot_rows, styles))

    story.append(Spacer(1, 0.2 * cm))
    story.append(_paragraph("Severity Breakdown", styles["subsection"]))
    severity_rows = [[_paragraph("Severity", styles["table_header"]), _paragraph("Count", styles["table_header"]), _paragraph("Share", styles["table_header"])]]
    total = summary.total_findings or 1
    for label, count in [
        ("Critical", summary.critical_count),
        ("High", summary.high_count),
        ("Medium", summary.medium_count),
        ("Low", summary.low_count),
        ("Info", summary.info_count),
    ]:
        severity_rows.append(
            [
                _paragraph(label, styles["table"]),
                _paragraph(str(count), styles["table_center"]),
                _paragraph(f"{(count / total) * 100:.0f}%", styles["table_center"]),
            ]
        )
    severity_table = Table(severity_rows, colWidths=[CONTENT_W * 0.5, CONTENT_W * 0.18, CONTENT_W * 0.18], repeatRows=1)
    severity_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(severity_table)

    if findings_by_domain:
        story.append(Spacer(1, 0.2 * cm))
        story.append(_paragraph("Domain Distribution", styles["subsection"]))
        domain_rows = [[_paragraph("Domain", styles["table_header"]), _paragraph("Findings", styles["table_header"]), _paragraph("Critical + High", styles["table_header"])]]
        for domain in DOMAIN_ORDER + [d for d in findings_by_domain if d not in DOMAIN_ORDER]:
            domain_findings = findings_by_domain.get(domain)
            if not domain_findings:
                continue
            elevated = sum(1 for finding in domain_findings if finding.severity.value in {"critical", "high"})
            domain_rows.append(
                [
                    _paragraph(DOMAIN_LABELS.get(domain, domain.replace("_", " ").title()), styles["table"]),
                    _paragraph(str(len(domain_findings)), styles["table_center"]),
                    _paragraph(str(elevated), styles["table_center"]),
                ]
            )
        domain_table = Table(domain_rows, colWidths=[CONTENT_W * 0.5, CONTENT_W * 0.18, CONTENT_W * 0.18], repeatRows=1)
        domain_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), DARK),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
                    ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(domain_table)

    architecture_excerpt = _truncate(review.input.description, 1200)
    if architecture_excerpt:
        story.extend([Spacer(1, 0.2 * cm), _paragraph("Architecture Scope", styles["subsection"]), _paragraph(architecture_excerpt, styles["body_small"])])

    if review.orchestration_plan:
        plan = review.orchestration_plan
        story.extend([_paragraph("AGENT MANAGER PLAN", styles["section"]), _rule()])
        plan_rows = [
            ("Architecture Type", plan.architecture_type),
            ("Complexity", plan.complexity.upper()),
            ("Active Agents", ", ".join(plan.active_agents) or "None"),
            ("Skipped Agents", ", ".join(plan.skipped_agents) or "None"),
            ("Cloud Providers", ", ".join(plan.cloud_providers) or "Not detected"),
            ("Compliance Flags", ", ".join(plan.compliance_flags) or "None"),
        ]
        story.append(_kv_table(plan_rows, styles))
        if plan.top_risks:
            story.extend([Spacer(1, 0.12 * cm), _paragraph("Manager-Identified Risks", styles["subsection"])])
            story.extend(_bullet_lines(plan.top_risks, styles))
        if plan.manager_briefing:
            story.extend([Spacer(1, 0.08 * cm), _paragraph("Manager Briefing", styles["subsection"]), _paragraph(plan.manager_briefing, styles["body"])])
        if plan.agent_focus_notes:
            focus_rows = [[_paragraph("Agent", styles["table_header"]), _paragraph("Priority", styles["table_header"]), _paragraph("Focus", styles["table_header"])]]
            for agent_name, note in plan.agent_focus_notes.items():
                focus_rows.append(
                    [
                        _paragraph(agent_name.replace("_", " "), styles["table"]),
                        _paragraph(plan.agent_priorities.get(agent_name, "normal").upper(), styles["table_center"]),
                        _paragraph(note, styles["table"]),
                    ]
                )
            focus_table = Table(focus_rows, colWidths=[CONTENT_W * 0.22, CONTENT_W * 0.16, CONTENT_W * 0.52], repeatRows=1)
            focus_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), DARK),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
                        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.extend([Spacer(1, 0.12 * cm), _paragraph("Agent Directives", styles["subsection"]), focus_table])

    if run_metrics:
        story.extend([_paragraph("RUN METRICS", styles["section"]), _rule()])
        metric_cards = Table(
            [[
                _metric_card("Total Time", _format_duration(run_metrics.total_duration_s), styles),
                _metric_card("Tokens", f"{run_metrics.tokens_total:,}", styles),
                _metric_card("Estimated Cost", f"${run_metrics.cost_usd:.4f}", styles),
                _metric_card("ROI", roi, styles),
            ]],
            colWidths=[CONTENT_W / 4] * 4,
        )
        story.append(metric_cards)
        story.append(Spacer(1, 0.18 * cm))
        runtime_rows = [
            ("Started At", _format_started_at(run_metrics.started_at)),
            ("Manager Phase", _format_duration(run_metrics.phase_manager_s)),
            ("Parallel Phase", _format_duration(run_metrics.phase_parallel_s)),
            ("Synthesizer Phase", _format_duration(run_metrics.phase_synth_s)),
        ]
        story.append(_kv_table(runtime_rows, styles))

        agent_rows = [[
            _paragraph("Agent", styles["table_header"]),
            _paragraph("Phase", styles["table_header"]),
            _paragraph("Duration", styles["table_header"]),
            _paragraph("Tokens", styles["table_header"]),
            _paragraph("Findings", styles["table_header"]),
        ]]
        for agent in run_metrics.agents:
            agent_rows.append(
                [
                    _paragraph(agent.agent_name.replace("_", " "), styles["table"]),
                    _paragraph(agent.phase, styles["table_center"]),
                    _paragraph(_format_duration(agent.duration_s), styles["table_center"]),
                    _paragraph(f"{agent.tokens_total:,}", styles["table_center"]),
                    _paragraph(str(agent.findings_count), styles["table_center"]),
                ]
            )
        agent_table = Table(agent_rows, colWidths=[CONTENT_W * 0.28, CONTENT_W * 0.16, CONTENT_W * 0.16, CONTENT_W * 0.18, CONTENT_W * 0.12], repeatRows=1)
        agent_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), DARK),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
                    ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.extend([Spacer(1, 0.12 * cm), _paragraph("Per-Agent Breakdown", styles["subsection"]), agent_table])

    if review.senior_architect_questions:
        story.extend([_paragraph("OPEN QUESTIONS", styles["section"]), _rule()])
        for idx, question in enumerate(review.senior_architect_questions, start=1):
            story.append(_paragraph(f"{idx}. {question}", styles["body"]))

    story.extend([_paragraph("FINDINGS", styles["section"]), _rule()])
    domains = [domain for domain in DOMAIN_ORDER if domain in findings_by_domain] + [domain for domain in findings_by_domain if domain not in DOMAIN_ORDER]
    finding_index = 0

    for domain in domains:
        domain_findings = sorted(findings_by_domain[domain], key=lambda item: _severity_order(item.severity.value))
        story.append(Spacer(1, 0.1 * cm))
        story.append(_paragraph(DOMAIN_LABELS.get(domain, domain.replace("_", " ").title()).upper(), styles["subsection"]))
        story.append(_paragraph(f"{len(domain_findings)} findings in this domain", styles["muted"]))

        for finding in domain_findings:
            finding_index += 1
            severity = finding.severity.value
            severity_color = SEV_COLORS.get(severity, DARK)
            rows = [
                [
                    Paragraph(
                        f'<font color="{_color_hex(severity_color)}"><b>{severity.upper()}</b></font> '
                        f'<font color="{_color_hex(MUTED)}">#{finding_index:02d}</font><br/><b>{_safe_text(finding.title)}</b>',
                        styles["card_title"],
                    )
                ],
                [_paragraph(finding.description, styles["body"])],
            ]
            if finding.affected_components:
                rows.append([_paragraph(f"Affected Components: {', '.join(finding.affected_components)}", styles["muted"])])
            rows.append([_paragraph("Recommendation", styles["label"])])
            rows.append([_paragraph(finding.recommendation, styles["body"])])
            if finding.questions_to_ask:
                rows.append([_paragraph("Questions to validate", styles["label"])])
                for question in finding.questions_to_ask:
                    rows.append([_paragraph(f"- {question}", styles["body_small"])])
            if finding.references:
                rows.append([_paragraph("References", styles["label"])])
                for reference in finding.references:
                    rows.append([_paragraph(f"- {reference}", styles["body_small"])])

            card = Table(rows, colWidths=[CONTENT_W - 4 * mm])
            card.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), SEV_BG.get(severity, WHITE)),
                        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                        ("LINEBEFORE", (0, 0), (-1, -1), 3.5, severity_color),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(KeepTogether([card, Spacer(1, 0.14 * cm)]))

    if review.recommended_adrs:
        story.extend([_paragraph("RECOMMENDED ADRS", styles["section"]), _rule()])
        story.extend(_bullet_lines([f"{idx}. {adr}" for idx, adr in enumerate(review.recommended_adrs, start=1)], styles))

    story.extend([PageBreak(), _paragraph("APPENDIX - FINDING INDEX", styles["section"]), _rule()])
    appendix_rows = [[
        _paragraph("#", styles["table_header"]),
        _paragraph("Finding", styles["table_header"]),
        _paragraph("Severity", styles["table_header"]),
        _paragraph("Domain", styles["table_header"]),
    ]]
    index_counter = 0
    for domain in domains:
        for finding in sorted(findings_by_domain[domain], key=lambda item: _severity_order(item.severity.value)):
            index_counter += 1
            appendix_rows.append(
                [
                    _paragraph(f"{index_counter:02d}", styles["table_center"]),
                    _paragraph(finding.title, styles["table"]),
                    _paragraph(finding.severity.value.upper(), styles["table_center"]),
                    _paragraph(DOMAIN_LABELS.get(domain, domain.replace("_", " ").title()), styles["table"]),
                ]
            )

    appendix_table = Table(appendix_rows, colWidths=[CONTENT_W * 0.08, CONTENT_W * 0.5, CONTENT_W * 0.16, CONTENT_W * 0.22], repeatRows=1)
    appendix_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(appendix_table)

    if review.findings:
        category_counts = Counter(finding.category.value for finding in review.findings)
        dominant_domain, dominant_count = category_counts.most_common(1)[0]
        summary_line = (
            f"{summary.total_findings} findings | dominant domain: "
            f"{DOMAIN_LABELS.get(dominant_domain, dominant_domain)} ({dominant_count}) | {review.model_used}"
        )
    else:
        summary_line = f"No findings | {review.model_used}"
    story.extend([Spacer(1, 0.25 * cm), _rule(), _paragraph(summary_line, styles["footer"])])

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
