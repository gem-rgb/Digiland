import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { cn } from '../../lib/utils.js';
import { generateReferenceId } from '../../lib/error-codes.js';

interface SectionErrorFallbackProps {
  error: Error;
  resetError: () => void;
  sectionName: string;
}

function SectionErrorFallback({ error, resetError, sectionName }: SectionErrorFallbackProps) {
  const referenceId = React.useMemo(() => generateReferenceId(), []);

  React.useEffect(() => {
    // Log internally — never expose to the user
    console.error(
      `[digiland] SectionErrorBoundary caught error in "${sectionName}":`,
      error,
      { referenceId },
    );
  }, [error, sectionName, referenceId]);

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        'rounded-3xl border border-border/70 bg-white/92 p-6 shadow-soft',
      )}
    >
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50">
          <AlertTriangle className="h-6 w-6 text-amber-600" aria-hidden="true" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-bold text-foreground">
            This section could not be displayed
          </h3>
          <p className="text-sm text-muted-foreground">
            Something went wrong while loading this content. The rest of the page is still available.
          </p>
        </div>
        <button
          type="button"
          onClick={resetError}
          className={cn(
            'inline-flex h-10 items-center justify-center gap-2 rounded-full',
            'border border-border bg-white px-5 text-sm font-semibold text-foreground',
            'transition-colors hover:bg-muted',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          )}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Retry
        </button>
        <p className="text-xs text-muted-foreground">
          Reference: {referenceId}
        </p>
      </div>
    </div>
  );
}

interface SectionErrorBoundaryProps {
  children: React.ReactNode;
  sectionName: string;
  fallback?: React.ComponentType<{
    error: Error;
    resetError: () => void;
    sectionName: string;
  }>;
}

interface SectionErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class SectionErrorBoundary extends React.Component<
  SectionErrorBoundaryProps,
  SectionErrorBoundaryState
> {
  constructor(props: SectionErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): SectionErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error(
      `[digiland] SectionErrorBoundary in "${this.props.sectionName}":`,
      error,
      errorInfo,
    );
  }

  resetError = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      const FallbackComponent = this.props.fallback ?? SectionErrorFallback;
      return (
        <FallbackComponent
          error={this.state.error}
          resetError={this.resetError}
          sectionName={this.props.sectionName}
        />
      );
    }
    return this.props.children;
  }
}
