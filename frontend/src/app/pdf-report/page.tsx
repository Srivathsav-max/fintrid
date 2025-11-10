'use client';

import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { Loader2 } from 'lucide-react';

function PDFViewerContent() {
  const searchParams = useSearchParams();
  const pdfPath = searchParams.get('path');

  if (!pdfPath) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-zinc-50 dark:bg-zinc-950">
        <div className="text-center">
          <p className="text-sm text-muted-foreground">No PDF path provided</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen bg-zinc-50 dark:bg-zinc-950">
      <iframe
        src={`/api/pdf-viewer?path=${encodeURIComponent(pdfPath)}`}
        className="w-full h-full border-0"
        title="TRID Curated Report"
      />
    </div>
  );
}

export default function PDFReportPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen bg-zinc-50 dark:bg-zinc-950">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin text-zinc-500 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Loading PDF...</p>
          </div>
        </div>
      }
    >
      <PDFViewerContent />
    </Suspense>
  );
}
