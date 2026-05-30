import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.js';

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return React.createElement('div', {
        style: { padding: 32, fontFamily: 'monospace', background: '#fff0f0', color: '#900', minHeight: '100vh' },
      },
        React.createElement('h1', null, 'React render crash'),
        React.createElement('pre', { style: { whiteSpace: 'pre-wrap', wordBreak: 'break-word' } }, this.state.error.message),
        React.createElement('pre', { style: { whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, marginTop: 16, color: '#666' } }, this.state.error.stack),
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
