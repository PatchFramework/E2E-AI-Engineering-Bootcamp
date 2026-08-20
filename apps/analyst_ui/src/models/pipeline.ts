export type DagState = 'queued' | 'running' | 'success' | 'failed' | null;

export interface TaskStatus {
  task_id: string;
  state: string;
  start_date: string | null;
  end_date: string | null;
}

export interface PipelineJob {
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

export interface PipelineStepConfig {
  id: string;
  label: string;
  description: string;
}

export const TASK_STEPS: PipelineStepConfig[] = [
  { id: 'parse_pdf', label: 'Parse PDF', description: 'Extract text, tables & page images' },
  { id: 'extract_facts', label: 'Extract Facts', description: 'AI financial concept extraction' },
  { id: 'index_chunks', label: 'Index Chunks', description: 'Vector embeddings to pgvector' },
  { id: 'validate_facts', label: 'Validate', description: 'Accounting rule consistency check' },
  { id: 'calculate_kpis', label: 'Calculate KPIs', description: 'Derive credit metrics' },
];
