export type RowStatus = "PASS" | "FAIL" | "REVIEW";

export type ToleranceFlag =
  | "ZERO_LINE_OVERAGE"
  | "SECTION_PLACEMENT_MISMATCH"
  | "PROVIDER_OFF_LIST"
  | "LOW_CONFIDENCE"
  | "OFF_LIST_EXCLUDED"
  | "PER_DIEM_OUTLIER"
  | "ESCROW_CUSHION_EXCEEDED"
  | "OPTIONALITY_MISMATCH";

export interface PayerSplit {
  borrower: number;
  seller?: number;
  other?: number;
}

export interface ZeroToleranceFee {
  id: string;
  fee: string;
  permittedToShop?: boolean;
  le: PayerSplit;
  cd: PayerSplit;
  changeReason: string;
}

export interface TenPercentFee {
  id: string;
  fee: string;
  provider: string;
  providerType: "C" | "E";
  whitelistConfidence: number;
  onWhitelist: boolean;
  matchConfidence: number;
  le: PayerSplit;
  cd: PayerSplit;
  changeReason: string;
  isRecording?: boolean;
}

export interface UnlimitedFee {
  id: string;
  bucket: "F" | "G" | "H";
  fee: string;
  le: PayerSplit;
  cd: PayerSplit;
  changeReason: string;
  perDiemDays?: number;
  escrowMonths?: number;
  isOptional?: boolean;
  lenderRequired?: boolean;
}

export interface FlagDetail {
  code: ToleranceFlag;
  label: string;
  severity: "error" | "warning";
  details?: string;
}

export interface ExceptionEntry {
  id: string;
  section: "A" | "B" | "C+E" | "F" | "G" | "H";
  fee: string;
  message: string;
  severity: "error" | "warning";
  amount?: number;
}
