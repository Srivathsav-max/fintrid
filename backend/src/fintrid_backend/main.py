from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Literal, Any, AsyncIterator, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
from rapidfuzz import fuzz
from reportlab.pdfgen import canvas

from fintrid_backend.generate_trid_curated_report import (
    build_trid_curated_report,
    extract_loan_meta_from_responses,
)

# ---------- LandingAI (PDF -> Markdown) ----------
from landingai_ade import LandingAIADE

# ---------- Gemini / LangChain (Markdown -> JSON) ----------
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

# ---------- Pydantic v1 schema ----------
from pydantic.v1 import BaseModel, Field, validator, conint, confloat

# Load environment variables
load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# 1) Schema (Pydantic models)

Currency = confloat(ge=-1e9, le=1e9)


class LatePayment(BaseModel):
    late_after_days: Optional[conint(ge=0)] = None
    fee_pct_of_monthly_p_and_i: Optional[confloat(ge=0, le=100)] = None


class RateLock(BaseModel):
    is_locked: Optional[bool] = None
    until: Optional[str] = None
    timezone: Optional[str] = None


class LoanCore(BaseModel):
    loan_id: Optional[str] = None
    type: Optional[Literal["conventional", "fha", "va", "other"]] = None
    purpose: Optional[Literal["purchase", "refinance", "construction", "other"]] = None
    product: Optional[Literal["fixed_rate", "adjustable_rate", "other"]] = None
    term_months: Optional[int] = Field(
        None, description="Total months, e.g., 360 for 30 years"
    )
    rate_lock: Optional[RateLock] = None
    costs_expire_at: Optional[Dict[str, Optional[str]]] = None


class Feature(BaseModel):
    has: Optional[bool] = None
    amount: Optional[Currency] = None
    due_month: Optional[int] = None
    note: Optional[str] = None


class LoanTerms(BaseModel):
    loan_amount: Optional[Currency] = None
    interest_rate_pct: Optional[confloat(ge=0, le=100)] = None
    monthly_principal_interest: Optional[Currency] = None
    features: Optional[Dict[str, Feature]] = None


class PeriodPayment(BaseModel):
    period_label: Optional[str] = None
    from_month: Optional[int] = None
    to_month: Optional[int] = None
    principal_interest: Optional[Currency] = None
    mortgage_insurance: Optional[Currency] = None
    escrow: Optional[Currency] = None
    estimated_total_monthly_payment: Optional[Currency] = None


class TaxesInsuranceAssessments(BaseModel):
    estimate_per_month: Optional[Currency] = None
    in_escrow: Optional[bool] = None
    includes: Optional[Dict[str, Optional[bool]]] = None
    note: Optional[str] = None


class CostsAtClosing(BaseModel):
    estimated_closing_costs: Optional[Currency] = None
    estimated_cash_to_close: Optional[Currency] = None


SubLabel = Literal[
    "borrower_paid_at_closing",
    "borrower_paid_before_closing",
    "seller_paid_at_closing",
    "seller_paid_before_closing",
    "paid_by_others",
]
Payer = Literal["borrower", "seller", "other"]
Timing = Literal["at_closing", "before_closing", "n/a"]


class LineItem(BaseModel):
    label: Optional[str] = None
    amount: Optional[Currency] = None
    sub_label: Optional[SubLabel] = None
    payer: Optional[Payer] = None
    timing: Optional[Timing] = None

    @validator("payer", always=True)
    def _derive_payer(cls, v, values):
        if v is not None:
            return v
        sub = values.get("sub_label")
        if sub in ("borrower_paid_at_closing", "borrower_paid_before_closing"):
            return "borrower"
        if sub in ("seller_paid_at_closing", "seller_paid_before_closing"):
            return "seller"
        if sub == "paid_by_others":
            return "other"
        return v

    @validator("timing", always=True)
    def _derive_timing(cls, v, values):
        if v is not None:
            return v
        sub = values.get("sub_label")
        if sub in ("borrower_paid_at_closing", "seller_paid_at_closing"):
            return "at_closing"
        if sub in ("borrower_paid_before_closing", "seller_paid_before_closing"):
            return "before_closing"
        if sub == "paid_by_others":
            return "n/a"
        return v


class SectionWithItems(BaseModel):
    label: Optional[str] = None
    total: Optional[Currency] = None
    items: Optional[List[LineItem]] = None


class LoanCosts(BaseModel):
    A: Optional[SectionWithItems] = None
    B: Optional[SectionWithItems] = None
    C: Optional[SectionWithItems] = None
    D_total: Optional[Currency] = None


class OtherCosts(BaseModel):
    E: Optional[SectionWithItems] = None
    F: Optional[SectionWithItems] = None
    G: Optional[SectionWithItems] = None
    H: Optional[SectionWithItems] = None
    I_total: Optional[Currency] = None
    J_total: Optional[Currency] = None
    lender_credits: Optional[Currency] = 0.0


class CashToClose(BaseModel):
    total_closing_costs_J: Optional[Currency] = None
    financed_from_loan: Optional[Currency] = None
    down_payment: Optional[Currency] = None
    deposit: Optional[Currency] = None
    funds_for_borrower: Optional[Currency] = None
    seller_credits: Optional[Currency] = None
    adjustments_and_other_credits: Optional[Currency] = None
    estimated_cash_to_close: Optional[Currency] = None


class ClosingCostDetails(BaseModel):
    loan_costs: Optional[LoanCosts] = None
    other_costs: Optional[OtherCosts] = None
    cash_to_close: Optional[CashToClose] = None


class Contacts(BaseModel):
    lender: Optional[Dict[str, Optional[str]]] = None
    loan_officer: Optional[Dict[str, Optional[str]]] = None
    mortgage_broker: Optional[Dict[str, Optional[str]]] = None


class Comparisons(BaseModel):
    in_5_years: Optional[Dict[str, Optional[Currency]]] = None
    apr_pct: Optional[confloat(ge=0, le=100)] = None
    tip_pct: Optional[confloat(ge=0, le=100)] = None


class OtherConsiderations(BaseModel):
    appraisal_may_be_ordered: Optional[bool] = None
    assumption_allowed: Optional[bool] = None
    homeowners_insurance_required: Optional[bool] = None
    late_payment: Optional[LatePayment] = None
    refinance_note: Optional[str] = None
    servicing_intent: Optional[Literal["service", "transfer", "unknown"]] = None


