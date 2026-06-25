/**
 * Diagnostics contracts and helpers.
 *
 * Provides the canonical diagnostic types, interfaces, and factory
 * consumed throughout the extension lifecycle for structured error,
 * warning, and info reporting. All contracts are data-only descriptions;
 * host-owned behaviour (e.g. routing diagnostics to a UI sink) lives
 * behind the public interfaces.
 *
 * @publicContract
 */

import type { DisposeHandle } from './dispose';
import type { ShaderMaterializerRequirementScope } from '@/sdk/video/rendering/capabilities';

// ---------------------------------------------------------------------------
// Core diagnostic types
// ---------------------------------------------------------------------------

export type DiagnosticSeverity = 'error' | 'warning' | 'info';

/**
 * Diagnostic provenance source.
 *
 * - `extension` — authored by a trusted local extension (the only source
 *   extensions themselves can produce).  The SDK pins this value for
 *   extension-reported diagnostics.
 * - `render` — emitted by the host render pipeline.
 * - `provider` — emitted by a host provider (editor runtime, etc.).
 *
 * Extensions MUST NOT set host-owned sources.
 */
export type DiagnosticSource = 'extension' | 'render' | 'provider';

/** The only diagnostic source extensions are permitted to use. */
export const DIAGNOSTIC_SOURCE_EXTENSION: DiagnosticSource = 'extension';

export interface ExtensionDiagnostic {
  severity: DiagnosticSeverity;
  code: string;
  message: string;
  extensionId?: string;
  contributionId?: string;
  /** The earliest milestone that is expected to activate this feature. */
  milestone?: string;
  /**
   * Diagnostic provenance source.
   * Extension-authored diagnostics always use {@link DIAGNOSTIC_SOURCE_EXTENSION}.
   */
  source?: DiagnosticSource;
  /** Additional structured detail (clip reference, effect ID, etc.). */
  detail?: Record<string, unknown>;
}

export interface DiagnosticSourceRange {
  startLine: number;
  startCol: number;
  endLine: number;
  endCol: number;
}

export interface Diagnostic extends ExtensionDiagnostic {
  id: string;
  sourceRange?: DiagnosticSourceRange;
  relatedRanges?: readonly DiagnosticSourceRange[];
}

// ---------------------------------------------------------------------------
// Diagnostic collection
// ---------------------------------------------------------------------------

export interface DiagnosticCollection {
  readonly snapshot: readonly Diagnostic[];
  publish(diagnostic: Diagnostic): void;
  remove(predicate: (diagnostic: Diagnostic) => boolean): void;
  /** Remove all diagnostics belonging to the given extension ID. */
  removeByExtensionId(extensionId: string): void;
  clear(): void;
  subscribe(listener: () => void): DisposeHandle;
  getSnapshot(): readonly Diagnostic[];
}

/** Default per-extension diagnostic capacity before oldest-first eviction. */
export const DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY = 100;

function freezeDiagnostic(diagnostic: Diagnostic): Diagnostic {
  return Object.freeze({
    ...diagnostic,
    ...(diagnostic.sourceRange ? { sourceRange: Object.freeze({ ...diagnostic.sourceRange }) } : {}),
    ...(diagnostic.relatedRanges
      ? { relatedRanges: Object.freeze(diagnostic.relatedRanges.map((range) => Object.freeze({ ...range }))) }
      : {}),
    ...(diagnostic.detail ? { detail: Object.freeze({ ...diagnostic.detail }) } : {}),
  });
}

export interface CreateDiagnosticCollectionOptions {
  /**
   * Maximum number of diagnostics allowed per extension ID.
   * When publishing a new diagnostic (not replacing an existing one by ID)
   * would exceed this limit, the oldest diagnostic for that extension is
   * evicted before the new one is added.
   * @default {@link DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY}
   */
  perExtensionCapacity?: number;
}

export function createDiagnosticCollection(
  initialDiagnostics: readonly Diagnostic[] = [],
  options: CreateDiagnosticCollectionOptions = {},
): DiagnosticCollection {
  const capacity = options.perExtensionCapacity ?? DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY;
  const diagnostics: Diagnostic[] = initialDiagnostics.map(freezeDiagnostic);
  const listeners = new Set<() => void>();
  let snapshot: readonly Diagnostic[] = Object.freeze([...diagnostics]);

  const publishSnapshot = () => {
    snapshot = Object.freeze([...diagnostics]);
    for (const listener of listeners) {
      listener();
    }
  };

  const evictOldestForExtension = (extensionId: string): void => {
    // Find the oldest (lowest index) diagnostic for this extension
    for (let i = 0; i < diagnostics.length; i += 1) {
      if (diagnostics[i].extensionId === extensionId) {
        diagnostics.splice(i, 1);
        return; // only evict one — the oldest
      }
    }
  };

  return {
    get snapshot(): readonly Diagnostic[] {
      return snapshot;
    },
    publish(diagnostic: Diagnostic): void {
      const frozen = freezeDiagnostic(diagnostic);
      const existingIndex = diagnostics.findIndex((item) => item.id === frozen.id);
      if (existingIndex >= 0) {
        // Replace in-place — does NOT count toward capacity
        diagnostics[existingIndex] = frozen;
      } else {
        // New diagnostic: enforce per-extension capacity
        const extId = frozen.extensionId;
        if (extId) {
          const extCount = diagnostics.reduce(
            (count, d) => count + (d.extensionId === extId ? 1 : 0),
            0,
          );
          if (extCount >= capacity) {
            evictOldestForExtension(extId);
          }
        }
        diagnostics.push(frozen);
      }
      publishSnapshot();
    },
    remove(predicate: (diagnostic: Diagnostic) => boolean): void {
      let changed = false;
      for (let index = diagnostics.length - 1; index >= 0; index -= 1) {
        if (predicate(diagnostics[index])) {
          diagnostics.splice(index, 1);
          changed = true;
        }
      }
      if (changed) {
        publishSnapshot();
      }
    },
    removeByExtensionId(extensionId: string): void {
      let changed = false;
      for (let index = diagnostics.length - 1; index >= 0; index -= 1) {
        if (diagnostics[index].extensionId === extensionId) {
          diagnostics.splice(index, 1);
          changed = true;
        }
      }
      if (changed) {
        publishSnapshot();
      }
    },
    clear(): void {
      if (diagnostics.length === 0) return;
      diagnostics.length = 0;
      publishSnapshot();
    },
    subscribe(listener: () => void): DisposeHandle {
      listeners.add(listener);
      return {
        dispose(): void {
          listeners.delete(listener);
        },
      };
    },
    getSnapshot(): readonly Diagnostic[] {
      return snapshot;
    },
  };
}

// ---------------------------------------------------------------------------
// Export-scoped diagnostic
// ---------------------------------------------------------------------------

/**
 * An export-scoped diagnostic produced by the pre-render export guard.
 * Carries the same shape as {@link ExtensionDiagnostic} but uses
 * export-prefixed diagnostic codes (e.g. `export/unknown-clip-type`)
 * and includes timeline-specific detail (clip ID, effect name, etc.).
 */
export interface ExportDiagnostic extends ExtensionDiagnostic {
  /** The diagnostic code is always an export-prefixed string. */
  code: `export/${string}`;
  /** Timeline-scoped detail such as clip ID, effect/transition name. */
  detail?: Record<string, unknown> & {
    clipId?: string;
    clipType?: string;
    effectType?: string;
    transitionType?: string;
    shaderId?: string;
    shaderScope?: ShaderMaterializerRequirementScope;
  };
}
