"""
LexAI — Professional PDF Document Generator v4.0
Generates FBR-compliant tax documents and professional legal documents.
All imports are self-contained; no circular dependencies.
"""
import io
import re
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import Frame, PageTemplate
from reportlab.lib.validators import isColor

# ═══════════════════════════════════════════════════════════════
#  BRAND COLOURS
# ═══════════════════════════════════════════════════════════════
NAVY      = colors.HexColor("#0D1B2A")
NAVY_MID  = colors.HexColor("#152336")
GOLD      = colors.HexColor("#C9A84C")
GOLD_L    = colors.HexColor("#E3B55A")
PARCH     = colors.HexColor("#F9F3E3")
PARCH_D   = colors.HexColor("#F0EDE4")
OFF_WHITE = colors.HexColor("#FAFAF7")
GREY_LT   = colors.HexColor("#E0DDD4")
GREY_MID  = colors.HexColor("#8A9AAA")
GREY_TXT  = colors.HexColor("#5A6A7A")
DARK_TXT  = colors.HexColor("#1A1A2E")
RED_LT    = colors.HexColor("#FDECEA")
GREEN_LT  = colors.HexColor("#EAF3DE")
GREEN_DRK = colors.HexColor("#1D6A3A")
RED_DRK   = colors.HexColor("#8B1A1A")
BLUE_INF  = colors.HexColor("#E8F4FD")


# ═══════════════════════════════════════════════════════════════
#  INLINE TAX CALCULATION (no external import)
# ═══════════════════════════════════════════════════════════════
_FBR_SLABS = [
    {"min": 0,       "max": 600000,      "rate": 0.00, "fixed": 0},
    {"min": 600001,  "max": 1200000,     "rate": 0.05, "fixed": 0},
    {"min": 1200001, "max": 2400000,     "rate": 0.15, "fixed": 30000},
    {"min": 2400001, "max": 3600000,     "rate": 0.25, "fixed": 210000},
    {"min": 3600001, "max": 6000000,     "rate": 0.30, "fixed": 510000},
    {"min": 6000001, "max": float("inf"),"rate": 0.35, "fixed": 1230000},
]

def _calc_tax(income: float) -> dict:
    tax, slab_info = 0.0, None
    for s in _FBR_SLABS:
        if s["min"] <= income <= s["max"]:
            tax = s["fixed"] + max(0, income - s["min"]) * s["rate"]
            slab_info = s
            break
    eff = (tax / income * 100) if income > 0 else 0
    if slab_info:
        mx = slab_info["max"]
        desc = (f"PKR {slab_info['min']:,} – ∞" if mx == float("inf")
                else f"PKR {slab_info['min']:,} – {mx:,}")
        mrate = slab_info["rate"] * 100
    else:
        desc, mrate = "N/A", 0
    return {
        "annual_income": income,
        "tax_liability": round(tax, 2),
        "effective_rate": round(eff, 2),
        "marginal_rate": mrate,
        "slab_description": desc,
    }


# ═══════════════════════════════════════════════════════════════
#  STYLE FACTORY
# ═══════════════════════════════════════════════════════════════
def _styles():
    base = getSampleStyleSheet()
    return {
        "doc_title": ParagraphStyle(
            "doc_title", parent=base["Heading1"],
            fontSize=17, fontName="Helvetica-Bold",
            alignment=TA_CENTER, textColor=NAVY,
            spaceAfter=3, spaceBefore=0),
        "doc_sub": ParagraphStyle(
            "doc_sub", parent=base["Normal"],
            fontSize=9.5, alignment=TA_CENTER,
            textColor=GREY_TXT, spaceAfter=2),
        "section": ParagraphStyle(
            "section", parent=base["Normal"],
            fontSize=10, fontName="Helvetica-Bold",
            textColor=NAVY, spaceBefore=10, spaceAfter=3,
            backColor=PARCH,
            leftIndent=0, rightIndent=0,
            borderPad=5),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontSize=9.5, leading=14, textColor=DARK_TXT,
            alignment=TA_JUSTIFY),
        "body_c": ParagraphStyle(
            "body_c", parent=base["Normal"],
            fontSize=9.5, leading=14, textColor=DARK_TXT,
            alignment=TA_CENTER),
        "small": ParagraphStyle(
            "small", parent=base["Normal"],
            fontSize=8, textColor=GREY_TXT),
        "label": ParagraphStyle(
            "label", parent=base["Normal"],
            fontSize=8.5, fontName="Helvetica-Bold",
            textColor=GREY_TXT),
        "value": ParagraphStyle(
            "value", parent=base["Normal"],
            fontSize=9.5, textColor=DARK_TXT),
        "disclaimer": ParagraphStyle(
            "disclaimer", parent=base["Normal"],
            fontSize=7.5, textColor=GREY_MID,
            backColor=PARCH_D,
            borderPad=6, borderColor=GOLD,
            borderWidth=0.5, leftIndent=4, rightIndent=4,
            alignment=TA_JUSTIFY),
        "legal_title": ParagraphStyle(
            "legal_title", parent=base["Normal"],
            fontSize=16, fontName="Helvetica-Bold",
            alignment=TA_CENTER, textColor=NAVY,
            spaceBefore=6, spaceAfter=6),
        "legal_h2": ParagraphStyle(
            "legal_h2", parent=base["Normal"],
            fontSize=11, fontName="Helvetica-Bold",
            textColor=NAVY, spaceBefore=10, spaceAfter=4),
        "legal_body": ParagraphStyle(
            "legal_body", parent=base["Normal"],
            fontSize=10, leading=16, textColor=DARK_TXT,
            alignment=TA_JUSTIFY),
        "legal_clause": ParagraphStyle(
            "legal_clause", parent=base["Normal"],
            fontSize=10, leading=16, textColor=DARK_TXT,
            leftIndent=14, alignment=TA_JUSTIFY),
        "sig_label": ParagraphStyle(
            "sig_label", parent=base["Normal"],
            fontSize=9, fontName="Helvetica-Bold",
            textColor=GREY_TXT, alignment=TA_CENTER),
        "sig_line": ParagraphStyle(
            "sig_line", parent=base["Normal"],
            fontSize=10, textColor=DARK_TXT, alignment=TA_CENTER),
        "watermark": ParagraphStyle(
            "watermark", parent=base["Normal"],
            fontSize=9, textColor=GREY_TXT,
            alignment=TA_CENTER, fontName="Helvetica-Oblique"),
    }


# ═══════════════════════════════════════════════════════════════
#  REUSABLE BUILDING BLOCKS
# ═══════════════════════════════════════════════════════════════
def _header_bar(elements, heading_line: str, styles):
    """Dark navy top bar with gold text."""
    t = Table([[heading_line]], colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), NAVY),
        ("TEXTCOLOR",     (0,0), (-1,-1), GOLD),
        ("FONTNAME",      (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 10),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 11),
        ("BOTTOMPADDING", (0,0), (-1,-1), 11),
    ]))
    elements.append(t)


def _gen_stamp(elements, styles):
    """LexAI generation stamp."""
    stamp = (f"Generated by LexAI  |  "
             f"{datetime.now().strftime('%d %B %Y, %I:%M %p')}  |  "
             f"lexai.app")
    elements.append(Paragraph(stamp, styles["watermark"]))


def _divider(elements):
    elements.append(HRFlowable(
        width="100%", thickness=1.2,
        color=GOLD, spaceAfter=5 * mm, spaceBefore=2 * mm))


