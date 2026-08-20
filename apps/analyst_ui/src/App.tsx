import React, { useState, useCallback } from 'react';
import { Header } from './views/components/Header';
import { DashboardView } from './views/DashboardView';
import { UploadView } from './views/UploadView';
import { useCompanyController } from './controllers/useCompanyController';
import { useMetricsController } from './controllers/useMetricsController';
import { useFactsController } from './controllers/useFactsController';
import { usePipelineController } from './controllers/usePipelineController';

export default function App() {
  const [activeNav, setActiveNav] = useState<'dashboard' | 'upload'>('dashboard');

  // Metric Controller handles derived metrics for active company
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);

  const metricsController = useMetricsController(selectedCompanyId);

  // When facts are updated/corrected, refresh metrics and facts
  const handleDataUpdated = useCallback(() => {
    metricsController.refreshMetrics();
  }, [metricsController]);


  const factsController = useFactsController(selectedCompanyId, handleDataUpdated);

  // Company Controller computes rating and manages company list
  const companyController = useCompanyController(metricsController.metrics, factsController.facts);

  // Sync selected company ID from companyController
  React.useEffect(() => {
    if (companyController.selectedCompanyId && companyController.selectedCompanyId !== selectedCompanyId) {
      setSelectedCompanyId(companyController.selectedCompanyId);
    }
  }, [companyController.selectedCompanyId, selectedCompanyId]);

  const handleSelectCompany = (id: number) => {
    companyController.setSelectedCompanyId(id);
    setSelectedCompanyId(id);
  };

  // Pipeline Controller handles filing uploads & Airflow task polling
  const pipelineController = usePipelineController(() => {
    // When a pipeline job completes, refresh companies, facts and metrics
    companyController.refreshCompanies();
    factsController.refreshFacts();
    metricsController.refreshMetrics();
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans antialiased selection:bg-brand-500 selection:text-white">
      {/* Top Navigation Header */}
      <Header
        activeNav={activeNav}
        setActiveNav={setActiveNav}
        companies={companyController.companies}
        selectedCompanyId={companyController.selectedCompanyId}
        onSelectCompany={handleSelectCompany}
        activeJobCount={pipelineController.activeJobCount}
      />

      {/* Main Views */}
      {activeNav === 'dashboard' && (
        <DashboardView
          companySummary={companyController.companySummary}
          activeCompanyId={companyController.selectedCompanyId}
          metrics={metricsController.metrics}
          filteredMetrics={metricsController.filteredMetrics}
          activeTab={metricsController.activeTab}
          onSelectTab={metricsController.setActiveTab}
          loadingMetrics={metricsController.loading}
          selectedMetric={metricsController.selectedMetric}
          onSelectMetric={metricsController.setSelectedMetric}
          lineage={metricsController.lineage}
          loadingLineage={metricsController.lineageLoading}
          selectedFactForCorrection={factsController.selectedFactForCorrection}
          onOpenCorrection={factsController.setSelectedFactForCorrection}
          correctionFeedback={factsController.correctionFeedback}
          onClearFeedback={factsController.clearFeedback}
          onVerifyFact={factsController.verifyFact}
          onCorrectFact={factsController.correctFact}
          isSubmittingCorrection={factsController.isSubmitting}
        />
      )}

      {activeNav === 'upload' && (
        <UploadView
          jobs={pipelineController.jobs}
          onUpload={pipelineController.handleUpload}
          onRemoveJob={pipelineController.removeJob}
        />
      )}
    </div>
  );
}
