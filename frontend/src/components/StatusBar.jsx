import './StatusBar.css';

const STATUS_DISPLAY = {
  queued:              { label: 'Queued',              className: 'badge-queued',              icon: '⏳' },
  running:             { label: 'Running',             className: 'badge-running',             icon: '⚙️' },
  verified:            { label: 'Verified',            className: 'badge-verified',            icon: '✅' },
  failed:              { label: 'Failed',              className: 'badge-failed',              icon: '❌' },
  blocked:             { label: 'Blocked',             className: 'badge-blocked',             icon: '⚠️' },
  model_unavailable:   { label: 'Model Unavailable',   className: 'badge-model-unavailable',   icon: '🔌' },
};

// Per-job soft cap: 3 iterations × up to 3 LLM calls each (diagnosis + patch + judge) = 9, plus headroom.
// This reflects the maximum calls a single job can make, NOT the OpenRouter account-level daily quota.
const MAX_CALLS_PER_JOB = 12;

export default function StatusBar({ status, iterationCount, llmCallCount, error }) {
  if (!status) return null;

  const display = STATUS_DISPLAY[status] || STATUS_DISPLAY.running;
  const budgetPercent = Math.min((llmCallCount / MAX_CALLS_PER_JOB) * 100, 100);
  const isTerminal = ['verified', 'failed', 'blocked', 'model_unavailable'].includes(status);

  return (
    <div className={`status-bar glass-card animate-fade-in ${isTerminal ? 'terminal' : ''}`} id="status-bar">
      <div className="status-row">
        <div className={`badge ${display.className}`} id="job-status-badge">
          <span>{display.icon}</span>
          {display.label}
          {status === 'running' && <span className="status-dot animate-pulse" />}
        </div>

        <div className="status-stats">
          <div className="stat" id="iteration-count">
            <span className="stat-label">Iteration</span>
            <span className="stat-value">{iterationCount}/3</span>
          </div>

          <div className="stat-divider" />

          <div className="stat" id="llm-call-count">
            <span className="stat-label">LLM Calls</span>
            <span className="stat-value">{llmCallCount}</span>
          </div>

          <div className="call-budget" id="call-budget-indicator" title={`${llmCallCount} of ${MAX_CALLS_PER_JOB} max job calls used`}>
            <span className="budget-label">Job usage</span>
            <div className="budget-track">
              <div
                className="budget-fill"
                style={{
                  width: `${budgetPercent}%`,
                  background: budgetPercent > 75
                    ? 'var(--color-warning)'
                    : 'var(--accent-gradient)',
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {status === 'model_unavailable' && (
        <div className="status-model-msg animate-fade-in">
          <span className="model-msg-icon">🔌</span>
          <span className="model-msg-text">
            No free LLM models are currently available. This may be caused by rate-limiting or
            model rotation on OpenRouter. Try again later.
          </span>
        </div>
      )}

      {error && isTerminal && status !== 'model_unavailable' && (
        <div className="status-error animate-fade-in">
          <span className="error-icon">⚠️</span>
          <span className="error-text">{error}</span>
        </div>
      )}
    </div>
  );
}
