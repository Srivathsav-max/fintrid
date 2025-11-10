import { NextRequest } from 'next/server';
import { db } from '@/db';
import { tridAnalysisTable } from '@/db/schema';
import type { BackendExtractResponse, LoanEstimateRecord } from '@/types/backend';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    
    const loanEstimateFile = formData.get('loanEstimate') as File | null;
    const closingDisclosureFile = formData.get('closingDisclosure') as File | null;

    if (!loanEstimateFile && !closingDisclosureFile) {
      const encoder = new TextEncoder();
      return new Response(
        encoder.encode('data: ' + JSON.stringify({ step: 'error', message: 'At least one file is required' }) + '\n\n'),
        {
          status: 400,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
          },
        }
      );
    }

    const backendFormData = new FormData();
    const files: File[] = [];
    const fileNames: Record<string, string> = {};

    if (loanEstimateFile) {
      backendFormData.append('files', loanEstimateFile);
      files.push(loanEstimateFile);
      fileNames.loanEstimate = loanEstimateFile.name;
    }

    if (closingDisclosureFile) {
      backendFormData.append('files', closingDisclosureFile);
      files.push(closingDisclosureFile);
      fileNames.closingDisclosure = closingDisclosureFile.name;
    }

    if (files.length === 1) {
      backendFormData.append('files', files[0]);
    }

    const backendResponse = await fetch(`${BACKEND_URL}/api/extract/pair/stream`, {
      method: 'POST',
      body: backendFormData,
    });

    if (!backendResponse.ok) {
      const errorText = await backendResponse.text();
      const encoder = new TextEncoder();
      return new Response(
        encoder.encode('data: ' + JSON.stringify({ step: 'error', message: `Backend failed: ${errorText}` }) + '\n\n'),
        {
          status: 500,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
          },
        }
      );
    }

    if (!backendResponse.body) {
      throw new Error('No response body from backend');
    }

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const reader = backendResponse.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalPayload: BackendExtractResponse | null = null;

        try {
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

                  if (data.step === 'complete' && data.payload) {
                    finalPayload = data.payload;
                  }

                  controller.enqueue(encoder.encode(line + '\n'));
                } catch (e) {
                  console.error('Failed to parse SSE:', e);
                }
              }
            }
          }

          if (!finalPayload) {
            controller.enqueue(encoder.encode('data: ' + JSON.stringify({ step: 'error', message: 'No final payload received' }) + '\n\n'));
            controller.close();
            return;
          }

          const backendData = finalPayload;
          console.log('Backend response:', JSON.stringify(backendData, null, 2));

          controller.enqueue(encoder.encode('data: ' + JSON.stringify({ step: 'saving', message: 'Saving to database' }) + '\n\n'));

          const processedDocuments: Record<string, LoanEstimateRecord> = {};

          for (const fileInfo of backendData.files) {
            if (fileInfo.json_data) {
              processedDocuments[fileInfo.source_file] = fileInfo.json_data;
              console.log(`Processed ${fileInfo.source_file}:`, fileInfo.json_data);
            }
          }

          let loanEstimateData: LoanEstimateRecord | null = null;
          let closingDisclosureData: LoanEstimateRecord | null = null;

          if (loanEstimateFile && processedDocuments[loanEstimateFile.name]) {
            loanEstimateData = processedDocuments[loanEstimateFile.name];
            console.log('Found Loan Estimate data');
          }

          if (closingDisclosureFile && processedDocuments[closingDisclosureFile.name]) {
            closingDisclosureData = processedDocuments[closingDisclosureFile.name];
            console.log('Found Closing Disclosure data');
          }

          if (!loanEstimateData && closingDisclosureData) {
            loanEstimateData = closingDisclosureData;
          }
          if (!closingDisclosureData && loanEstimateData) {
            closingDisclosureData = loanEstimateData;
          }

          const primaryDoc = loanEstimateData || closingDisclosureData;
          const loanId = primaryDoc?.loan?.loan_id || null;
          const applicantName = primaryDoc?.applicants?.[0]?.name || null;
          const propertyAddress = primaryDoc?.property?.address || null;
          const salePrice = primaryDoc?.sale_price?.toString() || null;
          const loanAmount = primaryDoc?.loan_terms?.loan_amount?.toString() || null;

          const valuesToInsert = {
            loanEstimateFileName: fileNames.loanEstimate || null,
            closingDisclosureFileName: fileNames.closingDisclosure || null,
            loanId,
            applicantName,
            propertyAddress,
            salePrice,
            loanAmount,
            loanEstimateData: loanEstimateData as any,
            closingDisclosureData: closingDisclosureData as any,
            tridComparison: backendData.trid_comparison as any,
            processingStatus: 'completed' as const,
            backendPipeline: backendData.meta.pipeline,
            landingModel: backendData.meta.landing_model,
            geminiModel: backendData.meta.gemini_model,
          };

          console.log('Inserting into database:', valuesToInsert);

          const [savedRecord] = await db
            .insert(tridAnalysisTable)
            .values(valuesToInsert)
            .returning();

          console.log('Saved record:', savedRecord);

          controller.enqueue(encoder.encode('data: ' + JSON.stringify({ 
            step: 'done', 
            message: 'All processing complete!',
            recordId: savedRecord.id 
          }) + '\n\n'));

          controller.close();
        } catch (error: unknown) {
          console.error('Stream processing error:', error);
          controller.enqueue(encoder.encode('data: ' + JSON.stringify({ 
            step: 'error', 
            message: error instanceof Error ? error.message : 'Unknown error' 
          }) + '\n\n'));
          controller.close();
        }
      }
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  } catch (error: unknown) {
    console.error('Upload error:', error);
    const encoder = new TextEncoder();
    return new Response(
      encoder.encode('data: ' + JSON.stringify({ 
        step: 'error', 
        message: error instanceof Error ? error.message : String(error) 
      }) + '\n\n'),
      {
        status: 500,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      }
    );
  }
}