def _field_table(rows: list, styles, col_w=(62, 108)) -> Table:
    """Two-column label / value table."""
    data = [
        [Paragraph(lbl, styles["label"]),
         Paragraph(str(val) if val else "—", styles["value"])]
        for lbl, val in rows
    ]
    t = Table(data, colWidths=[w * mm for w in col_w])
    t.setStyle(TableStyle([
        ("GRID",           (0,0), (-1,-1), 0.3, GREY_LT),
        ("BACKGROUND",     (0,0), (0,-1),  OFF_WHITE),
        ("BACKGROUND",     (1,0), (1,-1),  colors.white),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t


def _sig_block(elements, styles, parties: list):
    """Signature block for one or more parties."""
    elements.append(Spacer(1, 8 * mm))
    sig_rows = [[] for _ in range(3)]
    for name_label in parties:
        sig_rows[0].append(Paragraph("__________________________", styles["sig_line"]))
        sig_rows[1].append(Paragraph(name_label, styles["sig_label"]))
        sig_rows[2].append(Paragraph(datetime.now().strftime("%d %B %Y"), styles["sig_label"]))
    col_w = [170 // len(parties) * mm] * len(parties)
    t = Table(sig_rows, colWidths=col_w)
    t.setStyle(TableStyle([
        ("ALIGN",   (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    elements.append(t)


def _section_heading(text: str, styles) -> Paragraph:
    return Paragraph(f"&nbsp;&nbsp;{text}", styles["section"])


# ═══════════════════════════════════════════════════════════════
#  TAX DOCUMENT 1 — NTN APPLICATION (Form 181)
# ═══════════════════════════════════════════════════════════════
def generate_ntn_pdf(data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=16*mm, bottomMargin=20*mm)
    S = _styles()
    E = []

    # ── Header ──────────────────────────────────────────────
    _header_bar(E, "FEDERAL BOARD OF REVENUE — ISLAMIC REPUBLIC OF PAKISTAN", S)
    E.append(Spacer(1, 5*mm))
    E.append(Paragraph("NTN APPLICATION FORM", S["doc_title"]))
    E.append(Paragraph("Form 181 — Section 181, Income Tax Ordinance 2001", S["doc_sub"]))
    _gen_stamp(E, S)
    _divider(E)

    p = data.get("personal", {})
    inc = data.get("income", {})
    tc  = _calc_tax(float(inc.get("annual", 0)))
    tds = float(inc.get("tds", 0))
    net = tc["tax_liability"] - tds

    # ── Part A ───────────────────────────────────────────────
    E.append(_section_heading("PART A — PERSONAL IDENTIFICATION", S))
    E.append(Spacer(1, 2*mm))
    E.append(_field_table([
        ("Full Name (as on CNIC)",  p.get("name", "")),
        ("CNIC / NIC Number",       _fmt_cnic(p.get("cnic", ""))),
        ("Date of Birth",           p.get("dob", "")),
        ("Father's / Husband's Name", p.get("father_name", "—")),
        ("Gender",                  p.get("gender", "—")),
        ("Marital Status",          p.get("marital_status", "—")),
        ("Nationality",             "Pakistani"),
        ("Residential Status",      _fmt_citizen(p.get("citizen", "resident"))),
    ], S))
    E.append(Spacer(1, 3*mm))

    # ── Part B ───────────────────────────────────────────────
    E.append(_section_heading("PART B — CONTACT & ADDRESS", S))
    E.append(Spacer(1, 2*mm))
    E.append(_field_table([
        ("Residential Address",   p.get("address", "")),
        ("City / District",       p.get("city", "—")),
        ("Province",              p.get("province", "—")),
        ("Mobile Number",         p.get("phone", "")),
        ("Email Address",         p.get("email", "")),
        ("NTN of Employer / AOP", p.get("employer_ntn", "—")),
    ], S))
    E.append(Spacer(1, 3*mm))

    # ── Part C ───────────────────────────────────────────────
    E.append(_section_heading("PART C — INCOME & EMPLOYMENT DETAILS", S))
    E.append(Spacer(1, 2*mm))
    E.append(_field_table([
        ("Employment Type",             _fmt_emp(data.get("emp_type", "salaried"))),
        ("Employer / Business Name",    inc.get("employer", "—")),
        ("Employer's Address",          inc.get("employer_address", "—")),
        ("Annual Gross Salary (PKR)",   f"PKR {float(inc.get('annual', 0)):,.0f}"),
        ("Bank Account IBAN",           inc.get("iban", "—")),
        ("Bank Name",                   inc.get("bank_name", "—")),
        ("Tax Deducted at Source (PKR)",f"PKR {tds:,.0f}"),
        ("Principal Source of Income",  _fmt_emp(data.get("emp_type", "salaried"))),
    ], S))
    E.append(Spacer(1, 3*mm))

    # ── Part D — Tax Computation ─────────────────────────────
    E.append(_section_heading("PART D — TAX COMPUTATION (FBR SCHEDULE 2024–25)", S))
    E.append(Spacer(1, 2*mm))

    tax_rows = [
        ["Description",             "Amount (PKR)"],
        ["Gross Taxable Income",    f"PKR {tc['annual_income']:,.0f}"],
        ["Applicable Tax Slab",     tc["slab_description"]],
        ["Marginal Rate (%)",       f"{tc['marginal_rate']:.0f}%"],
        ["Gross Tax Liability",     f"PKR {tc['tax_liability']:,.2f}"],
        ["Less: Tax Deducted at Source", f"PKR {tds:,.2f}"],
        ["Effective Rate",          f"{tc['effective_rate']:.2f}%"],
        ["NET TAX PAYABLE / (REFUNDABLE)",
         f"PKR {abs(net):,.2f}  {'[ PAYABLE ]' if net > 0 else '[ REFUNDABLE ]'}"],
    ]
    comp_t = Table(tax_rows, colWidths=[110*mm, 60*mm])
    comp_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  NAVY),
        ("TEXTCOLOR",     (0,0),  (-1,0),  GOLD),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("BACKGROUND",    (0,-1), (-1,-1), PARCH),
        ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0,-1), (-1,-1), GREEN_DRK if net <= 0 else RED_DRK),
        ("GRID",          (0,0),  (-1,-1), 0.3, GREY_LT),
        ("ALIGN",         (1,0),  (1,-1),  "RIGHT"),
        ("TOPPADDING",    (0,0),  (-1,-1), 6),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 6),
        ("LEFTPADDING",   (0,0),  (-1,-1), 8),
        ("FONTSIZE",      (0,0),  (-1,-1), 9.5),
        ("ROWBACKGROUNDS",(0,1),  (-1,-2), [colors.white, OFF_WHITE]),
    ]))
    E.append(comp_t)
    E.append(Spacer(1, 5*mm))

    # ── FBR Tax Slab Reference Table ─────────────────────────
    E.append(_section_heading("PART E — FBR TAX SLAB REFERENCE (Tax Year 2024–25)", S))
    E.append(Spacer(1, 2*mm))
    slab_rows = [["Income Range (PKR)", "Fixed Amount (PKR)", "Rate on Excess (%)"]]
    for s in _FBR_SLABS:
        rng = ("Above 6,000,000" if s["max"] == float("inf")
               else f"{s['min']:,} – {s['max']:,}")
        slab_rows.append([rng, f"{s['fixed']:,}", f"{s['rate']*100:.0f}%"])
    slab_t = Table(slab_rows, colWidths=[70*mm, 55*mm, 45*mm])
    slab_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  NAVY_MID),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("GRID",          (0,0),  (-1,-1), 0.3, GREY_LT),
        ("ALIGN",         (1,0),  (-1,-1), "RIGHT"),
        ("TOPPADDING",    (0,0),  (-1,-1), 5),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 5),
        ("LEFTPADDING",   (0,0),  (-1,-1), 8),
        ("FONTSIZE",      (0,0),  (-1,-1), 9),
        ("ROWBACKGROUNDS",(0,1),  (-1,-1), [colors.white, OFF_WHITE]),
    ]))
    E.append(slab_t)
    E.append(Spacer(1, 5*mm))

    # ── Declaration ──────────────────────────────────────────
    E.append(_section_heading("DECLARATION", S))
    E.append(Spacer(1, 3*mm))
    E.append(Paragraph(
        "I, the undersigned, do hereby solemnly declare that the information furnished in this "
        "application is true, complete, and correct to the best of my knowledge and belief, and "
        "that nothing has been concealed or withheld. I understand that any false or misleading "
        "statement may render me liable to prosecution under the Income Tax Ordinance, 2001 and "
        "other applicable laws of Pakistan.", S["body"]))
    E.append(Spacer(1, 2*mm))
    E.append(Paragraph(
        "I further undertake to notify the Commissioner Inland Revenue of any change in the "
        "particulars stated above within 30 days of such change.", S["body"]))

    _sig_block(E, S, [p.get("name", "Applicant") + "\n(Taxpayer)"])

    # ── Instructions Box ─────────────────────────────────────
    instr = Table([[Paragraph(
        "<b>HOW TO SUBMIT:</b>  1) Visit <b>https://iris.fbr.gov.pk</b>  "
        "2) Create account using this CNIC  3) Upload scanned copy of CNIC (front & back)  "
        "4) NTN issued within 2–3 working days via SMS/email  "
        "5) For assistance: FBR helpline 051-111-772-772",
        ParagraphStyle("instr", parent=_styles()["body"], fontSize=8.5,
                       textColor=DARK_TXT, leading=13))]], colWidths=[170*mm])
    instr.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), BLUE_INF),
        ("BOX",           (0,0), (-1,-1), 0.8, colors.HexColor("#4A90D9")),
        ("TOPPADDING",    (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 9),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
    ]))
    E.append(instr)
    E.append(Spacer(1, 4*mm))
    E.append(Paragraph(
        "DISCLAIMER: This document is generated by LexAI for informational/preparation purposes. "
        "All data is as provided by the applicant. Verify all entries before official FBR submission. "
        "LexAI does not guarantee NTN issuance. Submission is the sole responsibility of the applicant.",
        S["disclaimer"]))

    doc.build(E)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  TAX DOCUMENT 2 — INCOME TAX RETURN (ITR) SUMMARY
