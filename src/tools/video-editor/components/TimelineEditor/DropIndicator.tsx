import {
  forwardRef,
  useImperativeHandle,
  useLayoutEffect,
  useState,
  type MutableRefObject,
} from 'react';
import { createPortal } from 'react-dom';
import type { GhostRect } from '@/tools/video-editor/lib/multi-drag-utils.ts';
import { VIDEO_EDITOR_THEME_VARS } from '@/tools/video-editor/lib/themeTokens.ts';

export interface DropIndicatorPosition {
  rowTop: number;
  rowHeight: number;
  rowLeft: number;
  rowWidth: number;
  lineLeft: number;
  ghostLeft: number;
  ghostTop: number;
  ghostWidth: number;
  ghostHeight: number;
  ghostLabel: string;
  label: string;
  isNewTrack: boolean;
  isNewTrackTop?: boolean;
  trackId?: string;
  /** When non-null, describes the kind of track that will be created. */
  newTrackKind: string | null;
  reject: boolean;
}

export interface DropIndicatorHandle {
  show(position: DropIndicatorPosition): void;
  showSecondaryGhosts(ghosts: GhostRect[]): void;
  hide(): void;
}

interface DropIndicatorProps {
  editAreaRef: MutableRefObject<HTMLElement | null>;
  onNewTrackLabel?: (label: string | null) => void;
}

export const DropIndicator = forwardRef<DropIndicatorHandle, DropIndicatorProps>(function DropIndicator(
  { editAreaRef, onNewTrackLabel },
  ref,
) {
  const [position, setPosition] = useState<DropIndicatorPosition | null>(null);
  const [secondaryGhosts, setSecondaryGhosts] = useState<GhostRect[]>([]);

  useImperativeHandle(ref, () => ({
    show(nextPosition) {
      setPosition(nextPosition);
    },
    showSecondaryGhosts(ghosts) {
      setSecondaryGhosts(ghosts);
    },
    hide() {
      setPosition(null);
      setSecondaryGhosts([]);
    },
  }), []);

  useLayoutEffect(() => {
    const editArea = editAreaRef.current;
    if (!editArea) {
      return undefined;
    }

    // Only show the "create new track" affordance when dragging below all rows
    // (not for kind-mismatch redirects — those resolve silently to a compatible track)
    const showNewTrack = position?.isNewTrack === true && position?.trackId === undefined;
    editArea.classList.toggle('drop-target-new-track', showNewTrack);
    const wrapper = editArea.closest('.timeline-wrapper');
    wrapper?.classList.toggle('drop-target-new-track', showNewTrack);

    if (showNewTrack) {
      const kind = position?.newTrackKind ?? 'visual';
      const where = position?.isNewTrackTop ? 'top' : 'bottom';
      onNewTrackLabel?.(`Drop to create new ${kind} track at ${where}`);
    } else {
      onNewTrackLabel?.(null);
    }

    return () => {
      editArea.classList.remove('drop-target-new-track');
      wrapper?.classList.remove('drop-target-new-track');
      onNewTrackLabel?.(null);
    };
  }, [editAreaRef, onNewTrackLabel, position?.isNewTrack, position?.isNewTrackTop, position?.newTrackKind, position?.trackId]);

  if (!position || typeof document === 'undefined') {
    return null;
  }

  const labelLeft = position.lineLeft - 30;
  const labelTop = position.rowTop - 16;

  // New-track edge indicator: glow along top or bottom of the timeline
  const editArea = editAreaRef.current;
  const showNewTrackEdge = position.isNewTrack && position.trackId === undefined && editArea;
  let edgeTop = 0;
  if (showNewTrackEdge) {
    const editRect = editArea.getBoundingClientRect();
    edgeTop = position.isNewTrackTop ? editRect.top : editRect.bottom;
  }

  return createPortal(
    <div style={VIDEO_EDITOR_THEME_VARS}>
      {showNewTrackEdge && (
        <div
          className="drop-indicator-new-track-edge"
          style={{
            left: position.rowLeft,
            top: edgeTop - 1,
            width: position.rowWidth,
            zIndex: 99999,
          }}
        />
      )}
      {!showNewTrackEdge && (
        <div
          className={position.reject ? 'drop-indicator-row drop-indicator-row--reject' : 'drop-indicator-row'}
          style={{
            left: position.rowLeft,
            top: position.rowTop,
            width: position.rowWidth,
            height: position.rowHeight,
            zIndex: 99998,
          }}
        />
      )}
      {!position.isNewTrack && (
        <>
          <div
            className="drop-indicator-line"
            style={{ left: position.lineLeft, top: position.rowTop, height: position.rowHeight, zIndex: 99999 }}
          />
          <div
            className="drop-indicator-ghost"
            style={{
              left: position.ghostLeft,
              top: position.ghostTop,
              width: position.ghostWidth,
              height: position.ghostHeight,
              zIndex: 99998,
            }}
          >
            <span className="drop-indicator-ghost-label">{position.ghostLabel}</span>
          </div>
          <div
            className="drop-indicator-label"
            style={{ left: labelLeft, top: labelTop, zIndex: 100000 }}
          >
            {position.label}
          </div>
        </>
      )}
      {secondaryGhosts.map((ghost, i) => (
        <div
          key={i}
          className="drop-indicator-ghost"
          style={{
            left: ghost.left,
            top: ghost.top,
            width: ghost.width,
            height: ghost.height,
            zIndex: 99997,
            opacity: 0.6,
          }}
        />
      ))}
    </div>,
    document.body,
  );
});
