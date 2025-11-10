'use client';

import { useMemo, useState, useEffect } from 'react';
import { HotTable } from '@handsontable/react';
import { registerAllModules } from 'handsontable/registry';
import 'handsontable/dist/handsontable.full.min.css';
import { Badge } from '@/components/ui/badge';

if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.textContent = `
    .handsontable td,
    .handsontable th {
      padding: 6px 8px !important;
      height: auto !important;
      line-height: 1.2 !important;
    }
    .handsontable td {
      vertical-align: middle !important;
    }
  `;
  document.head.appendChild(style);
}
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { buildDummyToleranceData } from '@/lib/trid-data';
import {
  evaluateZeroTolerance,
  evaluateTenPercent,
  evaluateUnlimited,
  collectExceptions,
  type TenPercentOverrideMap,
} from '@/lib/trid-rules';
import { formatUSD } from '@/lib/formatters';
import {
  feeRenderer,
  statusRenderer,
  deltaRenderer,
  amountRenderer,
  providerRenderer,
  tenGroupRenderer,
  unlimitedFeeRenderer,
} from '@/components/handsontable/cell-renderers';
import { ShieldAlert, Loader2, RefreshCw, FileText } from 'lucide-react';
import type { ExceptionEntry } from '@/types/trid';
import type { LoanEstimateRecord, TRIDComparison, FinancialProfileSummary } from '@/types/backend';
import { transformTridData } from '@/lib/trid-transformer';
import { transformAIMatchedData } from '@/lib/ai-trid-transformer';

const severityStyles: Record<'error' | 'warning', string> = {
  error: 'bg-rose-50 text-rose-700 border-rose-200',
  warning: 'bg-amber-50 text-amber-700 border-amber-200',
};

registerAllModules();

interface TridRecord {
  id: number;
  loanEstimateData: LoanEstimateRecord | null;
  closingDisclosureData: LoanEstimateRecord | null;
  tridComparison: TRIDComparison | null;
  financialSummary: FinancialProfileSummary | null;
  loanId: string | null;
  applicantName: string | null;
  createdAt: string;
  pdfReportPath: string | null;
}