# ═══════════════════════════════════════════════════════════════
def generate_itr_pdf(data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=16*mm, bottomMargin=20*mm)
    S = _styles()
    E = []

    _header_bar(E, "FEDERAL BOARD OF REVENUE — ISLAMIC REPUBLIC OF PAKISTAN", S)
    E.append(Spacer(1, 5*mm))
    E.append(Paragraph("INCOME TAX RETURN — SUMMARY", S["doc_title"]))
    E.append(Paragraph("Tax Year 2024–25 (01 July 2024 – 30 June 2025)", S["doc_sub"]))
    E.append(Paragraph("Filed under Section 114/115, Income Tax Ordinance 2001", S["doc_sub"]))
    _gen_stamp(E, S)
    _divider(E)

    p   = data.get("personal", {})
    inc = data.get("income", {})
    ast = data.get("assets", {})
    tc  = _calc_tax(float(inc.get("annual", 0)))
    tds = float(inc.get("tds", 0))
    net = tc["tax_liability"] - tds

    # ── Taxpayer Info ────────────────────────────────────────
    E.append(_section_heading("SECTION 1 — TAXPAYER IDENTIFICATION", S))
    E.append(Spacer(1, 2*mm))
    E.append(_field_table([
        ("Taxpayer Name",           p.get("name", "")),
        ("CNIC / NTN",              _fmt_cnic(p.get("cnic", ""))),
        ("Tax Year",                "2024–25"),
        ("Filing Type",             "Original"),
        ("Residential Status",      _fmt_citizen(p.get("citizen", "resident"))),
        ("Address",                 p.get("address", "")),
        ("Mobile",                  p.get("phone", "")),
        ("Email",                   p.get("email", "")),
        ("Filing Due Date",         "30 September 2025"),
    ], S))
    E.append(Spacer(1, 4*mm))

    # ── Income Schedule ──────────────────────────────────────
    E.append(_section_heading("SECTION 2 — INCOME SCHEDULE (SCHEDULE A)", S))
    E.append(Spacer(1, 2*mm))
    annual = float(inc.get("annual", 0))
    emp    = data.get("emp_type", "salaried")
    src_label = {
        "salaried": "Salary & Allowances from: " + (inc.get("employer") or "Employer"),
        "business": "Business / Professional Income",
        "overseas": "Foreign Source Income / Overseas Remittances",
    }.get(emp, "Income")

    inc_rows = [
        ["Income Source", "Code", "Amount (PKR)"],
        [src_label, "A-01", f"{annual:,.0f}"],
        ["Income from Property (if any)", "A-02", "0"],
        ["Capital Gains (if any)",        "A-03", "0"],
        ["Other Sources",                 "A-04", "0"],
        ["GROSS TOTAL INCOME",            "",     f"PKR {annual:,.0f}"],
        ["Less: Admissible Deductions",   "",     "—"],
        ["TAXABLE INCOME",                "",     f"PKR {annual:,.0f}"],
    ]
    inc_t = Table(inc_rows, colWidths=[90*mm, 25*mm, 55*mm])
    inc_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  NAVY),
        ("TEXTCOLOR",     (0,0),  (-1,0),  GOLD),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,-3), (-1,-1), "Helvetica-Bold"),
        ("BACKGROUND",    (0,-1), (-1,-1), PARCH),
        ("GRID",          (0,0),  (-1,-1), 0.3, GREY_LT),
        ("ALIGN",         (2,0),  (2,-1),  "RIGHT"),
        ("ALIGN",         (1,0),  (1,-1),  "CENTER"),
        ("TOPPADDING",    (0,0),  (-1,-1), 6),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 6),
        ("LEFTPADDING",   (0,0),  (-1,-1), 8),
        ("FONTSIZE",      (0,0),  (-1,-1), 9.5),
        ("ROWBACKGROUNDS",(0,1),  (-1,-4), [colors.white, OFF_WHITE]),
    ]))
    E.append(inc_t)
    E.append(Spacer(1, 4*mm))

    # ── Tax Computation ──────────────────────────────────────
    E.append(_section_heading("SECTION 3 — TAX COMPUTATION (SCHEDULE B)", S))
    E.append(Spacer(1, 2*mm))

    tax_rows = [
        ["Description",                    "Rate / Note",              "Amount (PKR)"],
        ["Taxable Income",                 tc["slab_description"],     f"{annual:,.0f}"],
        ["Tax on Income (Slab Rate)",      f"{tc['marginal_rate']:.0f}% marginal",
                                                                       f"{tc['tax_liability']:,.2f}"],
        ["Tax Credits / Reductions",       "Sec 60B/61/62 etc.",       "0.00"],
        ["GROSS TAX LIABILITY",            "",                         f"{tc['tax_liability']:,.2f}"],
        ["Less: Tax Deducted at Source",   f"(employer certificate)",  f"({tds:,.2f})"],
        ["Less: Advance Tax Paid",         "if any",                   "0.00"],
        ["NET TAX PAYABLE / (REFUNDABLE)", f"Effective {tc['effective_rate']:.2f}%",
                                           f"PKR {abs(net):,.2f}  {'PAYABLE' if net>0 else 'REFUNDABLE'}"],
    ]
    tax_t = Table(tax_rows, colWidths=[80*mm, 40*mm, 50*mm])
    tax_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  NAVY),
        ("TEXTCOLOR",     (0,0),  (-1,0),  GOLD),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("BACKGROUND",    (0,-1), (-1,-1),
         GREEN_LT if net <= 0 else RED_LT),
        ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0,-1), (-1,-1),
         GREEN_DRK if net <= 0 else RED_DRK),
        ("GRID",          (0,0),  (-1,-1), 0.3, GREY_LT),
        ("ALIGN",         (2,0),  (2,-1),  "RIGHT"),
        ("ALIGN",         (1,0),  (1,-1),  "CENTER"),
        ("TOPPADDING",    (0,0),  (-1,-1), 6),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 6),
        ("LEFTPADDING",   (0,0),  (-1,-1), 8),
        ("FONTSIZE",      (0,0),  (-1,-1), 9.5),
        ("ROWBACKGROUNDS",(0,1),  (-1,-2), [colors.white, OFF_WHITE]),
    ]))
    E.append(tax_t)
    E.append(Spacer(1, 4*mm))

    # ── Withholding Tax Transactions ─────────────────────────
    E.append(_section_heading("SECTION 4 — WITHHOLDING TAX SUMMARY (SCHEDULE C)", S))
    E.append(Spacer(1, 2*mm))
    wht_rows = [
        ["Transaction",              "Section", "Amount Subjected (PKR)", "Tax Withheld (PKR)"],
        ["Salary (employer)",        "149",     f"{annual:,.0f}",         f"{tds:,.2f}"],
        ["Bank profit (if any)",     "151",     "—",                      "—"],
        ["Dividend (if any)",        "150",     "—",                      "—"],
        ["Property (if any)",        "236C",    "—",                      "—"],
        ["TOTAL WITHHOLDING TAX",    "",        "",                       f"PKR {tds:,.2f}"],
    ]
    wht_t = Table(wht_rows, colWidths=[60*mm, 22*mm, 50*mm, 38*mm])
    wht_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  NAVY_MID),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
        ("BACKGROUND",    (0,-1), (-1,-1), PARCH),
        ("GRID",          (0,0),  (-1,-1), 0.3, GREY_LT),
        ("ALIGN",         (2,0),  (-1,-1), "RIGHT"),
        ("ALIGN",         (1,0),  (1,-1),  "CENTER"),
        ("TOPPADDING",    (0,0),  (-1,-1), 5),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 5),
        ("LEFTPADDING",   (0,0),  (-1,-1), 8),
        ("FONTSIZE",      (0,0),  (-1,-1), 9),
        ("ROWBACKGROUNDS",(0,1),  (-1,-2), [colors.white, OFF_WHITE]),
    ]))
    E.append(wht_t)
    E.append(Spacer(1, 4*mm))

    # ── Tax Saving Strategies ────────────────────────────────
    E.append(_section_heading("SECTION 5 — AVAILABLE TAX CREDITS & DEDUCTIONS (ITO 2001)", S))
    E.append(Spacer(1, 2*mm))
    ded_rows = [
        ["Section", "Description",                          "Limit",                "Your Saving (Est.)"],
        ["60B",    "Pension Fund Contribution",             "20% of income",        f"PKR {min(annual*0.20, 1000000)*tc['marginal_rate']/100:,.0f}"],
        ["60C",    "Voluntary Pension Scheme",              "20% of income",        "Included in 60B"],
        ["60D",    "Health Insurance Premium",              "PKR 150,000",          f"PKR {min(150000, annual*0.05)*tc['marginal_rate']/100:,.0f}"],
        ["61",     "Charitable Donations (approved NGOs)",  "30% of taxable income","Variable"],
        ["62",     "Investment in Listed Company Shares",   "PKR 2,000,000",        f"PKR {min(2000000, annual*0.15)*tc['marginal_rate']/100:,.0f}"],
        ["65D",    "Investment in New Manufacturing Plant", "100% of investment",   "Variable"],
        ["60",     "Zakat (deductible from income)",        "Actual amount paid",   "Variable"],
    ]
    ded_t = Table(ded_rows, colWidths=[17*mm, 62*mm, 48*mm, 43*mm])
    ded_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  NAVY_MID),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("GRID",          (0,0),  (-1,-1), 0.3, GREY_LT),
        ("TOPPADDING",    (0,0),  (-1,-1), 5),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 5),
        ("LEFTPADDING",   (0,0),  (-1,-1), 7),
        ("FONTSIZE",      (0,0),  (-1,-1), 8.5),
        ("ROWBACKGROUNDS",(0,1),  (-1,-1), [colors.white, OFF_WHITE]),
        ("ALIGN",         (3,0),  (3,-1),  "RIGHT"),
    ]))
    E.append(ded_t)
    E.append(Spacer(1, 4*mm))

    # ── Verification ─────────────────────────────────────────
    E.append(_section_heading("VERIFICATION", S))
    E.append(Spacer(1, 3*mm))
    E.append(Paragraph(
        "I, the undersigned, do hereby declare that the information furnished in this return is "
        "to the best of my knowledge and belief, true, correct and complete in accordance with "
        "the Income Tax Ordinance 2001 and the rules made thereunder.", S["body"]))

    _sig_block(E, S, [p.get("name", "Taxpayer") + "\n(Taxpayer / Authorised Representative)"])

    E.append(Paragraph(
        "FILE ONLINE: https://iris.fbr.gov.pk  |  DUE DATE: 30 September 2025  |  "
        "HELPLINE: 051-111-772-772  |  Generated by LexAI",
        S["disclaimer"]))

    doc.build(E)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  TAX DOCUMENT 3 — WEALTH STATEMENT (WWS)
