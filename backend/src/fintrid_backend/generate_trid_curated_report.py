from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet


def extract_loan_meta_from_responses(
    le_data: Optional[Dict[str, Any]],
    cd_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    data = cd_data or le_data or {}
    
    applicants = data.get("applicants", [])
    borrower_names = []
    if applicants:
        for applicant in applicants:
            name = applicant.get("name")
            if name:
                borrower_names.append(name)
    borrower_str = " & ".join(borrower_names) if borrower_names else "—"
    
    property_data = data.get("property", {})
    property_address = property_data.get("address", "—")
    
    loan_data = data.get("loan", {})
    loan_id = loan_data.get("loan_id", "—")
    loan_type = loan_data.get("type", "—")
    purpose = loan_data.get("purpose", "—")
    product = loan_data.get("product", "—")
    term_months = loan_data.get("term_months")
    term_str = f"{term_months} months" if term_months else "—"
    
    sale_price = data.get("sale_price")
    sale_price_str = f"${sale_price:,.2f}" if sale_price else "—"
    
    loan_terms = data.get("loan_terms", {})
    loan_amount = loan_terms.get("loan_amount")
    loan_amount_str = f"${loan_amount:,.2f}" if loan_amount else "—"
    
    return {
        "borrower": borrower_str,
        "property": property_address,
        "loan_id": loan_id,
        "loan_type": loan_type,
        "purpose": purpose,
        "product": product,
        "term": term_str,
        "sale_price": sale_price_str,
        "loan_amount": loan_amount_str,
    }

# ─────────────────────────────────────────────────────────────
# 1) Styles

styles = getSampleStyleSheet()
H1 = styles["Heading1"]
H2 = styles["Heading2"]
H3 = styles["Heading3"]
BODY = styles["Normal"]


# ─────────────────────────────────────────────────────────────
# 2) Helper functions

def format_money(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"${value:,.2f}"


def compute_status_and_diff(
    le_amount: Optional[float],
    cd_amount: Optional[float],
    tolerance: str,
) -> Dict[str, Any]:
    """
    Basic tolerance logic:
    - zero: cd must not exceed le (if both present)
    - ten_percent: cd <= le * 1.10
    - unlimited: always "OK" for tolerance purposes
    Also classify missing/added fees.
    """
    if le_amount is None and cd_amount is None:
        return {"status": "N/A", "difference": None, "violates": False}

    if le_amount is None and cd_amount is not None:
        return {"status": "Added on CD", "difference": cd_amount, "violates": True}

    if le_amount is not None and cd_amount is None:
        return {"status": "Missing on CD", "difference": -le_amount, "violates": True}

    diff = (cd_amount or 0.0) - (le_amount or 0.0)

    if tolerance == "unlimited":
        status = "Within tolerance (unlimited)"
        violates = False
    elif tolerance == "zero":
        if diff > 0:
            status = "Exceeded ZERO tolerance"
            violates = True
        else:
            status = "Within ZERO tolerance"
            violates = False
    elif tolerance == "ten_percent":
        if le_amount is None or le_amount == 0:
            status = "Check manually"
            violates = False
        else:
            allowed = le_amount * 0.10
            if diff > allowed:
                status = "Exceeded 10% tolerance"
                violates = True
            else:
                status = "Within 10% tolerance"
                violates = False
    else:
        status = "Unknown tolerance"
        violates = False

    return {"status": status, "difference": diff, "violates": violates}


def make_summary_table(loan_meta: Dict[str, Any], total_width: float) -> Table:
    rows = [
        ["Borrower(s)", loan_meta.get("borrower", "—")],
        ["Property", loan_meta.get("property", "—")],
        ["Loan ID", loan_meta.get("loan_id", "—")],
        ["Loan Type", loan_meta.get("loan_type", "—")],
        ["Purpose", loan_meta.get("purpose", "—")],
        ["Product", loan_meta.get("product", "—")],
        ["Term", loan_meta.get("term", "—")],
        ["Sale Price", loan_meta.get("sale_price", "—")],
        ["Loan Amount", loan_meta.get("loan_amount", "—")],
    ]
    col_widths = [0.25 * total_width, 0.75 * total_width]
    table = Table([["Field", "Value"]] + rows, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def make_stats_table(matched_fees: List[Dict[str, Any]], total_width: float) -> Table:
    total = len(matched_fees)
    viol_count = 0
    zero_count = ten_count = unlim_count = 0

    for fee in matched_fees:
        tol = fee.get("tolerance_category")
        if tol == "zero":
            zero_count += 1
        elif tol == "ten_percent":
            ten_count += 1
        elif tol == "unlimited":
            unlim_count += 1

        status_info = compute_status_and_diff(
            fee.get("le_amount"),
            fee.get("cd_amount"),
            fee.get("tolerance_category", "unlimited"),
        )
        if status_info["violates"]:
            viol_count += 1

    ok_count = total - viol_count

    rows = [
        ["Total Fees (matched/compared)", str(total)],
        ["Within tolerance (count)", str(ok_count)],
        ["Tolerance issues (count)", str(viol_count)],
        ["Zero Tolerance Fees (A, B)", str(zero_count)],
        ["10% Tolerance Fees (C, E)", str(ten_count)],
        ["Unlimited Tolerance Fees (F, G, H)", str(unlim_count)],
    ]
    col_widths = [0.4 * total_width, 0.6 * total_width]
    table = Table([["Metric", "Value"]] + rows, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
        )
    )
    return table


def make_fee_detail_table(
    matched_fees: List[Dict[str, Any]],
    total_width: float,
) -> Table:
    header = [
        "Fee Name",
        "Sec",
        "Tol.",
        "LE Amt",
        "CD Amt",
        "Diff",
        "Status",
        "Conf.",
        "Provider",
    ]
    rows = [header]

    for fee in matched_fees:
        le_amt = fee.get("le_amount")
        cd_amt = fee.get("cd_amount")
        tol = fee.get("tolerance_category", "unlimited")
        status_info = compute_status_and_diff(le_amt, cd_amt, tol)

        diff_val = status_info["difference"]
        if diff_val is None:
            diff_str = "—"
        else:
            sign = "+" if diff_val > 0 else ""
            diff_str = f"{sign}{diff_val:,.2f}"

        row = [
            fee.get("fee_name", "—"),
            fee.get("section", "—"),
            tol,
            format_money(le_amt),
            format_money(cd_amt),
            diff_str,
            status_info["status"],
            f"{fee.get('match_confidence', 0.0):.2f}",
            fee.get("provider_name") or "—",
        ]
        rows.append(row)

    # Fractions must sum to 1.0 – this guarantees it fits the page width.
    fractions = [
        0.22,  # Fee Name
        0.06,  # Sec
        0.08,  # Tol
        0.10,  # LE Amt
        0.10,  # CD Amt
        0.08,  # Diff
        0.20,  # Status
        0.06,  # Conf
        0.10,  # Provider
    ]
    col_widths = [f * total_width for f in fractions]

    table = Table(rows, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 1), (5, -1), "RIGHT"),   # money columns
        ("ALIGN", (7, 1), (7, -1), "RIGHT"),   # confidence
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 9),
    ]

    # Highlight violations in light red
    for idx, fee in enumerate(matched_fees, start=1):
        status_info = compute_status_and_diff(
            fee.get("le_amount"),
            fee.get("cd_amount"),
            fee.get("tolerance_category", "unlimited"),
        )
        if status_info["violates"]:
            style_cmds.append(
                ("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#ffe5e5"))
            )

    table.setStyle(TableStyle(style_cmds))
    return table


