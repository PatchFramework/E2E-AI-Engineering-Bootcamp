import React from 'react';
import { KPICategory, KPI_CATEGORIES, MetricItem } from '../../models/metric';

interface KPICategoryTabsProps {
  activeTab: KPICategory;
  onSelectTab: (tab: KPICategory) => void;
  metrics: MetricItem[];
}

export const KPICategoryTabs: React.FC<KPICategoryTabsProps> = ({ activeTab, onSelectTab, metrics }) => {
  const getCount = (cat: KPICategory) => {
    if (cat === 'Overview') return metrics.length;
    return metrics.filter(m => m.category === cat).length;
  };

  return (
    <div className="border-b border-slate-800 flex gap-2 overflow-x-auto py-1 scrollbar-thin">
      {KPI_CATEGORIES.map(tab => {
        const count = getCount(tab);
        const isActive = activeTab === tab;

        return (
          <button
            key={tab}
            onClick={() => onSelectTab(tab)}
            className={`px-4 py-2.5 rounded-t-lg font-semibold text-xs tracking-wide transition-all whitespace-nowrap border-b-2 -mb-1 flex items-center gap-2 ${
              isActive
                ? 'border-brand-500 text-brand-400 bg-brand-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
            }`}
          >
            <span>{tab}</span>
            <span
              className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold leading-tight ${
                isActive ? 'bg-brand-900/80 text-brand-300' : 'bg-slate-800 text-slate-400'
              }`}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
};
