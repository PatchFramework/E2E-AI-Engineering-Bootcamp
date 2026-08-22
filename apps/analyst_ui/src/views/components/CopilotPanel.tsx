import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  TrendingUp,
  ArrowRight,
  Send,
  Sparkles,
  Bot,
  User,
  BookOpen,
  Square,
  Plus,
  History,
  ChevronRight,
  ChevronDown,
  Loader2,
  X,
  Target,
  FileText,
  Building,
  Layers,
  CheckCircle2,
  Clock,
  Calculator,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  AlertTriangle,
  Check,
} from 'lucide-react';
import { CopilotMessage, CopilotContextSnapshot, ChatSessionSummary, CopilotCitation } from '../../models/copilot';
import { ChartWidgetRenderer } from './copilot/ChartWidgetRenderer';
import { MarkdownRenderer } from './copilot/MarkdownRenderer';

interface CopilotPanelProps {
  isOpen: boolean;
  onToggleOpen: () => void;
  width: number;
  onWidthChange: (w: number) => void;
  contextSnapshot: CopilotContextSnapshot;
  messages: CopilotMessage[];
  isStreaming: boolean;
  currentReasoningStatus: string | null;
  turnCount?: number;
  maxTurns?: number;
  isTurnLimitReached?: boolean;
  onSendMessage: (msg: string) => void;
  onAbortStream: () => void;
  onNewSession: () => void;
  sessions: ChatSessionSummary[];
  activeSessionId: string;
  onSwitchSession: (sessionId: string) => void;
  onOpenCitation?: (citation: CopilotCitation) => void;
  onSubmitFeedback?: (messageId: string, runId: string | undefined, score: 1 | -1, comment?: string) => void;
}

const formatFactValue = (val: number, unit?: string) => {
  if (Math.abs(val) >= 1_000_000_000) {
    return `€${(val / 1_000_000_000).toFixed(2)}B`;
  }
  if (Math.abs(val) >= 1_000_000) {
    return `€${(val / 1_000_000).toFixed(1)}M`;
  }
  if (Math.abs(val) >= 1_000) {
    return `€${(val / 1_000).toFixed(0)}k`;
  }
  return `${val} ${unit || ''}`;
};

