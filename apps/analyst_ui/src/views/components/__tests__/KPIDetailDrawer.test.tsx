import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { KPIDetailDrawer } from '../KPIDetailDrawer';

import { MetricItem, MetricLineage } from '../../../models/metric';

// Mock recharts ResponsiveContainer and AreaChart to avoid canvas rendering in tests
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  AreaChart: ({ children }: any) => <div data-testid="area-chart">{children}</div>,
  Area: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  CartesianGrid: () => <div />,
}));

describe('KPIDetailDrawer Integration', () => {
  const sampleMetric: MetricItem = {
    id: 1,
    metric_name: 'net_debt_to_ebitda',
    display_name: 'Net Debt / EBITDA',
    category: 'Leverage',
    formula_expression: '(total_debt - cash) / ebitda',
    unit: 'x',
    current_value: 4.72,
    prior_value: 3.1,
    yoy_change: 1.62,
    yoy_change_pct: 52.2,
    trend: 'up',
    verification_status: 'UNVERIFIED',
    status: 'AVAILABLE',
    fiscal_year: 2025,
    fiscal_period: 'FY',
    history: [
      { fiscal_year: 2024, fiscal_period: 'FY', value: 3.1, status: 'AVAILABLE' },
      { fiscal_year: 2025, fiscal_period: 'FY', value: 4.72, status: 'AVAILABLE' },
    ],
  };

  const sampleLineage: MetricLineage = {
    derived_metric_id: 1,
    metric_name: 'net_debt_to_ebitda',
    display_name: 'Net Debt / EBITDA',
    category: 'Leverage',
    formula_expression: '(total_debt - cash) / ebitda',
    value: 4.72,
    unit: 'x',
    status: 'AVAILABLE',
    fiscal_year: 2025,
    fiscal_period: 'FY',
    input_facts: [
      {
        fact_id: 10,
        concept: 'Total Debt',
        role: 'INPUT',
        value: 1200000000,
        unit: 'EUR',
        origin: 'AI_GENERATED',
        verification_status: 'UNVERIFIED',
        document: {
          document_id: 101,
          filename: 'Acme_2025_Annual_Report.pdf',
          fiscal_year: 2025,
          fiscal_period: 'FY',
        },
        source_location: {
          location_id: 1,
          page_number: 42,
          displayed_page_number: '42',
          section: 'Note 8. Debt',
          section_path: 'Financial Statements > Note 8. Debt',
          text_snippet: 'Total debt amounted to EUR 1,200M.',
          bounding_box: [50, 100, 500, 200],
        },
      },
      {
        fact_id: 11,
        concept: 'EBITDA',
        role: 'INPUT',
        value: 178000000,
        unit: 'EUR',
        origin: 'AI_GENERATED',
        verification_status: 'UNVERIFIED',
        document: {
          document_id: 102,
          filename: 'Acme_2025_Earnings_Release.pdf',
          fiscal_year: 2025,
          fiscal_period: 'FY',
        },
        source_location: {
          location_id: 2,
          page_number: 15,
          displayed_page_number: '15',
          section: 'Key Performance Indicators',
          section_path: 'Overview > Key Performance Indicators',
          text_snippet: 'Operating EBITDA was EUR 178M.',
          bounding_box: [40, 80, 480, 160],
        },
      },
    ],
    cited_chunks: [
      {
        chunk_id: 99,
        document_id: 101,
        page_number: 42,
        displayed_page_number: '42',
        section_path: 'Financial Statements > Note 8. Debt',
        text_content: 'Detailed breakdown of senior notes and bank borrowings.',
      },
    ],
  };

  const defaultProps = {
    metric: sampleMetric,
    lineage: sampleLineage,
    loadingLineage: false,
    onClose: vi.fn(),
    onOpenCorrection: vi.fn(),
    onVerifyFact: vi.fn().mockResolvedValue({}),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('renders split workbench layout with live preview on left and KPI details on right', () => {
    render(<KPIDetailDrawer {...defaultProps} />);

    // Live preview section on left
    expect(screen.getByText(/s3 source preview/i)).toBeInTheDocument();
    // Default selected fact breadcrumbs
    expect(screen.getAllByText(/Note 8\. Debt/i).length).toBeGreaterThan(0);

    // Right details panel
    expect(screen.getByText('Net Debt / EBITDA')).toBeInTheDocument();
    expect(screen.getAllByText('4.72x').length).toBeGreaterThan(0);
    expect(screen.getByText(/deterministic formula/i)).toBeInTheDocument();
    expect(screen.getAllByText('Total Debt').length).toBeGreaterThan(0);
    expect(screen.getAllByText('EBITDA').length).toBeGreaterThan(0);


  });

  it('dynamically switches document, page, and bounding box when clicking a different input fact', () => {
    render(<KPIDetailDrawer {...defaultProps} />);

    // Initially "Total Debt" on page 42 is active
    expect(screen.getAllByText(/Note 8\. Debt/i).length).toBeGreaterThan(0);

    // Click on "EBITDA" fact card (which is in a different document on page 15)
    const ebitdaFactCard = screen.getByText('EBITDA').closest('div[role="button"]') || screen.getByText('EBITDA');
    fireEvent.click(ebitdaFactCard);

    // Should now show breadcrumb and snippet for EBITDA
    expect(screen.getAllByText(/Key Performance Indicators/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Operating EBITDA was EUR 178M/i).length).toBeGreaterThan(0);
  });

  it('calls onClose when close button is clicked', () => {
    render(<KPIDetailDrawer {...defaultProps} />);
    const closeButtons = screen.getAllByRole('button', { name: /close/i });
    expect(closeButtons.length).toBeGreaterThan(0);
    fireEvent.click(closeButtons[0]);
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('returns null when metric is null', () => {
    const { container } = render(<KPIDetailDrawer {...defaultProps} metric={null} />);
    expect(container.firstChild).toBeNull();
  });
});
