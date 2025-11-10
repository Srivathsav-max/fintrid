import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/db';
import { tridAnalysisTable } from '@/db/schema';
import { desc, eq } from 'drizzle-orm';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const recordId = searchParams.get('id');

    if (recordId) {
      const [record] = await db
        .select()
        .from(tridAnalysisTable)
        .where(eq(tridAnalysisTable.id, parseInt(recordId)))
        .limit(1);

      if (!record) {
        return NextResponse.json(
          { error: 'Record not found' },
          { status: 404 }
        );
      }

      return NextResponse.json({ success: true, data: record });
    }

    const records = await db
      .select()
      .from(tridAnalysisTable)
      .orderBy(desc(tridAnalysisTable.createdAt));

    return NextResponse.json({
      success: true,
      data: records,
      count: records.length,
    });

  } catch (error) {
    console.error('Fetch error:', error);
    
    return NextResponse.json(
      {
        error: 'Failed to fetch records',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const recordId = searchParams.get('id');

    if (!recordId) {
      return NextResponse.json(
        { error: 'Record ID is required' },
        { status: 400 }
      );
    }

    const [deletedRecord] = await db
      .delete(tridAnalysisTable)
      .where(eq(tridAnalysisTable.id, parseInt(recordId)))
      .returning();

    if (!deletedRecord) {
      return NextResponse.json(
        { error: 'Record not found' },
        { status: 404 }
      );
    }

    return NextResponse.json({
      success: true,
      message: 'Record deleted successfully',
      data: deletedRecord,
    });

  } catch (error) {
    console.error('Delete error:', error);
    
    return NextResponse.json(
      {
        error: 'Failed to delete record',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

