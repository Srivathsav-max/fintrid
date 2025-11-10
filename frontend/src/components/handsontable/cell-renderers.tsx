'use client';

import { createRoot } from 'react-dom/client';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { formatUSD, formatPercent } from '@/lib/formatters';
import { ArrowUp, ArrowDown, ShieldAlert } from 'lucide-react';
import type { RowStatus, FlagDetail, PayerSplit } from '@/types/trid';

export function feeRenderer(
  instance: any,
  td: HTMLTableCellElement,
  row: number,
  col: number,
  prop: string | number,
  value: string,
  cellProperties: any
) {
  const flags = instance.getDataAtRowProp(row, 'flags') as FlagDetail[] | undefined;

  const container = document.createElement('div');
  container.className = 'flex items-center justify-between gap-2';

  const feeName = document.createElement('p');
  feeName.className = 'text-xs text-zinc-900 dark:text-zinc-50';
  feeName.textContent = value;
  container.appendChild(feeName);

  if (flags && flags.length > 0) {
    const flagsContainer = document.createElement('div');
    flagsContainer.className = 'flex items-center gap-1 shrink-0';

    flags.forEach((flag) => {
      const icon = document.createElement('div');
      const bgClass =
        flag.severity === 'error'
          ? 'bg-rose-500'
          : 'bg-amber-500';
      icon.className = `w-1.5 h-1.5 rounded-full ${bgClass}`;
      icon.title = flag.label;
      flagsContainer.appendChild(icon);
    });

    container.appendChild(flagsContainer);
  }

  td.innerHTML = '';
  td.appendChild(container);
  td.className = 'htMiddle';
  return td;
}

export function statusRenderer(
  instance: any,
  td: HTMLTableCellElement,
  row: number,
  col: number,
  prop: string | number,
  value: RowStatus,
  cellProperties: any
) {
  const statusConfig = {
    PASS: { dot: 'bg-emerald-500', text: 'text-emerald-700' },
    FAIL: { dot: 'bg-rose-500', text: 'text-rose-700' },
    REVIEW: { dot: 'bg-amber-500', text: 'text-amber-700' },
  };

  const config = statusConfig[value];
  const container = document.createElement('div');
  container.className = 'flex items-center justify-center gap-1.5';

  const dot = document.createElement('div');
  dot.className = `w-1.5 h-1.5 rounded-full ${config.dot}`;
  container.appendChild(dot);

  const text = document.createElement('span');
  text.className = `text-xs font-medium ${config.text}`;
  text.textContent = value;
  container.appendChild(text);

  td.innerHTML = '';
  td.appendChild(container);
  td.className = 'htCenter';
  return td;
}

export function deltaRenderer(
  instance: any,
  td: HTMLTableCellElement,
  row: number,
  col: number,
  prop: string | number,
  value: number,
  cellProperties: any
) {
  const changeReason = instance.getDataAtRowProp(row, 'changeReason') as string;
  const isPositive = value > 0;

  const container = document.createElement('div');
  container.className = 'flex items-center justify-center gap-1';
  container.title = changeReason || 'No change noted';

  if (isPositive) {
    const icon = document.createElement('span');
    icon.innerHTML = '↑';
    icon.className = 'text-rose-700 text-xs';
    container.appendChild(icon);
  } else if (value < 0) {
    const icon = document.createElement('span');
    icon.innerHTML = '↓';
    icon.className = 'text-emerald-700 text-xs';
    container.appendChild(icon);
  }

  const amount = document.createElement('span');
  amount.className = isPositive
    ? 'text-rose-700 font-medium text-xs'
    : value === 0
    ? 'text-zinc-600 font-medium text-xs'
    : 'text-emerald-700 font-medium text-xs';
  amount.textContent = formatUSD(Math.abs(value));
  container.appendChild(amount);

  td.innerHTML = '';
  td.appendChild(container);
  td.className = 'htCenter';
  return td;
}

export function amountRenderer(
  instance: any,
  td: HTMLTableCellElement,
  row: number,
  col: number,
  prop: string | number,
  value: PayerSplit,
  cellProperties: any
) {
  const container = document.createElement('div');
  container.className = 'flex items-center justify-end gap-2';

  const mainAmount = document.createElement('p');
  mainAmount.className = 'text-xs font-medium text-zinc-900 dark:text-zinc-100';
  mainAmount.textContent = formatUSD(value.borrower);
  container.appendChild(mainAmount);

  const notifications: Array<string> = [];
  if (value.seller) notifications.push('S');
  if (value.other) notifications.push('O');

  if (notifications.length > 0) {
    const notifContainer = document.createElement('div');
    notifContainer.className = 'flex items-center gap-1 shrink-0';

    notifications.forEach((label) => {
      const dot = document.createElement('div');
      dot.className = 'w-1.5 h-1.5 rounded-full bg-blue-500';
      dot.title = label === 'S' ? `Seller paid: ${formatUSD(value.seller || 0)}` : `Other paid: ${formatUSD(value.other || 0)}`;
      notifContainer.appendChild(dot);
    });

    container.appendChild(notifContainer);
  }

  td.innerHTML = '';
  td.appendChild(container);
  td.className = 'htRight';
  return td;
}

