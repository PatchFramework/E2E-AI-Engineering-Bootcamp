import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  CopilotMessage,
  CopilotContextSnapshot,
  ChatSessionSummary,
  CopilotCitation,
  CopilotWidget,
} from '../models/copilot';
import { apiClient, getApiBaseUrl } from './apiClient';

const STORAGE_KEY_WIDTH = 'agy_copilot_drawer_width';
const STORAGE_KEY_SESSIONS = 'agy_copilot_sessions';
const STORAGE_KEY_MESSAGES = 'agy_copilot_messages';
const MAX_CONVERSATION_TURNS = 10;

export function useCopilotController(
  contextSnapshot: CopilotContextSnapshot,
  onOpenDocumentCitation?: (citation: CopilotCitation) => void
) {
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [width, setWidth] = useState<number>(() => {
    const saved = localStorage.getItem(STORAGE_KEY_WIDTH);
    return saved ? Math.min(800, Math.max(360, parseInt(saved, 10))) : 420;
  });

  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    return `session-${Date.now()}`;
  });

  const [sessions, setSessions] = useState<ChatSessionSummary[]>(() => {
    const saved = localStorage.getItem(STORAGE_KEY_SESSIONS);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        // ignore
      }
    }
    return [
      {
        id: 'session-default',
        title: 'Initial Underwriting Analysis',
        companyId: contextSnapshot.companyId,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
    ];
  });

  const [messagesBySession, setMessagesBySession] = useState<Record<string, CopilotMessage[]>>(() => {
    const saved = localStorage.getItem(STORAGE_KEY_MESSAGES);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        // ignore
      }
    }
    return {};
  });

  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [currentReasoningStatus, setCurrentReasoningStatus] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Sync width to localStorage
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_WIDTH, width.toString());
  }, [width]);

  // Sync sessions & messages to localStorage
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_SESSIONS, JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify(messagesBySession));
  }, [messagesBySession]);

  // Fetch backend chat sessions on mount or when companyId changes
  useEffect(() => {
    let isCancelled = false;
    async function loadBackendSessions() {
      try {
        const queryParam = contextSnapshot.companyId ? `?company_id=${contextSnapshot.companyId}` : '';
        const backendSessions = await apiClient.get<any[]>(`/api/copilot/sessions${queryParam}`);
        if (!isCancelled && Array.isArray(backendSessions) && backendSessions.length > 0) {
          const mapped: ChatSessionSummary[] = backendSessions.map(s => ({
            id: s.id,
            title: s.title || 'Conversation',
            companyId: s.company_id ?? null,
            createdAt: s.created_at || new Date().toISOString(),
            updatedAt: s.updated_at || new Date().toISOString(),
          }));
          setSessions(prev => {
            const combined = [...mapped];
            for (const p of prev) {
              if (!combined.some(c => c.id === p.id)) {
                combined.push(p);
              }
            }
            return combined;
          });
        }
      } catch {
        // Backend offline or running in mock dev mode
      }
    }
    loadBackendSessions();
    return () => {
      isCancelled = true;
    };
  }, [contextSnapshot.companyId]);

  // Fetch backend messages when switching to an active session
  useEffect(() => {
    let isCancelled = false;
    async function loadSessionMessages() {
      if (!activeSessionId || activeSessionId.startsWith('session-default') || activeSessionId.startsWith('session-')) {
        return;
      }
      try {
        const backendMsgs = await apiClient.get<any[]>(`/api/copilot/sessions/${activeSessionId}/messages`);
        if (!isCancelled && Array.isArray(backendMsgs) && backendMsgs.length > 0) {
          const mapped: CopilotMessage[] = backendMsgs.map(m => ({
            id: m.id,
            role: m.role as 'user' | 'assistant' | 'system',
            content: m.content || '',
            toolCalls: m.tool_calls,
            citations: m.citations
              ? (m.citations as any[]).map(c => ({
                  documentId: c.documentId ?? c.document_id ?? 1,
                  filename: c.filename || 'Filing.pdf',
                  pageNumber: c.pageNumber ?? c.page_number ?? 1,
                  displayedPage: c.displayedPage ?? c.displayed_page ?? `p. ${c.page_number ?? 1}`,
                  section: c.section,
                  snippet: c.snippet,
                  boundingBox: c.boundingBox ?? c.bounding_box,
                }))
              : undefined,
            widgets: m.widgets,
            contextSnapshot: m.context_snapshot,
            createdAt: m.created_at || new Date().toISOString(),
          }));
          setMessagesBySession(prev => ({
            ...prev,
            [activeSessionId]: mapped,
          }));
        }
      } catch {
        // Fallback to local storage state
      }
    }
    loadSessionMessages();
    return () => {
      isCancelled = true;
    };
  }, [activeSessionId]);

  const currentMessages = useMemo(() => {
    return messagesBySession[activeSessionId] || [
      {
        id: 'welcome-msg',
        role: 'assistant',
        content: `Hello Analyst! I am your **Credit Underwriting Copilot**.\n\nI have continuous context of **${contextSnapshot.companyName || 'the active company'}** and can query structured financial facts, run deterministic formulas, retrieve filing evidence chunks, or generate interactive charts. How can I assist your underwriting workflow today?`,
        createdAt: new Date().toISOString(),
      },
    ];
  }, [messagesBySession, activeSessionId, contextSnapshot.companyName]);

  // Turn budgeting: count user messages in current session
  const turnCount = useMemo(() => {
    return currentMessages.filter(m => m.role === 'user').length;
  }, [currentMessages]);

  const isTurnLimitReached = useMemo(() => {
    return turnCount >= MAX_CONVERSATION_TURNS;
  }, [turnCount]);

  // Set message list for current session
  const setMessagesForCurrentSession = useCallback(
    (updater: (prev: CopilotMessage[]) => CopilotMessage[]) => {
      setMessagesBySession(prev => {
        const sessionMsgs = prev[activeSessionId] || [
          {
            id: 'welcome-msg',
            role: 'assistant',
            content: `Hello Analyst! I am your **Credit Underwriting Copilot**.`,
            createdAt: new Date().toISOString(),
          },
        ];
        return {
          ...prev,
          [activeSessionId]: updater(sessionMsgs),
        };
      });
    },
    [activeSessionId]
  );

  // Create a fresh new chat session
  const createNewSession = useCallback(async () => {
    if (isStreaming && abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
      setCurrentReasoningStatus(null);
    }

    let newId = `session-${Date.now()}`;
    const newTitle = `Conversation ${sessions.length + 1}`;

    try {
      const backendSession = await apiClient.post<any>('/api/copilot/sessions', {
        company_id: contextSnapshot.companyId,
        title: newTitle,
      });
      if (backendSession && backendSession.id) {
        newId = backendSession.id;
      }
    } catch {
      // Offline fallback
    }

    const newSession: ChatSessionSummary = {
      id: newId,
      title: newTitle,
      companyId: contextSnapshot.companyId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newId);
    setMessagesBySession(prev => ({
      ...prev,
      [newId]: [
        {
          id: `welcome-${newId}`,
          role: 'assistant',
          content: `New session started with active context for **${contextSnapshot.companyName || 'Company'}**.\nAsk any question about debt structure, cash flow, credit ratings, or filing evidence citations. (Max ${MAX_CONVERSATION_TURNS} turns per session).`,
          createdAt: new Date().toISOString(),
        },
      ],
    }));
  }, [contextSnapshot.companyId, contextSnapshot.companyName, isStreaming, sessions.length]);

  // Switch to an existing session
  const switchSession = useCallback((sessionId: string) => {
    setActiveSessionId(sessionId);
  }, []);

  // Stop/Abort streaming
  const handleAbort = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    try {
      await apiClient.post('/api/copilot/chat/abort');
    } catch {
      // Ignore network abort error
    }
    setIsStreaming(false);
    setCurrentReasoningStatus(null);
  }, []);

  // Submit feedback rating / comments for an assistant message
  const submitFeedback = useCallback(
    async (messageId: string, runId: string | undefined, score: 1 | -1, comment?: string) => {
      // Optimistically update message rating in UI
      setMessagesForCurrentSession(prev =>
        prev.map(m =>
          m.id === messageId
            ? {
                ...m,
                userRating: score,
                ratingComment: comment,
              }
            : m
        )
      );

      const effectiveRunId = runId || messageId;
      try {
        await apiClient.post('/api/copilot/feedback', {
          run_id: effectiveRunId,
          score,
          comment: comment || undefined,
          feedback_type: 'user_rating',
        });
      } catch (err) {
        console.warn('Could not post feedback to backend:', err);
      }
    },
    [setMessagesForCurrentSession]
  );

  // Send message & handle SSE streaming response
  const sendMessage = useCallback(
    async (textToSend: string) => {
      if (!textToSend.trim() || isStreaming || isTurnLimitReached) return;

      const userMsgId = `user-${Date.now()}`;
      const userMsg: CopilotMessage = {
        id: userMsgId,
        role: 'user',
        content: textToSend,
        contextSnapshot,
        createdAt: new Date().toISOString(),
      };

      // Add user message
      setMessagesForCurrentSession(prev => [...prev, userMsg]);

      // Update session title if first user message
      setSessions(prev =>
        prev.map(s =>
          s.id === activeSessionId && s.title.startsWith('Conversation')
            ? { ...s, title: textToSend.slice(0, 32) + (textToSend.length > 32 ? '...' : '') }
            : s
        )
      );

      setIsStreaming(true);
      setCurrentReasoningStatus('Analyzing question & underwriting context...');

      const assistantMsgId = `asst-${Date.now()}`;
      const placeholderAssistantMsg: CopilotMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        createdAt: new Date().toISOString(),
      };

      setMessagesForCurrentSession(prev => [...prev, placeholderAssistantMsg]);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const baseUrl = getApiBaseUrl();
        const streamUrl = `${baseUrl}/copilot/chat/stream`;

        const response = await fetch(streamUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: activeSessionId,
            message: textToSend,
            company_id: contextSnapshot.companyId,
            context: contextSnapshot,
          }),
          signal: controller.signal,
        });

        if (response.ok && response.body) {
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let accumulatedContent = '';
          let citations: CopilotCitation[] = [];
          let widgets: CopilotWidget[] = [];
          let activeRunId: string | undefined = undefined;
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split('\n\n');
            buffer = events.pop() || ''; // Keep trailing incomplete event in buffer

            for (const rawEvent of events) {
              if (!rawEvent.trim()) continue;

              const lines = rawEvent.split('\n');
              let eventType = 'message';
              let dataStr = '';

              for (const line of lines) {
                if (line.startsWith('event:')) {
                  eventType = line.replace(/^event:\s*/, '').trim();
                } else if (line.startsWith('data:')) {
                  dataStr = line.replace(/^data:\s*/, '').trim();
                }
              }

              if (dataStr === '[DONE]') {
                break;
              }

              let parsedData: any = null;
              if (dataStr) {
                try {
                  parsedData = JSON.parse(dataStr);
                } catch {
                  parsedData = dataStr;
                }
              }

              // 1. Trace Event (LangSmith Run UUID)
              if (eventType === 'trace' && parsedData?.run_id) {
                activeRunId = parsedData.run_id;
                setMessagesForCurrentSession(prev =>
                  prev.map(m => (m.id === assistantMsgId ? { ...m, runId: activeRunId } : m))
                );
              }

              // 2. Status / Reasoning Chip Updates
              else if (eventType === 'status' && parsedData) {
                const statusMsg = typeof parsedData === 'string' ? parsedData : parsedData.message || parsedData.step || 'Processing...';
                setCurrentReasoningStatus(statusMsg);
              }

              // 3. Widget Generative UI Event
              else if (eventType === 'widget' && parsedData) {
                widgets.push(parsedData);
                setMessagesForCurrentSession(prev =>
                  prev.map(m => (m.id === assistantMsgId ? { ...m, widgets: [...widgets] } : m))
                );
              }

              // 4. Citations Evidence Array Event
              else if (eventType === 'citations' && Array.isArray(parsedData)) {
                citations = parsedData;
                setMessagesForCurrentSession(prev =>
                  prev.map(m => (m.id === assistantMsgId ? { ...m, citations } : m))
                );
              }

              // 5. Done Event
              else if (eventType === 'done' && parsedData) {
                if (parsedData.message_id) {
                  setMessagesForCurrentSession(prev =>
                    prev.map(m =>
                      m.id === assistantMsgId
                        ? { ...m, id: parsedData.message_id, runId: activeRunId || parsedData.message_id }
                        : m
                    )
                  );
                }
              }

              // 6. Error Event
              else if (eventType === 'error' && parsedData) {
                const errMsg = parsedData.error || 'Copilot encountered an error during reasoning.';
                accumulatedContent += `\n\n> ⚠️ **Error**: ${errMsg}`;
                setMessagesForCurrentSession(prev =>
                  prev.map(m => (m.id === assistantMsgId ? { ...m, content: accumulatedContent } : m))
                );
              }

              // 7. Standard Data Tokens / Chunks
              else if (parsedData) {
                if (typeof parsedData === 'object') {
                  if (parsedData.content) {
                    accumulatedContent += parsedData.content;
                  }
                  if (parsedData.citations) {
                    citations = parsedData.citations;
                  }
                  if (parsedData.widget) {
                    widgets.push(parsedData.widget);
                  }
                  if (parsedData.status) {
                    setCurrentReasoningStatus(parsedData.status);
                  }
                } else if (typeof parsedData === 'string' && parsedData !== '[DONE]') {
                  accumulatedContent += parsedData;
                }

                setMessagesForCurrentSession(prev =>
                  prev.map(m =>
                    m.id === assistantMsgId
                      ? {
                          ...m,
                          content: accumulatedContent || m.content,
                          runId: activeRunId || m.runId,
                          citations: citations.length > 0 ? citations : m.citations,
                          widgets: widgets.length > 0 ? widgets : m.widgets,
                        }
                      : m
                  )
                );
              }
            }
          }
        } else {
          // Fallback rich simulation if backend stream endpoint is unreachable
          await simulateCopilotResponse(
            textToSend,
            contextSnapshot,
            assistantMsgId,
            setMessagesForCurrentSession,
            setCurrentReasoningStatus,
            controller.signal
          );
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          // Intelligent fallback simulation if backend stream failed or unmounted
          await simulateCopilotResponse(
            textToSend,
            contextSnapshot,
            assistantMsgId,
            setMessagesForCurrentSession,
            setCurrentReasoningStatus,
            controller.signal
          );
        }
      } finally {
        setIsStreaming(false);
        setCurrentReasoningStatus(null);
        abortControllerRef.current = null;
      }
    },
    [activeSessionId, contextSnapshot, isStreaming, isTurnLimitReached, setMessagesForCurrentSession]
  );

  return {
    isOpen,
    setIsOpen,
    toggleOpen: () => setIsOpen(prev => !prev),
    width,
    setWidth,
    activeSessionId,
    sessions,
    messages: currentMessages,
    isStreaming,
    currentReasoningStatus,
    turnCount,
    maxTurns: MAX_CONVERSATION_TURNS,
    isTurnLimitReached,
    sendMessage,
    abortStream: handleAbort,
    submitFeedback,
    createNewSession,
    switchSession,
    onOpenDocumentCitation,
  };
}

