import {
  Search,
  CheckCircle2,
  HelpCircle,
  Lightbulb,
  ArrowRightCircle,
  GitCommit,
  Terminal,
  Scale,
  Flag,
  Clock,
  ScrollText,
  AlertCircle,
} from 'lucide-react';
import './TraceView.css';

/**
 * Maps trace event kind → display configuration with Lucide icons.
 */
const EVENT_CONFIG = {
  LINT:          { icon: Search,           label: 'Lint Analysis', color: 'var(--color-info)' },
  KNOWN:         { icon: CheckCircle2,     label: 'Known Facts',   color: 'var(--color-success)' },
  UNKNOWN:       { icon: HelpCircle,       label: 'Unknowns',      color: 'var(--color-warning)' },
  HYPOTHESIS:    { icon: Lightbulb,        label: 'Hypothesis',    color: 'var(--accent-primary)' },
  'NEXT ACTION': { icon: ArrowRightCircle, label: 'Next Action',   color: '#38bdf8' },
  PATCH:         { icon: GitCommit,        label: 'Patch',         color: '#a855f7' },
  VERIFY:        { icon: Terminal,         label: 'Verification',  color: 'var(--color-info)' },
  JUDGE:         { icon: Scale,            label: 'Judge Verdict', color: 'var(--color-warning)' },
  FINAL:         { icon: Flag,             label: 'Final Status',  color: 'var(--text-primary)' },
};

function renderEventContent(event) {
  const { kind, message, data } = event;

  switch (kind) {
    case 'KNOWN':
    case 'UNKNOWN':
      return (
        <div className="event-content">
          <p className="event-message">{message}</p>
          {data.values && data.values.length > 0 && (
            <ul className="event-list">
              {data.values.map((item, i) => (
                <li key={i} className="event-list-item">{item}</li>
              ))}
            </ul>
          )}
        </div>
      );

    case 'HYPOTHESIS':
      return (
        <div className="event-content hypothesis-highlight">
          <p className="event-message event-hypothesis">{message}</p>
        </div>
      );

    case 'NEXT ACTION':
      return (
        <div className="event-content">
          <p className="event-message">{message}</p>
          {data.target_files && data.target_files.length > 0 && (
            <div className="target-files">
              <span className="target-label">Target files:</span>
              {data.target_files.map((f, i) => (
                <code key={i} className="target-file">{f}</code>
              ))}
            </div>
          )}
        </div>
      );

    case 'LINT':
      return (
        <div className="event-content">
          <p className="event-message">{message}</p>
          <div className="event-meta">
            {data.findings !== undefined && (
              <span className="meta-tag">Findings: {data.findings}</span>
            )}
            {data.exit_code !== undefined && (
              <span className="meta-tag">Exit code: {data.exit_code}</span>
            )}
          </div>
        </div>
      );

    case 'PATCH':
      return (
        <div className="event-content">
          <p className="event-message">{message}</p>
          {data.patched_files && data.patched_files.length > 0 && (
            <div className="target-files">
              <span className="target-label">Patched:</span>
              {data.patched_files.map((f, i) => (
                <code key={i} className="target-file">{f}</code>
              ))}
            </div>
          )}
          {data.error && <p className="event-error">{data.error}</p>}
        </div>
      );

    case 'VERIFY':
      return (
        <div className="event-content">
          <p className={`event-message ${message === 'pass' || message === 'Verification passed.' ? 'text-success' : 'text-error'}`}>
            {message}
          </p>
          {data.exit_code !== undefined && (
            <span className="meta-tag">Exit code: {data.exit_code}</span>
          )}
          {data.stdout && (
            <details className="verify-details">
              <summary>Standard Output (stdout)</summary>
              <pre className="verify-output">{data.stdout}</pre>
            </details>
          )}
          {data.stderr && (
            <details className="verify-details">
              <summary>Standard Error (stderr)</summary>
              <pre className="verify-output">{data.stderr}</pre>
            </details>
          )}
        </div>
      );

    case 'JUDGE':
      return (
        <div className="event-content">
          <p className="event-message">{message}</p>
          {data.genuine_fix !== undefined && (
            <div className={`judge-badge ${data.genuine_fix ? 'genuine' : 'rejected'}`}>
              {data.genuine_fix ? (
                <>
                  <CheckCircle2 size={13} />
                  <span>Genuine Fix Verified</span>
                </>
              ) : (
                <>
                  <AlertCircle size={13} />
                  <span>Rejected — Not a Genuine Fix</span>
                </>
              )}
            </div>
          )}
          {data.reasoning && (
            <p className="judge-reasoning">{data.reasoning}</p>
          )}
        </div>
      );

    case 'FINAL':
      return (
        <div className="event-content">
          <p className={`event-message final-status final-${message}`}>{message}</p>
          {data.error && <p className="event-error">{data.error}</p>}
        </div>
      );

    default:
      return (
        <div className="event-content">
          <p className="event-message">{message}</p>
          {Object.keys(data).length > 0 && (
            <pre className="event-raw">{JSON.stringify(data, null, 2)}</pre>
          )}
        </div>
      );
  }
}

export default function TraceView({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="trace-view glass-card animate-fade-in" id="trace-view">
        <div className="trace-empty">
          <div className="trace-empty-icon animate-pulse">
            <Clock size={28} />
          </div>
          <p>Waiting for trace events…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="trace-view glass-card" id="trace-view">
      <div className="trace-header">
        <div className="trace-title-group">
          <ScrollText size={18} className="trace-header-icon" />
          <h3 className="trace-title">Reasoning Trace</h3>
        </div>
        <span className="event-count">{events.length} events</span>
      </div>

      <div className="trace-timeline">
        {events.map((event, index) => {
          const config = EVENT_CONFIG[event.kind] || { icon: ArrowRightCircle, label: event.kind, color: 'var(--text-secondary)' };
          const IconComponent = config.icon;
          return (
            <div
              key={index}
              className="trace-event animate-slide-in"
              style={{ animationDelay: `${Math.min(index * 40, 300)}ms`, '--event-color': config.color }}
            >
              <div className="event-indicator">
                <div className="event-dot" />
                {index < events.length - 1 && <div className="event-line" />}
              </div>
              <div className="event-card">
                <div className="event-header">
                  <IconComponent size={14} style={{ color: config.color }} />
                  <span className="event-label" style={{ color: config.color }}>{config.label}</span>
                  <span className="event-index">#{index + 1}</span>
                </div>
                {renderEventContent(event)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
