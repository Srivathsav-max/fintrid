'use client';

import { HotTable } from '@handsontable/react';
import { registerAllModules } from 'handsontable/registry';
import 'handsontable/dist/handsontable.full.min.css';
import { useMemo } from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { formatUSD, formatPercent } from '@/lib/formatters';
import { ArrowUp, ArrowDown, ShieldAlert } from 'lucide-react';
import type { ZeroToleranceDisplayRow, TenPercentDisplayRow, UnlimitedDisplayRow } from '@/lib/trid-rules';
import type { RowStatus } from '@/types/trid';

registerAllModules();

interface TridTableProps {
  data: (ZeroToleranceDisplayRow | TenPercentDisplayRow | UnlimitedDisplayRow)[];
  type: 'zero' | 'ten' | 'unlimited';
}

export function TridTable({ data, type }: TridTableProps) {
  const columns = useMemo(() => {
    if (type === 'zero') {
      return [
        {
          data: 'fee',
          title: 'Fee',
          width: 280,
          renderer: 'html',
          readOnly: true,
        },
        {
          data: 'le.borrower',
          title: 'LE (borrower)',
          width: 160,
          type: 'numeric',
          numericFormat: {
            pattern: '$0,0.00',
          },
          readOnly: true,
        },
        {
          data: 'cd.borrower',
          title: 'CD (borrower)',
          width: 160,
          type: 'numeric',
          numericFormat: {
            pattern: '$0,0.00',
          },
          readOnly: true,
        },
        {
          data: 'delta',
          title: 'Δ',
          width: 120,
          type: 'numeric',
          numericFormat: {
            pattern: '$0,0.00',
          },
          readOnly: true,
        },
        {
          data: 'status',
          title: 'Status',
          width: 100,
          renderer: 'html',
          readOnly: true,
        },
      ];
    }

    if (type === 'ten') {
      return [
        {
          data: 'fee',
          title: 'Fee',
          width: 300,
          renderer: 'html',
          readOnly: true,
        },
        {
          data: 'provider',
          title: 'Provider',
          width: 280,
          renderer: 'html',
          readOnly: true,
        },
        {
          data: 'inTenGroup',
          title: 'In 10% group?',
          width: 140,
          renderer: 'html',
          readOnly: true,
        },
        {
          data: 'le.borrower',
          title: 'LE (borrower)',
          width: 160,
          type: 'numeric',
          numericFormat: {
            pattern: '$0,0.00',
          },
          readOnly: true,
        },
        {
          data: 'cd.borrower',
          title: 'CD (borrower)',
          width: 160,
          type: 'numeric',
          numericFormat: {
            pattern: '$0,0.00',
          },
          readOnly: true,
        },
        {
          data: 'delta',
          title: 'Δ',
          width: 120,
          type: 'numeric',
          numericFormat: {
            pattern: '$0,0.00',
          },
          readOnly: true,
        },
      ];
    }

    return [
      {
        data: 'fee',
        title: 'Fee',
        width: 300,
        renderer: 'html',
        readOnly: true,
      },
      {
        data: 'le.borrower',
        title: 'LE (borrower)',
        width: 160,
        type: 'numeric',
        numericFormat: {
          pattern: '$0,0.00',
        },
        readOnly: true,
      },
      {
        data: 'cd.borrower',
        title: 'CD (borrower)',
        width: 160,
        type: 'numeric',
        numericFormat: {
          pattern: '$0,0.00',
        },
        readOnly: true,
      },
      {
        data: 'delta',
        title: 'Δ',
        width: 120,
        type: 'numeric',
        numericFormat: {
          pattern: '$0,0.00',
        },
        readOnly: true,
      },
      {
        data: 'flags',
        title: 'Red-flags',
        width: 150,
        renderer: 'html',
        readOnly: true,
      },
    ];
  }, [type]);

  return (
    <div className="w-full">
      <HotTable
        data={data}
        columns={columns}
        colHeaders={true}
        rowHeaders={true}
        height="auto"
        autoWrapRow={true}
        autoWrapCol={true}
        licenseKey="non-commercial-and-evaluation"
        stretchH="all"
        className="htMiddle"
        cells={function (row, col) {
          const cellProperties: any = {};

          if (this.instance.getDataAtRowProp(row, 'status')) {
            cellProperties.renderer = function (
              instance: any,
              td: HTMLTableCellElement,
              row: number,
              col: number,
              prop: string | number,
              value: any,
              cellProperties: any
            ) {
              const status = instance.getDataAtRowProp(row, 'status') as RowStatus;
              const statusColors = {
                PASS: 'bg-emerald-100 text-emerald-800 border-emerald-200',
                FAIL: 'bg-rose-100 text-rose-800 border-rose-200',
                REVIEW: 'bg-amber-100 text-amber-800 border-amber-200',
              };

              td.innerHTML = `<span class="inline-flex px-2.5 py-0.5 rounded border text-xs font-semibold ${statusColors[status]}">${status}</span>`;
              return td;
            };
          }

          return cellProperties;
        }}
      />
    </div>
  );
}
