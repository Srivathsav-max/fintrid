import type {
  ExceptionEntry,
  FlagDetail,
  RowStatus,
  TenPercentFee,
  ToleranceFlag,
  UnlimitedFee,
  ZeroToleranceFee,
} from "@/types/trid";

export interface ZeroToleranceDisplayRow extends ZeroToleranceFee {
  delta: number;
  status: RowStatus;
  flags: FlagDetail[];
  cureAmount: number;
}

export interface ZeroToleranceResult {
  rows: ZeroToleranceDisplayRow[];
  subtotalLE: number;
  subtotalCD: number;
  passCount: number;
  failCount: number;
  reviewCount: number;
  cureAmount: number;
}

export interface TenPercentDisplayRow extends TenPercentFee {
  delta: number;
  status: RowStatus;
  flags: FlagDetail[];
  effectiveOnWhitelist: boolean;
  inTenGroup: boolean;
}

export interface TenPercentResult {
  rows: TenPercentDisplayRow[];
  leBase: number;
  cdTotal: number;
  allowedMax: number;
  overage: number;
  status: "PASS" | "OVER";
}

export interface UnlimitedDisplayRow extends UnlimitedFee {
  delta: number;
  status: RowStatus;
  flags: FlagDetail[];
}

export interface RuleOptions {
  zeroThreshold?: number;
  reviewConfidenceFloor?: number;
  reviewConfidenceCeil?: number;
  lenderCredits?: number;
}

export type TenPercentOverrideMap = Record<
  string,
  {
    includeInGroup?: boolean;
  }
>;

const DEFAULTS: Required<RuleOptions> = {
  zeroThreshold: 1,
  reviewConfidenceFloor: 0.8,
  reviewConfidenceCeil: 0.93,
  lenderCredits: 0,
};

const currency = (value: number) => Number(value.toFixed(2));

const borrowerDelta = (
  le: ZeroToleranceFee["le"] | TenPercentFee["le"] | UnlimitedFee["le"],
  cd: ZeroToleranceFee["cd"] | TenPercentFee["cd"] | UnlimitedFee["cd"],
) => currency(cd.borrower - le.borrower);

const buildFlag = (
  code: ToleranceFlag,
  label: string,
  severity: "error" | "warning" = "warning",
  details?: string,
): FlagDetail => ({
  code,
  label,
  severity,
  details,
});

export const evaluateZeroTolerance = (
  rows: ZeroToleranceFee[],
  bucket: "A" | "B",
  options?: RuleOptions,
): ZeroToleranceResult => {
  const config = { ...DEFAULTS, ...options };
  const lenderCredits = config.lenderCredits || 0;

  const evaluated = rows.map<ZeroToleranceDisplayRow>((row) => {
    const delta = borrowerDelta(row.le, row.cd);
    let status: RowStatus = delta > config.zeroThreshold ? "FAIL" : "PASS";
    const flags: FlagDetail[] = [];

    if (delta > config.zeroThreshold) {
      flags.push(
        buildFlag(
          "ZERO_LINE_OVERAGE",
          `Borrower owes $${(delta - config.zeroThreshold).toFixed(2)} over zero tolerance`,
          "error",
        ),
      );
    }

    if (bucket === "B" && row.permittedToShop) {
      flags.push(
        buildFlag(
          "SECTION_PLACEMENT_MISMATCH",
          "Fee marked permitted-to-shop but placed in zero bucket",
        ),
      );
      if (status === "PASS") {
        status = "REVIEW";
      }
    }

    const cureAmount =
      status === "FAIL" ? currency(delta - config.zeroThreshold) : 0;

    return {
      ...row,
      delta,
      status,
      flags,
      cureAmount,
    };
  });

  const totalCureNeeded = currency(
    evaluated.reduce((sum, row) => sum + row.cureAmount, 0),
  );
  
  if (lenderCredits > 0 && totalCureNeeded > 0) {
    evaluated.forEach((row) => {
      if (row.cureAmount > 0 && lenderCredits >= totalCureNeeded) {
        row.flags.push(
          buildFlag(
            "CURED_BY_LENDER",
            `Overage offset by lender credit ($${lenderCredits.toFixed(2)})`,
            "warning",
          ),
        );
      }
    });
  }

  const subtotalLE = currency(
    evaluated.reduce((sum, row) => sum + row.le.borrower, 0),
  );
  const subtotalCD = currency(
    evaluated.reduce((sum, row) => sum + row.cd.borrower, 0),
  );
  const passCount = evaluated.filter((row) => row.status === "PASS").length;
  const failCount = evaluated.filter((row) => row.status === "FAIL").length;
  const reviewCount = evaluated.filter(
    (row) => row.status === "REVIEW",
  ).length;
  const cureAmount = currency(
    evaluated.reduce((sum, row) => sum + row.cureAmount, 0),
  );

  return {
    rows: evaluated,
    subtotalLE,
    subtotalCD,
    passCount,
    failCount,
    reviewCount,
    cureAmount,
  };
};

