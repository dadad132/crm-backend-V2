"""
Job Card PDF Generator using ReportLab.
Produces a professional A4 job card for closed tickets.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Brand colours – subtle blue/slate palette
BRAND_DARK = colors.HexColor("#1e293b")   # slate-800
BRAND_MID = colors.HexColor("#3b82f6")    # blue-500
BRAND_LIGHT = colors.HexColor("#eff6ff")  # blue-50
BRAND_BORDER = colors.HexColor("#bfdbfe") # blue-200
LABEL_GRAY = colors.HexColor("#64748b")   # slate-500
TEXT_BLACK = colors.HexColor("#0f172a")   # slate-900
ROW_ALT = colors.HexColor("#f8fafc")      # slate-50


def _style(name, **kwargs) -> ParagraphStyle:
    base = getSampleStyleSheet()["Normal"]
    return ParagraphStyle(name, parent=base, **kwargs)


def generate_job_card_pdf(
    ticket_number: str,
    subject: str,
    priority: str,
    created_at: datetime,
    closed_at: datetime,
    technician_name: str,
    # Client details
    client_name: Optional[str] = None,
    client_surname: Optional[str] = None,
    client_phone: Optional[str] = None,
    client_office_number: Optional[str] = None,
    # Billing
    billable_traveling: Optional[str] = None,
    billable_labour_onsite: Optional[str] = None,
    billable_remote_labour: Optional[str] = None,
    billable_sundries: Optional[str] = None,
    # Notes
    additional_notes: Optional[str] = None,
    # Branding
    company_name: str = "Support Team",
    logo_path: Optional[str] = None,
) -> bytes:
    """Return a PDF job card as bytes."""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=20 * mm,
    )

    W = A4[0] - 36 * mm  # usable width

    # ── Styles ──────────────────────────────────────────────────────
    s_company = _style("company", fontSize=18, leading=22, textColor=BRAND_DARK,
                       fontName="Helvetica-Bold")
    s_jobcard_title = _style("jctitle", fontSize=11, leading=14, textColor=BRAND_MID,
                              fontName="Helvetica-Bold", spaceAfter=0)
    s_ticket_no = _style("tktno", fontSize=22, leading=26, textColor=BRAND_DARK,
                          fontName="Helvetica-Bold")
    s_meta = _style("meta", fontSize=8.5, leading=12, textColor=LABEL_GRAY)
    s_section_header = _style("sechdr", fontSize=9, leading=12, textColor=colors.white,
                               fontName="Helvetica-Bold")
    s_label = _style("lbl", fontSize=8.5, leading=12, textColor=LABEL_GRAY)
    s_value = _style("val", fontSize=9.5, leading=13, textColor=TEXT_BLACK,
                     fontName="Helvetica-Bold")
    s_value_normal = _style("valn", fontSize=9.5, leading=13, textColor=TEXT_BLACK)
    s_note = _style("note", fontSize=9, leading=13, textColor=TEXT_BLACK)
    s_footer = _style("footer", fontSize=7.5, leading=10, textColor=LABEL_GRAY,
                      alignment=TA_CENTER)
    s_sig_label = _style("siglbl", fontSize=8, leading=11, textColor=LABEL_GRAY,
                          alignment=TA_CENTER)

    story = []

    # ── Header row: logo + company + ticket number ───────────────────
    left_cells = []
    if logo_path and os.path.isfile(logo_path):
        try:
            img = Image(logo_path)
            img._restrictSize(48 * mm, 18 * mm)
            left_cells.append(img)
        except Exception:
            left_cells.append(Paragraph(company_name, s_company))
    else:
        left_cells.append(Paragraph(company_name, s_company))

    left_cells.append(Spacer(1, 2 * mm))
    left_cells.append(Paragraph("JOB CARD", s_jobcard_title))

    right_cells = [
        Paragraph(f"#{ticket_number}", s_ticket_no),
        Spacer(1, 1 * mm),
        Paragraph(f"Date: {closed_at.strftime('%d %B %Y')}", s_meta),
        Paragraph(f"Time: {closed_at.strftime('%H:%M')}", s_meta),
    ]

    header_table = Table(
        [[left_cells, right_cells]],
        colWidths=[W * 0.6, W * 0.4],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_MID, spaceAfter=4 * mm))

    # ── Job details banner ───────────────────────────────────────────
    def section_header(title: str):
        tbl = Table(
            [[Paragraph(title, s_section_header)]],
            colWidths=[W],
        )
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("ROUNDEDCORNERS", [3, 3, 3, 3]),
        ]))
        return tbl

    def info_row(label: str, value: str, alt: bool = False):
        bg = ROW_ALT if alt else colors.white
        row = Table(
            [[Paragraph(label, s_label), Paragraph(value or "—", s_value_normal)]],
            colWidths=[W * 0.38, W * 0.62],
        )
        row.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, BRAND_BORDER),
        ]))
        return row

    # Job summary
    story.append(section_header("  JOB SUMMARY"))
    story.append(info_row("Subject / Fault", subject, False))
    story.append(info_row("Ticket Number", f"#{ticket_number}", True))
    story.append(info_row("Priority", priority.title(), False))
    story.append(info_row("Opened", created_at.strftime("%d %b %Y  %H:%M"), True))
    story.append(info_row("Closed", closed_at.strftime("%d %b %Y  %H:%M"), False))
    story.append(info_row("Technician", technician_name, True))
    story.append(Spacer(1, 4 * mm))

    # ── Client details ───────────────────────────────────────────────
    story.append(section_header("  CLIENT DETAILS"))
    full_name = " ".join(filter(None, [client_name, client_surname])) or None
    story.append(info_row("Full Name", full_name, False))
    story.append(info_row("Phone Number", client_phone, True))
    story.append(info_row("Office Number", client_office_number, False))
    story.append(Spacer(1, 4 * mm))

    # ── Billable work ────────────────────────────────────────────────
    story.append(section_header("  BILLABLE WORK"))
    story.append(info_row("Traveling", billable_traveling, False))
    story.append(info_row("Labour Onsite", billable_labour_onsite, True))
    story.append(info_row("Remote Labour", billable_remote_labour, False))
    story.append(info_row("Sundries", billable_sundries, True))
    story.append(Spacer(1, 4 * mm))

    # ── Additional notes ─────────────────────────────────────────────
    story.append(section_header("  ADDITIONAL NOTES"))
    notes_text = additional_notes or "No additional notes."
    notes_tbl = Table(
        [[Paragraph(notes_text, s_note)]],
        colWidths=[W],
    )
    notes_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ROW_ALT),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, BRAND_BORDER),
    ]))
    story.append(notes_tbl)
    story.append(Spacer(1, 8 * mm))

    # ── Signature lines ──────────────────────────────────────────────
    sig_line = "_" * 32
    sig_data = [
        [
            Paragraph(sig_line, s_sig_label),
            Paragraph("", s_sig_label),
            Paragraph(sig_line, s_sig_label),
        ],
        [
            Paragraph("Client Signature", s_sig_label),
            Paragraph("", s_sig_label),
            Paragraph("Technician Signature", s_sig_label),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[W * 0.4, W * 0.2, W * 0.4])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 6 * mm))

    # ── Footer ───────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_BORDER, spaceAfter=3 * mm))
    story.append(Paragraph(
        f"{company_name}  ·  Job Card generated {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC",
        s_footer,
    ))

    doc.build(story)
    return buf.getvalue()
