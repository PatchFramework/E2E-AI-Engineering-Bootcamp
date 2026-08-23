import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MarkdownRenderer } from '../copilot/MarkdownRenderer';
import { CopilotCitation } from '../../../models/copilot';

// Mock Recharts components
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div />,
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div />,
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => <div />,
  Cell: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
  CartesianGrid: () => <div />,
}));

// Mock Mermaid
vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({ svg: '<svg data-testid="mermaid-svg"><text>Flowchart</text></svg>' }),
  },
}));

describe('MarkdownRenderer Component', () => {
  it('renders standard text formatting (bold, italic, strikethrough, headings, inline code)', () => {
    const markdown = `
# Executive Summary
## Risk Assessment
### Leverage Detail

This is **bold text**, this is *italic text*, and this is ~strikethrough~.
Here is an inline code snippet: \`total_debt / ebitda\`.
`;

    const { container } = render(<MarkdownRenderer content={markdown} />);

    expect(screen.getByRole('heading', { level: 1, name: 'Executive Summary' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Risk Assessment' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'Leverage Detail' })).toBeInTheDocument();

    expect(container.querySelector('strong')).toHaveTextContent('bold text');
    expect(container.querySelector('em')).toHaveTextContent('italic text');
    expect(container.querySelector('code')).toHaveTextContent('total_debt / ebitda');
  });

  it('renders bullet points, ordered lists, and task lists properly', () => {
    const markdown = `
Key Observations:
- Senior Debt: €650M
- Revolving Facility: €250M
- Subordinated Notes: €100M

Step-by-step procedure:
1. Extract EBITDA
2. Compute Gross Debt
3. Subtract Cash Equivalents

Checklist:
- [x] Verified by auditor
- [ ] Management sign-off pending
`;

    const { container } = render(<MarkdownRenderer content={markdown} />);

    expect(screen.getByText('Key Observations:')).toBeInTheDocument();
    expect(screen.getByText('Senior Debt: €650M')).toBeInTheDocument();
    expect(screen.getByText('Extract EBITDA')).toBeInTheDocument();

    const uls = container.querySelectorAll('ul');
    expect(uls.length).toBeGreaterThanOrEqual(1);

    const ols = container.querySelectorAll('ol');
    expect(ols.length).toBeGreaterThanOrEqual(1);

    const checkboxes = container.querySelectorAll('input[type="checkbox"]');
    expect(checkboxes.length).toBe(2);
    expect(checkboxes[0]).toBeChecked();
    expect(checkboxes[1]).not.toBeChecked();
  });

  it('renders raw HTML tags safely and correctly via rehype-raw', () => {
    const markdown = `
Analysis indicates <span class="highlight-risk" style="color: red;">Significant Increase</span> in leverage.<br />
<b>Status:</b> <i>Under Review</i>
`;

    render(<MarkdownRenderer content={markdown} />);

    expect(screen.getByText('Significant Increase')).toBeInTheDocument();
    expect(screen.getByText('Status:')).toBeInTheDocument();
    expect(screen.getByText('Under Review')).toBeInTheDocument();
  });

  it('renders markdown tables with headers and aligned cells', () => {
    const markdown = `
| Fiscal Year | Total Debt (€M) | EBITDA (€M) | Net Leverage |
| :--- | :--- | :--- | :--- |
| 2023 | 850 | 160 | 3.80x |
| 2024 | 980 | 170 | 4.15x |
| 2025 | 1200 | 178 | 4.72x |
`;

    render(<MarkdownRenderer content={markdown} />);

    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Fiscal Year')).toBeInTheDocument();
    expect(screen.getByText('Total Debt (€M)')).toBeInTheDocument();
    expect(screen.getByText('2025')).toBeInTheDocument();
    expect(screen.getByText('4.72x')).toBeInTheDocument();
  });

  it('renders embedded Mermaid diagrams when code block language is mermaid', async () => {
    const markdown = `
Below is the credit approval flow:

\`\`\`mermaid
graph TD
    A[Filing Ingested] --> B(Extract Financial Facts)
    B --> C{Deterministic Audit}
    C -->|Pass| D[Generate Assessment]
    C -->|Fail| E[Flag Discrepancies]
\`\`\`
`;

    render(<MarkdownRenderer content={markdown} />);

    expect(await screen.findByText('Mermaid Diagram')).toBeInTheDocument();
    expect(await screen.findByTestId('mermaid-svg')).toBeInTheDocument();
  });

  it('renders embedded Chart / Visual widgets when code block contains a widget definition', () => {
    const markdown = `
Here is the leverage progression:

\`\`\`chart
{
  "widgetType": "chart",
  "chartType": "line",
  "title": "Embedded 5-Year Leverage Trend",
  "series": [
    { "key": "leverage", "label": "Net Debt / EBITDA" }
  ],
  "data": [
    { "year": "2024", "leverage": 4.15 },
    { "year": "2025", "leverage": 4.72 }
  ]
}
\`\`\`
`;

    render(<MarkdownRenderer content={markdown} />);

    expect(screen.getByText('Embedded 5-Year Leverage Trend')).toBeInTheDocument();
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  it('renders blockquotes and standard code blocks with copy action', () => {
    const markdown = `
> Important: Leverage covenants restrict debt exceeding 5.00x EBITDA.

\`\`\`python
def calculate_leverage(debt, cash, ebitda):
    return (debt - cash) / ebitda
\`\`\`
`;

    const { container } = render(<MarkdownRenderer content={markdown} />);

    expect(container.querySelector('blockquote')).toHaveTextContent(
      'Important: Leverage covenants restrict debt exceeding 5.00x EBITDA.'
    );
    expect(screen.getByText('python')).toBeInTheDocument();
    expect(screen.getByText(/def calculate_leverage/)).toBeInTheDocument();
    expect(screen.getByTitle('Copy Code')).toBeInTheDocument();
  });

  it('renders inline bracketed citations matching citation list as clickable elements and fires onOpenCitation', () => {
    const handleOpenCitation = vi.fn();
    const sampleCitations: CopilotCitation[] = [
      {
        documentId: 1,
        filename: 'FY2025_Annual_Report.pdf',
        pageNumber: 42,
        displayedPage: 'p. 42',
        section: 'Financial Highlights',
        snippet: 'Operating EBITDA was €178M.',
        boundingBox: [10, 20, 100, 50],
      },
      {
        documentId: 1,
        filename: 'FY2025_Annual_Report.pdf',
        pageNumber: 87,
        displayedPage: 'p. 87',
        section: 'Debt Schedule',
      },
    ];

    const markdown = `
According to [FY2025_Annual_Report.pdf · p. 42], EBITDA was €178M.
Also refer to [FY2025_Annual_Report.pdf · p. 87] for debt breakdown.
`;

    render(
      <MarkdownRenderer
        content={markdown}
        citations={sampleCitations}
        onOpenCitation={handleOpenCitation}
      />
    );

    const citationButtons = screen.getAllByRole('button');
    const firstCitBtn = citationButtons.find(b => b.textContent?.includes('FY2025_Annual_Report.pdf · p. 42'));
    expect(firstCitBtn).toBeDefined();

    fireEvent.click(firstCitBtn!);
    expect(handleOpenCitation).toHaveBeenCalledTimes(1);
    expect(handleOpenCitation).toHaveBeenCalledWith(sampleCitations[0]);
  });

  it('renders explicit markdown citation links (citation:N) as clickable buttons', () => {
    const handleOpenCitation = vi.fn();
    const sampleCitations: CopilotCitation[] = [
      {
        documentId: 2,
        filename: 'FY2024_10K.pdf',
        pageNumber: 15,
        displayedPage: 'p. 15',
      },
    ];

    const markdown = `As stated in [Annual Filing 2024](citation:0), revenues grew 12%.`;

    render(
      <MarkdownRenderer
        content={markdown}
        citations={sampleCitations}
        onOpenCitation={handleOpenCitation}
      />
    );

    const btn = screen.getByRole('button', { name: /Annual Filing 2024/i });
    expect(btn).toBeInTheDocument();

    fireEvent.click(btn);
    expect(handleOpenCitation).toHaveBeenCalledWith(sampleCitations[0]);
  });

  it('does NOT convert non-citation bracketed content to citation buttons and preserves plain text/links', () => {
    const handleOpenCitation = vi.fn();
    const sampleCitations: CopilotCitation[] = [
      {
        documentId: 1,
        filename: 'FY2025_Annual_Report.pdf',
        pageNumber: 42,
        displayedPage: 'p. 42',
      },
    ];

    const markdown = `
- [Orchestrator Plan]: Execute workflow
- [Note]: Check debt covenants [x]
- [1] First observation
- Formula: [a + b] / c
- Regular link: [External Website](https://example.com)
`;

    const { container } = render(
      <MarkdownRenderer
        content={markdown}
        citations={sampleCitations}
        onOpenCitation={handleOpenCitation}
      />
    );

    // Non-citation brackets should not create citation buttons
    const buttons = screen.queryAllByRole('button');
    expect(buttons.length).toBe(0);

    // Text should be preserved
    expect(screen.getByText(/\[Orchestrator Plan\]: Execute workflow/i)).toBeInTheDocument();
    expect(screen.getByText(/\[Note\]: Check debt covenants/i)).toBeInTheDocument();
    expect(screen.getByText(/Formula: \[a \+ b\] \/ c/i)).toBeInTheDocument();

    // Regular markdown link should render as anchor tag
    const link = screen.getByRole('link', { name: /External Website/i });
    expect(link).toHaveAttribute('href', 'https://example.com');
  });

  it('renders citation button and opens PDF preview even if citations array is empty', () => {
    const handleOpenCitation = vi.fn();
    const markdown = `Refer to [FY2025_Annual_Report.pdf · p. 42] for details.`;

    render(
      <MarkdownRenderer
        content={markdown}
        onOpenCitation={handleOpenCitation}
      />
    );

    const btn = screen.getByRole('button', { name: /FY2025_Annual_Report\.pdf · p\. 42/i });
    expect(btn).toBeInTheDocument();

    fireEvent.click(btn);
    expect(handleOpenCitation).toHaveBeenCalledWith(
      expect.objectContaining({
        filename: 'FY2025_Annual_Report.pdf',
        pageNumber: 42,
        displayedPage: 'p. 42',
      })
    );
  });
});