# ═══════════════════════════════════════════════════════════════
def generate_wealth_pdf(data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=16*mm, bottomMargin=20*mm)
    S = _styles()
    E = []

    _header_bar(E, "FEDERAL BOARD OF REVENUE — ISLAMIC REPUBLIC OF PAKISTAN", S)
    E.append(Spacer(1, 5*mm))
    E.append(Paragraph("STATEMENT OF ASSETS & LIABILITIES (WEALTH STATEMENT)", S["doc_title"]))
    E.append(Paragraph("Tax Year 2024–25  |  Form WWS  |  Section 116, Income Tax Ordinance 2001", S["doc_sub"]))
    _gen_stamp(E, S)
    _divider(E)

    p   = data.get("personal", {})
    inc = data.get("income", {})
    ast = data.get("assets", {})
    tc  = _calc_tax(float(inc.get("annual", 0)))

    # ── Taxpayer ID ──────────────────────────────────────────
    E.append(_section_heading("PART A — TAXPAYER IDENTIFICATION", S))
    E.append(Spacer(1, 2*mm))
    E.append(_field_table([
        ("Taxpayer Name",       p.get("name", "")),
        ("CNIC",                _fmt_cnic(p.get("cnic", ""))),
        ("Residential Status",  _fmt_citizen(p.get("citizen", "resident"))),
        ("Address",             p.get("address", "")),
        ("Tax Year",            "2024–25"),
        ("Statement Date",      "30 June 2025"),
        ("Annual Income (PKR)", f"PKR {float(inc.get('annual', 0)):,.0f}"),
        ("Tax Liability (PKR)", f"PKR {tc['tax_liability']:,.0f}"),
    ], S))
    E.append(Spacer(1, 4*mm))

    # ── Assets ───────────────────────────────────────────────
    bank  = float(ast.get("bank", 0))
    inv   = float(ast.get("inv", 0))
    prop  = float(ast.get("prop", 0))
    veh   = float(ast.get("veh", 0))
    other = float(ast.get("other_assets", 0))
    total_assets = bank + inv + prop + veh + other

    E.append(_section_heading("PART B — SCHEDULE OF ASSETS (as at 30 June 2025)", S))
    E.append(Spacer(1, 2*mm))
    ast_rows = [
        ["Code", "Asset Description",            "Location / Details",               "Value (PKR)"],
        ["B-01", "Cash in Hand",                  "—",                               "—"],
        ["B-02", "Bank Balances (all accounts)",  "As on 30 June 2025",              f"{bank:,.0f}"],
        ["B-03", "Investments / Mutual Funds",    "Listed & unlisted securities",    f"{inv:,.0f}"],
        ["B-04", "Immovable Property",            ast.get("propAddr", "—"),          f"{prop:,.0f}"],
        ["B-05", "Motor Vehicle(s)",              ast.get("vehDesc", "—"),           f"{veh:,.0f}"],
        ["B-06", "Other Assets (jewellery etc.)", "—",                               f"{other:,.0f}"],
        ["",     "TOTAL ASSETS",                  "",                                f"PKR {total_assets:,.0f}"],
    ]
    ast_t = Table(ast_rows, colWidths=[15*mm, 60*mm, 55*mm, 40*mm])
    ast_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  NAVY),
        ("TEXTCOLOR",     (0,0),  (-1,0),  GOLD),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
        ("BACKGROUND",    (0,-1), (-1,-1), PARCH),
        ("GRID",          (0,0),  (-1,-1), 0.3, GREY_LT),
        ("ALIGN",         (0,0),  (0,-1),  "CENTER"),
        ("ALIGN",         (3,0),  (3,-1),  "RIGHT"),
        ("TOPPADDING",    (0,0),  (-1,-1), 6),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 6),
        ("LEFTPADDING",   (0,0),  (-1,-1), 8),
        ("FONTSIZE",      (0,0),  (-1,-1), 9.5),
        ("ROWBACKGROUNDS",(0,1),  (-1,-2), [colors.white, OFF_WHITE]),
    ]))
    E.append(ast_t)
    E.append(Spacer(1, 4*mm))

    # ── Liabilities ──────────────────────────────────────────
    loan   = float(ast.get("loan", 0))
    other_l= float(ast.get("otherL", 0))
    total_l= loan + other_l
    net_w  = total_assets - total_l

    E.append(_section_heading("PART C — SCHEDULE OF LIABILITIES (as at 30 June 2025)", S))
    E.append(Spacer(1, 2*mm))
    lib_rows = [
        ["Code", "Liability Description",       "Creditor / Note",      "Amount (PKR)"],
        ["C-01", "Bank Loan / Mortgage",         "As per loan statement",f"{loan:,.0f}"],
        ["C-02", "Other Liabilities",            "—",                   f"{other_l:,.0f}"],
        ["",     "TOTAL LIABILITIES",            "",                    f"PKR {total_l:,.0f}"],
    ]
    lib_t = Table(lib_rows, colWidths=[15*mm, 60*mm, 55*mm, 40*mm])
    lib_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  NAVY_MID),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
        ("BACKGROUND",    (0,-1), (-1,-1), RED_LT),
        ("GRID",          (0,0),  (-1,-1), 0.3, GREY_LT),
        ("ALIGN",         (0,0),  (0,-1),  "CENTER"),
        ("ALIGN",         (3,0),  (3,-1),  "RIGHT"),
        ("TOPPADDING",    (0,0),  (-1,-1), 6),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 6),
        ("LEFTPADDING",   (0,0),  (-1,-1), 8),
        ("FONTSIZE",      (0,0),  (-1,-1), 9.5),
        ("ROWBACKGROUNDS",(0,1),  (-1,-2), [colors.white, OFF_WHITE]),
    ]))
    E.append(lib_t)
    E.append(Spacer(1, 4*mm))

    # ── Net Worth Box ────────────────────────────────────────
    nw_bg   = GREEN_LT if net_w >= 0 else RED_LT
    nw_text = GREEN_DRK if net_w >= 0 else RED_DRK
    nw_t = Table([
        ["TOTAL ASSETS",      f"PKR {total_assets:,.0f}"],
        ["TOTAL LIABILITIES", f"PKR {total_l:,.0f}"],
        ["NET WORTH",         f"PKR {net_w:,.0f}"],
    ], colWidths=[110*mm, 60*mm])
    nw_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,-2), PARCH),
        ("BACKGROUND",    (0,-1), (-1,-1), nw_bg),
        ("TEXTCOLOR",     (0,-1), (-1,-1), nw_text),
        ("FONTNAME",      (0,0),  (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,-1), (-1,-1), 12),
        ("FONTSIZE",      (0,0),  (-1,-2), 10),
        ("ALIGN",         (1,0),  (1,-1),  "RIGHT"),
        ("TOPPADDING",    (0,0),  (-1,-1), 8),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 8),
        ("LEFTPADDING",   (0,0),  (-1,-1), 10),
        ("BOX",           (0,0),  (-1,-1), 1.5, GOLD),
        ("GRID",          (0,0),  (-1,-1), 0.3, GREY_LT),
    ]))
    E.append(nw_t)
    E.append(Spacer(1, 4*mm))

    # ── Part D: Reconciliation ────────────────────────────────
    E.append(_section_heading("PART D — RECONCILIATION OF NET WORTH", S))
    E.append(Spacer(1, 2*mm))
    annual_inc = float(inc.get("annual", 0))
    E.append(_field_table([
        ("Opening Net Worth (1 July 2024)",         "As per prior year wealth statement"),
        ("Add: Taxable Income for 2024–25",         f"PKR {annual_inc:,.0f}"),
        ("Add: Exempt Income / Gifts Received",     "—"),
        ("Less: Tax Paid",                          f"PKR {tc['tax_liability']:,.0f}"),
        ("Less: Household Expenditure (Estimate)",  "—"),
        ("Closing Net Worth (30 June 2025)",        f"PKR {net_w:,.0f}"),
        ("Increase / (Decrease) in Net Worth",      f"PKR {net_w - 0:,.0f}"),
    ], S, col_w=(75, 95)))
    E.append(Spacer(1, 5*mm))

    # ── Declaration ──────────────────────────────────────────
    E.append(_section_heading("DECLARATION", S))
    E.append(Spacer(1, 3*mm))
    E.append(Paragraph(
        "I hereby solemnly declare that the particulars given above are true, complete, and correct "
        "and that nothing has been concealed or withheld. All assets are correctly valued as at "
        "30 June 2025. I am aware that providing false information in a Wealth Statement is an "
        "offence punishable under Section 192A of the Income Tax Ordinance, 2001.", S["body"]))

    _sig_block(E, S, [p.get("name", "Taxpayer") + "\n(Taxpayer)"])

    E.append(Paragraph(
        "SUBMIT WITH TAX RETURN at: https://iris.fbr.gov.pk  |  "
        "Mandatory for persons with annual income above PKR 1,000,000  |  "
        "HELPLINE: 051-111-772-772  |  Generated by LexAI. "
        "All figures as declared by the taxpayer. LexAI bears no responsibility for accuracy.",
        S["disclaimer"]))

    doc.build(E)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  LEGAL DOCUMENT PDFs — Universal Renderer
