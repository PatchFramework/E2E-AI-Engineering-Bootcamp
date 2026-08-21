import React, { useState, useRef, useEffect } from 'react';
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
  Loader2,
  X,
  Target,
  FileText,
} from 'lucide-react';
import { CopilotMessage, CopilotContextSnapshot, ChatSessionSummary, CopilotCitation } from '../../models/copilot';
import { ChartWidgetRenderer } from './copilot/ChartWidgetRenderer';

interface CopilotPanelProps {
  isOpen: boolean;
  onToggleOpen: () => void;
  width: number;
  onWidthChange: (w: number) => void;
  contextSnapshot: CopilotContextSnapshot;
  messages: CopilotMessage[];
  isStreaming: boolean;
  currentReasoningStatus: string | null;
  onSendMessage: (msg: string) => void;
  onAbortStream: () => void;
  onNewSession: () => void;
  sessions: ChatSessionSummary[];
  activeSessionId: string;
  onSwitchSession: (sessionId: string) => void;
  onOpenCitation?: (citation: CopilotCitation) => void;
}

export const CopilotPanel: React.FC<CopilotPanelProps> = ({
  isOpen,
  onToggleOpen,
  width,
  onWidthChange,
  contextSnapshot,
  messages,
  isStreaming,
  currentReasoningStatus,
  onSendMessage,
  onAbortStream,
  onNewSession,
  sessions,
  activeSessionId,
  onSwitchSession,
  onOpenCitation,
}) => {
  const [query, setQuery] = useState('');
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);
  const isDraggingRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages or reasoning updates
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, currentReasoningStatus]);

  // Handle Drag-to-Resize on left border
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = true;

    const startX = e.clientX;
    const startWidth = width;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const delta = startX - moveEvent.clientX;
      const newWidth = Math.min(800, Math.max(360, startWidth + delta));
      onWidthChange(newWidth);
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const handleSend = (textToSend?: string) => {
    const q = textToSend || query;
    if (!q.trim() || isStreaming) return;
    onSendMessage(q);
    setQuery('');
  };

  // Dynamic context pill label
  const activeFocusLabel = contextSnapshot.activeMetric
    ? `Metric: ${contextSnapshot.activeMetric.display_name}`
    : contextSnapshot.activeFacts && contextSnapshot.activeFacts.length > 0
    ? `${contextSnapshot.activeFacts.length} Facts (${contextSnapshot.activeFacts.map(f => f.concept).join(', ')})`
    : contextSnapshot.activeDocuments && contextSnapshot.activeDocuments.length > 0
    ? `Doc: ${contextSnapshot.activeDocuments[0].displayedPage}`
    : `Company: ${contextSnapshot.companyName || 'Acme Corp'}`;

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
      className="relative flex flex-col h-full bg-slate-900/95 border-l border-slate-800 backdrop-blur-xl shadow-2xl z-30 transition-all duration-75 select-none"
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
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-brand-950 text-brand-400 border border-brand-800/60 shadow-sm">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-100 flex items-center gap-1.5">
              Underwriting Copilot
            </h3>
            <span className="text-[10px] text-slate-400 truncate block max-w-[160px]">
              {contextSnapshot.companyName || 'Corporate Filing'}
            </span>
          </div>
        </div>

        {/* Top Action Buttons */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onNewSession}
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

      {/* Dynamic Context Focus Pill Bar */}
      <div className="px-3.5 py-1.5 bg-slate-950/40 border-b border-slate-850 flex items-center justify-between text-[10px]">
        <div className="flex items-center gap-1.5 text-slate-300 font-medium truncate">
          <Target className="w-3 h-3 text-brand-400 flex-shrink-0" />
          <span className="text-slate-400">Context:</span>
          <span className="text-slate-200 font-semibold truncate">{activeFocusLabel}</span>
        </div>
        <span className="text-[9px] bg-slate-800/80 px-1.5 py-0.5 rounded text-brand-300 font-bold uppercase tracking-wider border border-slate-700/50 flex-shrink-0">
          Grounded
        </span>
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
            <div className="flex items-center gap-1.5 mb-1.5 text-[10px] font-bold text-slate-400">
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

            {/* Content Text */}
            <p className="whitespace-pre-line leading-relaxed">{m.content}</p>

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
          </div>
        ))}

        {/* Live Reasoning Status Badge */}
        {isStreaming && currentReasoningStatus && (
          <div className="flex items-center gap-2 p-2.5 rounded-xl bg-brand-950/60 border border-brand-800/80 text-brand-300 text-xs animate-pulse">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-400" />
            <span className="font-medium text-[11px]">{currentReasoningStatus}</span>
          </div>
        )}

        {/* Suggested Prompts */}
        {!isStreaming && messages.length <= 3 && (
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

      {/* Query Input Footer */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/90">
        <form
          onSubmit={e => {
            e.preventDefault();
            handleSend();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            placeholder="Ask Copilot about filings, ratios, trends..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            disabled={isStreaming}
            className="flex-1 bg-slate-900 border border-slate-800 focus:border-brand-500 disabled:opacity-50 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none transition"
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
              disabled={!query.trim()}
              className="bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-white p-2.5 rounded-xl transition shadow-md shadow-brand-600/30"
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
