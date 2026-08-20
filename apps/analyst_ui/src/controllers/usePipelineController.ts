import { useState, useEffect, useCallback } from 'react';
import { PipelineJob } from '../models/pipeline';

const API_BASE = ((import.meta as any).env?.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

export function usePipelineController(onPipelineCompleted?: () => void) {
  const [jobs, setJobs] = useState<PipelineJob[]>([]);

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
            setJobs(prev =>
              prev.map(j => (j.id === job.id ? { ...j, state: 'failed', error: err.detail ?? 'Upload failed' } : j))
            );
            return;
          }

          const data = await res.json();
          setJobs(prev =>
            prev.map(j =>
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
            )
          );
        } catch {
          setJobs(prev =>
            prev.map(j => (j.id === job.id ? { ...j, state: 'failed', error: 'Network error — could not reach API' } : j))
          );
        }
      })
    );
  }, []);

  // ── Poll active jobs every 5 seconds ──────────────────────────────────────
  useEffect(() => {
    const pollableJobs = jobs.filter(j => j.dag_run_id && (j.state === 'queued' || j.state === 'running'));

    if (pollableJobs.length === 0) return;

    const poll = async () => {
      let anyCompleted = false;

      await Promise.all(
        pollableJobs.map(async job => {
          if (!job.dag_run_id) return;
          try {
            const res = await fetch(`${API_BASE}/api/pipeline/status/${encodeURIComponent(job.dag_run_id)}`);
            if (!res.ok) return;
            const data = await res.json();

            if (data.state === 'success' && job.state !== 'success') {
              anyCompleted = true;
            }

            setJobs(prev =>
              prev.map(j =>
                j.id === job.id
                  ? {
                      ...j,
                      state: data.state,
                      tasks: data.tasks ?? [],
                    }
                  : j
              )
            );
          } catch {
            // Retry on next interval
          }
        })
      );

      if (anyCompleted && onPipelineCompleted) {
        onPipelineCompleted();
      }
    };

    poll(); // immediate first poll
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, [jobs, onPipelineCompleted]);

  const removeJob = useCallback((id: string) => {
    setJobs(prev => prev.filter(j => j.id !== id));
  }, []);

  const activeJobCount = jobs.filter(
    j => j.state === 'uploading' || j.state === 'queued' || j.state === 'running'
  ).length;

  return {
    jobs,
    activeJobCount,
    handleUpload,
    removeJob,
  };
}
