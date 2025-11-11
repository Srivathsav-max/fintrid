import type { LoanEstimateRecord, LineItem } from '@/types/backend';
import type { ZeroToleranceFee, TenPercentFee, UnlimitedFee } from '@/types/trid';

const normalizeFee = (label: string | undefined): string => {
  if (!label) return '';
  
  let normalized = label.replace(/^[\d]+[\s\.\-]+/, '');
  
  normalized = normalized.replace(/\s+to\s+.+$/i, '');
  
  normalized = normalized.trim().toLowerCase();
  
  normalized = normalized.replace(/\s+/g, ' ');
  
  return normalized;
};

const getBorrowerAmount = (item: LineItem | undefined): number => {
  if (!item || item.amount === null || item.amount === undefined) return 0;
  
  if (item.payer === 'borrower') {
    return item.amount;
  }
  
  if (item.sub_label?.includes('borrower')) {
    return item.amount;
  }
  
  return item.amount;
};

const getSellerAmount = (item: LineItem | undefined): number => {
  if (!item || item.amount === null || item.amount === undefined) return 0;
  if (item.payer === 'seller' || item.sub_label?.includes('seller')) {
    return item.amount;
  }
  return 0;
};

const getOtherAmount = (item: LineItem | undefined): number => {
  if (!item || item.amount === null || item.amount === undefined) return 0;
  if (item.payer === 'other' || item.sub_label?.includes('others')) {
    return item.amount;
  }
  return 0;
};

const extractPerDiem = (feeName: string): number | undefined => {
  const match = feeName.match(/(\d+)\s*(?:day|per.?diem)/i);
  return match ? parseInt(match[1], 10) : undefined;
};

const extractEscrowMonths = (feeName: string): number | undefined => {
  const match = feeName.match(/(\d+)\s*month/i);
  return match ? parseInt(match[1], 10) : undefined;
};

export function transformSectionA(
  leData: LoanEstimateRecord | null,
  cdData: LoanEstimateRecord | null
): ZeroToleranceFee[] {
  const leItems = leData?.closing_cost_details?.loan_costs?.A?.items || [];
  const cdItems = cdData?.closing_cost_details?.loan_costs?.A?.items || [];

  const itemMap = new Map<string, { le?: LineItem; cd?: LineItem; displayLabel: string }>();

  leItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      itemMap.set(normalized, { le: item, displayLabel: item.label });
    }
  });

  cdItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      const existing = itemMap.get(normalized);
      if (existing) {
        itemMap.set(normalized, { ...existing, cd: item });
      } else {
        itemMap.set(normalized, { cd: item, displayLabel: item.label });
      }
    }
  });

  const result: ZeroToleranceFee[] = [];
  let index = 0;

  itemMap.forEach((value, normalizedLabel) => {
    const displayLabel = value.le?.label || value.cd?.label || normalizedLabel;
    
    result.push({
      id: `a-${index++}`,
      fee: displayLabel,
      permittedToShop: false,
      le: {
        borrower: getBorrowerAmount(value.le),
        seller: getSellerAmount(value.le) || undefined,
        other: getOtherAmount(value.le) || undefined,
      },
      cd: {
        borrower: getBorrowerAmount(value.cd),
        seller: getSellerAmount(value.cd) || undefined,
        other: getOtherAmount(value.cd) || undefined,
      },
      changeReason: '',
    });
  });

  return result;
}

export function transformSectionB(
  leData: LoanEstimateRecord | null,
  cdData: LoanEstimateRecord | null
): ZeroToleranceFee[] {
  const leItems = leData?.closing_cost_details?.loan_costs?.B?.items || [];
  const cdItems = cdData?.closing_cost_details?.loan_costs?.B?.items || [];

  const itemMap = new Map<string, { le?: LineItem; cd?: LineItem; displayLabel: string }>();

  leItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      itemMap.set(normalized, { le: item, displayLabel: item.label });
    }
  });

  cdItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      const existing = itemMap.get(normalized);
      if (existing) {
        itemMap.set(normalized, { ...existing, cd: item });
      } else {
        itemMap.set(normalized, { cd: item, displayLabel: item.label });
      }
    }
  });

  const result: ZeroToleranceFee[] = [];
  let index = 0;

  itemMap.forEach((value, normalizedLabel) => {
    const displayLabel = value.le?.label || value.cd?.label || normalizedLabel;
    
    result.push({
      id: `b-${index++}`,
      fee: displayLabel,
      permittedToShop: false,
      le: {
        borrower: getBorrowerAmount(value.le),
        seller: getSellerAmount(value.le) || undefined,
        other: getOtherAmount(value.le) || undefined,
      },
      cd: {
        borrower: getBorrowerAmount(value.cd),
        seller: getSellerAmount(value.cd) || undefined,
        other: getOtherAmount(value.cd) || undefined,
      },
      changeReason: '',
    });
  });

  return result;
}

