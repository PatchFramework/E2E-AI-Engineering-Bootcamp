export interface FinancialFact {
  id: number;
  company_id: number;
  concept: string;
  value: number;
  unit: string;
  fiscal_year: number;
  fiscal_period: string;
  version: number;
  origin: 'AI_GENERATED' | 'ANALYST_CORRECTED' | 'ANALYST_ENTERED';
  verification_status: 'UNVERIFIED' | 'VERIFIED';
  updated_at: string;
}

export interface FactCorrectionPayload {
  value: number;
  change_reason: string;
}

export interface FactCorrectionResult {
  fact: FinancialFact;
  affected_metrics: string[];
}
