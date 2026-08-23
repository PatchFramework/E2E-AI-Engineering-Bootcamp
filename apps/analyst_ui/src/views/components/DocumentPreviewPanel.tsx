import React, { useState, useEffect, useRef } from 'react';
import {
  FileText,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  Loader2,
  Sparkles,
  Layers,
  AlertCircle,
  Eye,
} from 'lucide-react';
import { normalizeBoundingBox, PageDimensions } from '../../utils/bboxUtils';
import { getApiBaseUrl } from '../../controllers/apiClient';

export interface DocumentPreviewDocInfo {
  documentId: number;
  filename: string;
  fiscalYear?: number | null;
  fiscalPeriod?: string | null;
  pageNumbers: number[];
}

export interface DocumentPreviewPanelProps {
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
  availableDocuments?: DocumentPreviewDocInfo[];
  onSelectDocument?: (docId: number, pageNumber: number) => void;
  onPageChange?: (newPage: number) => void;
}

export const DocumentPreviewPanel: React.FC<DocumentPreviewPanelProps> = ({
  documentId,
  documentName,
  s3Path,
  pageNumber,
  displayedPageNumber,
  sectionPath,
  section,
  boundingBox,
  snippet,
  concept,
  availableDocuments = [],
  onSelectDocument,
  onPageChange,
}) => {
  const [zoom, setZoom] = useState<number>(100);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [pageDimensions, setPageDimensions] = useState<PageDimensions | undefined>(undefined);
  const [jumpPageInput, setJumpPageInput] = useState<string>(String(pageNumber || 1));

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    setJumpPageInput(String(pageNumber || 1));
  }, [pageNumber]);

  const apiBase = getApiBaseUrl();
  const [currentSrc, setCurrentSrc] = useState<string | null>(null);
  const [attemptIndex, setAttemptIndex] = useState<number>(0);

  const availableDocKey = (availableDocuments || []).map(d => `${d.documentId}:${d.pageNumbers?.join('-')}`).join(',');

  // Generate ordered list of fallback URLs for the page image:
  // 1. Primary: ${apiBase}/documents/${documentId}/pages/${pageNumber}
  // 2. Direct MinIO by documentId: http://localhost:9000/filings/pages/${documentId}/page_${pageNumber}.png
  // 3. Fallback to pageNumber folder in MinIO: http://localhost:9000/filings/pages/${pageNumber}/page_${pageNumber}.png
  // 4. Available documents fallback: ${apiBase}/documents/${doc.documentId}/pages/${pageNumber}
  const candidateUrls = React.useMemo(() => {
    if (!pageNumber) return [];
    const urls: string[] = [];
    if (documentId) {
      urls.push(`${apiBase}/documents/${documentId}/pages/${pageNumber}`);
      urls.push(`http://localhost:9000/filings/pages/${documentId}/page_${pageNumber}.png`);
    }
    // Also try page number folder directly in MinIO (e.g., filings/pages/3/page_3.png)
    urls.push(`http://localhost:9000/filings/pages/${pageNumber}/page_${pageNumber}.png`);
    
    if (availableDocuments && availableDocuments.length > 0) {
      for (const d of availableDocuments) {
        if (d.documentId && d.documentId !== documentId) {
          urls.push(`${apiBase}/documents/${d.documentId}/pages/${pageNumber}`);
          urls.push(`http://localhost:9000/filings/pages/${d.documentId}/page_${pageNumber}.png`);
        }
      }
    }
    return Array.from(new Set(urls));
  }, [apiBase, documentId, pageNumber, availableDocKey]);

  const fullPdfUrl = documentId
    ? `${apiBase}/documents/${documentId}/file`
    : (availableDocuments && availableDocuments.length > 0
        ? `${apiBase}/documents/${availableDocuments[0].documentId}/file`
        : `${apiBase}/documents/1/file`);

  // Track image loading on actual document or page changes
  useEffect(() => {
    setAttemptIndex(0);
    if (candidateUrls.length > 0) {
      setCurrentSrc(candidateUrls[0]);
      setLoading(true);
      setError(null);
    } else {
      setCurrentSrc(null);
      setLoading(false);
    }
  }, [documentId, pageNumber, availableDocKey]);

  // Ensure loading overlay is dismissed immediately whenever the image element is loaded/complete
  useEffect(() => {
    if (imgRef.current && imgRef.current.complete && imgRef.current.naturalWidth > 0) {
      setLoading(false);
      setError(null);
      setPageDimensions({
        naturalWidth: imgRef.current.naturalWidth,
        naturalHeight: imgRef.current.naturalHeight,
      });
    }
  });

  const handleImageLoaded = (e: React.SyntheticEvent<HTMLImageElement>) => {
    setLoading(false);
    setError(null);
    const img = e.currentTarget;
    if (img.naturalWidth && img.naturalHeight) {
      setPageDimensions({
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
      });
    }
  };

  const handleImageError = () => {
    const nextIdx = attemptIndex + 1;
    if (nextIdx < candidateUrls.length) {
      setAttemptIndex(nextIdx);
      setCurrentSrc(candidateUrls[nextIdx]);
    } else {
      setLoading(false);
      setError('Could not load filing page from storage.');
    }
  };

  // Calculate normalized bounding box
  const normalizedBBox = React.useMemo(() => {
    if (!boundingBox) return null;
    return normalizeBoundingBox(boundingBox, pageDimensions);
  }, [boundingBox, pageDimensions]);

  // Smoothly scroll to the highlighted bounding box when it renders/updates
  useEffect(() => {
    if (!highlightRef.current) return;
    const timer = setTimeout(() => {
      highlightRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
        inline: 'center',
      });
    }, 150);
    return () => clearTimeout(timer);
  }, [documentId, pageNumber, boundingBox, normalizedBBox]);


  const handleZoomIn = () => setZoom(prev => Math.min(250, prev + 25));
  const handleZoomOut = () => setZoom(prev => Math.max(50, prev - 25));
  const handleResetZoom = () => setZoom(100);
  const handleFitWidth = () => setZoom(125);

  const handlePrevPage = () => {
    if (pageNumber > 1 && onPageChange) {
      onPageChange(pageNumber - 1);
    }
  };

  const handleNextPage = () => {
    if (onPageChange) {
      onPageChange(pageNumber + 1);
    }
  };

  const handleJumpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseInt(jumpPageInput, 10);
    if (!isNaN(parsed) && parsed >= 1 && onPageChange) {
      onPageChange(parsed);
    }
  };

  // Format section breadcrumb segments
  const breadcrumbSegments = React.useMemo(() => {
    if (sectionPath && sectionPath.trim()) {
      return sectionPath.split('>').map(s => s.trim()).filter(Boolean);
    }
    if (section && section.trim()) {
      return [section.trim()];
    }
    return [];
  }, [sectionPath, section]);

  if (!documentId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-950/60 border-r border-slate-800">
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 text-slate-500 mb-3">
          <FileText className="w-10 h-10 opacity-50" />
        </div>
        <h4 className="text-base font-bold text-slate-300">No Document Linked</h4>
        <p className="text-xs text-slate-500 mt-1 max-w-xs">
          Select an input fact or cited RAG grounding in the right panel to view the source filing in live preview.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950/80 border-r border-slate-800 overflow-hidden select-none">
      {/* Top Header: Breadcrumbs & S3 Origin */}
      <div className="px-5 py-3 border-b border-slate-800/80 bg-slate-900/90 backdrop-blur-md flex flex-col gap-2">
        <div className="flex items-center justify-between gap-3">
          {/* Breadcrumbs */}
          <div className="flex items-center gap-1.5 min-w-0 text-xs text-slate-400">
            <span className="font-semibold text-brand-400 flex items-center gap-1 flex-shrink-0">
              <Eye className="w-3.5 h-3.5" /> S3 Source Preview
            </span>
            {breadcrumbSegments.length > 0 && <span className="text-slate-600">/</span>}
            <div className="flex items-center gap-1.5 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">
              {breadcrumbSegments.map((segment, idx) => (
                <React.Fragment key={idx}>
                  <span
                    className={`truncate ${
                      idx === breadcrumbSegments.length - 1
                        ? 'font-bold text-slate-100'
                        : 'text-slate-400'
                    }`}
                  >
                    {segment}
                  </span>
                  {idx < breadcrumbSegments.length - 1 && (
                    <span className="text-slate-600">›</span>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Full Original PDF Link from S3 */}
          {fullPdfUrl && (
            <a
              href={fullPdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-brand-300 bg-brand-950/60 hover:bg-brand-900/60 border border-brand-800/60 rounded-lg transition-colors flex-shrink-0 shadow-sm group"
              title={s3Path ? `Open full original document from S3 (${s3Path})` : 'Open or download the full original document from S3'}

            >
              <FileText className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
              <span>Full PDF</span>
              <ExternalLink className="w-3 h-3 opacity-70 group-hover:opacity-100" />
            </a>
          )}
        </div>

        {/* Multi-Document Selector Tabs if multiple documents cited */}
        {availableDocuments.length > 1 && (
          <div className="flex items-center gap-2 pt-1 overflow-x-auto pb-0.5 scrollbar-thin">
            <span className="text-[11px] text-slate-500 font-medium flex items-center gap-1 flex-shrink-0">
              <Layers className="w-3 h-3 text-slate-400" /> Filings:
            </span>
            {availableDocuments.map(doc => {
              const isActive = doc.documentId === documentId;
              return (
                <button
                  key={doc.documentId}
                  onClick={() => {
                    if (onSelectDocument) {
                      onSelectDocument(doc.documentId, doc.pageNumbers[0] || 1);
                    }
                  }}
                  className={`text-xs px-2.5 py-1 rounded-md transition-all font-medium whitespace-nowrap flex items-center gap-1.5 ${
                    isActive
                      ? 'bg-brand-500/20 text-brand-300 border border-brand-500/40 shadow-sm font-semibold'
                      : 'bg-slate-800/40 hover:bg-slate-800 text-slate-400 border border-slate-700/50'
                  }`}
                >
                  <span className="truncate max-w-[140px]">{doc.filename}</span>
                  {doc.fiscalYear && (
                    <span className="text-[10px] px-1 py-0.2 rounded bg-slate-900 text-slate-400 border border-slate-700/40">
                      FY{doc.fiscalYear}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Control Bar: Page Navigation & Zoom Tools */}
      <div className="px-5 py-2 border-b border-slate-800/60 bg-slate-900/60 flex items-center justify-between gap-4">
        {/* Page Switcher */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={handlePrevPage}
            disabled={pageNumber <= 1}
            title="Previous Page"
            className="p-1.5 rounded-lg bg-slate-800/50 hover:bg-slate-800 text-slate-300 disabled:opacity-40 disabled:hover:bg-slate-800/50 transition"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <form onSubmit={handleJumpSubmit} className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Page</span>
            <input
              type="text"
              value={jumpPageInput}
              onChange={e => setJumpPageInput(e.target.value)}
              className="w-12 text-center text-xs font-bold bg-slate-950 border border-slate-700 rounded-md py-0.5 px-1 text-white focus:outline-none focus:border-brand-500"
            />
            {displayedPageNumber && displayedPageNumber !== String(pageNumber) && (
              <span className="text-[11px] text-slate-500 font-mono">
                (Filing p. {displayedPageNumber})
              </span>
            )}
          </form>

          <button
            onClick={handleNextPage}
            title="Next Page"
            className="p-1.5 rounded-lg bg-slate-800/50 hover:bg-slate-800 text-slate-300 transition"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1 bg-slate-950/60 p-1 rounded-lg border border-slate-800/80">
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>

          <span className="text-[11px] font-mono font-bold text-slate-300 w-10 text-center">
            {zoom}%
          </span>

          <button
            onClick={handleZoomIn}
            title="Zoom In"
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>

          <div className="w-[1px] h-3 bg-slate-800 mx-0.5" />

          <button
            onClick={handleFitWidth}
            title="Fit Width"
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={handleResetZoom}
            title="Reset Zoom"
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Document Canvas Viewport */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-auto overscroll-contain p-6 flex items-start justify-center bg-slate-950 relative"
      >

        {loading && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-950/70 backdrop-blur-sm gap-2">
            <Loader2 className="w-7 h-7 text-brand-400 animate-spin" />
            <span className="text-xs text-slate-300 font-medium">
              Rendering S3 filing page {pageNumber}...
            </span>
          </div>
        )}

        {error ? (
          <div className="m-auto text-center p-8 bg-slate-900 border border-rose-900/40 rounded-2xl max-w-md">
            <AlertCircle className="w-8 h-8 text-rose-400 mx-auto mb-2" />
            <h4 className="text-sm font-bold text-slate-100">Failed to load page image</h4>
            <p className="text-xs text-slate-400 mt-1">{error}</p>
            <button
              onClick={() => {
                setLoading(true);
                setError(null);
              }}
              className="mt-4 px-4 py-1.5 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition"
            >
              Retry
            </button>
          </div>
        ) : (
          <div
            className="relative shadow-2xl transition-all duration-150 origin-top rounded-lg overflow-visible bg-white"
            style={{
              width: `${zoom}%`,
              maxWidth: zoom <= 100 ? '100%' : 'none',
            }}
          >
            {currentSrc && (
              <img
                key={currentSrc}
                ref={imgRef}
                src={currentSrc}
                alt={`Document ${documentName || ''} Page ${pageNumber}`}
                onLoad={handleImageLoaded}
                onError={handleImageError}
                className="w-full h-auto block rounded-lg pointer-events-none"
              />
            )}

            {/* Bounding Box Highlight Overlay */}
            {normalizedBBox && (
              <div
                ref={highlightRef}
                data-testid="bbox-highlight"
                className="absolute border-2 border-brand-400 bg-brand-500/25 shadow-[0_0_24px_rgba(59,130,246,0.6)] rounded-md transition-all duration-300 pointer-events-none z-10 animate-pulse ring-2 ring-brand-300/40"
                style={{
                  left: `${normalizedBBox.leftPct}%`,
                  top: `${normalizedBBox.topPct}%`,
                  width: `${normalizedBBox.widthPct}%`,
                  height: `${normalizedBBox.heightPct}%`,
                }}
              >
                {/* Floating Grounding Concept Badge */}
                {concept && (
                  <div className="absolute -top-7 left-0 bg-brand-600 text-white text-[10px] font-extrabold px-2 py-0.5 rounded shadow-lg flex items-center gap-1 whitespace-nowrap z-20">
                    <Sparkles className="w-2.5 h-2.5 text-amber-300" />
                    <span>{concept}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom Grounding Snippet Card */}
      {snippet && (
        <div className="p-4 border-t border-slate-800/80 bg-slate-900/95 backdrop-blur-md">
          <div className="flex items-center gap-2 mb-1.5">
            <Sparkles className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300">
              Cited Evidence Snippet {concept ? `for ${concept}` : ''}
            </span>
          </div>
          <p className="text-xs text-slate-300 italic bg-slate-950/70 p-3 rounded-xl border border-slate-800/80 leading-relaxed max-h-24 overflow-y-auto">
            "{snippet}"
          </p>
        </div>
      )}
    </div>
  );
};
