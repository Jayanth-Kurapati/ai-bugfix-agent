import { RotateCcw, CheckCircle2, XCircle, AlertTriangle, Cpu } from 'lucide-react';
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
    iterationCount,
    llmCallCount,
    submit,
    reset,
  } = useJobStream();

  const isActive = phase === 'submitting' || phase === 'streaming';
  const isDone = phase === 'done';

  // Derive diff: prefer finalJob.diff, fall back to last PATCH event data
  const diff = finalJob?.diff || null;

  return (
    <div className="app">
      {/* Precision Header */}
      <header className="app-header" id="app-header">
        <div className="header-container">
          <div className="brand-cluster">
            <div className="logo-box">
              <img src={logoMark} alt="BugFixAgent mark" className="logo-icon" width="26" height="26" />
            </div>
            <div className="brand-meta">
              <div className="title-row">
                <h1 className="brand-name">BugFixAgent</h1>
                <span className="env-badge">MVP</span>
              </div>
              <p className="tagline">
                Agentic Python bug diagnosis, unified diff patching, sandbox verification & judging
              </p>
            </div>
          </div>
          {isDone && (
            <button className="btn btn-secondary btn-sm" onClick={reset} id="new-analysis-btn">
              <RotateCcw size={13} />
              <span>New Analysis</span>
            </button>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="app-main">
        {/* Input form — show when idle or submitting */}
        {(phase === 'idle' || phase === 'submitting') && (
          <section className="section-center">
            <InputForm onSubmit={submit} disabled={isActive} />
          </section>
        )}

        {/* Status bar — show when streaming or done */}
        {(isActive || isDone) && (
          <StatusBar
            status={status}
            iterationCount={iterationCount}
            llmCallCount={isDone && finalJob ? finalJob.llm_call_count : llmCallCount}
            error={error}
          />
        )}

        {/* Results area */}
        {(phase === 'streaming' || isDone) && (
          <div className="results-grid">
            {/* Trace — always visible during/after streaming */}
            <TraceView events={events} />

            {/* Diff — show when available */}
            {diff && <DiffView diff={diff} status={status} />}

            {/* Final summary card */}
            {isDone && finalJob && (
              <div className="summary-card surface-panel animate-fade-in" id="summary-card">
                <div className="summary-header">
                  <div className="summary-title-group">
                    {status === 'verified' && (
                      <>
                        <CheckCircle2 size={20} className="summary-icon status-verified" />
                        <h3 className="summary-title">Bug Fixed & Verified</h3>
                      </>
                    )}
                    {status === 'failed' && (
                      <>
                        <XCircle size={20} className="summary-icon status-failed" />
                        <h3 className="summary-title">Analysis Failed</h3>
                      </>
                    )}
                    {status === 'blocked' && (
                      <>
                        <AlertTriangle size={20} className="summary-icon status-blocked" />
                        <h3 className="summary-title">Analysis Blocked by Host Sandbox</h3>
                      </>
                    )}
                    {status === 'model_unavailable' && (
                      <>
                        <Cpu size={20} className="summary-icon status-failed" />
                        <h3 className="summary-title">Models Unavailable</h3>
                      </>
                    )}
                  </div>
                  <span className={`status-pill status-pill-${status}`}>{status}</span>
                </div>

                <div className="summary-details">
                  <div className="summary-stat">
                    <span className="summary-label">Total Iterations</span>
                    <span className="summary-value">{finalJob.iteration_count || iterationCount} / 3</span>
                  </div>
                  <div className="summary-stat">
                    <span className="summary-label">LLM Calls Used</span>
                    <span className="summary-value">{finalJob.llm_call_count}</span>
                  </div>
                  {finalJob.judge_verdict !== null && finalJob.judge_verdict !== undefined && (
                    <div className="summary-stat">
                      <span className="summary-label">Judge Verdict</span>
                      <span className={`summary-value ${finalJob.judge_verdict ? 'color-success' : 'color-failed'}`}>
                        {finalJob.judge_verdict ? 'Genuine Fix Confirmed' : 'Rejected Gaming/Weakened Test'}
                      </span>
                    </div>
                  )}
                </div>

                {finalJob.judge_reasoning && (
                  <div className="summary-reasoning-box">
                    <span className="reasoning-heading">Judge Evaluation</span>
                    <p className="summary-reasoning">{finalJob.judge_reasoning}</p>
                  </div>
                )}
                {finalJob.error && (
                  <div className="summary-error-box">
                    <span className="error-heading">Execution Note</span>
                    <p className="summary-error">{finalJob.error}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Minimal Footer */}
      <footer className="app-footer">
        <div className="footer-meta">
          <span className="footer-item">AI Bug-Fixing Agent</span>
          <span className="footer-separator">/</span>
          <span className="footer-item">Python 3.11</span>
          <span className="footer-separator">/</span>
          <span className="footer-item">OpenRouter Free-Tier LLMs</span>
        </div>
      </footer>
    </div>
  );
}
