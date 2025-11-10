# Fintrid – AI-Powered TRID Analysis Platform

Fintrid is an end-to-end platform for analyzing Loan Estimates (LE) and Closing Disclosures (CD) with AI to ensure TRID (TILA-RESPA Integrated Disclosure) compliance, catch costly tolerance violations, and explain complex loan terms in plain English.

> **Disclaimer:** Fintrid is a decision-support and review tool. It does **not** provide legal advice and does not replace required regulatory reviews.

---

## 🇺🇸 The Problem We’re Solving

In the US mortgage market, TRID compliance is **high-stakes and painful**:

* **Manual, spreadsheet-driven reviews**
  Compliance and closing teams still compare LEs and CDs by hand, line by line, across multiple pages and versions.

* **Fee label chaos**
  The same fee appears as *“Appraisal Fee,” “01 Appraisal to ABC Appraisers,”* or “Appraisal – ABC,” making automated matching brittle and error-prone.

* **Tolerance violations = real money**
  Missing a zero-tolerance or 10%-tolerance breach can lead to:

  * Cure/credits at closing
  * Post-closing remediation
  * Regulatory and investor findings

* **No single source of truth**
  Data lives in PDFs, emails, LOS exports, and ad-hoc Excel files. Every team “rebuilds” the same comparison.

* **Borrower communication is hard**
  Borrowers don’t understand why fees changed from LE to CD, and loan officers lack a clear, client-friendly explanation.

Fintrid exists to **automate this entire workflow**, reduce risk, and give lenders and auditors a clear, defensible, AI-assisted comparison between LE and CD.

---

## ✅ What Fintrid Does

**In one pipeline, Fintrid:**

1. **Ingests mortgage PDFs** (Loan Estimates & Closing Disclosures)
2. **Extracts structured data** using LandingAI + Google Gemini
3. **Detects document type** (LE vs CD) automatically
4. **AI-matches borrower-paid fees** between LE and CD (even with messy labels)
5. **Checks TRID tolerance rules** (zero, 10%, unlimited)
6. **Builds curated PDF reports** for compliance & audit
7. **Generates an AI-written financial profile summary** that explains the loan, changes, and risks


## ✨ Key Features

### 🧾 Document Processing

* **PDF → Markdown → JSON**

  * Uses **LandingAI ADE** to convert PDFs into markdown
  * Uses **Google Gemini** (via LangChain) to extract into strict Pydantic models
* **Automatic document type detection**

  * Distinguishes Loan Estimates from Closing Disclosures based on fee structure
* **Parallel processing**

  * Handles multiple documents at once with async FastAPI endpoints

### 🧠 AI-Powered Analysis

* **Intelligent fee matching**

  * Matches **borrower-paid fees only** between LE and CD
  * Handles noisy labels, prefixes (e.g., “01”), and provider names
  * Computes a **match confidence score** per fee
* **TRID tolerance categorization**

  * Section A, B → **zero** tolerance
  * Section C, E → **10%** tolerance
  * Sections F, G, H → **unlimited** tolerance
* **Financial profile summary (optional)**

  * AI-generated narrative covering:

    * Borrower & property overview
    * Loan terms & structure
    * Cost and cash-to-close analysis
    * TRID compliance and tolerance breaches
    * Key changes from LE → CD
    * Risk & recommendations

### 📊 Reporting & UX

* **Curated TRID PDF report**

  * Detailed fee comparison table (LE vs CD)
  * Highlighted tolerance category & violation status
  * Borrower-friendly explanation sections
* **Interactive web UI (frontend)**

  * Upload and track processing in real time via **SSE streaming**
  * Explore fee comparison tables
  * View summary cards and analyticsx

## 🛠️ Tech Stack

### Backend

* **Framework**: FastAPI (async, type-safe)
* **AI / LLM Orchestration**:

  * LandingAI ADE – PDF parsing
  * Google Gemini 2.5 Pro – structured extraction & analysis
  * LangChain – chains & structured outputs
* **Data Modeling**: Pydantic v1 (LoanEstimateRecord, TRIDComparison, etc.)
* **Reporting**: ReportLab (PDF generation via `generate_trid_curated_report.py`)
* **Storage / DB**:

  * File system storage for JSON/markdown/PDF
  * PostgreSQL (via Drizzle ORM from the frontend)

### Frontend

* **Framework**: Next.js 16 (App Router) + React 19
* **Styling**: Tailwind CSS 4, shadcn/ui
* **Data Tables**: Handsontable, TanStack Table
* **ORM**: Drizzle (TypeScript models over PostgreSQL)
* **Tooling**: Biome for linting & formatting

## 📋 Prerequisites

* **Python**: 3.11+
* **Node.js**: 18+ (or Bun)
* **PostgreSQL**: 14+
* **API keys**:

  * `LANDINGAI_API_KEY`
  * `GOOGLE_API_KEY` (Gemini)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd fintrid
```

### 2. Backend Setup

```bash
cd backend

# Recommended: uv
uv sync

# Or traditional venv + pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend

