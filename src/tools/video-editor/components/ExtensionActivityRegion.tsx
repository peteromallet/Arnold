/**
 * ExtensionActivityRegion — M1 shallow placeholder for extension status events.
 *
 * Renders between the toolbar and timeline in TimelineEditorShellCore.
 * In M1 this is a contract-only placeholder: it exposes the minimal props and
 * renders status events with dismiss behavior but does NOT mount full agent
 * or diagnostic panels (those are later-milestone integrations).
 *
 * Future milestones will wire this region to the extension lifecycle host's
 * diagnostic collection, agent tool invocation status, and proposal import
 * feedback.
 */

import { useCallback, type FC, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn.ts';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Severity-driven kind for an extension status event. */
export type ExtensionStatusEventKind = 'info' | 'warning' | 'error' | 'success';

/** A single extension status event surfaced in the activity region. */
export interface ExtensionStatusEvent {
  /** Unique identifier for this event (used for dismiss targeting). */
  id: string;
  /** The extension that produced this event. */
  extensionId: string;
  /** Severity kind. */
  kind: ExtensionStatusEventKind;
  /** Human-readable event message. */
  message: string;
  /** Unix-ms timestamp of event origin. */
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ExtensionActivityRegionProps {
  /** Ordered list of status events to render (newest-first recommended). */
  statusEvents: readonly ExtensionStatusEvent[];
  /** Called when the user dismisses a specific event by id. */
  onDismiss: (eventId: string) => void;
  /** When true, the region renders in an expanded variant (future use). */
  isExpanded?: boolean;
  /**
   * Optional children rendered inside the activity region.
   *
   * Use this to mount panel content (e.g. ProposalPanel) alongside
   * extension status events.  Children are rendered below the status
   * event list so that status events remain prominent.
   */
  children?: ReactNode;
}

// ---------------------------------------------------------------------------
// Style helpers
// ---------------------------------------------------------------------------

const KIND_BORDER: Record<ExtensionStatusEventKind, string> = {
  info: 'border-blue-500/30',
  warning: 'border-yellow-500/30',
  error: 'border-red-500/30',
  success: 'border-emerald-500/30',
};

const KIND_BG: Record<ExtensionStatusEventKind, string> = {
  info: 'bg-blue-500/10',
  warning: 'bg-yellow-500/10',
  error: 'bg-red-500/10',
  success: 'bg-emerald-500/10',
};

const KIND_TEXT: Record<ExtensionStatusEventKind, string> = {
  info: 'text-blue-200',
  warning: 'text-yellow-200',
  error: 'text-red-200',
  success: 'text-emerald-200',
};

const KIND_LABEL: Record<ExtensionStatusEventKind, string> = {
  info: 'Info',
  warning: 'Warn',
  error: 'Error',
  success: 'OK',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Shallow event-rendering placeholder for the extension activity region.
 *
 * In M1 this is intentionally minimal — it renders status events with
 * dismiss buttons but does not wire agent invocation feedback, diagnostic
 * panels, or proposal-import status. Those are later-milestone additions.
 */
export const ExtensionActivityRegion: FC<ExtensionActivityRegionProps> = ({
  statusEvents,
  onDismiss,
  isExpanded = false,
  children,
}) => {
  const handleDismiss = useCallback(
    (eventId: string) => {
      onDismiss(eventId);
    },
    [onDismiss],
  );

  const hasEvents = statusEvents.length > 0;
  const hasChildren = children !== undefined && children !== null;

  // Render nothing only when there is truly nothing to show.
  if (!hasEvents && !hasChildren) {
    return null;
  }

  return (
    <div
      data-video-editor-activity-region="true"
      data-video-editor-activity-expanded={isExpanded ? 'true' : 'false'}
      className={cn(
        'flex flex-col gap-1 rounded-lg border border-border/60 bg-card/80 px-2 py-1.5 text-[11px]',
        isExpanded && 'gap-2 px-3 py-2',
      )}
      role="region"
      aria-label="Extension activity"
    >
      {hasEvents && (
        <>
          {statusEvents.map((event) => (
            <div
              key={event.id}
              data-video-editor-activity-event={event.id}
              data-video-editor-activity-event-kind={event.kind}
              className={cn(
                'flex items-start gap-2 rounded border px-2 py-1',
                KIND_BORDER[event.kind],
                KIND_BG[event.kind],
              )}
            >
              {/* Kind badge */}
              <span
                className={cn(
                  'shrink-0 rounded px-1 py-0 text-[9px] font-semibold uppercase tracking-[0.12em]',
                  KIND_TEXT[event.kind],
                  'bg-background/40',
                )}
              >
                {KIND_LABEL[event.kind]}
              </span>

              {/* Message */}
              <span className="min-w-0 flex-1 truncate text-muted-foreground">
                <span className="font-mono text-[10px] text-muted-foreground/60">
                  {event.extensionId}
                </span>
                <span className="mx-1 text-border">·</span>
                {event.message}
              </span>

              {/* Timestamp */}
              {isExpanded && (
                <span className="shrink-0 text-[10px] text-muted-foreground/50 tabular-nums">
                  {new Date(event.timestamp).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                  })}
                </span>
              )}

              {/* Dismiss button */}
              <button
                type="button"
                data-video-editor-activity-dismiss={event.id}
                className="shrink-0 rounded p-0.5 text-muted-foreground/40 transition-colors hover:bg-muted hover:text-foreground motion-reduce:transition-none"
                onClick={() => handleDismiss(event.id)}
                aria-label={`Dismiss ${event.kind} event from ${event.extensionId}`}
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}

          {/* Collapsed summary when not expanded and many events */}
          {!isExpanded && statusEvents.length > 3 && (
            <div className="text-center text-[10px] text-muted-foreground/50">
              +{statusEvents.length - 3} more event{statusEvents.length - 3 !== 1 ? 's' : ''}
            </div>
          )}
        </>
      )}

      {/* Children slot — rendered below status events so they remain prominent */}
      {hasChildren && (
        <div data-video-editor-activity-children="true">
          {children}
        </div>
      )}
    </div>
  );
};
