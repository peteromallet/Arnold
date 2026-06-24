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
import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { useOptionalVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';

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
  /**
   * Opaque recovery key.  When this value changes, the boundary clears any
   * caught error and attempts a fresh render of `children`.
   *
   * If a `recoveryKey` is provided, the boundary will **not** auto-reset on
   * arbitrary children-reference changes — it only resets when the recovery
   * key changes.  This prevents infinite crash→recover→crash loops that would
   * otherwise occur when a parent re-renders a persistently-broken renderer.
   *
   * When no `recoveryKey` is given the boundary falls back to the legacy
   * behaviour of resetting whenever the `children` reference changes
   * (e.g. HMR or extension replacement).
   */
  recoveryKey?: string;
  /** Called when the boundary catches an error. */
  onError?: (info: ContributionErrorInfo) => void;
  /**
   * User-visible retry callback.  When provided, the fallback UI renders a
   * "Retry" button that invokes this callback.  The host wrapper uses this
   * to implement bounded, debounced retry via the lifecycle-host recovery
   * key system.
   *
   * When undefined (no owning extension known) the retry button is not shown
   * and the boundary falls back to legacy children-change reset.
   */
  onRetry?: () => void;
  /** When true, the retry button is disabled (retries exhausted). */
  retryDisabled?: boolean;
  /** Number of retries remaining (shown in button text). */
  retriesRemaining?: number;
  children: ReactNode;
}

