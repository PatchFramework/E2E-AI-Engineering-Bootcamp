export type KPICategory =
  | 'Overview'
  | 'Profitability'
  | 'Leverage'
  | 'Coverage'
  | 'Liquidity'
  | 'Cash Flow'
  | 'Balance Sheet';

export const KPI_CATEGORIES: KPICategory[] = [
  'Overview',
  'Profitability',
  'Leverage',
  'Coverage',
  'Liquidity',
  'Cash Flow',
  'Balance Sheet',
];

export interface MetricHistoryPoint {
  fiscal_year: number;
  fiscal_period: string;
  value: number | null;
  status: string;
}

export interface MetricItem {
  id?: number | null;
  metric_name: string;
  display_name: string;
  category: KPICategory;
  formula_expression?: string | null;
  unit: string;
  description?: string | null;
  current_value?: number | null;
  prior_value?: number | null;
  yoy_change?: number | null;
  yoy_change_pct?: number | null;
  trend: 'up' | 'down' | 'neutral';
  verification_status: 'VERIFIED' | 'CORRECTED' | 'UNVERIFIED' | 'UNAVAILABLE';
  status: 'AVAILABLE' | 'UNAVAILABLE' | 'ERROR';
  status_reason?: string | null;
  fiscal_year: number;
  fiscal_period: string;
  calculated_at?: string | null;
  history: MetricHistoryPoint[];
}

export interface SourceLocationInfo {
  location_id?: number | null;
  page_number?: number | null;
  displayed_page_number?: string | null;
  section?: string | null;
  section_path?: string | null;
  text_snippet?: string | null;
  bounding_box?: any;
}

export interface DocumentInfo {
  document_id?: number | null;
  filename?: string | null;
  s3_path?: string | null;
  fiscal_year?: number | null;
  fiscal_period?: string | null;
}

export interface MetricInputFactLineage {
  fact_id?: number | null;
  fact_version_id?: number | null;
  concept: string;
  role: string;
  value?: number | null;
  unit: string;
  origin?: string | null;
  verification_status?: string | null;
  source_location?: SourceLocationInfo | null;
  document?: DocumentInfo | null;
}

export interface MetricCitedChunk {
  chunk_id: number;
  document_id: number;
  page_number: number;
  displayed_page_number?: string | null;
  section_path?: string | null;
  text_content: string;
  chunk_metadata?: Record<string, any> | null;
}

export interface MetricLineage {
  derived_metric_id: number;
  metric_name: string;
  display_name: string;
  category: string;
  formula_expression?: string | null;
  value?: number | null;
  unit: string;
  status: string;
  status_reason?: string | null;
  fiscal_year: number;
  fiscal_period: string;
  calculated_at?: string | null;
  input_facts: MetricInputFactLineage[];
  cited_chunks: MetricCitedChunk[];
}

// ─── Value Formatting Utilities ──────────────────────────────────────────────