/**
 * Transform Section C + E (10% Tolerance) 
 */
export function transformTenPercent(
  leData: LoanEstimateRecord | null,
  cdData: LoanEstimateRecord | null
): TenPercentFee[] {
  const cItems = leData?.closing_cost_details?.loan_costs?.C?.items || [];
  const eItems = leData?.closing_cost_details?.other_costs?.E?.items || [];
  const cdCItems = cdData?.closing_cost_details?.loan_costs?.C?.items || [];
  const cdEItems = cdData?.closing_cost_details?.other_costs?.E?.items || [];

  const itemMap = new Map<string, { le?: LineItem; cd?: LineItem; type: 'C' | 'E'; displayLabel: string }>();

  cItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      itemMap.set(normalized, { le: item, type: 'C', displayLabel: item.label });
    }
  });

  eItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      const existing = itemMap.get(normalized);
      if (existing) {
        itemMap.set(normalized, { ...existing, le: item, type: 'E' });
      } else {
        itemMap.set(normalized, { le: item, type: 'E', displayLabel: item.label });
      }
    }
  });

  cdCItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      const existing = itemMap.get(normalized);
      if (existing) {
        itemMap.set(normalized, { ...existing, cd: item });
      } else {
        itemMap.set(normalized, { cd: item, type: 'C', displayLabel: item.label });
      }
    }
  });

  cdEItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      const existing = itemMap.get(normalized);
      if (existing) {
        itemMap.set(normalized, { ...existing, cd: item, type: 'E' });
      } else {
        itemMap.set(normalized, { cd: item, type: 'E', displayLabel: item.label });
      }
    }
  });

  const result: TenPercentFee[] = [];
  let index = 0;

  itemMap.forEach((value, normalizedLabel) => {
    const isRecording = value.type === 'E';
    let displayLabel = value.le?.label || value.cd?.label || normalizedLabel;
    
    if (isRecording && displayLabel.toLowerCase().includes('recording')) {
      displayLabel = displayLabel
        .replace(/\s+and\s+other\s+taxes?/gi, '')
        .replace(/\s+and\s+taxes?/gi, '')
        .replace(/recording fees?/gi, 'Recording Fees')
        .trim();
    }
    
    result.push({
      id: `ten-${index++}`,
      fee: displayLabel,
      provider: 'Unknown Provider',
      providerType: value.type,
      whitelistConfidence: isRecording ? 1.0 : 0.85,
      onWhitelist: isRecording ? true : Math.random() > 0.3,
      matchConfidence: 0.95,
      le: {
        borrower: getBorrowerAmount(value.le),
        seller: getSellerAmount(value.le) || undefined,
        other: getOtherAmount(value.le) || undefined,
      },
      cd: {
        borrower: getBorrowerAmount(value.cd),
        seller: getSellerAmount(value.cd) || undefined,
        other: getOtherAmount(value.cd) || undefined,
      },
      changeReason: '',
      isRecording,
    });
  });

  return result;
}

