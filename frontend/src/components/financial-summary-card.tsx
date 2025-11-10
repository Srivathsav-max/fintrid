'use client';

import { FinancialProfileSummary } from '@/types/backend';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, AlertTriangle, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface FinancialSummaryCardProps {
  summary: FinancialProfileSummary;
}

export function FinancialSummaryCard({ summary }: FinancialSummaryCardProps) {
  const getRiskColor = (riskText: string) => {
    const lowerRisk = riskText.toLowerCase();
    if (lowerRisk.includes('low') || lowerRisk.includes('minimal')) {
      return 'text-emerald-600 dark:text-emerald-400';
    }
    if (lowerRisk.includes('medium') || lowerRisk.includes('moderate')) {
      return 'text-amber-600 dark:text-amber-400';
    }
    if (lowerRisk.includes('high') || lowerRisk.includes('significant')) {
      return 'text-rose-600 dark:text-rose-400';
    }
    return 'text-zinc-600 dark:text-zinc-400';
  };

  const getChangeIcon = (change: string) => {
    const lowerChange = change.toLowerCase();
    if (lowerChange.includes('increase') || lowerChange.includes('higher') || lowerChange.includes('more')) {
      return <TrendingUp className="h-4 w-4 text-rose-500" />;
    }
    if (lowerChange.includes('decrease') || lowerChange.includes('lower') || lowerChange.includes('less')) {
      return <TrendingDown className="h-4 w-4 text-emerald-500" />;
    }
    return <Minus className="h-4 w-4 text-zinc-400" />;
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-blue-500" />
              Borrower Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed">
              {summary.borrower_overview}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-blue-500" />
              Loan Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed">
              {summary.loan_overview}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Cost Analysis</CardTitle>
          <CardDescription>Breakdown of closing costs and cash to close</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-line">
            {summary.cost_analysis}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>TRID Compliance Status</CardTitle>
          <CardDescription>Tolerance analysis and violations</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-line">
            {summary.trid_compliance}
          </p>
        </CardContent>
      </Card>

      {summary.key_changes && summary.key_changes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Key Changes from LE to CD</CardTitle>
            <CardDescription>Notable differences between documents</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {summary.key_changes.map((change, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  {getChangeIcon(change)}
                  <span className="text-sm text-zinc-700 dark:text-zinc-300">
                    {change}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {summary.recommendations && summary.recommendations.length > 0 && (
        <Card className="border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-amber-900 dark:text-amber-100">
              <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              Recommendations
            </CardTitle>
            <CardDescription className="text-amber-700 dark:text-amber-300">
              Important items to review
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {summary.recommendations.map((rec, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <div className="mt-1">
                    <div className="h-2 w-2 rounded-full bg-amber-500" />
                  </div>
                  <span className="text-sm text-amber-900 dark:text-amber-100">
                    {rec}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Risk Assessment</CardTitle>
          <CardDescription>Overall loan risk profile</CardDescription>
        </CardHeader>
        <CardContent>
          <p className={`text-sm font-medium leading-relaxed ${getRiskColor(summary.risk_assessment)}`}>
            {summary.risk_assessment}
          </p>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Badge variant="outline" className="text-xs">
          Generated {new Date(summary.generated_at).toLocaleString()}
        </Badge>
      </div>
    </div>
  );
}

