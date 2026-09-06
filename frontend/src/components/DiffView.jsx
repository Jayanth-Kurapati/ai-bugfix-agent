import { useState } from 'react';
import './DiffView.css';

export default function DiffView({ diff, status }) {
  const [copied, setCopied] = useState(false);

  if (!diff) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(diff);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-secure contexts
      const ta = document.createElement('textarea');
      ta.value = diff;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const lines = diff.split('\n');

  return (
    <div className="diff-view glass-card animate-fade-in" id="diff-view">
      <div className="diff-header">
        <h3 className="diff-title">
          <span>📄</span> Generated Patch
        </h3>
        <button
          className="btn btn-secondary btn-sm copy-btn"
          onClick={handleCopy}
          id="copy-diff-btn"
        >
          {copied ? '✅ Copied!' : '📋 Copy'}
        </button>
      </div>

      {/* Honesty Status Banner whenever not verified */}
      {status === 'blocked' && (
        <div className="diff-status-banner diff-status-blocked" id="diff-status-indicator">
          <span className="diff-status-icon">⚠️</span>
          <div className="diff-status-body">
            <strong>Unverified — generated but not confirmed to fix the bug</strong>
            <span>Sandbox execution is blocked on this host environment; patch has not been verified against the test suite.</span>
          </div>
        </div>
      )}

      {status === 'failed' && (
        <div className="diff-status-banner diff-status-failed" id="diff-status-indicator">
          <span className="diff-status-icon">❌</span>
          <div className="diff-status-body">
            <strong>Unverified — patch verification failed</strong>
            <span>A patch was generated, but it failed sandbox test execution or diff application.</span>
          </div>
        </div>
      )}

      {status === 'verified' && (
        <div className="diff-status-banner diff-status-verified" id="diff-status-indicator">
          <span className="diff-status-icon">✅</span>
          <div className="diff-status-body">
            <strong>Verified Fix</strong>
            <span>Candidate patch successfully passed sandboxed test execution and judge verification.</span>
          </div>
        </div>
      )}

      {(status === 'running' || status === 'queued') && (
        <div className="diff-status-banner diff-status-pending" id="diff-status-indicator">
          <span className="diff-status-icon">⏳</span>
          <div className="diff-status-body">
            <strong>Verification in progress...</strong>
            <span>Candidate patch generated; executing test verification in the sandbox.</span>
          </div>
        </div>
      )}

      <div className="diff-content">
        <pre className="diff-code">
          {lines.map((line, i) => {
            let lineClass = 'diff-line';
            if (line.startsWith('+') && !line.startsWith('+++')) {
              lineClass += ' diff-add';
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              lineClass += ' diff-remove';
            } else if (line.startsWith('@@')) {
              lineClass += ' diff-hunk';
            } else if (line.startsWith('diff ') || line.startsWith('---') || line.startsWith('+++')) {
              lineClass += ' diff-meta';
            }
            return (
              <div key={i} className={lineClass}>
                <span className="diff-line-num">{i + 1}</span>
                <span className="diff-line-content">{line || ' '}</span>
              </div>
            );
          })}
        </pre>
      </div>
    </div>
  );
}
