import React from 'react';
import { AlertTriangle, ArrowLeft, Home, HelpCircle, RefreshCw } from 'lucide-react';
import { cn } from '../../lib/utils.js';
import { generateReferenceId } from '../../lib/error-codes.js';

interface PageErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

interface PageErrorBoundaryProps {
  children: React.ReactNode;
}

function PageErrorFallback({ error, resetError }: { error: Error; resetError: () => void }) {
  const referenceId = React.useMemo(() => generateReferenceId(), []);

  React.useEffect(() => {
    console.error('[digiland] PageErrorBoundary caught error:', error, { referenceId });
  }, [error, referenceId]);

  const handleGoBack = () => {
    window.history.back();
  };

  const handleGoDashboard = () => {
    window.location.href = '/';
  };

  const handleRefresh = () => {
    window.location.reload();
  };

  const handleContactSupport = () => {
    window.location.href = '/support/';
  };

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="flex min-h-screen items-center justify-center bg-gradient-to-b from-stone-50 to-white p-6"
    >
      <div className="w-full max-w-lg space-y-8 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-rose-50">
          <AlertTriangle className="h-8 w-8 text-rose-600" aria-hidden="true" />
        </div>

        <div className="space-y-3">
          <h1 className="text-2xl font-black tracking-tight text-foreground">
            Something went wrong
          </h1>
          <p className="text-sm leading-7 text-muted-foreground">
            We encountered an unexpected error while loading this page. Our team has been notified
            and is working on a fix. Your data is safe.
          </p>
        </div>

        <div className="rounded-3xl border border-border/70 bg-white/92 p-5 shadow-soft">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">
            Reference ID
          </p>
          <p className="mt-1 font-mono text-sm font-semibold text-foreground">{referenceId}</p>
        </div>

        <nav aria-label="Error recovery options" className="flex flex-col gap-3">
          <button
            type="button"
            onClick={resetError}
            className={cn(
              'inline-flex h-12 w-full items-center justify-center gap-2 rounded-full',
              'bg-emerald-700 px-6 text-sm font-semibold text-white',
              'transition-colors hover:bg-emerald-800',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            )}
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Try again
          </button>

          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={handleGoBack}
              className={cn(
                'inline-flex h-11 items-center justify-center gap-2 rounded-full',
                'border border-border bg-white px-4 text-sm font-semibold text-foreground',
                'transition-colors hover:bg-muted',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              )}
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Go back
            </button>

            <button
              type="button"
              onClick={handleGoDashboard}
              className={cn(
                'inline-flex h-11 items-center justify-center gap-2 rounded-full',
                'border border-border bg-white px-4 text-sm font-semibold text-foreground',
                'transition-colors hover:bg-muted',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              )}
            >
              <Home className="h-4 w-4" aria-hidden="true" />
              Dashboard
            </button>
          </div>

          <button
            type="button"
            onClick={handleContactSupport}
            className={cn(
              'inline-flex h-11 w-full items-center justify-center gap-2 rounded-full',
              'border border-border bg-white px-4 text-sm font-semibold text-foreground',
              'transition-colors hover:bg-muted',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            )}
          >
            <HelpCircle className="h-4 w-4" aria-hidden="true" />
            Contact support
          </button>
        </nav>
      </div>
    </div>
  );
}

export class PageErrorBoundary extends React.Component<
  PageErrorBoundaryProps,
  PageErrorBoundaryState
> {
  constructor(props: PageErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): PageErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // In production, never expose stack traces to users.
    // Log to internal monitoring only.
    console.error('[digiland] Unhandled page error:', error, errorInfo);

    // If an error reporting service is available, send the error there.
    // e.g., Sentry, DataDog, etc.
    if (typeof window !== 'undefined' && (window as any).__DIGILAND_REPORT_ERROR__) {
      (window as any).__DIGILAND_REPORT_ERROR__(error, errorInfo);
    }
  }

  resetError = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      return <PageErrorFallback error={this.state.error} resetError={this.resetError} />;
    }
    return this.props.children;
  }
}
