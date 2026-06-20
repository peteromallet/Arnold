/**
 * Extension reference report (M14, T23).
 *
 * Scans the current project for extension-owned references before uninstall
 * and produces a structured report with counts, expandable reference lists,
 * and diagnostics/export blockers when references remain after uninstall.
 *
 * Timeline data that references extension contributions is preserved on
 * uninstall (not deleted). When references remain, the report surfaces them
 * as diagnostics so the user can manually resolve or export before removing
 * the extension.
 */

import type { ExtensionDiagnostic } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Reference types
// ---------------------------------------------------------------------------

/** Kinds of references an extension may have in the project. */
export type ReferenceKind =
  | 'contribution'
  | 'effect'
  | 'transition'
  | 'shader'
  | 'clip-type'
  | 'agent-tool'
  | 'live-data-source'
  | 'settings'
  | 'lock-entry'
  | 'other';

/** A single reference to an extension-owned item in the project. */
export interface ExtensionReference {
  /** The kind of reference. */
  readonly kind: ReferenceKind;
  /** The ID of the referenced item (contribution ID, effect ID, etc.). */
  readonly referenceId: string;
  /** Human-readable label for the referenced item. */
  readonly label: string;
  /** Where in the project the reference occurs (e.g., timeline name, clip name). */
  readonly location: string;
  /** The extension ID that owns the referenced item. */
  readonly ownerExtensionId: string;
}

// ---------------------------------------------------------------------------
// Scan input
// ---------------------------------------------------------------------------

/**
 * Project data provided to the reference scanner.
 *
 * Consumers pass whatever project data is available.  The scanner is
 * designed to work with partial data — it reports what it can find
 * and marks the report as incomplete when project data is unavailable.
 */
export interface ProjectReferenceScan {
  /**
   * Contribution IDs used in the project, keyed by contribution kind.
   *
   * Each entry maps a contribution ID to the location(s) where it is used.
   * Example: { effects: { 'myEffect': ['Timeline A > Clip 3'] } }
   */
  readonly usedContributions?: Record<string, Record<string, readonly string[]>>;

  /**
   * Extension-owned settings values referenced by project configuration.
   *
   * Each entry maps an extension ID to the setting keys that are referenced
   * by project-level configuration.
   */
  readonly settingsReferences?: Record<string, readonly string[]>;

  /**
   * Lock entries active in the project.
   *
   * Each entry maps an extension ID to its contribution refs.
   */
  readonly lockEntries?: Record<string, readonly string[]>;

  /**
   * Whether the scan data is complete (true) or partial (false).
   *
   * When false, the report will note that it may be incomplete.
   */
  readonly isComplete: boolean;
}

// ---------------------------------------------------------------------------
// Report output
// ---------------------------------------------------------------------------

/** Reference report for a single extension. */
export interface ExtensionReferenceReport {
  /** The extension ID this report is for. */
  readonly extensionId: string;
  /** Total number of references found for this extension. */
  readonly totalReferenceCount: number;
  /** References grouped by kind. */
  readonly referencesByKind: Record<ReferenceKind, readonly ExtensionReference[]>;
  /** Whether any references were found. */
  readonly hasReferences: boolean;
  /** Whether the scan data was complete. */
  readonly scanIsComplete: boolean;
}

/** Aggregate reference report for all scanned extensions. */
export interface ReferenceReportResult {
  /** Per-extension reports. */
  readonly entries: readonly ExtensionReferenceReport[];
  /** Extension IDs with remaining references. */
  readonly extensionIdsWithReferences: readonly string[];
  /** Diagnostics generated for extensions with remaining references. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /** Total reference count across all extensions. */
  readonly totalReferenceCount: number;
  /** Whether the scan data was complete. */
  readonly scanIsComplete: boolean;
}

// ---------------------------------------------------------------------------
// Uninstall precondition result
// ---------------------------------------------------------------------------

