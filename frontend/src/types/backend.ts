export type Currency = number;

export interface LatePayment {
  late_after_days?: number | null;
  fee_pct_of_monthly_p_and_i?: number | null;
}

export interface RateLock {
  is_locked?: boolean | null;
  until?: string | null;
  timezone?: string | null;
}

export interface LoanCore {
  loan_id?: string | null;
  type?: "conventional" | "fha" | "va" | "other" | null;
  purpose?: "purchase" | "refinance" | "construction" | "other" | null;
  product?: "fixed_rate" | "adjustable_rate" | "other" | null;
  term_months?: number | null;
  rate_lock?: RateLock | null;
  costs_expire_at?: Record<string, string | null> | null;
}

export interface Feature {
  has?: boolean | null;
  amount?: Currency | null;
  due_month?: number | null;
  note?: string | null;
}

export interface LoanTerms {
  loan_amount?: Currency | null;
  interest_rate_pct?: number | null;
  monthly_principal_interest?: Currency | null;
  features?: Record<string, Feature> | null;
}

export interface PeriodPayment {
  period_label?: string | null;
  from_month?: number | null;
  to_month?: number | null;
  principal_interest?: Currency | null;
  mortgage_insurance?: Currency | null;
  escrow?: Currency | null;
  estimated_total_monthly_payment?: Currency | null;
}

export interface TaxesInsuranceAssessments {
  estimate_per_month?: Currency | null;
  in_escrow?: boolean | null;
  includes?: Record<string, boolean | null> | null;
  note?: string | null;
}

export interface CostsAtClosing {
  estimated_closing_costs?: Currency | null;
  estimated_cash_to_close?: Currency | null;
}

export type SubLabel =
  | "borrower_paid_at_closing"
  | "borrower_paid_before_closing"
  | "seller_paid_at_closing"
  | "seller_paid_before_closing"
  | "paid_by_others";

export type Payer = "borrower" | "seller" | "other";
export type Timing = "at_closing" | "before_closing" | "n/a";

export interface LineItem {
  label?: string | null;
  amount?: Currency | null;
  sub_label?: SubLabel | null;
  payer?: Payer | null;
  timing?: Timing | null;
}

export interface SectionWithItems {
  label?: string | null;
  total?: Currency | null;
  items?: LineItem[] | null;
}

export interface LoanCosts {
  A?: SectionWithItems | null;
  B?: SectionWithItems | null;
  C?: SectionWithItems | null;
  D_total?: Currency | null;
}

export interface OtherCosts {
  E?: SectionWithItems | null;
  F?: SectionWithItems | null;
  G?: SectionWithItems | null;
  H?: SectionWithItems | null;
  I_total?: Currency | null;
  J_total?: Currency | null;
  lender_credits?: Currency | null;
}

export interface CashToClose {
  total_closing_costs_J?: Currency | null;
  financed_from_loan?: Currency | null;
  down_payment?: Currency | null;
  deposit?: Currency | null;
  funds_for_borrower?: Currency | null;
  seller_credits?: Currency | null;
  adjustments_and_other_credits?: Currency | null;
  estimated_cash_to_close?: Currency | null;
}

export interface ClosingCostDetails {
  loan_costs?: LoanCosts | null;
  other_costs?: OtherCosts | null;
  cash_to_close?: CashToClose | null;
}

export interface Contacts {
  lender?: Record<string, string | null> | null;
  loan_officer?: Record<string, string | null> | null;
  mortgage_broker?: Record<string, string | null> | null;
}

export interface Comparisons {
  in_5_years?: Record<string, Currency | null> | null;
  apr_pct?: number | null;
  tip_pct?: number | null;
}

export interface OtherConsiderations {
  appraisal_may_be_ordered?: boolean | null;
  assumption_allowed?: boolean | null;
  homeowners_insurance_required?: boolean | null;
  late_payment?: LatePayment | null;
  refinance_note?: string | null;
  servicing_intent?: "service" | "transfer" | "unknown" | null;
}

export interface Applicant {
  name?: string | null;
  address?: string | null;
}

export interface Meta {
  source_id?: string | null;
  source_file?: string | null;
  page_count?: number | null;
  extracted_at?: string | null;
  parser_version?: string | null;
}

export interface LoanEstimateRecord {
  meta?: Meta | null;
  applicants?: Applicant[] | null;
  property?: Record<string, string | null> | null;
  sale_price?: Currency | null;
  loan?: LoanCore | null;
  loan_terms?: LoanTerms | null;
  projected_payments?: PeriodPayment[] | null;
  taxes_insurance_assessments?: TaxesInsuranceAssessments | null;
  costs_at_closing?: CostsAtClosing | null;
  closing_cost_details?: ClosingCostDetails | null;
  contacts?: Contacts | null;
  comparisons?: Comparisons | null;
  other_considerations?: OtherConsiderations | null;
  confirm_receipt?: Record<string, boolean | null> | null;
}

export interface MatchedFee {
  fee_name: string;
  section: string;
  le_amount?: Currency | null;
  cd_amount?: Currency | null;
  le_label?: string | null;
  cd_label?: string | null;
  match_confidence: number;
  tolerance_category: "zero" | "ten_percent" | "unlimited";
  provider_name?: string | null;
  is_new: boolean;
}

export interface TRIDComparison {
  matched_fees: MatchedFee[];
  summary: Record<string, any>;
  processed_at: string;
}

export interface FinancialProfileSummary {
  borrower_overview: string;
  loan_overview: string;
  cost_analysis: string;
  trid_compliance: string;
  key_changes: string[];
  recommendations: string[];
  risk_assessment: string;
  generated_at: string;
}

export interface ProcessedFileResponse {
  source_file: string;
  json_path: string;
  markdown_path?: string | null;
  json_data: LoanEstimateRecord;
  document_type?: "loan_estimate" | "closing_disclosure" | "unknown";
}

export interface BackendExtractResponse {
  meta: {
    pipeline: string;
    landing_model: string;
    gemini_model: string;
    saved_to: string;
    ai_matching_enabled?: boolean;
    summary_generation_enabled?: boolean;
    pdf_report_path?: string | null;
  };
  files: ProcessedFileResponse[];
  trid_comparison?: TRIDComparison | null;
  financial_summary?: FinancialProfileSummary | null;
  errors?: string[] | null;
}