# ─────────────────────────────────────────────────────────────
# 3) Main report builder

def build_trid_curated_report(
    comparison: Dict[str, Any],
    loan_meta: Dict[str, Any],
    output_path: str = "trid_curated_report.pdf",
) -> None:
    matched_fees: List[Dict[str, Any]] = comparison.get("matched_fees", [])
    processed_at: str = comparison.get("processed_at", datetime.now().isoformat())

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(LETTER),
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
    )

    width = doc.width  # 👈 usable page width after margins

    story = []

    # Header
    story.append(Paragraph("TRID Curated Comparison Report", H1))
    story.append(
        Paragraph(
            f"Generated At: {datetime.fromisoformat(processed_at):%Y-%m-%d %H:%M:%S}",
            BODY,
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    # Loan summary
    story.append(Paragraph("Loan & Property Summary", H2))
    story.append(Spacer(1, 0.05 * inch))
    story.append(make_summary_table(loan_meta, width))
    story.append(Spacer(1, 0.2 * inch))

    # Stats summary
    story.append(Paragraph("TRID Fee Matching Summary", H2))
    story.append(Spacer(1, 0.05 * inch))
    story.append(make_stats_table(matched_fees, width))
    story.append(Spacer(1, 0.2 * inch))

    # Optional narrative summary
    summary_dict = comparison.get("summary", {})
    if isinstance(summary_dict, dict) and summary_dict:
        story.append(Paragraph("AI Summary (Optional)", H3))
        bullets = []
        for k, v in summary_dict.items():
            bullets.append(f"• <b>{k}:</b> {v}")
        story.append(Paragraph("<br/>".join(bullets), BODY))
        story.append(Spacer(1, 0.2 * inch))

    # Fees detail page
    story.append(PageBreak())
    story.append(Paragraph("Detailed Fee Comparison (Loan Estimate vs Closing Disclosure)", H2))
    story.append(Spacer(1, 0.1 * inch))
    if matched_fees:
        story.append(make_fee_detail_table(matched_fees, width))
    else:
        story.append(Paragraph("No matched fees found in comparison.", BODY))

    doc.build(story)
    print(f"✅ TRID curated report created at: {output_path}")


# ─────────────────────────────────────────────────────────────
# 4) Dummy data for stand-alone run

def make_dummy_comparison() -> Dict[str, Any]:
    return {
        "processed_at": datetime.now().isoformat(),
        "summary": {
            "high_level": "Most fees are within TRID tolerance; a few zero-tolerance items exceed LE amounts.",
            "zero_tolerance_issues": "Origination Fee increased from LE to CD.",
            "ten_percent_tolerance_issues": "Recording fees remain within 10% aggregate threshold.",
        },
        "matched_fees": [
            {
                "fee_name": "Origination Fee",
                "section": "A",
                "le_amount": 1000.00,
                "cd_amount": 1200.00,
                "le_label": "01 Origination Fee",
                "cd_label": "01 Origination Fee",
                "match_confidence": 0.99,
                "tolerance_category": "zero",
                "provider_name": "ABC Mortgage, Inc.",
            },
            {
                "fee_name": "Application Fee",
                "section": "A",
                "le_amount": 500.00,
                "cd_amount": 500.00,
                "le_label": "02 Application Fee",
                "cd_label": "02 Application Fee",
                "match_confidence": 0.98,
                "tolerance_category": "zero",
                "provider_name": "ABC Mortgage, Inc.",
            },
            {
                "fee_name": "Appraisal Fee",
                "section": "B",
                "le_amount": 600.00,
                "cd_amount": 650.00,
                "le_label": "Appraisal Fee",
                "cd_label": "Appraisal Fee to ABC Appraisers",
                "match_confidence": 0.97,
                "tolerance_category": "zero",
                "provider_name": "ABC Appraisers LLC",
            },
            {
                "fee_name": "Recording Fees",
                "section": "E",
                "le_amount": 600.00,
                "cd_amount": 650.00,
                "le_label": "Recording Fees",
                "cd_label": "Recording Fees",
                "match_confidence": 0.95,
                "tolerance_category": "ten_percent",
                "provider_name": "County Recorder",
            },
            {
                "fee_name": "Transfer Taxes",
                "section": "E",
                "le_amount": 600.00,
                "cd_amount": 600.00,
                "le_label": "Transfer Taxes",
                "cd_label": "Transfer Taxes",
                "match_confidence": 0.98,
                "tolerance_category": "ten_percent",
                "provider_name": "County Tax Authority",
            },
            {
                "fee_name": "Homeowner’s Insurance (12 months)",
                "section": "F",
                "le_amount": 900.00,
                "cd_amount": 900.00,
                "le_label": "Homeowner’s Insurance (12 months)",
                "cd_label": "Homeowner’s Insurance (12 months)",
                "match_confidence": 0.99,
                "tolerance_category": "unlimited",
                "provider_name": "Best Home Insurance Co.",
            },
            {
                "fee_name": "HOA Transfer Fee",
                "section": "H",
                "le_amount": None,
                "cd_amount": 400.00,
                "le_label": None,
                "cd_label": "HOA Transfer Fee",
                "match_confidence": 0.80,
                "tolerance_category": "unlimited",
                "provider_name": "Pine Ridge HOA",
            },
        ],
    }


def make_dummy_loan_meta() -> Dict[str, Any]:
    return {
        "borrower": "John & Jane Doe",
        "property": "123 Main Street, Springfield, ST 12345",
        "loan_id": "123456789",
        "loan_type": "Conventional",
        "purpose": "Purchase",
        "product": "30-year fixed",
        "term": "360 months",
    }


# ─────────────────────────────────────────────────────────────
# 5) Entry point

if __name__ == "__main__":
    comparison = make_dummy_comparison()
    loan_meta = make_dummy_loan_meta()
    build_trid_curated_report(comparison, loan_meta, output_path="trid_curated_report.pdf")
