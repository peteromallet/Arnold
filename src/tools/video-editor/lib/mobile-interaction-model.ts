export type TimelineDeviceClass = 'desktop' | 'tablet' | 'phone';

export type TimelineInputModality = 'mouse' | 'touch' | 'pen' | 'keyboard' | 'unknown';

export type TimelineInteractionMode = 'browse' | 'select' | 'move' | 'trim' | 'precision';

export type TimelineGestureOwner =
  | 'none'
  | 'timeline'
  | 'ruler'
  | 'clip'
  | 'trim'
  | 'preview'
  | 'inspector'
  | 'shell';

export type TimelineInteractionTargetKind =
  | 'clip'
  | 'shader'
  | 'track'
  | 'timeline'
  | 'selection'
  | 'preview'
  | 'overlay'
  | 'shell';

export interface TimelineInteractionTarget {
  kind: TimelineInteractionTargetKind;
  clipId?: string | null;
  trackId?: string | null;
  clipIds?: string[];
  shaderScope?: 'clip' | 'postprocess';
  shaderId?: string | null;
  extensionId?: string | null;
  contributionId?: string | null;
}

export type TimelineContextTarget = TimelineInteractionTarget | null;
export type TimelineInspectorTarget = TimelineInteractionTarget | null;

export interface MobileInteractionPolicy {
  deviceClass: TimelineDeviceClass;
  inputModality: TimelineInputModality;
  interactionMode: TimelineInteractionMode;
  gestureOwner: TimelineGestureOwner;
  precisionEnabled: boolean;
  contextTarget: TimelineContextTarget;
  inspectorTarget: TimelineInspectorTarget;
}

export function resolveTimelineDeviceClass({
  isMobile,
  isTablet,
}: {
  isMobile: boolean;
  isTablet: boolean;
}): TimelineDeviceClass {
  if (isTablet) {
    return 'tablet';
  }

  return isMobile ? 'phone' : 'desktop';
}

export function resolveInputModalityFromPointerType(
  pointerType: string | null | undefined,
): TimelineInputModality {
  switch (pointerType) {
    case 'mouse':
      return 'mouse';
    case 'touch':
      return 'touch';
    case 'pen':
      return 'pen';
    default:
      return 'unknown';
  }
}

export function getDefaultInteractionMode(
  deviceClass: TimelineDeviceClass,
): TimelineInteractionMode {
  return deviceClass === 'phone' ? 'browse' : 'select';
}

export function createMobileInteractionPolicy(
  deviceClass: TimelineDeviceClass,
): MobileInteractionPolicy {
  return {
    deviceClass,
    inputModality: 'unknown',
    interactionMode: getDefaultInteractionMode(deviceClass),
    gestureOwner: 'none',
    precisionEnabled: false,
    contextTarget: null,
    inspectorTarget: null,
  };
}

export function isTouchTimelineInput(
  deviceClass: TimelineDeviceClass,
  inputModality: TimelineInputModality,
): boolean {
  return inputModality === 'touch' && (deviceClass === 'phone' || deviceClass === 'tablet');
}

export function shouldAllowTouchClipDrag(
  deviceClass: TimelineDeviceClass,
  inputModality: TimelineInputModality,
  interactionMode: TimelineInteractionMode,
): boolean {
  if (!isTouchTimelineInput(deviceClass, inputModality)) {
    return true;
  }

  return interactionMode === 'move';
}

export function shouldAllowTouchMarquee(
  deviceClass: TimelineDeviceClass,
  inputModality: TimelineInputModality,
  interactionMode: TimelineInteractionMode,
): boolean {
  if (!isTouchTimelineInput(deviceClass, inputModality)) {
    return true;
  }

  return deviceClass === 'tablet' && interactionMode === 'select';
}

export function shouldExpandTouchTrimHandles(
  deviceClass: TimelineDeviceClass,
  inputModality: TimelineInputModality,
  interactionMode: TimelineInteractionMode,
): boolean {
  return isTouchTimelineInput(deviceClass, inputModality) && interactionMode === 'trim';
}

export function shouldToggleTouchSelection(
  deviceClass: TimelineDeviceClass,
  inputModality: TimelineInputModality,
  interactionMode: TimelineInteractionMode,
): boolean {
  return isTouchTimelineInput(deviceClass, inputModality) && interactionMode === 'select';
}

export function shouldPreserveTouchSelectionForMove(
  deviceClass: TimelineDeviceClass,
  inputModality: TimelineInputModality,
  interactionMode: TimelineInteractionMode,
): boolean {
  return isTouchTimelineInput(deviceClass, inputModality) && interactionMode === 'move';
}

export function areTimelineInteractionTargetsEqual(
  left: TimelineInteractionTarget | null | undefined,
  right: TimelineInteractionTarget | null | undefined,
): boolean {
  if (left === right) {
    return true;
  }

  if (!left || !right) {
    return false;
  }

  if (left.kind !== right.kind || left.clipId !== right.clipId || left.trackId !== right.trackId) {
    return false;
  }

  const leftClipIds = left.clipIds ?? [];
  const rightClipIds = right.clipIds ?? [];
  if (leftClipIds.length !== rightClipIds.length) {
    return false;
  }

  return leftClipIds.every((clipId, index) => clipId === rightClipIds[index]);
}
