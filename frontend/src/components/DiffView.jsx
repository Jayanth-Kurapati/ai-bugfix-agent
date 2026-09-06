import { useState } from 'react';
import {
  FileCode2,
  Copy,
  Check,
  Download,
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
      // Fallback for non-secure / browser-restricted contexts
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

  const handleDownload = () => {
    try {
      const blob = new Blob([diff], { type: 'text/x-diff;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'patch.diff';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch {
      // Ignore download errors
    }
  };

  const lines = diff.split('\n');

  // Compute addition / deletion metrics
  let additions = 0;
  let deletions = 0;
  for (const line of lines) {
    if (line.startsWith('+') && !line.startsWith('+++')) additions++;
    else if (line.startsWith('-') && !line.startsWith('---')) deletions++;
  }

  return (
    <div className="diff-view surface-card animate-fade-in" id="diff-view">
      {/* Header with Title and Actions */}
      <div className="diff-header">
        <div className="diff-title-group">
          <div className="diff-icon-wrapper" aria-hidden="true">
            <FileCode2 size={16} />
          </div>
          <div>
            <h3 className="diff-title">Generated Patch</h3>
            <div className="diff-stats-badge">
              <span className="diff-badge-add">+{additions}</span>
              <span className="diff-badge-del">−{deletions}</span>
            </div>
          </div>
        </div>

        <div className="diff-actions">
          <button
            type="button"
            className="btn btn-secondary btn-sm copy-btn"
            onClick={handleCopy}
            id="copy-diff-btn"
            title="Copy unified diff to clipboard"
          >
            {copied ? (
              <>
                <Check size={13} className="text-success" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy size={13} />
                <span>Copy Diff</span>
              </>
            )}
          </button>

          <button
            type="button"
            className="btn btn-secondary btn-sm download-btn"
            onClick={handleDownload}
            id="download-diff-btn"
            title="Download patch file as patch.diff"
          >
            <Download size={13} />
            <span>Download .patch</span>
          </button>
        </div>
      </div>

      {/* Honesty Status Banner */}
      {status === 'blocked' && (
        <div className="diff-status-banner diff-status-blocked" id="diff-status-indicator" role="alert">
          <AlertTriangle size={17} className="diff-status-icon" aria-hidden="true" />
          <div className="diff-status-body">
            <strong>Verification Blocked</strong>
            <span>Patch candidate was generated, but sandbox execution is blocked on this host environment. It has not been confirmed to fix the bug.</span>
          </div>
        </div>
      )}

      {status === 'failed' && (
        <div className="diff-status-banner diff-status-failed" id="diff-status-indicator" role="alert">
          <XCircle size={17} className="diff-status-icon" aria-hidden="true" />
          <div className="diff-status-body">
            <strong>Verification Failed</strong>
            <span>Patch candidate was generated, but failed sandbox test execution or diff application.</span>
          </div>
        </div>
      )}

      {status === 'verified' && (
        <div className="diff-status-banner diff-status-verified" id="diff-status-indicator" role="status">
          <CheckCircle2 size={17} className="diff-status-icon" aria-hidden="true" />
          <div className="diff-status-body">
            <strong>Verified Fix</strong>
            <span>Candidate patch successfully passed sandboxed test execution and judge verification.</span>
          </div>
        </div>
      )}

      {(status === 'running' || status === 'queued') && (
        <div className="diff-status-banner diff-status-pending" id="diff-status-indicator">
          <Loader2 size={17} className="diff-status-icon banner-spinner animate-spin" aria-hidden="true" />
          <div className="diff-status-body">
            <strong>Verification in progress…</strong>
            <span>Candidate patch generated; executing test verification inside the sandbox.</span>
          </div>
        </div>
      )}

      {/* Technical IDE Code Window */}
      <div className="diff-window">
        <div className="diff-window-bar">
          <div className="window-dots" aria-hidden="true">
            <span className="dot dot-red" />
            <span className="dot dot-yellow" />
            <span className="dot dot-green" />
          </div>
          <span className="window-filename">patch.diff</span>
          <span className="window-meta">{lines.length} lines</span>
        </div>
        <div className="diff-content">
          <pre className="diff-code" tabIndex={0} aria-label="Unified patch diff content">
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
                  <span className="diff-line-num" aria-hidden="true">{i + 1}</span>
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