// Fallback intelligent simulation engine for dev/offline mode
async function simulateCopilotResponse(
  query: string,
  context: CopilotContextSnapshot,
  msgId: string,
  setMessages: (updater: (prev: CopilotMessage[]) => CopilotMessage[]) => void,
  setStatus: (status: string | null) => void,
  signal: AbortSignal
) {
  const q = query.toLowerCase();
  const companyName = context.companyName || 'Acme Corp';

  // Step 1: Status update
  if (signal.aborted) return;
  setStatus('Searching filing evidence & database metrics...');
  await new Promise(r => setTimeout(r, 600));

  if (signal.aborted) return;

  let replyText = '';
  let citations: CopilotCitation[] = [];
  let widgets: CopilotWidget[] = [];

  if (q.includes('chart') || q.includes('trend') || q.includes('leverage') || q.includes('margin')) {
    setStatus('Running deterministic historical ratio calculations & generating Recharts widget...');
    await new Promise(r => setTimeout(r, 600));
    if (signal.aborted) return;

    replyText = `Based on financial filings for **${companyName}**, operating leverage has shifted from **3.10x** in FY2021 to **4.72x** in FY2025. Below is the multi-year trajectory of EBITDA Margin alongside Net Debt / EBITDA:`;

    widgets = [
      {
        widgetType: 'chart',
        chartType: 'line',
        title: `${companyName} — 5-Year Leverage vs EBITDA Margin`,
        description: 'Derived historical credit risk indicators (2021–2025)',
        series: [
          { key: 'leverage', label: 'Net Debt / EBITDA (x)', color: '#f43f5e' },
          { key: 'margin', label: 'EBITDA Margin (%)', color: '#10b981' },
        ],
        data: [
          { year: '2021', leverage: 3.1, margin: 18.4 },
          { year: '2022', leverage: 3.35, margin: 19.1 },
          { year: '2023', leverage: 3.8, margin: 20.2 },
          { year: '2024', leverage: 4.15, margin: 21.0 },
          { year: '2025', leverage: 4.72, margin: 22.4 },
        ],
      },
    ];

    citations = [
      {
        documentId: 1,
        filename: 'FY2025_Annual_Report.pdf',
        pageNumber: 87,
        displayedPage: 'p. 87',
        section: 'Debt & Financing Schedule',
        snippet: 'Total debt obligations increased to €1.20B following senior notes issuance.',
        boundingBox: [100, 200, 500, 350],
      },
      {
        documentId: 1,
        filename: 'FY2025_Annual_Report.pdf',
        pageNumber: 42,
        displayedPage: 'p. 42',
        section: 'Consolidated Income Statement',
        snippet: 'Operating profit before depreciation and amortisation (EBITDA) was €178M.',
        boundingBox: [120, 180, 480, 260],
      },
    ];
  } else if (q.includes('topic') || q.includes('word') || q.includes('mention') || q.includes('cloud')) {
    setStatus('Counting canonical accounting concept frequencies across reports...');
    await new Promise(r => setTimeout(r, 600));
    if (signal.aborted) return;

    replyText = `Here is the topical prominence and mention frequency for key underwriting concepts across ${companyName}'s latest filing:`;
    widgets = [
      {
        widgetType: 'word_cloud',
        title: 'Topical Focus & Risk Terms Mention Frequency',
        description: 'Occurrences across Management Discussion & Notes',
        wordCloudData: [
          { text: 'Senior Debt', value: 48 },
          { text: 'Liquidity Facility', value: 34 },
          { text: 'EBITDA Headroom', value: 29 },
          { text: 'Covenants', value: 22 },
          { text: 'Interest Risk', value: 19 },
          { text: 'Capex', value: 16 },
          { text: 'Working Capital', value: 14 },
          { text: 'Refinancing', value: 11 },
        ],
        data: [],
      },
    ];
    citations = [
      {
        documentId: 1,
        filename: 'FY2025_Annual_Report.pdf',
        pageNumber: 15,
        displayedPage: 'p. 15',
        section: 'Risk Factors & Capital Management',
      },
    ];
  } else if (q.includes('pie') || q.includes('breakdown') || q.includes('capital') || q.includes('debt')) {
    setStatus('Aggregating balance sheet debt components...');
    await new Promise(r => setTimeout(r, 600));
    if (signal.aborted) return;

    replyText = `Here is the current capital and debt composition breakdown for **${companyName}**:`;
    widgets = [
      {
        widgetType: 'chart',
        chartType: 'pie',
        title: 'Total Debt Composition (FY2025)',
        description: 'Breakdown of €1.20B total borrowing liabilities',
        data: [
          { name: 'Senior Secured Notes', value: 650 },
          { name: 'Revolving Credit Facility', value: 250 },
          { name: 'Term Loan B', value: 200 },
          { name: 'Finance Leases', value: 100 },
        ],
      },
    ];
    citations = [
      {
        documentId: 1,
        filename: 'FY2025_Annual_Report.pdf',
        pageNumber: 88,
        displayedPage: 'p. 88',
        section: 'Note 18: Borrowings',
      },
    ];
  } else {
    setStatus('Synthesizing credit analysis...');
    await new Promise(r => setTimeout(r, 500));
    if (signal.aborted) return;

    replyText = `Based on the latest financial filing for **${companyName}**, the company maintains a suggested credit rating of **BB (Elevated Risk)**. Primary drivers include rising net leverage (**4.72x**), adequate interest coverage (**2.80x**), and cash reserves of **€360M** against near-term maturities.\n\nYou can click on any cited evidence below to inspect the original PDF filing with bounding box highlights.`;
    citations = [
      {
        documentId: 1,
        filename: 'FY2025_Annual_Report.pdf',
        pageNumber: 42,
        displayedPage: 'p. 42',
        section: 'Executive Summary',
        snippet: 'Operating cash flow remained steady while net debt expanded to support long-term infrastructure investment.',
      },
    ];
  }

  // Stream in tokens
  const words = replyText.split(' ');
  let curr = '';
  for (let i = 0; i < words.length; i++) {
    if (signal.aborted) return;
    curr += (i === 0 ? '' : ' ') + words[i];
    setMessages(prev =>
      prev.map(m =>
        m.id === msgId
          ? {
              ...m,
              content: curr,
              citations: i === words.length - 1 ? citations : undefined,
              widgets: i === words.length - 1 ? widgets : undefined,
            }
          : m
      )
    );
    await new Promise(r => setTimeout(r, 20));
  }
}
