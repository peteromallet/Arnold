/**
 * Extension local-to-installed migration flow (M14, T24).
 *
 * Provides a structured migration path for converting a workspace-source
 * (local) extension into an installed-bundle extension while preserving:
 *   - Extension ID (same identity)
 *   - Enablement state (transferred to repository)
 *   - Settings (transferred from localStorage to repository snapshot)
 *   - Project requirements / lock metadata (created on migration)
 *   - Timeline references (preserved because extension ID is unchanged)
 *
 * Contribution ID comparison verifies that local and installed manifests
 * resolve to the same contribution IDs. Metadata gap detection surfaces
 * diagnostics when the local source has fields that the installed pack
 * doesn't support.
 */

import type {
  ExtensionManifest,
  ExtensionDiagnostic,
  ExtensionContribution,
  ExtensionDependency,
  InstalledExtensionPackage,
  InstalledExtensionMetadata,
  IntegrityHash,
} from '@reigh/editor-sdk';
import type {
  ExtensionStateRepository,
  ExtensionPackRecord,
  ExtensionEnablementState,
  ExtensionSettingsSnapshot,
  ExtensionLifecycleEvent,
  FullExtensionState,
} from '@/tools/video-editor/runtime/extensionStateRepository';
import {
  createLifecycleEvent,
  createEnablementState,
  createSettingsSnapshot,
} from '@/tools/video-editor/runtime/extensionStateRepository';
import { extractContributionRefs } from '@/tools/video-editor/runtime/extensionLockMetadata';
import { getSettingsPrefix } from '@/sdk/extensionSettingsService';
import { getManifestSettingsSchemaVersion } from '@/sdk/extensionSettingsMigration';

// ---------------------------------------------------------------------------
// Contribution ID comparison types
// ---------------------------------------------------------------------------

/** Result of comparing contribution IDs between local and installed manifests. */
export interface ContributionIdComparison {
  /** Whether all contribution IDs in both manifests match perfectly. */
  readonly identical: boolean;
  /** Contribution IDs present in the local source but missing from the installed bundle. */
  readonly localOnly: readonly string[];
  /** Contribution IDs present in the installed bundle but missing from the local source. */
  readonly installedOnly: readonly string[];
  /** Contribution IDs present in both. */
  readonly shared: readonly string[];
  /** Total contribution count in the local source. */
  readonly localCount: number;
  /** Total contribution count in the installed bundle. */
  readonly installedCount: number;
}

// ---------------------------------------------------------------------------
// Metadata gap types
// ---------------------------------------------------------------------------

/** A metadata gap between local source and installed bundle manifests. */
export interface MetadataGap {
  /** The field or area where the gap exists. */
  readonly field: string;
  /** Which side has the data that the other is missing. */
  readonly presentIn: 'local-only' | 'installed-only';
  /** Human-readable description of the gap. */
  readonly description: string;
  /** Whether this gap blocks migration. */
  readonly blocking: boolean;
  /** Severity of the diagnostic produced for this gap. */
  readonly severity: 'error' | 'warning' | 'info';
}

