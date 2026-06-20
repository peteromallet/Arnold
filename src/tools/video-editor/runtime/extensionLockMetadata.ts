/**
 * Extension lock metadata (M14, T17).
 *
 * Manages project-level extension requirements/lock metadata when installed
 * packs are enabled. The lock captures:
 *   - Extension ID
 *   - Version or range
 *   - Referenced contribution IDs (from manifest contributions)
 *   - Integrity hash
 *
 * Keeps patch-backed extension-owned project data separate: the lock only
 * records the project's contract with installed extensions, not any data
 * the extension writes to the project (settings values, project configuration,
 * etc. — these live in their own storage).
 */

import type { ExtensionManifest, ExtensionContribution } from '@reigh/editor-sdk';
import type {
  ExtensionPackRecord,
  ExtensionStateRepository,
  ExtensionLockEntry,
  ExtensionLock,
} from '@/tools/video-editor/runtime/extensionStateRepository';

// ---------------------------------------------------------------------------
// Contribution ID extraction
// ---------------------------------------------------------------------------

/**
 * Extract all contribution IDs from a manifest, sorted and deduplicated.
 *
 * Contribution IDs are used in the lock to track which extension-provided
 * capabilities the project depends on. This is metadata about the project
 * contract, not extension-owned state.
 */
export function extractContributionRefs(
  manifest: ExtensionManifest,
): readonly string[] {
  const contributions: readonly ExtensionContribution[] =
    (manifest as any).contributions ?? [];

  const ids = new Set<string>();
  for (const contribution of contributions) {
    if (contribution.id && typeof contribution.id === 'string') {
      ids.add(contribution.id);
    }
  }

  // Sort for determinism
  return Object.freeze([...ids].sort());
}

// ---------------------------------------------------------------------------
// Version range computation
// ---------------------------------------------------------------------------

/**
 * Compute a lock version range from an installed version.
 *
 * Defaults to the exact installed version. When the pack record includes
 * a versionRange or the manifest declares one, that takes precedence.
 *
 * Returns the exact version as the lock range by default — this ensures
 * project reproducibility unless a range is explicitly specified.
 */
export function getLockVersionRange(
  packRecord: ExtensionPackRecord,
  manifest: ExtensionManifest,
): string {
  // Manifest-level range takes highest precedence (if declared)
  const manifestRange = (manifest as any).lockVersionRange as string | undefined;
  if (manifestRange && typeof manifestRange === 'string' && manifestRange.trim()) {
    return manifestRange.trim();
  }

  // Fall back to exact installed version
  return packRecord.version;
}

// ---------------------------------------------------------------------------
// Lock entry builder
// ---------------------------------------------------------------------------

/**
 * Build a full ExtensionLockEntry from a pack record and manifest.
 *
 * The lock entry is project metadata — it captures what the project requires
 * from this extension. It does NOT include extension settings values or
 * any extension-owned project data.
 */
export function buildLockEntry(
  packRecord: ExtensionPackRecord,
  manifest: ExtensionManifest,
): ExtensionLockEntry {
  const extensionId = packRecord.extensionId;
  const version = packRecord.version;
  const versionRange = getLockVersionRange(packRecord, manifest);
  const contributionRefs = extractContributionRefs(manifest);
  const integrity = packRecord.integrity;
  const now = new Date().toISOString();

  return Object.freeze({
    extensionId,
    version,
    versionRange,
    contributionRefs,
    integrity,
    lockedAt: now,
    updatedAt: now,
  });
}

/**
 * Build a lock entry from pack record only (manifest extracted from the record).
 */
export function buildLockEntryFromPackRecord(
  packRecord: ExtensionPackRecord,
): ExtensionLockEntry {
  return buildLockEntry(packRecord, packRecord.manifestSnapshot);
}

// ---------------------------------------------------------------------------
// Lock sync integration
// ---------------------------------------------------------------------------

/**
 * Synchronize project lock metadata with a set of enabled installed packs.
 *
 * For each installed pack that successfully loaded, this updates (upserts)
 * a lock entry in the repository. The lock is kept separate from
 * extension-owned data — only the project's extension requirements are
 * stored.
 *
 * ## What goes in the lock:
 * - Extension ID
 * - Version and version range
 * - Contribution IDs (which capabilities the project uses)
 * - Integrity hash (for secure reproducibility)
 *
 * ## What stays OUT of the lock:
 * - Extension settings values (in ExtensionSettingsSnapshot)
 * - Extension-owned project data patches
 * - Lifecycle events (in append-only event log)
 * - Bundle content (in IndexedDB per SD2)
 *
 * @param repository - The extension state repository
 * @param enabledInstalledPacks - Pack records for enabled installed extensions
 * @returns The updated lock after synchronization
 */
export async function syncEnabledPackLockEntries(
  repository: ExtensionStateRepository,
  enabledInstalledPacks: readonly ExtensionPackRecord[],
): Promise<ExtensionLock> {
  if (repository.isDisposed) {
    throw new Error('Repository is disposed — cannot sync lock metadata.');
  }

  for (const packRecord of enabledInstalledPacks) {
    const entry = buildLockEntryFromPackRecord(packRecord);
    await repository.putLockEntry(entry);
  }

  return repository.getLock();
}

/**
 * Remove a lock entry for an extension being uninstalled.
 *
 * This keeps the lock clean when extensions are removed from the project.
 */
export async function removeLockEntry(
  repository: ExtensionStateRepository,
  extensionId: string,
): Promise<void> {
  if (repository.isDisposed) return;
  await repository.deleteLockEntry(extensionId);
}

/**
 * Fetch the current project lock for inspection/display.
 */
export async function getProjectLock(
  repository: ExtensionStateRepository,
): Promise<ExtensionLock> {
  return repository.getLock();
}
