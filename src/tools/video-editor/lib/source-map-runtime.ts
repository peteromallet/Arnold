/**
 * SourceMapRuntime — provider-scoped source-map entry lifecycle manager.
 *
 * Manages SourceMapEntry CRUD via project-data.write/delete operations,
 * with bidirectional lookup (by target, by source URI) and stale marking
 * after source edits.
 *
 * Entries are stored in extension project-data under the key pattern
 * `__sm__:<entryId>` so they are replayable, rollback-safe, and
 * visible in TimelineSnapshot.app.
 *
 * Stale marking is durable: `markStale` and `markStaleForTarget` write
 * updated entries back to project-data so the stale flag survives
 * checkpoint/rollback and replay.
 *
 * @publicContract — implements the SourceMapRuntime interface from the SDK.
 */

import type {
  SourceMapRuntime,
  SourceMapEntry,
  TimelineOps,
  TimelineReader,
  TimelinePatch,
  TimelineDiffGranularity,
} from '@/sdk/index';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Key prefix for source-map entries in extension project-data. */
const SM_KEY_PREFIX = '__sm__:';

/** Build the project-data key for a source-map entry. */
function smKey(entryId: string): string {
  return `${SM_KEY_PREFIX}${entryId}`;
}

/** Generate a unique source-map entry ID. */
let nextSmId = 0;
function generateSmId(): string {
  nextSmId += 1;
  return `sme-${nextSmId}-${Date.now().toString(36)}`;
}

