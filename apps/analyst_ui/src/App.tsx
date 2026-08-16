import { useState } from 'react';
import { 
  Building2, 
  TrendingUp, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  ArrowRight, 
  ChevronRight, 
  Send, 
  BookOpen, 
  Settings, 
  FileText, 
  Activity 
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('Overview');
  const [copilotQuery, setCopilotQuery] = useState('');
  const [selectedFact, setSelectedFact] = useState<string | null>(null);

  // Stub data for demonstration
  const companyInfo = {
    name: 'Acme Corporation',
    rating: 'BB',
    risk: 'Elevated',
    latestFiling: 'FY2025 Annual Report',
    dataQuality: '87%',
    issuesCount: 3
  };

  const tabs = ['Overview', 'Profitability', 'Leverage', 'Coverage', 'Liquidity', 'Cash Flow', 'Balance Sheet'];

  const metrics = [
    { name: 'Revenue', value: '€2.4B', change: '+12% YoY', trend: 'up', status: 'Verified', category: 'Profitability' },
    { name: 'EBITDA', value: '€184M', change: '-4% YoY', trend: 'down', status: 'Corrected', category: 'Profitability' },
    { name: 'Total Debt', value: '€1.2B', change: '+35% YoY', trend: 'up', status: 'Verified', category: 'Leverage' },
    { name: 'Net Debt / EBITDA', value: '4.57x', change: '+0.83x YoY', trend: 'up', status: 'Corrected', category: 'Leverage' },
    { name: 'EBITDA / Interest', value: '2.8x', change: '-1.2x YoY', trend: 'down', status: 'Unverified', category: 'Coverage' },
    { name: 'Current Ratio', value: '1.45x', change: '-0.1x YoY', trend: 'down', status: 'Verified', category: 'Liquidity' },
    { name: 'Free Cash Flow', value: '-€22M', change: '-€45M YoY', trend: 'down', status: 'Verified', category: 'Cash Flow' }
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Navigation Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md px-6 py-4 flex justify-between items-center sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="bg-brand-600 text-white p-2 rounded-lg font-bold flex items-center justify-center">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
              CreditUnderwriter <span className="text-brand-400 text-xs font-semibold px-2 py-0.5 rounded-full bg-brand-900/30 border border-brand-800/50">CoPilot v1.0</span>
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-800/40 px-3 py-1.5 rounded-md border border-slate-700/30">
            <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            API Connected
          </div>
          <button className="text-slate-400 hover:text-white transition">
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Side: Workstation */}
        <main className="flex-1 p-6 overflow-y-auto space-y-6">
          {/* Company Banner */}
          <div className="bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800/80 rounded-xl p-6 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-96 h-96 bg-brand-900/10 rounded-full blur-3xl -z-10 pointer-events-none"></div>

            <div className="flex flex-col lg:flex-row lg:justify-between lg:items-start gap-6">
              <div>
                <span className="text-xs text-brand-400 font-semibold tracking-wider uppercase">Active Portfolio Company</span>
                <h2 className="text-3xl font-extrabold tracking-tight mt-1">{companyInfo.name}</h2>
                <p className="text-xs text-slate-400 mt-2 flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-slate-400" />
                  Primary Filing: <span className="text-slate-200 font-medium">{companyInfo.latestFiling}</span>
                </p>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-slate-950/60 p-4 rounded-lg border border-slate-800/50 backdrop-blur-sm">
                <div className="px-2">
                  <div className="text-xs text-slate-400">Suggested Rating</div>
                  <div className="flex items-center gap-1.5 mt-1">
                    <span className="text-2xl font-black text-amber-500">{companyInfo.rating}</span>
                    <span className="text-xs text-slate-400 font-medium">({companyInfo.risk} Risk)</span>
                  </div>
                </div>

                <div className="border-l border-slate-800 px-4">
                  <div className="text-xs text-slate-400">Data Quality</div>
                  <div className="text-lg font-bold text-emerald-400 mt-1">{companyInfo.dataQuality} <span className="text-xs text-slate-400 font-normal">verified</span></div>
                </div>

                <div className="border-l border-slate-800 px-4 col-span-2">
                  <div className="text-xs text-slate-400">Discrepancies</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="flex h-2 w-2 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                    </span>
                    <span className="text-sm font-semibold text-red-400">{companyInfo.issuesCount} issues require review</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Navigation Category Tabs */}
          <div className="border-b border-slate-800 flex gap-2 overflow-x-auto py-1">
            {tabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2.5 rounded-t-lg font-medium text-sm transition-all whitespace-nowrap border-b-2 -mb-1 ${
                  activeTab === tab 
                    ? 'border-brand-500 text-brand-400 bg-brand-950/10' 
                    : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/30'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* KPI Dashboard */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {metrics
              .filter(m => activeTab === 'Overview' || m.category === activeTab)
              .map((metric, idx) => (
                <div 
                  key={idx} 
                  onClick={() => setSelectedFact(metric.name)}
                  className="bg-slate-900/60 border border-slate-800 hover:border-slate-700/80 hover:bg-slate-900 transition p-5 rounded-xl cursor-pointer group flex flex-col justify-between h-44"
                >
                  <div>
                    <div className="flex justify-between items-start">
                      <span className="text-xs text-slate-400 font-semibold tracking-wide">{metric.name}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                        metric.status === 'Verified' ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/50' :
                        metric.status === 'Corrected' ? 'bg-indigo-950/40 text-indigo-400 border border-indigo-900/50' :
                        'bg-amber-950/40 text-amber-400 border border-amber-900/50'
                      }`}>
                        {metric.status}
                      </span>
                    </div>
                    <div className="text-3xl font-black tracking-tight text-white mt-3">{metric.value}</div>
                  </div>

                  <div className="flex justify-between items-center border-t border-slate-800/60 pt-3 mt-4">
                    <div className="flex items-center gap-1.5">
                      <span className={`text-xs font-bold ${metric.trend === 'up' && metric.name.includes('Debt') ? 'text-red-400' : 'text-emerald-400'}`}>
                        {metric.change}
                      </span>
                    </div>
                    <div className="text-slate-500 group-hover:text-slate-300 text-xs flex items-center gap-1 transition">
                      Details <ChevronRight className="w-3.5 h-3.5" />
                    </div>
                  </div>
                </div>
              ))}
          </div>

          {/* Data Correction Drawer (Simulated inline for demo) */}
          {selectedFact && (
            <div className="bg-slate-900 border border-indigo-900/60 rounded-xl p-6 relative">
              <button 
                onClick={() => setSelectedFact(null)} 
                className="absolute top-4 right-4 text-slate-400 hover:text-slate-100"
              >
                ✕
              </button>
              <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-indigo-400" />
                Data Correction UX &bull; {selectedFact}
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Verify or edit facts extracted by AI from source filings. Any update triggers automatic synchronous recalculation of all derived KPIs.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
                <div>
                  <div className="text-xs text-slate-400 uppercase tracking-wide">Current Extracted Fact</div>
                  <div className="text-2xl font-black mt-1 text-white">€178,000,000</div>
                  <div className="text-xs text-indigo-400 mt-2 bg-indigo-950/30 border border-indigo-900/50 px-2 py-1 rounded inline-block">
                    Status: AI-Generated (Unverified)
                  </div>
                </div>

                <div className="border-l border-slate-800 pl-6">
                  <div className="text-xs text-slate-400 uppercase tracking-wide">Analyst Override</div>
                  <input 
                    type="text" 
                    placeholder="Enter corrected value (e.g. 184000000)" 
                    className="w-full bg-slate-950 border border-slate-800 focus:border-brand-500 rounded px-3 py-2 text-sm mt-2 text-white focus:outline-none" 
                  />
                  <input 
                    type="text" 
                    placeholder="Reason for change..." 
                    className="w-full bg-slate-950 border border-slate-800 focus:border-brand-500 rounded px-3 py-2 text-sm mt-2 text-white focus:outline-none" 
                  />
                </div>

                <div className="border-l border-slate-800 pl-6 flex flex-col justify-end gap-3">
                  <button className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs px-4 py-2.5 rounded-lg transition">
                    Verify Correct
                  </button>
                  <button className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs px-4 py-2.5 rounded-lg transition">
                    Save Correction
                  </button>
                </div>
              </div>

              {/* Provenance lineage snippet */}
              <div className="bg-slate-950 border border-slate-800/80 rounded-lg p-4 mt-6 flex items-start gap-3">
                <BookOpen className="w-5 h-5 text-brand-400 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="text-xs font-bold text-slate-300">Evidence Provenance Lineage:</div>
                  <p className="text-xs text-slate-400 mt-1 italic">
                    "...operating income was €184.2M after adjustments (see page 42). Reported EBITDA according to traditional standard definition was €178M..."
                  </p>
                  <div className="text-[10px] text-brand-400 mt-2 font-medium">
                    Filing Source: <a href="#" className="underline hover:text-brand-300">Annual Report 2025 &bull; Section: Finance Highlights &bull; Page 42</a>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>

        {/* Right Side: Copilot Panel */}
        <aside className="w-96 border-l border-slate-800 bg-slate-900/30 backdrop-blur-md flex flex-col">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <h3 className="font-bold flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-brand-400" />
              Underwriting Copilot
            </h3>
            <span className="text-[9px] bg-slate-800 px-2 py-1 rounded text-slate-400 font-bold uppercase">
              GPT-4o Ready
            </span>
          </div>

          <div className="flex-1 p-4 overflow-y-auto space-y-4">
            <div className="bg-slate-800/40 border border-slate-700/30 p-3.5 rounded-lg">
              <p className="text-xs text-slate-300 leading-relaxed">
                Hello Analyst! I have analyzed <strong>{companyInfo.name}</strong>'s financial history from 2021 to 2025. 
              </p>
              <p className="text-xs text-slate-300 leading-relaxed mt-2">
                The leverage ratio deteriorated to <strong>4.57x</strong> due to rising debt. Ask me questions about specific metrics or evidence.
              </p>
            </div>

            <div className="space-y-2">
              <div className="text-[10px] font-semibold text-slate-500 uppercase">Suggested Prompts</div>
              <button className="w-full text-left bg-slate-850 hover:bg-slate-800 border border-slate-800/80 p-2.5 rounded text-xs text-slate-300 transition flex justify-between items-center group">
                <span>Why did leverage increase in 2025?</span>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-300" />
              </button>
              <button className="w-full text-left bg-slate-850 hover:bg-slate-800 border border-slate-800/80 p-2.5 rounded text-xs text-slate-300 transition flex justify-between items-center group">
                <span>List details of long-term debt items</span>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-300" />
              </button>
            </div>
          </div>

          <div className="p-4 border-t border-slate-800 bg-slate-950/80">
            <form onSubmit={(e) => { e.preventDefault(); setCopilotQuery(''); }} className="flex gap-2">
              <input
                type="text"
                placeholder="Ask Copilot about filings..."
                value={copilotQuery}
                onChange={(e) => setCopilotQuery(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-800 focus:border-brand-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none"
              />
              <button 
                type="submit" 
                className="bg-brand-600 hover:bg-brand-500 text-white p-2 rounded-lg transition"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </aside>
      </div>
    </div>
  );
}
