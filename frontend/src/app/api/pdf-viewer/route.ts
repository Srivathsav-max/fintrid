import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const pdfPath = searchParams.get('path');

    if (!pdfPath) {
      return NextResponse.json(
        { error: 'PDF path is required' },
        { status: 400 }
      );
    }
    const absolutePath = path.isAbsolute(pdfPath)
      ? pdfPath
      : path.join(process.cwd(), '..', 'backend', pdfPath);

    if (!fs.existsSync(absolutePath)) {
      return NextResponse.json(
        { error: 'PDF file not found' },
        { status: 404 }
      );
    }

    const fileBuffer = fs.readFileSync(absolutePath);

    return new NextResponse(fileBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'inline',
      },
    });
  } catch (error) {
    console.error('Error serving PDF:', error);
    return NextResponse.json(
      { error: 'Failed to serve PDF file' },
      { status: 500 }
    );
  }
}