class Applicant(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None


class Meta(BaseModel):
    source_id: Optional[str] = None
    source_file: Optional[str] = None
    page_count: Optional[int] = 3
    extracted_at: Optional[str] = None
    parser_version: Optional[str] = "1.0.0"


class LoanEstimateRecord(BaseModel):
    meta: Optional[Meta] = None
    applicants: Optional[List[Applicant]] = None
    property: Optional[Dict[str, Optional[str]]] = None
    sale_price: Optional[Currency] = None
    loan: Optional[LoanCore] = None
    loan_terms: Optional[LoanTerms] = None
    projected_payments: Optional[List[PeriodPayment]] = None
    taxes_insurance_assessments: Optional[TaxesInsuranceAssessments] = None
    costs_at_closing: Optional[CostsAtClosing] = None
    closing_cost_details: Optional[ClosingCostDetails] = None
    contacts: Optional[Contacts] = None
    comparisons: Optional[Comparisons] = None
    other_considerations: Optional[OtherConsiderations] = None
    confirm_receipt: Optional[Dict[str, Optional[bool]]] = None

    @validator("closing_cost_details", pre=False, always=False)
    def recompute_totals(cls, v: ClosingCostDetails | None) -> ClosingCostDetails | None:
        if not v or not v.loan_costs or not v.other_costs:
            return v

        A = v.loan_costs.A.total if v.loan_costs.A and v.loan_costs.A.total is not None else None
        B = v.loan_costs.B.total if v.loan_costs.B and v.loan_costs.B.total is not None else None
        C = v.loan_costs.C.total if v.loan_costs.C and v.loan_costs.C.total is not None else None

        if all(x is not None for x in [A, B, C]):
            v.loan_costs.D_total = round(float(A) + float(B) + float(C), 2)

        E = v.other_costs.E.total if v.other_costs.E and v.other_costs.E.total is not None else None
        F = v.other_costs.F.total if v.other_costs.F and v.other_costs.F.total is not None else None
        G = v.other_costs.G.total if v.other_costs.G and v.other_costs.G.total is not None else None
        H = v.other_costs.H.total if v.other_costs.H and v.other_costs.H.total is not None else None

        if all(x is not None for x in [E, F, G, H]):
            v.other_costs.I_total = round(float(E) + float(F) + float(G) + float(H), 2)

        if (
            v.loan_costs
            and v.other_costs
            and v.loan_costs.D_total is not None
            and v.other_costs.I_total is not None
        ):
            v.other_costs.J_total = round(float(v.loan_costs.D_total) + float(v.other_costs.I_total), 2)

        return v


# ──────────────────────────────────────────────────────────────────────────────
# AI-Powered Fee Matching Schema

class MatchedFee(BaseModel):
    """A single matched fee between LE and CD"""
    fee_name: str = Field(description="Normalized fee name")
    section: str = Field(description="Section: A, B, C, E, F, G, H")
    le_amount: Optional[Currency] = Field(
        None, description="Borrower-paid amount from Loan Estimate"
    )
    cd_amount: Optional[Currency] = Field(
        None,
        description="Borrower-paid amount from Closing Disclosure (sum of at_closing + before_closing)",
    )
    le_label: Optional[str] = Field(None, description="Original label from LE")
    cd_label: Optional[str] = Field(None, description="Original label from CD")
    match_confidence: float = Field(description="AI confidence in match (0-1)")
    tolerance_category: str = Field(description="zero, ten_percent, or unlimited")
    provider_name: Optional[str] = Field(
        None, description="Service provider name if applicable"
    )
    is_new: bool = Field(
        default=False,
        description="True if fee exists in CD but not in LE (new fee)",
    )
    chosen_from_list: Optional[bool] = Field(
        None,
        description="True if borrower selected the provider from the creditor's written list (Section C handling)",
    )
    changed_circumstance: Optional[bool] = Field(
        default=False,
        description="Flag if a valid changed circumstance applies to this fee",
    )


class FeeDiffSummary(BaseModel):
    fee_name: Optional[str] = None
    section: Optional[str] = None
    tolerance_category: Optional[str] = None
    le_label: Optional[str] = None
    cd_label: Optional[str] = None
    le_amount: Optional[Currency] = None
    cd_amount: Optional[Currency] = None
    difference: Optional[Currency] = None
    diff_type: Literal[
        "increase", "decrease", "missing_on_cd", "new_on_cd", "reclassified_off_borrower"
    ]
    match_confidence: Optional[float] = None
    is_new: Optional[bool] = None
    provider_name: Optional[str] = None
    reclassified_to: Optional[Literal["seller", "other"]] = None
    reclassified_amount: Optional[Currency] = None


class PdfHighlightAsset(BaseModel):
    source_pdf_path: Optional[str] = None
    highlighted_pdf_path: Optional[str] = None
    page_count: Optional[int] = None
    annotation_count: Optional[int] = None
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class PdfHighlightBundle(BaseModel):
    loan_estimate: Optional[PdfHighlightAsset] = None
    closing_disclosure: Optional[PdfHighlightAsset] = None
    legend: Optional[Dict[str, str]] = None


class TRIDComparison(BaseModel):
    """AI-processed TRID comparison between LE and CD"""
    matched_fees: List[MatchedFee] = Field(default_factory=list)
    summary: Optional[Dict[str, Any]] = Field(default_factory=dict)
    processed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    diff_summary: List[FeeDiffSummary] = Field(default_factory=list)
    pdf_highlights: Optional[PdfHighlightBundle] = None


class FinancialProfileSummary(BaseModel):
    """Comprehensive financial profile summary"""
    borrower_overview: str = Field(description="Summary of borrower(s) and property")
    loan_overview: str = Field(description="Loan type, purpose, and key terms")
    cost_analysis: str = Field(description="Analysis of closing costs and cash to close")
    trid_compliance: str = Field(description="TRID compliance status and violations")
    key_changes: List[str] = Field(description="Key changes from LE to CD")
    recommendations: List[str] = Field(description="Recommendations or concerns")
    risk_assessment: str = Field(description="Overall risk assessment")
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ──────────────────────────────────────────────────────────────────────────────
# 2) Document Type Detection

def detect_document_type(record: dict) -> Literal["loan_estimate", "closing_disclosure", "unknown"]:
    """Detect if a document is a Loan Estimate or Closing Disclosure based on its structure"""
    closing_cost_details = record.get("closing_cost_details", {})

    if not closing_cost_details:
        return "unknown"

    loan_costs = closing_cost_details.get("loan_costs", {})
    other_costs = closing_cost_details.get("other_costs", {})

    has_sub_labels = False
    for section_key in ["A", "B", "C"]:
        section = loan_costs.get(section_key, {})
        items = section.get("items", [])
        for item in items:
            if item.get("sub_label"):
                has_sub_labels = True
                break
        if has_sub_labels:
            break

    if not has_sub_labels:
        for section_key in ["E", "F", "G", "H"]:
            section = other_costs.get(section_key, {})
            items = section.get("items", [])
            for item in items:
                if item.get("sub_label"):
                    has_sub_labels = True
                    break
            if has_sub_labels:
                break

    if has_sub_labels:
        return "closing_disclosure"
    else:
        return "loan_estimate"


# ──────────────────────────────────────────────────────────────────────────────
# 3) AI-Powered Fee Matching Function

MATCHING_SYSTEM = """You are an expert TRID (TILA-RESPA Integrated Disclosure) analyst.

Your task is to intelligently match BORROWER-PAID ONLY fees between a Loan Estimate (LE) and Closing Disclosure (CD).

MATCHING RULES:
1. **BORROWER-PAID ONLY**: Only include fees where the borrower is paying
   - For LE: Include all fees (borrower pays all in LE)
   - For CD: Only include fees with sub_label = "borrower_paid_at_closing" or "borrower_paid_before_closing"
   - IGNORE seller-paid and other-paid fees entirely

2. **SUM BORROWER AMOUNTS**: 
   - For each fee, sum borrower_paid_at_closing + borrower_paid_before_closing
   - Return single borrower amount (not split by timing)

3. **MATCHING LOGIC**:
   - Match fees even if labels differ slightly (spacing, prefixes, vendor names)
   - Extract provider names from labels like "01 Appraisal Fee to John Smith Appraisers Inc."
   - Determine the correct section (A, B, C, E, F, G, H) for each fee
   - Assign tolerance category:
     * Section A, B → "zero" tolerance
     * Section C, E → "ten_percent" tolerance
     * Section F, G, H → "unlimited" tolerance

4. **CONFIDENCE SCORING** (0.0 to 1.0):
   - 1.0 = Perfect match (same fee, minor label differences)
   - 0.8-0.99 = High confidence (similar names, same amounts)
   - 0.5-0.79 = Medium confidence (similar purpose, different amounts)
   - Below 0.5 = Low confidence (unsure if same fee)

5. **NEW FEES**:
   - If a fee appears in LE but not CD: include with cd_amount=null, is_new=false
   - If a fee appears in CD but not LE: include with le_amount=null, is_new=true (NEW FEE!)
   - Use normalized fee_name (remove prefixes, normalize spacing)
   - Extract clean provider_name if present

CRITICAL: Exclude all fees with zero or null borrower amounts. Only return fees where borrower is actually paying.

Return a complete TRIDComparison with all matched BORROWER-PAID fees.
"""


DIFF_EPSILON = 0.01
SECTION_HEADER_PATTERN = re.compile(r"^([A-H])\.\s", re.IGNORECASE)
E_RECORDING_TOKENS = {
    "recording",
    "deed recording",
    "mortgage recording",
    "recording fee",
    "recordation",
}
E_TRANSFER_TAX_TOKENS = {
    "transfer tax",
    "transfer taxes",
    "intangible tax",
    "doc stamp",
    "documentary stamp",
    "stamp tax",
}


def classify_fee_tolerance(
    section: Optional[str],
    label: Optional[str],
    chosen_from_list: Optional[bool],
    changed_circumstance: Optional[bool],
) -> str:
    sec = (section or "").strip().upper()
    text = (label or "").lower()

    if sec == "A":
        return "zero"

    if sec == "B":
        if changed_circumstance:
            return "unlimited"
        return "zero"

    if sec == "C":
        return "ten_percent" if chosen_from_list else "unlimited"

    if sec == "E":
        if any(token in text for token in E_TRANSFER_TAX_TOKENS):
            return "zero"
        if any(token in text for token in E_RECORDING_TOKENS):
            return "ten_percent"
        return "ten_percent"

    if sec in {"F", "G", "H"}:
        return "unlimited"

    return "unlimited"


def compute_tolerance_metrics(matched_fees: List[Dict[str, Any]]) -> Dict[str, Any]:
    bucket_totals: Dict[str, Dict[str, float]] = {
        "zero": {"le_sum": 0.0, "cd_sum": 0.0, "count": 0},
        "ten_percent": {"le_sum": 0.0, "cd_sum": 0.0, "count": 0},
        "unlimited": {"le_sum": 0.0, "cd_sum": 0.0, "count": 0},
    }

    for fee in matched_fees:
        tol = fee.get("tolerance_category") or "unlimited"
        tol = tol if tol in bucket_totals else "unlimited"
        le = float(fee.get("le_amount") or 0.0)
        cd = float(fee.get("cd_amount") or 0.0)
        bucket_totals[tol]["le_sum"] += le
        bucket_totals[tol]["cd_sum"] += cd
        bucket_totals[tol]["count"] += 1

    ten = bucket_totals["ten_percent"]
    limit = round(ten["le_sum"] * 1.10, 2)
    cure = max(0.0, round(ten["cd_sum"] - limit, 2))

    ten_percent_test = {
        "le_sum": round(ten["le_sum"], 2),
        "cd_sum": round(ten["cd_sum"], 2),
        "limit": limit,
        "cure_required": cure,
    }

    for bucket in bucket_totals.values():
        bucket["le_sum"] = round(bucket["le_sum"], 2)
        bucket["cd_sum"] = round(bucket["cd_sum"], 2)

    return {
        "bucket_totals": bucket_totals,
        "ten_percent_test": ten_percent_test,
    }


def _normalize_label_for_key(label: Optional[str]) -> str:
    if not label:
        return ""
    text = label.lower()
    text = re.sub(r"^\s*\d{2}\s*[-.:)]?\s*", "", text)
    text = re.sub(r"\bto\b.+$", "", text)
    text = text.replace("owner’s", "owners").replace("owner's", "owners")
    text = text.replace("fee", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_cd_label_index(cd_record: dict) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}

    def section_items(sec: str) -> List[dict]:
        bag = "loan_costs" if sec in {"A", "B", "C"} else "other_costs"
        return (
            cd_record.get("closing_cost_details", {})
            .get(bag, {})
            .get(sec, {})
            .get("items", [])
            or []
        )

    for sec in ["A", "B", "C", "E", "F", "G", "H"]:
        for item in section_items(sec):
            label = item.get("label") or ""
            key = f"{sec}:{_normalize_label_for_key(label)}"
            entry = index.setdefault(
                key,
                {
                    "section": sec,
                    "label": label,
                    "borrower": 0.0,
                    "seller": 0.0,
                    "other": 0.0,
                },
            )
            amount = float(item.get("amount") or 0.0)
            sub_label = (item.get("sub_label") or "").lower()
            if sub_label.startswith("borrower_paid"):
                entry["borrower"] += amount
            elif sub_label.startswith("seller_paid"):
                entry["seller"] += amount
            elif sub_label == "paid_by_others":
                entry["other"] += amount
    return index


PDF_COLOR_SCHEME = {
    "loan_estimate_change": {
        "rgb": (14, 165, 233),
        "hex": "#0EA5E9",
        "description": "Loan Estimate fee changed vs Closing Disclosure",
    },
    "loan_estimate_missing": {
        "rgb": (249, 115, 22),
        "hex": "#F97316",
        "description": "Fee missing on Closing Disclosure (highlighted on LE)",
    },
    "closing_disclosure_change": {
        "rgb": (190, 24, 93),
        "hex": "#BE185D",
        "description": "Closing Disclosure fee changed vs Loan Estimate",
    },
    "closing_disclosure_new": {
        "rgb": (22, 163, 74),
        "hex": "#16A34A",
        "description": "New fee introduced on Closing Disclosure",
    },
}


def build_fee_diff_summary(matched_fees: List[dict]) -> List[Dict[str, Any]]:
    """Derive per-fee difference metadata for downstream consumers."""
    summary: List[Dict[str, Any]] = []
    for fee in matched_fees:
        fee_dict = fee if isinstance(fee, dict) else fee.dict()  # type: ignore[arg-type]
        le_amount = fee_dict.get("le_amount")
        cd_amount = fee_dict.get("cd_amount")
        reclassified_to = fee_dict.get("reclassified_to")

        diff_type: Optional[str] = None
        diff_value: Optional[float] = None

        if le_amount is None and cd_amount is None:
            continue

        if cd_amount is None and le_amount is not None and reclassified_to:
            diff_type = "reclassified_off_borrower"
            diff_value = -float(le_amount)
        elif le_amount is None and cd_amount is not None:
            diff_type = "new_on_cd"
        elif cd_amount is None and le_amount is not None:
            diff_type = "missing_on_cd"
            diff_value = -float(le_amount)
        else:
            diff_value = float(cd_amount) - float(le_amount)
            if abs(diff_value) < DIFF_EPSILON:
                continue
            diff_type = "increase" if diff_value > 0 else "decrease"

        if diff_type is None:
            continue

        summary.append(
            {
                "fee_name": fee_dict.get("fee_name"),
                "section": fee_dict.get("section"),
                "tolerance_category": fee_dict.get("tolerance_category"),
                "le_label": fee_dict.get("le_label") or fee_dict.get("fee_name"),
                "cd_label": fee_dict.get("cd_label") or fee_dict.get("fee_name"),
                "le_amount": le_amount,
                "cd_amount": cd_amount,
                "difference": diff_value,
                "diff_type": diff_type,
                "match_confidence": fee_dict.get("match_confidence"),
                "is_new": fee_dict.get("is_new"),
                "provider_name": fee_dict.get("provider_name"),
                "reclassified_to": reclassified_to,
                "reclassified_amount": fee_dict.get("reclassified_amount"),
            }
        )
    return summary


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _normalize_for_fuzz(value: Optional[str]) -> str:
    if not value:
        return ""
    text = value.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize_text(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return re.findall(r"[a-z0-9]+", value.lower())


def _normalize_amount_digits(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    formatted = f"{float(value):,.2f}"
    digits = re.sub(r"[^0-9]", "", formatted)
    return digits or None


def _cluster_words_into_lines(words: List[dict], y_tol: float = 3.0) -> List[Dict[str, Any]]:
    lines: List[Dict[str, Any]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        matched_line: Optional[Dict[str, Any]] = None
        for line in lines:
            if abs(line["top"] - word["top"]) <= y_tol:
                matched_line = line
                break
        if matched_line is None:
            matched_line = {
                "top": word["top"],
                "bottom": word["bottom"],
                "x0": word["x0"],
                "x1": word["x1"],
                "words": [word],
            }
            lines.append(matched_line)
        else:
            matched_line["top"] = min(matched_line["top"], word["top"])
            matched_line["bottom"] = max(matched_line["bottom"], word["bottom"])
            matched_line["x0"] = min(matched_line["x0"], word["x0"])
            matched_line["x1"] = max(matched_line["x1"], word["x1"])
            matched_line["words"].append(word)

    for line in lines:
        ordered_words = sorted(line["words"], key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in ordered_words).strip()
        line["text"] = text
        line["norm_text"] = _normalize_text(text)
        line["digits"] = re.sub(r"[^0-9]", "", text)
        line["fuzzy_text"] = _normalize_for_fuzz(text)
        line["tokens"] = _tokenize_text(text)
        line["mid_y"] = (line["top"] + line["bottom"]) / 2
    return lines


def _extract_pdf_pages(pdf_path: Path) -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages):
            words = page.extract_words(
                x_tolerance=1.5, y_tolerance=0.5, keep_blank_chars=False, use_text_flow=True
            )
            lines = _cluster_words_into_lines(words)
            section_markers: List[Dict[str, Any]] = []
            for line in lines:
                text = (line.get("text") or "").strip()
                match = SECTION_HEADER_PATTERN.match(text)
                if match:
                    section_markers.append(
                        {
                            "section": match.group(1).upper(),
                            "top": line["top"],
                        }
                    )
            section_ranges: Dict[str, Tuple[float, float]] = {}
            for idx, marker in enumerate(section_markers):
                start = marker["top"]
                end = (
                    section_markers[idx + 1]["top"]
                    if idx + 1 < len(section_markers)
                    else page.height
                )
                section_ranges[marker["section"]] = (start, end)
            pages.append(
                {
                    "index": index,
                    "width": page.width,
                    "height": page.height,
                    "lines": lines,
                    "section_ranges": section_ranges,
                }
            )
    return pages


def _resolve_color(doc_type: str, diff_type: str) -> Dict[str, Any]:
    if doc_type == "loan_estimate":
        key = "loan_estimate_missing" if diff_type == "missing_on_cd" else "loan_estimate_change"
    else:
        key = "closing_disclosure_new" if diff_type == "new_on_cd" else "closing_disclosure_change"
    config = PDF_COLOR_SCHEME[key]
    return {
        "key": key,
        "rgb": tuple(channel / 255.0 for channel in config["rgb"]),
        "hex": config["hex"],
        "description": config["description"],
    }


def _build_highlight_requests(diff_summary: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    requests: Dict[str, List[Dict[str, Any]]] = {"loan_estimate": [], "closing_disclosure": []}
    for entry in diff_summary:
        diff_type = entry.get("diff_type")
        if not diff_type:
            continue

        base_payload = {
            "fee_name": entry.get("fee_name"),
            "provider_name": entry.get("provider_name"),
            "section": entry.get("section"),
            "tolerance_category": entry.get("tolerance_category"),
        }

        row_hint: Optional[str] = None
        for candidate in [entry.get("cd_label"), entry.get("le_label"), entry.get("fee_name")]:
            if not candidate:
                continue
            match = re.match(r"^\s*(\d{2})\b", candidate)
            if match:
                row_hint = match.group(1)
                break

        if diff_type == "reclassified_off_borrower":
            requests["loan_estimate"].append(
                {
                    **base_payload,
                    "label": entry.get("le_label"),
                    "amount": entry.get("le_amount"),
                    "diff_type": "decrease",
                    "doc_type": "loan_estimate",
                    "row_hint": row_hint,
                }
            )
            requests["closing_disclosure"].append(
                {
                    **base_payload,
                    "label": entry.get("cd_label"),
                    "amount": entry.get("reclassified_amount") or entry.get("cd_amount"),
                    "diff_type": "decrease",
                    "doc_type": "closing_disclosure",
                    "row_hint": row_hint,
                }
            )
            continue

        if diff_type == "missing_on_cd":
            payload = {
                **base_payload,
                "label": entry.get("le_label"),
                "amount": entry.get("le_amount"),
                "diff_type": diff_type,
                "doc_type": "loan_estimate",
                "row_hint": row_hint,
            }
            requests["loan_estimate"].append(payload)
        elif diff_type == "new_on_cd":
            payload = {
                **base_payload,
                "label": entry.get("cd_label"),
                "amount": entry.get("cd_amount"),
                "diff_type": diff_type,
                "doc_type": "closing_disclosure",
                "row_hint": row_hint,
            }
            requests["closing_disclosure"].append(payload)
        else:
            requests["loan_estimate"].append(
                {
                    **base_payload,
                    "label": entry.get("le_label"),
                    "amount": entry.get("le_amount"),
                    "diff_type": diff_type,
                    "doc_type": "loan_estimate",
                    "row_hint": row_hint,
                }
            )
            requests["closing_disclosure"].append(
                {
                    **base_payload,
                    "label": entry.get("cd_label"),
                    "amount": entry.get("cd_amount"),
                    "diff_type": diff_type,
                    "doc_type": "closing_disclosure",
                    "row_hint": row_hint,
                }
            )
    return requests


def _score_line_for_targets(
    line: Dict[str, Any],
    primary_targets: List[str],
    secondary_targets: List[str],
    amount_digits: Optional[str],
    *,
    page_width: Optional[float] = None,
    row_hint: Optional[str] = None,
    section_hint: Optional[str] = None,
    page_section_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
) -> float:
    score = 0.0
    fuzzy_text = line.get("fuzzy_text", "")
    norm_text = line.get("norm_text", "")

    for target in primary_targets:
        norm_target = _normalize_for_fuzz(target)
        if not norm_target:
            continue
        ratio = fuzz.partial_ratio(norm_target, fuzzy_text)
        if ratio > score:
            score = ratio

        target_tokens = _tokenize_text(target)
        if target_tokens and line.get("tokens"):
            token_hits = sum(1 for token in target_tokens if token in line["tokens"])
            if token_hits:
                score += min(20, token_hits * 6)

    for secondary in secondary_targets:
        norm_secondary = _normalize_for_fuzz(secondary)
        if not norm_secondary:
            continue
        ratio = fuzz.partial_ratio(norm_secondary, fuzzy_text)
        score = max(score, ratio * 0.85)

    if amount_digits and amount_digits in (line.get("digits") or ""):
        score += 25
        if page_width and page_width > 0:
            right_ratio = (line.get("x1", 0.0) / page_width) if page_width else 0.0
            if right_ratio >= 0.7:
                score += 12

    if row_hint and row_hint in line.get("tokens", []):
        score += 10

    if section_hint and page_section_ranges:
        rng = page_section_ranges.get(section_hint.upper())
        mid = line.get("mid_y")
        if rng and mid is not None:
            if rng[0] - 6 <= mid <= rng[1] + 6:
                score += 12
            else:
                score -= 12

    # penalty if no primary match context
    if score < 50 and not amount_digits:
        score *= 0.8

    return score


def _find_best_line_match(
    pages: List[Dict[str, Any]],
    primary_targets: List[str],
    secondary_targets: List[str],
    amount_digits: Optional[str],
    *,
    section_hint: Optional[str] = None,
    row_hint: Optional[str] = None,
    min_score: float = 60.0,
) -> Optional[Dict[str, Any]]:
    best: Optional[Dict[str, Any]] = None
    for page in pages:
        for line in page["lines"]:
            if not line.get("norm_text"):
                continue
            score = _score_line_for_targets(
                line,
                primary_targets,
                secondary_targets,
                amount_digits,
                page_width=page.get("width"),
                row_hint=row_hint,
                section_hint=section_hint,
                page_section_ranges=page.get("section_ranges"),
            )

            if score < min_score:
                continue

            if best is None or score > best["score"]:
                best = {
                    "score": score,
                    "page_index": page["index"],
                    "line": line,
                    "page": page,
                }
    return best


def _build_annotations(
    pdf_path: Path,
    requests: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    pages = _extract_pdf_pages(pdf_path)
    annotations: List[Dict[str, Any]] = []

    def locate_amount_line(page: Dict[str, Any], base_line: Dict[str, Any], amount_digits: Optional[str]):
        if not amount_digits:
            return None
        target_mid = base_line.get("mid_y")
        if target_mid is None:
            return None
        for candidate in page["lines"]:
            if candidate is base_line:
                continue
            if amount_digits not in (candidate.get("digits") or ""):
                continue
            candidate_mid = candidate.get("mid_y")
            if candidate_mid is None:
                continue
            if abs(candidate_mid - target_mid) <= 3.5:
                return candidate
        return None

    for request in requests:
        label = request.get("label") or request.get("fee_name")
        if not label:
            continue
        amount_digits = _normalize_amount_digits(request.get("amount"))
        primary_targets = [request.get("label"), request.get("fee_name")]
        secondary_targets = [
            request.get("provider_name"),
            f"section {request.get('section')}" if request.get("section") else "",
            request.get("section"),
            request.get("tolerance_category"),
        ]
        match = _find_best_line_match(
            pages,
            [t for t in primary_targets if t],
            [t for t in secondary_targets if t],
            amount_digits,
            section_hint=request.get("section"),
            row_hint=request.get("row_hint"),
        )
        if not match and amount_digits:
            match = _find_best_line_match(
                pages,
                [],
                [],
                amount_digits,
                section_hint=request.get("section"),
                row_hint=request.get("row_hint"),
                min_score=35,
            )
        if not match:
            continue

        amount_line = locate_amount_line(match["page"], match["line"], amount_digits)

        color_info = _resolve_color(request["doc_type"], request["diff_type"])

        line = match["line"]
        page_height = match["page"]["height"]
        padding = 2.5
        x0 = line["x0"]
        x1 = line["x1"]
        top = line["top"]
        bottom = line["bottom"]
        if amount_line:
            x0 = min(x0, amount_line["x0"])
            x1 = max(x1, amount_line["x1"])
            top = min(top, amount_line["top"])
            bottom = max(bottom, amount_line["bottom"])
        x0 = max(0.0, x0 - padding)
        x1 = min(match["page"]["width"], x1 + padding)
        top = max(0.0, top - padding)
        bottom = min(match["page"]["height"], bottom + padding)
        width = x1 - x0
        height = bottom - top
        y0 = page_height - bottom

        annotations.append(
            {
                "page_index": match["page_index"],
                "x0": x0,
                "y0": y0,
                "width": width,
                "height": height,
                "color": color_info["rgb"],
                "color_hex": color_info["hex"],
                "diff_type": request["diff_type"],
                "label": label,
            }
        )

    return annotations, pages


def _draw_annotations(
    source_pdf: Path,
    annotations: List[Dict[str, Any]],
    pages_meta: List[Dict[str, Any]],
    output_pdf: Path,
) -> None:
    reader = PdfReader(str(source_pdf))
    writer = PdfWriter()
    grouped: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for annotation in annotations:
        grouped[annotation["page_index"]].append(annotation)

    for index, page in enumerate(reader.pages):
        boxes = grouped.get(index)
        if boxes:
            packet = io.BytesIO()
            page_meta = pages_meta[index]
            canv = canvas.Canvas(packet, pagesize=(page_meta["width"], page_meta["height"]))
            for box in boxes:
                canv.setStrokeColorRGB(*box["color"])
                canv.setLineWidth(1.8)
                canv.rect(box["x0"], box["y0"], box["width"], box["height"], fill=0, stroke=1)
            canv.save()
            packet.seek(0)
            overlay = PdfReader(packet)
            page.merge_page(overlay.pages[0])
        writer.add_page(page)

    with output_pdf.open("wb") as buffer:
        writer.write(buffer)


def generate_pdf_highlights(
    le_pdf_path: Optional[str],
    cd_pdf_path: Optional[str],
    diff_summary: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not diff_summary:
        return None

    requests = _build_highlight_requests(diff_summary)
    bundle: Dict[str, Any] = {
        "legend": {
            key: {"description": config["description"], "color": config["hex"]}
            for key, config in PDF_COLOR_SCHEME.items()
        }
    }

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if le_pdf_path and requests["loan_estimate"]:
        source_path = Path(le_pdf_path)
        output_path = source_path.with_name(f"{source_path.stem}_annotated_LE_{timestamp}.pdf")
        annotations, pages_meta = _build_annotations(source_path, requests["loan_estimate"])
        if annotations:
            _draw_annotations(source_path, annotations, pages_meta, output_path)
            bundle["loan_estimate"] = {
                "source_pdf_path": str(source_path),
                "highlighted_pdf_path": str(output_path),
                "page_count": len(pages_meta),
                "annotation_count": len(annotations),
                "generated_at": datetime.now().isoformat(),
            }

    if cd_pdf_path and requests["closing_disclosure"]:
        source_path = Path(cd_pdf_path)
        output_path = source_path.with_name(f"{source_path.stem}_annotated_CD_{timestamp}.pdf")
        annotations, pages_meta = _build_annotations(source_path, requests["closing_disclosure"])
        if annotations:
            _draw_annotations(source_path, annotations, pages_meta, output_path)
            bundle["closing_disclosure"] = {
                "source_pdf_path": str(source_path),
                "highlighted_pdf_path": str(output_path),
                "page_count": len(pages_meta),
                "annotation_count": len(annotations),
                "generated_at": datetime.now().isoformat(),
            }

    if not bundle.get("loan_estimate") and not bundle.get("closing_disclosure"):
        return None

    return bundle


async def ai_match_fees(
    le_record: dict,
    cd_record: dict,
    gemini_model: str = "gemini-2.5-pro",
) -> dict:
    """
    Use AI to intelligently match and normalize fees between LE and CD
    """
    try:
        prompt_data = {
            "loan_estimate": {
                "section_A": le_record.get("closing_cost_details", {})
                .get("loan_costs", {})
                .get("A", {})
                .get("items", []),
                "section_B": le_record.get("closing_cost_details", {})
                .get("loan_costs", {})
                .get("B", {})
                .get("items", []),
                "section_C": le_record.get("closing_cost_details", {})
                .get("loan_costs", {})
                .get("C", {})
                .get("items", []),
                "section_E": le_record.get("closing_cost_details", {})
                .get("other_costs", {})
                .get("E", {})
                .get("items", []),
                "section_F": le_record.get("closing_cost_details", {})
                .get("other_costs", {})
                .get("F", {})
                .get("items", []),
                "section_G": le_record.get("closing_cost_details", {})
                .get("other_costs", {})
                .get("G", {})
                .get("items", []),
                "section_H": le_record.get("closing_cost_details", {})
                .get("other_costs", {})
                .get("H", {})
                .get("items", []),
            },
            "closing_disclosure": {
                "section_A": cd_record.get("closing_cost_details", {})
                .get("loan_costs", {})
                .get("A", {})
                .get("items", []),
                "section_B": cd_record.get("closing_cost_details", {})
                .get("loan_costs", {})
                .get("B", {})
                .get("items", []),
                "section_C": cd_record.get("closing_cost_details", {})
                .get("loan_costs", {})
                .get("C", {})
                .get("items", []),
                "section_E": cd_record.get("closing_cost_details", {})
                .get("other_costs", {})
                .get("E", {})
                .get("items", []),
                "section_F": cd_record.get("closing_cost_details", {})
                .get("other_costs", {})
                .get("F", {})
                .get("items", []),
                "section_G": cd_record.get("closing_cost_details", {})
                .get("other_costs", {})
                .get("G", {})
                .get("items", []),
                "section_H": cd_record.get("closing_cost_details", {})
                .get("other_costs", {})
                .get("H", {})
                .get("items", []),
            },
        }

        llm = ChatGoogleGenerativeAI(model=gemini_model, temperature=0.0)
        structured_llm = llm.with_structured_output(
            TRIDComparison, method="function_calling"
        )

        prompt = f"""Match the BORROWER-PAID fees between Loan Estimate and Closing Disclosure.

LOAN ESTIMATE FEES (all borrower-paid):
{json.dumps(prompt_data["loan_estimate"], indent=2)}

CLOSING DISCLOSURE FEES (filter for borrower-paid only):
{json.dumps(prompt_data["closing_disclosure"], indent=2)}

INSTRUCTIONS:
1. For LE: Use the "amount" field directly (all LE fees are borrower-paid)
2. For CD: ONLY include items where sub_label contains "borrower_paid"
3. For CD: SUM the amounts from "borrower_paid_at_closing" + "borrower_paid_before_closing" for each fee
4. Mark is_new=true if fee appears in CD but not LE
5. Exclude any fees with null or zero borrower amounts
6. Leave summary as empty dict {{}}

Return a TRIDComparison with matched_fees list and empty summary.
"""

        result: TRIDComparison = await run_in_threadpool(
            structured_llm.invoke,
            [
                SystemMessage(content=MATCHING_SYSTEM),
                HumanMessage(content=prompt),
            ],
        )

        result_dict = result.dict()
        if not isinstance(result_dict.get("summary"), dict):
            result_dict["summary"] = {}

        matched_fee_dicts: List[Dict[str, Any]] = []
        for fee in result_dict.get("matched_fees", []):
            fee_dict = fee if isinstance(fee, dict) else fee.dict()  # type: ignore[arg-type]
            chosen_flag = fee_dict.get("chosen_from_list")
            if chosen_flag is None:
                if fee_dict.get("le_amount") is None:
                    chosen_flag = False
                elif float(fee_dict.get("match_confidence") or 0.0) < 0.6:
                    chosen_flag = False
                else:
                    chosen_flag = True
            fee_dict["chosen_from_list"] = chosen_flag
            fee_dict["changed_circumstance"] = bool(fee_dict.get("changed_circumstance"))
            tolerance = classify_fee_tolerance(
                fee_dict.get("section"),
                fee_dict.get("le_label") or fee_dict.get("cd_label") or fee_dict.get("fee_name"),
                fee_dict.get("chosen_from_list"),
                fee_dict.get("changed_circumstance"),
            )
            fee_dict["tolerance_category"] = tolerance
            matched_fee_dicts.append(fee_dict)

        cd_index = _build_cd_label_index(cd_record)

        def _mark_reclassified_off_borrower(matched: List[Dict[str, Any]]) -> None:
            for entry in matched:
                if entry.get("le_amount") is None or entry.get("cd_amount") is not None:
                    continue
                section = (entry.get("section") or "").upper()
                if not section:
                    continue
                label = entry.get("le_label") or entry.get("cd_label") or entry.get("fee_name")
                if not label:
                    continue
                key = f"{section}:{_normalize_label_for_key(label)}"
                cd_entry = cd_index.get(key)
                if not cd_entry:
                    norm_target = _normalize_label_for_key(label)
                    best_key: Optional[str] = None
                    best_score = 0
                    for idx_key, idx_entry in cd_index.items():
                        if not idx_key.startswith(f"{section}:"):
                            continue
                        score = fuzz.token_set_ratio(norm_target, idx_key.split(":", 1)[1])
                        if score > best_score:
                            best_score = score
                            best_key = idx_key
                    if best_key and best_score >= 80:
                        cd_entry = cd_index.get(best_key)
                if not cd_entry:
                    continue
                if cd_entry["seller"] > 0:
                    reclass_dest = "seller"
                elif cd_entry["other"] > 0:
                    reclass_dest = "other"
                else:
                    continue

                entry["reclassified_to"] = reclass_dest
                entry["reclassified_amount"] = cd_entry[reclass_dest]
                if cd_entry.get("label"):
                    entry["cd_label"] = cd_entry["label"]

        _mark_reclassified_off_borrower(matched_fee_dicts)

        result_dict["matched_fees"] = matched_fee_dicts

        tolerance_metrics = compute_tolerance_metrics(matched_fee_dicts)
        result_dict["summary"]["tolerance_summary"] = tolerance_metrics["bucket_totals"]
        result_dict["summary"]["ten_percent_test"] = tolerance_metrics["ten_percent_test"]
        if tolerance_metrics["ten_percent_test"]["cure_required"] > 0:
            result_dict["summary"]["lender_credit_recommendation"] = {
                "recommended_credit": tolerance_metrics["ten_percent_test"]["cure_required"],
                "note": "Apply lender credit to cure 10% tolerance excess.",
            }

        result_dict["diff_summary"] = build_fee_diff_summary(matched_fee_dicts)

        return result_dict

    except Exception as e:  # noqa: BLE001
        print(f"AI matching failed: {e}")
        return {
            "matched_fees": [],
            "summary": {},
            "processed_at": datetime.now().isoformat(),
            "diff_summary": [],
        }


async def generate_financial_profile_summary(
    le_data: Optional[dict],
    cd_data: Optional[dict],
    trid_comparison: Optional[dict],
    gemini_model: str,
) -> dict:
    """Generate comprehensive financial profile summary using AI"""
    try:
        llm = ChatGoogleGenerativeAI(model=gemini_model, temperature=0.3)
        structured_llm = llm.with_structured_output(
            FinancialProfileSummary, method="function_calling"
        )

        prompt = f"""Analyze the following loan documents and TRID comparison to generate a comprehensive financial profile summary.

LOAN ESTIMATE DATA:
{json.dumps(le_data, indent=2) if le_data else "Not provided"}

CLOSING DISCLOSURE DATA:
{json.dumps(cd_data, indent=2) if cd_data else "Not provided"}

TRID COMPARISON:
{json.dumps(trid_comparison, indent=2) if trid_comparison else "Not provided"}

Provide a comprehensive analysis covering:
1. Borrower Overview: Who are the borrowers and what property are they purchasing?
2. Loan Overview: What type of loan, its purpose, and key terms (amount, rate, term)?
3. Cost Analysis: Total closing costs, cash to close, and breakdown of major expenses
4. TRID Compliance: Any tolerance violations? Which fees changed and why?
5. Key Changes: What are the most significant changes from LE to CD?
6. Recommendations: Any red flags or concerns the borrower should be aware of?
7. Risk Assessment: Overall assessment of the loan's risk profile

Be specific with numbers and provide actionable insights."""

        result: FinancialProfileSummary = await run_in_threadpool(
            structured_llm.invoke,
            [
                SystemMessage(
                    content="You are an expert mortgage analyst providing comprehensive loan analysis."
                ),
                HumanMessage(content=prompt),
            ],
        )

        return result.dict()

    except Exception as e:  # noqa: BLE001
        print(f"Financial profile summary generation failed: {e}")
        return {
            "borrower_overview": "Analysis not available",
            "loan_overview": "Analysis not available",
            "cost_analysis": "Analysis not available",
            "trid_compliance": "Analysis not available",
            "key_changes": [],
            "recommendations": [],
            "risk_assessment": "Analysis not available",
            "generated_at": datetime.now().isoformat(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# 4) LLM chain builders and helpers

SYSTEM = """You are a meticulous extraction system.
Extract ONLY factual values present in the user's Loan Estimate or Closing Disclosure markdown.
- Do NOT invent values. Use null for missing fields.
- Money as numbers (no $ or commas). Dates ISO-8601 if present.
- Map A..J totals to correct sections.
- For CLOSING DISCLOSURE (Page 2 loan/other costs): for each fee line item set
  `sub_label` to one of: borrower_paid_at_closing, borrower_paid_before_closing,
  seller_paid_at_closing, seller_paid_before_closing, paid_by_others.
  Also set `payer`/`timing` accordingly (derived automatically if omitted).
- For LOAN ESTIMATE docs, leave sub_label/payer/timing null.
Return ONLY the structured JSON object—no prose.
"""


def build_structured_chain(
    model_name: str = "gemini-2.5-pro", temperature: float = 0.0
):
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
    structured_llm = llm.with_structured_output(
        LoanEstimateRecord, method="function_calling"
    )
    chain = (
        {
            "sys": RunnableLambda(lambda x: SYSTEM),
            "md": RunnableLambda(lambda x: x["markdown"]),
            "meta": RunnableLambda(lambda x: x.get("meta", {})),
        }
        | RunnableLambda(
            lambda x: [
                SystemMessage(content=x["sys"]),
                HumanMessage(
                    content=(
                        "Extract the following Loan Estimate/Closing Disclosure markdown into the JSON schema.\n\n"
                        f"### SOURCE_META\n{json.dumps(x['meta'])}\n\n"
                        f"### MARKDOWN\n{x['md']}\n"
                    )
                ),
            ]
        )
        | structured_llm
    )
    return chain


def build_fallback_json_chain(
    model_name: str = "gemini-2.5-pro", temperature: float = 0.0
):
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        response_mime_type="application/json",
    )
    chain = (
        {
            "sys": RunnableLambda(lambda x: SYSTEM),
            "md": RunnableLambda(lambda x: x["markdown"]),
            "meta": RunnableLambda(lambda x: x.get("meta", {})),
        }
        | RunnableLambda(
            lambda x: [
                SystemMessage(content=x["sys"]),
                HumanMessage(
                    content=(
                        "Return ONLY valid JSON for the schema (no prose).\n\n"
                        f"### SOURCE_META\n{json.dumps(x['meta'])}\n\n"
                        f"### MARKDOWN\n{x['md']}\n"
                    )
                ),
            ]
        )
        | llm
    )
    return chain


async def extract_json_from_markdown(
    markdown_text: str,
    source_file: Optional[str],
    gemini_model: str,
) -> dict:
    try:
        chain = build_structured_chain(model_name=gemini_model)
        record: LoanEstimateRecord = await run_in_threadpool(
            chain.invoke, {"markdown": markdown_text, "meta": {"source_file": source_file}}
        )
        data = record.dict()
        data.setdefault("meta", {})
        data["meta"]["source_file"] = source_file
        return data
    except ChatGoogleGenerativeAIError:
        chain = build_fallback_json_chain(model_name=gemini_model)
        raw = await run_in_threadpool(
            chain.invoke, {"markdown": markdown_text, "meta": {"source_file": source_file}}
        )
        raw_text = getattr(raw, "content", str(raw))
        try:
            obj = json.loads(raw_text)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Gemini JSON parse failed: {e}") from e
        try:
            record = LoanEstimateRecord(**obj)
            data = record.dict()
            data.setdefault("meta", {})
            data["meta"]["source_file"] = source_file
            return data
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Pydantic validation failed: {e}") from e


# LandingAI PDF → markdown
def pdf_to_markdown(pdf_path: Path, landing_model: str = "dpt-2-latest") -> str:
    client = LandingAIADE()
    response = client.parse(document=pdf_path, model=landing_model)
    return response.markdown


# ──────────────────────────────────────────────────────────────────────────────
# 5) Persistence helpers

def ensure_storage_dir() -> Path:
    storage = Path(os.getenv("STORAGE_DIR", "./storage")).resolve()
    storage.mkdir(parents=True, exist_ok=True)
    return storage


SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def safe_stem(filename: str) -> str:
    stem = Path(filename).stem
    stem = SAFE_CHARS.sub("_", stem).strip("_")
    if not stem:
        stem = "document"
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stem}-{ts}"


async def process_file(
    file: UploadFile,
    landing_model: str,
    gemini_model: str,
    save_markdown: bool,
) -> dict:
    storage = ensure_storage_dir()
    base = safe_stem(file.filename)

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail=f"Empty file: {file.filename}")

    pdf_storage_path = storage / f"{base}.pdf"
    pdf_storage_path.write_bytes(pdf_bytes)

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / file.filename
        pdf_path.write_bytes(pdf_bytes)

        # 1) PDF -> Markdown
        markdown_text = await run_in_threadpool(
            pdf_to_markdown, pdf_path, landing_model
        )

        # 2) Markdown -> JSON
        record = await extract_json_from_markdown(
            markdown_text=markdown_text,
            source_file=file.filename,
            gemini_model=gemini_model,
        )

    # 3) Persist outputs
    json_path = storage / f"{base}.json"
    json_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md_path = None
    if save_markdown:
        md_path = storage / f"{base}.md"
        md_path.write_text(markdown_text, encoding="utf-8")

    return {
        "source_file": file.filename,
        "json_path": str(json_path),
        "markdown_path": str(md_path) if md_path else None,
        "json_data": record,
        "pdf_path": str(pdf_storage_path),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 6) FastAPI app

app = FastAPI(title="Fintrid TRID Analyzer API", version="1.0.0")

# CORS for your Next.js frontend (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Fintrid TRID Analyzer API",
        "version": "1.0.0",
        "status": "healthy",
    }


async def progress_generator(
    files: List[UploadFile],
    landing_model: str,
    gemini_model: str,
    save_markdown: bool,
    run_ai_matching: bool,
    generate_summary: bool,
) -> AsyncIterator[str]:
    try:
        yield f"data: {json.dumps({'step': 'start', 'message': 'Starting document processing'})}\n\n"

        yield f"data: {json.dumps({'step': 'upload', 'message': f'Received {len(files)} document(s)'})}\n\n"

        yield (
            f"data: {json.dumps({'step': 'pdf_to_md', 'message': 'Converting PDFs to Markdown (parallel)'})}\n\n"
        )

        results = await asyncio.gather(
            *(process_file(f, landing_model, gemini_model, save_markdown) for f in files),
            return_exceptions=True,
        )

        outputs: List[dict] = []
        errors: List[str] = []

        for res in results:
            if isinstance(res, Exception):
                errors.append(str(res))
            else:
                outputs.append(res)

        if errors and not outputs:
            yield f"data: {json.dumps({'step': 'error', 'message': '; '.join(errors)})}\n\n"
            return

        yield f"data: {json.dumps({'step': 'extraction_complete', 'message': f'Extracted {len(outputs)} document(s)'})}\n\n"

        yield f"data: {json.dumps({'step': 'detecting', 'message': 'Detecting document types'})}\n\n"

        le_data: Optional[dict] = None
        cd_data: Optional[dict] = None
        le_pdf_path: Optional[str] = None
        cd_pdf_path: Optional[str] = None

        for output in outputs:
            doc_type = detect_document_type(output["json_data"])
            output["document_type"] = doc_type

            if doc_type == "loan_estimate":
                le_data = output["json_data"]
                le_pdf_path = output.get("pdf_path")
                source_file = output["source_file"]
                yield f"data: {json.dumps({'step': 'detection', 'message': f'Detected Loan Estimate: {source_file}'})}\n\n"
            elif doc_type == "closing_disclosure":
                cd_data = output["json_data"]
                cd_pdf_path = output.get("pdf_path")
                source_file = output["source_file"]
                yield f"data: {json.dumps({'step': 'detection', 'message': f'Detected Closing Disclosure: {source_file}'})}\n\n"
            else:
                source_file = output["source_file"]
                yield f"data: {json.dumps({'step': 'detection', 'message': f'Unknown document type: {source_file}'})}\n\n"

        trid_comparison: Optional[dict] = None
        if run_ai_matching and le_data and cd_data:
            yield f"data: {json.dumps({'step': 'ai_matching', 'message': 'AI matching borrower-paid fees'})}\n\n"

            try:
                trid_comparison = await ai_match_fees(
                    le_data, cd_data, gemini_model
                )

                fee_count = len(trid_comparison.get("matched_fees", []))
                yield f"data: {json.dumps({'step': 'ai_complete', 'message': f'Matched {fee_count} borrower-paid fees'})}\n\n"
            except Exception as match_error:  # noqa: BLE001
                errors.append(f"AI matching failed: {str(match_error)}")
                yield f"data: {json.dumps({'step': 'ai_error', 'message': str(match_error)})}\n\n"

        financial_summary: Optional[dict] = None
        if generate_summary and (le_data or cd_data):
            yield f"data: {json.dumps({'step': 'summary_generation', 'message': 'Generating comprehensive financial profile summary'})}\n\n"

            try:
                financial_summary = await generate_financial_profile_summary(
                    le_data, cd_data, trid_comparison, gemini_model
                )
                yield f"data: {json.dumps({'step': 'summary_complete', 'message': 'Financial profile summary generated'})}\n\n"
            except Exception as summary_error:  # noqa: BLE001
                errors.append(f"Summary generation failed: {str(summary_error)}")
                yield f"data: {json.dumps({'step': 'summary_error', 'message': str(summary_error)})}\n\n"

        if trid_comparison and (le_pdf_path or cd_pdf_path):
            yield f"data: {json.dumps({'step': 'pdf_highlight', 'message': 'Annotating PDFs with diff highlights'})}\n\n"
            try:
                pdf_highlights = await run_in_threadpool(
                    generate_pdf_highlights,
                    le_pdf_path,
                    cd_pdf_path,
                    trid_comparison.get("diff_summary"),
                )
                if pdf_highlights:
                    trid_comparison["pdf_highlights"] = pdf_highlights
                    yield f"data: {json.dumps({'step': 'pdf_highlight_complete', 'message': 'PDF highlights generated'})}\n\n"
                else:
                    yield f"data: {json.dumps({'step': 'pdf_highlight', 'message': 'No diff highlights needed'})}\n\n"
            except Exception as highlight_error:  # noqa: BLE001
                errors.append(f"PDF highlighting failed: {str(highlight_error)}")
                yield f"data: {json.dumps({'step': 'pdf_highlight_error', 'message': str(highlight_error)})}\n\n"

        pdf_report_path: Optional[str] = None
        if trid_comparison and (le_data or cd_data):
            try:
                yield f"data: {json.dumps({'step': 'report_generation', 'message': 'Generating TRID curated PDF report'})}\n\n"

                loan_meta = extract_loan_meta_from_responses(le_data, cd_data)

                storage_dir = ensure_storage_dir()
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                pdf_filename = f"trid_report_{timestamp}.pdf"
                pdf_report_path = str(storage_dir / pdf_filename)

                await run_in_threadpool(
                    build_trid_curated_report,
                    trid_comparison,
                    loan_meta,
                    pdf_report_path,
                )

                yield f"data: {json.dumps({'step': 'report_complete', 'message': f'PDF report generated: {pdf_filename}'})}\n\n"
            except Exception as report_error:  # noqa: BLE001
                errors.append(f"Report generation failed: {str(report_error)}")
                yield f"data: {json.dumps({'step': 'report_error', 'message': str(report_error)})}\n\n"

        payload = {
            "meta": {
                "pipeline": "landingai_pdf_to_md -> gemini_md_to_json -> document_detection -> ai_fee_matching -> pdf_report -> financial_summary",
                "landing_model": landing_model,
                "gemini_model": gemini_model,
                "saved_to": os.getenv("STORAGE_DIR", "./storage"),
                "ai_matching_enabled": run_ai_matching,
                "summary_generation_enabled": generate_summary,
                "pdf_report_path": pdf_report_path,
                "pdf_highlights_enabled": bool(trid_comparison and trid_comparison.get("pdf_highlights")),
            },
            "files": outputs,
            "trid_comparison": trid_comparison,
            "financial_summary": financial_summary,
            "errors": errors or None,
        }

        yield f"data: {json.dumps({'step': 'complete', 'message': 'Processing complete', 'payload': payload})}\n\n"

    except Exception as e:  # noqa: BLE001
        yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"


@app.post("/api/extract/stream")
async def extract_stream_endpoint(
    files: List[UploadFile] = File(
        ..., description="One or more PDF files (Loan Estimate and/or Closing Disclosure)"
    ),
    save_markdown: bool = Query(True),
    landing_model: str = Query("dpt-2-latest"),
    gemini_model: str = Query("gemini-2.5-pro"),
    run_ai_matching: bool = Query(
        True,
        description="Run AI-powered fee matching if both LE and CD are present",
    ),
    generate_summary: bool = Query(
        True, description="Generate comprehensive financial profile summary"
    ),
):
    if len(files) == 0:
        raise HTTPException(
            status_code=400, detail="Please upload at least one PDF file"
        )

    return StreamingResponse(
        progress_generator(
            files,
            landing_model,
            gemini_model,
            save_markdown,
            run_ai_matching,
            generate_summary,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/extract/pair", response_class=JSONResponse)
async def extract_pair_endpoint(
    files: List[UploadFile] = File(..., description="Exactly two PDF files"),
    save_markdown: bool = Query(
        True, description="Persist markdown alongside JSON"
    ),
    include_paths: bool = Query(True, description="Return saved file paths"),
    landing_model: str = Query("dpt-2-latest"),
    gemini_model: str = Query("gemini-2.5-pro"),
    run_ai_matching: bool = Query(True, description="Run AI-powered fee matching"),
):
    if len(files) != 2:
        raise HTTPException(
            status_code=400,
            detail="Please upload exactly two PDF files (files=...).",
        )

    try:
        # Run both in parallel
        results = await asyncio.gather(
            *(process_file(f, landing_model, gemini_model, save_markdown) for f in files),
            return_exceptions=True,
        )

        outputs: List[dict] = []
        errors: List[str] = []

        for res in results:
            if isinstance(res, Exception):
                errors.append(str(res))
            else:
                outputs.append(res)

        if errors and not outputs:
            raise HTTPException(
                status_code=500, detail="; ".join(errors)
            )

        # AI-powered fee matching (if both files processed successfully)
        trid_comparison: Optional[dict] = None
        if run_ai_matching and len(outputs) == 2:
            try:
                file1_data = outputs[0]["json_data"]
                file2_data = outputs[1]["json_data"]
                trid_comparison = await ai_match_fees(
                    file1_data, file2_data, gemini_model
                )
                print(
                    f"AI Matching completed: {len(trid_comparison.get('matched_fees', []))} fees matched"
                )
            except Exception as match_error:  # noqa: BLE001
                print(f"AI matching error: {match_error}")
                errors.append(f"AI matching failed: {str(match_error)}")

        payload = {
            "meta": {
                "pipeline": "landingai_pdf_to_md -> gemini_md_to_json -> ai_fee_matching",
                "landing_model": landing_model,
                "gemini_model": gemini_model,
                "saved_to": os.getenv("STORAGE_DIR", "./storage"),
                "ai_matching_enabled": run_ai_matching,
            },
            "files": outputs
            if include_paths
            else [{"source_file": o["source_file"]} for o in outputs],
            "trid_comparison": trid_comparison,
            "errors": errors or None,
        }
        return JSONResponse(payload)

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/extract", response_class=JSONResponse)
async def extract_single_endpoint(
    file: UploadFile = File(..., description="Single PDF file"),
    save_markdown: bool = Query(True),
    include_paths: bool = Query(True),
    landing_model: str = Query("dpt-2-latest"),
    gemini_model: str = Query("gemini-2.5-pro"),
):
    try:
        result = await process_file(file, landing_model, gemini_model, save_markdown)
        payload = {
            "meta": {
                "pipeline": "landingai_pdf_to_md -> gemini_md_to_json",
                "landing_model": landing_model,
                "gemini_model": gemini_model,
                "saved_to": os.getenv("STORAGE_DIR", "./storage"),
            },
            "file": result
            if include_paths
            else {"source_file": result["source_file"]},
        }
        return JSONResponse(payload)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e


# ──────────────────────────────────────────────────────────────────────────────
# 7) Main entry point (for running with uvicorn)

def main():
    """
    Main entry point for the Fintrid API server.
    Reads configuration from environment variables or uses defaults.
    """
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"
    log_level = os.getenv("API_LOG_LEVEL", "info")

    uvicorn.run(
        "fintrid_backend.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
