"""Portable KC-branded PDF reports (no GTK, Cairo or external executables)."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#0B1B3D")
CYAN = colors.HexColor("#2CB4E8")
GOLD = colors.HexColor("#D7A72A")
MUTED = colors.HexColor("#64748B")
BORDER = colors.HexColor("#E2E8F0")


def safe(value):
    return escape(str(value if value is not None else ""))


def styles():
    default = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "KCTitle",
            parent=default["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "heading": ParagraphStyle(
            "KCHeading",
            parent=default["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=NAVY,
            spaceBefore=16,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "KCBody",
            parent=default["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=NAVY,
            spaceAfter=5,
        ),
        "muted": ParagraphStyle(
            "KCMuted",
            parent=default["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=12,
            textColor=MUTED,
            spaceAfter=5,
        ),
        "cell": ParagraphStyle(
            "KCCell",
            parent=default["BodyText"],
            fontSize=8,
            leading=11,
            textColor=NAVY,
            wordWrap="CJK",
        ),
        "tablehead": ParagraphStyle(
            "KCHead",
            parent=default["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
        ),
    }


def paragraph(value, style):
    return Paragraph(safe(value), style)


def table(headers, rows, sheet, widths=None):
    if not rows:
        return [Paragraph("No records.", sheet["muted"])]
    head = [paragraph(v, sheet["tablehead"]) for v in headers]
    body = [[paragraph(v, sheet["cell"]) for v in row] for row in rows]
    result = Table([head, *body], colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return [result]


def _page(canvas, document):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 18 * mm, width, 18 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(20 * mm, height - 11 * mm, "KC LEDGER")
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(2)
    canvas.line(20 * mm, height - 19 * mm, width - 20 * mm, height - 19 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, "PRIVATE FINANCIAL OPERATIONS  •  KC LEDGER")
    canvas.drawRightString(width - 20 * mm, 12 * mm, f"Page {document.page}")
    canvas.restoreState()


def build(title, story):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=title,
        author="KC Ledger",
        topMargin=27 * mm,
        bottomMargin=22 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )
    document.build(story, onFirstPage=_page, onLaterPages=_page)
    data = buffer.getvalue()
    if not data.startswith(b"%PDF"):
        raise ValueError("PDF generation failed.")
    return data


def invoice_pdf(invoice, payments, instalments, paid, outstanding):
    sheet = styles()
    story = [
        paragraph(f"Invoice {invoice.number}", sheet["title"]),
        paragraph(f"{invoice.title}  |  {invoice.status.replace('_', ' ').title()}", sheet["body"]),
        paragraph(f"Client: {invoice.client.name}  |  Currency: {invoice.currency}", sheet["body"]),
        paragraph(f"Issued: {invoice.issue_date}  |  Due: {invoice.due_date}", sheet["body"]),
        Spacer(1, 10),
        *table(
            ["Billed", "Collected", "Outstanding"],
            [
                [
                    f"{invoice.amount:.2f} {invoice.currency}",
                    f"{paid:.2f} {invoice.currency}",
                    f"{outstanding:.2f} {invoice.currency}",
                ]
            ],
            sheet,
            [155, 155, 155],
        ),
        Paragraph("Recorded payments", sheet["heading"]),
        *table(
            ["Date", "Amount", "Method", "Reference"],
            [
                [
                    p.paid_on,
                    f"{p.amount:.2f} {invoice.currency}",
                    p.method or "—",
                    p.reference or "—",
                ]
                for p in payments
            ],
            sheet,
            [100, 130, 110, 125],
        ),
        Paragraph("Instalment schedule", sheet["heading"]),
        *table(
            ["Due date", "Description", "Amount", "State"],
            [
                [i.due_date, i.label, f"{i.amount:.2f} {invoice.currency}", i.status]
                for i in instalments
            ],
            sheet,
            [95, 180, 105, 85],
        ),
    ]
    if invoice.notes:
        story.extend(
            [Paragraph("Notes", sheet["heading"]), paragraph(invoice.notes, sheet["body"])]
        )
    return build(f"KC Ledger - invoice {invoice.number}", story)


def client_dossier_pdf(client, score, invoices, events, base_currency, collected):
    sheet = styles()
    story = [
        paragraph(f"Client dossier: {client.name}", sheet["title"]),
        paragraph(f"{client.company or 'Independent'}  |  Status: {client.status}", sheet["body"]),
        paragraph(f"Health: {score['score']}/100 — {score['tier']}", sheet["body"]),
        paragraph(f"Lifetime collected: {collected} {base_currency}", sheet["body"]),
        Paragraph("Health score breakdown", sheet["heading"]),
        *table(
            ["Factor", "Points", "Assessment"],
            [
                [f.get("label"), f"{f.get('points')}/{f.get('maximum')}", f.get("detail")]
                for f in score.get("factors", [])
            ],
            sheet,
            [115, 65, 285],
        ),
        Paragraph("Invoices", sheet["heading"]),
        *table(
            ["Invoice", "Due", "Amount", "Outstanding", "Status"],
            [
                [
                    i["number"],
                    i["due_date"],
                    f"{i['amount']:.2f} {i['currency']}",
                    f"{i['outstanding']:.2f}",
                    i["status"],
                ]
                for i in invoices
            ],
            sheet,
            [100, 75, 110, 105, 75],
        ),
        Paragraph("Audit timeline (latest 250)", sheet["heading"]),
        *table(
            ["Date", "Event", "Details"],
            [[e.occurred_at.strftime("%Y-%m-%d"), e.title, e.detail] for e in events],
            sheet,
            [70, 165, 230],
        ),
    ]
    return build(f"KC Ledger - client dossier {client.name}", story)
