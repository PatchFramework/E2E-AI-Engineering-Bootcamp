import React, { useState, useEffect, useMemo } from 'react';
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
  Eye,
  BarChart3,
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
  MetricInputFactLineage,
  MetricCitedChunk,
  formatMetricValue,
  formatYoYChange,
  getMetricRiskInterpretation,
} from '../../models/metric';

import { FinancialFact } from '../../models/fact';
import {
  DocumentPreviewPanel,
  DocumentPreviewDocInfo,
} from './DocumentPreviewPanel';

interface ActiveGroundingState {
  documentId: number | null;
  documentName: string | null;
  s3Path?: string | null;
  pageNumber: number;
  displayedPageNumber?: string | null;
  sectionPath?: string | null;
  section?: string | null;
  boundingBox?: any;
  snippet?: string | null;
  concept?: string | null;
  sourceKey?: string; // identifier for matching active card
}

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
  const [activeGrounding, setActiveGrounding] = useState<ActiveGroundingState | null>(null);
  const [mobileActiveTab, setMobileActiveTab] = useState<'preview' | 'details'>('details');
  const [verifiedFactIds, setVerifiedFactIds] = useState<Set<number>>(new Set());

  // Aggregate available documents from lineage
  const availableDocuments = useMemo<DocumentPreviewDocInfo[]>(() => {
    if (!lineage) return [];
    const docMap = new Map<number, DocumentPreviewDocInfo>();

    // From input facts
    for (const inf of lineage.input_facts) {
      const doc = inf.document;
      const loc = inf.source_location;
      if (doc && doc.document_id) {
        if (!docMap.has(doc.document_id)) {
          docMap.set(doc.document_id, {
            documentId: doc.document_id,
            filename: doc.filename || `Document #${doc.document_id}`,
            fiscalYear: doc.fiscal_year,
            fiscalPeriod: doc.fiscal_period,
            pageNumbers: [],
          });
        }
        if (loc?.page_number && !docMap.get(doc.document_id)!.pageNumbers.includes(loc.page_number)) {
          docMap.get(doc.document_id)!.pageNumbers.push(loc.page_number);
        }
      }
    }

    // From cited chunks
    for (const chunk of lineage.cited_chunks) {
      if (chunk.document_id) {
        if (!docMap.has(chunk.document_id)) {
          docMap.set(chunk.document_id, {
            documentId: chunk.document_id,
            filename: `Document #${chunk.document_id}`,
            pageNumbers: [],
          });
        }
        if (chunk.page_number && !docMap.get(chunk.document_id)!.pageNumbers.includes(chunk.page_number)) {
          docMap.get(chunk.document_id)!.pageNumbers.push(chunk.page_number);
        }
      }
    }

    return Array.from(docMap.values());
  }, [lineage]);

  // Set default active grounding when lineage loads or metric changes
  useEffect(() => {
    if (!lineage) {
      setActiveGrounding(null);
      return;
    }

    // First try: first input fact with document & page
    const firstFactWithDoc = lineage.input_facts.find(
      f => f.document?.document_id && f.source_location?.page_number
    );

    if (firstFactWithDoc) {
      const doc = firstFactWithDoc.document!;
      const loc = firstFactWithDoc.source_location!;
      setActiveGrounding({
        documentId: doc.document_id!,
        documentName: doc.filename || null,
        s3Path: doc.s3_path,
        pageNumber: loc.page_number!,
        displayedPageNumber: loc.displayed_page_number,
        sectionPath: loc.section_path,
        section: loc.section,
        boundingBox: loc.bounding_box,
        snippet: loc.text_snippet,
        concept: firstFactWithDoc.concept,
        sourceKey: `fact-${firstFactWithDoc.fact_id || firstFactWithDoc.concept}`,
      });
      return;
    }

    // Second try: first cited chunk
    const firstChunk = lineage.cited_chunks.find(c => c.document_id && c.page_number);
    if (firstChunk) {
      setActiveGrounding({
        documentId: firstChunk.document_id,
        documentName: `Document #${firstChunk.document_id}`,
        pageNumber: firstChunk.page_number,
        displayedPageNumber: firstChunk.displayed_page_number,
        sectionPath: firstChunk.section_path,
        section: firstChunk.section_path?.split('>').pop()?.trim(),
        boundingBox: firstChunk.chunk_metadata?.bbox,
        snippet: firstChunk.text_content,
        concept: 'RAG Citation',
        sourceKey: `chunk-${firstChunk.chunk_id}`,
      });
      return;
    }

    // Fallback if document exists without location
    const firstDoc = availableDocuments[0];
    if (firstDoc) {
      setActiveGrounding({
        documentId: firstDoc.documentId,
        documentName: firstDoc.filename,
        pageNumber: firstDoc.pageNumbers[0] || 1,
        sourceKey: `doc-${firstDoc.documentId}`,
      });
    } else {
      setActiveGrounding(null);
    }
  }, [lineage, availableDocuments]);


  // Prevent background body scroll when the detail modal is open
  useEffect(() => {
    if (!metric) return;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [metric]);


  if (!metric) return null;

  const formattedValue = formatMetricValue(metric.current_value, metric.unit);
  const yoyInfo = formatYoYChange(metric.yoy_change, metric.yoy_change_pct, metric.unit);
  const riskInterpretation = getMetricRiskInterpretation(
    metric.metric_name,
    metric.current_value,
    metric.trend
  );

  // Deduplicate and sort history by fiscal year
  const uniqueHistory = (() => {
    const map = new Map<number, (typeof metric.history)[0]>();
    for (const h of metric.history) {
      if (!map.has(h.fiscal_year) || (h.value !== null && map.get(h.fiscal_year)?.value === null)) {
        map.set(h.fiscal_year, h);
      }
    }
    return Array.from(map.values()).sort((a, b) => a.fiscal_year - b.fiscal_year);
  })();

  // Historical chart data
  const chartData = uniqueHistory.map(h => ({
    year: `${h.fiscal_year}`,
    val: h.value !== null ? Number(h.value.toFixed(2)) : null,
  }));

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

  const handleSelectGroundingFromFact = (inf: MetricInputFactLineage) => {
    if (inf.document?.document_id) {
      setActiveGrounding({
        documentId: inf.document.document_id,
        documentName: inf.document.filename || null,
        s3Path: inf.document.s3_path,
        pageNumber: inf.source_location?.page_number || 1,
        displayedPageNumber: inf.source_location?.displayed_page_number,
        sectionPath: inf.source_location?.section_path,
        section: inf.source_location?.section,
        boundingBox: inf.source_location?.bounding_box,
        snippet: inf.source_location?.text_snippet,
        concept: inf.concept,
        sourceKey: `fact-${inf.fact_id || inf.concept}`,
      });
      setMobileActiveTab('preview');
    }
  };

  const handleSelectGroundingFromChunk = (chunk: MetricCitedChunk) => {
    setActiveGrounding({
      documentId: chunk.document_id,
      documentName: `Document #${chunk.document_id}`,
      pageNumber: chunk.page_number,
      displayedPageNumber: chunk.displayed_page_number,
      sectionPath: chunk.section_path,
      section: chunk.section_path?.split('>').pop()?.trim(),
      boundingBox: chunk.chunk_metadata?.bbox,
      snippet: chunk.text_content,
      concept: 'RAG Citation',
      sourceKey: `chunk-${chunk.chunk_id}`,
    });
    setMobileActiveTab('preview');
  };

  return (
    <div
      onWheel={e => e.stopPropagation()}
      onTouchMove={e => e.stopPropagation()}
      className="fixed inset-0 z-50 overflow-hidden overscroll-contain bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-0 lg:p-4 transition-opacity animate-in fade-in duration-200"
    >
      {/* Outer Modal Container */}
      <div className="w-full h-full max-w-[1720px] bg-slate-900 border-0 lg:border border-slate-800 lg:rounded-2xl overflow-hidden flex flex-col shadow-2xl overscroll-contain">

        {/* Mobile View Toggle Bar (visible only on small screens) */}
        <div className="flex lg:hidden bg-slate-900 border-b border-slate-800 px-4 py-2 justify-between items-center">
          <div className="flex gap-2">
            <button
              onClick={() => setMobileActiveTab('preview')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 ${
                mobileActiveTab === 'preview'
                  ? 'bg-brand-600 text-white'
                  : 'bg-slate-800 text-slate-300'
              }`}
            >
              <Eye className="w-3.5 h-3.5" /> Source Preview
            </button>
            <button
              onClick={() => setMobileActiveTab('details')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 ${
                mobileActiveTab === 'details'
                  ? 'bg-brand-600 text-white'
                  : 'bg-slate-800 text-slate-300'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" /> Metric Details
            </button>
          </div>

          <button
            onClick={onClose}
            aria-label="Close"
            className="text-slate-400 hover:text-white p-1.5 rounded-lg bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Split Workbench Body */}
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden relative">
          {/* Left Pane: S3 RAG Grounding Document Live Preview */}
          <div
            className={`flex-1 h-full flex flex-col ${
              mobileActiveTab === 'preview' ? 'flex' : 'hidden lg:flex'
            }`}
          >
            <DocumentPreviewPanel
              documentId={activeGrounding?.documentId ?? null}
              documentName={activeGrounding?.documentName ?? null}
              s3Path={activeGrounding?.s3Path}
              pageNumber={activeGrounding?.pageNumber ?? 1}
              displayedPageNumber={activeGrounding?.displayedPageNumber}
              sectionPath={activeGrounding?.sectionPath}
              section={activeGrounding?.section}
              boundingBox={activeGrounding?.boundingBox}
              snippet={activeGrounding?.snippet}
              concept={activeGrounding?.concept}
              availableDocuments={availableDocuments}
              onSelectDocument={(docId, pageNum) => {
                const doc = availableDocuments.find(d => d.documentId === docId);
                setActiveGrounding(prev => ({
                  documentId: docId,
                  documentName: doc?.filename || null,
                  pageNumber: pageNum,
                  displayedPageNumber: String(pageNum),
                  concept: prev?.concept,
                  sourceKey: `doc-${docId}`,
                }));
              }}
              onPageChange={newPage => {
                setActiveGrounding(prev => (prev ? { ...prev, pageNumber: newPage } : null));
              }}
            />
          </div>

          {/* Right Pane: Comprehensive KPI Analytics & Interactive Provenance Drawer */}
          <div
            className={`w-full lg:w-[540px] xl:w-[600px] bg-slate-900 border-t lg:border-t-0 lg:border-l border-slate-800 h-full overflow-y-auto flex flex-col shadow-2xl flex-shrink-0 ${
              mobileActiveTab === 'details' ? 'flex' : 'hidden lg:flex'
            }`}
          >
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-800 sticky top-0 bg-slate-900/95 backdrop-blur-md z-10 flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-brand-400 bg-brand-950/60 border border-brand-800/50 px-2.5 py-0.5 rounded-full">
                    {metric.category} KPI
                  </span>
                  <span className="text-xs text-slate-400 font-medium">
                    FY{metric.fiscal_year} {metric.fiscal_period}
                  </span>
                </div>
                <h2 className="text-2xl font-extrabold text-white tracking-tight mt-1">
                  {metric.display_name}
                </h2>
              </div>

              <button
                onClick={onClose}
                aria-label="Close"
                className="text-slate-400 hover:text-white p-2 rounded-lg bg-slate-800/60 hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body Content */}
            <div className="p-5 space-y-5 flex-1">
              {/* Primary Metric Snapshot */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                  <div className="text-xs text-slate-400 font-medium">
                    Current Period Value ({metric.fiscal_year})
                  </div>
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

                <div className="flex flex-col gap-1.5 items-start sm:items-end">
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

                {chartData.length > 1 ? (
                  <div className="h-40 w-full pt-2">
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
                  <div className="text-xs text-slate-500 py-4 text-center">Single period available</div>
                )}

                <div className="grid grid-cols-5 gap-2 border-t border-slate-800/80 pt-3">
                  {uniqueHistory.map(h => (
                    <div
                      key={h.fiscal_year}
                      className="text-center p-2 rounded-lg bg-slate-900/60 border border-slate-800/50"
                    >
                      <div className="text-[10px] text-slate-400">{h.fiscal_year}</div>
                      <div className="text-xs font-bold text-slate-100 mt-0.5">
                        {formatMetricValue(h.value, metric.unit)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Underwriting Risk Interpretation */}
              <div className="bg-slate-950/40 border border-slate-800/80 rounded-2xl p-4 space-y-2">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-amber-400" /> Credit Risk Interpretation
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed">{riskInterpretation}</p>
              </div>

              {/* Mathematical Formula Breakdown */}
              {metric.formula_expression && (
                <div className="bg-slate-950/40 border border-slate-800/80 rounded-2xl p-4 space-y-2">
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
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                    <Layers className="w-4 h-4 text-brand-400" /> Input Financial Facts & Citations
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
                      const isSelected =
                        activeGrounding?.sourceKey === `fact-${inf.fact_id || inf.concept}` ||
                        (activeGrounding?.concept === inf.concept &&
                          activeGrounding?.pageNumber === inf.source_location?.page_number);

                      return (
                        <div
                          key={idx}
                          role="button"
                          tabIndex={0}
                          onClick={() => handleSelectGroundingFromFact(inf)}
                          className={`bg-slate-950/60 border rounded-2xl p-4 transition-all cursor-pointer relative group ${
                            isSelected
                              ? 'border-brand-500 ring-2 ring-brand-500/40 bg-slate-900 shadow-lg'
                              : 'border-slate-800/80 hover:border-slate-700 hover:bg-slate-900/50'
                          }`}
                        >
                          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-bold text-white group-hover:text-brand-300 transition">
                                  {inf.concept}
                                </span>
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

                              <div className="text-lg font-black text-slate-100 mt-1">
                                {factValueStr}
                              </div>
                            </div>

                            {/* Quick action buttons for analyst */}
                            <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                              {!isVerified && inf.fact_id && (
                                <button
                                  onClick={() => handleVerifyFact(inf.fact_id!)}
                                  className="text-xs font-semibold bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-400 border border-emerald-800/60 px-2.5 py-1.5 rounded-lg transition flex items-center gap-1.5"
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
                                  className="text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-2.5 py-1.5 rounded-lg transition flex items-center gap-1.5"
                                >
                                  <Edit3 className="w-3.5 h-3.5" /> Correct
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Source Citation & Evidence Snippet */}
                          {inf.source_location && (
                            <div className="mt-3 pt-3 border-t border-slate-800/70 text-xs text-slate-400 flex items-start gap-2">
                              <BookOpen className="w-4 h-4 text-brand-400 flex-shrink-0 mt-0.5" />
                              <div className="flex-1 min-w-0">
                                <div className="font-semibold text-slate-300 flex items-center justify-between">
                                  <span>
                                    {inf.document?.filename || 'Annual Report'}{' '}
                                    {inf.source_location.page_number && `· Page ${inf.source_location.page_number}`}
                                    {inf.source_location.section && ` · ${inf.source_location.section}`}
                                  </span>
                                  <span className="text-[10px] text-brand-400 font-bold group-hover:underline">
                                    View in PDF →
                                  </span>
                                </div>
                                {inf.source_location.text_snippet && (
                                  <p className="italic text-slate-400 mt-1 text-[11px] bg-slate-900/60 p-2 rounded-lg border border-slate-800/60 line-clamp-2">
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
                    {lineage.cited_chunks.slice(0, 3).map(chunk => {
                      const isSelected = activeGrounding?.sourceKey === `chunk-${chunk.chunk_id}`;
                      return (
                        <div
                          key={chunk.chunk_id}
                          role="button"
                          tabIndex={0}
                          onClick={() => handleSelectGroundingFromChunk(chunk)}
                          className={`bg-slate-950/80 border rounded-xl p-3.5 text-xs text-slate-300 cursor-pointer transition-all ${
                            isSelected
                              ? 'border-indigo-500 ring-2 ring-indigo-500/40 bg-slate-900'
                              : 'border-slate-800/80 hover:border-slate-700 hover:bg-slate-900/50'
                          }`}
                        >
                          <div className="flex items-center justify-between text-[10px] font-bold text-indigo-400 mb-1">
                            <span>
                              Page {chunk.page_number} {chunk.section_path && `· ${chunk.section_path}`}
                            </span>
                            <span className="text-indigo-400 underline">Show in PDF</span>
                          </div>
                          <p className="line-clamp-2 text-slate-400">{chunk.text_content}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