export const evaluateTenPercent = (
  rows: TenPercentFee[],
  overrides: TenPercentOverrideMap = {},
  options?: RuleOptions,
): TenPercentResult => {
  const config = { ...DEFAULTS, ...options };

  const evaluated = rows.map<TenPercentDisplayRow>((row) => {
    const delta = borrowerDelta(row.le, row.cd);
    const isRecording = row.providerType === "E" || Boolean(row.isRecording);
    const override = overrides[row.id];
    const effectiveOnWhitelist =
      typeof override?.includeInGroup === "boolean"
        ? override.includeInGroup
        : row.onWhitelist;

    const flags: FlagDetail[] = [];

    const isLowConfidence = row.matchConfidence < config.reviewConfidenceFloor;
    const needsReview =
      row.matchConfidence >= config.reviewConfidenceFloor &&
      row.matchConfidence < config.reviewConfidenceCeil;

    if (!effectiveOnWhitelist && !isRecording && !needsReview && !isLowConfidence) {
      flags.push(
        buildFlag(
          "PROVIDER_OFF_LIST",
          "Provider chosen off-list; unlimited tolerance",
          "warning",
        ),
      );
    }
    
    if (needsReview) {
      flags.push(
        buildFlag(
          "LOW_CONFIDENCE",
          `Match confidence ${Math.round(row.matchConfidence * 100)}% - Review`,
        ),
      );
    }

    const inTenGroup: boolean = (effectiveOnWhitelist || isRecording) && !isLowConfidence;

    let status: RowStatus = "PASS";
    if (isLowConfidence || needsReview) {
      status = "REVIEW";
    } else if (!effectiveOnWhitelist && !isRecording) {
      status = "REVIEW";
    }

    return {
      ...row,
      delta,
      status,
      flags,
      effectiveOnWhitelist,
      inTenGroup,
    };
  });

  const eligibleRows = evaluated.filter((row) => row.inTenGroup);
  const leBase = currency(
    eligibleRows.reduce((sum, row) => sum + row.le.borrower, 0),
  );
  const cdTotal = currency(
    eligibleRows.reduce((sum, row) => sum + row.cd.borrower, 0),
  );
  const allowedMax = currency(leBase * 1.1);
  const overage = currency(Math.max(0, cdTotal - allowedMax));
  let status: "PASS" | "OVER" = overage > 0 ? "OVER" : "PASS";

  const lenderCredits = config.lenderCredits || 0;
  if (overage > 0 && lenderCredits >= overage) {
    evaluated.forEach((row) => {
      if (row.inTenGroup && row.delta > 0) {
        row.flags.push(
          buildFlag(
            "CURED_BY_LENDER",
            `10% overage offset by lender credit ($${lenderCredits.toFixed(2)})`,
            "warning",
          ),
        );
      }
    });
  }

  return {
    rows: evaluated,
    leBase,
    cdTotal,
    allowedMax,
    overage,
    status,
  };
};

export const evaluateUnlimited = (
  rows: UnlimitedFee[],
): UnlimitedDisplayRow[] => {
  return rows.map<UnlimitedDisplayRow>((row) => {
    const delta = borrowerDelta(row.le, row.cd);
    const flags: FlagDetail[] = [];

    if (row.bucket === "F" && row.perDiemDays && row.perDiemDays > 15) {
      flags.push(
        buildFlag(
          "PER_DIEM_OUTLIER",
          `${row.perDiemDays} per-diem days recorded`,
        ),
      );
    }

    if (
      row.bucket === "F" && 
      row.perDiemDays && 
      row.loanAmount && 
      row.interestRate &&
      row.cd.borrower > 0
    ) {
      const expectedPerDiem = currency(
        (row.loanAmount * row.interestRate / 100 / 365) * row.perDiemDays
      );
      const deviation = Math.abs(row.cd.borrower - expectedPerDiem);
      const deviationPercent = (deviation / expectedPerDiem) * 100;
      
      if (deviationPercent > 10) {
        flags.push(
          buildFlag(
            "PER_DIEM_INTEREST_DEVIATION",
            `Expected ${formatUSD(expectedPerDiem)}, actual ${formatUSD(row.cd.borrower)} (${deviationPercent.toFixed(1)}% deviation)`,
            "warning",
          ),
        );
      }
    }

    if (row.bucket === "G" && row.escrowMonths && row.escrowMonths > 2) {
      flags.push(
        buildFlag(
          "ESCROW_CUSHION_EXCEEDED",
          `${row.escrowMonths} months collected (max 2 permitted)`,
          "warning",
        ),
      );
    }

    if (
      row.bucket === "H" &&
      row.lenderRequired &&
      (row.isOptional ?? false) === false
    ) {
      flags.push(
        buildFlag(
          "OPTIONALITY_MISMATCH",
          "Disclosed optional item appears lender-required",
          "warning",
        ),
      );
    }

    const status: RowStatus = flags.length > 0 ? "REVIEW" : "PASS";

    return {
      ...row,
      delta,
      flags,
      status,
    };
  });
};

const formatUSD = (amount: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
};

export const collectExceptions = ({
  a,
  b,
  ten,
  unlimited,
}: {
  a: ZeroToleranceResult;
  b: ZeroToleranceResult;
  ten: TenPercentResult;
  unlimited: UnlimitedDisplayRow[];
}): ExceptionEntry[] => {
  const entries: ExceptionEntry[] = [];

  const pushFlags = (
    section: ExceptionEntry["section"],
    rows: Array<
      ZeroToleranceDisplayRow | TenPercentDisplayRow | UnlimitedDisplayRow
    >,
  ) => {
    rows.forEach((row) => {
      row.flags.forEach((flag) => {
        entries.push({
          id: row.id,
          section,
          fee: row.fee,
          message: flag.label,
          severity: flag.severity,
          amount: row.delta,
        });
      });
    });
  };

  pushFlags("A", a.rows);
  pushFlags("B", b.rows);
  pushFlags("C+E", ten.rows);
  unlimited.forEach((row) => pushFlags(row.bucket, [row]));

  if (ten.overage > 0) {
    entries.push({
      id: "ten-percent-overage",
      section: "C+E",
      fee: "10% Aggregated",
      message: `Exceeded by $${ten.overage.toFixed(2)}`,
      severity: "error",
      amount: ten.overage,
    });
  }

  return entries;
};
