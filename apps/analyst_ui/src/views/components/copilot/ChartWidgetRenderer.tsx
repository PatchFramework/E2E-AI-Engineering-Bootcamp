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
} from 'lucide-react';
import { CopilotWidget } from '../../../models/copilot';

interface ChartWidgetRendererProps {
  widget: CopilotWidget;
}

const DEFAULT_COLORS = ['#38bdf8', '#818cf8', '#34d399', '#f472b6', '#fbbf24', '#a78bfa'];

export const ChartWidgetRenderer: React.FC<ChartWidgetRendererProps> = ({ widget }) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showTable, setShowTable] = useState(false);
  const chartContainerRef = useRef<HTMLDivElement>(null);

  const series = widget.series && widget.series.length > 0
    ? widget.series
    : [{ key: 'value', label: 'Value', color: '#38bdf8' }];

  const data = widget.data || [];

  // Export chart as PNG via SVG canvas rendering
  const handleExportPNG = () => {
    if (!chartContainerRef.current) return;
    const svgElement = chartContainerRef.current.querySelector('svg');
    if (!svgElement) return;

    const svgString = new XMLSerializer().serializeToString(svgElement);
    const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const URL = window.URL || window.webkitURL || window;
    const blobURL = URL.createObjectURL(svgBlob);

    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = (svgElement.clientWidth || 600) * 2;
      canvas.height = (svgElement.clientHeight || 400) * 2;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#0f172a'; // slate-900 dark background
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

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

  const renderChartContent = (heightClass = 'h-52') => {
    if (showTable) {
      return (
        <div className={`${heightClass} overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-2`}>
          <table className="w-full text-[11px] text-left text-slate-300">
            <thead className="text-[10px] uppercase bg-slate-900 text-slate-400 border-b border-slate-800">
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
        <div className={`${heightClass} flex flex-wrap items-center justify-center gap-2.5 p-4 rounded-lg bg-slate-950/60 border border-slate-800/80 overflow-y-auto`}>
          {words.map((item, idx) => {
            const ratio = item.value / maxVal;
            const fontSize = Math.max(11, Math.min(24, Math.round(11 + ratio * 14)));
            const colorClass = ratio > 0.7 ? 'text-brand-400 font-bold' : ratio > 0.4 ? 'text-sky-400 font-semibold' : 'text-slate-400';
            return (
              <span
                key={idx}
                style={{ fontSize: `${fontSize}px` }}
                className={`${colorClass} px-2 py-0.5 rounded bg-slate-900/80 border border-slate-800 transition hover:scale-110 hover:border-brand-500 cursor-default`}
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
            <PieChart>
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
                itemStyle={{ color: '#e2e8f0' }}
              />
              <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '4px' }} />
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={heightClass === 'h-52' ? 65 : 120}
                innerRadius={heightClass === 'h-52' ? 35 : 60}
                paddingAngle={3}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
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
            <BarChart data={data} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey={xKey} stroke="#64748b" tick={{ fontSize: 10 }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
                itemStyle={{ color: '#e2e8f0' }}
              />
              <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '4px' }} />
              {series.map((s, idx) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  fill={s.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length]}
                  radius={[4, 4, 0, 0]}
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
          <LineChart data={data} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey={xKey} stroke="#64748b" tick={{ fontSize: 10 }} />
            <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
              itemStyle={{ color: '#e2e8f0' }}
            />
            <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '4px' }} />
            {series.map((s, idx) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3, fill: s.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length] }}
                activeDot={{ r: 5 }}
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
      <div
        ref={chartContainerRef}
        className="my-3 rounded-xl border border-slate-800 bg-slate-950/90 p-3.5 shadow-lg shadow-black/40 backdrop-blur-sm"
      >
        {/* Header with Title and Action Icons */}
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-850">
          <div className="flex items-center gap-2">
            <div className="p-1 rounded-md bg-brand-950 text-brand-400 border border-brand-800/60">
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
            <div>
              <h4 className="text-xs font-bold text-slate-100">{widget.title}</h4>
              {widget.description && (
                <p className="text-[10px] text-slate-400">{widget.description}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1">
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
              onClick={handleExportPNG}
              className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-brand-300 hover:border-brand-700/60 transition"
              title="Download PNG"
            >
              <Download className="w-3 h-3" />
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

        {/* Chart Viewport */}
        {renderChartContent('h-48')}
      </div>

      {/* Full-Screen Modal Overlay */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-6">
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
                  onClick={handleExportPNG}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 transition"
                >
                  <Download className="w-3.5 h-3.5" /> Download PNG
                </button>
                <button
                  type="button"
                  onClick={() => setIsFullscreen(false)}
                  className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
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
