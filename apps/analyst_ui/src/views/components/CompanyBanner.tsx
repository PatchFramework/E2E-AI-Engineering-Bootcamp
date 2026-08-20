import React from 'react';
import { FileText, ShieldCheck } from 'lucide-react';
import { CompanySummary } from '../../models/company';

interface CompanyBannerProps {
  summary: CompanySummary;
}

export const CompanyBanner: React.FC<CompanyBannerProps> = ({ summary }) => {
  const getRatingColor = (riskLevel: string) => {
    switch (riskLevel) {
      case 'low':
        return 'text-emerald-400';
      case 'moderate':
        return 'text-sky-400';
      case 'elevated':
        return 'text-amber-400';
      case 'high':
        return 'text-rose-400';
      default:
        return 'text-amber-400';
    }
  };

  return (
    <div className="bg-gradient-to-br from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800/90 rounded-2xl p-6 relative overflow-hidden shadow-xl">
      {/* Background ambient glow */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-brand-600/10 rounded-full blur-3xl -z-10 pointer-events-none" />

      <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-6">
        {/* Left: Company Identity */}
        <div>
          <span className="text-[11px] text-brand-400 font-bold tracking-widest uppercase bg-brand-950/60 border border-brand-800/40 px-2.5 py-0.5 rounded-full">
            Active Portfolio Company
          </span>
          <div className="flex items-baseline gap-3 mt-2">
            <h2 className="text-3xl font-extrabold tracking-tight text-white">{summary.name}</h2>
            {summary.ticker && (
              <span className="text-sm font-semibold text-slate-400 bg-slate-800/80 px-2.5 py-0.5 rounded-md border border-slate-700/50">
                {summary.ticker}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-2 flex items-center gap-1.5 font-medium">
            <FileText className="w-3.5 h-3.5 text-slate-400" />
            Primary Filing: <span className="text-slate-200 font-semibold">{summary.latestFiling}</span>
          </p>
        </div>

        {/* Right: Underwriting Summary Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-slate-950/70 p-4 rounded-xl border border-slate-800/80 backdrop-blur-md">
          {/* Suggested Rating */}
          <div className="px-3">
            <div className="text-[11px] text-slate-400 font-medium">Suggested Rating</div>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className={`text-2xl font-black ${getRatingColor(summary.riskLevel)}`}>{summary.rating}</span>
              <span className="text-xs text-slate-400 font-medium">({summary.risk} Risk)</span>
            </div>
          </div>

          {/* Latest Filing Year */}
          <div className="border-l border-slate-800/80 px-4">
            <div className="text-[11px] text-slate-400 font-medium">Latest Filing</div>
            <div className="text-sm font-bold text-slate-200 mt-1.5 truncate">{summary.latestFiling.split(' ')[0]}</div>
            <div className="text-[10px] text-slate-400">Annual Report</div>
          </div>

          {/* Data Quality */}
          <div className="border-l border-slate-800/80 px-4">
            <div className="text-[11px] text-slate-400 font-medium flex items-center gap-1">
              <ShieldCheck className="w-3 h-3 text-emerald-400" /> Data Quality
            </div>
            <div className="text-lg font-bold text-emerald-400 mt-0.5">
              {summary.dataQualityPct}% <span className="text-xs text-slate-400 font-normal">verified</span>
            </div>
          </div>

          {/* Quality Issues / Discrepancies */}
          <div className="border-l border-slate-800/80 px-4">
            <div className="text-[11px] text-slate-400 font-medium">Discrepancies</div>
            <div className="flex items-center gap-2 mt-1">
              {summary.issuesCount > 0 ? (
                <>
                  <span className="flex h-2 w-2 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
                  </span>
                  <span className="text-xs font-bold text-red-400">{summary.issuesCount} issues review</span>
                </>
              ) : (
                <div className="flex items-center gap-1 text-xs text-emerald-400 font-semibold">
                  <ShieldCheck className="w-3.5 h-3.5" /> 0 issues
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