# ═══════════════════════════════════════════════════════════════
def generate_legal_document_pdf(doc_type: str, content: str,
                                 jurisdiction: str, party_data: dict = None) -> bytes:
    """
    Render any AI-generated legal document as a formatted, stamp-paper-style PDF.
    `content` is the markdown text from the LLM.
    `party_data` can contain: party1_name, party2_name, place, etc.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=22*mm, leftMargin=22*mm,
                            topMargin=18*mm, bottomMargin=22*mm)
    S = _styles()
    E = []

    # ── Document Header ──────────────────────────────────────
    jur_upper = jurisdiction.upper() if jurisdiction else "PAKISTAN"
    _header_bar(E, f"LEGAL DOCUMENT — {jur_upper}", S)
    E.append(Spacer(1, 5*mm))
    E.append(Paragraph(doc_type.upper(), S["legal_title"]))
    E.append(Paragraph(f"Jurisdiction: {jurisdiction}", S["doc_sub"]))
    _gen_stamp(E, S)
    _divider(E)

    # ── Stamp Duty Notice ────────────────────────────────────
    stamp_note = _stamp_duty_note(doc_type, jurisdiction)
    if stamp_note:
        sn = Table([[Paragraph(stamp_note, ParagraphStyle(
            "sn", parent=S["body"], fontSize=9, textColor=DARK_TXT,
            backColor=colors.HexColor("#FFF8E1")))]], colWidths=[166*mm])
        sn.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#FFF8E1")),
            ("BOX",           (0,0), (-1,-1), 1, colors.HexColor("#E6B800")),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ]))
        E.append(sn)
        E.append(Spacer(1, 4*mm))

    # ── Parse and render content ─────────────────────────────
    lines = content.split("\n")
    for line in lines:
        line = line.rstrip()
        if not line:
            E.append(Spacer(1, 3*mm))
            continue

        # Bold section headings like **HEADING** or # Heading
        if re.match(r"^\*\*[A-Z\s\-\/&,0-9\.]+\*\*$", line.strip()):
            heading = line.strip().strip("*")
            E.append(Spacer(1, 2*mm))
            E.append(_section_heading(heading, S))
            E.append(Spacer(1, 1*mm))
        elif re.match(r"^#{1,3}\s+", line):
            heading = re.sub(r"^#+\s+", "", line)
            E.append(Spacer(1, 2*mm))
            E.append(_section_heading(heading, S))
            E.append(Spacer(1, 1*mm))
        elif re.match(r"^\d+\.\s", line) or re.match(r"^[a-z]\)\s", line):
            # Numbered / lettered clause
            txt = _md_inline(line)
            E.append(Paragraph(txt, S["legal_clause"]))
        elif re.match(r"^[-•]\s", line):
            txt = _md_inline(line[2:])
            E.append(Paragraph("•  " + txt, S["legal_clause"]))
        else:
            txt = _md_inline(line)
            E.append(Paragraph(txt, S["legal_body"]))

    E.append(Spacer(1, 10*mm))

    # ── Signature Block ──────────────────────────────────────
    parties = _get_parties(doc_type, party_data)
    _sig_block(E, S, parties)

    E.append(Spacer(1, 5*mm))

    # ── Witness Block ────────────────────────────────────────
    if _needs_witnesses(doc_type):
        E.append(Paragraph("WITNESSES:", S["legal_h2"]))
        witness_rows = [[
            Paragraph("1.  ________________________\n"
                      "    Name: ____________________\n"
                      "    CNIC: ____________________", S["legal_body"]),
            Paragraph("2.  ________________________\n"
                      "    Name: ____________________\n"
                      "    CNIC: ____________________", S["legal_body"]),
        ]]
        wt = Table(witness_rows, colWidths=[83*mm, 83*mm])
        wt.setStyle(TableStyle([
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ]))
        E.append(wt)

    E.append(Spacer(1, 6*mm))
    E.append(Paragraph(
        "DISCLAIMER: This document is AI-generated by LexAI for informational and drafting "
        "assistance purposes only. It must be reviewed by a qualified attorney licensed in "
        f"{jurisdiction} before execution. LexAI does not provide legal advice. Ensure proper "
        "stamp duty is affixed and the document is registered with the relevant authority where "
        "required under applicable law.",
        S["disclaimer"]))

    doc.build(E)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  AFFIDAVIT — Dedicated high-quality generator
# ═══════════════════════════════════════════════════════════════
def generate_affidavit_pdf(data: dict) -> bytes:
    """
    Structured affidavit compliant with Pakistan Qanun-e-Shahadat Order 1984
    and Oaths Act 1873.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=25*mm, leftMargin=25*mm,
                            topMargin=18*mm, bottomMargin=22*mm)
    S = _styles()
    E = []
    p = data.get("personal", {})
    content = data.get("content", "")
    jurisdiction = data.get("jurisdiction", "Pakistan")

    _header_bar(E, f"AFFIDAVIT — {jurisdiction.upper()}", S)
    E.append(Spacer(1, 5*mm))
    E.append(Paragraph("AFFIDAVIT", S["legal_title"]))
    E.append(Paragraph(
        "Sworn under Oaths Act 1873 | Qanun-e-Shahadat Order 1984 (Art. 3 & 4)",
        S["doc_sub"]))
    _gen_stamp(E, S)
    _divider(E)

    # Stamp note
    sn = Table([[Paragraph(
        "⚠  STAMP PAPER REQUIREMENT: This Affidavit must be typed / printed on "
        "non-judicial stamp paper of appropriate value (PKR 100 – PKR 500 depending on purpose). "
        "It must be sworn before a Judicial Magistrate, Oath Commissioner, or Notary Public.",
        ParagraphStyle("sn2", parent=S["body"], fontSize=9, textColor=DARK_TXT)
    )]], colWidths=[160*mm])
    sn.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#FFF3CD")),
        ("BOX",           (0,0), (-1,-1), 1, GOLD),
        ("TOPPADDING",    (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 9),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
    ]))
    E.append(sn)
    E.append(Spacer(1, 5*mm))

    # Preamble
    name    = p.get("name", "[DEPONENT NAME]")
    cnic    = _fmt_cnic(p.get("cnic", "[CNIC]"))
    addr    = p.get("address", "[ADDRESS]")
    father  = p.get("father_name", "[FATHER/HUSBAND NAME]")
    occ     = p.get("occupation", "[OCCUPATION]")

    E.append(Paragraph(
        f"I, <b>{name}</b>, son/daughter/wife of <b>{father}</b>, "
        f"CNIC No. <b>{cnic}</b>, occupation <b>{occ}</b>, "
        f"residing at <b>{addr}</b>, do hereby solemnly affirm and declare as under:",
        S["legal_body"]))
    E.append(Spacer(1, 5*mm))

    # Body paragraphs
    if content:
        for i, line in enumerate(content.strip().split("\n"), 1):
            line = line.strip()
            if not line:
                E.append(Spacer(1, 2*mm))
                continue
            E.append(Paragraph(f"{i}.  {_md_inline(line)}", S["legal_clause"]))
            E.append(Spacer(1, 2*mm))
    else:
        E.append(Paragraph("1.  That [STATE YOUR FACTS HERE].", S["legal_clause"]))
        E.append(Spacer(1, 2*mm))
        E.append(Paragraph("2.  That the above facts are within my personal knowledge and "
                           "I am competent to depose thereto.", S["legal_clause"]))

    E.append(Spacer(1, 5*mm))
    E.append(Paragraph(
        "That the contents of this Affidavit are true and correct to the best of my knowledge "
        "and belief. Nothing has been concealed or misstated therein.", S["legal_body"]))

    E.append(Spacer(1, 8*mm))
    _sig_block(E, S, [name + "\n(Deponent)"])
    E.append(Spacer(1, 8*mm))

    # Attestation box
    att = Table([[Paragraph(
        "ATTESTATION\n\n"
        "Sworn before me on this _______ day of _______________, 20____\n\n"
        "_______________________________\n"
        "Signature & Seal of Oath Commissioner / Judicial Magistrate / Notary Public\n"
        "Name: _________________________\n"
        "Designation: __________________",
        ParagraphStyle("att", parent=S["legal_body"], fontSize=10, leading=18)
    )]], colWidths=[160*mm])
    att.setStyle(TableStyle([
        ("BOX",           (0,0), (-1,-1), 1.5, NAVY),
        ("BACKGROUND",    (0,0), (-1,-1), OFF_WHITE),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("LEFTPADDING",   (0,0), (-1,-1), 14),
    ]))
    E.append(att)
    E.append(Spacer(1, 5*mm))
    E.append(Paragraph(
        "DISCLAIMER: AI-generated by LexAI. Must be verified by a qualified attorney. "
        "Affiant is responsible for truthfulness of content. False affidavit is an offence "
        "under Section 182 / 193 / 199 PPC.", S["disclaimer"]))

    doc.build(E)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  WAKALATNAAMA (Power of Attorney) — Dedicated generator