export function formatMetricValue(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }

  const normalizedUnit = (unit || '').trim().toLowerCase();

  if (normalizedUnit === 'eur' || normalizedUnit === 'usd' || normalizedUnit === 'gbp') {
    const symbol = normalizedUnit === 'usd' ? '$' : normalizedUnit === 'gbp' ? '£' : '€';
    const absVal = Math.abs(value);
    const sign = value < 0 ? '-' : '';

    if (absVal >= 1_000_000_000) {
      const billions = absVal / 1_000_000_000;
      const numStr = billions >= 10 ? billions.toFixed(1) : billions.toFixed(2);
      const cleanNum = parseFloat(numStr).toString();
      return `${sign}${symbol}${cleanNum}B`;
    } else if (absVal >= 1_000_000) {
      const millions = absVal / 1_000_000;
      const numStr = millions >= 10 ? millions.toFixed(1) : millions.toFixed(2);
      const cleanNum = parseFloat(numStr).toString();
      return `${sign}${symbol}${cleanNum}M`;
    } else if (absVal >= 1_000) {
      const thousands = absVal / 1_000;
      const numStr = thousands >= 10 ? thousands.toFixed(1) : thousands.toFixed(2);
      const cleanNum = parseFloat(numStr).toString();
      return `${sign}${symbol}${cleanNum}k`;
    } else {
      return `${sign}${symbol}${absVal.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
    }
  }

  if (normalizedUnit === '%') {
    const pctVal = Math.abs(value) <= 1.0 && value !== 0 ? value * 100 : value;
    return `${pctVal.toFixed(1)}%`;
  }

  if (normalizedUnit === 'x' || normalizedUnit === 'ratio') {
    return `${value.toFixed(2)}x`;
  }

  return `${value.toFixed(2)}`;
}

export function parseAnalystInput(inputStr: string): number | null {

  if (!inputStr || !inputStr.trim()) return null;
  let s = inputStr.trim().toLowerCase();

  // Strip currency symbols and whitespace
  s = s.replace(/[$€£]/g, '').replace(/\s+/g, '');

  let multiplier = 1;
  if (s.endsWith('b') || s.endsWith('bn') || s.endsWith('billion')) {
    multiplier = 1_000_000_000;
    s = s.replace(/billion|bn|b$/, '');
  } else if (s.endsWith('m') || s.endsWith('mn') || s.endsWith('million')) {
    multiplier = 1_000_000;
    s = s.replace(/million|mn|m$/, '');
  } else if (s.endsWith('k') || s.endsWith('thousand')) {
    multiplier = 1_000;
    s = s.replace(/thousand|k$/, '');
  } else if (s.endsWith('%')) {
    s = s.replace('%', '');
  } else if (s.endsWith('x')) {
    s = s.replace('x', '');
  }

  // Handle European comma decimal vs American thousands separators
  if (s.includes(',') && !s.includes('.')) {
    s = s.replace(',', '.');
  } else {
    s = s.replace(/,/g, '');
  }

  const parsed = parseFloat(s);
  if (isNaN(parsed)) return null;

  return parsed * multiplier;
}


export function formatYoYChange(
  change: number | null | undefined,
  changePct: number | null | undefined,
  unit: string
): { text: string; direction: 'up' | 'down' | 'neutral' } {
  if (change === null || change === undefined || isNaN(change)) {
    return { text: '— YoY', direction: 'neutral' };
  }

  const isPositive = change > 0.0001;
  const isNegative = change < -0.0001;
  const arrow = isPositive ? '↑' : isNegative ? '↓' : '';
  const sign = isPositive ? '+' : '';

  const normalizedUnit = unit.trim().toLowerCase();

  if (normalizedUnit === 'x' || normalizedUnit === 'ratio') {
    return {
      text: `${arrow} ${sign}${change.toFixed(2)}x YoY`,
      direction: isPositive ? 'up' : isNegative ? 'down' : 'neutral',
    };
  }

  if (normalizedUnit === '%') {
    const val = Math.abs(change) <= 1.0 && change !== 0 ? change * 100 : change;
    return {
      text: `${arrow} ${sign}${val.toFixed(1)}% YoY`,
      direction: isPositive ? 'up' : isNegative ? 'down' : 'neutral',
    };
  }

  if (changePct !== null && changePct !== undefined && !isNaN(changePct)) {
    return {
      text: `${arrow} ${sign}${changePct.toFixed(0)}% YoY`,
      direction: isPositive ? 'up' : isNegative ? 'down' : 'neutral',
    };
  }

  return {
    text: `${arrow} ${formatMetricValue(change, unit)} YoY`,
    direction: isPositive ? 'up' : isNegative ? 'down' : 'neutral',
  };
}

/**
 * Returns risk interpretation narrative based on metric trend & thresholds
 */
export function getMetricRiskInterpretation(metricName: string, value: number | null | undefined, trend: string): string {
  if (value === null || value === undefined) {
    return 'Metric data is currently unavailable from source filings.';
  }

  switch (metricName) {
    case 'net_debt_to_ebitda':
    case 'debt_to_ebitda':
      if (value > 4.5) return `Leverage is elevated at ${value.toFixed(2)}x, indicating increased debt payback duration.`;
      if (value > 3.0) return `Leverage is moderate at ${value.toFixed(2)}x. Debt servicing capacity is stable.`;
      return `Leverage is conservative at ${value.toFixed(2)}x with strong debt protection.`;

    case 'ebitda_to_interest':
    case 'interest_coverage':
      if (value < 2.0) return `Interest coverage is weak at ${value.toFixed(2)}x, indicating sensitivity to rate increases.`;
      if (value < 4.0) return `Interest coverage is adequate at ${value.toFixed(2)}x.`;
      return `Interest coverage is robust at ${value.toFixed(2)}x with substantial cash flow headroom.`;

    case 'current_ratio':
    case 'quick_ratio':
      if (value < 1.0) return `Liquidity buffer is strained with current ratio below 1.0x.`;
      return `Adequate short-term liquidity buffer to cover immediate obligations.`;

    case 'free_cash_flow':
      if (value < 0) return `Negative free cash flow in the period due to operating investments or capex.`;
      return `Positive free cash flow generated after capital expenditures.`;

    case 'revenue_growth':
      if (value < 0) return `Top-line revenue contracted compared to the prior period.`;
      return `Positive revenue trajectory year-over-year.`;

    default:
      return `Metric trajectory is ${trend === 'up' ? 'improving' : trend === 'down' ? 'declining' : 'steady'} relative to historical baseline.`;
  }
}
