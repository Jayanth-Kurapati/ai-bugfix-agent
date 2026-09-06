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
      {/* Header */}
      <header className="app-header" id="app-header">
        <div className="header-content">
          <div className="logo-group">
            <img src={logoMark} alt="BugFixAgent logo" className="logo-icon" width="32" height="32" />
            <h1 className="logo-text text-gradient">BugFixAgent</h1>
          </div>
          <p className="tagline">
            AI-powered Python bug fixing — diagnose, patch, verify, judge.
          </p>
        </div>
        {isDone && (
          <button className="btn btn-secondary" onClick={reset} id="new-analysis-btn">
            ← New Analysis
          </button>
        )}
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
              <div className="summary-card glass-card animate-fade-in" id="summary-card">
                <h3 className="summary-title">
                  {status === 'verified' && <><span>🎉</span> Bug Fixed Successfully</>}
                  {status === 'failed' && <><span>💥</span> Analysis Failed</>}
                  {status === 'blocked' && <><span>🚧</span> Analysis Blocked</>}
                  {status === 'model_unavailable' && <><span>🔌</span> Models Unavailable</>}
                </h3>
                <div className="summary-details">
                  <div className="summary-stat">
                    <span className="summary-label">Status</span>
                    <span className={`summary-value status-${status}`}>{status}</span>
                  </div>
                  <div className="summary-stat">
                    <span className="summary-label">Iterations</span>
                    <span className="summary-value">{finalJob.iteration_count || iterationCount}</span>
                  </div>
                  <div className="summary-stat">
                    <span className="summary-label">LLM Calls</span>
                    <span className="summary-value">{finalJob.llm_call_count}</span>
                  </div>
                  {finalJob.judge_verdict !== null && finalJob.judge_verdict !== undefined && (
                    <div className="summary-stat">
                      <span className="summary-label">Judge</span>
                      <span className={`summary-value ${finalJob.judge_verdict ? 'status-verified' : 'status-failed'}`}>
                        {finalJob.judge_verdict ? 'Genuine Fix' : 'Rejected'}
                      </span>
                    </div>
                  )}
                </div>
                {finalJob.judge_reasoning && (
                  <p className="summary-reasoning">
                    <strong>Judge reasoning:</strong> {finalJob.judge_reasoning}
                  </p>
                )}
                {finalJob.error && (
                  <p className="summary-error">{finalJob.error}</p>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <div className="footer-meta">
          <span className="footer-item">AI Bug-Fixing Agent MVP</span>
          <span className="footer-item">Python only</span>
          <span className="footer-item">Free-tier LLMs via OpenRouter</span>
        </div>
      </footer>
    </div>
  );
}
