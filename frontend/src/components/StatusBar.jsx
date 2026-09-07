import {
  Clock,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Unplug,
  Layers,
  Cpu,
  RefreshCw,
} from 'lucide-react';
import './StatusBar.css';

function deriveAgentStage(status, events) {
  if (status === 'queued') return { label: 'Queued in Workstation', stage: 'queued' };
  if (status === 'verified') return { label: 'Bug Fixed & Verified', stage: 'verified' };
  if (status === 'failed') return { label: 'Verification Failed', stage: 'failed' };
  if (status === 'blocked') return { label: 'Execution Blocked by Sandbox', stage: 'blocked' };
  if (status === 'model_unavailable') return { label: 'Free Models Unavailable', stage: 'model_unavailable' };
  if (status === 'verification_inconclusive') return { label: 'Verification Inconclusive', stage: 'verification_inconclusive' };
  if (status === 'repository_error') return { label: 'Repository Error', stage: 'repository_error' };
  if (status === 'invalid_input') return { label: 'Invalid Input Syntax', stage: 'invalid_input' };

  // Status is running — derive lifecycle from the last event
  if (events && events.length > 0) {
    const last = events[events.length - 1];
    if (last.kind === 'JUDGE') return { label: 'Judging Patch Authenticity', stage: 'judging' };
    if (last.kind === 'VERIFY') return { label: 'Running Sandboxed Verification', stage: 'verifying' };
    if (last.kind === 'PATCH' || last.kind === 'NEXT ACTION') return { label: 'Generating Unified Diff Patch', stage: 'patching' };
    if (last.kind === 'HYPOTHESIS' || last.kind === 'KNOWN' || last.kind === 'UNKNOWN' || last.kind === 'LINT' || last.kind === 'MODELS') {
      return { label: 'Diagnosing Root Cause', stage: 'diagnosing' };
    }
  }

  return { label: 'Analyzing Code & Tests', stage: 'running' };
}

export default function StatusBar({
  status,
  events,
  iterationCount,
  llmCallCount,
  error,
  onRetry,
}) {
  if (!status) return null;

  const currentStage = deriveAgentStage(status, events);
  const isTerminal = [
    'verified',
    'failed',
    'blocked',
    'model_unavailable',
    'verification_inconclusive',
    'repository_error',
    'invalid_input',
  ].includes(status);
  const isRunning = status === 'running' || status === 'queued';

  return (
    <div className={`status-bar surface-card animate-fade-in ${isTerminal ? 'terminal' : ''}`} id="status-bar">
      {/* Screen Reader Announcement for meaningful state changes */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {`Agent state: ${currentStage.label}. Iteration ${iterationCount || 1} of 3. ${llmCallCount} model calls used.`}
      </div>

      <div className="status-row">
        {/* Primary Agent Stage Badge */}
        <div className="status-primary-group">
          <div className={`badge badge-${status}`} id="job-status-badge">
            {isRunning ? (
              <Loader2 size={13} className="badge-spinner animate-spin" aria-hidden="true" />
            ) : status === 'verified' ? (
              <CheckCircle2 size={13} aria-hidden="true" />
            ) : status === 'failed' ? (
              <XCircle size={13} aria-hidden="true" />
            ) : status === 'blocked' ? (
              <AlertTriangle size={13} aria-hidden="true" />
            ) : status === 'model_unavailable' ? (
              <Unplug size={13} aria-hidden="true" />
            ) : status === 'verification_inconclusive' ? (
              <AlertTriangle size={13} aria-hidden="true" />
            ) : (
              <Clock size={13} aria-hidden="true" />
            )}
            <span className="stage-label-text">{currentStage.label}</span>
            {isRunning && <span className="status-dot animate-pulse" aria-hidden="true" />}
          </div>

          {/* Inline Retry if terminated with error/blocked/inconclusive */}
          {isTerminal && status !== 'verified' && onRetry && (
            <button
              type="button"
              className="btn btn-secondary btn-sm retry-btn"
              onClick={onRetry}
              title="Re-run analysis with your existing input"
            >
              <RefreshCw size={12} />
              <span>Retry</span>
            </button>
          )}
        </div>

        {/* Secondary Telemetry */}
        <div className="status-stats">
          <div className="stat" id="iteration-count">
            <span className="stat-label">
              <Layers size={10} className="stat-icon" aria-hidden="true" />
              Iteration
            </span>
            <span className="stat-value">{iterationCount || 1} / 3</span>
          </div>

          <div className="stat-divider" aria-hidden="true" />

          <div className="stat" id="llm-call-count">
            <span className="stat-label">
              <Cpu size={10} className="stat-icon" aria-hidden="true" />
              Model Calls
            </span>
            <span className="stat-value">{llmCallCount}</span>
          </div>
        </div>
      </div>

      {/* Model Unavailable Notice */}
      {status === 'model_unavailable' && (
        <div className="status-model-msg animate-fade-in" role="alert">
          <Unplug size={15} className="model-msg-icon" aria-hidden="true" />
          <span className="model-msg-text">
            No free LLM models are currently responding on OpenRouter. Free-tier quotas may be rate-limited or in rotation. Please retry in a moment.
          </span>
        </div>
      )}

      {/* Execution Error Notice */}
      {error && isTerminal && status !== 'model_unavailable' && (
        <div className="status-error animate-fade-in" role="alert">
          <AlertTriangle size={15} className="error-icon" aria-hidden="true" />
          <span className="error-text">{error}</span>
        </div>
      )}
    </div>
  );
}
