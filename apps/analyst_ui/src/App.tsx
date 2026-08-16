import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Building2,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
  ArrowRight,
  ChevronRight,
  Send,
  BookOpen,
  Settings,
  FileText,
  Activity,
  Upload,
  X,
  CloudUpload,
  Loader2,
  CheckCheck,
  XCircle,
  ChevronDown,
  LayoutDashboard,
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

type DagState = 'queued' | 'running' | 'success' | 'failed' | null;

interface TaskStatus {
  task_id: string;
  state: string;
  start_date: string | null;
  end_date: string | null;
}

interface PipelineJob {
  /** Unique client-side ID */
  id: string;
  filename: string;
  company?: string;
  fiscal_year?: number;
  fiscal_period?: string;
  document_type?: string;
  document_id?: number;
  dag_run_id: string | null;
  /** null = upload in progress, otherwise Airflow DAG state */
  state: 'uploading' | DagState;
  /** Error message if something went wrong */
  error?: string;
  tasks: TaskStatus[];
  uploadedAt: Date;
}

// ─── Task step config (ordered as DAG topology) ──────────────────────────────

const TASK_STEPS = [
  { id: 'parse_pdf', label: 'Parse PDF', description: 'Extract text, tables & page images' },
  { id: 'extract_facts', label: 'Extract Facts', description: 'AI financial concept extraction' },
  { id: 'index_chunks', label: 'Index Chunks', description: 'Vector embeddings to pgvector' },
  { id: 'validate_facts', label: 'Validate', description: 'Accounting rule consistency check' },
  { id: 'calculate_kpis', label: 'Calculate KPIs', description: 'Derive credit metrics' },
];

// ─── Helper: state → colour ───────────────────────────────────────────────────

function stateColor(state: string | null | undefined) {
  switch (state) {
    case 'success': return 'text-emerald-400';
    case 'running': return 'text-brand-400';
    case 'failed':
    case 'upstream_failed': return 'text-red-400';
    default: return 'text-slate-500';
  }
}

function stateBg(state: string | null | undefined) {
  switch (state) {
    case 'success': return 'bg-emerald-950/50 border-emerald-900/50';
    case 'running': return 'bg-brand-950/50 border-brand-900/50 animate-pulse';
    case 'failed':
    case 'upstream_failed': return 'bg-red-950/40 border-red-900/50';
    default: return 'bg-slate-900/40 border-slate-800/60';
  }
}

function overallBadge(state: PipelineJob['state']) {
  if (state === 'uploading')
    return <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-sky-400 bg-sky-950/40 border border-sky-900/50 px-2.5 py-0.5 rounded-full">
      <Loader2 className="w-3 h-3 animate-spin" /> Uploading
    </span>;
  if (state === 'queued')
    return <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 bg-slate-800/60 border border-slate-700/50 px-2.5 py-0.5 rounded-full">
      <Clock className="w-3 h-3" /> Queued
    </span>;
  if (state === 'running')
    return <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-brand-400 bg-brand-950/40 border border-brand-900/50 px-2.5 py-0.5 rounded-full animate-pulse">
      <Activity className="w-3 h-3" /> Processing
    </span>;
  if (state === 'success')
    return <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-950/40 border border-emerald-900/50 px-2.5 py-0.5 rounded-full">
      <CheckCircle className="w-3 h-3" /> Complete
    </span>;
  if (state === 'failed')
    return <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-red-400 bg-red-950/40 border border-red-900/50 px-2.5 py-0.5 rounded-full">
      <XCircle className="w-3 h-3" /> Failed
    </span>;
  return null;
}

// ─── Job Card ─────────────────────────────────────────────────────────────────

