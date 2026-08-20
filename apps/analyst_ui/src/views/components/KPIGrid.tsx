import React from 'react';
import { MetricItem } from '../../models/metric';
import { KPICard } from './KPICard';
import { Layers } from 'lucide-react';


interface KPIGridProps {
  metrics: MetricItem[];
  loading: boolean;
  onSelectMetric: (metric: MetricItem) => void;
}

export const KPIGrid: React.FC<KPIGridProps> = ({ metrics, loading, onSelectMetric }) => {
  if (loading && metrics.length === 0) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div
            key={i}
            className="bg-slate-900/40 border border-slate-800 rounded-2xl p-5 h-48 animate-pulse flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="h-3 bg-slate-800 rounded w-24" />
              <div className="h-5 bg-slate-800 rounded w-36" />
              <div className="h-8 bg-slate-800 rounded w-28 mt-4" />
            </div>
            <div className="h-4 bg-slate-800 rounded w-full border-t border-slate-800/80 pt-3" />
          </div>
        ))}
      </div>
    );
  }

  if (metrics.length === 0) {
    return (
      <div className="bg-slate-900/30 border border-slate-800/80 rounded-2xl p-12 text-center flex flex-col items-center justify-center gap-3">
        <div className="p-3 bg-slate-800/50 rounded-xl text-slate-400">
          <Layers className="w-8 h-8" />
        </div>
        <h3 className="text-base font-bold text-slate-200">No KPIs in this category</h3>
        <p className="text-xs text-slate-400 max-w-sm">
          Filing facts have not yet been extracted for this category. Upload a filing PDF to trigger extraction.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {metrics.map(metric => (
        <KPICard key={metric.metric_name} metric={metric} onClick={() => onSelectMetric(metric)} />
      ))}
    </div>
  );
};
