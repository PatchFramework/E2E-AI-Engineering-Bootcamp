import React from 'react';
import { ChevronRight } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area } from 'recharts';
import { MetricItem, formatMetricValue, formatYoYChange } from '../../models/metric';

interface KPICardProps {
  metric: MetricItem;
  onClick: () => void;
}

export const KPICard: React.FC<KPICardProps> = ({ metric, onClick }) => {
  const formattedValue = formatMetricValue(metric.current_value, metric.unit);
  const yoyInfo = formatYoYChange(metric.yoy_change, metric.yoy_change_pct, metric.unit);

  // Contextual color logic for trends
  const isDebtMetric =
    metric.metric_name.includes('debt') ||
    metric.metric_name.includes('liability') ||
    metric.metric_name === 'capex';

  const isGoodTrend = isDebtMetric ? yoyInfo.direction === 'down' : yoyInfo.direction === 'up';
  const isBadTrend = isDebtMetric ? yoyInfo.direction === 'up' : yoyInfo.direction === 'down';

  const trendColorClass = isGoodTrend
    ? 'text-emerald-400'
    : isBadTrend
    ? 'text-rose-400'
    : 'text-slate-400';

  // Status badge styling
  const statusBadge = (() => {
    switch (metric.verification_status) {
      case 'VERIFIED':
        return (
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider bg-emerald-950/40 text-emerald-400 border border-emerald-900/50">
            ✓ Verified
          </span>
        );
      case 'CORRECTED':
        return (
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider bg-indigo-950/40 text-indigo-400 border border-indigo-900/50">
            Corrected
          </span>
        );
      case 'UNAVAILABLE':
        return (
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider bg-slate-800/60 text-slate-400 border border-slate-700/50">
            N/A
          </span>
        );
      default:
        return (
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider bg-amber-950/40 text-amber-400 border border-amber-900/50">
            Unverified
          </span>
        );
    }
  })();

  // Sparkline data deduplicated by fiscal_year
  const sparkData = React.useMemo(() => {
    const map = new Map<number, number>();
    for (const h of metric.history) {
      if (!map.has(h.fiscal_year) || h.value !== null) {
        map.set(h.fiscal_year, h.value !== null ? h.value : 0);
      }
    }
    return Array.from(map.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([yr, val]) => ({ year: yr, val }));
  }, [metric.history]);


  const sparkColor = isBadTrend ? '#f43f5e' : '#10b981';

  return (
    <div
      onClick={onClick}
      className="bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-brand-500/50 transition-all duration-200 p-5 rounded-2xl cursor-pointer group flex flex-col justify-between h-48 relative overflow-hidden shadow-lg hover:shadow-brand-950/40 hover:scale-[1.01]"
    >
      <div>
        {/* Card Header: Title & Verification Badge */}
        <div className="flex justify-between items-start gap-2">
          <div>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
              {metric.category}
            </span>
            <h3 className="text-sm font-bold text-slate-100 tracking-tight group-hover:text-brand-300 transition">
              {metric.display_name}
            </h3>
          </div>
          {statusBadge}
        </div>

        {/* Metric Primary Value */}
        <div className="text-3xl font-extrabold tracking-tight text-white mt-3 flex items-baseline gap-2">
          {metric.status === 'AVAILABLE' ? (
            formattedValue
          ) : (
            <span className="text-xl font-bold text-slate-500">N/A</span>
          )}
        </div>
      </div>

      {/* Sparkline & YoY Footer */}
      <div className="border-t border-slate-800/70 pt-3 mt-3 flex items-center justify-between gap-3">
        {/* YoY delta */}
        <div className="flex items-center gap-1.5 min-w-0">
          <span className={`text-xs font-bold ${trendColorClass} truncate`}>{yoyInfo.text}</span>
        </div>

        {/* Mini Sparkline preview if multiple points exist */}
        {sparkData.length >= 2 && (
          <div className="w-16 h-7 opacity-75 group-hover:opacity-100 transition">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkData}>
                <Area
                  type="monotone"
                  dataKey="val"
                  stroke={sparkColor}
                  strokeWidth={1.5}
                  fill={sparkColor}
                  fillOpacity={0.15}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        <div className="text-slate-500 group-hover:text-slate-200 text-xs flex items-center gap-0.5 transition flex-shrink-0 font-medium">
          Details <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
        </div>
      </div>
    </div>
  );
};
