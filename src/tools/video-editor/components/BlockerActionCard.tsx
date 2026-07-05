/**
 * BlockerActionCard — shared card for surfacing a blocker diagnostic.
 *
 * Renders severity, diagnostic code, message, and exactly one next-action
 * button wired to `onAction`.  Consumers (export guard summary, render
 * planner blocker panel, inline clip overlays) provide the diagnostic
 * payload and the action callback.
 *
 * @hostOwned — NOT exported through public SDK contracts.
 */

import type { DiagnosticSeverity } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Public props
// ---------------------------------------------------------------------------

/** Shape of the next-action payload that drives the single CTA button. */
export interface BlockerActionCardNextAction {
  /** Action kind (e.g. 'materialize', 'bake', 'open-settings'). */
  kind: string;
  /** Human-readable button label. */
  label: string;
  /** Optional longer description surfaced as a tooltip. */
  message?: string;
}

export interface BlockerActionCardProps {
  /** Diagnostic severity — drives the visual badge and data attribute. */
  severity: DiagnosticSeverity;
  /** Canonical diagnostic code (e.g. `composition/effect-missing-ref`). */
  code: string;
  /** Human-readable diagnostic message. */
  message: string;
  /** Next-action descriptor. When present together with `onAction` the
   *  single CTA button is rendered; otherwise no button appears. */
  nextAction?: BlockerActionCardNextAction;
  /** Callback invoked when the action button is clicked. */
  onAction?: () => void;
}

function titleCase(value: string): string {
  return value
    .split(/[-_\s]+/u)
    .filter(Boolean)
    .map((segment) => segment[0]?.toUpperCase() + segment.slice(1))
    .join(' ');
}

function defaultActionLabel(kind: string, route?: string): string {
  switch (kind) {
    case 'select-route':
      return route ? `Select ${route}` : 'Select Route';
    case 'materialize':
      return 'Materialize';
    case 'bake':
      return 'Bake';
    case 'invoke-agent':
      return 'Invoke Agent';
    case 'open-settings':
      return 'Open Settings';
    case 'install-extension':
      return 'Install Extension';
    case 'enable-extension':
      return 'Enable Extension';
    case 'resolve-blockers':
      return 'Resolve Blockers';
    case 'start-process':
      return 'Start Process';
    default:
      return titleCase(kind);
  }
}

export function normalizeBlockerActionCardNextAction(
  value: unknown,
  fallback?: Partial<BlockerActionCardNextAction>,
): BlockerActionCardNextAction | undefined {
  if (value == null || typeof value !== 'object') {
    if (!fallback?.kind || !fallback.label) return undefined;
    return {
      kind: fallback.kind,
      label: fallback.label,
      ...(fallback.message ? { message: fallback.message } : {}),
    };
  }

  const record = value as Record<string, unknown>;
  const kind = typeof record.kind === 'string'
    ? record.kind
    : fallback?.kind;
  if (!kind) return undefined;

  const route = typeof record.route === 'string' ? record.route : undefined;
  const label = typeof record.label === 'string'
    ? record.label
    : fallback?.label ?? defaultActionLabel(kind, route);
  const message = typeof record.message === 'string'
    ? record.message
    : fallback?.message;

  return {
    kind,
    label,
    ...(message ? { message } : {}),
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BlockerActionCard({
  severity,
  code,
  message,
  nextAction,
  onAction,
}: BlockerActionCardProps) {
  const showAction = nextAction != null && onAction != null;

  return (
    <div
      data-video-editor-blocker-action-card
      data-video-editor-blocker-severity={severity}
      data-video-editor-blocker-code={code}
      role="alert"
    >
      <div className="blocker-action-card-header">
        <span
          className="blocker-action-card-severity"
          data-video-editor-blocker-severity-badge={severity}
        >
          {severity.toUpperCase()}
        </span>
        <code className="blocker-action-card-code">{code}</code>
      </div>

      <p className="blocker-action-card-message">{message}</p>

      {showAction && (
        <button
          type="button"
          className="blocker-action-card-action"
          data-video-editor-blocker-action-kind={nextAction!.kind}
          title={nextAction!.message}
          onClick={onAction}
        >
          {nextAction!.label}
        </button>
      )}
    </div>
  );
}
