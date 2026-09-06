import { useState } from 'react';
import {
  FileCode2,
  Copy,
  Check,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
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
        <div className="diff-title-group">
          <div className="diff-icon-wrapper">
            <FileCode2 size={16} />
          </div>
          <h3 className="diff-title">Generated Patch</h3>
        </div>
        <button
          className="btn btn-secondary btn-sm copy-btn"
          onClick={handleCopy}
          id="copy-diff-btn"
        >
          {copied ? (
            <>
              <Check size={14} className="text-success" />
              <span>Copied!</span>
            </>
          ) : (
            <>
              <Copy size={14} />
              <span>Copy Diff</span>
            </>
          )}
        </button>
      </div>

      {/* Honesty Status Banner whenever not verified */}
      {status === 'blocked' && (
        <div className="diff-status-banner diff-status-blocked" id="diff-status-indicator">
          <AlertTriangle size={18} className="diff-status-icon" />
          <div className="diff-status-body">
            <strong>Unverified — generated but not confirmed to fix the bug</strong>
            <span>Sandbox execution is blocked on this host environment; patch has not been verified against the test suite.</span>
          </div>
        </div>
      )}

      {status === 'failed' && (
        <div className="diff-status-banner diff-status-failed" id="diff-status-indicator">
          <XCircle size={18} className="diff-status-icon" />
          <div className="diff-status-body">
            <strong>Unverified — patch verification failed</strong>
            <span>A patch was generated, but it failed sandbox test execution or diff application.</span>
          </div>
        </div>
      )}

      {status === 'verified' && (
        <div className="diff-status-banner diff-status-verified" id="diff-status-indicator">
          <CheckCircle2 size={18} className="diff-status-icon" />
          <div className="diff-status-body">
            <strong>Verified Fix</strong>
            <span>Candidate patch successfully passed sandboxed test execution and judge verification.</span>
          </div>
        </div>
      )}

      {(status === 'running' || status === 'queued') && (
        <div className="diff-status-banner diff-status-pending" id="diff-status-indicator">
          <Loader2 size={18} className="diff-status-icon banner-spinner" />
          <div className="diff-status-body">
            <strong>Verification in progress...</strong>
            <span>Candidate patch generated; executing test verification in the sandbox.</span>
          </div>
        </div>
      )}

      <div className="diff-window">
        <div className="diff-window-bar">
          <div className="window-dots">
            <span className="dot dot-red" />
            <span className="dot dot-yellow" />
            <span className="dot dot-green" />
          </div>
          <span className="window-filename">patch.diff</span>
          <span className="window-meta">{lines.length} lines</span>
        </div>
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
    </div>
  );
}