# ═══════════════════════════════════════════════════════════════
def generate_wakalatnaama_pdf(data: dict) -> bytes:
    """
    Wakalatnaama / Power of Attorney under Powers of Attorney Act 1882 (Pakistan).
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=22*mm, leftMargin=22*mm,
                            topMargin=18*mm, bottomMargin=22*mm)
    S = _styles()
    E = []

    p  = data.get("personal", {})
    ak = data.get("attorney", {})
    jur = data.get("jurisdiction", "Pakistan")
    scope = data.get("scope", "General")
    purpose = data.get("purpose", "general legal matters")

    _header_bar(E, f"WAKALATNAAMA / POWER OF ATTORNEY — {jur.upper()}", S)
    E.append(Spacer(1, 5*mm))
    E.append(Paragraph("WAKALATNAAMA / POWER OF ATTORNEY", S["legal_title"]))
    E.append(Paragraph(
        f"Under Powers of Attorney Act 1882 & Article 129, Qanun-e-Shahadat Order 1984",
        S["doc_sub"]))
    E.append(Paragraph(f"Type: {scope} Power of Attorney", S["doc_sub"]))
    _gen_stamp(E, S)
    _divider(E)

    # Stamp note
    sn = Table([[Paragraph(
        "⚠  STAMP DUTY: A General Power of Attorney requires non-judicial stamp paper of "
        "PKR 500–1,000 (Punjab) or as prescribed by provincial stamp schedules. "
        "A Special / Limited POA requires stamp paper of PKR 100–500. "
        "Must be attested by a Notary Public or Oath Commissioner for use in courts.",
        ParagraphStyle("sn3", parent=S["body"], fontSize=9, textColor=DARK_TXT))
    ]], colWidths=[166*mm])
    sn.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#FFF3CD")),
        ("BOX",           (0,0), (-1,-1), 1, GOLD),
        ("TOPPADDING",    (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 9),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
    ]))
    E.append(sn)
    E.append(Spacer(1, 5*mm))

    princ_name = p.get("name", "[PRINCIPAL NAME]")
    princ_cnic = _fmt_cnic(p.get("cnic", "[CNIC]"))
    princ_addr = p.get("address", "[ADDRESS]")
    princ_father = p.get("father_name", "[FATHER/HUSBAND]")

    atty_name  = ak.get("name", "[ATTORNEY NAME]")
    atty_cnic  = _fmt_cnic(ak.get("cnic", "[CNIC]"))
    atty_addr  = ak.get("address", "[ADDRESS]")
    atty_rel   = ak.get("relationship", "duly appointed")

    # Parties
    E.append(_section_heading("PARTIES", S))
    E.append(Spacer(1, 2*mm))
    E.append(_field_table([
        ("PRINCIPAL (Moakkil)",   f"{princ_name}"),
        ("S/o, D/o, W/o",        princ_father),
        ("CNIC (Principal)",      princ_cnic),
        ("Address (Principal)",   princ_addr),
        ("ATTORNEY (Wakeel)",     atty_name),
        ("Relationship",          atty_rel),
        ("CNIC (Attorney)",       atty_cnic),
        ("Address (Attorney)",    atty_addr),
    ], S, col_w=(65, 105)))
    E.append(Spacer(1, 4*mm))

    # Body
    E.append(_section_heading("AUTHORITY GRANTED", S))
    E.append(Spacer(1, 3*mm))
    E.append(Paragraph(
        f"I, <b>{princ_name}</b>, son/daughter/wife of <b>{princ_father}</b>, "
        f"CNIC <b>{princ_cnic}</b>, resident of <b>{princ_addr}</b>, "
        f"(hereinafter referred to as the \"Principal\"), do hereby appoint and constitute "
        f"<b>{atty_name}</b>, CNIC <b>{atty_cnic}</b>, resident of <b>{atty_addr}</b>, "
        f"(hereinafter referred to as the \"Attorney\" or \"Wakeel\") as my lawful attorney "
        f"to act on my behalf in connection with the following matters:",
        S["legal_body"]))
    E.append(Spacer(1, 4*mm))

    # Powers
    powers = data.get("powers", [
        "To appear before all Courts, Tribunals, quasi-judicial bodies, and government offices in Pakistan.",
        "To sign, execute, and deliver all pleadings, petitions, applications, affidavits, and legal documents.",
        "To engage and instruct advocates, counsels, and legal representatives on my behalf.",
        "To compromise, settle, refer to arbitration, or withdraw any legal proceedings.",
        "To collect, receive, and give receipts for any money, documents, or property on my behalf.",
        "To execute Sale Deed, Transfer Deed, Gift Deed or any other deed as specifically directed.",
        f"To do all acts pertaining to: <b>{purpose}</b>.",
    ])
    for i, pw in enumerate(powers, 1):
        E.append(Paragraph(f"{i}.  {pw}", S["legal_clause"]))
        E.append(Spacer(1, 1.5*mm))

    E.append(Spacer(1, 4*mm))
    E.append(Paragraph(
        "The Principal hereby ratifies and confirms all acts, deeds, and things lawfully done "
        "by the said Attorney by virtue of this Wakalatnaama as if the same were done by the "
        "Principal personally. This Power of Attorney shall remain valid until expressly revoked "
        "in writing by the Principal.", S["legal_body"]))

    E.append(Spacer(1, 4*mm))
    if scope.lower() == "special":
        E.append(Paragraph(
            "<b>LIMITATION:</b> This is a <b>Special / Limited Power of Attorney</b> restricted "
            f"to the specific purpose(s) described above only.", S["legal_body"]))

    _sig_block(E, S, [
        princ_name + "\n(Principal / Moakkil)",
        atty_name  + "\n(Attorney / Wakeel)"])

    E.append(Spacer(1, 5*mm))

    # Witnesses
    E.append(Paragraph("WITNESSES:", S["legal_h2"]))
    wt = Table([[
        Paragraph("1. Signature: ______________\n"
                  "   Name: ___________________\n"
                  "   CNIC: ___________________\n"
                  "   Address: ________________", S["legal_body"]),
        Paragraph("2. Signature: ______________\n"
                  "   Name: ___________________\n"
                  "   CNIC: ___________________\n"
                  "   Address: ________________", S["legal_body"]),
    ]], colWidths=[83*mm, 83*mm])
    wt.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    E.append(wt)

    # Notary block
    E.append(Spacer(1, 5*mm))
    nb = Table([[Paragraph(
        "NOTARIAL ATTESTATION\n\n"
        "Attested before me on this ______ day of ______________, 20____\n\n"
        "_______________________________          Stamp:\n"
        "Notary Public / Oath Commissioner\n"
        "Name: _________________________\n"
        "Registration No.: ______________",
        ParagraphStyle("nb", parent=S["legal_body"], fontSize=10, leading=18))
    ]], colWidths=[166*mm])
    nb.setStyle(TableStyle([
        ("BOX",        (0,0), (-1,-1), 1.5, NAVY),
        ("BACKGROUND", (0,0), (-1,-1), OFF_WHITE),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING",(0,0),(-1,-1),12),
        ("LEFTPADDING",(0,0), (-1,-1), 14),
    ]))
    E.append(nb)
    E.append(Spacer(1, 4*mm))
    E.append(Paragraph(
        "AI-generated by LexAI under Powers of Attorney Act 1882. Must be reviewed by a "
        "qualified attorney. Affix appropriate stamp duty before execution. "
        "For overseas use, requires apostille / consular attestation.", S["disclaimer"]))

    doc.build(E)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  TENANCY AGREEMENT — Dedicated generator
# ═══════════════════════════════════════════════════════════════
def generate_tenancy_pdf(data: dict) -> bytes:
    """Pakistan tenancy agreement — Punjab Rented Premises Act 2009."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=22*mm, leftMargin=22*mm,
                            topMargin=18*mm, bottomMargin=22*mm)
    S = _styles()
    E = []
    p   = data.get("landlord", {})
    t   = data.get("tenant", {})
    prop= data.get("property", {})
    fin = data.get("financial", {})
    jur = data.get("jurisdiction", "Pakistan, Punjab")

    _header_bar(E, f"TENANCY AGREEMENT — {jur.upper()}", S)
    E.append(Spacer(1, 5*mm))
    E.append(Paragraph("RESIDENTIAL / COMMERCIAL TENANCY AGREEMENT", S["legal_title"]))
    E.append(Paragraph(
        "Under Punjab Rented Premises Act 2009 / Sindh Rented Premises Ordinance 1979",
        S["doc_sub"]))
    _gen_stamp(E, S)
    _divider(E)

    E.append(_section_heading("PARTIES", S))
    E.append(Spacer(1, 2*mm))
    E.append(_field_table([
        ("LANDLORD Name",      p.get("name", "[LANDLORD NAME]")),
        ("Landlord CNIC",      _fmt_cnic(p.get("cnic", ""))),
        ("Landlord Address",   p.get("address", "[ADDRESS]")),
        ("Landlord Phone",     p.get("phone", "")),
        ("TENANT Name",        t.get("name", "[TENANT NAME]")),
        ("Tenant CNIC",        _fmt_cnic(t.get("cnic", ""))),
        ("Tenant Address",     t.get("address", "[ADDRESS]")),
        ("Tenant Phone",       t.get("phone", "")),
    ], S))
    E.append(Spacer(1, 4*mm))

    E.append(_section_heading("PROPERTY & FINANCIAL TERMS", S))
    E.append(Spacer(1, 2*mm))
    monthly = float(fin.get("monthly_rent", 0))
    deposit = float(fin.get("security_deposit", 0))
    E.append(_field_table([
        ("Property Address",          prop.get("address", "[PROPERTY ADDRESS]")),
        ("Property Type",             prop.get("type", "Residential")),
        ("Floor / Unit",              prop.get("unit", "—")),
        ("Commencement Date",         fin.get("start_date", "[DATE]")),
        ("Tenancy Duration",          fin.get("duration", "12 months")),
        ("Expiry Date",               fin.get("end_date", "[DATE]")),
        ("Monthly Rent (PKR)",        f"PKR {monthly:,.0f}"),
        ("Security Deposit (PKR)",    f"PKR {deposit:,.0f}  (max 2 months per S.22 PRPA)"),
        ("Rent Payment Day",          fin.get("payment_day", "1st of each month")),
        ("Bank / Payment Method",     fin.get("payment_method", "[METHOD]")),
    ], S))
    E.append(Spacer(1, 4*mm))

    E.append(_section_heading("TERMS & CONDITIONS", S))
    E.append(Spacer(1, 2*mm))
    clauses = [
        "<b>USE OF PREMISES:</b> The Tenant shall use the premises solely for the purpose stated above and shall not sub-let, assign, or transfer the tenancy without prior written consent of the Landlord.",
        "<b>RENT & INCREASES:</b> Rent is payable on the date specified above. Rent may be increased by maximum <b>10% per annum</b> with 30 days written notice, as per Section 7 of the Punjab Rented Premises Act 2009.",
        "<b>SECURITY DEPOSIT:</b> The Tenant has deposited PKR {:,.0f} as security deposit. This amount is refundable within 30 days of vacating the premises, subject to deductions for damage beyond normal wear and tear.".format(deposit),
        "<b>MAINTENANCE:</b> The Landlord is responsible for major structural repairs (Section 17 PRPA). The Tenant shall maintain the premises in clean condition and carry out minor day-to-day repairs.",
        "<b>UTILITIES:</b> Electricity, gas, and water bills shall be paid by the [Tenant/Landlord] as agreed. WAPDA, SNGPL/SSGC and WASA connections shall remain in [Tenant/Landlord] name.",
        "<b>ACCESS:</b> The Landlord shall not enter the premises without prior notice of at least 24 hours except in emergency. Unauthorised entry may constitute criminal trespass under Section 448 PPC.",
        "<b>EVICTION:</b> Neither party shall terminate this agreement without minimum 30 days written notice. Eviction can only be effected through the Rent Controller Court; self-help eviction is a criminal offence (Section 14 PRPA).",
        "<b>ALTERATIONS:</b> The Tenant shall not make any structural alterations without prior written consent of the Landlord.",
        "<b>GOVERNING LAW:</b> This Agreement shall be governed by the laws of Pakistan and the jurisdiction of the appropriate Rent Controller / Civil Court.",
    ]
    for i, cl in enumerate(clauses, 1):
        E.append(Paragraph(f"{i}.  {cl}", S["legal_clause"]))
        E.append(Spacer(1, 2.5*mm))

    _sig_block(E, S, [
        p.get("name", "Landlord") + "\n(Landlord)",
        t.get("name", "Tenant") + "\n(Tenant)",
    ])

    E.append(Spacer(1, 3*mm))
    E.append(Paragraph("WITNESSES:", S["legal_h2"]))
    wt = Table([[
        Paragraph("1. _______________________\n   Name: _______________\n   CNIC: _______________", S["legal_body"]),
        Paragraph("2. _______________________\n   Name: _______________\n   CNIC: _______________", S["legal_body"]),
    ]], colWidths=[83*mm, 83*mm])
    wt.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    E.append(wt)

    E.append(Spacer(1, 4*mm))
    E.append(Paragraph(
        "STAMP DUTY: PKR 200 stamp paper required (Punjab). Register with relevant Rent Controller "
        "if tenancy exceeds 1 year. Generated by LexAI. Verify with a qualified lawyer before execution.",
        S["disclaimer"]))

    doc.build(E)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  EMPLOYMENT CONTRACT — Dedicated generator
