/**
 * ExtensionManagerErrorBoundary — Host-owned React error boundary for the
 * Extension Manager UI.
 *
 * Wraps the entire manager so that a rendering failure in the manager tab
 * does not break the inspector or other editor chrome. Provides retry/reset
 * controls and distinct states for loading, empty, and render-error.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw, RotateCcw, Puzzle } from 'lucide-react';
import { Button } from '@/shared/components/ui/button.tsx';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ManagerErrorInfo {
  error: Error;
  componentStack: string | null;
}

export interface ExtensionManagerErrorBoundaryProps {
  /** Called when the boundary catches an error. */
  onError?: (info: ManagerErrorInfo) => void;
  /** Optional recovery key — when it changes the boundary resets. */
  recoveryKey?: string;
  children: ReactNode;
}

interface ExtensionManagerErrorBoundaryState {
  error: Error | null;
}

// ---------------------------------------------------------------------------
// States: Loading, Empty, RenderError
// ---------------------------------------------------------------------------

export function ManagerLoadingState() {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-8 text-muted-foreground"
      role="status"
      aria-label="Loading extensions"
    >
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground" />
      <span className="text-sm">Loading extensions…</span>
    </div>
  );
}

export function ManagerEmptyState() {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-8 text-muted-foreground"
      role="status"
      aria-label="No extensions loaded"
    >
      <Puzzle className="h-8 w-8 opacity-40" />
      <span className="text-sm">No extensions loaded.</span>
      <span className="text-xs text-muted-foreground/60">
        Extensions provided by the host will appear here.
      </span>
    </div>
  );
}

export function ManagerRenderErrorState({
  error,
  onRetry,
  onReset,
}: {
  error: Error | null;
  onRetry: () => void;
  onReset: () => void;
}) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-8 text-muted-foreground"
      role="alert"
      aria-label="Extension manager render error"
    >
      <AlertTriangle className="h-8 w-8 text-red-400" />
      <span className="text-sm font-medium text-red-400">
        Extension Manager Error
      </span>
      {error && (
        <span
          className="max-w-[280px] truncate text-xs text-red-400/70"
          title={error.message}
        >
          {error.message}
        </span>
      )}
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onRetry}
          aria-label="Retry loading extensions"
        >
          <RefreshCw className="mr-1 h-3.5 w-3.5" />
          Retry
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onReset}
          aria-label="Reset extension manager"
        >
          <RotateCcw className="mr-1 h-3.5 w-3.5" />
          Reset
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error boundary (class component)
// ---------------------------------------------------------------------------

export class ExtensionManagerErrorBoundary extends Component<
  ExtensionManagerErrorBoundaryProps,
  ExtensionManagerErrorBoundaryState
> {
  private _lastRecoveryKey: string | undefined;
  private _retryCounter = 0;

  constructor(props: ExtensionManagerErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
    this._lastRecoveryKey = props.recoveryKey;
  }

  static getDerivedStateFromError(
    error: Error,
  ): ExtensionManagerErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const componentStack = errorInfo.componentStack ?? null;

    if (typeof console !== 'undefined') {
      console.error(
        '[ExtensionManager] Render error caught by boundary:',
        error,
        componentStack ? `\nComponent stack:\n${componentStack}` : '',
      );
    }

    this.props.onError?.({ error, componentStack });
  }

  componentDidUpdate(
    prevProps: ExtensionManagerErrorBoundaryProps,
    prevState: ExtensionManagerErrorBoundaryState,
  ): void {
    if (prevState.error === null) return;

    const recoveryKeyChanged =
      this.props.recoveryKey !== undefined &&
      this.props.recoveryKey !== this._lastRecoveryKey;

    if (recoveryKeyChanged) {
      this._lastRecoveryKey = this.props.recoveryKey;
      this.setState({ error: null });
    }
  }

  handleRetry = () => {
    this._retryCounter++;
    this.setState({ error: null });
  };

  handleReset = () => {
    this._retryCounter = 0;
    this._lastRecoveryKey = undefined;
    this.setState({ error: null });
  };

  render(): ReactNode {
    if (this.state.error) {
      return (
        <ManagerRenderErrorState
          error={this.state.error}
          onRetry={this.handleRetry}
          onReset={this.handleReset}
        />
      );
    }

    return this.props.children;
  }
}
