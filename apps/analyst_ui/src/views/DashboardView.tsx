import React from 'react';
import { CompanySummary } from '../models/company';
import { MetricItem, KPICategory, MetricLineage } from '../models/metric';
import { FinancialFact } from '../models/fact';
import { CorrectionFeedbackState } from '../controllers/useFactsController';
import { CompanyBanner } from './components/CompanyBanner';
import { KPICategoryTabs } from './components/KPICategoryTabs';
import { KPIGrid } from './components/KPIGrid';
import { KPIDetailDrawer } from './components/KPIDetailDrawer';
import { DataCorrectionModal } from './components/DataCorrectionModal';

interface DashboardViewProps {
  companySummary: CompanySummary;
  metrics: MetricItem[];
  filteredMetrics: MetricItem[];
  activeTab: KPICategory;
  onSelectTab: (tab: KPICategory) => void;
  loadingMetrics: boolean;
  selectedMetric: MetricItem | null;
  onSelectMetric: (metric: MetricItem | null) => void;
  lineage: MetricLineage | null;
  loadingLineage: boolean;
  selectedFactForCorrection: FinancialFact | null;
  onOpenCorrection: (fact: FinancialFact | null) => void;
  correctionFeedback: CorrectionFeedbackState | null;
  onClearFeedback: () => void;
  onVerifyFact: (factId: number) => Promise<any>;
  onCorrectFact: (factId: number, value: number, reason: string) => Promise<any>;
  isSubmittingCorrection: boolean;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  companySummary,
  metrics,
  filteredMetrics,
  activeTab,
  onSelectTab,
  loadingMetrics,
  selectedMetric,
  onSelectMetric,
  lineage,
  loadingLineage,
  selectedFactForCorrection,
  onOpenCorrection,
  correctionFeedback,
  onClearFeedback,
  onVerifyFact,
  onCorrectFact,
  isSubmittingCorrection,
}) => {
  return (
    <div className="flex-1 flex overflow-hidden relative min-h-0 min-w-0">
      {/* Main Analysis Canvas */}
      <main className="flex-1 p-6 overflow-y-auto space-y-6 min-h-0 min-w-0">
        {/* Company Header Banner */}
        <CompanyBanner summary={companySummary} />

        {/* Category Tabs */}
        <KPICategoryTabs activeTab={activeTab} onSelectTab={onSelectTab} metrics={metrics} />

        {/* KPI Grid Cards */}
        <KPIGrid
          metrics={filteredMetrics}
          loading={loadingMetrics}
          onSelectMetric={onSelectMetric}
        />

        {/* KPI Detail Drawer */}
        <KPIDetailDrawer
          metric={selectedMetric}
          lineage={lineage}
          loadingLineage={loadingLineage}
          onClose={() => onSelectMetric(null)}
          onOpenCorrection={fact => onOpenCorrection(fact)}
          onVerifyFact={onVerifyFact}
        />

        {/* Data Correction Modal */}
        <DataCorrectionModal
          fact={selectedFactForCorrection}
          feedback={correctionFeedback}
          isSubmitting={isSubmittingCorrection}
          onClose={() => onOpenCorrection(null)}
          onClearFeedback={onClearFeedback}
          onVerify={onVerifyFact}
          onCorrect={onCorrectFact}
        />
      </main>
    </div>
  );
};

