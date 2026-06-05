import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.js';
import { PageErrorBoundary } from './components/error-boundaries/page-error-boundary.js';
import { OfflineProvider } from './components/offline/offline-provider.js';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PageErrorBoundary>
      <OfflineProvider>
        <App />
      </OfflineProvider>
    </PageErrorBoundary>
  </React.StrictMode>,
);
