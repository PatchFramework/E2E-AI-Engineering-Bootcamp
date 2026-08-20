import React from 'react';
import {
  X,
  TrendingUp,
  Calculator,
  Layers,
  FileText,
  CheckCircle,
  Edit3,
  BookOpen,
  Loader2,
  Sparkles,
} from 'lucide-react';

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import {
  MetricItem,
  MetricLineage,
  formatMetricValue,
  formatYoYChange,
  getMetricRiskInterpretation,
} from '../../models/metric';
import { FinancialFact } from '../../models/fact';

interface KPIDetailDrawerProps {
  metric: MetricItem | null;
  lineage: MetricLineage | null;
  loadingLineage: boolean;
  onClose: () => void;
  onOpenCorrection: (fact: FinancialFact) => void;
  onVerifyFact: (factId: number) => Promise<any>;
}

export const KPIDetailDrawer: React.FC<KPIDetailDrawerProps> = ({
  metric,
  lineage,
  loadingLineage,
  onClose,
  onOpenCorrection,
  onVerifyFact,
}) => {
  if (!metric) return null;

  const formattedValue = formatMetricValue(metric.current_value, metric.unit);
  const yoyInfo = formatYoYChange(metric.yoy_change, metric.yoy_change_pct, metric.unit);
  const riskInterpretation = getMetricRiskInterpretation(
    metric.metric_name,
    metric.current_value,
    metric.trend
  );

  // Deduplicate and sort history by fiscal year
  const uniqueHistory = React.useMemo(() => {
    const map = new Map<number, (typeof metric.history)[0]>();
    for (const h of metric.history) {
      if (!map.has(h.fiscal_year) || (h.value !== null && map.get(h.fiscal_year)?.value === null)) {
        map.set(h.fiscal_year, h);
      }
    }
    return Array.from(map.values()).sort((a, b) => a.fiscal_year - b.fiscal_year);
  }, [metric.history]);

  // Historical chart data
  const chartData = uniqueHistory.map(h => ({
    year: `${h.fiscal_year}`,
    val: h.value !== null ? Number(h.value.toFixed(2)) : null,
  }));


  const [verifiedFactIds, setVerifiedFactIds] = React.useState<Set<number>>(new Set());

  const handleVerifyFact = async (factId: number) => {
    setVerifiedFactIds(prev => new Set(prev).add(factId));
    try {
      await onVerifyFact(factId);
    } catch {
      setVerifiedFactIds(prev => {
        const next = new Set(prev);
        next.delete(factId);
        return next;
      });
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/70 backdrop-blur-sm flex justify-end transition-opacity">
      <div className="w-full max-w-2xl bg-slate-900 border-l border-slate-800 h-full overflow-y-auto flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
        {/* Drawer Header */}
        <div className="p-6 border-b border-slate-800 sticky top-0 bg-slate-900/95 backdrop-blur-md z-10 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-brand-400 bg-brand-950/60 border border-brand-800/50 px-2.5 py-0.5 rounded-full">
                {metric.category} KPI
              </span>
              <span className="text-xs text-slate-400 font-medium">FY{metric.fiscal_year} {metric.fiscal_period}</span>
            </div>
            <h2 className="text-2xl font-extrabold text-white tracking-tight mt-1.5">{metric.display_name}</h2>
          </div>

          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-2 rounded-lg bg-slate-800/40 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drawer Body */}
        <div className="p-6 space-y-6 flex-1">
          {/* Primary Metric Snapshot */}
          <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <div className="text-xs text-slate-400 font-medium">Current Period Value ({metric.fiscal_year})</div>
              <div className="text-4xl font-black text-white mt-1">{formattedValue}</div>
              <div className="text-xs font-bold text-slate-400 mt-2 flex items-center gap-2">
                <span
                  className={
                    metric.trend === 'up' && metric.metric_name.includes('debt')
                      ? 'text-rose-400'
                      : metric.trend === 'up'
                      ? 'text-emerald-400'
                      : 'text-slate-300'
                  }
                >
                  {yoyInfo.text}
                </span>
                {metric.prior_value !== null && metric.prior_value !== undefined && (
                  <span className="text-slate-500 font-normal">
                    (Prior: {formatMetricValue(metric.prior_value, metric.unit)})
                  </span>
                )}
              </div>
            </div>

            <div className="flex flex-col gap-2 items-start sm:items-end">
              <span className="text-xs text-slate-400">Provenance Status:</span>
              <span
                className={`text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wider ${
                  metric.verification_status === 'VERIFIED'
                    ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/60'
                    : metric.verification_status === 'CORRECTED'
                    ? 'bg-indigo-950/60 text-indigo-400 border border-indigo-800/60'
                    : 'bg-amber-950/60 text-amber-400 border border-amber-800/60'
                }`}
              >
                {metric.verification_status === 'VERIFIED'
                  ? '✓ Verified'
                  : metric.verification_status === 'CORRECTED'
                  ? 'Corrected'
                  : 'AI-Generated (Unverified)'}
              </span>
            </div>
          </div>

          {/* Historical Trend Chart & Data Table */}
          <div className="bg-slate-950/40 border border-slate-800/80 rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-brand-400" /> Historical Performance
              </h3>
              <span className="text-[11px] text-slate-400">Multi-year trend</span>
            </div>

            {/* Recharts Area Chart */}
            {chartData.length > 1 ? (
              <div className="h-44 w-full pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="metricGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="year" stroke="#64748b" fontSize={11} />
                    <YAxis stroke="#64748b" fontSize={11} domain={['auto', 'auto']} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                      labelStyle={{ color: '#94a3b8', fontSize: '11px' }}
                      formatter={(val: any) => [formatMetricValue(val, metric.unit), metric.display_name]}
                    />
                    <Area
                      type="monotone"
                      dataKey="val"
                      stroke="#3b82f6"
                      strokeWidth={2.5}
                      fill="url(#metricGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="text-xs text-slate-500 py-6 text-center">Single period available</div>
            )}

            {/* Quick Data Points */}
            <div className="grid grid-cols-5 gap-2 border-t border-slate-800/80 pt-3">
              {uniqueHistory.map(h => (
                <div key={h.fiscal_year} className="text-center p-2 rounded-lg bg-slate-900/60 border border-slate-800/50">
                  <div className="text-[10px] text-slate-400">{h.fiscal_year}</div>
                  <div className="text-xs font-bold text-slate-100 mt-0.5">
                    {formatMetricValue(h.value, metric.unit)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Underwriting Risk Interpretation */}
          <div className="bg-slate-950/40 border border-slate-800/80 rounded-2xl p-5 space-y-2">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" /> Credit Risk Interpretation
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">{riskInterpretation}</p>
          </div>

          {/* Mathematical Formula Breakdown */}
          {metric.formula_expression && (
            <div className="bg-slate-950/40 border border-slate-800/80 rounded-2xl p-5 space-y-3">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Calculator className="w-4 h-4 text-emerald-400" /> Deterministic Formula
              </h3>
              <div className="bg-slate-900/80 font-mono text-xs text-emerald-400 px-4 py-2.5 rounded-xl border border-slate-800 flex items-center justify-between">
                <span>{metric.formula_expression}</span>
                <span className="text-white font-bold">= {formattedValue}</span>
              </div>
            </div>
          )}

          {/* Input Facts & Traceability Provenance */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Layers className="w-4 h-4 text-brand-400" /> Input Financial Facts & Sources
              </h3>
              {loadingLineage && <Loader2 className="w-3.5 h-3.5 text-brand-400 animate-spin" />}
            </div>

            {lineage && lineage.input_facts.length > 0 ? (
              <div className="space-y-3">
                {lineage.input_facts.map((inf, idx) => {
                  const factValueStr = formatMetricValue(inf.value, inf.unit);
                  const isVerified =
                    inf.verification_status === 'VERIFIED' ||
                    (inf.fact_id ? verifiedFactIds.has(inf.fact_id) : false);
                  const isCorrected = inf.origin === 'ANALYST_CORRECTED';

                  return (
                    <div
                      key={idx}
                      className="bg-slate-950/60 border border-slate-800/80 rounded-2xl p-4 transition hover:border-slate-700"
                    >
                      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-white">{inf.concept}</span>
                            <span
                              className={`text-[10px] px-2 py-0.2 rounded-full font-bold uppercase tracking-wider ${
                                isCorrected
                                  ? 'bg-indigo-950/50 text-indigo-400 border border-indigo-800/50'
                                  : isVerified
                                  ? 'bg-emerald-950/50 text-emerald-400 border border-emerald-800/50'
                                  : 'bg-amber-950/50 text-amber-400 border border-amber-800/50'
                              }`}
                            >
                              {isCorrected ? 'Corrected' : isVerified ? '✓ Verified' : 'Unverified'}
                            </span>
                          </div>

                          <div className="text-lg font-black text-slate-100 mt-1">{factValueStr}</div>
                        </div>

                        {/* Quick action buttons for analyst */}
                        <div className="flex items-center gap-2">
                          {!isVerified && inf.fact_id && (
                            <button
                              onClick={() => handleVerifyFact(inf.fact_id!)}
                              className="text-xs font-semibold bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-400 border border-emerald-800/60 px-3 py-1.5 rounded-lg transition flex items-center gap-1.5"
                            >
                              <CheckCircle className="w-3.5 h-3.5" /> Verify
                            </button>
                          )}

                          {inf.fact_id && (
                            <button
                              onClick={() => {
                                onOpenCorrection({
                                  id: inf.fact_id!,
                                  company_id: metric.fiscal_year,
                                  concept: inf.concept,
                                  value: inf.value ?? 0,
                                  unit: inf.unit,
                                  fiscal_year: metric.fiscal_year,
                                  fiscal_period: metric.fiscal_period,
                                  version: inf.fact_version_id ?? 1,
                                  origin: (inf.origin as any) ?? 'AI_GENERATED',
                                  verification_status: isVerified ? 'VERIFIED' : ((inf.verification_status as any) ?? 'UNVERIFIED'),
                                  updated_at: new Date().toISOString(),
                                });
                              }}
                              className="text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-lg transition flex items-center gap-1.5"
                            >
                              <Edit3 className="w-3.5 h-3.5" /> Correct
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Source Citation & Evidence Snippet (PRD lines 74-78) */}
                      {inf.source_location && (
                        <div className="mt-3 pt-3 border-t border-slate-800/70 text-xs text-slate-400 flex items-start gap-2">
                          <BookOpen className="w-4 h-4 text-brand-400 flex-shrink-0 mt-0.5" />
                          <div>
                            <div className="font-semibold text-slate-300">
                              {inf.document?.filename || 'Annual Report'}{' '}
                              {inf.source_location.page_number && `· Page ${inf.source_location.page_number}`}
                              {inf.source_location.section && ` · ${inf.source_location.section}`}
                            </div>
                            {inf.source_location.text_snippet && (
                              <p className="italic text-slate-400 mt-1 text-[11px] bg-slate-900/60 p-2 rounded-lg border border-slate-800/60">
                                "{inf.source_location.text_snippet}"
                              </p>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="bg-slate-950/40 border border-slate-800/60 rounded-xl p-4 text-center text-xs text-slate-500">
                {loadingLineage ? 'Loading provenance lineage...' : 'No direct fact lineage linked.'}
              </div>
            )}
          </div>

          {/* Cited Document Chunks for RAG (if present) */}
          {lineage && lineage.cited_chunks && lineage.cited_chunks.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-400" /> Citable Filing Chunks (RAG Grounding)
              </h3>
              <div className="space-y-2">
                {lineage.cited_chunks.slice(0, 2).map(chunk => (
                  <div
                    key={chunk.chunk_id}
                    className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3.5 text-xs text-slate-300"
                  >
                    <div className="text-[10px] font-bold text-indigo-400 mb-1">
                      Page {chunk.page_number} {chunk.section_path && `· ${chunk.section_path}`}
                    </div>
                    <p className="line-clamp-3 text-slate-400">{chunk.text_content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
