import { RafLoopDetector } from '@/tools/video-editor/lib/perf-diagnostics.ts';

const EDGE_ZONE_PX = 40;
const MAX_SCROLL_SPEED = 12;

/**
 * Auto-scroll a container when the pointer is near its edges.
 * Call on every pointermove/dragover. Returns a cleanup function
 * that stops the scroll animation.
 */
export function createAutoScroller(
  container: HTMLElement,
  onTick?: (clientX: number, clientY: number) => void,
) {
  let frameId: number | null = null;
  let dx = 0;
  let dy = 0;
  let lastClientX = 0;
  let lastClientY = 0;

  const tick = () => {
    if (dx === 0 && dy === 0) {
      frameId = null;
      return;
    }

    container.scrollLeft += dx;
    container.scrollTop += dy;
    onTick?.(lastClientX, lastClientY);
    RafLoopDetector.track('autoScroll');
    frameId = requestAnimationFrame(tick);
  };

  const update = (clientX: number, clientY: number) => {
    lastClientX = clientX;
    lastClientY = clientY;
    const rect = container.getBoundingClientRect();

    // Vertical — extend top zone above the container (e.g. ruler area)
    const distFromTop = clientY - rect.top;
    const distFromBottom = rect.bottom - clientY;
    if (distFromTop < EDGE_ZONE_PX) {
      // When above the container (distFromTop < 0), scroll at max speed
      const factor = distFromTop < 0 ? 1 : (1 - distFromTop / EDGE_ZONE_PX);
      dy = -Math.round(MAX_SCROLL_SPEED * factor);
    } else if (distFromBottom < EDGE_ZONE_PX && distFromBottom >= 0) {
      dy = Math.round(MAX_SCROLL_SPEED * (1 - distFromBottom / EDGE_ZONE_PX));
    } else {
      dy = 0;
    }

    // Horizontal
    const distFromLeft = clientX - rect.left;
    const distFromRight = rect.right - clientX;
    if (distFromLeft < EDGE_ZONE_PX && distFromLeft >= 0) {
      dx = -Math.round(MAX_SCROLL_SPEED * (1 - distFromLeft / EDGE_ZONE_PX));
    } else if (distFromRight < EDGE_ZONE_PX && distFromRight >= 0) {
      dx = Math.round(MAX_SCROLL_SPEED * (1 - distFromRight / EDGE_ZONE_PX));
    } else {
      dx = 0;
    }

    if ((dx !== 0 || dy !== 0) && frameId === null) {
      frameId = requestAnimationFrame(tick);
    }
  };

  const stop = () => {
    dx = 0;
    dy = 0;
    if (frameId !== null) {
      cancelAnimationFrame(frameId);
      frameId = null;
    }
  };

  return { update, stop };
}
