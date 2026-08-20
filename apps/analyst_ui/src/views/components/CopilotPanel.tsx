import React, { useState } from 'react';
import {
  TrendingUp,
  ArrowRight,
  Send,
  Sparkles,
  Bot,
  User,
  BookOpen,
} from 'lucide-react';
import { CompanySummary } from '../../models/company';

interface CopilotPanelProps {
  companySummary: CompanySummary;
  activeCompanyId: number | null;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
}

export const CopilotPanel: React.FC<CopilotPanelProps> = ({ companySummary }) => {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: `Hello Analyst! I have analyzed **${companySummary.name}**'s latest filing (${companySummary.latestFiling}). Credit rating is **${companySummary.rating}** with **${companySummary.risk} Risk**. Ask me any question about the company's financial leverage, debt structure, or filing evidence citations.`,
    },
  ]);

  const handleSend = (textToSend?: string) => {
    const q = textToSend || query;
    if (!q.trim()) return;

    const userMsg: Message = { role: 'user', content: q };
    setMessages(prev => [...prev, userMsg]);
    setQuery('');

    // Generate context-aware assistant reply
    setTimeout(() => {
      let reply = `Based on the latest filing for ${companySummary.name}, operating leverage is rated ${companySummary.rating}. Net debt increased due to debt additions against steady EBITDA.`;
      let citations: string[] = ['Annual Report 2025 · Section: Financial Highlights · p.42'];

      if (q.toLowerCase().includes('leverage') || q.toLowerCase().includes('debt')) {
        reply = `Total debt increased to €1.2B with net debt rising to €840M. Combined with reported EBITDA of €178M, the Net Debt / EBITDA ratio stands at 4.72x.`;
        citations = [
          'Annual Report 2025 · p.87 (Debt Schedule)',
          'Annual Report 2025 · p.104 (Cash & Equivalents)',
        ];
      } else if (q.toLowerCase().includes('interest') || q.toLowerCase().includes('coverage')) {
        reply = `Interest coverage is calculated from EBITDA / Interest Expense. The ratio is 2.80x, providing adequate headroom over typical loan covenants of 2.0x.`;
        citations = ['Annual Report 2025 · p.45 (Finance Expenses)'];
      }

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: reply,
          citations,
        },
      ]);
    }, 600);
  };

  const suggestedPrompts = [
    'Why did leverage increase in FY2025?',
    'Analyze interest coverage sensitivity',
    'List breakdown of long-term debt items',
  ];

  return (
    <aside className="w-96 border-l border-slate-800 bg-slate-900/40 backdrop-blur-md flex flex-col h-full">
      {/* Panel Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-brand-950 text-brand-400 border border-brand-800/60">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-100 flex items-center gap-1.5">
              Underwriting Copilot
            </h3>
            <span className="text-[10px] text-slate-400">Context: {companySummary.name}</span>
          </div>
        </div>
        <span className="text-[9px] bg-slate-800/80 px-2 py-0.5 rounded text-brand-300 font-bold uppercase tracking-wider border border-slate-700/50">
          GPT-4o Ready
        </span>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`p-3.5 rounded-xl text-xs leading-relaxed ${
              m.role === 'assistant'
                ? 'bg-slate-950/80 border border-slate-800 text-slate-200'
                : 'bg-brand-950/40 border border-brand-900/50 text-brand-100 ml-4'
            }`}
          >
            <div className="flex items-center gap-1.5 mb-1 text-[10px] font-bold text-slate-400">
              {m.role === 'assistant' ? (
                <>
                  <Bot className="w-3.5 h-3.5 text-brand-400" /> Copilot
                </>
              ) : (
                <>
                  <User className="w-3.5 h-3.5 text-slate-400" /> Analyst
                </>
              )}
            </div>
            <p className="whitespace-pre-line">{m.content}</p>

            {m.citations && m.citations.length > 0 && (
              <div className="mt-2.5 pt-2 border-t border-slate-800 text-[10px] text-brand-400 font-medium">
                <div className="flex items-center gap-1 text-slate-400 mb-0.5">
                  <BookOpen className="w-3 h-3" /> Citations:
                </div>
                {m.citations.map((c, i) => (
                  <div key={i} className="hover:underline cursor-pointer">
                    • {c}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Suggested Prompts */}
        <div className="space-y-2 pt-2">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-amber-400" /> Suggested Prompts
          </div>
          {suggestedPrompts.map((prompt, i) => (
            <button
              key={i}
              onClick={() => handleSend(prompt)}
              className="w-full text-left bg-slate-950/50 hover:bg-slate-850 border border-slate-800/80 p-2.5 rounded-xl text-xs text-slate-300 transition flex justify-between items-center group"
            >
              <span className="truncate pr-2">{prompt}</span>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-brand-400 transition-colors flex-shrink-0" />
            </button>
          ))}
        </div>
      </div>

      {/* Query Input Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/90">
        <form
          onSubmit={e => {
            e.preventDefault();
            handleSend();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            placeholder="Ask Copilot about filings..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="flex-1 bg-slate-900 border border-slate-800 focus:border-brand-500 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none transition"
          />
          <button
            type="submit"
            className="bg-brand-600 hover:bg-brand-500 text-white p-2.5 rounded-xl transition shadow-md shadow-brand-600/30"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </aside>
  );
};
