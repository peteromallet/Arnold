/**
 * ContributionErrorBoundary — Host-owned React error boundary for extension
 * contributions.
 *
 * Each boundary is scoped to a single contribution (slot, dialog, panel, or
 * inspector section) so that one misbehaving extension cannot break other
 * contributions or the built-in editor chrome.
 *
 * When an error is caught:
 *  1. A compact, contribution-only fallback UI is rendered in place of the
 *     contribution's content.
 *  2. A structured diagnostic is emitted to the console.
 *  3. The optional `onError` callback is invoked so the host can aggregate
 *     diagnostics into a shared diagnostics sink.
 *
 * The boundary preserves existing built-in fallback behaviour: if no extension
 * contribution declares a given slot/panel/section, the built-in content
 * renders normally without ever passing through this boundary.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ErrorBoundaryContributionKind =
  | 'slot'
  | 'dialog'
  | 'panel'
  | 'inspectorSection';

export interface ContributionErrorInfo {
  contributionId: string;
  extensionId?: string;
  kind: ErrorBoundaryContributionKind;
  error: Error;
  componentStack: string | null;
}

export interface ContributionErrorBoundaryProps {
  /** Stable ID of the failing contribution (used in diagnostics). */
  contributionId: string;
  /** Extension that owns this contribution (if known). */
  extensionId?: string;
  /** Contribution kind for contextual fallback label. */
  kind: ErrorBoundaryContributionKind;
  /** Human-readable label shown in the fallback UI (defaults to contributionId). */
  label?: string;
  /** Called when the boundary catches an error. */
  onError?: (info: ContributionErrorInfo) => void;
  children: ReactNode;
}

interface ContributionErrorBoundaryState {
  error: Error | null;
}

// ---------------------------------------------------------------------------
// Fallback UI
// ---------------------------------------------------------------------------

function ContributionErrorFallback({
  kind,
  label,
  error,
}: {
  kind: ErrorBoundaryContributionKind;
  label: string;
  error: Error | null;
}) {
  const kindLabel = {
    slot: 'Slot',
    dialog: 'Dialog',
    panel: 'Panel',
    inspectorSection: 'Inspector section',
  }[kind];

  // For the compact "inspectorSection" fallback, render even smaller.
  const isInline = kind === 'inspectorSection';

  return (
    <div
      role="alert"
      data-video-editor-contribution-error="true"
      data-video-editor-contribution-kind={kind}
      className={
        isInline
          ? 'rounded-md border border-red-500/30 bg-red-500/5 px-2 py-1 text-[10px] text-red-400'
          : 'rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2'
      }
    >
      <div className="flex items-start gap-1.5">
        <AlertTriangle
          className={isInline ? 'mt-px h-3 w-3 shrink-0 text-red-400' : 'mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400'}
        />
        <div className="min-w-0 flex-1">
          <span className="font-medium text-red-300">
            {kindLabel} error
          </span>
          <span className="text-red-400/70"> — {label}</span>
          {error && (
            <div
              className={
                isInline
                  ? 'mt-0.5 truncate text-[10px] text-red-400/50'
                  : 'mt-1 truncate text-[11px] text-red-400/50'
              }
              title={error.message}
            >
              {error.message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error boundary (class component — React error boundaries must be classes)
// ---------------------------------------------------------------------------

export class ContributionErrorBoundary extends Component<
  ContributionErrorBoundaryProps,
  ContributionErrorBoundaryState
> {
  constructor(props: ContributionErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ContributionErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const { contributionId, extensionId, kind, onError } = this.props;
    const componentStack = errorInfo.componentStack ?? null;

    // Emit structured diagnostic to the console (host-owned diagnostics path).
    if (typeof console !== 'undefined') {
      console.error(
        `[Extension contribution error] kind=${kind} contributionId="${contributionId}"` +
          (extensionId ? ` extensionId="${extensionId}"` : '') +
          `:`,
        error,
        componentStack ? `\nComponent stack:\n${componentStack}` : '',
      );
    }

    // Notify host diagnostics sink.
    onError?.({
      contributionId,
      extensionId,
      kind,
      error,
      componentStack,
    });
  }

  componentDidUpdate(
    _prevProps: ContributionErrorBoundaryProps,
    prevState: ContributionErrorBoundaryState,
  ): void {
    // Reset error state when children change (e.g. HMR or extension replacement).
    if (prevState.error !== null && this.props.children !== _prevProps.children) {
      // eslint-disable-next-line react/no-did-update-set-state -- intentional reset
      this.setState({ error: null });
    }
  }

  render(): ReactNode {
    if (this.state.error) {
      const { kind, label, contributionId } = this.props;
      const displayLabel = label ?? contributionId;
      return (
        <ContributionErrorFallback
          kind={kind}
          label={displayLabel}
          error={this.state.error}
        />
      );
    }

    return this.props.children;
  }
}