export default function DataHandsontablePage() {
  const [isLoading, setIsLoading] = useState(true);
  const [records, setRecords] = useState<TridRecord[]>([]);
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null);
  const [dataset, setDataset] = useState(buildDummyToleranceData);
  const [tenOverrides] = useState<TenPercentOverrideMap>({});

  useEffect(() => {
    fetchRecords();
  }, []);

  useEffect(() => {
    if (selectedRecordId) {
      const record = records.find((r) => r.id === selectedRecordId);
      if (record) {
        const transformedData = record.tridComparison
          ? transformAIMatchedData(record.tridComparison)
          : transformTridData(record.loanEstimateData, record.closingDisclosureData);
        
        setDataset(transformedData);
      }
    }
  }, [selectedRecordId, records]);

  const fetchRecords = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/trid-records');
      const result = await response.json();
      
      if (result.success && result.data) {
        setRecords(result.data);
        if (result.data.length > 0 && !selectedRecordId) {
          setSelectedRecordId(result.data[0].id);
        }
      }
    } catch (error) {
      console.error('Failed to fetch records:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const zeroA = useMemo(
    () => evaluateZeroTolerance(dataset.origination, 'A'),
    [dataset.origination]
  );
  const zeroB = useMemo(
    () => evaluateZeroTolerance(dataset.cannotShop, 'B'),
    [dataset.cannotShop]
  );
  const tenPercent = useMemo(
    () => evaluateTenPercent(dataset.tenPercent, tenOverrides),
    [dataset.tenPercent, tenOverrides]
  );
  const unlimitedRows = useMemo(
    () => evaluateUnlimited(dataset.unlimited),
    [dataset.unlimited]
  );

  const exceptions = useMemo(
    () => collectExceptions({ a: zeroA, b: zeroB, ten: tenPercent, unlimited: unlimitedRows }),
    [zeroA, zeroB, tenPercent, unlimitedRows]
  );

  const totalDifference = useMemo(() => {
    const zeroADiff = zeroA.subtotalCD - zeroA.subtotalLE;
    const zeroBDiff = zeroB.subtotalCD - zeroB.subtotalLE;
    const tenPercentDiff = tenPercent.cdTotal - tenPercent.leBase;

    const unlimitedDiff = unlimitedRows.reduce((sum, row) => {
      return sum + (row.cd.borrower - row.le.borrower);
    }, 0);

    return zeroADiff + zeroBDiff + tenPercentDiff + unlimitedDiff;
  }, [zeroA, zeroB, tenPercent, unlimitedRows]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white px-4 py-6 font-sans dark:bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-zinc-500 mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">Loading TRID records...</p>
        </div>
      </div>
    );
  }

  const selectedRecord = records.find((r) => r.id === selectedRecordId);

  return (
    <div className="min-h-screen bg-white px-4 py-6 font-sans dark:bg-zinc-950">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        {/* Dropdown and Refresh - Top Section */}
        {records.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex-1">
              <select
                value={selectedRecordId || ''}
                onChange={(e) => setSelectedRecordId(Number(e.target.value))}
                className="w-full max-w-md rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              >
                {records.map((record) => (
                  <option key={record.id} value={record.id}>
                    {record.applicantName || 'Unknown Applicant'} - Loan {record.loanId || 'N/A'} (
                    {new Date(record.createdAt).toLocaleDateString()})
                  </option>
                ))}
              </select>
            </div>
            <Button
              onClick={fetchRecords}
              variant="outline"
              size="sm"
              className="h-9"
            >
              <RefreshCw className="mr-2 h-3.5 w-3.5" />
              Refresh
            </Button>
          </div>
        )}

        {records.length === 0 && (
          <div className="rounded-lg border bg-amber-50 p-6 text-center dark:bg-amber-950">
            <p className="text-sm font-medium text-amber-900 dark:text-amber-100 mb-2">
              No TRID analysis records found
            </p>
            <p className="text-xs text-amber-700 dark:text-amber-300 mb-4">
              Upload documents on the home page to create your first analysis
            </p>
            <Button onClick={() => window.location.href = '/'} variant="default" size="sm">
              Go to Upload
            </Button>
          </div>
        )}

        {/* Borrower Name and Address */}
        {selectedRecord && (
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
                  {selectedRecord.applicantName || 'Unknown Applicant'}
                </h1>
                {selectedRecord.pdfReportPath && (
                  <Button
                    onClick={() => window.open(`/pdf-report?path=${encodeURIComponent(selectedRecord.pdfReportPath || '')}`, '_blank')}
                    variant="outline"
                    size="sm"
                    className="h-8"
                  >
                    <FileText className="mr-2 h-3.5 w-3.5" />
                    Preview TRID Report
                  </Button>
                )}
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                Loan ID: {selectedRecord.loanId || 'N/A'}
              </p>
            </div>
            <div className="text-left md:text-right">
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                {selectedRecord.loanEstimateData?.property?.address ||
                 selectedRecord.closingDisclosureData?.property?.address ||
                 'Address not available'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Analysis Date: {new Date(selectedRecord.createdAt).toLocaleDateString()}
              </p>
            </div>
          </div>
        )}

        {/* Borrower Overview and Loan Overview */}
        {selectedRecord?.financialSummary && (
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-3">
                Borrower Overview
              </h2>
              <div className="text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-line">
                {selectedRecord.financialSummary.borrower_overview}
              </div>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-3">
                Loan Overview
              </h2>
              <div className="text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-line">
                {selectedRecord.financialSummary.loan_overview}
              </div>
            </div>
          </div>
        )}

        {/* Cost Analysis */}
        {selectedRecord?.financialSummary && (
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-3">
              Cost Analysis
            </h2>
            <div className="text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-line">
              {selectedRecord.financialSummary.cost_analysis}
            </div>
          </div>
        )}

        {/* TRID Analysis - Loan Estimate vs Closing Disclosure */}
        {records.length > 0 && (
        <>
          <div className="border-t border-zinc-200 dark:border-zinc-800 pt-6">
            <div className="flex flex-wrap items-baseline justify-between gap-4 mb-4">
              <div>
                <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50 mb-1">
                  Loan Estimate vs Closing Disclosure
                </h2>
                <p className="text-sm text-muted-foreground">
                  TRID tolerance validation and fee comparison
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
                  Total Difference
                </p>
                <p className={`text-2xl font-bold mt-1 ${
                  totalDifference > 0
                    ? 'text-rose-600 dark:text-rose-400'
                    : totalDifference < 0
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-zinc-900 dark:text-zinc-50'
                }`}>
                  {totalDifference > 0 ? '+' : ''}{formatUSD(totalDifference)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  CD vs LE (borrower paid)
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="space-y-3">
              {/* Section A: Origination (Zero Tolerance) */}
            <section className="space-y-1.5">
              <div className="flex items-center gap-2 pb-1">
                <Badge variant="secondary" className="text-xs font-semibold px-2.5 py-1">
                  A — Origination (Zero)
                </Badge>
                <span className="text-xs text-muted-foreground">
                  Flagged when CD &gt; LE + $1
                </span>
              </div>
              <HotTable
                data={zeroA.rows}
                colHeaders={['Fee', 'LE (borrower)', 'CD (borrower)', 'Δ', 'Status']}
                columns={[
                  { data: 'fee', renderer: feeRenderer },
                  { data: 'le', renderer: amountRenderer },
                  { data: 'cd', renderer: amountRenderer },
                  { data: 'delta', renderer: deltaRenderer },
                  { data: 'status', renderer: statusRenderer },
                ]}
                rowHeaders={true}
                height="auto"
                licenseKey="non-commercial-and-evaluation"
                colWidths={[300, 180, 180, 140, 120]}
                autoColumnSize={true}
                className="htMiddle"
                readOnly={true}
              />
              <div className="mt-2 flex flex-wrap items-center justify-between gap-4 rounded-lg border bg-zinc-50/50 px-4 py-2.5 text-sm dark:bg-zinc-900/50">
                <div className="flex flex-wrap gap-4 text-sm">
                  <span className="text-muted-foreground">
                    Subtotal LE:{' '}
                    <strong className="text-zinc-900 dark:text-zinc-100">
                      {formatUSD(zeroA.subtotalLE)}
                    </strong>
                  </span>
                  <span className="text-muted-foreground">
                    Subtotal CD:{' '}
                    <strong className="text-zinc-900 dark:text-zinc-100">
                      {formatUSD(zeroA.subtotalCD)}
                    </strong>
                  </span>
                </div>
                <div className="flex gap-4 text-sm font-medium">
                  <span className="text-emerald-700">Pass {zeroA.passCount}</span>
                  <span className="text-amber-700">Review {zeroA.reviewCount}</span>
                  <span className="text-rose-700">Fail {zeroA.failCount}</span>
                </div>
              </div>
            </section>

            {/* Section B: Cannot Shop (Zero Tolerance) */}
            <section className="space-y-1.5">
              <div className="flex items-center gap-2 pb-1">
                <Badge variant="secondary" className="text-xs font-semibold px-2.5 py-1">
                  B — Cannot Shop (Zero)
                </Badge>
                <span className="text-xs text-muted-foreground">
                  Warn when permitted-to-shop appears here
                </span>
              </div>
              <HotTable
                data={zeroB.rows}
                colHeaders={['Fee', 'LE (borrower)', 'CD (borrower)', 'Δ', 'Status']}
                columns={[
                  { data: 'fee', renderer: feeRenderer },
                  { data: 'le', renderer: amountRenderer },
                  { data: 'cd', renderer: amountRenderer },
                  { data: 'delta', renderer: deltaRenderer },
                  { data: 'status', renderer: statusRenderer },
                ]}
                rowHeaders={true}
                height="auto"
                licenseKey="non-commercial-and-evaluation"
                colWidths={[300, 180, 180, 140, 120]}
                autoColumnSize={true}
                className="htMiddle"
                readOnly={true}
              />
              <div className="mt-2 flex flex-wrap items-center justify-between gap-4 rounded-lg border bg-zinc-50/50 px-4 py-2.5 text-sm dark:bg-zinc-900/50">
                <div className="flex flex-wrap gap-4 text-sm">
                  <span className="text-muted-foreground">
                    Subtotal LE:{' '}
                    <strong className="text-zinc-900 dark:text-zinc-100">
                      {formatUSD(zeroB.subtotalLE)}
                    </strong>
                  </span>
                  <span className="text-muted-foreground">
                    Subtotal CD:{' '}
                    <strong className="text-zinc-900 dark:text-zinc-100">
                      {formatUSD(zeroB.subtotalCD)}
                    </strong>
                  </span>
                </div>
                <div className="flex gap-4 text-sm font-medium">
                  <span className="text-emerald-700">Pass {zeroB.passCount}</span>
                  <span className="text-amber-700">Review {zeroB.reviewCount}</span>
                  <span className="text-rose-700">Fail {zeroB.failCount}</span>
                </div>
              </div>
            </section>

            {/* Section C+E: 10% Aggregate */}
            <section className="space-y-1.5">
              <div className="flex items-center gap-2 pb-1">
                <Badge variant="secondary" className="text-xs font-semibold px-2.5 py-1">
                  C + E — 10% Aggregate
                </Badge>
                <span className="text-xs text-muted-foreground">
                  On-list providers roll into the cap
                </span>
              </div>
              <div className="rounded-lg border bg-white/95 px-4 py-2.5 text-sm shadow-sm backdrop-blur dark:bg-zinc-900/95">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                    <span>
                      LE base{' '}
                      <strong className="text-zinc-900 dark:text-zinc-100">
                        {formatUSD(tenPercent.leBase)}
                      </strong>
                    </span>
                    <span>
                      CD total{' '}
                      <strong className="text-zinc-900 dark:text-zinc-100">
                        {formatUSD(tenPercent.cdTotal)}
                      </strong>
                    </span>
                    <span>
                      Allowed max{' '}
                      <strong className="text-zinc-900 dark:text-zinc-100">
                        {formatUSD(tenPercent.allowedMax)}
                      </strong>
                    </span>
                  </div>
                  <Badge
                    className={cn(
                      'border text-xs font-semibold px-2.5 py-0.5',
                      tenPercent.status === 'PASS'
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                        : 'bg-rose-50 text-rose-800 border-rose-200'
                    )}
                  >
                    {tenPercent.status === 'PASS'
                      ? 'PASS'
                      : `OVER by ${formatUSD(tenPercent.overage)}`}
                  </Badge>
                </div>
              </div>
              <HotTable
                data={tenPercent.rows}
                colHeaders={[
                  'Fee',
                  'Provider',
                  'In 10% group?',
                  'LE (borrower)',
                  'CD (borrower)',
                  'Δ',
                ]}
                columns={[
                  { data: 'fee', renderer: 'html' },
                  { data: 'provider', renderer: providerRenderer },
                  { data: 'inTenGroup', renderer: tenGroupRenderer },
                  { data: 'le', renderer: amountRenderer },
                  { data: 'cd', renderer: amountRenderer },
                  { data: 'delta', renderer: deltaRenderer },
                ]}
                rowHeaders={true}
                height="auto"
                licenseKey="non-commercial-and-evaluation"
                colWidths={[250, 200, 120, 180, 180, 140]}
                autoColumnSize={true}
                className="htMiddle"
                readOnly={true}
              />
              <div className="mt-2 flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-zinc-50/50 px-4 py-2.5 text-sm dark:bg-zinc-900/50">
                <span className="text-sm text-muted-foreground">
                  Aggregated result:{' '}
                  <strong className="text-zinc-900 dark:text-zinc-100">
                    {tenPercent.status === 'PASS'
                      ? 'Within 10% tolerance'
                      : `Over by ${formatUSD(tenPercent.overage)}`}
                  </strong>
                </span>
                {tenPercent.overage > 0 && (
                  <Button size="sm" variant="destructive" className="h-8 text-xs">
                    Generate Cure Letter
                  </Button>
                )}
              </div>
            </section>

            {/* Section F,G,H: Unlimited */}
            <section className="space-y-1.5">
              <div className="flex items-center gap-2 pb-1">
                <Badge variant="secondary" className="text-xs font-semibold px-2.5 py-1">
                  F, G, H — Unlimited
                </Badge>
                <span className="text-xs text-muted-foreground">
                  Sanity badges highlight outliers
                </span>
              </div>
              <HotTable
                data={unlimitedRows}
                colHeaders={['Fee', 'LE (borrower)', 'CD (borrower)', 'Δ']}
                columns={[
                  { data: 'fee', renderer: unlimitedFeeRenderer },
                  { data: 'le', renderer: amountRenderer },
                  { data: 'cd', renderer: amountRenderer },
                  { data: 'delta', renderer: deltaRenderer },
                ]}
                rowHeaders={true}
                height="auto"
                licenseKey="non-commercial-and-evaluation"
                colWidths={[400, 180, 180, 140]}
                autoColumnSize={true}
                className="htMiddle"
                readOnly={true}
              />
            </section>
          </div>

          {/* Exceptions Rail */}
          <div className="space-y-6">
            <div className="rounded-lg border bg-zinc-50 p-4 shadow-sm dark:bg-zinc-900">
              <div className="mb-3 flex items-center gap-2 text-xs font-bold text-zinc-900 dark:text-zinc-100">
                <ShieldAlert className="size-3.5 text-amber-600" />
                EXCEPTIONS ({exceptions.length})
              </div>
              {exceptions.length === 0 ? (
                <p className="text-xs text-muted-foreground">No active exceptions.</p>
              ) : (
                <ul className="space-y-2 text-xs">
                  {exceptions.map((entry: ExceptionEntry) => (
                    <li key={`${entry.section}-${entry.id}`}>
                      <div className="w-full rounded-md border px-2.5 py-2 bg-white dark:bg-zinc-800">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-xs">
                            {entry.section} · {entry.fee}
                          </span>
                          <Badge
                            className={cn(
                              'border text-[10px] px-1.5 py-0',
                              severityStyles[entry.severity],
                            )}
                          >
                            {entry.severity === 'error' ? 'Error' : 'Warn'}
                          </Badge>
                        </div>
                        <p className="mt-1 text-[11px] text-muted-foreground leading-snug">
                          {entry.message}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          </div>
        </>
        )}

        {/* TRID Compliance Status */}
        {selectedRecord?.financialSummary && (
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-3">
              TRID Compliance Status
            </h2>
            <div className="text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-line">
              {selectedRecord.financialSummary.trid_compliance}
            </div>
          </div>
        )}

        {/* Key Changes from LE to CD */}
        {selectedRecord?.financialSummary?.key_changes && selectedRecord.financialSummary.key_changes.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-3">
              Key Changes from LE to CD
            </h2>
            <ul className="space-y-2">
              {selectedRecord.financialSummary.key_changes.map((change, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                  <span className="text-blue-500 mt-1">•</span>
                  <span>{change}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Recommendations */}
        {selectedRecord?.financialSummary?.recommendations && selectedRecord.financialSummary.recommendations.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-3">
              Recommendations
            </h2>
            <ul className="space-y-2">
              {selectedRecord.financialSummary.recommendations.map((rec, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                  <span className="text-emerald-500 mt-1">•</span>
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Risk Assessment */}
        {selectedRecord?.financialSummary && (
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-3">
              Risk Assessment
            </h2>
            <div className="text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-line">
              {selectedRecord.financialSummary.risk_assessment}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