export function providerRenderer(
  instance: any,
  td: HTMLTableCellElement,
  row: number,
  col: number,
  prop: string | number,
  value: any,
  cellProperties: any
) {
  const effectiveOnWhitelist = instance.getDataAtRowProp(row, 'effectiveOnWhitelist') as boolean;
  const matchConfidence = instance.getDataAtRowProp(row, 'matchConfidence') as number;
  const provider = instance.getDataAtRowProp(row, 'provider') as string;

  const container = document.createElement('div');
  container.className = 'flex items-center gap-2 flex-wrap';

  const statusBadge = document.createElement('span');
  const statusClass = effectiveOnWhitelist
    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
    : 'border-amber-200 bg-amber-50 text-amber-800';
  statusBadge.className = `inline-flex items-center px-1.5 py-0 border text-[10px] rounded ${statusClass}`;
  statusBadge.textContent = effectiveOnWhitelist ? 'On-list' : 'Off-list';
  container.appendChild(statusBadge);

  const confidenceBadge = document.createElement('span');
  confidenceBadge.className =
    'inline-flex items-center px-1.5 py-0 border border-zinc-300 text-[10px] rounded';
  confidenceBadge.textContent = `Confidence ${formatPercent(matchConfidence)}`;
  confidenceBadge.title = 'Vendor match confidence';
  container.appendChild(confidenceBadge);

  td.innerHTML = '';
  td.appendChild(container);
  return td;
}

export function tenGroupRenderer(
  instance: any,
  td: HTMLTableCellElement,
  row: number,
  col: number,
  prop: string | number,
  value: boolean,
  cellProperties: any
) {
  const badge = document.createElement('span');
  const badgeClass = value
    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
    : 'border-zinc-200 text-zinc-700';
  badge.className = `inline-flex items-center px-1.5 py-0 border text-[10px] rounded ${badgeClass}`;
  badge.textContent = value ? 'Yes' : 'No';

  td.innerHTML = '';
  td.appendChild(badge);
  return td;
}

export function unlimitedFeeRenderer(
  instance: any,
  td: HTMLTableCellElement,
  row: number,
  col: number,
  prop: string | number,
  value: string,
  cellProperties: any
) {
  const bucket = instance.getDataAtRowProp(row, 'bucket') as string;
  const perDiemDays = instance.getDataAtRowProp(row, 'perDiemDays') as number | undefined;
  const escrowMonths = instance.getDataAtRowProp(row, 'escrowMonths') as number | undefined;
  const isOptional = instance.getDataAtRowProp(row, 'isOptional') as boolean | undefined;
  const flags = instance.getDataAtRowProp(row, 'flags') as FlagDetail[] | undefined;

  const container = document.createElement('div');
  container.className = 'flex items-center justify-between gap-2';

  const leftContent = document.createElement('div');
  leftContent.className = 'flex items-center gap-2 flex-wrap';

  const feeName = document.createElement('span');
  feeName.className = 'text-xs text-zinc-900 dark:text-zinc-50';
  feeName.textContent = value;
  leftContent.appendChild(feeName);

  const bucketBadge = document.createElement('span');
  bucketBadge.className = 'inline-flex items-center px-1.5 py-0 bg-zinc-200 text-zinc-800 text-[10px] rounded';
  bucketBadge.textContent = `${bucket}`;
  leftContent.appendChild(bucketBadge);

  if (bucket === 'F' && perDiemDays) {
    const daysBadge = document.createElement('span');
    daysBadge.className = 'inline-flex items-center px-1.5 py-0 border border-zinc-300 text-[10px] rounded';
    daysBadge.textContent = `${perDiemDays}d`;
    daysBadge.title = `${perDiemDays} per-diem days`;
    leftContent.appendChild(daysBadge);
  }

  if (bucket === 'G' && escrowMonths) {
    const monthsBadge = document.createElement('span');
    monthsBadge.className = 'inline-flex items-center px-1.5 py-0 border border-zinc-300 text-[10px] rounded';
    monthsBadge.textContent = `${escrowMonths}m`;
    monthsBadge.title = `${escrowMonths} months`;
    leftContent.appendChild(monthsBadge);
  }

  if (bucket === 'H') {
    const optionalBadge = document.createElement('span');
    optionalBadge.className = 'inline-flex items-center px-1.5 py-0 border border-zinc-300 text-[10px] rounded';
    optionalBadge.textContent = isOptional ? 'Opt' : 'Req';
    optionalBadge.title = isOptional ? 'Optional' : 'Required';
    leftContent.appendChild(optionalBadge);
  }

  container.appendChild(leftContent);

  if (flags && flags.length > 0) {
    const flagsContainer = document.createElement('div');
    flagsContainer.className = 'flex items-center gap-1 shrink-0';

    flags.forEach((flag) => {
      const dot = document.createElement('div');
      const bgClass =
        flag.severity === 'error'
          ? 'bg-rose-500'
          : 'bg-amber-500';
      dot.className = `w-1.5 h-1.5 rounded-full ${bgClass}`;
      dot.title = flag.label;
      flagsContainer.appendChild(dot);
    });

    container.appendChild(flagsContainer);
  }

  td.innerHTML = '';
  td.appendChild(container);
  td.className = 'htMiddle';
  return td;
}
