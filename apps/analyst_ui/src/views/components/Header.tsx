import React from 'react';
import { Building2, LayoutDashboard, Upload, Activity, ChevronDown } from 'lucide-react';
import { Company } from '../../models/company';

interface HeaderProps {
  activeNav: 'dashboard' | 'upload';
  setActiveNav: (nav: 'dashboard' | 'upload') => void;
  companies: Company[];
  selectedCompanyId: number | null;
  onSelectCompany: (id: number) => void;
  activeJobCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  activeNav,
  setActiveNav,
  companies,
  selectedCompanyId,
  onSelectCompany,
  activeJobCount,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md px-6 py-3.5 flex justify-between items-center sticky top-0 z-40">
      {/* Brand & Company Switcher */}
      <div className="flex items-center gap-5">
        <div className="flex items-center gap-3">
          <div className="bg-brand-600 text-white p-2 rounded-lg font-bold flex items-center justify-center shadow-lg shadow-brand-500/20">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-2">
              CreditUnderwriter
              <span className="text-brand-400 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-brand-950/60 border border-brand-800/50">
                CoPilot v2.0
              </span>
            </h1>
          </div>
        </div>

        {/* Company Dropdown Switcher */}
        {companies.length > 0 && (
          <div className="relative group">
            <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-800 hover:border-slate-700 rounded-lg px-3 py-1.5 transition text-xs font-medium text-slate-200 cursor-pointer">
              <span className="text-slate-400">Company:</span>
              <select
                value={selectedCompanyId ?? ''}
                onChange={e => onSelectCompany(Number(e.target.value))}
                className="bg-transparent text-white font-semibold focus:outline-none cursor-pointer pr-4 appearance-none"
              >
                {companies.map(c => (
                  <option key={c.id} value={c.id} className="bg-slate-900 text-slate-100">
                    {c.name} {c.ticker ? `(${c.ticker})` : ''}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 pointer-events-none -ml-3" />
            </div>
          </div>
        )}
      </div>

      {/* Nav Tabs */}
      <nav className="flex items-center gap-1 bg-slate-950/70 border border-slate-800/80 rounded-lg p-1">
        <button
          id="nav-dashboard"
          onClick={() => setActiveNav('dashboard')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all ${
            activeNav === 'dashboard'
              ? 'bg-brand-600 text-white shadow-md shadow-brand-600/30'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <LayoutDashboard className="w-3.5 h-3.5" />
          Dashboard
        </button>
        <button
          id="nav-upload"
          onClick={() => setActiveNav('upload')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all relative ${
            activeNav === 'upload'
              ? 'bg-brand-600 text-white shadow-md shadow-brand-600/30'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Upload className="w-3.5 h-3.5" />
          Upload Filing
          {activeJobCount > 0 && (
            <span className="bg-amber-400 text-slate-950 text-[10px] font-black px-1.5 py-0.2 rounded-full leading-tight ml-1 animate-pulse">
              {activeJobCount}
            </span>
          )}
        </button>
      </nav>

      {/* Live System Status */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-900/60 px-3 py-1.5 rounded-md border border-slate-800/80">
          <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
          <span className="text-slate-300 font-medium">Pipeline Connected</span>
        </div>
      </div>
    </header>
  );
};