/** Result of detecting metadata gaps between local and installed manifests. */
export interface MetadataGapResult {
  /** Whether any blocking gaps exist. */
  readonly hasBlockingGaps: boolean;
  /** All detected gaps. */
  readonly gaps: readonly MetadataGap[];
  /** Blocking gaps (prevent migration). */
  readonly blockingGaps: readonly MetadataGap[];
  /** Non-blocking gaps (warnings/info). */
  readonly nonBlockingGaps: readonly MetadataGap[];
  /** Diagnostics produced for all gaps. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Migration types
// ---------------------------------------------------------------------------

/** Input to a local-to-installed migration operation. */
export interface LocalInstalledMigrationInput {
  /** The workspace-source (local) extension manifest. */
  readonly localManifest: ExtensionManifest;
  /** The installed extension package being migrated to. */
  readonly installedPack: InstalledExtensionPackage;
  /** The extension state repository for persistence. */
  readonly repository: ExtensionStateRepository;
  /**
   * Current settings values from the local extension's localStorage.
   * Pass an empty record if local settings are unavailable or the extension
   * hasn't been activated yet.
   */
  readonly localSettings: Record<string, unknown>;
  /** Bundle content reference key (IndexedDB key for the installed bundle bytes). */
  readonly bundleContentRef: string;
}

/** Result of executing a local-to-installed migration. */
export interface MigrationExecuteResult {
  /** Whether the migration completed successfully. */
  readonly success: boolean;
  /** The extension ID that was migrated. */
  readonly extensionId: string;
  /** Contribution ID comparison result. */
  readonly contributionComparison: ContributionIdComparison;
  /** Metadata gap detection result. */
  readonly metadataGaps: MetadataGapResult;
  /** Whether the migration was blocked (by metadata gaps or other issues). */
  readonly blocked: boolean;
  /** Blocking diagnostics that prevented migration. */
  readonly blockingDiagnostics: readonly ExtensionDiagnostic[];
  /** Warning/info diagnostics (non-blocking). */
  readonly warningDiagnostics: readonly ExtensionDiagnostic[];
  /** The pack record created (null if migration was blocked). */
  readonly packRecord: ExtensionPackRecord | null;
  /** Whether settings were successfully transferred. */
  readonly settingsTransferred: boolean;
  /** Transferred settings count (keys that were moved to repository). */
  readonly settingsKeyCount: number;
  /** Whether project lock metadata was created. */
  readonly lockEntryCreated: boolean;
  /** Lifecycle events emitted during the migration. */
  readonly lifecycleEvents: readonly ExtensionLifecycleEvent[];
  /** Human-readable summary of the migration. */
  readonly summary: string;
}

// ---------------------------------------------------------------------------
// Contribution ID comparison
// ---------------------------------------------------------------------------

/**
 * Extract all contribution IDs from a manifest, sorted and deduplicated.
 *
 * This extracts IDs from the `contributions` array declared in the manifest.
 */
function extractAllContributionIds(manifest: ExtensionManifest): readonly string[] {
  const contributions: readonly ExtensionContribution[] =
    (manifest as any).contributions ?? [];
  const ids = new Set<string>();
  for (const contribution of contributions) {
    if (contribution.id && typeof contribution.id === 'string') {
      ids.add(contribution.id);
    }
  }
  return Object.freeze([...ids].sort());
}

/**
 * Compare contribution IDs between a local (workspace-source) manifest
 * and an installed-bundle manifest.
 *
 * Verifies that both manifests declare the same contribution IDs. IDs
 * that differ are surfaced for diagnostics.
 */
export function compareContributionIds(
  localManifest: ExtensionManifest,
  installedManifest: ExtensionManifest,
): ContributionIdComparison {
  const localIds = extractAllContributionIds(localManifest);
  const installedIds = extractAllContributionIds(installedManifest);

  const localSet = new Set(localIds);
  const installedSet = new Set(installedIds);

  const shared: string[] = [];
  const localOnly: string[] = [];
  const installedOnly: string[] = [];

  for (const id of localIds) {
    if (installedSet.has(id)) {
      shared.push(id);
    } else {
      localOnly.push(id);
    }
  }
  for (const id of installedIds) {
    if (!localSet.has(id)) {
      installedOnly.push(id);
    }
  }

  const identical = localOnly.length === 0 && installedOnly.length === 0;

  return Object.freeze({
    identical,
    localOnly: Object.freeze([...localOnly]),
    installedOnly: Object.freeze([...installedOnly]),
    shared: Object.freeze([...shared]),
    localCount: localIds.length,
    installedCount: installedIds.length,
  });
}

// ---------------------------------------------------------------------------
// Metadata gap detection
// ---------------------------------------------------------------------------

/**
 * Detect unsupported metadata gaps between a local source manifest and
 * an installed bundle manifest.
 *
 * Gaps include:
 *   - Fields present in local source but missing from installed.
 *   - Fields present in installed but missing from local source.
 *   - API version differences.
 *   - Dependency differences.
 *   - Contribution type differences.
 *   - Settings schema version differences.
 *   - Migration declarations present in local but not installed.
 *
 * Some gaps are blocking (e.g., contribution ID mismatch), others are
 * informational (e.g., different descriptions).
 */
export function detectMetadataGaps(
  localManifest: ExtensionManifest,
  installedManifest: ExtensionManifest,
): MetadataGapResult {
  const gaps: MetadataGap[] = [];
  const extensionId = localManifest.id as string;

  // ---- Identity checks ----

  // Extension ID must match (should be enforced by caller, but verify here)
  if ((localManifest.id as string) !== (installedManifest.id as string)) {
    gaps.push({
      field: 'id',
      presentIn: 'local-only',
      description: `Extension ID mismatch: local "${localManifest.id as string}" vs installed "${installedManifest.id as string}". Migration requires the same extension ID.`,
      blocking: true,
      severity: 'error',
    });
    // If IDs don't match, skip further checks — they're meaningless
    return buildMetadataGapResult(gaps, extensionId);
  }

  // ---- Version check ----
  if (localManifest.version !== installedManifest.version) {
    gaps.push({
      field: 'version',
      presentIn: 'local-only',
      description: `Version difference: local "${localManifest.version}" vs installed "${installedManifest.version}". This is expected during migration — the installed version will take effect.`,
      blocking: false,
      severity: 'info',
    });
  }

  // ---- API version check ----
  const localApiVersion = localManifest.apiVersion;
  const installedApiVersion = installedManifest.apiVersion;
  if (localApiVersion !== undefined && installedApiVersion === undefined) {
    gaps.push({
      field: 'apiVersion',
      presentIn: 'local-only',
      description: `Local source declares apiVersion ${localApiVersion} but installed bundle does not declare apiVersion.`,
      blocking: false,
      severity: 'warning',
    });
  } else if (installedApiVersion !== undefined && localApiVersion === undefined) {
    gaps.push({
      field: 'apiVersion',
      presentIn: 'installed-only',
      description: `Installed bundle declares apiVersion ${installedApiVersion} but local source does not. The installed value will be used.`,
      blocking: false,
      severity: 'info',
    });
  } else if (
    localApiVersion !== undefined &&
    installedApiVersion !== undefined &&
    localApiVersion !== installedApiVersion
  ) {
    gaps.push({
      field: 'apiVersion',
      presentIn: 'local-only',
      description: `API version difference: local ${localApiVersion} vs installed ${installedApiVersion}. The installed value (${installedApiVersion}) will be used.`,
      blocking: false,
      severity: 'info',
    });
  }

  // ---- Contribution count check ----
  const localContribs: readonly ExtensionContribution[] =
    (localManifest as any).contributions ?? [];
  const installedContribs: readonly ExtensionContribution[] =
    (installedManifest as any).contributions ?? [];

  if (localContribs.length !== installedContribs.length) {
    gaps.push({
      field: 'contributions',
      presentIn: 'local-only',
      description: `Contribution count difference: local has ${localContribs.length}, installed has ${installedContribs.length}. Contribution ID comparison will provide detailed diagnostics.`,
      blocking: false,
      severity: 'warning',
    });
  }

  // ---- Publisher check ----
  if ((localManifest.publisher ?? '') !== (installedManifest.publisher ?? '')) {
    const side = (installedManifest.publisher && !localManifest.publisher)
      ? 'installed-only'
      : 'local-only';
    gaps.push({
      field: 'publisher',
      presentIn: side as 'local-only' | 'installed-only',
      description: `Publisher difference: local "${localManifest.publisher ?? '(none)'}" vs installed "${installedManifest.publisher ?? '(none)'}". The installed publisher will be used.`,
      blocking: false,
      severity: 'info',
    });
  }

  // ---- License check ----
  if ((localManifest.license ?? '') !== (installedManifest.license ?? '')) {
    const side = (installedManifest.license && !localManifest.license)
      ? 'installed-only'
      : 'local-only';
    gaps.push({
      field: 'license',
      presentIn: side as 'local-only' | 'installed-only',
      description: `License difference: local "${localManifest.license ?? '(none)'}" vs installed "${installedManifest.license ?? '(none)'}". The installed license will be used.`,
      blocking: false,
      severity: 'info',
    });
  }

  // ---- Settings schema version check ----
  const localSchemaVersion = getManifestSettingsSchemaVersion(localManifest);
  const installedSchemaVersion = getManifestSettingsSchemaVersion(installedManifest);
  if (localSchemaVersion !== installedSchemaVersion) {
    gaps.push({
      field: 'settingsSchema',
      presentIn: 'local-only',
      description: `Settings schema version difference: local v${localSchemaVersion} vs installed v${installedSchemaVersion}. Settings migration will handle the schema transition.`,
      blocking: false,
      severity: 'warning',
    });
  }

  // ---- Dependency check ----
  const localDeps: readonly ExtensionDependency[] = localManifest.dependsOn ?? [];
  const installedDeps: readonly ExtensionDependency[] = installedManifest.dependsOn ?? [];

  if (localDeps.length !== installedDeps.length) {
    gaps.push({
      field: 'dependsOn',
      presentIn: localDeps.length > installedDeps.length ? 'local-only' : 'installed-only',
      description: `Dependency count difference: local has ${localDeps.length}, installed has ${installedDeps.length}. The installed dependency list will be used.`,
      blocking: false,
      severity: 'warning',
    });
  } else {
    // Compare individual dependencies
    const localDepMap = new Map<string, ExtensionDependency>();
    for (const dep of localDeps) {
      localDepMap.set(dep.extensionId, dep);
    }
    for (const dep of installedDeps) {
      const localDep = localDepMap.get(dep.extensionId);
      if (!localDep) {
        gaps.push({
          field: 'dependsOn',
          presentIn: 'installed-only',
          description: `Dependency "${dep.extensionId}" is present in installed bundle but missing from local source.`,
          blocking: false,
          severity: 'info',
        });
      }
    }
    for (const dep of localDeps) {
      const installedDep = installedDeps.find((d) => d.extensionId === dep.extensionId);
      if (!installedDep) {
        gaps.push({
          field: 'dependsOn',
          presentIn: 'local-only',
          description: `Dependency "${dep.extensionId}" is present in local source but missing from installed bundle.`,
          blocking: false,
          severity: 'warning',
        });
      }
    }
  }

  // ---- Migration declarations check ----
  const localMigrations = localManifest.migrations ?? [];
  const installedMigrations = installedManifest.migrations ?? [];
  if (localMigrations.length > 0 && installedMigrations.length === 0) {
    gaps.push({
      field: 'migrations',
      presentIn: 'local-only',
      description: `Local source declares ${localMigrations.length} migration hook(s) but installed bundle declares none. Migration capability may be reduced.`,
      blocking: false,
      severity: 'warning',
    });
  }

  // ---- Contribution ID comparison for blocking/non-blocking ----
  const contribComparison = compareContributionIds(localManifest, installedManifest);

  if (!contribComparison.identical) {
    if (contribComparison.localOnly.length > 0) {
      gaps.push({
        field: 'contributions',
        presentIn: 'local-only',
        description: `${contribComparison.localOnly.length} contribution ID(s) present in local source but missing from installed bundle: [${contribComparison.localOnly.join(', ')}]. Project references to these contributions will break after migration.`,
        blocking: contribComparison.localOnly.length > 0 && contribComparison.installedOnly.length === 0,
        severity: 'error',
      });
    }
    if (contribComparison.installedOnly.length > 0) {
      gaps.push({
        field: 'contributions',
        presentIn: 'installed-only',
        description: `${contribComparison.installedOnly.length} contribution ID(s) present in installed bundle but missing from local source: [${contribComparison.installedOnly.join(', ')}]. New contributions will become available after migration.`,
        blocking: false,
        severity: 'info',
      });
    }
  }

  // ---- Description / label check (purely informational) ----
  if (localManifest.label !== installedManifest.label) {
    gaps.push({
      field: 'label',
      presentIn: 'local-only',
      description: `Label differs: local "${localManifest.label}" vs installed "${installedManifest.label}". The installed label will be displayed.`,
      blocking: false,
      severity: 'info',
    });
  }

  return buildMetadataGapResult(gaps, extensionId);
}

/** Build a MetadataGapResult from a list of gaps. */
function buildMetadataGapResult(
  gaps: readonly MetadataGap[],
  extensionId: string,
): MetadataGapResult {
  const blockingGaps: MetadataGap[] = [];
  const nonBlockingGaps: MetadataGap[] = [];
  const diagnostics: ExtensionDiagnostic[] = [];

  for (const gap of gaps) {
    if (gap.blocking) {
      blockingGaps.push(gap);
    } else {
      nonBlockingGaps.push(gap);
    }
    diagnostics.push({
      severity: gap.severity,
      code: `migration/metadata-gap/${gap.presentIn}/${gap.field}`,
      message: gap.description,
      extensionId,
    });
  }

  return Object.freeze({
    hasBlockingGaps: blockingGaps.length > 0,
    gaps: Object.freeze([...gaps]),
    blockingGaps: Object.freeze([...blockingGaps]),
    nonBlockingGaps: Object.freeze([...nonBlockingGaps]),
    diagnostics: Object.freeze([...diagnostics]),
  });
}

// ---------------------------------------------------------------------------
// Settings transfer
// ---------------------------------------------------------------------------

/**
 * Read local extension settings from localStorage using the standard
 * reigh.ext.* prefix.
 *
 * Returns all key-value pairs currently stored for the extension.
 */
export function readLocalSettings(extensionId: string): Record<string, unknown> {
  const prefix = getSettingsPrefix(extensionId);
  const settings: Record<string, unknown> = {};
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(prefix)) {
        const settingKey = key.slice(prefix.length);
        try {
          const raw = localStorage.getItem(key);
          if (raw !== null) {
            settings[settingKey] = JSON.parse(raw);
          }
        } catch {
          // Unparseable value — skip
        }
      }
    }
  } catch {
    // localStorage may throw in restricted environments — return empty
  }
  return settings;
}

