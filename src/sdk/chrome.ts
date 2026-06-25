// ---------------------------------------------------------------------------
// M2a — Core SDK boundary: chrome contracts
// ---------------------------------------------------------------------------
//
// These contracts define the type surface for the extension chrome service
// (toast, progress, save, render-status events) and the associated event
// payload types.  The module is kept modality-neutral: it exports only the
// interface contracts with no runtime dependency on any video-editor subsystem.
//
// Extracted from src/sdk/index.ts during M2a Step 9 (T12).
// ---------------------------------------------------------------------------

import type { DiagnosticSeverity } from './diagnostics';
import type { DisposeHandle } from './dispose';

/** Chrome service: host-visible toast/progress/subscribe scaffolding. */
export interface ExtensionChromeService {
  toast(message: string, severity?: DiagnosticSeverity): void;
  progress(percent: number, label?: string): void;
  subscribe<E extends ChromeEvent>(
    event: E,
    handler: (payload: ChromeEventPayload<E>) => void,
  ): DisposeHandle;
  /**
   * Focus an element matching the CSS selector within the editor shell root.
   *
   * Scoped to the editor shell root: only descendants of the shell root are
   * considered valid targets.  Emits diagnostics when:
   * - No shell root is mounted (`chrome/focus-no-shell`)
   * - The selector matches an element outside the shell root, e.g. a portal
   *   target (`chrome/focus-out-of-shell`)
   * - The selector does not match any element (`chrome/focus-missing-selector`)
   *
   * Safe to call from extension code at any time.
   */
  focus(selector: string): void;
  /**
   * Announce a message to assistive technology via an aria-live region
   * within the editor shell root.
   *
   * Creates a `.sr-only` container with `aria-live` and `aria-atomic`
   * inside the shell root on first call.  Subsequent calls update the
   * text content so screen readers re-announce.  If no shell root is
   * mounted the message is logged to the console as a fallback.
   *
   * @param message     The text to announce.
   * @param politeness  `'polite'` (default) or `'assertive'`.
   */
  announce(message: string, politeness?: 'polite' | 'assertive'): void;
}

// ---------------------------------------------------------------------------
// Chrome events
// ---------------------------------------------------------------------------

export type ChromeEvent =
  | 'toast'
  | 'progress'
  | 'save'
  | 'renderStatus';

export interface ChromeToastPayload {
  message: string;
  severity: DiagnosticSeverity;
}

export interface ChromeProgressPayload {
  percent: number;
  label?: string;
}

export interface ChromeSavePayload {
  status: 'started' | 'completed' | 'failed';
  error?: string;
}

export interface ChromeRenderStatusPayload {
  status: 'idle' | 'rendering' | 'completed' | 'failed';
  error?: string;
}

export type ChromeEventPayload<E extends ChromeEvent> =
  E extends 'toast' ? ChromeToastPayload :
  E extends 'progress' ? ChromeProgressPayload :
  E extends 'save' ? ChromeSavePayload :
  E extends 'renderStatus' ? ChromeRenderStatusPayload :
  never;
