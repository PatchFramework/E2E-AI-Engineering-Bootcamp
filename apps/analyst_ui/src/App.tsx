import React, { useState, useCallback, useMemo } from 'react';
import { Header } from './views/components/Header';
import { DashboardView } from './views/DashboardView';
import { UploadView } from './views/UploadView';
import { CopilotPanel } from './views/components/CopilotPanel';
import { DocumentPreviewPanel } from './views/components/DocumentPreviewPanel';
import { useCompanyController } from './controllers/useCompanyController';
import { useMetricsController } from './controllers/useMetricsController';
import { useFactsController } from './controllers/useFactsController';
import { usePipelineController } from './controllers/usePipelineController';
import { useCopilotController } from './controllers/useCopilotController';
import { CopilotContextSnapshot, CopilotCitation } from './models/copilot';
import { X } from 'lucide-react';

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

  // State for document citation preview modal
  const [previewCitation, setPreviewCitation] = useState<CopilotCitation | null>(null);

  // Build real-time context snapshot for the Copilot
  const contextSnapshot: CopilotContextSnapshot = useMemo(() => {
    return {
      currentView: activeNav,
      companyId: companyController.selectedCompanyId,
      companyName: companyController.companySummary.name,
      activeMetric: metricsController.selectedMetric,
      activeFacts: factsController.facts,
      activeDocuments: previewCitation
        ? [
            {
              documentId: previewCitation.documentId,
              filename: previewCitation.filename,
              pageNumber: previewCitation.pageNumber,
              displayedPage: previewCitation.displayedPage,
              snippet: previewCitation.snippet,
              boundingBox: previewCitation.boundingBox,
            },
          ]
        : undefined,
    };
  }, [
    activeNav,
    companyController.selectedCompanyId,
    companyController.companySummary.name,
    metricsController.selectedMetric,
    factsController.facts,
    previewCitation,
  ]);

  // Copilot Controller handles streaming, sessions, and dynamic sizing
  const copilotController = useCopilotController(contextSnapshot, citation => {
    setPreviewCitation(citation);
  });

  return (
    <div className="h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 flex flex-col font-sans antialiased selection:bg-brand-500 selection:text-white">
      {/* Top Navigation Header */}
      <Header
        activeNav={activeNav}
        setActiveNav={setActiveNav}
        companies={companyController.companies}
        selectedCompanyId={companyController.selectedCompanyId}
        onSelectCompany={handleSelectCompany}
        activeJobCount={pipelineController.activeJobCount}
      />

      {/* Main Workspace Area (Canvas + Omnipresent Copilot) */}
      <div className="flex-1 flex overflow-hidden relative min-h-0 min-w-0">
        {/* Active Navigation Views */}
        <div className="flex-1 flex overflow-hidden relative min-h-0 min-w-0">
          {activeNav === 'dashboard' && (
            <DashboardView
              companySummary={companyController.companySummary}
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

          {/* Grounded Citation Document Preview Embedded Panel */}
          {previewCitation && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/90 backdrop-blur-md p-3 animate-fadeIn">
              <div className="w-full h-full rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl flex flex-col overflow-hidden">
                <div className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-slate-950">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-100">
                      Grounded Citation Evidence: {previewCitation.filename} ({previewCitation.displayedPage})
                    </span>
                    {previewCitation.section && (
                      <span className="text-xs text-slate-400">· {previewCitation.section}</span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setPreviewCitation(null)}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
                    title="Close Preview"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1 overflow-hidden">
                  <DocumentPreviewPanel
                    documentId={previewCitation.documentId}
                    documentName={previewCitation.filename}
                    pageNumber={previewCitation.pageNumber}
                    displayedPageNumber={previewCitation.displayedPage}
                    section={previewCitation.section}
                    boundingBox={previewCitation.boundingBox}
                    snippet={previewCitation.snippet}
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Omnipresent Resizable Underwriting Copilot Drawer */}
        <CopilotPanel
          isOpen={copilotController.isOpen}
          onToggleOpen={copilotController.toggleOpen}
          width={copilotController.width}
          onWidthChange={copilotController.setWidth}
          contextSnapshot={contextSnapshot}
          messages={copilotController.messages}
          isStreaming={copilotController.isStreaming}
          currentReasoningStatus={copilotController.currentReasoningStatus}
          turnCount={copilotController.turnCount}
          maxTurns={copilotController.maxTurns}
          isTurnLimitReached={copilotController.isTurnLimitReached}
          onSendMessage={copilotController.sendMessage}
          onAbortStream={copilotController.abortStream}
          onSubmitFeedback={copilotController.submitFeedback}
          onNewSession={copilotController.createNewSession}
          sessions={copilotController.sessions}
          activeSessionId={copilotController.activeSessionId}
          onSwitchSession={copilotController.switchSession}
          onOpenCitation={citation => setPreviewCitation(citation)}
        />
      </div>
    </div>
  );
}
