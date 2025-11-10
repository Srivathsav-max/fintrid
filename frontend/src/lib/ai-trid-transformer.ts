import type { MatchedFee, TRIDComparison } from "@/types/backend";
import type {
  ZeroToleranceFee,
  TenPercentFee,
  UnlimitedFee,
} from "@/types/trid";

export interface ToleranceDataset {
  origination: ZeroToleranceFee[];
  cannotShop: ZeroToleranceFee[];
  tenPercent: TenPercentFee[];
  unlimited: UnlimitedFee[];
}

export function transformAIMatchedData(
  tridComparison: TRIDComparison | null
): ToleranceDataset {
  if (!tridComparison || !tridComparison.matched_fees) {
    return {
      origination: [],
      cannotShop: [],
      tenPercent: [],
      unlimited: [],
    };
  }

  const originationFees: ZeroToleranceFee[] = [];
  const cannotShopFees: ZeroToleranceFee[] = [];
  const tenPercentFees: TenPercentFee[] = [];
  const unlimitedFees: UnlimitedFee[] = [];

  for (const fee of tridComparison.matched_fees) {
    const leAmount = fee.le_amount ?? 0;
    const cdAmount = fee.cd_amount ?? 0;
    
    if (leAmount === 0 && cdAmount === 0) {
      continue;
    }

    if (fee.tolerance_category === "zero") {
      const transformedFee = transformToZeroTolerance(fee);
      if (fee.section === "A") {
        originationFees.push(transformedFee);
      } else if (fee.section === "B") {
        cannotShopFees.push(transformedFee);
      }
    } else if (fee.tolerance_category === "ten_percent") {
      tenPercentFees.push(transformToTenPercent(fee));
    } else if (fee.tolerance_category === "unlimited") {
      unlimitedFees.push(transformToUnlimited(fee));
    }
  }

  return {
    origination: originationFees,
    cannotShop: cannotShopFees,
    tenPercent: tenPercentFees,
    unlimited: unlimitedFees,
  };
}

function transformToZeroTolerance(fee: MatchedFee): ZeroToleranceFee {
  return {
    id: `ai-zero-${fee.section}-${sanitizeId(fee.fee_name)}`,
    fee: fee.is_new ? `${fee.fee_name} [NEW]` : fee.fee_name,
    permittedToShop: fee.section === "B",
    le: {
      borrower: fee.le_amount ?? 0,
    },
    cd: {
      borrower: fee.cd_amount ?? 0,
    },
    changeReason: calculateChangeReason(fee.le_amount ?? 0, fee.cd_amount ?? 0, fee.is_new),
  };
}

function transformToTenPercent(fee: MatchedFee): TenPercentFee {
  return {
    id: `ai-ten-${fee.section}-${sanitizeId(fee.fee_name)}`,
    fee: fee.is_new ? `${fee.fee_name} [NEW]` : fee.fee_name,
    provider: fee.provider_name || extractProvider(fee.cd_label || fee.le_label || fee.fee_name),
    providerType: fee.section as "C" | "E",
    whitelistConfidence: fee.match_confidence,
    onWhitelist: fee.match_confidence >= 0.7,
    matchConfidence: fee.match_confidence,
    le: {
      borrower: fee.le_amount ?? 0,
    },
    cd: {
      borrower: fee.cd_amount ?? 0,
    },
    changeReason: calculateChangeReason(fee.le_amount ?? 0, fee.cd_amount ?? 0, fee.is_new),
    isRecording: fee.fee_name.toLowerCase().includes("recording"),
  };
}

function transformToUnlimited(fee: MatchedFee): UnlimitedFee {
  return {
    id: `ai-unlim-${fee.section}-${sanitizeId(fee.fee_name)}`,
    bucket: fee.section as "F" | "G" | "H",
    fee: fee.is_new ? `${fee.fee_name} [NEW]` : fee.fee_name,
    le: {
      borrower: fee.le_amount ?? 0,
    },
    cd: {
      borrower: fee.cd_amount ?? 0,
    },
    changeReason: calculateChangeReason(fee.le_amount ?? 0, fee.cd_amount ?? 0, fee.is_new),
    perDiemDays: extractPerDiem(fee.fee_name),
    escrowMonths: extractEscrowMonths(fee.fee_name),
    isOptional: fee.fee_name.toLowerCase().includes("optional"),
    lenderRequired: !fee.fee_name.toLowerCase().includes("optional"),
  };
}

function sanitizeId(str: string): string {
  return str.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function calculateChangeReason(leAmount: number, cdAmount: number, isNew: boolean): string {
  if (isNew) return "NEW FEE - Not in Loan Estimate";
  
  const diff = cdAmount - leAmount;
  if (diff === 0) return "No change";
  if (diff > 0) return `Increased by $${diff.toFixed(2)}`;
  return `Decreased by $${Math.abs(diff).toFixed(2)}`;
}

function extractProvider(label: string): string {
  const match = label.match(/\bto\s+(.+?)$/i);
  return match ? match[1].trim() : "Unknown Provider";
}

function extractPerDiem(feeName: string): number | undefined {
  const match = feeName.match(/(\d+)\s*(?:day|per.?diem)/i);
  return match ? parseInt(match[1], 10) : undefined;
}

function extractEscrowMonths(feeName: string): number | undefined {
  const match = feeName.match(/(\d+)\s*month/i);
  return match ? parseInt(match[1], 10) : undefined;
}