export interface HostContributionErrorBoundaryProps {
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
  /**
   * Maximum number of user-initiated retry attempts when the owning extension
   * is known.  After this many retries the retry button is disabled until an
   * external recovery signal (e.g. extension re-activation) clears the error.
   *
   * @default 3
   */
  maxRetries?: number;
  /**
   * Minimum time (in ms) between user-initiated retry attempts.  Prevents
   * retry-storm when a persistently-broken renderer crashes on every attempt.
   *
   * @default 5000
   */
  retryDebounceMs?: number;
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
  onRetry,
  retryDisabled = false,
  retriesRemaining,
}: {
  kind: ErrorBoundaryContributionKind;
  label: string;
  error: Error | null;
  onRetry?: () => void;
  retryDisabled?: boolean;
  retriesRemaining?: number;
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
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            disabled={retryDisabled}
            data-video-editor-contribution-retry="true"
            className={
              isInline
                ? 'ml-auto shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium text-red-300 hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-40'
                : 'ml-auto shrink-0 rounded px-2 py-1 text-[11px] font-medium text-red-300 hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-40'
            }
            title={
              retryDisabled
                ? 'Retries exhausted — extension must be re-activated to recover'
                : retriesRemaining != null
                  ? `${retriesRemaining} retr${retriesRemaining === 1 ? 'y' : 'ies'} remaining`
                  : 'Retry this contribution'
            }
          >
            <RefreshCw
              className={isInline ? 'mr-0.5 inline h-2.5 w-2.5' : 'mr-1 inline h-3 w-3'}
            />
            {retryDisabled
              ? 'Exhausted'
              : retriesRemaining != null
                ? `Retry (${retriesRemaining})`
                : 'Retry'}
          </button>
        )}
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
  /** Last recovery key seen by this boundary — used to detect explicit reset. */
  private _lastRecoveryKey: string | undefined;

  constructor(props: ContributionErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
    this._lastRecoveryKey = props.recoveryKey;
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
    prevProps: ContributionErrorBoundaryProps,
    prevState: ContributionErrorBoundaryState,
  ): void {
    if (prevState.error === null) return;

    const recoveryKeyChanged =
      this.props.recoveryKey !== undefined &&
      this.props.recoveryKey !== this._lastRecoveryKey;

    const childrenChanged = this.props.children !== prevProps.children;

    // When a recoveryKey is provided, only reset on explicit key change.
    // Without a recoveryKey, fall back to the legacy children-change reset.
    const shouldReset =
      recoveryKeyChanged ||
      (this.props.recoveryKey === undefined && childrenChanged);

    if (shouldReset) {
      this._lastRecoveryKey = this.props.recoveryKey;
      this.setState({ error: null });
    }
  }

  render(): ReactNode {
    if (this.state.error) {
      const { kind, label, contributionId, onRetry, retryDisabled, retriesRemaining } = this.props;
      const displayLabel = label ?? contributionId;
      return (
        <ContributionErrorFallback
          kind={kind}
          label={displayLabel}
          error={this.state.error}
          onRetry={onRetry}
          retryDisabled={retryDisabled}
          retriesRemaining={retriesRemaining}
        />
      );
    }

    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// HostContributionErrorBoundary — function component wrapper that wires
// lifecycle-host-owned recovery keys and a user-visible bounded retry
// control into the underlying ContributionErrorBoundary class component.
// ---------------------------------------------------------------------------

/**
 * Host-owned contribution error boundary.
 *
 * Wraps {@link ContributionErrorBoundary} and wires in host-owned recovery-key
 * state from the {@link VideoEditorRuntimeContextValue}. When an owning
 * extension is known (`extensionId` is set), the boundary:
 *
 *  1. Pulls the current monotonic recovery key from the lifecycle host.
 *  2. Passes it to the underlying boundary, preventing legacy children-change
 *     auto-reset and anchoring reset semantics to host-owned lifecycle events.
 *  3. Exposes a user-visible "Retry" button on the error fallback.  Activating
 *     it increments the lifecycle-host recovery key (up to `maxRetries`, with
 *     at least `retryDebounceMs` between attempts) and triggers a fresh render
 *     of the contribution children.
 *
 * When no owning extension is known (`extensionId` is undefined or the runtime
 * context is unavailable) the boundary falls back to the legacy
 * {@link ContributionErrorBoundary} behaviour (reset on children change,
 * no recovery key, no retry button).
 *
 * The existing fallback appearance is fully preserved — this component only
 * adds host wiring and the bounded, user-visible retry control.
 */
export function HostContributionErrorBoundary({
  contributionId,
  extensionId,
  kind,
  label,
  onError,
  children,
  maxRetries = 3,
  retryDebounceMs = 5000,
}: HostContributionErrorBoundaryProps) {
  const runtime = useOptionalVideoEditorRuntime();

  // ── Retry bookkeeping (reset when extensionId changes) ────────────────
  const retryCountRef = useRef(0);
  const lastRetryTimeRef = useRef(0);

  // Reset retry state when the owning extension changes identity.
  useEffect(() => {
    retryCountRef.current = 0;
    lastRetryTimeRef.current = 0;
  }, [extensionId]);

  // ── Recovery key state ────────────────────────────────────────────────
  // We maintain a local counter so that HostContributionErrorBoundary can
  // trigger its own re-render when it increments the recovery key.
  // The actual host key is passed through for external resets.
  const [localEpoch, setLocalEpoch] = useState(0);

  // Read the host-owned recovery key (changes on activation, manifest
  // replacement, re-add, or external incrementRecoveryKey calls).
  const hostKey = useMemo(() => {
    if (extensionId && runtime?.getRecoveryKey) {
      const key = runtime.getRecoveryKey(extensionId);
      return key !== '0' ? key : undefined;
    }
    return undefined;
  }, [extensionId, runtime]);

  // Reset local epoch when the host key changes externally (so external
  // recovery signals are honoured without double-incrementing).
  useEffect(() => {
    setLocalEpoch(0);
  }, [hostKey]);

  // Composite recovery key: host key + local retry epoch.
  // When either changes, the underlying boundary resets.
  const recoveryKey = useMemo(() => {
    if (!extensionId || !hostKey) return undefined;
    return `${hostKey}:${localEpoch}`;
  }, [extensionId, hostKey, localEpoch]);

  // ── Error handler (no auto-retry — retry is user-initiated) ───────────
  const handleError = useCallback(
    (info: ContributionErrorInfo) => {
      // Forward to the caller's callback only.
      onError?.(info);
    },
    [onError],
  );

  // ── Bounded, debounced retry handler for the visible button ───────────
  const handleRetry = useCallback(() => {
    if (!extensionId || !runtime?.incrementRecoveryKey) return;

    const now = Date.now();
    const elapsed = now - lastRetryTimeRef.current;

    if (retryCountRef.current >= maxRetries) return; // exhausted
    if (elapsed < retryDebounceMs) return; // debounced

    retryCountRef.current++;
    lastRetryTimeRef.current = now;

    // Increment the host key so that other boundaries scoped to the
    // same extension also see the recovery signal.
    runtime.incrementRecoveryKey(extensionId);

    // Bump our local epoch to trigger re-render with the new composite key.
    setLocalEpoch((prev) => prev + 1);
  }, [extensionId, runtime, maxRetries, retryDebounceMs]);

  // ── Derived retry button state ────────────────────────────────────────
  const retriesRemaining = Math.max(0, maxRetries - retryCountRef.current);
  const retryDisabled = retryCountRef.current >= maxRetries;

  // Only expose retry when the owning extension is known.
  const onRetry = extensionId ? handleRetry : undefined;

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <ContributionErrorBoundary
      contributionId={contributionId}
      extensionId={extensionId}
      kind={kind}
      label={label}
      recoveryKey={recoveryKey}
      onError={handleError}
      onRetry={onRetry}
      retryDisabled={retryDisabled}
      retriesRemaining={retriesRemaining}
    >
      {children}
    </ContributionErrorBoundary>
  );
}
