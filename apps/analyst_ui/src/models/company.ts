export interface Company {
  id: number;
  name: string;
  ticker?: string | null;
  created_at: string;
}

export interface DataQualityIssue {
  id: number;
  company_id: number;
  document_id?: number | null;
  issue_type: string;
  severity: string;
  concept?: string | null;
  message: string;
  is_resolved: boolean;
  created_at: string;
}

export interface CompanySummary {
  name: string;
  ticker?: string;
  rating: string;
  risk: string;
  riskLevel: 'low' | 'moderate' | 'elevated' | 'high';
  latestFiling: string;
  dataQualityPct: number;
  verifiedCount: number;
  totalFactsCount: number;
  issuesCount: number;
}

/**
 * Deterministic helper to evaluate credit rating and risk level
 * from financial leverage, coverage, and liquidity metrics.
 */
export function calculateCompanyRating(metrics: { metric_name: string; current_value?: number | null }[]): {
  rating: string;
  risk: string;
  riskLevel: 'low' | 'moderate' | 'elevated' | 'high';
} {
  const getVal = (name: string) => metrics.find(m => m.metric_name === name)?.current_value ?? null;

  const netDebtEbitda = getVal('net_debt_to_ebitda');
  const interestCoverage = getVal('interest_coverage') ?? getVal('ebitda_to_interest');
  const currentRatio = getVal('current_ratio');

  if (netDebtEbitda === null && interestCoverage === null) {
    return { rating: 'BB', risk: 'Elevated', riskLevel: 'elevated' };
  }

  // Underwriting risk rules
  if (
    (netDebtEbitda !== null && netDebtEbitda > 5.0) ||
    (interestCoverage !== null && interestCoverage < 1.5) ||
    (currentRatio !== null && currentRatio < 0.8)
  ) {
    return { rating: 'B', risk: 'High', riskLevel: 'high' };
  } else if (
    (netDebtEbitda !== null && netDebtEbitda > 3.5) ||
    (interestCoverage !== null && interestCoverage < 3.0) ||
    (currentRatio !== null && currentRatio < 1.0)
  ) {
    return { rating: 'BB', risk: 'Elevated', riskLevel: 'elevated' };
  } else if (
    (netDebtEbitda !== null && netDebtEbitda > 2.0) ||
    (interestCoverage !== null && interestCoverage < 5.0)
  ) {
    return { rating: 'BBB', risk: 'Moderate', riskLevel: 'moderate' };
  } else {
    return { rating: 'A', risk: 'Low', riskLevel: 'low' };
  }
}

