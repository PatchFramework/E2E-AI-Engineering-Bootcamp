import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CopilotPanel } from '../CopilotPanel';
import { CopilotContextSnapshot, CopilotMessage, ChatSessionSummary } from '../../../models/copilot';

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

describe('CopilotPanel Component', () => {
  const contextSnapshot: CopilotContextSnapshot = {
    currentView: 'dashboard',
    companyId: 1,
    companyName: 'Acme Corporation',
    activeMetric: {
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
      history: [],
    },
    activeFacts: [
      {
        id: 10,
        company_id: 1,
        concept: 'EBITDA',
        value: 178000000,
        unit: 'EUR',
        fiscal_year: 2025,
        fiscal_period: 'FY',
        version: 1,
        origin: 'AI_GENERATED',
        verification_status: 'UNVERIFIED',
        updated_at: '2026-08-21T10:00:00Z',
      },
    ],
  };

  const sampleMessages: CopilotMessage[] = [
    {
      id: 'msg-1',
      role: 'user',
      content: 'Explain why leverage increased in FY2025',
      createdAt: '2026-08-21T10:00:00Z',
    },
    {
      id: 'msg-2',
      role: 'assistant',
      runId: 'run-trace-123',
      content: 'Total debt increased to €1.2B according to [Annual_Report_2025.pdf · p. 42] while EBITDA remained steady at €178M.',
      citations: [
        {
          documentId: 1,
          filename: 'Annual_Report_2025.pdf',
          pageNumber: 42,
          displayedPage: 'p. 42',
          section: 'Financial Highlights',
          snippet: 'Operating EBITDA was reported at €178M.',
          boundingBox: [10, 20, 100, 50],
        },
      ],
      widgets: [
        {
          widgetType: 'chart',
          chartType: 'line',
          title: '5-Year Leverage vs EBITDA Margin',
          series: [
            { key: 'leverage', label: 'Net Debt / EBITDA' },
            { key: 'margin', label: 'EBITDA Margin' },
          ],
          data: [
            { year: '2024', leverage: 3.1, margin: 18.0 },
            { year: '2025', leverage: 4.72, margin: 22.4 },
          ],
        },
      ],
      createdAt: '2026-08-21T10:00:05Z',
    },
  ];

  const sessions: ChatSessionSummary[] = [
    {
      id: 'session-1',
      title: 'Leverage Analysis',
      companyId: 1,
      createdAt: '2026-08-21T09:00:00Z',
      updatedAt: '2026-08-21T10:00:00Z',
    },
  ];

  it('renders Copilot panel with active context pill, turn counter, and messages', () => {
    render(
      <CopilotPanel
        isOpen={true}
        onToggleOpen={vi.fn()}
        width={420}
        onWidthChange={vi.fn()}
        contextSnapshot={contextSnapshot}
        messages={sampleMessages}
        isStreaming={false}
        currentReasoningStatus={null}
        turnCount={1}
        maxTurns={10}
        onSendMessage={vi.fn()}
        onAbortStream={vi.fn()}
        onNewSession={vi.fn()}
        sessions={sessions}
        activeSessionId="session-1"
        onSwitchSession={vi.fn()}
        onOpenCitation={vi.fn()}
      />
    );

    expect(screen.getAllByText('Underwriting Copilot').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Turn 1/10')).toBeInTheDocument();
    expect(screen.getByText('Acme Corporation')).toBeInTheDocument();
    expect(screen.getByText(/Metric: Net Debt \/ EBITDA/)).toBeInTheDocument();
    expect(screen.getByText('Explain why leverage increased in FY2025')).toBeInTheDocument();
    expect(screen.getByText(/Total debt increased to €1.2B/)).toBeInTheDocument();
  });

  it('renders dynamic Recharts widget and handles citation click (both inline and tray)', () => {
    const handleOpenCitation = vi.fn();

    render(
      <CopilotPanel
        isOpen={true}
        onToggleOpen={vi.fn()}
        width={420}
        onWidthChange={vi.fn()}
        contextSnapshot={contextSnapshot}
        messages={sampleMessages}
        isStreaming={false}
        currentReasoningStatus={null}
        onSendMessage={vi.fn()}
        onAbortStream={vi.fn()}
        onNewSession={vi.fn()}
        sessions={sessions}
        activeSessionId="session-1"
        onSwitchSession={vi.fn()}
        onOpenCitation={handleOpenCitation}
      />
    );

    // Verify chart widget is rendered
    expect(screen.getByText('5-Year Leverage vs EBITDA Margin')).toBeInTheDocument();
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();

    // Verify citation is rendered and clickable in bottom tray
    const citationTrayItems = screen.getAllByText(/Annual_Report_2025\.pdf/i);
    expect(citationTrayItems.length).toBeGreaterThanOrEqual(1);

    // Click the inline citation button inside the prose text
    const inlineCitationBtn = screen.getByRole('button', { name: /Annual_Report_2025\.pdf · p\. 42/i });
    expect(inlineCitationBtn).toBeInTheDocument();

    fireEvent.click(inlineCitationBtn);
    expect(handleOpenCitation).toHaveBeenCalledTimes(1);
    expect(handleOpenCitation).toHaveBeenCalledWith(
      expect.objectContaining({
        documentId: 1,
        pageNumber: 42,
        displayedPage: 'p. 42',
      })
    );
  });

  it('handles thumbs up rating and comment submission', () => {
    const handleSubmitFeedback = vi.fn();

    render(
      <CopilotPanel
        isOpen={true}
        onToggleOpen={vi.fn()}
        width={420}
        onWidthChange={vi.fn()}
        contextSnapshot={contextSnapshot}
        messages={sampleMessages}
        isStreaming={false}
        currentReasoningStatus={null}
        onSendMessage={vi.fn()}
        onAbortStream={vi.fn()}
        onSubmitFeedback={handleSubmitFeedback}
        onNewSession={vi.fn()}
        sessions={sessions}
        activeSessionId="session-1"
        onSwitchSession={vi.fn()}
      />
    );

    const thumbsUpBtn = screen.getByTitle('Thumbs Up (Accurate & Helpful)');
    expect(thumbsUpBtn).toBeInTheDocument();

    fireEvent.click(thumbsUpBtn);
    expect(handleSubmitFeedback).toHaveBeenCalledWith('msg-2', 'run-trace-123', 1, undefined);

    // Comment box opens
    const commentInput = screen.getByPlaceholderText(/Optional feedback/i);
    expect(commentInput).toBeInTheDocument();

    fireEvent.change(commentInput, { target: { value: 'High accuracy on debt breakdown' } });
    const submitFeedbackBtn = screen.getByRole('button', { name: /Submit Feedback/i });
    fireEvent.click(submitFeedbackBtn);

    expect(handleSubmitFeedback).toHaveBeenCalledWith('msg-2', 'run-trace-123', 1, 'High accuracy on debt breakdown');
  });

  it('enforces 10-turn cap warning and disables prompt input', () => {
    const handleNewSession = vi.fn();

    render(
      <CopilotPanel
        isOpen={true}
        onToggleOpen={vi.fn()}
        width={420}
        onWidthChange={vi.fn()}
        contextSnapshot={contextSnapshot}
        messages={sampleMessages}
        isStreaming={false}
        currentReasoningStatus={null}
        turnCount={10}
        maxTurns={10}
        isTurnLimitReached={true}
        onSendMessage={vi.fn()}
        onAbortStream={vi.fn()}
        onNewSession={handleNewSession}
        sessions={sessions}
        activeSessionId="session-1"
        onSwitchSession={vi.fn()}
      />
    );

    // Turn limit banner
    expect(screen.getByText(/Turn Limit Reached \(10\/10\)/i)).toBeInTheDocument();
    expect(screen.getByText(/You have reached the maximum of 10 conversational turns/i)).toBeInTheDocument();

    // Input disabled
    const input = screen.getByPlaceholderText(/Maximum turns reached \(10\/10\)/i) as HTMLInputElement;
    expect(input).toBeDisabled();

    // Start New Chat button inside warning banner
    const startNewChatBtn = screen.getByRole('button', { name: /Start New Chat/i });
    fireEvent.click(startNewChatBtn);
    expect(handleNewSession).toHaveBeenCalledTimes(1);
  });

  it('displays live reasoning status during streaming and handles stop', () => {
    const handleAbort = vi.fn();

    render(
      <CopilotPanel
        isOpen={true}
        onToggleOpen={vi.fn()}
        width={420}
        onWidthChange={vi.fn()}
        contextSnapshot={contextSnapshot}
        messages={sampleMessages}
        isStreaming={true}
        currentReasoningStatus="Searching FY2025 Debt Schedule..."
        onSendMessage={vi.fn()}
        onAbortStream={handleAbort}
        onNewSession={vi.fn()}
        sessions={sessions}
        activeSessionId="session-1"
        onSwitchSession={vi.fn()}
        onOpenCitation={vi.fn()}
      />
    );

    expect(screen.getByText('Searching FY2025 Debt Schedule...')).toBeInTheDocument();

    const stopButton = screen.getByRole('button', { name: /Stop/i });
    expect(stopButton).toBeInTheDocument();

    fireEvent.click(stopButton);
    expect(handleAbort).toHaveBeenCalledTimes(1);
  });

  it('supports starting new session and switching conversation drawer', () => {
    const handleNewSession = vi.fn();
    const handleSwitchSession = vi.fn();

    render(
      <CopilotPanel
        isOpen={true}
        onToggleOpen={vi.fn()}
        width={420}
        onWidthChange={vi.fn()}
        contextSnapshot={contextSnapshot}
        messages={sampleMessages}
        isStreaming={false}
        currentReasoningStatus={null}
        onSendMessage={vi.fn()}
        onAbortStream={vi.fn()}
        onNewSession={handleNewSession}
        sessions={sessions}
        activeSessionId="session-1"
        onSwitchSession={handleSwitchSession}
        onOpenCitation={vi.fn()}
      />
    );

    const newChatBtn = screen.getByTitle('Start New Chat Session');
    fireEvent.click(newChatBtn);
    expect(handleNewSession).toHaveBeenCalledTimes(1);

    const historyBtn = screen.getByTitle('Chat History');
    fireEvent.click(historyBtn);
    expect(screen.getByText('Conversations')).toBeInTheDocument();
  });
});
