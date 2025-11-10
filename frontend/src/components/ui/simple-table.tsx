'use client';

import { cn } from '@/lib/utils';

interface SimpleTableProps {
  title: string;
  headers: string[];
  data: (string | number)[][];
  className?: string;
}

export function SimpleTable({ title, headers, data, className }: SimpleTableProps) {
  return (
    <div className={cn('w-full space-y-3', className)}>
      <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
        {title}
      </h3>
      <div className="overflow-hidden rounded-lg border border-zinc-300 dark:border-zinc-700">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-zinc-100 dark:bg-zinc-800">
              {headers.map((header, index) => (
                <th
                  key={index}
                  className="border border-zinc-300 px-4 py-2 text-left text-sm font-semibold text-zinc-900 dark:border-zinc-700 dark:text-zinc-50"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className="bg-white even:bg-zinc-50 dark:bg-zinc-900 dark:even:bg-zinc-800/50"
              >
                {row.map((cell, cellIndex) => (
                  <td
                    key={cellIndex}
                    className="border border-zinc-300 px-4 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
