import { useState, useCallback, useRef } from 'react';

/**
 * Custom hook for job submission and SSE streaming.
 *
 * Flow:
 * 1. POST /api/analyze → { job_id }
 * 2. EventSource on /api/jobs/{id}/stream
 * 3. Parse "trace" and "final" SSE events
 * 4. Polling fallback via GET /api/jobs/{id}
 */

const API_BASE = '/api';

const TERMINAL_STATUSES = new Set(['verified', 'failed', 'blocked', 'model_unavailable']);

export function useJobStream() {
  const [state, setState] = useState({
    phase: 'idle',       // idle | submitting | streaming | done
    jobId: null,
    status: null,        // queued | running | verified | failed | blocked
    events: [],          // array of trace event objects
    finalJob: null,      // full final JobResponse
    error: null,
    iterationCount: 0,
    llmCallCount: 0,
  });

  const eventSourceRef = useRef(null);
  const pollingRef = useRef(null);

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPollingFallback = useCallback((jobId) => {
    if (pollingRef.current) return;
    pollingRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/jobs/${jobId}`);
        if (!res.ok) return;
        const data = await res.json();
        setState(prev => ({
          ...prev,
          status: data.status,
          events: (data.trace || []).map(e => ({
            kind: e.kind,
            message: e.message,
            data: e.data || {},
          })),
          iterationCount: data.iteration_count || 0,
          llmCallCount: data.llm_call_count || 0,
          ...(TERMINAL_STATUSES.has(data.status) ? {
            phase: 'done',
            finalJob: data,
          } : {}),
        }));
        if (TERMINAL_STATUSES.has(data.status)) {
          cleanup();
        }
      } catch {
        // silent retry
      }
    }, 3000);
  }, [cleanup]);

  const connectSSE = useCallback((jobId) => {
    const es = new EventSource(`${API_BASE}/jobs/${jobId}/stream`);
    eventSourceRef.current = es;

    es.addEventListener('trace', (e) => {
      try {
        const event = JSON.parse(e.data);
        setState(prev => {
          const newEvents = [...prev.events, event];
          let iterationCount = prev.iterationCount;
          if (event.kind === 'HYPOTHESIS') {
            iterationCount += 1;
          }
          return {
            ...prev,
            phase: 'streaming',
            status: 'running',
            events: newEvents,
            iterationCount,
          };
        });
      } catch {
        // malformed event, skip
      }
    });

    es.addEventListener('final', (e) => {
      try {
        const job = JSON.parse(e.data);
        setState(prev => ({
          ...prev,
          phase: 'done',
          status: job.status,
          finalJob: job,
          llmCallCount: job.llm_call_count || 0,
          iterationCount: job.iteration_count || prev.iterationCount,
        }));
      } catch {
        // malformed
      }
      cleanup();
    });

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;
      // Fall back to polling
      startPollingFallback(jobId);
    };
  }, [cleanup, startPollingFallback]);

  const submit = useCallback(async (payload) => {
    cleanup();
    setState({
      phase: 'submitting',
      jobId: null,
      status: null,
      events: [],
      finalJob: null,
      error: null,
      iterationCount: 0,
      llmCallCount: 0,
    });

    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorBody = await res.json().catch(() => ({}));
        const detail = errorBody.detail;
        let message;
        if (Array.isArray(detail)) {
          message = detail.map(d => d.msg || JSON.stringify(d)).join('; ');
        } else {
          message = detail || `Request failed (${res.status})`;
        }
        setState(prev => ({
          ...prev,
          phase: 'done',
          status: 'failed',
          error: message,
        }));
        return;
      }

      const { job_id } = await res.json();
      setState(prev => ({
        ...prev,
        phase: 'streaming',
        jobId: job_id,
        status: 'queued',
      }));
      connectSSE(job_id);
    } catch (err) {
      setState(prev => ({
        ...prev,
        phase: 'done',
        status: 'failed',
        error: `Network error: ${err.message}`,
      }));
    }
  }, [cleanup, connectSSE]);

  const reset = useCallback(() => {
    cleanup();
    setState({
      phase: 'idle',
      jobId: null,
      status: null,
      events: [],
      finalJob: null,
      error: null,
      iterationCount: 0,
      llmCallCount: 0,
    });
  }, [cleanup]);

  return { ...state, submit, reset };
}
