import { useRef, useCallback } from 'react';
import {
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Unplug,
  ExternalLink,
  RefreshCw,
} from 'lucide-react';
import { useJobStream } from './hooks/useJobStream';
import InputForm from './components/InputForm';
import TraceView from './components/TraceView';
import DiffView from './components/DiffView';
import StatusBar from './components/StatusBar';
import logoMark from './assets/logo-mark.svg';
import './App.css';

export default function App() {
  const {
    phase,
    status,
    events,
    finalJob,
    error,
    submitError,
    iterationCount,
    llmCallCount,
    submit,
    reset,
    clearSubmitError,
  } = useJobStream();

  const lastSubmittedPayloadRef = useRef(null);

  const handleSubmit = useCallback((payload) => {
    lastSubmittedPayloadRef.current = payload;
    submit(payload);
  }, [submit]);

  const handleRetry = useCallback(() => {
    if (lastSubmittedPayloadRef.current) {
      submit(lastSubmittedPayloadRef.current);
    }
  }, [submit]);

  const handleBrandClick = (e) => {
    e.preventDefault();
    reset();
  };

  const isActive = phase === 'submitting' || phase === 'streaming';
  const isDone = phase === 'done';

  // Derive diff: prefer finalJob.diff, fall back to patch event data if available
  const diff = finalJob?.diff || null;

  // Derive root cause hypothesis from trace events
  const hypothesisEvent = events?.find(e => e.kind === 'HYPOTHESIS');
  const rootCause = hypothesisEvent ? hypothesisEvent.message : null;

  return (
    <div className="app">
      {/* Developer Tool Navigation Header */}
      <header className="app-header" id="app-header">
        <div className="header-container">
          <div className="brand-cluster">
            <a
              href="/"
              className="brand-link"
              onClick={handleBrandClick}
              title="BugFixAgent Home — Reset Workstation"
              aria-label="BugFixAgent Home"
            >
              <div className="logo-box" aria-hidden="true">
                <img src={logoMark} alt="" className="logo-icon" width="22" height="22" />
              </div>
              <span className="brand-name">BugFixAgent</span>
            </a>

            <div className="brand-divider" aria-hidden="true" />

            <p className="tagline">
              Diagnose, patch, and verify Python bugs with an AI agent.
            </p>
          </div>

          <div className="header-actions">
            <a
              href="https://github.com/Jayanth-Kurapati/ai-bugfix-agent"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost btn-sm header-link"
              title="View repository on GitHub"
            >
              <span>GitHub</span>
              <ExternalLink size={12} aria-hidden="true" />
            </a>

            {/* Stable Reset / New Analysis Action */}
            {(isDone || isActive) && (
              <button
                type="button"
                className="btn btn-secondary btn-sm new-analysis-btn"
                onClick={reset}
                id="new-analysis-btn"
                title="Clear current run and return to clean analysis state"
              >
                <RotateCcw size={12} aria-hidden="true" />
                <span>New Analysis</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Workstation Body */}
      <main className="app-main">
        {/* Input Form — Always visible when idle, submitting, or when submission error occurs */}
        {(phase === 'idle' || phase === 'submitting') && (
          <section className="section-center" aria-label="Bug submission input">
            <InputForm
              onSubmit={handleSubmit}
              disabled={isActive}
              isSubmitting={phase === 'submitting'}
              submitError={submitError}
              onClearError={clearSubmitError}
            />
          </section>
        )}

        {/* Live Execution Telemetry Bar */}
        {(isActive || isDone) && (
          <section className="section-fullwidth" aria-label="Agent execution status">
            <StatusBar
              status={status}
              events={events}
              iterationCount={iterationCount}
              llmCallCount={isDone && finalJob ? finalJob.llm_call_count : llmCallCount}
              error={error}
              onRetry={handleRetry}
            />
          </section>
        )}

        {/* Workstation Results Area */}
        {(phase === 'streaming' || isDone) && (
          <div className="results-grid">
            {/* 1. Primary Final Verdict Card (dominant result state) */}
            {isDone && finalJob && (
              <section className="verdict-banner-card surface-card animate-fade-in" id="summary-card" aria-label="Final verification result">
                <div className="verdict-header">
                  <div className="verdict-title-group">
                    {status === 'verified' && (
                      <>
                        <div className="verdict-icon-box status-verified-box" aria-hidden="true">
                          <CheckCircle2 size={22} className="color-success" />
                        </div>
                        <div>
                          <h2 className="verdict-title">Bug Fixed & Verified</h2>
                          <p className="verdict-subtitle">
                            The candidate patch successfully passed sandboxed test execution and the judge confirmed the fix.
                          </p>
                        </div>
                      </>
                    )}
                    {status === 'blocked' && (
                      <>
                        <div className="verdict-icon-box status-blocked-box" aria-hidden="true">
                          <AlertTriangle size={22} className="color-warning" />
                        </div>
                        <div>
                          <h2 className="verdict-title">Verification Blocked by Host Sandbox</h2>
                          <p className="verdict-subtitle">
                            A patch was generated, but test execution is blocked on this host environment. The patch is unverified.
                          </p>
                        </div>
                      </>
                    )}
                    {status === 'failed' && (
                      <>
                        <div className="verdict-icon-box status-failed-box" aria-hidden="true">
                          <XCircle size={22} className="color-error" />
                        </div>
                        <div>
                          <h2 className="verdict-title">Verification Failed</h2>
                          <p className="verdict-subtitle">
                            The candidate patch failed sandboxed test execution or judge verification.
                          </p>
                        </div>
                      </>
                    )}
                    {status === 'model_unavailable' && (
                      <>
                        <div className="verdict-icon-box status-failed-box" aria-hidden="true">
                          <Unplug size={22} className="color-error" />
                        </div>
                        <div>
                          <h2 className="verdict-title">Model Service Unavailable</h2>
                          <p className="verdict-subtitle">
                            Free-tier LLM models are currently rate-limited or in rotation on OpenRouter. Please retry in a moment.
                          </p>
                        </div>
                      </>
                    )}
                    {status === 'verification_inconclusive' && (
                      <>
                        <div className="verdict-icon-box status-blocked-box" aria-hidden="true">
                          <AlertTriangle size={22} className="color-warning" />
                        </div>
                        <div>
                          <h2 className="verdict-title">Verification Inconclusive</h2>
                          <p className="verdict-subtitle">
                            The reported failure could not be deterministically reproduced in the verification environment.
                          </p>
                        </div>
                      </>
                    )}
                    {status === 'repository_error' && (
                      <>
                        <div className="verdict-icon-box status-failed-box" aria-hidden="true">
                          <XCircle size={22} className="color-error" />
                        </div>
                        <div>
                          <h2 className="verdict-title">Repository Error</h2>
                          <p className="verdict-subtitle">
                            The repository could not be cloned or processed. Please verify repository URL and visibility.
                          </p>
                        </div>
                      </>
                    )}
                    {status === 'invalid_input' && (
                      <>
                        <div className="verdict-icon-box status-failed-box" aria-hidden="true">
                          <XCircle size={22} className="color-error" />
                        </div>
                        <div>
                          <h2 className="verdict-title">Invalid Input Syntax</h2>
                          <p className="verdict-subtitle">
                            This MVP supports Python only by design. No valid Python code was found in the input.
                          </p>
                        </div>
                      </>
                    )}
                  </div>
                  <span className={`status-pill status-pill-${status}`}>{status}</span>
                </div>

                {/* What Changed — Key Metrics */}
                <div className="verdict-metrics">
                  <div className="verdict-stat">
                    <span className="stat-meta-label">Iterations</span>
                    <span className="stat-meta-value">{finalJob.iteration_count || iterationCount} / 3</span>
                  </div>
                  <div className="verdict-stat">
                    <span className="stat-meta-label">Model Calls</span>
                    <span className="stat-meta-value">{finalJob.llm_call_count}</span>
                  </div>
                  {finalJob.judge_verdict !== null && finalJob.judge_verdict !== undefined && (
                    <div className="verdict-stat">
                      <span className="stat-meta-label">Judge Verdict</span>
                      <span className={`stat-meta-value ${finalJob.judge_verdict ? 'color-success' : 'color-failed'}`}>
                        {finalJob.judge_verdict ? 'Genuine Fix Confirmed' : 'Rejected Gaming / Weakened Test'}
                      </span>
                    </div>
                  )}
                </div>

                {/* Why Did It Work — Root Cause Explanation */}
                {rootCause && (
                  <div className="verdict-root-cause">
                    <span className="root-cause-label">Diagnosed Root Cause</span>
                    <p className="root-cause-text">{rootCause}</p>
                  </div>
                )}

                {/* Judge Reasoning */}
                {finalJob.judge_reasoning && (
                  <div className="verdict-reasoning-box">
                    <span className="root-cause-label">Judge Evaluation</span>
                    <p className="reasoning-text">{finalJob.judge_reasoning}</p>
                  </div>
                )}

                {/* Execution Note */}
                {finalJob.error && (
                  <div className="verdict-error-box">
                    <span className="root-cause-label">Execution Note</span>
                    <p className="error-note-text">{finalJob.error}</p>
                  </div>
                )}

                {/* Terminal Actions */}
                <div className="verdict-actions">
                  {status !== 'verified' && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={handleRetry}
                      title="Re-run analysis with the same input"
                    >
                      <RefreshCw size={13} />
                      <span>Retry Analysis</span>
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={reset}
                  >
                    <RotateCcw size={13} />
                    <span>New Analysis</span>
                  </button>
                </div>
              </section>
            )}

            {/* 2. Reasoning Trace (left column) */}
            <TraceView events={events} />

            {/* 3. Generated Patch DiffView (right column) */}
            {diff && <DiffView diff={diff} status={status} />}
          </div>
        )}
      </main>

      {/* Developer Tool Footer */}
      <footer className="app-footer">
        <div className="footer-meta">
          <span className="footer-item">BugFixAgent</span>
          <span className="footer-separator" aria-hidden="true">·</span>
          <span className="footer-item">AI-assisted Python debugging</span>
          <span className="footer-separator" aria-hidden="true">·</span>
          <a
            href="https://github.com/Jayanth-Kurapati/ai-bugfix-agent"
            target="_blank"
            rel="noopener noreferrer"
            className="footer-link"
          >
            GitHub
          </a>
          <span className="footer-separator" aria-hidden="true">·</span>
          <a
            href="https://github.com/Jayanth-Kurapati/ai-bugfix-agent#readme"
            target="_blank"
            rel="noopener noreferrer"
            className="footer-link"
          >
            Documentation
          </a>
          <span className="footer-separator" aria-hidden="true">·</span>
          <a
            href="https://github.com/Jayanth-Kurapati/ai-bugfix-agent/issues"
            target="_blank"
            rel="noopener noreferrer"
            className="footer-link"
          >
            Report an issue
          </a>
        </div>
      </footer>
    </div>
  );
}
