import { MetricItem } from './metric';
import { FinancialFact } from './fact';

export interface CopilotCitation {
  documentId: number;
  filename: string;
  pageNumber: number;       // 1-based physical page
  displayedPage: string;    // e.g. "p. 42"
  section?: string;
  snippet?: string;
  boundingBox?: [number, number, number, number]; // [x0, y0, x1, y1]
}

export interface ChartSeriesConfig {
  key: string;
  label: string;
  color?: string;
  yAxis?: 'left' | 'right';
}

export interface WordCloudItem {
  text: string;
  value: number;
}

export interface CopilotWidget {
  widgetType: 'chart' | 'word_cloud' | 'table';
  chartType?: 'line' | 'bar' | 'pie';
  title: string;
  description?: string;
  unit?: string;
  series?: ChartSeriesConfig[];
  data?: Record<string, any>[];
  columns?: string[];
  rows?: Record<string, any>[];
  wordCloudData?: WordCloudItem[];
}

export interface CopilotContextSnapshot {
  currentView: 'dashboard' | 'upload';
  companyId: number | null;
  companyName?: string;
  activeMetric?: MetricItem | null;
  activeFacts?: FinancialFact[];
  activeDocuments?: {
    documentId: number;
    filename?: string;
    pageNumber: number;
    displayedPage: string;
    snippet?: string;
    boundingBox?: [number, number, number, number];
  }[];
}

export interface CopilotMessage {
  id: string;
  runId?: string; // LangSmith execution trace ID
  role: 'user' | 'assistant' | 'system';
  content: string;
  status?: string; // Live reasoning state during stream
  toolCalls?: { tool: string; args: Record<string, any> }[];
  citations?: CopilotCitation[];
  widgets?: CopilotWidget[];
  contextSnapshot?: CopilotContextSnapshot;
  userRating?: 1 | -1 | null;
  ratingComment?: string;
  createdAt: string;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  companyId: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface FeedbackSubmission {
  runId: string;
  score: 1 | -1 | 0;
  comment?: string;
  feedbackType?: string;
}

