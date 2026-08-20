import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  CloudUpload,
  FileText,
  ArrowRight,
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  CheckCheck,
  ChevronDown,
  X,
  Upload,
  AlertTriangle,
  Building2,
} from 'lucide-react';
import { PipelineJob, TASK_STEPS } from '../models/pipeline';

interface UploadViewProps {
  jobs: PipelineJob[];
  onUpload: (files: FileList) => void;
  onRemoveJob: (id: string) => void;
}

function stateColor(state: string | null | undefined) {
  switch (state) {
    case 'success':
      return 'text-emerald-400';
    case 'running':
      return 'text-brand-400';
    case 'failed':
    case 'upstream_failed':
      return 'text-rose-400';
    default:
      return 'text-slate-500';
  }
}

function stateBg(state: string | null | undefined) {
  switch (state) {
    case 'success':
      return 'bg-emerald-950/50 border-emerald-900/50';
    case 'running':
      return 'bg-brand-950/50 border-brand-900/50 animate-pulse';
    case 'failed':
    case 'upstream_failed':
      return 'bg-rose-950/40 border-rose-900/50';
    default:
      return 'bg-slate-900/40 border-slate-800/60';
  }
}

function overallBadge(state: PipelineJob['state']) {
  if (state === 'uploading')
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-sky-400 bg-sky-950/40 border border-sky-900/50 px-2.5 py-0.5 rounded-full">
        <Loader2 className="w-3 h-3 animate-spin" /> Uploading
      </span>
    );
  if (state === 'queued')
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 bg-slate-800/60 border border-slate-700/50 px-2.5 py-0.5 rounded-full">
        <Clock className="w-3 h-3" /> Queued
      </span>
    );
  if (state === 'running')
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-brand-400 bg-brand-950/40 border border-brand-900/50 px-2.5 py-0.5 rounded-full animate-pulse">
        <Activity className="w-3 h-3" /> Processing
      </span>
    );
  if (state === 'success')
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-950/40 border border-emerald-900/50 px-2.5 py-0.5 rounded-full">
        <CheckCircle className="w-3 h-3" /> Complete
      </span>
    );
  if (state === 'failed')
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-rose-400 bg-rose-950/40 border border-rose-900/50 px-2.5 py-0.5 rounded-full">
        <XCircle className="w-3 h-3" /> Failed
      </span>
    );
  return null;
}

