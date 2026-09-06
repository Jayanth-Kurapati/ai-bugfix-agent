import { useState } from 'react';
import { generateRandomExample } from '../utils/exampleGenerator';
import './InputForm.css';

export default function InputForm({ onSubmit, disabled }) {
  const [mode, setMode] = useState('snippet');
  const [code, setCode] = useState('');
  const [testType, setTestType] = useState('pytest');
  const [testContent, setTestContent] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [testCommand, setTestCommand] = useState('');
  const [lastIndex, setLastIndex] = useState(-1);

  const handleSubmit = (e) => {
    e.preventDefault();
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
    const { example, templateIndex } = generateRandomExample(lastIndex);
    setLastIndex(templateIndex);
    setMode('snippet');
    setCode(example.code);
    setTestType(example.test_type);
    setTestContent(example.test_content);
  };

  const isValid = mode === 'snippet'
    ? code.trim() && testContent.trim()
    : repoUrl.trim() && testCommand.trim();

  return (
    <form className="input-form glass-card animate-fade-in" onSubmit={handleSubmit} id="analyze-form">
      <div className="form-header">
        <h2 className="form-title">
          <span className="form-icon">🔍</span>
          Analyze Bug
        </h2>
        <button type="button" className="btn btn-secondary btn-sm" onClick={fillExample} disabled={disabled} id="fill-example-btn">
          Try Example
        </button>
      </div>

      <div className="mode-switcher" role="tablist">
        <button
          type="button"
          role="tab"
          className={`mode-tab ${mode === 'snippet' ? 'active' : ''}`}
          onClick={() => setMode('snippet')}
          aria-selected={mode === 'snippet'}
          disabled={disabled}
          id="mode-snippet-tab"
        >
          <span className="tab-icon">📝</span>
          Code Snippet
        </button>
        <button
          type="button"
          role="tab"
          className={`mode-tab ${mode === 'repo' ? 'active' : ''}`}
          onClick={() => setMode('repo')}
          aria-selected={mode === 'repo'}
          disabled={disabled}
          id="mode-repo-tab"
        >
          <span className="tab-icon">📦</span>
          GitHub Repo
        </button>
      </div>

      {mode === 'snippet' ? (
        <div className="form-fields animate-fade-in" key="snippet-fields">
          <div className="field-group">
            <label className="label" htmlFor="code-input">Python Code</label>
            <textarea
              id="code-input"
              className="textarea"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Paste your buggy Python code here…"
              rows={6}
              disabled={disabled}
              spellCheck={false}
            />
          </div>

          <div className="field-group">
            <label className="label" htmlFor="test-type-select">Test Type</label>
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
            <label className="label" htmlFor="test-content-input">
              {testType === 'pytest' ? 'Test Function' : 'Error Traceback'}
            </label>
            <textarea
              id="test-content-input"
              className="textarea"
              value={testContent}
              onChange={(e) => setTestContent(e.target.value)}
              placeholder={testType === 'pytest'
                ? 'def test_something():\n    from snippet import ...\n    assert ...'
                : 'Paste the error traceback here…'}
              rows={6}
              disabled={disabled}
              spellCheck={false}
            />
          </div>
        </div>
      ) : (
        <div className="form-fields animate-fade-in" key="repo-fields">
          <div className="field-group">
            <label className="label" htmlFor="repo-url-input">GitHub Repository URL</label>
            <input
              id="repo-url-input"
              className="input"
              type="url"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              disabled={disabled}
            />
          </div>

          <div className="field-group">
            <label className="label" htmlFor="test-command-input">Test Command</label>
            <input
              id="test-command-input"
              className="input"
              type="text"
              value={testCommand}
              onChange={(e) => setTestCommand(e.target.value)}
              placeholder="pytest tests/test_example.py -q"
              disabled={disabled}
            />
            <span className="field-hint">Must be a pytest command with relative paths only.</span>
          </div>
        </div>
      )}

      <button
        type="submit"
        className="btn btn-primary submit-btn"
        disabled={disabled || !isValid}
        id="submit-analysis-btn"
      >
        {disabled ? (
          <>
            <span className="spinner" />
            Analyzing…
          </>
        ) : (
          <>
            <span>🚀</span>
            Start Analysis
          </>
        )}
      </button>
    </form>
  );
}
