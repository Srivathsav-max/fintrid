# python extract_loan_estimate_gemini.py path/to/file.md
# or:    extract_loan_estimate_gemini.py path/to/folder out.jsonl

from __future__ import annotations
import json, sys
from pathlib import Path
from typing import List, Optional, Literal, Dict
from pydantic.v1 import BaseModel, Field, validator, conint, confloat
from typing import Optional, Literal

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI

# ---------- 1) Pydantic schema (matches the JSON you approved) ----------
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
    type: Optional[Literal["conventional","fha","va","other"]] = None
    purpose: Optional[Literal["purchase","refinance","construction","other"]] = None
    product: Optional[Literal["fixed_rate","adjustable_rate","other"]] = None
    term_months: Optional[int] = Field(None, description="Total months, e.g., 360 for 30 years")
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

    # NEW — only populated for Closing Disclosure docs
    sub_label: Optional[SubLabel] = None

    # Parsed convenience fields (derived from sub_label when missing)
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
    servicing_intent: Optional[Literal["service","transfer","unknown"]] = None

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

    # Keep A..J math consistent if items exist
    @validator("closing_cost_details", pre=False, always=False)
    def recompute_totals(cls, v: ClosingCostDetails | None) -> ClosingCostDetails | None:
        if not v or not v.loan_costs or not v.other_costs:
            return v
        A = v.loan_costs.A.total if v.loan_costs.A and v.loan_costs.A.total is not None else None
        B = v.loan_costs.B.total if v.loan_costs.B and v.loan_costs.B.total is not None else None
        C = v.loan_costs.C.total if v.loan_costs.C and v.loan_costs.C.total is not None else None
        if all(x is not None for x in [A, B, C]):
            v.loan_costs.D_total = round(float(A) + float(B) + float(C), 2)
        E = v.other_costs.E.total if v.other_costs.E else None
        F = v.other_costs.F.total if v.other_costs.F else None
        G = v.other_costs.G.total if v.other_costs.G else None
        H = v.other_costs.H.total if v.other_costs.H else None
        if all(x is not None for x in [E, F, G, H]):
            v.other_costs.I_total = round(float(E) + float(F) + float(G) + float(H), 2)
        if v.loan_costs and v.other_costs and v.loan_costs.D_total is not None and v.other_costs.I_total is not None:
            v.other_costs.J_total = round(float(v.loan_costs.D_total) + float(v.other_costs.I_total), 2)
        return v

# ---------- 2) Build Gemini chain with native JSON schema ----------
SYSTEM = """You are a meticulous extraction system.
Extract ONLY factual values present in the user's Loan Estimate markdown.
- Do NOT invent values. Use null for missing fields.
- Money as numbers (no $ or commas). Dates ISO-8601 if present.
- Map A..J totals to correct sections.
Return ONLY the structured JSON object—no prose.
"""

def build_chain(model_name: str = "gemini-2.5-pro", temperature: float = 0.0):
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
    # ⬇️ Use tools/function-calling instead of json_schema
    structured_llm = llm.with_structured_output(LoanEstimateRecord, method="function_calling")
    chain = (
        {
            "sys": RunnableLambda(lambda x: SYSTEM),
            "md": RunnableLambda(lambda x: x["markdown"]),
            "meta": RunnableLambda(lambda x: x.get("meta", {})),
        }
        | RunnableLambda(lambda x: [
            SystemMessage(content=x["sys"]),
            HumanMessage(content=(
                "Extract the following Loan Estimate markdown into the JSON schema.\n\n"
                f"### SOURCE_META\n{json.dumps(x['meta'])}\n\n"
                f"### MARKDOWN\n{x['md']}\n"
            ))
        ])
        | structured_llm
    )
    return chain

def extract_one(markdown_text: str, source_file: Optional[str] = None) -> dict:
    record: LoanEstimateRecord = build_chain().invoke(
        {"markdown": markdown_text, "meta": {"source_file": source_file}}
    )
    data = record.dict()
    data.setdefault("meta", {})
    data["meta"]["source_file"] = source_file
    return data

def extract_folder(input_path: str, output_jsonl: str = "loan_estimates.jsonl", glob: str = "*.md"):
    p = Path(input_path)
    out = Path(output_jsonl)
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for md_file in sorted(p.rglob(glob)):
            md = md_file.read_text(encoding="utf-8")
            obj = extract_one(md, source_file=str(md_file))
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            n += 1
    print(f"Wrote {n} records to {out}")

if __name__ == "__main__":
    if len(sys.argv) >= 2 and Path(sys.argv[1]).is_file():
        in_path = Path(sys.argv[1])
        out_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else Path("Loan_estimate.json")

        md = in_path.read_text(encoding="utf-8")
        obj = extract_one(md, source_file=str(in_path))

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        print(f"Saved → {out_path}")

    elif len(sys.argv) >= 2 and Path(sys.argv[1]).is_dir():
        input_dir = sys.argv[1]
        output = sys.argv[2] if len(sys.argv) >= 3 else "loan_estimates.jsonl"
        extract_folder(input_dir, output_jsonl=output)

    else:
        print("Usage:\n  python extract_loan_estimate_gemini.py path/to/file.md [out.json]\n"
              "  python extract_loan_estimate_gemini.py path/to/folder [out.jsonl]")