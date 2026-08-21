import React, { useState, useRef } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import {
  Maximize2,
  Minimize2,
  Download,
  Table as TableIcon,
  BarChart2,
  TrendingUp,
  PieChart as PieIcon,
  Cloud,
  FileSpreadsheet,
} from 'lucide-react';
import { CopilotWidget } from '../../../models/copilot';

interface ChartWidgetRendererProps {
  widget: CopilotWidget;
}

const DEFAULT_COLORS = ['#38bdf8', '#818cf8', '#34d399', '#f472b6', '#fbbf24', '#a78bfa'];

const formatCompactAxis = (val: any) => {
  if (typeof val !== 'number') return String(val);
  if (Math.abs(val) >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(0)}M`;
  if (Math.abs(val) >= 1_000) return `${(val / 1_000).toFixed(0)}k`;
  if (Number.isInteger(val)) return String(val);
  return val.toFixed(1);
};

export const ChartWidgetRenderer: React.FC<ChartWidgetRendererProps> = ({ widget }) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showTable, setShowTable] = useState(false);
  const chartViewportRef = useRef<HTMLDivElement>(null);

  const series = widget.series && widget.series.length > 0
    ? widget.series
    : [{ key: 'value', label: 'Value', color: '#38bdf8' }];

  const data = widget.data || [];

  // Export source data table as CSV
  const handleExportCSV = () => {
    if (!data || data.length === 0) return;
    const headers = Object.keys(data[0]);
    const csvRows: string[] = [];

    // Header row
    csvRows.push(headers.map(h => `"${h.replace(/"/g, '""')}"`).join(','));

    // Data rows
    for (const row of data) {
      const values = headers.map(header => {
        const val = row[header];
        if (val === null || val === undefined) return '""';
        const escaped = String(val).replace(/"/g, '""');
        return `"${escaped}"`;
      });
      csvRows.push(values.join(','));
    }

    const csvString = csvRows.join('\r\n');
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const URL = window.URL || window.webkitURL || window;
    const blobURL = URL.createObjectURL(blob);

    const downloadLink = document.createElement('a');
    downloadLink.setAttribute('href', blobURL);
    downloadLink.setAttribute('download', `${widget.title.toLowerCase().replace(/[^a-z0-9]+/g, '_')}_data.csv`);
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
    URL.revokeObjectURL(blobURL);
  };

  // Export chart graphic as PNG via SVG canvas rendering (specifically targeting the recharts SVG)
  const handleExportPNG = () => {
    if (!chartViewportRef.current) return;

    // Specifically target the Recharts canvas SVG (excluding Lucide icon SVGs)
    const svgElement =
      chartViewportRef.current.querySelector<SVGElement>('.recharts-surface') ||
      chartViewportRef.current.querySelector<SVGElement>('.recharts-wrapper svg') ||
      chartViewportRef.current.querySelector<SVGElement>('svg:not(.lucide)');

    if (!svgElement) {
      // Fallback to CSV if no chart SVG element is found
      handleExportCSV();
      return;
    }

    const svgClone = svgElement.cloneNode(true) as SVGElement;
    const svgRect = svgElement.getBoundingClientRect();
    const width = Math.max(svgRect.width || 600, 500);
    const height = Math.max(svgRect.height || 350, 300);

    svgClone.setAttribute('width', `${width}`);
    svgClone.setAttribute('height', `${height}`);

    const svgString = new XMLSerializer().serializeToString(svgClone);
    const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const URL = window.URL || window.webkitURL || window;
    const blobURL = URL.createObjectURL(svgBlob);

    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement('canvas');
      const scale = 2; // High-DPI 2x
      canvas.width = width * scale;
      canvas.height = height * scale;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.scale(scale, scale);
        ctx.fillStyle = '#090d16'; // Deep slate dark background
        ctx.fillRect(0, 0, width, height);

        // Header Title
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 13px system-ui, -apple-system, sans-serif';
        ctx.fillText(widget.title, 14, 22);

        // Draw Chart Graphic
        ctx.drawImage(image, 0, 28, width, height - 28);

        const pngURL = canvas.toDataURL('image/png');
        const downloadLink = document.createElement('a');
        downloadLink.download = `${widget.title.toLowerCase().replace(/[^a-z0-9]+/g, '_')}_chart.png`;
        downloadLink.href = pngURL;
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
      }
      URL.revokeObjectURL(blobURL);
    };
    image.src = blobURL;
  };

  // Unified download action based on currently active view
  const handleDownload = () => {
    if (showTable) {
      handleExportCSV();
    } else {
      handleExportPNG();
    }
  };

  const renderChartContent = (heightClass = 'h-52') => {
    if (showTable) {
      return (
        <div className={`${heightClass} overflow-y-auto rounded-lg border border-slate-800 bg-slate-950/90 p-2`}>
          <table className="w-full text-[11px] text-left text-slate-300">
            <thead className="text-[10px] uppercase bg-slate-900 text-slate-400 border-b border-slate-800 sticky top-0">
              <tr>
                {data.length > 0 && Object.keys(data[0]).map(key => (
                  <th key={key} className="px-2.5 py-1.5 font-semibold">{key}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {data.map((row, i) => (
                <tr key={i} className="hover:bg-slate-900/50">
                  {Object.values(row).map((val: any, j) => (
                    <td key={j} className="px-2.5 py-1.5 font-mono text-slate-200">
                      {typeof val === 'number' ? val.toLocaleString() : String(val)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    if (widget.widgetType === 'word_cloud' || widget.wordCloudData) {
      const words = widget.wordCloudData || [];
      const maxVal = Math.max(...words.map(w => w.value), 1);
      return (
        <div className={`${heightClass} flex flex-wrap items-center justify-center gap-2 p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 overflow-y-auto`}>
          {words.map((item, idx) => {
            const ratio = item.value / maxVal;
            const fontSize = Math.max(10, Math.min(20, Math.round(10 + ratio * 10)));
            const colorClass = ratio > 0.7 ? 'text-brand-400 font-bold' : ratio > 0.4 ? 'text-sky-400 font-semibold' : 'text-slate-400';
            return (
              <span
                key={idx}
                style={{ fontSize: `${fontSize}px` }}
                className={`${colorClass} px-2 py-0.5 rounded-md bg-slate-900/80 border border-slate-800 transition hover:border-brand-500 cursor-default`}
                title={`${item.text}: ${item.value} mentions`}
              >
                {item.text} <span className="text-[9px] opacity-60">({item.value})</span>
              </span>
            );
          })}
        </div>
      );
    }

    if (widget.chartType === 'pie') {
      const pieData = data.map((d, i) => ({
        name: d.name || d.label || d.category || `Item ${i + 1}`,
        value: Number(d.value || d.amount || Object.values(d).find(v => typeof v === 'number') || 0),
      }));

      return (
        <div className={heightClass}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
                itemStyle={{ color: '#e2e8f0' }}
              />
              <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '2px' }} />
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={heightClass === 'h-52' || heightClass === 'h-48' ? 55 : 110}
                innerRadius={heightClass === 'h-52' || heightClass === 'h-48' ? 30 : 55}
                paddingAngle={3}
              >
                {pieData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={DEFAULT_COLORS[index % DEFAULT_COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (widget.chartType === 'bar') {
      const xKey = Object.keys(data[0] || {}).find(k => k === 'year' || k === 'period' || k === 'name' || k === 'category') || 'year';
      return (
        <div className={heightClass}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 10, left: -18, bottom: 2 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey={xKey}
                stroke="#64748b"
                tick={{ fontSize: 9, fill: '#94a3b8' }}
                axisLine={{ stroke: '#334155' }}
                tickLine={false}
              />
              <YAxis
                stroke="#64748b"
                width={36}
                tick={{ fontSize: 9, fill: '#94a3b8' }}
                axisLine={{ stroke: '#334155' }}
                tickLine={false}
                tickFormatter={formatCompactAxis}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
                itemStyle={{ color: '#e2e8f0' }}
              />
              <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '2px' }} />
              {series.map((s, idx) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  fill={s.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length]}
                  radius={[3, 3, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    }

    // Default: Line chart
    const xKey = Object.keys(data[0] || {}).find(k => k === 'year' || k === 'period' || k === 'date' || k === 'fiscal_year') || 'year';
    return (
      <div className={heightClass}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 10, left: -18, bottom: 2 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey={xKey}
              stroke="#64748b"
              tick={{ fontSize: 9, fill: '#94a3b8' }}
              axisLine={{ stroke: '#334155' }}
              tickLine={false}
            />
            <YAxis
              stroke="#64748b"
              width={36}
              tick={{ fontSize: 9, fill: '#94a3b8' }}
              axisLine={{ stroke: '#334155' }}
              tickLine={false}
              tickFormatter={formatCompactAxis}
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
              itemStyle={{ color: '#e2e8f0' }}
            />
            <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '2px' }} />
            {series.map((s, idx) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length]}
                strokeWidth={2}
                dot={{ r: 2.5, fill: s.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length] }}
                activeDot={{ r: 4 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  };

  return (
    <>
      {/* Inline Chart Card */}
      <div className="my-2.5 rounded-xl border border-slate-800 bg-slate-950/95 p-3 shadow-lg shadow-black/40 backdrop-blur-sm">
        {/* Header with Title and Action Icons */}
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-850">
          <div className="flex items-center gap-2 min-w-0">
            <div className="p-1 rounded-md bg-brand-950 text-brand-400 border border-brand-800/60 flex-shrink-0">
              {widget.widgetType === 'word_cloud' ? (
                <Cloud className="w-3.5 h-3.5" />
              ) : widget.chartType === 'pie' ? (
                <PieIcon className="w-3.5 h-3.5" />
              ) : widget.chartType === 'bar' ? (
                <BarChart2 className="w-3.5 h-3.5" />
              ) : (
                <TrendingUp className="w-3.5 h-3.5" />
              )}
            </div>
            <div className="truncate">
              <h4 className="text-xs font-bold text-slate-100 truncate">{widget.title}</h4>
              {widget.description && (
                <p className="text-[10px] text-slate-400 truncate">{widget.description}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0 ml-2">
            {data.length > 0 && (
              <button
                type="button"
                onClick={() => setShowTable(!showTable)}
                className={`p-1.5 rounded-lg border transition ${
                  showTable
                    ? 'bg-brand-900/50 border-brand-700 text-brand-300'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
                title={showTable ? 'Show Chart' : 'Show Data Table'}
              >
                <TableIcon className="w-3 h-3" />
              </button>
            )}
            <button
              type="button"
              onClick={handleDownload}
              className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-brand-300 hover:border-brand-700/60 transition"
              title={showTable ? 'Download Table as CSV' : 'Download Chart as PNG'}
            >
              {showTable ? (
                <FileSpreadsheet className="w-3 h-3 text-emerald-400" />
              ) : (
                <Download className="w-3 h-3" />
              )}
            </button>
            <button
              type="button"
              onClick={() => setIsFullscreen(true)}
              className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-brand-300 hover:border-brand-700/60 transition"
              title="Full-Screen Overlay"
            >
              <Maximize2 className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* Chart Viewport specifically referenced for SVG query */}
        <div ref={chartViewportRef}>
          {renderChartContent('h-48')}
        </div>
      </div>

      {/* Full-Screen Modal Overlay */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-6">
          <div className="w-full max-w-4xl rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-brand-950 text-brand-400 border border-brand-800">
                  <TrendingUp className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-100">{widget.title}</h3>
                  {widget.description && (
                    <p className="text-xs text-slate-400">{widget.description}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleDownload}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 transition"
                  title={showTable ? 'Download Table as CSV' : 'Download Chart as PNG'}
                >
                  {showTable ? (
                    <>
                      <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" /> Download CSV
                    </>
                  ) : (
                    <>
                      <Download className="w-3.5 h-3.5" /> Download PNG
                    </>
                  )}
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

            <div className="flex-1 min-h-[400px]">
              {renderChartContent('h-[420px]')}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