function JobCard({ job, onRemove }: { job: PipelineJob; onRemove: () => void }) {
  const [expanded, setExpanded] = useState(job.state === 'running' || job.state === 'failed');

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
      const runningTasks = job.tasks.filter(t => t.state === 'running');
      if (runningTasks.length > 0) {
        const names = runningTasks.map(t => TASK_STEPS.find(s => s.id === t.task_id)?.label || t.task_id);
        return `Currently running: ${names.join(', ')}`;
      }
      return 'Processing pipeline tasks...';
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
    <div
      className={`rounded-2xl border transition-all duration-500 overflow-hidden ${
        job.state === 'failed'
          ? 'border-rose-900/60 bg-rose-950/10'
          : job.state === 'success'
          ? 'border-emerald-900/60 bg-emerald-950/10'
          : 'border-slate-800/80 bg-slate-900/50'
      }`}
    >
      {/* Card Header */}
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
              {job.fiscal_year && (
                <span>
                  {job.document_type} {job.fiscal_year} {job.fiscal_period}
                </span>
              )}
            </div>
          )}

          {statusMessage && (
            <div
              className={`text-xs mt-2 flex items-center gap-1.5 ${
                job.state === 'failed'
                  ? 'text-rose-400 font-medium'
                  : job.state === 'success'
                  ? 'text-emerald-400'
                  : 'text-slate-300'
              }`}
            >
              {job.state === 'running' && <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-400" />}
              {job.state === 'failed' && <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />}
              {job.state === 'success' && <CheckCheck className="w-3.5 h-3.5 text-emerald-400" />}
              <span>{statusMessage}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {job.dag_run_id && job.state !== 'uploading' && (
            <button
              onClick={() => setExpanded(e => !e)}
              className="text-slate-400 hover:text-slate-200 transition"
            >
              <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </button>
          )}
          {(job.state === 'success' || job.state === 'failed' || job.error) && (
            <button onClick={onRemove} className="text-slate-500 hover:text-slate-200 transition">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      {job.state !== 'uploading' && job.dag_run_id && (
        <div className="px-4 pb-1">
          <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ease-out ${
                job.state === 'failed'
                  ? 'bg-rose-500'
                  : job.state === 'success'
                  ? 'bg-emerald-500'
                  : 'bg-brand-500'
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Task Step Breakdown */}
      {expanded && job.dag_run_id && (
        <div className="px-4 pb-4 pt-2 space-y-2">
          {TASK_STEPS.map(step => {
            const taskStatus = job.tasks.find(t => t.task_id === step.id);
            const state = taskStatus?.state ?? 'queued';
            return (
              <div
                key={step.id}
                className={`flex items-center gap-3 rounded-xl px-3 py-2 border ${stateBg(state)}`}
              >
                <div className="w-5 h-5 flex-shrink-0">
                  {state === 'success' && <CheckCheck className="w-5 h-5 text-emerald-400" />}
                  {state === 'running' && <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />}
                  {(state === 'failed' || state === 'upstream_failed') && (
                    <XCircle className="w-5 h-5 text-rose-400" />
                  )}
                  {(state === 'queued' || state === 'skipped' || !taskStatus) && (
                    <Clock className="w-5 h-5 text-slate-600" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className={`text-xs font-semibold ${stateColor(state)}`}>{step.label}</div>
                  <div className="text-[10px] text-slate-400">{step.description}</div>
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

export const UploadView: React.FC<UploadViewProps> = ({ jobs, onUpload, onRemoveJob }) => {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (e.dataTransfer.files.length > 0) onUpload(e.dataTransfer.files);
    },
    [onUpload]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback(() => setDragActive(false), []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) onUpload(e.target.files);
      e.target.value = '';
    },
    [onUpload]
  );

  const activeJobs = jobs.filter(
    j => j.state === 'running' || j.state === 'uploading' || j.state === 'queued'
  );
  const completedJobs = jobs.filter(j => j.state === 'success' || j.state === 'failed');

  return (
    <div className="flex-1 p-6 overflow-y-auto max-w-3xl mx-auto space-y-8 py-6">
      {/* View Header */}
      <div>
        <h2 className="text-2xl font-extrabold tracking-tight text-white">Upload Filing</h2>
        <p className="text-sm text-slate-400 mt-1">
          Upload annual reports, 10-Ks, or 10-Qs. The AI pipeline will extract financial facts and compute credit KPIs automatically.
        </p>
      </div>

      {/* Drag & Drop Dropzone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-3xl p-12 flex flex-col items-center justify-center gap-4 cursor-pointer transition-all duration-200 select-none ${
          dragActive
            ? 'border-brand-400 bg-brand-950/20 scale-[1.01]'
            : 'border-slate-800 hover:border-slate-700 bg-slate-900/30 hover:bg-slate-900/50'
        }`}
      >
        <div className={`p-5 rounded-2xl transition-all ${dragActive ? 'bg-brand-900/40' : 'bg-slate-800/40'}`}>
          <CloudUpload className={`w-12 h-12 ${dragActive ? 'text-brand-400' : 'text-slate-400'}`} />
        </div>

        <div className="text-center">
          <p className="text-base font-semibold text-slate-100">
            {dragActive ? 'Drop filing to upload' : 'Drag & drop filing PDFs here'}
          </p>
          <p className="text-sm text-slate-400 mt-1">
            or <span className="text-brand-400 underline underline-offset-2">browse files</span>
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-900/80 px-4 py-2 rounded-xl border border-slate-800">
          <FileText className="w-3.5 h-3.5" />
          Supported: PDF · Max 50 MB · Multi-file supported
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

      {/* Pipeline Steps Strip */}
      <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-5">
        <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3">
          Airflow Data Pipeline Architecture
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {TASK_STEPS.map((step, i) => (
            <div key={step.id} className="flex items-center gap-2">
              <div className="text-xs text-slate-300 bg-slate-800/60 border border-slate-700/60 px-3 py-1.5 rounded-lg font-medium">
                {step.label}
              </div>
              {i < TASK_STEPS.length - 1 && <ArrowRight className="w-3.5 h-3.5 text-slate-600" />}
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-500 mt-3 leading-relaxed">
          Uploads execute asynchronously without blocking the UI. You can monitor task status live or navigate to the dashboard.
        </p>
      </div>

      {/* Active Pipeline Jobs */}
      {activeJobs.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-brand-400 animate-pulse" />
            <h3 className="text-sm font-bold text-slate-200">Active Ingestion Pipelines</h3>
            <span className="text-[11px] font-bold text-brand-400 bg-brand-950/60 border border-brand-800/50 px-2.5 py-0.5 rounded-full">
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

      {/* Completed Jobs */}
      {completedJobs.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-bold text-slate-400">Completed Jobs</h3>
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
          <p className="text-sm">No filings uploaded yet in this session</p>
        </div>
      )}
    </div>
  );
};
