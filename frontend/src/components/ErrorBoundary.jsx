import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an unhandled component error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    } else {
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-fallback" role="alert" style={{
          maxWidth: '600px',
          margin: '3rem auto',
          padding: '2rem',
          background: 'var(--color-surface, #181a20)',
          border: '1px solid var(--color-border, #2d3139)',
          borderRadius: '8px',
          textAlign: 'center',
          color: 'var(--color-text-main, #f0f3f6)',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)'
        }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '44px',
            height: '44px',
            borderRadius: '50%',
            background: 'rgba(239, 68, 68, 0.15)',
            color: 'var(--color-error, #ef4444)',
            marginBottom: '1rem'
          }}>
            <AlertTriangle size={22} aria-hidden="true" />
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.75rem' }}>
            Application Display Error
          </h2>
          <p style={{
            color: 'var(--color-text-muted, #94a3b8)',
            fontSize: '0.95rem',
            lineHeight: 1.5,
            marginBottom: '1.5rem'
          }}>
            Something went wrong displaying this result — your request may have still completed.
          </p>
          <button
            type="button"
            onClick={this.handleReset}
            className="btn btn-secondary btn-sm"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.5rem 1.25rem',
              fontSize: '0.875rem',
              fontWeight: 500,
              cursor: 'pointer'
            }}
          >
            <RotateCcw size={14} aria-hidden="true" />
            <span>Start New Analysis</span>
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
