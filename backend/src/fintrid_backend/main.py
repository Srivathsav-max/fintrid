from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

# ---------- LandingAI (PDF -> Markdown) ----------
from landingai_ade import LandingAIADE

# ---------- Gemini / LangChain (Markdown -> JSON) ----------
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

# ---------- Pydantic v1 schema (your schema) ----------
from pydantic.v1 import BaseModel, Field, validator, conint, confloat

# ──────────────────────────────────────────────────────────────────────────────
# 1) Schema (unchanged from your working version, trimmed for brevity)
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

# ──────────────────────────────────────────────────────────────────────────────
# 2) LLM chain builders and helpers

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

def build_structured_chain(model_name: str = "gemini-2.5-pro", temperature: float = 0.0):
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
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
                "Extract the following Loan Estimate/Closing Disclosure markdown into the JSON schema.\n\n"
                f"### SOURCE_META\n{json.dumps(x['meta'])}\n\n"
                f"### MARKDOWN\n{x['md']}\n"
            ))
        ])
        | structured_llm
    )
    return chain

def build_fallback_json_chain(model_name: str = "gemini-2.5-pro", temperature: float = 0.0):
    # No function schema → plain JSON returned; we validate with Pydantic locally.
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
        | RunnableLambda(lambda x: [
            SystemMessage(content=x["sys"]),
            HumanMessage(content=(
                "Return ONLY valid JSON for the schema (no prose).\n\n"
                f"### SOURCE_META\n{json.dumps(x['meta'])}\n\n"
                f"### MARKDOWN\n{x['md']}\n"
            ))
        ])
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
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gemini JSON parse failed: {e}")
        try:
            record = LoanEstimateRecord(**obj)
            data = record.dict()
            data.setdefault("meta", {})
            data["meta"]["source_file"] = source_file
            return data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Pydantic validation failed: {e}")

# LandingAI PDF → markdown
def pdf_to_markdown(pdf_path: Path, landing_model: str = "dpt-2-latest") -> str:
    client = LandingAIADE()
    response = client.parse(document=pdf_path, model=landing_model)
    return response.markdown

# ──────────────────────────────────────────────────────────────────────────────
# 3) Persistence helpers

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

    # Save uploaded PDF to temp
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail=f"Empty file: {file.filename}")

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / file.filename
        pdf_path.write_bytes(pdf_bytes)

        # 1) PDF -> Markdown
        markdown_text = await run_in_threadpool(pdf_to_markdown, pdf_path, landing_model)

        # 2) Markdown -> JSON
        record = await extract_json_from_markdown(
            markdown_text=markdown_text,
            source_file=file.filename,
            gemini_model=gemini_model,
        )

    # 3) Persist outputs
    json_path = storage / f"{base}.json"
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = None
    if save_markdown:
        md_path = storage / f"{base}.md"
        md_path.write_text(markdown_text, encoding="utf-8")

    return {
        "source_file": file.filename,
        "json_path": str(json_path),
        "markdown_path": str(md_path) if md_path else None,
    }

# ──────────────────────────────────────────────────────────────────────────────
# 4) FastAPI app

load_dotenv()
app = FastAPI(title="Closing Docs Extractor API", version="1.0.0")

# CORS for your Next.js frontend (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/extract/pair", response_class=JSONResponse)
async def extract_pair_endpoint(
    files: List[UploadFile] = File(..., description="Exactly two PDF files"),
    save_markdown: bool = Query(True, description="Persist markdown alongside JSON"),
    include_paths: bool = Query(True, description="Return saved file paths"),
    landing_model: str = Query("dpt-2-latest"),
    gemini_model: str = Query("gemini-2.5-pro"),
):
    if len(files) != 2:
        raise HTTPException(status_code=400, detail="Please upload exactly two PDF files (files=...).")

    try:
        # Run both in parallel
        results = await asyncio.gather(
            *(process_file(f, landing_model, gemini_model, save_markdown) for f in files),
            return_exceptions=True,
        )

        outputs = []
        errors = []
        for res in results:
            if isinstance(res, Exception):
                errors.append(str(res))
            else:
                outputs.append(res)

        if errors and not outputs:
            raise HTTPException(status_code=500, detail="; ".join(errors))

        payload = {
            "meta": {
                "pipeline": "landingai_pdf_to_md -> gemini_md_to_json",
                "landing_model": landing_model,
                "gemini_model": gemini_model,
                "saved_to": os.getenv("STORAGE_DIR", "./storage"),
            },
            "files": outputs if include_paths else [{"source_file": o["source_file"]} for o in outputs],
            "errors": errors or None,
        }
        return JSONResponse(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Optional single-file endpoint (handy for debugging / future use)
@app.post("/api/extract", response_class=JSONResponse)
async def extract_single_endpoint(
    file: UploadFile = File(..., description="Single PDF file"),
    save_markdown: bool = Query(True),
    include_paths: bool = Query(True),
    landing_model: str = Query("dpt-2-latest"),
    gemini_model: str = Query("gemini-2.5-pro"),
):
    return await extract_pair_endpoint(
        files=[file, file],  # NOT ideal; reuse logic by wrapping below instead
        save_markdown=save_markdown,
        include_paths=include_paths,
        landing_model=landing_model,
        gemini_model=gemini_model,
    )