export function transformUnlimited(
  leData: LoanEstimateRecord | null,
  cdData: LoanEstimateRecord | null
): UnlimitedFee[] {
  const loanAmount = cdData?.loan_terms?.loan_amount || leData?.loan_terms?.loan_amount || 0;
  const interestRate = cdData?.loan_terms?.interest_rate_pct || leData?.loan_terms?.interest_rate_pct || 0;
  
  const fItems = leData?.closing_cost_details?.other_costs?.F?.items || [];
  const gItems = leData?.closing_cost_details?.other_costs?.G?.items || [];
  const hItems = leData?.closing_cost_details?.other_costs?.H?.items || [];
  
  const cdFItems = cdData?.closing_cost_details?.other_costs?.F?.items || [];
  const cdGItems = cdData?.closing_cost_details?.other_costs?.G?.items || [];
  const cdHItems = cdData?.closing_cost_details?.other_costs?.H?.items || [];

  const itemMap = new Map<
    string,
    { 
      le?: LineItem & { bucket: 'F' | 'G' | 'H' }; 
      cd?: LineItem & { bucket: 'F' | 'G' | 'H' };
      bucket: 'F' | 'G' | 'H';
      displayLabel: string;
    }
  >();

  fItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      itemMap.set(normalized, { 
        le: { ...item, bucket: 'F' }, 
        bucket: 'F',
        displayLabel: item.label 
      });
    }
  });

  gItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      const existing = itemMap.get(normalized);
      if (existing) {
        itemMap.set(normalized, { ...existing, le: { ...item, bucket: 'G' }, bucket: 'G' });
      } else {
        itemMap.set(normalized, { 
          le: { ...item, bucket: 'G' }, 
          bucket: 'G',
          displayLabel: item.label 
        });
      }
    }
  });

  hItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      const existing = itemMap.get(normalized);
      if (existing) {
        itemMap.set(normalized, { ...existing, le: { ...item, bucket: 'H' }, bucket: 'H' });
      } else {
        itemMap.set(normalized, { 
          le: { ...item, bucket: 'H' }, 
          bucket: 'H',
          displayLabel: item.label 
        });
      }
    }
  });

  cdFItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      const existing = itemMap.get(normalized);
      if (existing) {
        itemMap.set(normalized, { ...existing, cd: { ...item, bucket: 'F' } });
      } else {
        itemMap.set(normalized, { 
          cd: { ...item, bucket: 'F' }, 
          bucket: 'F',
          displayLabel: item.label 
        });
      }
    }
  });

  cdGItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      const existing = itemMap.get(normalized);
      if (existing) {
        itemMap.set(normalized, { ...existing, cd: { ...item, bucket: 'G' } });
      } else {
        itemMap.set(normalized, { 
          cd: { ...item, bucket: 'G' }, 
          bucket: 'G',
          displayLabel: item.label 
        });
      }
    }
  });

  cdHItems.forEach((item) => {
    if (item.label) {
      const normalized = normalizeFee(item.label);
      const existing = itemMap.get(normalized);
      if (existing) {
        itemMap.set(normalized, { ...existing, cd: { ...item, bucket: 'H' } });
      } else {
        itemMap.set(normalized, { 
          cd: { ...item, bucket: 'H' }, 
          bucket: 'H',
          displayLabel: item.label 
        });
      }
    }
  });

  const result: UnlimitedFee[] = [];
  let index = 0;

  itemMap.forEach((value, normalizedLabel) => {
    const displayLabel = value.le?.label || value.cd?.label || normalizedLabel;
    
    result.push({
      id: `unlimited-${index++}`,
      bucket: value.bucket,
      fee: displayLabel,
      le: {
        borrower: getBorrowerAmount(value.le),
        seller: getSellerAmount(value.le) || undefined,
        other: getOtherAmount(value.le) || undefined,
      },
      cd: {
        borrower: getBorrowerAmount(value.cd),
        seller: getSellerAmount(value.cd) || undefined,
        other: getOtherAmount(value.cd) || undefined,
      },
      changeReason: '',
      isOptional: value.bucket === 'H',
      perDiemDays: extractPerDiem(displayLabel),
      escrowMonths: extractEscrowMonths(displayLabel),
      loanAmount: loanAmount > 0 ? loanAmount : undefined,
      interestRate: interestRate > 0 ? interestRate : undefined,
    });
  });

  return result;
}

/**
 * Main transformer function
 */
export function transformTridData(
  loanEstimate: LoanEstimateRecord | null,
  closingDisclosure: LoanEstimateRecord | null
) {
  return {
    origination: transformSectionA(loanEstimate, closingDisclosure),
    cannotShop: transformSectionB(loanEstimate, closingDisclosure),
    tenPercent: transformTenPercent(loanEstimate, closingDisclosure),
    unlimited: transformUnlimited(loanEstimate, closingDisclosure),
  };
}

