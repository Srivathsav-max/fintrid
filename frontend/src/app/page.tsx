'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { FileUpload } from '@/components/ui/file-upload';
import { Button } from '@/components/ui/button';
import { Loader2, CheckCircle2, Sparkles } from 'lucide-react';

interface ProgressStep {
  step: string;
  message: string;
  timestamp: number;
  status?: 'processing' | 'completed' | 'error';
}

export default function Home() {
  const router = useRouter();
  const [loanEstimateFiles, setLoanEstimateFiles] = useState<File[]>([]);
  const [closingDisclosureFiles, setClosingDisclosureFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);

  const handleSubmit = async () => {
    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(false);
    setProgressSteps([]);

    try {
      const formData = new FormData();
      
      if (loanEstimateFiles.length > 0) {
        formData.append('loanEstimate', loanEstimateFiles[0]);
      }
      
      if (closingDisclosureFiles.length > 0) {
        formData.append('closingDisclosure', closingDisclosureFiles[0]);
      }

      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.step) {
                setProgressSteps(prev => [...prev, { 
                  ...data, 
                  timestamp: Date.now(),
                  status: data.step === 'complete' || data.step === 'done' ? 'completed' : data.step === 'error' ? 'error' : 'processing'
                }]);
                
                if (data.step === 'complete' || data.step === 'done') {
                  setUploadSuccess(true);
                  setTimeout(() => router.push('/data'), 1500);
                }
                
                if (data.step === 'error') {
                  throw new Error(data.message);
                }
              }
            } catch (e) {
              console.error('Failed to parse SSE:', e);
            }
          }
        }
      }

    } catch (error) {
      console.error('Upload error:', error);
      setUploadError(error instanceof Error ? error.message : 'An error occurred');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-zinc-950">
      <main className="w-full max-w-7xl px-6 py-12">
        {/* Header - hidden during processing */}
        {!isUploading && (
          <div className="mb-12 text-center">
            <h1 className="mb-4 text-4xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
              Document Upload Portal
            </h1>
            <p className="text-lg text-zinc-600 dark:text-zinc-400">
              Upload your financial documents for review
            </p>
          </div>
        )}

        {/* Upload Form - only show when not uploading */}
        {!isUploading && (
          <div className="space-y-8 rounded-xl bg-white p-8 shadow-sm dark:bg-zinc-900">
            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              <FileUpload
                title="Loan Estimate Documents"
                description="Upload one or more Loan Estimate PDF files"
                accept=".pdf"
                multiple={true}
                onFilesChange={setLoanEstimateFiles}
              />

              <FileUpload
                title="Closing Disclosure Documents"
                description="Upload one or more Closing Disclosure PDF files"
                accept=".pdf"
                multiple={true}
                onFilesChange={setClosingDisclosureFiles}
              />
            </div>

            <div className="border-t border-zinc-200 dark:border-zinc-800 pt-6 space-y-4">
              {uploadError && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-center dark:border-rose-900 dark:bg-rose-950">
                  <p className="text-sm font-medium text-rose-900 dark:text-rose-100">
                    {uploadError}
                  </p>
                </div>
              )}

              <div className="flex justify-center">
                <Button
                  onClick={handleSubmit}
                  disabled={
                    loanEstimateFiles.length === 0 && closingDisclosureFiles.length === 0
                  }
                  className="min-w-[200px]"
                  size="lg"
                >
                  Submit Documents
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Processing Screen - Full screen takeover */}
        {isUploading && (
          <div className="flex flex-col items-center justify-center min-h-[600px]">
            {/* Header */}
            <div className="text-center mb-12">
               <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-linear-to-br from-blue-500 to-indigo-600 mb-4 shadow-lg">
                <Loader2 className="h-8 w-8 text-white animate-spin" />
              </div>
              <h2 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50 mb-2">
                Processing Your Documents
              </h2>
              <p className="text-zinc-600 dark:text-zinc-400">
                AI is analyzing your files and extracting data
              </p>
            </div>

            {/* Progress Checklist */}
            <div className="w-full max-w-2xl">
              <div className="relative min-h-[400px]">
                {/* Progress Steps Container */}
                <div className="space-y-3">
                  {progressSteps.map((step, idx) => {
                    const isCompleted = step.status === 'completed' || step.step === 'complete' || step.step === 'done';
                    const isError = step.status === 'error';

                    return (
                      <div
                        key={idx}
                        className="opacity-0 animate-marquee-up"
                        style={{
                          animationDelay: `${idx * 0.1}s`,
                          animationFillMode: 'forwards'
                        }}
                      >
                        <div className="flex items-center gap-3">
                          <div className="shrink-0">
                            {isCompleted ? (
                              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                            ) : isError ? (
                              <CheckCircle2 className="h-5 w-5 text-rose-500" />
                            ) : (
                              <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
                            )}
                          </div>

                          <p
                            className={`
                              text-sm font-medium
                              ${isCompleted
                                ? 'text-emerald-600 dark:text-emerald-400'
                                : isError
                                ? 'text-rose-600 dark:text-rose-400'
                                : 'text-zinc-900 dark:text-zinc-100'
                              }
                            `}
                          >
                            {step.message}
                          </p>
                        </div>
                      </div>
                    );
                  })}

                  {/* Initial Loading State */}
                  {progressSteps.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-12">
                      <Loader2 className="h-12 w-12 animate-spin text-blue-500 mb-4" />
                      <p className="text-sm text-zinc-500 dark:text-zinc-400">
                        Initializing...
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Success Message */}
              {uploadSuccess && (
                <div className="mt-8 rounded-lg border border-emerald-200 bg-linear-to-r from-emerald-50 to-green-50 p-6 text-center dark:border-emerald-900 dark:from-emerald-950 dark:to-green-950 animate-fade-in">
                  <div className="flex items-center justify-center gap-3 mb-2">
                    <Sparkles className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
                    <h3 className="text-lg font-semibold text-emerald-900 dark:text-emerald-100">
                      Processing Complete!
                    </h3>
                  </div>
                  <p className="text-sm text-emerald-700 dark:text-emerald-300">
                    Redirecting to data page...
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
