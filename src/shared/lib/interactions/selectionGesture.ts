type AdditiveSelectionEvent = Pick<MouseEvent, 'metaKey' | 'ctrlKey' | 'shiftKey'>;
type PointerButtonEvent = Pick<PointerEvent | MouseEvent, 'button'>;
type Point = { x: number; y: number };

export function isAdditiveSelectionEvent(event: AdditiveSelectionEvent): boolean {
  return Boolean(event.metaKey || event.ctrlKey || event.shiftKey);
}

export function isPrimaryPointer(event: PointerButtonEvent): boolean {
  return event.button === 0;
}

export function isClickLikePointerGesture(
  start: Point,
  end: Point,
  threshold = 8,
): boolean {
  return Math.hypot(end.x - start.x, end.y - start.y) <= threshold;
}
