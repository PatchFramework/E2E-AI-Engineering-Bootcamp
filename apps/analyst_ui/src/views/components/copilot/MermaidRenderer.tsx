import React, { useEffect, useRef, useState, useId } from 'react';
import mermaid from 'mermaid';
import { Copy, Check, AlertCircle, Maximize2, Minimize2, Download } from 'lucide-react';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    darkMode: true,
    background: '#020617', // slate-950
    primaryColor: '#4f46e5', // indigo-600
    primaryTextColor: '#f8fafc', // slate-50
    primaryBorderColor: '#6366f1', // indigo-500
    lineColor: '#94a3b8', // slate-400
    secondaryColor: '#0f172a', // slate-900
    tertiaryColor: '#1e293b', // slate-800
    mainBkg: '#0f172a',
    nodeBorder: '#475569',
    clusterBkg: '#0b1120',
    clusterBorder: '#334155',
    defaultLinkColor: '#94a3b8',
    titleColor: '#e2e8f0',
    edgeLabelBackground: '#0f172a',
    actorBorder: '#6366f1',
    actorBkg: '#1e1b4b',
    actorTextColor: '#e0e7ff',
    signalColor: '#cbd5e1',
    signalTextColor: '#e2e8f0',
    labelBoxBkgColor: '#0f172a',
    labelBoxBorderColor: '#334155',
    labelTextColor: '#e2e8f0',
    loopTextColor: '#e2e8f0',
    noteBorderColor: '#475569',
    noteBkgColor: '#1e293b',
    noteTextColor: '#cbd5e1',
    activationBorderColor: '#6366f1',
    activationBkgColor: '#312e81',
    sequenceNumberColor: '#ffffff',
  },
  securityLevel: 'loose',
  fontFamily: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
});

interface MermaidRendererProps {
  chart: string;
}

export const MermaidRenderer: React.FC<MermaidRendererProps> = ({ chart }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>('');
  const [hasError, setHasError] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const rawId = useId();
  const diagramId = `mermaid-${rawId.replace(/:/g, '')}`;

  useEffect(() => {
    let isCancelled = false;

    const renderChart = async () => {
      if (!chart.trim()) {
        setSvgContent('');
        setHasError(false);
        return;
      }

      try {
        setHasError(false);
        const { svg } = await mermaid.render(diagramId, chart.trim());
        if (!isCancelled) {
          setSvgContent(svg);
        }
      } catch (err) {
        if (!isCancelled) {
          // If error occurs during streaming or invalid syntax, show fallback
          console.warn('Mermaid rendering error:', err);
          setHasError(true);
        }
      }
    };

    renderChart();

    return () => {
      isCancelled = true;
    };
  }, [chart, diagramId]);

  const handleCopyCode = async () => {
    try {
      await navigator.clipboard.writeText(chart);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  const handleDownloadSVG = () => {
    if (!svgContent) return;
    const blob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `diagram_${Date.now()}.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (hasError) {
    return (
      <div className="my-2 p-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 font-mono text-[11px] overflow-x-auto">
        <div className="flex items-center gap-1.5 text-amber-400 text-xs mb-1.5 font-sans font-semibold">
          <AlertCircle className="w-3.5 h-3.5" />
          <span>Mermaid Diagram</span>
        </div>
        <pre className="text-slate-400 whitespace-pre-wrap">{chart}</pre>
      </div>
    );
  }

  return (
    <>
      <div className="my-2.5 rounded-xl border border-slate-800 bg-slate-950/90 shadow-md backdrop-blur-sm overflow-hidden group">
        {/* Diagram Header */}
        <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/80 border-b border-slate-800/80 text-[10px] text-slate-400">
          <div className="flex items-center gap-1.5 font-semibold text-slate-300">
            <span className="w-2 h-2 rounded-full bg-brand-400"></span>
            <span>Mermaid Diagram</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleCopyCode}
              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
              title="Copy Diagram Source"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            </button>
            <button
              type="button"
              onClick={handleDownloadSVG}
              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
              title="Download SVG"
            >
              <Download className="w-3 h-3" />
            </button>
            <button
              type="button"
              onClick={() => setIsFullscreen(true)}
              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
              title="Fullscreen Diagram"
            >
              <Maximize2 className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* Diagram Container */}
        <div
          ref={containerRef}
          className="p-3 overflow-x-auto flex justify-center items-center [&>svg]:max-w-full [&>svg]:h-auto [&>svg]:mx-auto"
          dangerouslySetInnerHTML={{ __html: svgContent }}
        />
      </div>

      {/* Fullscreen Overlay */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-6">
          <div className="w-full max-w-5xl rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-brand-400"></span>
                <h3 className="text-sm font-bold text-slate-100">Mermaid Diagram View</h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleDownloadSVG}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 transition"
                >
                  <Download className="w-3.5 h-3.5" /> Download SVG
                </button>
                <button
                  type="button"
                  onClick={() => setIsFullscreen(false)}
                  className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
                  title="Close Fullscreen"
                >
                  <Minimize2 className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div
              className="flex-1 overflow-auto flex justify-center items-center p-4 bg-slate-950/80 rounded-xl border border-slate-800/80 [&>svg]:max-w-full [&>svg]:h-auto"
              dangerouslySetInnerHTML={{ __html: svgContent }}
            />
          </div>
        </div>
      )}
    </>
  );
};