# Using Bun
bun install
# or
npm install
# or
yarn install
```

### 4. Environment Variables

Create `.env` in `backend/`:

```env
# API
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=false
API_LOG_LEVEL=info

# CORS
CORS_ALLOW_ORIGINS=http://localhost:3000

# Storage
STORAGE_DIR=./storage

# LandingAI
LANDINGAI_API_KEY=your_landingai_api_key

# Google Gemini
GOOGLE_API_KEY=your_google_gemini_api_key
```

Create `.env.local` in `frontend/`:

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/fintrid
```

### 5. Database (Frontend)

```bash
cd frontend

bun run db:generate
bun run db:push

# Optional: Drizzle Studio
bun run db:studio
```

### 6. Run Backend

```bash
cd backend
uv run fintrid-api
# or
python -m fintrid_backend.main
```

Backend:

* API root: [http://localhost:8000](http://localhost:8000)
* Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)
* ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 7. Run Frontend

```bash
cd frontend
bun dev
# or
npm run dev
```

Frontend: [http://localhost:3000](http://localhost:3000)

---

## 📡 Core API Endpoints

### `POST /api/extract/stream`

* Upload **one or more** PDFs (LE and/or CD)
* Server-Sent Events (SSE) stream with steps such as:

  * `start`, `pdf_to_md`, `extraction_complete`
  * `detecting`, `ai_matching`, `report_generation`, `summary_generation`
* Final event includes:

  * `files` (metadata)
  * `trid_comparison` (if LE & CD present)
  * `financial_summary` (if enabled)
  * `pdf_report_path`

### `POST /api/extract/pair`

* Expect **exactly two** PDF files (typically 1× LE, 1× CD)
* Returns JSON:

```jsonc
{
  "meta": { "...": "..." },
  "files": [ /* each with json_data & paths */ ],
  "trid_comparison": { /* matched_fees[], summary */ },
  "errors": []
}
```

### `POST /api/extract`

* Process a **single** PDF (for raw extraction use cases)
* Returns structured `LoanEstimateRecord` JSON

### Common Query Parameters

* `save_markdown` (bool, default: `true`) – persist intermediate `.md`
* `landing_model` (str, default: `"dpt-2-latest"`)
* `gemini_model` (str, default: `"gemini-2.5-pro"`)
* `run_ai_matching` (bool) – run TRID fee matching (if LE+CD present)
* `generate_summary` (bool) – generate financial profile summary

---

## 📁 Project Layout

```text
fintrid/
├── backend/
│   ├── src/
│   │   └── fintrid_backend/
│   │       ├── main.py                       # FastAPI app & endpoints
│   │       └── generate_trid_curated_report.py  # PDF report builder
│   ├── storage/                              # JSON, markdown, PDFs
│   ├── pyproject.toml
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx                      # Main upload / analysis page
│   │   │   ├── data/page.tsx                 # Data explorer page
│   │   │   └── api/
│   │   │       ├── upload/route.ts           # Upload proxy
│   │   │       └── trid-records/route.ts     # Persisted TRID records
│   │   ├── components/
│   │   │   ├── ui/                           # shadcn/ui primitives
│   │   │   ├── handsontable/                 # Spreadsheet-like tables
│   │   │   └── financial-summary-card.tsx
│   │   ├── lib/
│   │   │   ├── trid-transformer.ts           # Data transformation & mapping
│   │   │   └── trid-rules.ts                 # TRID tolerance logic
│   │   ├── db/
│   │   │   ├── schema.ts                     # Drizzle schema
│   │   │   └── index.ts                      # DB client
│   │   └── types/
│   │       ├── trid.ts                       # TRID domain types
│   │       └── backend.ts                    # Backend API types
│   ├── package.json
│   └── drizzle.config.ts
│
└── README.md
```

---

## 🔄 Processing Pipeline (End-to-End)

1. **Upload** – User uploads LE and/or CD PDFs via UI
2. **LandingAI** – PDFs parsed into markdown
3. **Gemini Extraction** – Markdown → `LoanEstimateRecord` JSON (Pydantic-validated)
4. **Doc Detection** – Classify each record as LE, CD, or unknown
5. **AI Fee Matching** – Borrower-paid fees mapped from LE → CD (`TRIDComparison`)
6. **Tolerance Evaluation** – Zero / 10% / unlimited tolerance logic
7. **Curated PDF Report** – Generated with detailed tables & status
8. **Financial Summary** – Optional AI narrative for human-friendly review

---

## 🧪 Development Workflows

### Backend

```bash
cd backend

# Run with auto-reload
API_RELOAD=true uv run fintrid-api

# Tests (if configured)
pytest

# Lint / format (example)
black src/
ruff check src/
```

### Frontend

```bash
cd frontend

bun dev          # or npm run dev
bun run lint     # or npm run lint
bun run format   # or npm run format

# Database
bun run db:generate
bun run db:push
```

---

## 👥 Contributors

* **Jaya Raj Srivathsav Adari**
* **Abhishek Mamidipally**

---

Built with ❤️ for mortgage compliance teams, secondary marketing, auditors, and borrowers who deserve clarity.