export const CopilotPanel: React.FC<CopilotPanelProps> = ({
  isOpen,
  onToggleOpen,
  width,
  onWidthChange,
  contextSnapshot,
  messages,
  isStreaming,
  currentReasoningStatus,
  turnCount: turnCountProp,
  maxTurns = 10,
  isTurnLimitReached: isTurnLimitReachedProp,
  onSendMessage,
  onAbortStream,
  onNewSession,
  sessions,
  activeSessionId,
  onSwitchSession,
  onOpenCitation,
  onSubmitFeedback,
}) => {
  const [query, setQuery] = useState('');
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);
  const [isContextExpanded, setIsContextExpanded] = useState(false);
  const [activeFeedbackMsgId, setActiveFeedbackMsgId] = useState<string | null>(null);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [submittedFeedbackMsgIds, setSubmittedFeedbackMsgIds] = useState<Record<string, boolean>>({});

  const isDraggingRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Compute turns if not provided directly
  const computedTurnCount = useMemo(() => {
    return turnCountProp !== undefined
      ? turnCountProp
      : messages.filter(m => m.role === 'user').length;
  }, [turnCountProp, messages]);

  const isTurnLimitReached = useMemo(() => {
    return isTurnLimitReachedProp !== undefined
      ? isTurnLimitReachedProp
      : computedTurnCount >= maxTurns;
  }, [isTurnLimitReachedProp, computedTurnCount, maxTurns]);

  // Auto-scroll to bottom on new messages or reasoning updates
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, currentReasoningStatus]);

  // Handle Drag-to-Resize on left border
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isDraggingRef.current = true;

    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'ew-resize';

    const startX = e.clientX;
    const startWidth = width;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isDraggingRef.current) return;
      moveEvent.preventDefault();
      const delta = startX - moveEvent.clientX;
      const newWidth = Math.min(800, Math.max(360, startWidth + delta));
      onWidthChange(newWidth);
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const handleSend = (textToSend?: string) => {
    const q = textToSend || query;
    if (!q.trim() || isStreaming || isTurnLimitReached) return;
    onSendMessage(q);
    setQuery('');
  };

  // Handle rating click
  const handleRate = (msg: CopilotMessage, score: 1 | -1) => {
    if (onSubmitFeedback) {
      onSubmitFeedback(msg.id, msg.runId, score, msg.ratingComment);
    }
    setActiveFeedbackMsgId(msg.id);
    setFeedbackComment(msg.ratingComment || '');
  };

  const handleSaveComment = (msg: CopilotMessage) => {
    const currentScore = msg.userRating || 1;
    if (onSubmitFeedback) {
      onSubmitFeedback(msg.id, msg.runId, currentScore, feedbackComment);
    }
    setSubmittedFeedbackMsgIds(prev => ({ ...prev, [msg.id]: true }));
    setActiveFeedbackMsgId(null);
  };

  // Compute grounding items count
  const contextStats = useMemo(() => {
    let count = 0;
    if (contextSnapshot.companyName) count++;
    if (contextSnapshot.activeMetric) count++;
    if (contextSnapshot.activeFacts && contextSnapshot.activeFacts.length > 0) {
      count += contextSnapshot.activeFacts.length;
    }
    if (contextSnapshot.activeDocuments && contextSnapshot.activeDocuments.length > 0) {
      count += contextSnapshot.activeDocuments.length;
    }
    return count;
  }, [contextSnapshot]);

  const suggestedPrompts = [
    contextSnapshot.activeMetric
      ? `Explain why ${contextSnapshot.activeMetric.display_name} changed YoY`
      : 'Why did leverage increase in FY2025?',
    'Show 5-year leverage vs margin in a chart',
    'What are the most frequent credit risk topics in the report?',
    'Show breakdown of total debt items',
  ];

  if (!isOpen) {
    return (
      <button
        onClick={onToggleOpen}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-2.5 rounded-full bg-brand-600 hover:bg-brand-500 text-white shadow-xl shadow-brand-900/50 border border-brand-400/40 transition hover:scale-105"
        title="Open Underwriting Copilot"
      >
        <TrendingUp className="w-4 h-4" />
        <span className="text-xs font-bold tracking-wide">Copilot</span>
      </button>
    );
  }

  return (
    <aside
      style={{ width: `${width}px` }}
      className="relative flex flex-col h-full flex-shrink-0 min-h-0 bg-slate-900/95 border-l border-slate-800 backdrop-blur-xl shadow-2xl z-30 transition-all duration-75 select-none overflow-hidden"
    >
      {/* Horizontal Resize Drag Handle on Left Border */}
      <div
        onMouseDown={handleMouseDown}
        onDoubleClick={() => onWidthChange(420)}
        className="absolute -left-1.5 top-0 bottom-0 w-3 cursor-ew-resize hover:bg-brand-500/40 transition flex items-center justify-center group z-40"
        title="Drag to resize panel (Double-click to reset)"
      >
        <div className="h-8 w-1 rounded-full bg-slate-700 group-hover:bg-brand-400 transition" />
      </div>

      {/* Header */}
      <div className="p-3.5 border-b border-slate-800 flex items-center justify-between bg-slate-950/80">
        <div className="flex items-center gap-2 min-w-0">
          <div className="p-1.5 rounded-lg bg-brand-950 text-brand-400 border border-brand-800/60 shadow-sm flex-shrink-0">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold text-slate-100 truncate">
                Underwriting Copilot
              </h3>
              {/* Turn Indicator Badge */}
              <span
                className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold tracking-tight ${
                  isTurnLimitReached
                    ? 'bg-rose-950 text-rose-300 border border-rose-800'
                    : computedTurnCount >= 7
                    ? 'bg-amber-950 text-amber-300 border border-amber-800'
                    : 'bg-slate-900 text-slate-400 border border-slate-800'
                }`}
                title={`Conversational turns: ${computedTurnCount} / ${maxTurns}`}
              >
                Turn {computedTurnCount}/{maxTurns}
              </span>
            </div>
            <span className="text-[10px] text-slate-400 truncate block max-w-[170px]">
              {contextSnapshot.companyName || 'Corporate Filing'}
            </span>
          </div>
        </div>

        {/* Top Action Buttons */}
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            type="button"
            onClick={onNewSession}
            aria-label="Start New Session"
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-brand-300 transition"
            title="Start New Chat Session"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setShowHistoryDrawer(!showHistoryDrawer)}
            className={`p-1.5 rounded-lg border transition ${
              showHistoryDrawer
                ? 'bg-brand-900/60 border-brand-700 text-brand-300'
                : 'bg-slate-900 hover:bg-slate-800 border-slate-800 text-slate-300'
            }`}
            title="Chat History"
          >
            <History className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={onToggleOpen}
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-white transition ml-1"
            title="Collapse Copilot"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Expandable Grounding Context Header */}
      <div className="border-b border-slate-850 bg-slate-950/60 transition-colors">
        {/* Compact Toggle Row */}
        <div
          onClick={() => setIsContextExpanded(!isContextExpanded)}
          className="px-3 py-1.5 flex items-center justify-between cursor-pointer hover:bg-slate-900/50 transition"
        >
          <div className="flex items-center gap-1.5 text-[10px] font-medium text-slate-300 truncate">
            <Target className="w-3 h-3 text-brand-400 flex-shrink-0" />
            <span className="text-slate-400">Context:</span>
            <span className="text-slate-200 font-semibold truncate">
              {contextSnapshot.activeMetric
                ? `Metric: ${contextSnapshot.activeMetric.display_name}`
                : contextSnapshot.companyName || 'Acme Corp'}
            </span>
            {contextStats > 1 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full bg-brand-950 text-brand-300 border border-brand-800/80 text-[9px] font-bold">
                +{contextStats - 1} more
              </span>
            )}
          </div>

          <div className="flex items-center gap-1 text-[9px] text-slate-400 font-medium">
            <span className="hidden sm:inline">{isContextExpanded ? 'Hide' : 'Details'}</span>
            <ChevronDown
              className={`w-3 h-3 text-slate-400 transition-transform duration-200 ${
                isContextExpanded ? 'rotate-180 text-brand-400' : ''
              }`}
            />
          </div>
        </div>

        {/* Expanded Grounding Information Drawer */}
        {isContextExpanded && (
          <div className="p-3 bg-slate-950/95 border-t border-slate-850/80 max-h-56 overflow-y-auto space-y-2.5 animate-fadeIn text-[11px]">
            {/* 1. Active Company */}
            {contextSnapshot.companyName && (
              <div>
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                  Active Company
                </span>
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-200">
                  <Building className="w-3 h-3 text-sky-400" />
                  <span className="font-semibold">{contextSnapshot.companyName}</span>
                </div>
              </div>
            )}

            {/* 2. Active KPI Focus */}
            {contextSnapshot.activeMetric && (
              <div>
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                  Focused Metric
                </span>
                <div className="p-2 rounded-lg bg-brand-950/50 border border-brand-800/60 text-slate-200 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-brand-300 flex items-center gap-1">
                      <Calculator className="w-3 h-3 text-brand-400" />
                      {contextSnapshot.activeMetric.display_name}
                    </span>
                    <span className="font-mono font-bold text-xs text-white">
                      {contextSnapshot.activeMetric.current_value !== null
                        ? `${contextSnapshot.activeMetric.current_value}${contextSnapshot.activeMetric.unit || ''}`
                        : 'N/A'}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono">
                    Formula: {contextSnapshot.activeMetric.formula_expression}
                  </div>
                </div>
              </div>
            )}

            {/* 3. Constituent Financial Facts */}
            {contextSnapshot.activeFacts && contextSnapshot.activeFacts.length > 0 && (
              <div>
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                  Input Facts ({contextSnapshot.activeFacts.length})
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {contextSnapshot.activeFacts.map((fact, fIdx) => (
                    <div
                      key={fact.id || fIdx}
                      title={fact.verification_status === 'VERIFIED' ? 'Verified Fact' : 'Unverified Fact'}
                      className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-900 border border-slate-800 text-[10px] text-slate-300"
                    >
                      <Layers className="w-2.5 h-2.5 text-indigo-400" />
                      <span className="font-medium">{fact.concept}:</span>
                      <span className="font-mono text-slate-100 font-semibold">
                        {formatFactValue(fact.value, fact.unit)}
                      </span>
                      {fact.verification_status === 'VERIFIED' ? (
                        <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" />
                      ) : (
                        <Clock className="w-2.5 h-2.5 text-amber-400" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 4. Active Document & Page References */}
            {contextSnapshot.activeDocuments && contextSnapshot.activeDocuments.length > 0 && (
              <div>
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                  Referenced Documents & Pages
                </span>
                <div className="space-y-1">
                  {contextSnapshot.activeDocuments.map((doc, dIdx) => (
                    <div
                      key={dIdx}
                      className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-900 border border-slate-800 text-[10px] text-slate-300"
                    >
                      <FileText className="w-3 h-3 text-brand-400" />
                      <span className="font-semibold text-slate-200">
                        {doc.filename || 'Filing'} · {doc.displayedPage}
                      </span>
                      {doc.snippet && (
                        <span className="text-slate-400 truncate italic max-w-[180px]">
                          "{doc.snippet}"
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* History Slide-Over Drawer */}
      {showHistoryDrawer && (
        <div className="p-3 bg-slate-950 border-b border-slate-800 max-h-48 overflow-y-auto space-y-1.5 animate-fadeIn">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase text-slate-400 mb-1 px-1">
            <span>Conversations</span>
            <button
              onClick={() => setShowHistoryDrawer(false)}
              className="text-slate-500 hover:text-slate-300"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
          {sessions.map(s => (
            <button
              key={s.id}
              onClick={() => {
                onSwitchSession(s.id);
                setShowHistoryDrawer(false);
              }}
              className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition truncate flex items-center justify-between ${
                s.id === activeSessionId
                  ? 'bg-brand-950 border border-brand-800/80 text-brand-200 font-semibold'
                  : 'hover:bg-slate-900 border border-transparent text-slate-300'
              }`}
            >
              <span className="truncate pr-2">{s.title}</span>
              <span className="text-[9px] text-slate-500">
                {new Date(s.updatedAt).toLocaleDateString([], { month: 'short', day: 'numeric' })}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Messages Scroll View */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4 select-text">
        {messages.map((m, idx) => (
          <div
            key={m.id || idx}
            className={`p-3.5 rounded-xl text-xs leading-relaxed ${
              m.role === 'assistant'
                ? 'bg-slate-950/80 border border-slate-800 text-slate-200 shadow-md'
                : 'bg-brand-950/40 border border-brand-900/50 text-brand-100 ml-4'
            }`}
          >
            {/* Role Header */}
            <div className="flex items-center justify-between mb-1.5 text-[10px] font-bold text-slate-400">
              <div className="flex items-center gap-1.5">
                {m.role === 'assistant' ? (
                  <>
                    <Bot className="w-3.5 h-3.5 text-brand-400" /> Underwriting Copilot
                  </>
                ) : (
                  <>
                    <User className="w-3.5 h-3.5 text-slate-400" /> Analyst
                  </>
                )}
              </div>
              <span className="text-[9px] text-slate-500 font-mono font-normal">
                {new Date(m.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>

            {/* Content Text (Rich Markdown with HTML, Lists, Code, Mermaid & Inline Visualizations) */}
            <MarkdownRenderer content={m.content} />

            {/* Dynamic Generative UI Chart Widgets */}
            {m.widgets && m.widgets.length > 0 && (
              <div className="mt-2 space-y-2">
                {m.widgets.map((w, wIdx) => (
                  <ChartWidgetRenderer key={wIdx} widget={w} />
                ))}
              </div>
            )}

            {/* Citations & Evidence Grounding */}
            {m.citations && m.citations.length > 0 && (
              <div className="mt-2.5 pt-2 border-t border-slate-850 text-[10px] text-brand-400 font-medium">
                <div className="flex items-center gap-1 text-slate-400 mb-1">
                  <BookOpen className="w-3 h-3 text-slate-400" /> Grounded Evidence Citations:
                </div>
                <div className="space-y-1">
                  {m.citations.map((c, i) => (
                    <div
                      key={i}
                      onClick={() => onOpenCitation && onOpenCitation(c)}
                      className="flex items-start gap-1 p-1.5 rounded-lg bg-slate-900/80 hover:bg-slate-850 border border-slate-800/80 text-brand-300 hover:text-brand-200 transition cursor-pointer group"
                      title="Click to view original PDF page and highlight"
                    >
                      <FileText className="w-3 h-3 text-brand-400 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 truncate">
                        <span className="font-semibold underline underline-offset-2">
                          {c.filename || 'Filing'} · {c.displayedPage || `p. ${c.pageNumber}`}
                        </span>
                        {c.section && (
                          <span className="text-slate-400 ml-1">({c.section})</span>
                        )}
                        {c.snippet && (
                          <p className="text-[9px] text-slate-400 truncate mt-0.5 italic">
                            "{c.snippet}"
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Assistant Rating & Feedback Bar */}
            {m.role === 'assistant' && m.id !== 'welcome-msg' && !isStreaming && (
              <div className="mt-3 pt-2 border-t border-slate-850/80 flex flex-col gap-1.5 text-[10px]">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-[9px] text-slate-500">Was this response helpful?</span>
                  <div className="flex items-center gap-1">
                    {/* Thumbs Up Button */}
                    <button
                      type="button"
                      onClick={() => handleRate(m, 1)}
                      className={`p-1 rounded-md border transition flex items-center gap-1 ${
                        m.userRating === 1
                          ? 'bg-emerald-950 border-emerald-700 text-emerald-400'
                          : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-emerald-300 hover:border-emerald-800/50'
                      }`}
                      title="Thumbs Up (Accurate & Helpful)"
                    >
                      <ThumbsUp className="w-3 h-3" />
                    </button>

                    {/* Thumbs Down Button */}
                    <button
                      type="button"
                      onClick={() => handleRate(m, -1)}
                      className={`p-1 rounded-md border transition flex items-center gap-1 ${
                        m.userRating === -1
                          ? 'bg-rose-950 border-rose-700 text-rose-400'
                          : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-rose-300 hover:border-rose-800/50'
                      }`}
                      title="Thumbs Down (Inaccurate / Needs Correction)"
                    >
                      <ThumbsDown className="w-3 h-3" />
                    </button>

                    {/* Optional Comment Toggle */}
                    <button
                      type="button"
                      onClick={() => {
                        setActiveFeedbackMsgId(activeFeedbackMsgId === m.id ? null : m.id);
                        setFeedbackComment(m.ratingComment || '');
                      }}
                      className={`p-1 rounded-md border transition ${
                        activeFeedbackMsgId === m.id || m.ratingComment
                          ? 'bg-brand-950 border-brand-700 text-brand-300'
                          : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                      title="Add Feedback Comment"
                    >
                      <MessageSquare className="w-3 h-3" />
                    </button>
                  </div>
                </div>

                {/* Submitted confirmation tag */}
                {submittedFeedbackMsgIds[m.id] && (
                  <div className="flex items-center gap-1 text-[9px] text-emerald-400 animate-fadeIn">
                    <Check className="w-2.5 h-2.5" /> Feedback forwarded to LangSmith
                  </div>
                )}

                {/* Collapsible Feedback Comment Input Box */}
                {activeFeedbackMsgId === m.id && (
                  <div className="mt-1 p-2 rounded-lg bg-slate-900 border border-slate-800 space-y-1.5 animate-fadeIn">
                    <textarea
                      rows={2}
                      value={feedbackComment}
                      onChange={e => setFeedbackComment(e.target.value)}
                      placeholder="Optional feedback (e.g. correct formula, note discrepancies)..."
                      className="w-full bg-slate-950 border border-slate-800 focus:border-brand-500 rounded-md p-1.5 text-[10px] text-slate-200 focus:outline-none resize-none"
                    />
                    <div className="flex justify-end gap-1.5">
                      <button
                        type="button"
                        onClick={() => setActiveFeedbackMsgId(null)}
                        className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white text-[9px] transition"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSaveComment(m)}
                        className="px-2 py-0.5 rounded bg-brand-600 hover:bg-brand-500 text-white font-semibold text-[9px] transition shadow-sm"
                      >
                        Submit Feedback
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Live Reasoning Status Badge */}
        {isStreaming && currentReasoningStatus && (
          <div className="flex items-center gap-2 p-2.5 rounded-xl bg-brand-950/60 border border-brand-800/80 text-brand-300 text-xs animate-pulse">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-400 flex-shrink-0" />
            <span className="font-medium text-[11px] truncate">{currentReasoningStatus}</span>
          </div>
        )}

        {/* Suggested Prompts */}
        {!isStreaming && !isTurnLimitReached && messages.length <= 3 && (
          <div className="space-y-1.5 pt-2">
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-amber-400" /> Suggested Prompts
            </div>
            {suggestedPrompts.map((prompt, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleSend(prompt)}
                className="w-full text-left bg-slate-950/50 hover:bg-slate-850 border border-slate-800/80 p-2 rounded-xl text-xs text-slate-300 transition flex justify-between items-center group"
              >
                <span className="truncate pr-2">{prompt}</span>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-brand-400 transition-colors flex-shrink-0" />
              </button>
            ))}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Query Input Footer with Turn Limit Warning Banner */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/90">
        {/* 10-Turn Cap Warning Alert */}
        {isTurnLimitReached && (
          <div className="mb-2 p-2.5 rounded-xl bg-amber-950/70 border border-amber-800/80 text-amber-200 text-xs flex flex-col gap-2 animate-fadeIn">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-amber-300">Turn Limit Reached ({maxTurns}/{maxTurns})</span>
                <p className="text-[10px] text-amber-200/80 mt-0.5 leading-snug">
                  You have reached the maximum of {maxTurns} conversational turns for this chat session. Please start a new session to continue asking questions.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onNewSession}
              className="self-end px-3 py-1 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-[11px] transition shadow-sm flex items-center gap-1.5"
            >
              <Plus className="w-3 h-3" /> Start New Chat
            </button>
          </div>
        )}

        <form
          onSubmit={e => {
            e.preventDefault();
            handleSend();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            placeholder={
              isTurnLimitReached
                ? `Maximum turns reached (${maxTurns}/${maxTurns}). Start a new chat to continue.`
                : 'Ask Copilot about filings, ratios, trends...'
            }
            value={query}
            onChange={e => setQuery(e.target.value)}
            disabled={isStreaming || isTurnLimitReached}
            className="flex-1 bg-slate-900 border border-slate-800 focus:border-brand-500 disabled:opacity-50 disabled:bg-slate-950 disabled:cursor-not-allowed rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none transition"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={onAbortStream}
              className="bg-rose-600 hover:bg-rose-500 text-white px-3 py-2 rounded-xl transition flex items-center gap-1.5 text-xs font-semibold shadow-md shadow-rose-900/40"
              title="Stop Generation"
            >
              <Square className="w-3 h-3 fill-current" /> Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!query.trim() || isTurnLimitReached}
              className="bg-brand-600 hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed text-white p-2.5 rounded-xl transition shadow-md shadow-brand-600/30"
              title="Send Prompt"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          )}
        </form>
      </div>
    </aside>
  );
};