/** Shallow-clone a SourceMapEntry. */
function cloneEntry(e: SourceMapEntry): SourceMapEntry {
  return {
    ...e,
    meta: e.meta ? { ...e.meta } : undefined,
  };
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export interface CreateSourceMapRuntimeOptions {
  /** Stable TimelineOps adapter for writing project-data. */
  timelineOps: TimelineOps;

  /** Stable TimelineReader for reading current project-data. */
  reader: TimelineReader;
}

/**
 * Create a provider-scoped SourceMapRuntime.
 *
 * ## Storage model
 *
 * Each SourceMapEntry is stored as a project-data value under the key
 * `__sm__:<entryId>` in the creating extension's namespace.  The entries
 * are extracted from `reader.snapshot().app[extensionId]` at read time
 * and written back via `project-data.write` / `project-data.delete` on
 * mutation.
 *
 * ## Stale marking
 *
 * When a source file is edited, the owning extension (or host tooling)
 * calls `markStale(extensionId, sourceUri)` to set `stale: true` on
 * every entry that references that URI.  The stale flag is persisted
 * via project-data.write so it survives rollback/replay.
 *
 * ## Replay / rollback
 *
 * Because entries are stored via project-data.write/delete they
 * participate in checkpoint/rollback and replay like any other
 * extension project data.
 */
export function createSourceMapRuntime(
  options: CreateSourceMapRuntimeOptions,
): SourceMapRuntime {
  const { timelineOps, reader } = options;

  // ── Internal helpers ──────────────────────────────────────────────────

  /** Get the app data for a specific extension from the current snapshot. */
  function getExtensionApp(extensionId: string): Record<string, unknown> {
    const app = reader.snapshot().app;
    const extData = app[extensionId];
    if (!extData || typeof extData !== 'object' || Array.isArray(extData)) {
      return {};
    }
    return extData as Record<string, unknown>;
  }

  /** Parse a single SourceMapEntry from a raw project-data value. */
  function parseEntry(raw: unknown): SourceMapEntry | null {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
    const r = raw as Record<string, unknown>;
    if (typeof r.id !== 'string') return null;
    if (typeof r.source !== 'string') return null;
    if (typeof r.targetId !== 'string') return null;
    return {
      id: r.id,
      source: r.source,
      targetId: r.targetId,
      targetGranularity: (r.targetGranularity as TimelineDiffGranularity) ?? 'clip',
      sourceUri: typeof r.sourceUri === 'string' ? r.sourceUri : '',
      sourceStartLine: typeof r.sourceStartLine === 'number' ? r.sourceStartLine : 0,
      sourceStartColumn: typeof r.sourceStartColumn === 'number' ? r.sourceStartColumn : 0,
      sourceEndLine: typeof r.sourceEndLine === 'number' ? r.sourceEndLine : 0,
      sourceEndColumn: typeof r.sourceEndColumn === 'number' ? r.sourceEndColumn : 0,
      stale: r.stale === true,
      ...(r.meta !== undefined && typeof r.meta === 'object' && !Array.isArray(r.meta)
        ? { meta: r.meta as Record<string, unknown> }
        : {}),
    };
  }

  /** Serialize a SourceMapEntry to a plain object for project-data storage. */
  function serializeEntry(entry: SourceMapEntry): Record<string, unknown> {
    return {
      id: entry.id,
      source: entry.source,
      targetId: entry.targetId,
      targetGranularity: entry.targetGranularity,
      sourceUri: entry.sourceUri,
      sourceStartLine: entry.sourceStartLine,
      sourceStartColumn: entry.sourceStartColumn,
      sourceEndLine: entry.sourceEndLine,
      sourceEndColumn: entry.sourceEndColumn,
      stale: entry.stale,
      ...(entry.meta !== undefined ? { meta: entry.meta } : {}),
    };
  }

  /** Patch helper: apply a project-data.write operation via TimelineOps. */
  function writeProjectData(
    extensionId: string,
    key: string,
    value: unknown,
  ): void {
    const patch: TimelinePatch = {
      version: reader.snapshot().baseVersion,
      operations: [
        {
          op: 'project-data.write',
          target: extensionId,
          payload: {
            key,
            value,
            mode: 'replace',
          },
        },
      ],
    };
    timelineOps.apply(patch);
  }

  /** Patch helper: apply a project-data.delete operation via TimelineOps. */
  function deleteProjectData(
    extensionId: string,
    key: string,
  ): void {
    const patch: TimelinePatch = {
      version: reader.snapshot().baseVersion,
      operations: [
        {
          op: 'project-data.delete',
          target: extensionId,
          payload: {
            key,
          },
        },
      ],
    };
    timelineOps.apply(patch);
  }

  // ── Public API ────────────────────────────────────────────────────────

  return {
    create(
      extensionId: string,
      targetId: string,
      targetGranularity: TimelineDiffGranularity,
      sourceUri: string,
      sourceStartLine: number,
      sourceStartColumn: number,
      sourceEndLine: number,
      sourceEndColumn: number,
      meta?: Record<string, unknown>,
    ): SourceMapEntry {
      const id = generateSmId();
      const entry: SourceMapEntry = {
        id,
        source: extensionId,
        targetId,
        targetGranularity,
        sourceUri,
        sourceStartLine,
        sourceStartColumn,
        sourceEndLine,
        sourceEndColumn,
        stale: false,
        ...(meta !== undefined ? { meta } : {}),
      };

      writeProjectData(extensionId, smKey(id), serializeEntry(entry));
      return entry;
    },

    get(extensionId: string, entryId: string): SourceMapEntry | undefined {
      const extApp = getExtensionApp(extensionId);
      const raw = extApp[smKey(entryId)];
      const entry = parseEntry(raw);
      return entry ?? undefined;
    },

    getForTarget(extensionId: string, targetId: string): SourceMapEntry[] {
      const extApp = getExtensionApp(extensionId);
      const results: SourceMapEntry[] = [];
      for (const [key, raw] of Object.entries(extApp)) {
        if (!key.startsWith(SM_KEY_PREFIX)) continue;
        const entry = parseEntry(raw);
        if (entry && entry.targetId === targetId) {
          results.push(entry);
        }
      }
      return results;
    },

    getForSource(extensionId: string, sourceUri: string): SourceMapEntry[] {
      const extApp = getExtensionApp(extensionId);
      const results: SourceMapEntry[] = [];
      for (const [key, raw] of Object.entries(extApp)) {
        if (!key.startsWith(SM_KEY_PREFIX)) continue;
        const entry = parseEntry(raw);
        if (entry && entry.sourceUri === sourceUri) {
          results.push(entry);
        }
      }
      return results;
    },

    markStale(extensionId: string, sourceUri: string): SourceMapEntry[] {
      const extApp = getExtensionApp(extensionId);
      const updated: SourceMapEntry[] = [];

      for (const [key, raw] of Object.entries(extApp)) {
        if (!key.startsWith(SM_KEY_PREFIX)) continue;
        const entry = parseEntry(raw);
        if (!entry || entry.sourceUri !== sourceUri) continue;
        if (entry.stale) {
          updated.push(entry);
          continue; // already stale
        }

        const staleEntry = cloneEntry(entry);
        staleEntry.stale = true;
        writeProjectData(extensionId, key, serializeEntry(staleEntry));
        updated.push(staleEntry);
      }

      return updated;
    },

    markStaleForTarget(extensionId: string, targetId: string): SourceMapEntry[] {
      const extApp = getExtensionApp(extensionId);
      const updated: SourceMapEntry[] = [];

      for (const [key, raw] of Object.entries(extApp)) {
        if (!key.startsWith(SM_KEY_PREFIX)) continue;
        const entry = parseEntry(raw);
        if (!entry || entry.targetId !== targetId) continue;
        if (entry.stale) {
          updated.push(entry);
          continue; // already stale
        }

        const staleEntry = cloneEntry(entry);
        staleEntry.stale = true;
        writeProjectData(extensionId, key, serializeEntry(staleEntry));
        updated.push(staleEntry);
      }

      return updated;
    },

    delete(extensionId: string, entryId: string): boolean {
      const extApp = getExtensionApp(extensionId);
      const key = smKey(entryId);
      if (!(key in extApp)) return false;

      deleteProjectData(extensionId, key);
      return true;
    },

    list(extensionId: string): SourceMapEntry[] {
      const extApp = getExtensionApp(extensionId);
      const results: SourceMapEntry[] = [];
      for (const [key, raw] of Object.entries(extApp)) {
        if (!key.startsWith(SM_KEY_PREFIX)) continue;
        const entry = parseEntry(raw);
        if (entry) {
          results.push(entry);
        }
      }
      return results;
    },
  };
}
