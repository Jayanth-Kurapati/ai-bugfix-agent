import { useState, useCallback, useRef, useEffect } from 'react';

const API_BASE = '/api';
const TERMINAL_STATUSES = new Set(['verified', 'failed', 'blocked', 'model_unavailable']);

/**
 * Robust custom hook for job submission, live SSE streaming, and resilient polling fallback.
 *
 * Guaranteed Behaviors:
 * - Failed submission keeps phase in 'idle' with submitError, NEVER unmounting the form.
 * - Stale job updates are discarded via currentJobIdRef guarding.
 * - Parse failures on 'final' event fallback to GET /api/jobs/{id} to recover the final state.
 * - Cleanup is guaranteed on unmount, terminal status, or reset.
 */
export function useJobStream() {
  const [state, setState] = useState({
    phase: 'idle',       // idle | submitting | streaming | done
    jobId: null,
    status: null,        // queued | running | verified | failed | blocked | model_unavailable
    events: [],          // array of trace event objects
    finalJob: null,      // full final JobResponse
    error: null,         // runtime / execution / judge error
    submitError: null,   // validation / network error before job starts
    iterationCount: 0,
    llmCallCount: 0,
  });

  const eventSourceRef = useRef(null);
  const pollingRef = useRef(null);
  const currentJobIdRef = useRef(null);

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

  // Guarantee cleanup on hook unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  const fetchJobDirectly = useCallback(async (jobId) => {
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}`);
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }, []);

  const startPollingFallback = useCallback((jobId) => {
    if (pollingRef.current) return;
    pollingRef.current = setInterval(async () => {
      // Guard against stale job
      if (currentJobIdRef.current !== jobId) {
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
        return;
      }

      try {
        const data = await fetchJobDirectly(jobId);
        if (!data) return;

        // Verify still current
        if (currentJobIdRef.current !== jobId) return;

        const isTerminal = TERMINAL_STATUSES.has(data.status);
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
          error: data.error || prev.error,
          ...(isTerminal ? {
            phase: 'done',
            finalJob: data,
          } : {}),
        }));

        if (isTerminal) {
          cleanup();
        }
      } catch {
        // Retry silently on network jitter
      }
    }, 2500);
  }, [cleanup, fetchJobDirectly]);

  const connectSSE = useCallback((jobId) => {
    cleanup();
    const es = new EventSource(`${API_BASE}/jobs/${jobId}/stream`);
    eventSourceRef.current = es;

    es.addEventListener('trace', (e) => {
      if (currentJobIdRef.current !== jobId) return;
      try {
        const event = JSON.parse(e.data);
        setState(prev => {
          if (currentJobIdRef.current !== jobId) return prev;
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
        // Skip malformed trace frame
      }
    });

    es.addEventListener('final', async (e) => {
      if (currentJobIdRef.current !== jobId) return;
      let job = null;
      try {
        job = JSON.parse(e.data);
      } catch {
        // Fallback to fetch API directly to recover authoritative final state
        job = await fetchJobDirectly(jobId);
      }

      if (currentJobIdRef.current !== jobId) return;

      if (job) {
        setState(prev => ({
          ...prev,
          phase: 'done',
          status: job.status,
          finalJob: job,
          llmCallCount: job.llm_call_count ?? prev.llmCallCount,
          iterationCount: job.iteration_count ?? prev.iterationCount,
          error: job.error ?? null,
        }));
      } else {
        // If recovery still failed, poll once
        startPollingFallback(jobId);
      }
      cleanup();
    });

    es.onerror = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      // Fall back immediately to polling
      if (currentJobIdRef.current === jobId) {
        startPollingFallback(jobId);
      }
    };
  }, [cleanup, fetchJobDirectly, startPollingFallback]);

  const submit = useCallback(async (payload) => {
    cleanup();
    const tempId = 'pending-' + Date.now();
    currentJobIdRef.current = tempId;

    setState(prev => ({
      ...prev,
      phase: 'submitting',
      jobId: null,
      status: null,
      events: [],
      finalJob: null,
      error: null,
      submitError: null,
      iterationCount: 0,
      llmCallCount: 0,
    }));

    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      // Guard: user may have clicked reset during fetch
      if (currentJobIdRef.current !== tempId) return;

      if (!res.ok) {
        const errorBody = await res.json().catch(() => ({}));
        const detail = errorBody.detail;
        let message;
        if (Array.isArray(detail)) {
          message = detail.map(d => d.msg || JSON.stringify(d)).join('; ');
        } else {
          message = detail || `Submission failed with status ${res.status}.`;
        }

        // CRITICAL P0 FIX: keep phase in 'idle' so form remains visible with inputs preserved
        setState(prev => ({
          ...prev,
          phase: 'idle',
          submitError: message,
        }));
        return;
      }

      const { job_id } = await res.json();
      if (currentJobIdRef.current !== tempId) return;

      currentJobIdRef.current = job_id;
      setState(prev => ({
        ...prev,
        phase: 'streaming',
        jobId: job_id,
        status: 'queued',
        submitError: null,
      }));

      connectSSE(job_id);
    } catch (err) {
      if (currentJobIdRef.current !== tempId) return;

      // CRITICAL P0 FIX: keep phase in 'idle' on network error
      setState(prev => ({
        ...prev,
        phase: 'idle',
        submitError: `Network error: ${err.message || 'Unable to reach the server. Check your connection.'}`,
      }));
    }
  }, [cleanup, connectSSE]);

  const reset = useCallback(() => {
    currentJobIdRef.current = null;
    cleanup();
    setState({
      phase: 'idle',
      jobId: null,
      status: null,
      events: [],
      finalJob: null,
      error: null,
      submitError: null,
      iterationCount: 0,
      llmCallCount: 0,
    });
  }, [cleanup]);

  const clearSubmitError = useCallback(() => {
    setState(prev => ({ ...prev, submitError: null }));
  }, []);

  return {
    ...state,
    submit,
    reset,
    clearSubmitError,
  };
}