# ═══════════════════════════════════════════════════════════════
def generate_employment_contract_pdf(data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=22*mm, leftMargin=22*mm,
                            topMargin=18*mm, bottomMargin=22*mm)
    S = _styles()
    E = []

    emp = data.get("employee", {})
    er  = data.get("employer", {})
    terms = data.get("terms", {})
    jur = data.get("jurisdiction", "Pakistan")

    _header_bar(E, f"EMPLOYMENT CONTRACT — {jur.upper()}", S)
    E.append(Spacer(1, 5*mm))
    E.append(Paragraph("CONTRACT OF EMPLOYMENT", S["legal_title"]))
    E.append(Paragraph(
        "Under Industrial & Commercial Employment (Standing Orders) Ordinance 1968 "
        "& Payment of Wages Act 1936",
        S["doc_sub"]))
    _gen_stamp(E, S)
    _divider(E)

    E.append(_section_heading("EMPLOYER", S))
    E.append(Spacer(1, 2*mm))
    E.append(_field_table([
        ("Company Name",     er.get("name", "[COMPANY NAME]")),
        ("NTN / STRN",       er.get("ntn", "—")),
        ("Registered Office",er.get("address", "[ADDRESS]")),
        ("HR Contact",       er.get("hr_contact", "—")),
    ], S))
    E.append(Spacer(1, 3*mm))

    E.append(_section_heading("EMPLOYEE", S))
    E.append(Spacer(1, 2*mm))
    gross = float(terms.get("gross_salary", 0))
    E.append(_field_table([
        ("Employee Name",     emp.get("name", "[NAME]")),
        ("CNIC",              _fmt_cnic(emp.get("cnic", ""))),
        ("Father/Husband",    emp.get("father_name", "—")),
        ("Designation",       terms.get("designation", "[DESIGNATION]")),
        ("Department",        terms.get("department", "—")),
        ("Joining Date",      terms.get("joining_date", "[DATE]")),
        ("Employment Type",   terms.get("emp_type", "Permanent")),
        ("Probation Period",  terms.get("probation", "3 months")),
    ], S))
    E.append(Spacer(1, 3*mm))

    E.append(_section_heading("COMPENSATION & BENEFITS", S))
    E.append(Spacer(1, 2*mm))
    E.append(_field_table([
        ("Gross Monthly Salary (PKR)", f"PKR {gross:,.0f}"),
        ("Basic Salary",              f"PKR {gross * 0.6:,.0f}  (60% of gross)"),
        ("House Rent Allowance",      f"PKR {gross * 0.3:,.0f}  (30% of gross)"),
        ("Medical Allowance",         f"PKR {gross * 0.1:,.0f}  (10% of gross)"),
        ("Annual Increment",          terms.get("increment", "As per policy")),
        ("Annual Bonus",              terms.get("bonus", "As per policy")),
        ("EOBI Deduction",            "1% of minimum wage (employee share)"),
        ("Income Tax Deduction",      "As per FBR tax slabs (Section 149 ITO 2001)"),
        ("Working Hours",             "8 hours/day, 48 hours/week (S. 4 S&E Ord. 1969)"),
        ("Annual Leave",              "14 days earned leave (S. 8 S&E Ord.)"),
        ("Sick Leave",                "10 days per year"),
        ("Casual Leave",              "10 days per year"),
    ], S))
    E.append(Spacer(1, 3*mm))

    E.append(_section_heading("TERMS OF EMPLOYMENT", S))
    E.append(Spacer(1, 2*mm))
    clauses = [
        "<b>NOTICE PERIOD:</b> Either party may terminate this contract with 30 days written notice or one month's salary in lieu thereof, as per Section 11 of the Industrial & Commercial Employment Ordinance 1968.",
        "<b>CONFIDENTIALITY:</b> The Employee shall maintain strict confidentiality of all proprietary information, trade secrets, and business data during employment and for 2 years thereafter.",
        "<b>CONFLICT OF INTEREST:</b> The Employee shall not engage in any activity that conflicts with the interests of the Employer without prior written consent.",
        "<b>DISCIPLINE & CONDUCT:</b> The Employee shall comply with the Employer's Code of Conduct, Standing Orders, and all applicable policies.",
        "<b>UNFAIR DISMISSAL:</b> The Employee's rights are protected under the Industrial Relations Act 2012. Complaints may be filed with the Labour Court within 3 years.",
        "<b>MATERNITY:</b> Female employees are entitled to 12 weeks paid maternity leave under the Maternity Benefits Ordinance 1958.",
        "<b>EOBI:</b> Both parties shall contribute to EOBI (Employees Old-Age Benefits Institution) as required by law.",
        "<b>GOVERNING LAW:</b> This contract is governed by the laws of Pakistan.",
    ]
    for i, cl in enumerate(clauses, 1):
        E.append(Paragraph(f"{i}.  {cl}", S["legal_clause"]))
        E.append(Spacer(1, 2*mm))

    _sig_block(E, S, [
        emp.get("name", "Employee") + "\n(Employee)",
        er.get("name", "Employer") + "\n(Authorised Signatory)",
    ])

    E.append(Spacer(1, 4*mm))
    E.append(Paragraph(
        "Generated by LexAI. This is a standard form contract; adapt to specific circumstances. "
        "Reviewed for compliance with Pakistan labour laws as of 2024. "
        "Consult a labour lawyer for complex employment relationships.",
        S["disclaimer"]))

    doc.build(E)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════
