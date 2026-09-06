import { useState, useRef, useEffect } from 'react';
import { Code2, GitBranch, Sparkles, Play, Loader2, Bug, AlertCircle, Check } from 'lucide-react';
import { generateRandomExample } from '../utils/exampleGenerator';
import './InputForm.css';

export default function InputForm({ onSubmit, disabled, isSubmitting, submitError, onClearError }) {
  const [mode, setMode] = useState('snippet');
  const [code, setCode] = useState('');
  const [testType, setTestType] = useState('pytest');
  const [testContent, setTestContent] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [testCommand, setTestCommand] = useState('');
  const [lastIndex, setLastIndex] = useState(-1);
  const [exampleFeedback, setExampleFeedback] = useState(false);

  const snippetTabRef = useRef(null);
  const repoTabRef = useRef(null);

  // Clear example feedback toast after 2s
  useEffect(() => {
    if (exampleFeedback) {
      const timer = setTimeout(() => setExampleFeedback(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [exampleFeedback]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (onClearError) onClearError();
    if (mode === 'snippet') {
      onSubmit({
        mode: 'snippet',
        code: code.trim(),
        test_type: testType,
        test_content: testContent.trim(),
      });
    } else {
      onSubmit({
        mode: 'repo',
        repo_url: repoUrl.trim(),
        test_command: testCommand.trim(),
      });
    }
  };

  const fillExample = () => {
    if (onClearError) onClearError();
    const { example, templateIndex } = generateRandomExample(lastIndex);
    setLastIndex(templateIndex);
    // Explicitly switch to snippet mode since this is a Python snippet example
    setMode('snippet');
    setCode(example.code);
    setTestType(example.test_type);
    setTestContent(example.test_content);
    setExampleFeedback(true);
  };

  // Keyboard navigation for accessible tabs
  const handleTabKeyDown = (e, targetMode) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault();
      const nextMode = targetMode === 'snippet' ? 'repo' : 'snippet';
      setMode(nextMode);
      if (nextMode === 'snippet') {
        snippetTabRef.current?.focus();
      } else {
        repoTabRef.current?.focus();
      }
    } else if (e.key === 'Home') {
      e.preventDefault();
      setMode('snippet');
      snippetTabRef.current?.focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      setMode('repo');
      repoTabRef.current?.focus();
    }
  };

  const isValid = mode === 'snippet'
    ? code.trim().length > 0 && testContent.trim().length > 0
    : repoUrl.trim().length > 0 && testCommand.trim().length > 0;

  return (
    <form className="input-form surface-card animate-fade-in" onSubmit={handleSubmit} id="analyze-form">
      {/* Form Header */}
      <div className="form-header">
        <div className="form-title-group">
          <div className="form-icon-wrapper" aria-hidden="true">
            <Bug className="form-icon" size={16} />
          </div>
          <div>
            <h2 className="form-title">Analyze Bug</h2>
            <p className="form-subtitle">Submit Python code or a public GitHub repository for automated repair</p>
          </div>
        </div>
        <div className="form-actions-header">
          <button
            type="button"
            className="btn btn-secondary btn-sm try-example-btn"
            onClick={fillExample}
            disabled={disabled}
            id="fill-example-btn"
            title="Load a procedurally generated Python bug example"
          >
            {exampleFeedback ? (
              <>
                <Check size={13} className="text-success" />
                <span>Example Inserted</span>
              </>
            ) : (
              <>
                <Sparkles size={13} />
                <span>Try Python Example</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Submission Error Banner (Preserves all inputs) */}
      {submitError && (
        <div className="form-error-banner animate-fade-in" role="alert">
          <AlertCircle size={16} className="error-banner-icon" />
          <div className="error-banner-body">
            <strong className="error-banner-title">Submission Error</strong>
            <p className="error-banner-text">{submitError}</p>
          </div>
          {onClearError && (
            <button
              type="button"
              className="btn btn-ghost btn-sm error-dismiss-btn"
              onClick={onClearError}
              aria-label="Dismiss error"
            >
              Dismiss
            </button>
          )}
        </div>
      )}

      {/* Accessible Tab List */}
      <div className="mode-switcher" role="tablist" aria-label="Analysis input mode">
        <button
          ref={snippetTabRef}
          type="button"
          role="tab"
          className={`mode-tab ${mode === 'snippet' ? 'active' : ''}`}
          onClick={() => setMode('snippet')}
          onKeyDown={(e) => handleTabKeyDown(e, 'snippet')}
          aria-selected={mode === 'snippet'}
          aria-controls="panel-snippet"
          tabIndex={mode === 'snippet' ? 0 : -1}
          disabled={disabled}
          id="mode-snippet-tab"
        >
          <Code2 size={15} aria-hidden="true" />
          <span>Code Snippet</span>
        </button>
        <button
          ref={repoTabRef}
          type="button"
          role="tab"
          className={`mode-tab ${mode === 'repo' ? 'active' : ''}`}
          onClick={() => setMode('repo')}
          onKeyDown={(e) => handleTabKeyDown(e, 'repo')}
          aria-selected={mode === 'repo'}
          aria-controls="panel-repo"
          tabIndex={mode === 'repo' ? 0 : -1}
          disabled={disabled}
          id="mode-repo-tab"
        >
          <GitBranch size={15} aria-hidden="true" />
          <span>GitHub Repo</span>
        </button>
      </div>

      {/* Tab Panels */}
      {mode === 'snippet' ? (
        <div
          id="panel-snippet"
          role="tabpanel"
          aria-labelledby="mode-snippet-tab"
          className="form-fields animate-fade-in"
          key="snippet-fields"
        >
          <div className="field-group">
            <div className="label-row">
              <label className="label" htmlFor="code-input">
                Python Code
              </label>
              <span className="editor-lang-tag">python</span>
            </div>
            <textarea
              id="code-input"
              className="textarea code-textarea"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Paste the smallest reproducible version of the buggy Python code here…"
              rows={7}
              disabled={disabled}
              spellCheck={false}
              aria-describedby="code-hint"
            />
            <span id="code-hint" className="field-hint">Paste the standalone buggy function or module.</span>
          </div>

          <div className="field-group">
            <label className="label" htmlFor="test-type-select">
              Verification Target
            </label>
            <select
              id="test-type-select"
              className="select"
              value={testType}
              onChange={(e) => setTestType(e.target.value)}
              disabled={disabled}
            >
              <option value="pytest">Pytest Function</option>
              <option value="traceback">Error Traceback</option>
            </select>
          </div>

          <div className="field-group">
            <div className="label-row">
              <label className="label" htmlFor="test-content-input">
                {testType === 'pytest' ? 'Test Function' : 'Error Traceback'}
              </label>
              <span className="editor-lang-tag">{testType === 'pytest' ? 'pytest' : 'traceback'}</span>
            </div>
            <textarea
              id="test-content-input"
              className="textarea code-textarea"
              value={testContent}
              onChange={(e) => setTestContent(e.target.value)}
              placeholder={testType === 'pytest'
                ? 'def test_example():\n    from snippet import ...\n    assert ...'
                : 'Traceback (most recent call last):\n  File "snippet.py", line 4, in ...\nAssertionError: ...'}
              rows={6}
              disabled={disabled}
              spellCheck={false}
              aria-describedby="test-hint"
            />
            <span id="test-hint" className="field-hint">
              {testType === 'pytest'
                ? 'A pytest test asserting the expected behavior.'
                : 'Python stack traceback produced when the bug is triggered.'}
            </span>
          </div>
        </div>
      ) : (
        <div
          id="panel-repo"
          role="tabpanel"
          aria-labelledby="mode-repo-tab"
          className="form-fields animate-fade-in"
          key="repo-fields"
        >
          <div className="field-group">
            <label className="label" htmlFor="repo-url-input">
              GitHub Repository URL
            </label>
            <input
              id="repo-url-input"
              className="input"
              type="url"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repository"
              disabled={disabled}
              aria-describedby="repo-hint"
            />
            <span id="repo-hint" className="field-hint">Public repository containing Python code with tests.</span>
          </div>

          <div className="field-group">
            <label className="label" htmlFor="test-command-input">
              Test Command
            </label>
            <input
              id="test-command-input"
              className="input code-input"
              type="text"
              value={testCommand}
              onChange={(e) => setTestCommand(e.target.value)}
              placeholder="pytest tests/test_example.py -q"
              disabled={disabled}
              aria-describedby="command-hint"
            />
            <span id="command-hint" className="field-hint">Must be a relative pytest command targeting the test suite.</span>
          </div>
        </div>
      )}

      {/* Submit Button */}
      <button
        type="submit"
        className="btn btn-primary submit-btn"
        disabled={disabled || !isValid}
        id="submit-analysis-btn"
      >
        {isSubmitting ? (
          <>
            <Loader2 size={15} className="btn-spinner animate-spin" />
            <span>Starting agent…</span>
          </>
        ) : disabled ? (
          <>
            <Loader2 size={15} className="btn-spinner animate-spin" />
            <span>Agent active…</span>
          </>
        ) : (
          <>
            <Play size={14} fill="currentColor" />
            <span>Start Analysis</span>
          </>
        )}
      </button>
    </form>
  );
}