/** Result of checking uninstall preconditions for an extension. */
export interface UninstallPreconditionResult {
  /** The extension ID being checked. */
  readonly extensionId: string;
  /** Whether the uninstall can proceed (no blocking references). */
  readonly canProceed: boolean;
  /** Reference report for this extension. */
  readonly referenceReport: ExtensionReferenceReport;
  /** Blocking diagnostics (export blockers). */
  readonly blockingDiagnostics: readonly ExtensionDiagnostic[];
  /** Warning diagnostics (informational, non-blocking). */
  readonly warningDiagnostics: readonly ExtensionDiagnostic[];
  /** Whether references will be orphaned by this uninstall. */
  readonly willOrphanReferences: boolean;
  /** Human-readable summary of the reference situation. */
  readonly summary: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map contribution kind strings to ReferenceKind. */
function mapContributionKindToReferenceKind(
  contributionKind: string,
): ReferenceKind {
  const map: Record<string, ReferenceKind> = {
    effect: 'effect',
    effects: 'effect',
    transition: 'transition',
    transitions: 'transition',
    shader: 'shader',
    shaders: 'shader',
    clipType: 'clip-type',
    clipTypes: 'clip-type',
    'clip-type': 'clip-type',
    agentTool: 'agent-tool',
    agentTools: 'agent-tool',
    'agent-tool': 'agent-tool',
    liveDataSource: 'live-data-source',
    liveDataSources: 'live-data-source',
    'live-data-source': 'live-data-source',
    command: 'contribution',
    commands: 'contribution',
  };
  return map[contributionKind] ?? 'other';
}

/** Build a human-readable label for a reference. */
function buildReferenceLabel(
  kind: ReferenceKind,
  referenceId: string,
  location: string,
): string {
  const kindLabel = kind
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
  return `${kindLabel} "${referenceId}" used in ${location}`;
}

// ---------------------------------------------------------------------------
// Scanner
// ---------------------------------------------------------------------------

/**
 * Scan project data for extension-owned references.
 *
 * Produces a per-extension report with counts and expandable reference lists.
 * When project data is incomplete, marks the report accordingly.
 *
 * @param scan - Project data to scan for references
 * @param extensionIds - Specific extension IDs to scan for (empty = all)
 * @returns Aggregate reference report
 */
export function scanProjectReferences(
  scan: ProjectReferenceScan,
  extensionIds: readonly string[] = [],
): ReferenceReportResult {
  const entries: ExtensionReferenceReport[] = [];
  const diagnostics: ExtensionDiagnostic[] = [];
  const extensionIdsWithRefs: string[] = [];
  let totalRefCount = 0;

  // Track which extension IDs we've already built reports for
  const seenExtensionIds = new Set<string>();

  // Process contribution references
  if (scan.usedContributions) {
    for (const [contributionKind, contributionMap] of Object.entries(
      scan.usedContributions,
    )) {
      const refKind = mapContributionKindToReferenceKind(contributionKind);

      for (const [contributionId, locations] of Object.entries(contributionMap)) {
        // Determine owner extension from contribution ID
        // Convention: contribution IDs are extension-owned with dot-separated prefixes,
        // e.g., "com.example.ext.myEffect" → extension "com.example.ext"
        const parts = contributionId.split('.');
        // Walk backwards from full ID, trying progressively shorter prefixes
        // until we find a matching extension ID
        let ownerExtensionId = '';
        for (let i = parts.length - 1; i >= 2; i--) {
          const candidate = parts.slice(0, i).join('.');
          if (extensionIds.length === 0 || extensionIds.includes(candidate)) {
            ownerExtensionId = candidate;
            break;
          }
        }
        // Fallback: use the full contribution ID prefix minus last segment
        if (!ownerExtensionId && parts.length >= 2) {
          ownerExtensionId = parts.slice(0, -1).join('.');
        }

        if (!ownerExtensionId) continue;

        // Skip if we're filtering to specific extension IDs and this doesn't match
        if (extensionIds.length > 0 && !extensionIds.includes(ownerExtensionId)) {
          continue;
        }

        const refs: ExtensionReference[] = locations.map((location) => ({
          kind: refKind,
          referenceId: contributionId,
          label: buildReferenceLabel(refKind, contributionId, location),
          location,
          ownerExtensionId,
        }));

        // Accumulate into the report for this extension
        addToReport(
          entries,
          seenExtensionIds,
          ownerExtensionId,
          refKind,
          refs,
          scan.isComplete,
        );
        totalRefCount += refs.length;
        if (!extensionIdsWithRefs.includes(ownerExtensionId)) {
          extensionIdsWithRefs.push(ownerExtensionId);
        }
      }
    }
  }

  // Process settings references
  if (scan.settingsReferences) {
    for (const [extId, settingKeys] of Object.entries(scan.settingsReferences)) {
      if (extensionIds.length > 0 && !extensionIds.includes(extId)) continue;

      const refs: ExtensionReference[] = settingKeys.map((key) => ({
        kind: 'settings' as ReferenceKind,
        referenceId: key,
        label: `Settings key "${key}" for extension "${extId}"`,
        location: 'Project settings / configuration',
        ownerExtensionId: extId,
      }));

      addToReport(entries, seenExtensionIds, extId, 'settings', refs, scan.isComplete);
      totalRefCount += refs.length;
      if (!extensionIdsWithRefs.includes(extId)) {
        extensionIdsWithRefs.push(extId);
      }
    }
  }

  // Process lock entries
  if (scan.lockEntries) {
    for (const [extId, contributionRefs] of Object.entries(scan.lockEntries)) {
      if (extensionIds.length > 0 && !extensionIds.includes(extId)) continue;

      const refs: ExtensionReference[] = contributionRefs.map((ref) => ({
        kind: 'lock-entry' as ReferenceKind,
        referenceId: ref,
        label: `Lock entry contribution "${ref}" for extension "${extId}"`,
        location: 'Project extension lock',
        ownerExtensionId: extId,
      }));

      addToReport(entries, seenExtensionIds, extId, 'lock-entry', refs, scan.isComplete);
      totalRefCount += refs.length;
      if (!extensionIdsWithRefs.includes(extId)) {
        extensionIdsWithRefs.push(extId);
      }
    }
  }

  // Generate diagnostics for extensions with references
  for (const entry of entries) {
    if (entry.hasReferences) {
      const diag: ExtensionDiagnostic = {
        severity: 'warning',
        code: 'uninstall/orphaned-references',
        message: `Extension "${entry.extensionId}" has ${entry.totalReferenceCount} project reference(s) that will be orphaned after uninstall.`,
        extensionId: entry.extensionId,
        detail: {
          totalReferences: entry.totalReferenceCount,
          kindsWithReferences: Object.entries(entry.referencesByKind)
            .filter(([, refs]) => refs.length > 0)
            .map(([kind, refs]) => ({ kind, count: refs.length })),
        },
      };
      diagnostics.push(diag);
    }
  }

  return {
    entries: Object.freeze([...entries]),
    extensionIdsWithReferences: Object.freeze([...extensionIdsWithRefs]),
    diagnostics: Object.freeze([...diagnostics]),
    totalReferenceCount: totalRefCount,
    scanIsComplete: scan.isComplete,
  };
}

/** Helper: add references to a per-extension report entry, creating if needed. */
function addToReport(
  entries: ExtensionReferenceReport[],
  seenExtensionIds: Set<string>,
  extensionId: string,
  kind: ReferenceKind,
  refs: readonly ExtensionReference[],
  scanIsComplete: boolean,
): void {
  let entry = entries.find((e) => e.extensionId === extensionId);
  if (!entry) {
    entry = {
      extensionId,
      totalReferenceCount: 0,
      referencesByKind: {},
      hasReferences: false,
      scanIsComplete,
    };
    entries.push(entry);
    seenExtensionIds.add(extensionId);
  }

  const existing = entry.referencesByKind[kind] ?? [];
  entry.referencesByKind[kind] = Object.freeze([...existing, ...refs]);
  entry.totalReferenceCount += refs.length;
  entry.hasReferences = entry.totalReferenceCount > 0;
}

// ---------------------------------------------------------------------------
// Uninstall precondition check
// ---------------------------------------------------------------------------

/**
 * Check uninstall preconditions for a single extension.
 *
 * Scans for project references and returns whether uninstall can proceed.
 * When references exist, they become export blockers — the user must
 * manually resolve them before uninstalling.
 *
 * Timeline data is preserved (not deleted) — references remain as
 * diagnostics until manually resolved.
 *
 * @param scan - Project data to scan
 * @param extensionId - The extension being uninstalled
 * @returns Precondition result with diagnostics
 */
export function checkUninstallPreconditions(
  scan: ProjectReferenceScan,
  extensionId: string,
): UninstallPreconditionResult {
  const report = scanProjectReferences(scan, [extensionId]);
  const extReport = report.entries.find((e) => e.extensionId === extensionId) ?? {
    extensionId,
    totalReferenceCount: 0,
    referencesByKind: {},
    hasReferences: false,
    scanIsComplete: scan.isComplete,
  };

  const blockingDiagnostics: ExtensionDiagnostic[] = [];
  const warningDiagnostics: ExtensionDiagnostic[] = [];
  const willOrphanReferences = extReport.hasReferences;

  if (willOrphanReferences) {
    // References exist — produce a blocking diagnostic (export blocker)
    const kindsDetail = Object.entries(extReport.referencesByKind)
      .filter(([, refs]) => refs.length > 0)
      .map(([kind, refs]) => ({
        kind,
        count: refs.length,
        refs: refs.slice(0, 10).map((r) => ({
          referenceId: r.referenceId,
          location: r.location,
        })),
      }));

    const blockerDiag: ExtensionDiagnostic = {
      severity: 'warning',
      code: 'uninstall/references-remain',
      message: `Extension "${extensionId}" has ${extReport.totalReferenceCount} active reference(s) in the project. Uninstalling will orphan these references. Timeline data will be preserved — the references will appear as diagnostics until resolved.`,
      extensionId,
      detail: {
        totalReferences: extReport.totalReferenceCount,
        referencesByKind: kindsDetail,
        note: 'Timeline data is preserved on uninstall. References become project diagnostics.',
      },
    };
    blockingDiagnostics.push(blockerDiag);
  }

  if (!scan.isComplete) {
    const incompleteDiag: ExtensionDiagnostic = {
      severity: 'info',
      code: 'uninstall/scan-incomplete',
      message: `Reference scan for extension "${extensionId}" is incomplete. Some project data may not have been scanned.`,
      extensionId,
    };
    warningDiagnostics.push(incompleteDiag);
  }

  const summary = willOrphanReferences
    ? `${extReport.totalReferenceCount} reference(s) will be orphaned after uninstall. Timeline data is preserved.`
    : 'No project references found. Uninstall can proceed.';

  return {
    extensionId,
    canProceed: true, // Uninstall can always proceed — references become diagnostics
    referenceReport: extReport,
    blockingDiagnostics: Object.freeze([...blockingDiagnostics]),
    warningDiagnostics: Object.freeze([...warningDiagnostics]),
    willOrphanReferences,
    summary,
  };
}

// ---------------------------------------------------------------------------
// Uninstall action result
// ---------------------------------------------------------------------------

/**
 * Result of performing an uninstall action.
 */
export interface UninstallActionResult {
  /** The extension ID that was uninstalled. */
  readonly extensionId: string;
  /** Whether the uninstall completed successfully. */
  readonly success: boolean;
  /** Error message if the uninstall failed. */
  readonly error?: string;
  /** Remaining orphaned reference diagnostics after uninstall. */
  readonly orphanedReferenceDiagnostics: readonly ExtensionDiagnostic[];
  /** Lifecycle events emitted during uninstall. */
  readonly lifecycleEventIds: readonly string[];
}

/**
 * Perform the uninstall actions: remove lock entry, delete pack record,
 * delete enablement state, delete settings snapshot, delete dev overrides,
 * and preserve lifecycle events.
 *
 * This is a standalone function that can be called by the manager UI or
 * any other uninstall flow. The caller is responsible for unregistering
 * contributions from the runtime (this function only handles repository
 * cleanup).
 */
export async function performUninstallRepositoryCleanup(
  repository: {
    deleteLockEntry(extensionId: string): Promise<void>;
    deletePackRecord(extensionId: string): Promise<void>;
    deleteEnablementState(extensionId: string): Promise<void>;
    deleteSettingsSnapshot(extensionId: string): Promise<void>;
    deleteDevOverride(extensionId: string): Promise<void>;
    appendLifecycleEvent(event: {
      readonly extensionId: string;
      readonly kind: string;
      readonly message: string;
      readonly timestamp: string;
      readonly detail?: Record<string, unknown>;
    }): Promise<void>;
    isDisposed: boolean;
  },
  extensionId: string,
): Promise<{
  success: boolean;
  error?: string;
  lifecycleEventIds: readonly string[];
}> {
  if (repository.isDisposed) {
    return { success: false, error: 'Repository is disposed.', lifecycleEventIds: [] };
  }

  const lifecycleEventIds: string[] = [];

  try {
    // Delete in order: lock → pack → enablement → settings → dev overrides
    await repository.deleteLockEntry(extensionId);
    await repository.deletePackRecord(extensionId);
    await repository.deleteEnablementState(extensionId);
    await repository.deleteSettingsSnapshot(extensionId);
    await repository.deleteDevOverride(extensionId);

    // Append uninstall lifecycle event (preserved for audit)
    const eventId = `uninstall-${extensionId}-${Date.now()}`;
    await repository.appendLifecycleEvent({
      extensionId,
      kind: 'uninstall',
      message: `Extension "${extensionId}" uninstalled. Pack record, enablement state, settings, and dev overrides removed.`,
      timestamp: new Date().toISOString(),
      detail: {
        action: 'uninstall',
        cleanedUp: [
          'lockEntry',
          'packRecord',
          'enablementState',
          'settingsSnapshot',
          'devOverride',
        ],
      },
    });
    lifecycleEventIds.push(eventId);

    return { success: true, lifecycleEventIds };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      success: false,
      error: `Failed to uninstall extension "${extensionId}": ${message}`,
      lifecycleEventIds,
    };
  }
}