function JobCard({ job, onRemove }: { job: PipelineJob; onRemove: () => void }) {
  const [expanded, setExpanded] = useState(job.state === 'running' || job.state === 'failed');

  // Auto-expand when transitioning to running or failed
  useEffect(() => {
    if (job.state === 'running' || job.state === 'failed') setExpanded(true);
  }, [job.state]);

  const progress = (() => {
    const total = TASK_STEPS.length;
    const done = job.tasks.filter(t => t.state === 'success').length;
    return (done / total) * 100;
  })();

  const statusMessage = (() => {
    if (job.state === 'uploading') return 'Uploading document to storage...';
    if (job.state === 'queued') return 'Waiting in queue...';
    if (job.state === 'running') {
      if (!job.tasks || job.tasks.length === 0) {
        return 'Starting up pipeline...';
      }
      const runningTasks = job.tasks.filter(t => t.state === 'running');
      if (runningTasks.length > 0) {
        const names = runningTasks.map(t => TASK_STEPS.find(s => s.id === t.task_id)?.label || t.task_id);
        return `Currently running: ${names.join(', ')}`;
      }
      // Look for first queued/pending task
      const nextTask = TASK_STEPS.find(step => {
        const t = job.tasks.find(task => task.task_id === step.id);
        return !t || t.state === 'queued';
      });
      return nextTask ? `Preparing: ${nextTask.label}` : 'Initializing pipeline...';
    }
    if (job.state === 'failed') {
      const failedTask = job.tasks.find(t => t.state === 'failed' || t.state === 'upstream_failed');
      if (failedTask) {
        const stepName = TASK_STEPS.find(s => s.id === failedTask.task_id)?.label || failedTask.task_id;
        return `Error occurred during step: ${stepName}`;
      }
      return job.error || 'Pipeline execution failed';
    }
    if (job.state === 'success') {
      return 'Processing complete';
    }
    return null;
  })();

  return (
    <div className={`rounded-xl border transition-all duration-500 overflow-hidden ${
      job.state === 'failed' ? 'border-red-900/60 bg-red-950/10' :
      job.state === 'success' ? 'border-emerald-900/60 bg-emerald-950/10' :
      'border-slate-800/70 bg-slate-900/50'
    }`}>
      {/* Card header */}
      <div className="p-4 flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
            <span className="text-sm font-semibold text-slate-100 truncate">{job.filename}</span>
            {overallBadge(job.state)}
          </div>
          {job.company && (
            <div className="text-xs text-slate-400 mt-1 flex items-center gap-2">
              <Building2 className="w-3.5 h-3.5" />
              {job.company}
              {job.fiscal_year && <span className="text-slate-600">·</span>}
              {job.fiscal_year && <span>{job.document_type} {job.fiscal_year} {job.fiscal_period}</span>}
            </div>
          )}
          {statusMessage && (
            <div className={`text-xs mt-2 flex items-center gap-1.5 ${
              job.state === 'failed' ? 'text-red-400 font-medium' :
              job.state === 'success' ? 'text-emerald-400' : 'text-slate-300'
            }`}>
              {job.state === 'running' && <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-400" />}
              {job.state === 'failed' && <AlertTriangle className="w-3.5 h-3.5 text-red-400" />}
              {job.state === 'success' && <CheckCheck className="w-3.5 h-3.5 text-emerald-400" />}
              <span>{statusMessage}</span>
            </div>
          )}
          {job.error && !statusMessage.includes(job.error) && (
            <p className="text-xs text-red-400 mt-1">{job.error}</p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {job.dag_run_id && job.state !== 'uploading' && (
            <button
              onClick={() => setExpanded(e => !e)}
              className="text-slate-500 hover:text-slate-300 transition"
            >
              <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </button>
          )}
          {(job.state === 'success' || job.state === 'failed' || job.error) && (
            <button onClick={onRemove} className="text-slate-600 hover:text-slate-300 transition">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {job.state !== 'uploading' && job.dag_run_id && (
        <div className="px-4 pb-1">
          <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ease-out ${
                job.state === 'failed' ? 'bg-red-500' :
                job.state === 'success' ? 'bg-emerald-500' : 'bg-brand-500'
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Task breakdown */}
      {expanded && job.dag_run_id && (
        <div className="px-4 pb-4 pt-2 space-y-2">
          {TASK_STEPS.map(step => {
            const taskStatus = job.tasks.find(t => t.task_id === step.id);
            const state = taskStatus?.state ?? 'queued';
            return (
              <div key={step.id} className={`flex items-center gap-3 rounded-lg px-3 py-2 border ${stateBg(state)}`}>
                <div className="w-5 h-5 flex-shrink-0">
                  {state === 'success' && <CheckCheck className="w-5 h-5 text-emerald-400" />}
                  {state === 'running' && <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />}
                  {(state === 'failed' || state === 'upstream_failed') && <XCircle className="w-5 h-5 text-red-400" />}
                  {(state === 'queued' || state === 'skipped' || !taskStatus) && <Clock className="w-5 h-5 text-slate-600" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className={`text-xs font-semibold ${stateColor(state)}`}>{step.label}</div>
                  <div className="text-[10px] text-slate-500">{step.description}</div>
                </div>
                <div className={`text-[10px] font-bold uppercase tracking-wider ${stateColor(state)}`}>
                  {state}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Upload Screen ─────────────────────────────────────────────────────────────

function UploadScreen({ jobs, onUpload, onRemoveJob }: {
  jobs: PipelineJob[];
  onUpload: (files: FileList) => void;
  onRemoveJob: (id: string) => void;
}) {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files.length > 0) onUpload(e.dataTransfer.files);
  }, [onUpload]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback(() => setDragActive(false), []);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) onUpload(e.target.files);
    e.target.value = ''; // reset so same file can be re-uploaded
  }, [onUpload]);

  const activeJobs = jobs.filter(j => j.state === 'running' || j.state === 'uploading' || j.state === 'queued');
  const completedJobs = jobs.filter(j => j.state === 'success' || j.state === 'failed');

  return (
    <div className="max-w-2xl mx-auto space-y-8 py-4">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-extrabold tracking-tight">Upload Filing</h2>
        <p className="text-sm text-slate-400 mt-1">
          Upload annual reports, 10-Ks, or 10-Qs. The AI pipeline will extract financial facts automatically.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-12 flex flex-col items-center justify-center gap-4 cursor-pointer transition-all duration-200 select-none ${
          dragActive
            ? 'border-brand-400 bg-brand-950/20 scale-[1.01]'
            : 'border-slate-700/70 hover:border-slate-600 bg-slate-900/30 hover:bg-slate-900/50'
        }`}
      >
        <div className={`p-5 rounded-2xl transition-all ${dragActive ? 'bg-brand-900/40' : 'bg-slate-800/40'}`}>
          <CloudUpload className={`w-12 h-12 ${dragActive ? 'text-brand-400' : 'text-slate-500'}`} />
        </div>

        <div className="text-center">
          <p className="text-base font-semibold text-slate-200">
            {dragActive ? 'Drop to upload' : 'Drag & drop PDFs here'}
          </p>
          <p className="text-sm text-slate-400 mt-1">
            or <span className="text-brand-400 underline underline-offset-2">browse files</span>
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-900/60 px-4 py-2 rounded-lg border border-slate-800/60">
          <FileText className="w-3.5 h-3.5" />
          Supported: PDF · Max 50 MB per file · Multiple files allowed
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          onChange={handleFileChange}
          className="hidden"
          id="filing-upload-input"
        />
      </div>

      {/* Pipeline info strip */}
      <div className="bg-slate-900/40 border border-slate-800/60 rounded-xl p-4">
        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Processing pipeline</div>
        <div className="flex items-center gap-2 flex-wrap">
          {TASK_STEPS.map((step, i) => (
            <div key={step.id} className="flex items-center gap-2">
              <div className="text-xs text-slate-300 bg-slate-800/60 border border-slate-700/50 px-2.5 py-1 rounded-md">
                {step.label}
              </div>
              {i < TASK_STEPS.length - 1 && <ArrowRight className="w-3 h-3 text-slate-600" />}
            </div>
          ))}
        </div>
        <p className="text-[11px] text-slate-500 mt-3 leading-relaxed">
          Uploads are non-blocking — you can navigate away and come back to check progress. The status tracker below updates every 5 seconds automatically.
        </p>
      </div>

      {/* Active jobs */}
      {activeJobs.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-brand-400 animate-pulse" />
            <h3 className="text-sm font-bold text-slate-300">Active Jobs</h3>
            <span className="text-[11px] font-bold text-brand-400 bg-brand-950/40 border border-brand-900/50 px-2 py-0.5 rounded-full">
              {activeJobs.length}
            </span>
          </div>
          <div className="space-y-3">
            {activeJobs.map(job => (
              <JobCard key={job.id} job={job} onRemove={() => onRemoveJob(job.id)} />
            ))}
          </div>
        </div>
      )}

      {/* Completed jobs */}
      {completedJobs.length > 0 && (
        <div>
          <h3 className="text-sm font-bold text-slate-400 mb-3">Completed</h3>
          <div className="space-y-3">
            {completedJobs.map(job => (
              <JobCard key={job.id} job={job} onRemove={() => onRemoveJob(job.id)} />
            ))}
          </div>
        </div>
      )}

      {jobs.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-6 text-slate-600">
          <Upload className="w-8 h-8" />
          <p className="text-sm">No uploads yet</p>
        </div>
      )}
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [activeNav, setActiveNav] = useState<'dashboard' | 'upload'>('dashboard');
  const [activeTab, setActiveTab] = useState('Overview');
  const [copilotQuery, setCopilotQuery] = useState('');
  const [selectedFact, setSelectedFact] = useState<string | null>(null);
  const [jobs, setJobs] = useState<PipelineJob[]>([]);

  // ── Stub data ──────────────────────────────────────────────────────────────
  const companyInfo = {
    name: 'Acme Corporation',
    rating: 'BB',
    risk: 'Elevated',
    latestFiling: 'FY2025 Annual Report',
    dataQuality: '87%',
    issuesCount: 3,
  };

  const tabs = ['Overview', 'Profitability', 'Leverage', 'Coverage', 'Liquidity', 'Cash Flow', 'Balance Sheet'];

  const metrics = [
    { name: 'Revenue', value: '€2.4B', change: '+12% YoY', trend: 'up', status: 'Verified', category: 'Profitability' },
    { name: 'EBITDA', value: '€184M', change: '-4% YoY', trend: 'down', status: 'Corrected', category: 'Profitability' },
    { name: 'Total Debt', value: '€1.2B', change: '+35% YoY', trend: 'up', status: 'Verified', category: 'Leverage' },
    { name: 'Net Debt / EBITDA', value: '4.57x', change: '+0.83x YoY', trend: 'up', status: 'Corrected', category: 'Leverage' },
    { name: 'EBITDA / Interest', value: '2.8x', change: '-1.2x YoY', trend: 'down', status: 'Unverified', category: 'Coverage' },
    { name: 'Current Ratio', value: '1.45x', change: '-0.1x YoY', trend: 'down', status: 'Verified', category: 'Liquidity' },
    { name: 'Free Cash Flow', value: '-€22M', change: '-€45M YoY', trend: 'down', status: 'Verified', category: 'Cash Flow' },
  ];

  // ── Upload handler ─────────────────────────────────────────────────────────
  const handleUpload = useCallback(async (files: FileList) => {
    const fileArray = Array.from(files).filter(f => f.type === 'application/pdf' || f.name.endsWith('.pdf'));
    if (fileArray.length === 0) return;

    const newJobs: PipelineJob[] = fileArray.map(f => ({
      id: `${Date.now()}-${Math.random()}`,
      filename: f.name,
      dag_run_id: null,
      state: 'uploading',
      tasks: [],
      uploadedAt: new Date(),
    }));

    setJobs(prev => [...newJobs, ...prev]);

    // Upload each file in parallel
    await Promise.all(
      fileArray.map(async (file, idx) => {
        const job = newJobs[idx];
        try {
          const formData = new FormData();
          formData.append('file', file);

          const res = await fetch(`${API_BASE}/api/documents/upload`, {
            method: 'POST',
            body: formData,
          });

          if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
            setJobs(prev => prev.map(j =>
              j.id === job.id
                ? { ...j, state: 'failed', error: err.detail ?? 'Upload failed' }
                : j
            ));
            return;
          }

          const data = await res.json();
          setJobs(prev => prev.map(j =>
            j.id === job.id
              ? {
                  ...j,
                  company: data.company_id ? `Company #${data.company_id}` : undefined,
                  fiscal_year: data.fiscal_year,
                  fiscal_period: data.fiscal_period,
                  document_type: data.document_type,
                  document_id: data.id,
                  dag_run_id: data.dag_run_id ?? null,
                  state: data.dag_run_id ? 'queued' : 'success',
                }
              : j
          ));
        } catch (e) {
          setJobs(prev => prev.map(j =>
            j.id === job.id
              ? { ...j, state: 'failed', error: 'Network error — could not reach API' }
              : j
          ));
        }
      })
    );
  }, []);

  // ── Poll active jobs every 5 seconds ──────────────────────────────────────
  useEffect(() => {
    const pollableJobs = jobs.filter(
      j => j.dag_run_id && (j.state === 'queued' || j.state === 'running')
    );

    if (pollableJobs.length === 0) return;

    const poll = async () => {
      await Promise.all(
        pollableJobs.map(async job => {
          if (!job.dag_run_id) return;
          try {
            const res = await fetch(`${API_BASE}/api/pipeline/status/${encodeURIComponent(job.dag_run_id)}`);
            if (!res.ok) return;
            const data = await res.json();
            setJobs(prev => prev.map(j =>
              j.id === job.id
                ? { ...j, state: data.state, tasks: data.tasks ?? [] }
                : j
            ));
          } catch {
            // Silent — will retry on next interval
          }
        })
      );
    };

    poll(); // immediate first poll
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, [jobs]);

  // ── Active job count badge ─────────────────────────────────────────────────
  const activeJobCount = jobs.filter(j => j.state === 'uploading' || j.state === 'queued' || j.state === 'running').length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Navigation Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md px-6 py-4 flex justify-between items-center sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="bg-brand-600 text-white p-2 rounded-lg font-bold flex items-center justify-center">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
              CreditUnderwriter <span className="text-brand-400 text-xs font-semibold px-2 py-0.5 rounded-full bg-brand-900/30 border border-brand-800/50">CoPilot v1.0</span>
            </h1>
          </div>
        </div>

        {/* Nav tabs */}
        <nav className="flex items-center gap-1 bg-slate-900/60 border border-slate-800/60 rounded-lg p-1">
          <button
            id="nav-dashboard"
            onClick={() => setActiveNav('dashboard')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeNav === 'dashboard'
                ? 'bg-brand-600 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            Dashboard
          </button>
          <button
            id="nav-upload"
            onClick={() => setActiveNav('upload')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeNav === 'upload'
                ? 'bg-brand-600 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Upload className="w-3.5 h-3.5" />
            Upload Filing
            {activeJobCount > 0 && (
              <span className="bg-amber-500 text-black text-[9px] font-black px-1.5 py-0.5 rounded-full leading-none">
                {activeJobCount}
              </span>
            )}
          </button>
        </nav>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-800/40 px-3 py-1.5 rounded-md border border-slate-700/30">
            <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            API Connected
          </div>
          <button className="text-slate-400 hover:text-white transition">
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* ─── Upload Screen ────────────────────────────────────────────────── */}
      {activeNav === 'upload' && (
        <div className="flex-1 p-6 overflow-y-auto">
          <UploadScreen
            jobs={jobs}
            onUpload={handleUpload}
            onRemoveJob={(id) => setJobs(prev => prev.filter(j => j.id !== id))}
          />
        </div>
      )}

      {/* ─── Dashboard ────────────────────────────────────────────────────── */}
      {activeNav === 'dashboard' && (
        <div className="flex-1 flex overflow-hidden">
          {/* Left Side: Workstation */}
          <main className="flex-1 p-6 overflow-y-auto space-y-6">
            {/* Company Banner */}
            <div className="bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800/80 rounded-xl p-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-96 h-96 bg-brand-900/10 rounded-full blur-3xl -z-10 pointer-events-none" />

              <div className="flex flex-col lg:flex-row lg:justify-between lg:items-start gap-6">
                <div>
                  <span className="text-xs text-brand-400 font-semibold tracking-wider uppercase">Active Portfolio Company</span>
                  <h2 className="text-3xl font-extrabold tracking-tight mt-1">{companyInfo.name}</h2>
                  <p className="text-xs text-slate-400 mt-2 flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-slate-400" />
                    Primary Filing: <span className="text-slate-200 font-medium">{companyInfo.latestFiling}</span>
                  </p>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-slate-950/60 p-4 rounded-lg border border-slate-800/50 backdrop-blur-sm">
                  <div className="px-2">
                    <div className="text-xs text-slate-400">Suggested Rating</div>
                    <div className="flex items-center gap-1.5 mt-1">
                      <span className="text-2xl font-black text-amber-500">{companyInfo.rating}</span>
                      <span className="text-xs text-slate-400 font-medium">({companyInfo.risk} Risk)</span>
                    </div>
                  </div>

                  <div className="border-l border-slate-800 px-4">
                    <div className="text-xs text-slate-400">Data Quality</div>
                    <div className="text-lg font-bold text-emerald-400 mt-1">{companyInfo.dataQuality} <span className="text-xs text-slate-400 font-normal">verified</span></div>
                  </div>

                  <div className="border-l border-slate-800 px-4 col-span-2">
                    <div className="text-xs text-slate-400">Discrepancies</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="flex h-2 w-2 relative">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
                      </span>
                      <span className="text-sm font-semibold text-red-400">{companyInfo.issuesCount} issues require review</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Navigation Category Tabs */}
            <div className="border-b border-slate-800 flex gap-2 overflow-x-auto py-1">
              {tabs.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2.5 rounded-t-lg font-medium text-sm transition-all whitespace-nowrap border-b-2 -mb-1 ${
                    activeTab === tab
                      ? 'border-brand-500 text-brand-400 bg-brand-950/10'
                      : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/30'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* KPI Dashboard */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {metrics
                .filter(m => activeTab === 'Overview' || m.category === activeTab)
                .map((metric, idx) => (
                  <div
                    key={idx}
                    onClick={() => setSelectedFact(metric.name)}
                    className="bg-slate-900/60 border border-slate-800 hover:border-slate-700/80 hover:bg-slate-900 transition p-5 rounded-xl cursor-pointer group flex flex-col justify-between h-44"
                  >
                    <div>
                      <div className="flex justify-between items-start">
                        <span className="text-xs text-slate-400 font-semibold tracking-wide">{metric.name}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                          metric.status === 'Verified' ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/50' :
                          metric.status === 'Corrected' ? 'bg-indigo-950/40 text-indigo-400 border border-indigo-900/50' :
                          'bg-amber-950/40 text-amber-400 border border-amber-900/50'
                        }`}>
                          {metric.status}
                        </span>
                      </div>
                      <div className="text-3xl font-black tracking-tight text-white mt-3">{metric.value}</div>
                    </div>

                    <div className="flex justify-between items-center border-t border-slate-800/60 pt-3 mt-4">
                      <div className="flex items-center gap-1.5">
                        <span className={`text-xs font-bold ${metric.trend === 'up' && metric.name.includes('Debt') ? 'text-red-400' : 'text-emerald-400'}`}>
                          {metric.change}
                        </span>
                      </div>
                      <div className="text-slate-500 group-hover:text-slate-300 text-xs flex items-center gap-1 transition">
                        Details <ChevronRight className="w-3.5 h-3.5" />
                      </div>
                    </div>
                  </div>
                ))}
            </div>

            {/* Data Correction Drawer */}
            {selectedFact && (
              <div className="bg-slate-900 border border-indigo-900/60 rounded-xl p-6 relative">
                <button onClick={() => setSelectedFact(null)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-100">✕</button>
                <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-indigo-400" />
                  Data Correction UX &bull; {selectedFact}
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Verify or edit facts extracted by AI from source filings. Any update triggers automatic synchronous recalculation of all derived KPIs.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
                  <div>
                    <div className="text-xs text-slate-400 uppercase tracking-wide">Current Extracted Fact</div>
                    <div className="text-2xl font-black mt-1 text-white">€178,000,000</div>
                    <div className="text-xs text-indigo-400 mt-2 bg-indigo-950/30 border border-indigo-900/50 px-2 py-1 rounded inline-block">
                      Status: AI-Generated (Unverified)
                    </div>
                  </div>

                  <div className="border-l border-slate-800 pl-6">
                    <div className="text-xs text-slate-400 uppercase tracking-wide">Analyst Override</div>
                    <input type="text" placeholder="Enter corrected value (e.g. 184000000)" className="w-full bg-slate-950 border border-slate-800 focus:border-brand-500 rounded px-3 py-2 text-sm mt-2 text-white focus:outline-none" />
                    <input type="text" placeholder="Reason for change..." className="w-full bg-slate-950 border border-slate-800 focus:border-brand-500 rounded px-3 py-2 text-sm mt-2 text-white focus:outline-none" />
                  </div>

                  <div className="border-l border-slate-800 pl-6 flex flex-col justify-end gap-3">
                    <button className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs px-4 py-2.5 rounded-lg transition">Verify Correct</button>
                    <button className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs px-4 py-2.5 rounded-lg transition">Save Correction</button>
                  </div>
                </div>

                <div className="bg-slate-950 border border-slate-800/80 rounded-lg p-4 mt-6 flex items-start gap-3">
                  <BookOpen className="w-5 h-5 text-brand-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="text-xs font-bold text-slate-300">Evidence Provenance Lineage:</div>
                    <p className="text-xs text-slate-400 mt-1 italic">
                      "...operating income was €184.2M after adjustments (see page 42). Reported EBITDA according to traditional standard definition was €178M..."
                    </p>
                    <div className="text-[10px] text-brand-400 mt-2 font-medium">
                      Filing Source: <a href="#" className="underline hover:text-brand-300">Annual Report 2025 &bull; Section: Finance Highlights &bull; Page 42</a>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </main>

          {/* Right Side: Copilot Panel */}
          <aside className="w-96 border-l border-slate-800 bg-slate-900/30 backdrop-blur-md flex flex-col">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h3 className="font-bold flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-brand-400" />
                Underwriting Copilot
              </h3>
              <span className="text-[9px] bg-slate-800 px-2 py-1 rounded text-slate-400 font-bold uppercase">GPT-4o Ready</span>
            </div>

            <div className="flex-1 p-4 overflow-y-auto space-y-4">
              <div className="bg-slate-800/40 border border-slate-700/30 p-3.5 rounded-lg">
                <p className="text-xs text-slate-300 leading-relaxed">
                  Hello Analyst! I have analyzed <strong>{companyInfo.name}</strong>'s financial history from 2021 to 2025.
                </p>
                <p className="text-xs text-slate-300 leading-relaxed mt-2">
                  The leverage ratio deteriorated to <strong>4.57x</strong> due to rising debt. Ask me questions about specific metrics or evidence.
                </p>
              </div>

              <div className="space-y-2">
                <div className="text-[10px] font-semibold text-slate-500 uppercase">Suggested Prompts</div>
                <button className="w-full text-left bg-slate-850 hover:bg-slate-800 border border-slate-800/80 p-2.5 rounded text-xs text-slate-300 transition flex justify-between items-center group">
                  <span>Why did leverage increase in 2025?</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-300" />
                </button>
                <button className="w-full text-left bg-slate-850 hover:bg-slate-800 border border-slate-800/80 p-2.5 rounded text-xs text-slate-300 transition flex justify-between items-center group">
                  <span>List details of long-term debt items</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-300" />
                </button>
              </div>
            </div>

            <div className="p-4 border-t border-slate-800 bg-slate-950/80">
              <form onSubmit={(e) => { e.preventDefault(); setCopilotQuery(''); }} className="flex gap-2">
                <input
                  type="text"
                  placeholder="Ask Copilot about filings..."
                  value={copilotQuery}
                  onChange={(e) => setCopilotQuery(e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-800 focus:border-brand-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none"
                />
                <button type="submit" className="bg-brand-600 hover:bg-brand-500 text-white p-2 rounded-lg transition">
                  <Send className="w-4 h-4" />
                </button>
              </form>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
