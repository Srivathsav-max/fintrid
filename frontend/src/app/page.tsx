'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { FileUpload } from '@/components/ui/file-upload';
import { Button } from '@/components/ui/button';
import { Loader2, CheckCircle2, Sparkles, Upload, FileText, Zap } from 'lucide-react';

interface ProgressStep {
  step: string;
  message: string;
  timestamp: number;
  status?: 'processing' | 'completed' | 'error';
}

export default function Home() {
  const router = useRouter();
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
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
      
      uploadedFiles.forEach(file => {
        formData.append('documents', file);
      });

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
                setProgressSteps(prev => {
                  const updatedPrev = prev.map((step, idx) => {
                    if (idx === prev.length - 1 && step.status === 'processing') {
                      return { ...step, status: 'completed' as const };
                    }
                    return step;
                  });

                  const newStatus = data.step === 'complete' || data.step === 'done'
                    ? 'completed' as const
                    : data.step === 'error'
                    ? 'error' as const
                    : 'processing' as const;

                  return [...updatedPrev, {
                    ...data,
                    timestamp: Date.now(),
                    status: newStatus
                  }];
                });

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
    <div className="flex min-h-screen items-center justify-center bg-white font-sans dark:bg-zinc-950">
      <main className="w-full max-w-4xl px-6 py-12">
        {/* Header - hidden during processing */}
        {!isUploading && (
          <div className="mb-10 text-center">
            <h1 className="mb-3 text-4xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-5xl">
              TRID Analysis Portal
            </h1>
            <p className="text-lg text-zinc-600 dark:text-zinc-400 max-w-2xl mx-auto">
              Intelligent document analysis for Loan Estimates and Closing Disclosures to ensure TRID compliance
            </p>
          </div>
        )}

        {/* Upload Form - only show when not uploading */}
        {!isUploading && (
          <div className="space-y-6">
            {/* Feature Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-zinc-100 dark:bg-zinc-800">
                    <Upload className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
                  </div>
                  <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-50">
                    Upload Documents
                  </h3>
                </div>
                <p className="text-xs text-zinc-600 dark:text-zinc-400">
                  Upload LE and CD PDFs for automated analysis
                </p>
              </div>

              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-zinc-100 dark:bg-zinc-800">
                    <Zap className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
                  </div>
                  <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-50">
                    AI-Powered Analysis
                  </h3>
                </div>
                <p className="text-xs text-zinc-600 dark:text-zinc-400">
                  Advanced AI extracts and validates data
                </p>
              </div>

              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-zinc-100 dark:bg-zinc-800">
                    <Sparkles className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
                  </div>
                  <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-50">
                    TRID Compliance
                  </h3>
                </div>
                <p className="text-xs text-zinc-600 dark:text-zinc-400">
                  Automatic tolerance validation and reporting
                </p>
              </div>
            </div>

            {/* Upload Card */}
            <div className="space-y-6 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white p-8 shadow-lg dark:bg-zinc-900">
              <FileUpload
                title="Select PDF Files"
                description="Drag and drop your PDF files here, or click to browse"
                accept=".pdf"
                multiple={true}
                onFilesChange={setUploadedFiles}
              />

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
                    disabled={uploadedFiles.length === 0}
                    className="min-w-[220px] bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 dark:text-zinc-900"
                    size="lg"
                  >
                    <Zap className="mr-2 h-4 w-4" />
                    Start Analysis
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Processing Screen - Full screen takeover */}
        {isUploading && (
          <div className="flex flex-col items-center justify-center min-h-[80vh]">
            {/* Processing Header */}
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50 mb-2">
                Analyzing Documents
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Our AI is processing your files and extracting data
              </p>
            </div>

            {/* Progress Checklist - Centered */}
            <div className="w-full max-w-2xl">
              <div className="relative min-h-[400px] flex flex-col items-center justify-center">
                {/* Progress Steps Container */}
                <div className="space-y-3 w-full bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-lg">
                  {progressSteps.map((step, idx) => {
                    const isCompleted = step.status === 'completed';
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
                        <div className="flex items-center gap-3 p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/50">
                          <div className="shrink-0">
                            {isCompleted ? (
                              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-zinc-200 dark:bg-zinc-700">
                                <CheckCircle2 className="h-4 w-4 text-zinc-900 dark:text-zinc-100" />
                              </div>
                            ) : isError ? (
                              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-zinc-200 dark:bg-zinc-700">
                                <CheckCircle2 className="h-4 w-4 text-zinc-900 dark:text-zinc-100" />
                              </div>
                            ) : (
                              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-zinc-200 dark:bg-zinc-700">
                                <Loader2 className="h-4 w-4 text-zinc-900 dark:text-zinc-100 animate-spin" />
                              </div>
                            )}
                          </div>

                          <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                            {step.message}
                          </p>
                        </div>
                      </div>
                    );
                  })}

                  {/* Initial Loading State */}
                  {progressSteps.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-12">
                      <div className="mb-4 inline-flex items-center justify-center w-16 h-16 rounded-full bg-zinc-200 dark:bg-zinc-700">
                        <Loader2 className="h-8 w-8 animate-spin text-zinc-900 dark:text-zinc-100" />
                      </div>
                      <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
                        Initializing analysis engine...
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Success Message */}
              {uploadSuccess && (
                <div className="mt-6 rounded-xl border border-zinc-200 bg-zinc-50 p-6 text-center dark:border-zinc-800 dark:bg-zinc-900 animate-fade-in shadow-lg">
                  <div className="flex items-center justify-center gap-3 mb-2">
                    <div className="flex items-center justify-center w-10 h-10 rounded-full bg-zinc-200 dark:bg-zinc-700">
                      <Sparkles className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
                    </div>
                    <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                      Analysis Complete!
                    </h3>
                  </div>
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">
                    Redirecting to results dashboard...
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
