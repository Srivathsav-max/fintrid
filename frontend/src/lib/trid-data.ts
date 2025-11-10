import type {
  TenPercentFee,
  UnlimitedFee,
  ZeroToleranceFee,
} from "@/types/trid";

export interface ToleranceDataset {
  origination: ZeroToleranceFee[];
  cannotShop: ZeroToleranceFee[];
  tenPercent: TenPercentFee[];
  unlimited: UnlimitedFee[];
}

const currency = (value: number) => Number(value.toFixed(2));

const split = (
  borrower: number,
  seller?: number,
  other?: number,
) => ({
  borrower: currency(borrower),
  seller: seller ? currency(seller) : undefined,
  other: other ? currency(other) : undefined,
});

export const buildDummyToleranceData = (): ToleranceDataset => ({
  origination: [
    {
      id: "orig-1",
      fee: "Origination Charge",
      le: split(1950),
      cd: split(2105),
      changeReason: "Rate lock extended two days",
    },
    {
      id: "orig-2",
      fee: "Processing Fee",
      le: split(675),
      cd: split(675),
      changeReason: "No change",
    },
    {
      id: "orig-3",
      fee: "Underwriting Fee",
      le: split(795),
      cd: split(795),
      changeReason: "No change",
    },
  ],
  cannotShop: [
    {
      id: "cant-1",
      fee: "Appraisal",
      le: split(650),
      cd: split(725),
      permittedToShop: false,
      changeReason: "Rush order requested by borrower",
    },
    {
      id: "cant-2",
      fee: "Credit Report",
      le: split(48),
      cd: split(48),
      changeReason: "No change",
    },
    {
      id: "cant-3",
      fee: "Flood Certification",
      le: split(32),
      cd: split(32),
      permittedToShop: true,
      changeReason: "Provider flagged as preferred by borrower",
    },
  ],
  tenPercent: [
    {
      id: "grp-1",
      fee: "Title - Settlement Agent",
      provider: "Metro Title Co.",
      providerType: "C",
      whitelistConfidence: 0.96,
      onWhitelist: true,
      matchConfidence: 0.96,
      le: split(1275),
      cd: split(1350, 0, 150),
      changeReason: "Seller requested mobile signing",
    },
    {
      id: "grp-2",
      fee: "Title Search",
      provider: "Metro Title Co.",
      providerType: "C",
      whitelistConfidence: 0.91,
      onWhitelist: true,
      matchConfidence: 0.91,
      le: split(450),
      cd: split(525),
      changeReason: "Abstractor billed extra trip",
    },
    {
      id: "grp-3",
      fee: "Recording Fees (E)",
      provider: "County Recorder",
      providerType: "E",
      whitelistConfidence: 0.99,
      onWhitelist: true,
      matchConfidence: 0.99,
      le: split(210),
      cd: split(210),
      changeReason: "No change",
      isRecording: true,
    },
    {
      id: "grp-4",
      fee: "Pest Inspection",
      provider: "Ace Inspectors",
      providerType: "C",
      whitelistConfidence: 0.84,
      onWhitelist: false,
      matchConfidence: 0.84,
      le: split(125),
      cd: split(0, 0, 150),
      changeReason: "Borrower insisted on preferred vendor",
    },
  ],
  unlimited: [
    {
      id: "unlim-1",
      bucket: "F",
      fee: "Daily Interest Charges",
      le: split(875),
      cd: split(1045),
      changeReason: "Closing moved to 27th (20 per-diem days)",
      perDiemDays: 20,
    },
    {
      id: "unlim-2",
      bucket: "G",
      fee: "Escrow Deposit - Taxes",
      le: split(1650),
      cd: split(1850),
      changeReason: "County cycle requires three months cushion",
      escrowMonths: 3,
    },
    {
      id: "unlim-3",
      bucket: "H",
      fee: "Owner's Title Policy",
      le: split(0, 0, 980),
      cd: split(0, 0, 980),
      changeReason: "Optional coverage",
      isOptional: true,
      lenderRequired: false,
    },
    {
      id: "unlim-4",
      bucket: "H",
      fee: "HOA Capital Contribution",
      le: split(0, 600),
      cd: split(0, 800),
      changeReason: "Association dues increased",
      isOptional: false,
      lenderRequired: true,
    },
  ],
});