// ---------------------------------------------------------------------------
// Migration execution
// ---------------------------------------------------------------------------

/**
 * Execute a local-to-installed migration: transfer enablement, settings,
 * create pack record, and set up project lock metadata.
 *
 * ## What this does:
 *
 * 1. Validates that extension IDs match between local and installed.
 * 2. Detects metadata gaps and checks contribution ID compatibility.
 * 3. Creates the ExtensionPackRecord in the repository.
 * 4. Transfers enablement state (preserves existing enablement or creates new).
 * 5. Transfers settings from localStorage to a repository snapshot.
 * 6. Creates project lock metadata (lock entry) for the installed pack.
 * 7. Emits `install` lifecycle event with migration detail.
 * 8. Timeline references are preserved because the extension ID is unchanged.
 *
 * ## What this does NOT do:
 *
 * - It does NOT unregister local source contributions. The caller should
 *   handle that via the loader's unload method before calling this.
 * - It does NOT handle bundle content storage (IndexedDB). The caller must
 *   have already stored the bundle bytes and provide the bundleContentRef.
 *
 * @param input - The migration input (local manifest, installed pack, repository, settings, ref).
 * @returns Migration execution result with diagnostics and lifecycle events.
 */
export async function executeLocalToInstalledMigration(
  input: LocalInstalledMigrationInput,
): Promise<MigrationExecuteResult> {
  const {
    localManifest,
    installedPack,
    repository,
    localSettings,
    bundleContentRef,
  } = input;

  const extensionId = localManifest.id as string;
  const installedManifest = installedPack.manifest;
  const lifecycleEvents: ExtensionLifecycleEvent[] = [];
  const blockingDiagnostics: ExtensionDiagnostic[] = [];
  const warningDiagnostics: ExtensionDiagnostic[] = [];

  // ---- Helper: append a lifecycle event ----
  async function appendEvent(
    kind: string,
    message: string,
    detail?: Record<string, unknown>,
    diagnostic?: ExtensionDiagnostic,
  ): Promise<ExtensionLifecycleEvent> {
    const event = createLifecycleEvent(
      extensionId,
      kind as any,
      message,
      detail,
      diagnostic,
    );
    lifecycleEvents.push(event);
    try {
      if (!repository.isDisposed) {
        await repository.appendLifecycleEvent(event);
      }
    } catch {
      // Persistence failure is non-blocking
    }
    return event;
  }

  // ---- Step 1: Validate extension IDs match ----
  if ((localManifest.id as string) !== (installedManifest.id as string)) {
    const diag: ExtensionDiagnostic = {
      severity: 'error',
      code: 'migration/id-mismatch',
      message: `Cannot migrate: local extension ID "${localManifest.id as string}" does not match installed extension ID "${installedManifest.id as string}".`,
      extensionId,
    };
    blockingDiagnostics.push(diag);
    await appendEvent('migration_failure', 'Migration blocked: extension ID mismatch.', undefined, diag);
    return Object.freeze({
      success: false,
      extensionId,
      contributionComparison: compareContributionIds(localManifest, installedManifest),
      metadataGaps: detectMetadataGaps(localManifest, installedManifest),
      blocked: true,
      blockingDiagnostics: Object.freeze([...blockingDiagnostics]),
      warningDiagnostics: Object.freeze([]),
      packRecord: null,
      settingsTransferred: false,
      settingsKeyCount: 0,
      lockEntryCreated: false,
      lifecycleEvents: Object.freeze([...lifecycleEvents]),
      summary: `Migration blocked: extension ID mismatch (local "${localManifest.id as string}", installed "${installedManifest.id as string}").`,
    });
  }

  // ---- Step 2: Contribution ID comparison ----
  const contributionComparison = compareContributionIds(localManifest, installedManifest);

  // ---- Step 3: Metadata gap detection ----
  const metadataGaps = detectMetadataGaps(localManifest, installedManifest);

  // ---- Step 4: Check for blocking conditions ----
  if (metadataGaps.hasBlockingGaps) {
    for (const gap of metadataGaps.blockingGaps) {
      const diag: ExtensionDiagnostic = {
        severity: gap.severity,
        code: `migration/metadata-gap/${gap.presentIn}/${gap.field}`,
        message: gap.description,
        extensionId,
      };
      blockingDiagnostics.push(diag);
    }
    await appendEvent(
      'migration_failure',
      `Migration blocked: ${metadataGaps.blockingGaps.length} blocking metadata gap(s).`,
      { blockingGaps: metadataGaps.blockingGaps.map((g) => ({ field: g.field, description: g.description })) },
    );
    return Object.freeze({
      success: false,
      extensionId,
      contributionComparison,
      metadataGaps,
      blocked: true,
      blockingDiagnostics: Object.freeze([...blockingDiagnostics]),
      warningDiagnostics: Object.freeze([...metadataGaps.diagnostics.filter((d) => d.severity !== 'error')]),
      packRecord: null,
      settingsTransferred: false,
      settingsKeyCount: 0,
      lockEntryCreated: false,
      lifecycleEvents: Object.freeze([...lifecycleEvents]),
      summary: `Migration blocked: ${metadataGaps.blockingGaps.length} blocking metadata gap(s) detected.`,
    });
  }

  // Collect non-blocking diagnostics
  for (const gap of metadataGaps.nonBlockingGaps) {
    warningDiagnostics.push({
      severity: gap.severity,
      code: `migration/metadata-gap/${gap.presentIn}/${gap.field}`,
      message: gap.description,
      extensionId,
    });
  }

  // ---- Step 5: Emit migration start event ----
  await appendEvent(
    'migration_start',
    `Starting local-to-installed migration for extension "${extensionId}" (local v${localManifest.version} → installed v${installedManifest.version}).`,
    {
      localVersion: localManifest.version,
      installedVersion: installedManifest.version,
      localContributionCount: contributionComparison.localCount,
      installedContributionCount: contributionComparison.installedCount,
      sharedContributionIds: contributionComparison.shared,
    },
  );

  // ---- Step 6: Create pack record ----
  const metadata: InstalledExtensionMetadata = installedPack.metadata;
  const packRecord: ExtensionPackRecord = Object.freeze({
    extensionId,
    version: installedManifest.version as string,
    apiVersion: installedManifest.apiVersion,
    integrity: metadata.integrity,
    installedAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    bundleContentRef,
    manifestSnapshot: installedManifest,
    publisher: installedManifest.publisher,
    license: installedManifest.license,
    icon: installedManifest.icon,
  });

  try {
    await repository.putPackRecord(packRecord);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const diag: ExtensionDiagnostic = {
      severity: 'error',
      code: 'migration/pack-record-failed',
      message: `Failed to create pack record for extension "${extensionId}": ${message}`,
      extensionId,
    };
    blockingDiagnostics.push(diag);
    await appendEvent('migration_failure', `Failed to create pack record: ${message}`, undefined, diag);
    return Object.freeze({
      success: false,
      extensionId,
      contributionComparison,
      metadataGaps,
      blocked: true,
      blockingDiagnostics: Object.freeze([...blockingDiagnostics]),
      warningDiagnostics: Object.freeze([...warningDiagnostics]),
      packRecord: null,
      settingsTransferred: false,
      settingsKeyCount: 0,
      lockEntryCreated: false,
      lifecycleEvents: Object.freeze([...lifecycleEvents]),
      summary: `Migration failed: could not create pack record (${message}).`,
    });
  }

  await appendEvent('install', `Pack record created for extension "${extensionId}" (installed v${installedManifest.version}).`, {
    version: installedManifest.version,
    integrity: metadata.integrity,
  });

  // ---- Step 7: Transfer enablement state ----
  let enablementTransferred = false;
  try {
    // Check if enablement already exists (e.g., from a prior install)
    const existingEnablement = await repository.getEnablementState(extensionId);
    if (!existingEnablement) {
      // Create new enablement state — enabled by default after migration
      const enablementState = createEnablementState(
        extensionId,
        true,
        'Enabled after local-to-installed migration',
      );
      await repository.putEnablementState(enablementState);
      enablementTransferred = true;
      await appendEvent('enable', `Enablement state created for extension "${extensionId}" (enabled).`, {
        enabled: true,
        reason: 'local-to-installed migration',
      });
    } else {
      // Keep existing enablement state unchanged
      enablementTransferred = true;
      warningDiagnostics.push({
        severity: 'info',
        code: 'migration/enablement-preserved',
        message: `Enablement state for extension "${extensionId}" already exists in repository; preserving current state (enabled: ${existingEnablement.enabled}).`,
        extensionId,
      });
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    warningDiagnostics.push({
      severity: 'warning',
      code: 'migration/enablement-transfer-failed',
      message: `Failed to transfer enablement state for extension "${extensionId}": ${message}`,
      extensionId,
    });
  }

  // ---- Step 8: Transfer settings ----
  let settingsTransferred = false;
  let settingsKeyCount = 0;

  const settingsKeys = Object.keys(localSettings);
  if (settingsKeys.length > 0) {
    try {
      const schemaVersion = getManifestSettingsSchemaVersion(installedManifest);
      const settingsSnapshot = createSettingsSnapshot(
        extensionId,
        schemaVersion,
        { ...localSettings },
      );
      await repository.putSettingsSnapshot(settingsSnapshot);
      settingsTransferred = true;
      settingsKeyCount = settingsKeys.length;
      await appendEvent(
        'migration_success',
        `Settings transferred for extension "${extensionId}" (${settingsKeyCount} keys at schema v${schemaVersion}).`,
        {
          settingsKeyCount,
          schemaVersion,
          transferredKeys: settingsKeys.slice(0, 20), // Cap for event detail size
          ...(settingsKeys.length > 20 ? { additionalKeys: settingsKeys.length - 20 } : {}),
        },
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      warningDiagnostics.push({
        severity: 'warning',
        code: 'migration/settings-transfer-failed',
        message: `Failed to transfer ${settingsKeys.length} setting(s) for extension "${extensionId}": ${message}`,
        extensionId,
      });
    }
  } else {
    // No local settings to transfer — create empty snapshot from manifest defaults
    try {
      const schemaVersion = getManifestSettingsSchemaVersion(installedManifest);
      const manifestDefaults: Record<string, unknown> =
        (installedManifest as any).settingsDefaults ?? {};
      const settingsSnapshot = createSettingsSnapshot(
        extensionId,
        schemaVersion,
        { ...manifestDefaults },
      );
      await repository.putSettingsSnapshot(settingsSnapshot);
      settingsTransferred = true;
      settingsKeyCount = Object.keys(manifestDefaults).length;
    } catch {
      // Non-blocking
    }
  }

  // ---- Step 9: Create project lock metadata ----
  let lockEntryCreated = false;
  try {
    const { buildLockEntry } = await import('@/tools/video-editor/runtime/extensionLockMetadata');
    const lockEntry = buildLockEntry(packRecord, installedManifest);
    await repository.putLockEntry(lockEntry);
    lockEntryCreated = true;
    await appendEvent('install', `Project lock entry created for extension "${extensionId}".`, {
      version: lockEntry.version,
      versionRange: lockEntry.versionRange,
      contributionRefs: lockEntry.contributionRefs,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    warningDiagnostics.push({
      severity: 'warning',
      code: 'migration/lock-entry-failed',
      message: `Failed to create project lock entry for extension "${extensionId}": ${message}`,
      extensionId,
    });
  }

  // ---- Step 10: Build summary ----
  const parts: string[] = [];
  parts.push(`Extension "${extensionId}" migrated from local source to installed bundle.`);
  parts.push(`Version: ${installedManifest.version}`);

  if (contributionComparison.identical) {
    parts.push(`Contribution IDs: ${contributionComparison.shared.length} match (identical).`);
  } else {
    parts.push(`Contribution IDs: ${contributionComparison.shared.length} shared, ${contributionComparison.localOnly.length} local-only, ${contributionComparison.installedOnly.length} installed-only.`);
  }

  if (settingsTransferred && settingsKeyCount > 0) {
    parts.push(`${settingsKeyCount} setting(s) transferred to repository.`);
  } else if (settingsTransferred) {
    parts.push('No local settings to transfer — defaults written.');
  }

  if (lockEntryCreated) {
    parts.push('Project lock entry created.');
  }

  if (metadataGaps.nonBlockingGaps.length > 0) {
    parts.push(`${metadataGaps.nonBlockingGaps.length} metadata gap(s) noted (non-blocking).`);
  }

  const summary = parts.join(' ');

  // ---- Emit completion event ----
  await appendEvent('activation_success', summary, {
    settingsTransferred,
    settingsKeyCount,
    lockEntryCreated,
    enablementTransferred,
    contributionComparison: {
      identical: contributionComparison.identical,
      sharedCount: contributionComparison.shared.length,
      localOnlyCount: contributionComparison.localOnly.length,
      installedOnlyCount: contributionComparison.installedOnly.length,
    },
    gapCount: metadataGaps.gaps.length,
  });

  return Object.freeze({
    success: true,
    extensionId,
    contributionComparison,
    metadataGaps,
    blocked: false,
    blockingDiagnostics: Object.freeze([]),
    warningDiagnostics: Object.freeze([...warningDiagnostics]),
    packRecord,
    settingsTransferred,
    settingsKeyCount,
    lockEntryCreated,
    lifecycleEvents: Object.freeze([...lifecycleEvents]),
    summary,
  });
}

// ---------------------------------------------------------------------------
// Precondition check
// ---------------------------------------------------------------------------

/**
 * Result of checking whether a local-to-installed migration can proceed.
 */
export interface MigrationPreconditionResult {
  /** Whether all preconditions are satisfied. */
  readonly canProceed: boolean;
  /** The extension ID being checked. */
  readonly extensionId: string;
  /** Contribution ID comparison result. */
  readonly contributionComparison: ContributionIdComparison;
  /** Metadata gap result (may include blocking gaps). */
  readonly metadataGaps: MetadataGapResult;
  /** Blocking diagnostics. */
  readonly blockingDiagnostics: readonly ExtensionDiagnostic[];
  /** Warning/info diagnostics. */
  readonly warningDiagnostics: readonly ExtensionDiagnostic[];
  /** Human-readable summary of the precondition check. */
  readonly summary: string;
}

/**
 * Check preconditions for a local-to-installed migration.
 *
 * Verifies:
 *   - Extension IDs match.
 *   - No blocking metadata gaps.
 *   - Contribution IDs are compatible (local-only contributions are flagged
 *     as blocking since they would be orphaned after migration).
 *
 * This is a lightweight check that does not modify any state.
 * It can be used to preview the migration before committing.
 *
 * @param localManifest - The workspace-source (local) extension manifest.
 * @param installedManifest - The installed extension manifest.
 * @returns Precondition check result with diagnostics.
 */
export function checkMigrationPreconditions(
  localManifest: ExtensionManifest,
  installedManifest: ExtensionManifest,
): MigrationPreconditionResult {
  const extensionId = localManifest.id as string;
  const blockingDiagnostics: ExtensionDiagnostic[] = [];
  const warningDiagnostics: ExtensionDiagnostic[] = [];

  // Check extension ID match
  if ((localManifest.id as string) !== (installedManifest.id as string)) {
    const diag: ExtensionDiagnostic = {
      severity: 'error',
      code: 'migration/id-mismatch',
      message: `Cannot migrate: local extension ID "${localManifest.id as string}" does not match installed extension ID "${installedManifest.id as string}".`,
      extensionId,
    };
    blockingDiagnostics.push(diag);
    return Object.freeze({
      canProceed: false,
      extensionId,
      contributionComparison: compareContributionIds(localManifest, installedManifest),
      metadataGaps: detectMetadataGaps(localManifest, installedManifest),
      blockingDiagnostics: Object.freeze([...blockingDiagnostics]),
      warningDiagnostics: Object.freeze([]),
      summary: `Migration blocked: extension ID mismatch.`,
    });
  }

  // Contribution ID comparison
  const contributionComparison = compareContributionIds(localManifest, installedManifest);

  // Metadata gap detection
  const metadataGaps = detectMetadataGaps(localManifest, installedManifest);

  // Add blocking diagnostics from metadata gaps
  for (const gap of metadataGaps.blockingGaps) {
    blockingDiagnostics.push({
      severity: gap.severity,
      code: `migration/metadata-gap/${gap.presentIn}/${gap.field}`,
      message: gap.description,
      extensionId,
    });
  }

  // Add non-blocking diagnostics
  for (const gap of metadataGaps.nonBlockingGaps) {
    warningDiagnostics.push({
      severity: gap.severity,
      code: `migration/metadata-gap/${gap.presentIn}/${gap.field}`,
      message: gap.description,
      extensionId,
    });
  }

  // If local-only contribution IDs exist, add a specific blocking diagnostic
  if (contributionComparison.localOnly.length > 0) {
    const diag: ExtensionDiagnostic = {
      severity: 'error',
      code: 'migration/local-only-contributions',
      message: `${contributionComparison.localOnly.length} contribution ID(s) exist in the local source but are missing from the installed bundle: [${contributionComparison.localOnly.join(', ')}]. These contributions will not be available after migration and any project references to them will break.`,
      extensionId,
      detail: {
        localOnlyIds: contributionComparison.localOnly,
        recommendation: 'Ensure the installed bundle includes all contributions currently used in the project before migrating.',
      },
    };
    blockingDiagnostics.push(diag);
  }

  const canProceed = blockingDiagnostics.length === 0;

  // Build summary
  let summary: string;
  if (!canProceed) {
    const reasons = blockingDiagnostics.map((d) => d.code).join(', ');
    summary = `Migration cannot proceed: ${blockingDiagnostics.length} blocking issue(s) found (${reasons}).`;
  } else {
    const parts: string[] = [];
    parts.push('Migration can proceed.');
    if (contributionComparison.identical) {
      parts.push('All contribution IDs match.');
    } else {
      parts.push(`${contributionComparison.shared.length} contribution IDs shared.`);
      if (contributionComparison.installedOnly.length > 0) {
        parts.push(`${contributionComparison.installedOnly.length} new contribution(s) available in installed bundle.`);
      }
    }
    if (metadataGaps.nonBlockingGaps.length > 0) {
      parts.push(`${metadataGaps.nonBlockingGaps.length} non-blocking metadata gap(s) noted.`);
    }
    summary = parts.join(' ');
  }

  return Object.freeze({
    canProceed,
    extensionId,
    contributionComparison,
    metadataGaps,
    blockingDiagnostics: Object.freeze([...blockingDiagnostics]),
    warningDiagnostics: Object.freeze([...warningDiagnostics]),
    summary,
  });
}