def _fmt_cnic(cnic: str) -> str:
    c = re.sub(r"\D", "", str(cnic))
    if len(c) == 13:
        return f"{c[:5]}-{c[5:12]}-{c[12]}"
    return cnic or "—"


def _fmt_citizen(code: str) -> str:
    return {
        "resident": "Pakistani Resident",
        "overseas": "Overseas Pakistani (Non-Resident)",
        "nrp":      "Non-Resident Pakistani (NRP)",
    }.get(code, code.replace("_", " ").title() if code else "Pakistani Resident")


def _fmt_emp(code: str) -> str:
    return {
        "salaried": "Salaried Employee",
        "business": "Business Owner / Self-Employed",
        "overseas": "Overseas Pakistani",
    }.get(code, code.title() if code else "Salaried")


def _md_inline(text: str) -> str:
    """Convert basic inline markdown to ReportLab XML."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*",     r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`",       r"<font name='Helvetica-Oblique'>\1</font>", text)
    return text


def _stamp_duty_note(doc_type: str, jurisdiction: str) -> str:
    notes = {
        "Tenancy Agreement":
            "STAMP DUTY: PKR 200 stamp paper required (Punjab). "
            "Register with Rent Controller if >1 year tenure.",
        "Employment Contract":
            "This contract does not require stamp duty but should be retained by both parties.",
        "Affidavit":
            "STAMP PAPER: PKR 100–500 non-judicial stamp paper required. "
            "Must be sworn before Oath Commissioner / Magistrate.",
        "Power of Attorney":
            "STAMP DUTY: PKR 500–1,000 non-judicial stamp paper (Punjab). "
            "Notarial / Oath Commissioner attestation required for court use.",
        "Wakalatnaama":
            "STAMP DUTY: PKR 500–1,000 non-judicial stamp paper (Punjab). "
            "Must be attested before a Notary Public or Oath Commissioner.",
        "Partnership Deed":
            "STAMP DUTY: Applicable as per Punjab Stamp Act; typically 1% of capital. "
            "Register with Registrar of Firms for legal protection.",
    }
    for key, note in notes.items():
        if key.lower() in doc_type.lower():
            return f"⚠  {note}"
    return ""


def _needs_witnesses(doc_type: str) -> bool:
    return any(k in doc_type.lower() for k in [
        "affidavit", "power of attorney", "wakalatnaama",
        "tenancy", "partnership", "deed", "agreement"])


def _get_parties(doc_type: str, party_data: dict) -> list:
    dt = doc_type.lower()
    pd = party_data or {}
    if "tenancy" in dt or "rent" in dt:
        return [pd.get("landlord_name", "Landlord"), pd.get("tenant_name", "Tenant")]
    if "employment" in dt:
        return [pd.get("employee_name", "Employee"), pd.get("employer_name", "Employer")]
    if "partnership" in dt:
        return [pd.get("partner1_name", "Partner 1"), pd.get("partner2_name", "Partner 2")]
    if "power of attorney" in dt or "wakalatnaama" in dt:
        return [pd.get("principal_name", "Principal"), pd.get("attorney_name", "Attorney")]
    return [pd.get("party1_name", "Party 1"), pd.get("party2_name", "Party 2")]