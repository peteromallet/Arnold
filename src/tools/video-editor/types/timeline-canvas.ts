export interface TimelineAction {
  id: string;
  start: number;
  end: number;
  effectId: string;
  selected?: boolean;
  flexible?: boolean;
  movable?: boolean;
  disable?: boolean;
  minStart?: number;
  maxEnd?: number;
}

export interface TimelineRow {
  id: string;
  actions: TimelineAction[];
  rowHeight?: number;
  selected?: boolean;
  classNames?: string[];
}

export interface TimelineEffectSourceParam {
  time: number;
  isPlaying: boolean;
  action: TimelineAction;
  effect: TimelineEffect;
  engine: any;
}

export interface TimelineEffectSource {
  start?: (param: TimelineEffectSourceParam) => void;
  enter?: (param: TimelineEffectSourceParam) => void;
  update?: (param: TimelineEffectSourceParam) => void;
  leave?: (param: TimelineEffectSourceParam) => void;
  stop?: (param: TimelineEffectSourceParam) => void;
}

export interface TimelineEffect {
  id: string;
  name?: string;
  source?: TimelineEffectSource;
}

export interface TimelineCanvasHandle {
  target: HTMLElement | null;
  listener: any;
  isPlaying: boolean;
  isPaused: boolean;
  setTime: (time: number) => void;
  getTime: () => number;
  setPlayRate: (rate: number) => void;
  getPlayRate: () => number;
  reRender: () => void;
  play: (param: {
    toTime?: number;
    autoEnd?: boolean;
    runActionIds?: string[];
  }) => boolean;
  pause: () => void;
  setScrollLeft: (value: number) => void;
}

/** A ghost preview entry for rendering proposal previews on the timeline.
 *  Uses distinct data-testid attributes and never collides with canonical
 *  data-action-id (which belongs to real rows/actions). */
export interface TimelineGhostEntry {
  /** Stable ghost identifier (not a clip ID — avoids data-action-id collisions). */
  id: string;
  /** Track ID this ghost overlay belongs to. */
  trackId: string;
  /** Start time in seconds (canonical transform math). */
  start: number;
  /** End time in seconds (canonical transform math). */
  end: number;
  /** The kind of diff change being previewed. */
  kind: 'added' | 'removed' | 'modified' | 'reordered';
  /** Optional clip type label for diagnostics / tooltip. */
  clipType?: string;
}
