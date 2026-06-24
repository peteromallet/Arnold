/**
 * Host-owned hook that wires ExtensionLoader into the provider lifecycle.
 *
 * Accepts direct-local extensions plus optional repository/bundle state and
 * resolves them into a final ReighExtension[] suitable for the existing
 * `extensions` prop of VideoEditorProvider / EditorRuntimeProvider.
 *
 * This keeps the loader/lifecycle state scoped to the mounted provider
 * (per SD1) and feeds diagnostics/status surfaces without duplicate
 * activation.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ExtensionDiagnostic, ReighExtension } from '@reigh/editor-sdk';
import type { ExtensionStateRepository } from '@/tools/video-editor/runtime/extensionStateRepository';
import {
  createExtensionLoader,
  type ExtensionLoader,
  type ExtensionLoaderLoadResult,
  type DirectExtensionInput,
  type InstalledExtensionInput,
  type ExtensionLoaderInput,
  type PackageMetadata,
} from '@/tools/video-editor/runtime/extensionLoader';
import type { ExtensionPackRecord } from '@/tools/video-editor/runtime/extensionStateRepository';
import type { PackageStateInventoryEntry } from '@/tools/video-editor/runtime/extensionSurface';
import { computePackageContributionSummary } from '@/tools/video-editor/runtime/extensionSurface';
import type { ExtensionContribution } from '@reigh/editor-sdk';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function extensionIdFromInput(input: ExtensionLoaderInput, diagnostics: readonly ExtensionDiagnostic[]): string {
  if (input.kind === 'installed') {
    return input.packRecord.extensionId;
  }

  const manifestId = input.extension.manifest.id;
  if (typeof manifestId === 'string' && manifestId.length > 0) {
    return manifestId;
  }

  return diagnostics.find((diagnostic) => diagnostic.extensionId)?.extensionId ?? '(unknown)';
}

function metadataFromManifest(manifest: Partial<ReighExtension['manifest']> | null | undefined): PackageMetadata | null {
  if (!manifest || typeof manifest !== 'object') return null;

  const id = typeof manifest.id === 'string' ? manifest.id : undefined;
  const label = typeof manifest.label === 'string' ? manifest.label : id;
  const version = typeof manifest.version === 'string' ? manifest.version : '0.0.0';
  if (!label && !id) return null;

  return {
    label: label ?? id ?? '(unknown)',
    version,
    publisher: typeof manifest.publisher === 'string' ? manifest.publisher : undefined,
    description: typeof manifest.description === 'string' ? manifest.description : undefined,
    license: typeof manifest.license === 'string' ? manifest.license : undefined,
  };
}

function metadataFromInput(input: ExtensionLoaderInput): PackageMetadata | null {
  if (input.kind === 'installed') {
    const manifest = input.packRecord.manifestSnapshot;
    const manifestMetadata = metadataFromManifest(manifest);
    return manifestMetadata
      ? {
          ...manifestMetadata,
          publisher: input.packRecord.publisher ?? manifestMetadata.publisher,
          license: input.packRecord.license ?? manifestMetadata.license,
        }
      : null;
  }

  return metadataFromManifest(input.extension.manifest);
}

function diagnosticMessage(diagnostics: readonly ExtensionDiagnostic[], fallback: string): string {
  const messages = diagnostics
    .map((diagnostic) => diagnostic.message)
    .filter((message): message is string => typeof message === 'string' && message.length > 0);
  return messages.length > 0 ? messages.join('; ') : fallback;
}

function settingValueMatchesType(value: unknown, rawType: unknown): boolean {
  const types = Array.isArray(rawType)
    ? rawType.filter((item): item is string => typeof item === 'string')
    : typeof rawType === 'string'
      ? [rawType]
      : [];

  if (types.length === 0) return true;
  if (value === null) return types.includes('null');

  return types.some((type) => {
    switch (type) {
      case 'object':
        return isRecord(value);
      case 'array':
        return Array.isArray(value);
      case 'string':
        return typeof value === 'string';
      case 'number':
        return typeof value === 'number' && Number.isFinite(value);
      case 'integer':
        return typeof value === 'number' && Number.isInteger(value);
      case 'boolean':
        return typeof value === 'boolean';
      default:
        return true;
    }
  });
}

function validateSettingsValuesAgainstSchema(
  values: Record<string, unknown>,
  rawSchema: unknown,
): string | null {
  if (!isRecord(rawSchema)) {
    return 'settingsSchema.schema must be an object.';
  }
  if (rawSchema.type !== undefined && rawSchema.type !== 'object') {
    return 'settingsSchema.schema.type must be "object".';
  }

  const properties = isRecord(rawSchema.properties) ? rawSchema.properties : {};
  const required = Array.isArray(rawSchema.required)
    ? rawSchema.required.filter((item): item is string => typeof item === 'string')
    : [];

  for (const key of required) {
    if (!(key in values)) {
      return `Missing required setting "${key}".`;
    }
  }

  if (rawSchema.additionalProperties === false) {
    const knownKeys = new Set(Object.keys(properties));
    const unknownKey = Object.keys(values).find((key) => !knownKeys.has(key));
    if (unknownKey) {
      return `Unknown setting "${unknownKey}" is not allowed by the manifest schema.`;
    }
  }

  for (const [key, propSchema] of Object.entries(properties)) {
    if (!(key in values) || !isRecord(propSchema)) continue;

    const value = values[key];
    if (!settingValueMatchesType(value, propSchema.type)) {
      return `Setting "${key}" does not match the manifest schema type.`;
    }

    if (Array.isArray(propSchema.enum) && !propSchema.enum.includes(value)) {
      return `Setting "${key}" must be one of the manifest schema enum values.`;
    }

    if (typeof value === 'number') {
      if (typeof propSchema.minimum === 'number' && value < propSchema.minimum) {
        return `Setting "${key}" must be greater than or equal to ${propSchema.minimum}.`;
      }
      if (typeof propSchema.maximum === 'number' && value > propSchema.maximum) {
        return `Setting "${key}" must be less than or equal to ${propSchema.maximum}.`;
      }
    }

    if (typeof value === 'string') {
      if (typeof propSchema.minLength === 'number' && value.length < propSchema.minLength) {
        return `Setting "${key}" is shorter than the manifest schema minimum length.`;
      }
      if (typeof propSchema.maxLength === 'number' && value.length > propSchema.maxLength) {
        return `Setting "${key}" is longer than the manifest schema maximum length.`;
      }
      if (typeof propSchema.pattern === 'string') {
        try {
          if (!new RegExp(propSchema.pattern).test(value)) {
            return `Setting "${key}" does not match the manifest schema pattern.`;
          }
        } catch {
          return `Setting "${key}" has an invalid manifest schema pattern.`;
        }
      }
    }
  }

  return null;
}

function createSettingsErrorDiagnostic(extensionId: string, reason: string): ExtensionDiagnostic {
  return {
    severity: 'error',
    code: 'settings/resolution-failed',
    message: `Settings resolution failed: ${reason}`,
    extensionId,
    detail: { source: 'extension-loader-wiring' },
  };
}

function contributionsFromManifest(manifest: Partial<ReighExtension['manifest']> | null | undefined): readonly ExtensionContribution[] | null {
  if (!manifest || !manifest.contributions) return null;
  const contribs = manifest.contributions;
  if (!Array.isArray(contribs)) return null;
  try {
    return Object.freeze(contribs.map((c) => ({ ...c })));
  } catch {
    return null;
  }
}

function contributionsFromInput(input: ExtensionLoaderInput): readonly ExtensionContribution[] | null {
  if (input.kind === 'installed') {
    return contributionsFromManifest(input.packRecord.manifestSnapshot);
  }
  return contributionsFromManifest(input.extension.manifest);
}


// ---------------------------------------------------------------------------
// Bundle content store (separate from metadata repo per SD2)
// ---------------------------------------------------------------------------

/**
 * Minimal interface for retrieving installed bundle content bytes.
 *
 * The base ExtensionStateRepository contract does not include bundle
 * storage (per SD2 — bundle bytes are browser-local in IndexedDB).
 * Consumers that need to load installed packs must provide an object
 * conforming to this interface.
 */
export interface BundleContentStore {
  getBundleContent(ref: string): Promise<string | null>;
}

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

export interface UseExtensionLoaderWiringOptions {
  /**
   * Direct workspace-source extensions (the existing `extensions` prop).
   * Passed through as-is when no repository is provided.
   */
  directExtensions?: readonly ReighExtension[];

  /**
   * Repository for installed pack records, enablement, dev overrides,
   * and settings snapshots.  When null/undefined, only direct extensions
   * are used and the loader is bypassed entirely.
   *
   * M1-LOCKED: Direct host-supplied extensions that bypass the loader are
   * excluded from the manager's package-state inventory.  Only installed
   * packs that pass through the loader populate PackageStateInventoryEntry[].
   * See docs/extensions/extension-layer-foundation-assessment.md §2.3.
   */
  repository?: ExtensionStateRepository | null;

  /**
   * Store for retrieving installed bundle content bytes.
   *
   * Required when `repository` is provided AND installed packs exist.
   * This is typically the IndexedDB-backed repository (per SD2).
   */
  bundleStore?: BundleContentStore | null;

  /**
   * Monotonic refresh key that triggers re-resolution when incremented.
   *
   * After a successful persistence write (enable/disable, settings save),
   * the caller should increment this key to force the loader to re-read
   * repository state and produce updated extensions, diagnostics, and
   * package-state inventory.  Defaults to 0 when not provided.
   *
   * Without this, the hook's internal deduplication key (based only on
   * direct extension IDs + repository presence) would skip re-resolution
   * even after the repository state changes, leaving UI, contributions,
   * and diagnostics stale.
   */
  refreshKey?: number;
}

// ---------------------------------------------------------------------------
// Result
// ---------------------------------------------------------------------------

export interface UseExtensionLoaderWiringResult {
  /**
   * Resolved extensions ready for the `normalizeExtensionRuntime` +
   * `ExtensionLifecycleHost` pipeline (the `extensions` prop).
   */
  resolvedExtensions: readonly ReighExtension[];

  /**
   * Combined diagnostics from loader validation, dependency resolution,
   * conflict resolution, and load errors.  Empty when no repository is
   * provided (only direct extensions, no loader diagnostics generated).
   */
  diagnostics: readonly ExtensionDiagnostic[];

  /** Whether async resolution is in progress. */
  isResolving: boolean;

  /**
   * Full loader load result.  `null` when no repository is provided
   * or resolution has not yet completed.
   */
  loaderResult: ExtensionLoaderLoadResult | null;

  /**
   * Any error that prevented resolution from completing.
   * `null` on success.
   */
  error: Error | null;

  /**
   * Package-state inventory entries derived from the loader result.
   *
   * Carries package state for every package that reached the loader,
   * including non-activated packages (disabled, invalid, incompatible,
   * duplicate, settings-error, runtime-error).  Empty when no repository
   * is provided or resolution has not yet completed.
   *
   * Consumers should read this rather than inferring state from
   * `resolvedExtensions`.
   */
  packageStateEntries: readonly PackageStateInventoryEntry[];
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Wire the ExtensionLoader into provider-scoped extension resolution.
 *
 * When `repository` is provided:
 *   1. Fetches all installed pack records + enablement + dev overrides.
 *   2. Fetches bundle content for each installed pack (via `bundleStore`).
 *   3. Combines with direct-local extensions.
 *   4. Runs through loader.validate() → loader.load() (includes dependency
 *      resolution, conflict resolution, integrity checks).
 *   5. Returns the resolved ReighExtension[] + diagnostics.
 *
 * When `repository` is null/undefined:
 *   Falls back to passing `directExtensions` through unchanged (backward
 *   compatible with the pre-loader behaviour).
 *
 * The loader is created once per hook mount (memoized via useRef) to avoid
 * repeated instantiation across re-renders.
 */
export function useExtensionLoaderWiring(
  options: UseExtensionLoaderWiringOptions,
): UseExtensionLoaderWiringResult {
  const {
    directExtensions,
    repository,
    bundleStore,
    refreshKey = 0,
  } = options;

  const direct = directExtensions ?? [];

  // ---- No repository → fast path (no loader needed) ---------------------
  if (!repository) {
    return useMemo<UseExtensionLoaderWiringResult>(() => {
      const packageStateEntries: PackageStateInventoryEntry[] = direct.map((ext) => {
        const manifest = ext.manifest;
        const rawId = manifest.id;
        const extensionId = (typeof rawId === 'string' && rawId.length > 0) ? rawId : '(unknown)';
        const metadata = metadataFromManifest(manifest);
        const contribs = contributionsFromManifest(manifest);
        const summary = computePackageContributionSummary(contribs);
        return {
          extensionId,
          packageState: 'loaded' as const,
          stateReason: 'Direct host-supplied extension',
          packageMetadata: metadata,
          manifestContributions: contribs,
          contributionSummary: summary,
        };
      });
      return {
        resolvedExtensions: direct,
        diagnostics: [],
        isResolving: false,
        loaderResult: null,
        error: null,
        packageStateEntries: Object.freeze(packageStateEntries),
      };
    }, [direct]);
  }

  // ---- Repository path --------------------------------------------------
  // Stabilise the repository reference with a ref to avoid re-triggering
  // the async effect when the caller passes a new object with the same
  // logical identity on every render (common with inline mock objects).
  const repoRef = useRef<ExtensionStateRepository | null>(repository);
  const prevRepoRef = useRef<ExtensionStateRepository | null>(repository);
  if (prevRepoRef.current !== repository) {
    prevRepoRef.current = repository;
    // Only update the loader if the repository actually changes identity
    if (repoRef.current !== repository) {
      repoRef.current = repository;
    }
  }
  const stableRepo = repoRef.current;

  const loaderRef = useRef<ExtensionLoader | null>(null);
  if (!loaderRef.current) {
    loaderRef.current = createExtensionLoader(stableRepo);
  }

  const [state, setState] = useState<{
    resolvedExtensions: readonly ReighExtension[];
    diagnostics: readonly ExtensionDiagnostic[];
    loaderResult: ExtensionLoaderLoadResult | null;
    error: Error | null;
    packageStateEntries: readonly PackageStateInventoryEntry[];
  }>({
    resolvedExtensions: direct,
    diagnostics: [],
    loaderResult: null,
    error: null,
    packageStateEntries: [],
  });

  const [isResolving, setIsResolving] = useState(true);

  // Track the last resolution key to avoid duplicate resolutions
  const lastResolvedKeyRef = useRef<string>('');

  // Stable serialization of directExtensions for the effect dependency.
  // We key on extension IDs + versions to avoid re-triggering the async
  // resolution when the array reference changes but content is identical.
  const directKey = useMemo(
    () => direct.map((e) => `${e.manifest.id as string}@${e.manifest.version}`).join(','),
    [direct],
  );

  useEffect(() => {
    const resolveKey = `${directKey}::${String(Boolean(stableRepo))}::${refreshKey}`;
    if (resolveKey === lastResolvedKeyRef.current && state.loaderResult !== null) {
      // Already resolved this combination — don't re-resolve
      setIsResolving(false);
      return;
    }

    let cancelled = false;
    const loader = loaderRef.current!;

    async function resolve() {
      setIsResolving(true);

      try {
        // 1. Fetch the full repo state (pack records, enablement, overrides)
        const fullState = await stableRepo!.getFullExtensionState();

        if (cancelled) return;

        const packRecords: ExtensionPackRecord[] = fullState.packs
          ? Object.values(fullState.packs)
          : [];
        const enablementStates = fullState.enablement
          ? Object.values(fullState.enablement)
          : [];
        const devOverrides = fullState.devOverrides
          ? Object.values(fullState.devOverrides)
          : [];

        // 2. Build loader inputs: direct + installed
        const inputs: ExtensionLoaderInput[] = [];

        // ---- Build input-metadata map for manifest-contribution resolution ----
        // Tracks per-extensionId direct and installed manifest contributions
        // so load result entries (which don't carry form information) can be
        // enriched with the correct manifestContributions and contributionSummary.
        interface InputMeta {
          manifestContributions: readonly ExtensionContribution[] | null;
        }
        const inputMetaByExtId = new Map<string, { direct: InputMeta | null; installed: InputMeta | null }>();
        function ensureMeta(extId: string) {
          let meta = inputMetaByExtId.get(extId);
          if (!meta) {
            meta = { direct: null, installed: null };
            inputMetaByExtId.set(extId, meta);
          }
          return meta;
        }

        // Direct extensions (workspace source)
        for (const ext of direct) {
          inputs.push({
            kind: 'direct',
            extension: ext,
          } satisfies DirectExtensionInput);
        }

        // Installed pack extensions
        const bundleRefToInput = new Map<string, InstalledExtensionInput>();
        for (const record of packRecords) {
          if (!bundleStore) {
            // No bundle store — skip installed packs (diagnostic emitted by loader)
            continue;
          }
          const content = await bundleStore.getBundleContent(record.bundleContentRef);
          if (cancelled) return;

          if (content === null) {
            // Missing bundle content — the loader will emit a diagnostic
            continue;
          }

          // Populate installed input metadata for manifest contribution resolution
          const extId = record.extensionId;
          const installedMeta = ensureMeta(extId);
          installedMeta.installed = {
            manifestContributions: contributionsFromManifest(record.manifestSnapshot),
          };

          bundleRefToInput.set(record.bundleContentRef, {
            kind: 'installed',
            packRecord: record,
            bundleContent: content,
          });
        }

        inputs.push(...bundleRefToInput.values());

        if (cancelled) return;

        // Populate direct input metadata (extracted from extension manifests)
        for (const ext of direct) {
          const extId = (ext.manifest.id as string) || '(unknown)';
          const directMeta = ensureMeta(extId);
          directMeta.direct = {
            manifestContributions: contributionsFromManifest(ext.manifest),
          };
        }

        // 3. Validate
        const validation = loader.validate(inputs);

        if (cancelled) return;

        const invalidPackageStateEntries: PackageStateInventoryEntry[] = validation.entries
          .filter((entry) => !entry.valid)
          .map((entry) => {
            const extId = extensionIdFromInput(entry.input, entry.errors);
            const manifestContribs = contributionsFromInput(entry.input);
            return {
              extensionId: extId,
              packageState: 'invalid' as const,
              stateReason: diagnosticMessage(entry.errors, 'Manifest validation failed.'),
              packageMetadata: metadataFromInput(entry.input),
              manifestContributions: manifestContribs,
              contributionSummary: manifestContribs && manifestContribs.length > 0
                ? computePackageContributionSummary(manifestContribs)
                : null,
            };
          });

        const validPackages = validation.entries
          .filter((entry) => entry.valid && entry.validatedPackage)
          .map((entry) => entry.validatedPackage!);

        const settingsErrorEntries: PackageStateInventoryEntry[] = [];
        const settingsDiagnostics: ExtensionDiagnostic[] = [];
        const loadablePackages = validPackages.filter((pkg) => {
          const manifest = pkg.form === 'workspace-source' ? pkg.manifest : pkg.pack.manifest;
          const extensionId = manifest.id as string;
          const snapshot = fullState.settings?.[extensionId];
          if (!snapshot) return true;

          try {
            if (!isRecord(snapshot.values)) {
              const diagnostic = createSettingsErrorDiagnostic(
                extensionId,
                'settings snapshot values must be a JSON object.',
              );
              settingsDiagnostics.push(diagnostic);
              {
                const manifestContribs = contributionsFromManifest(manifest);
                settingsErrorEntries.push({
                  extensionId,
                  packageState: 'settings-error' as const,
                  stateReason: diagnostic.message,
                  packageMetadata: metadataFromManifest(manifest),
                  manifestContributions: manifestContribs,
                  contributionSummary: manifestContribs && manifestContribs.length > 0
                    ? computePackageContributionSummary(manifestContribs)
                    : null,
                });
              }
              return false;
            }

            const validationError = validateSettingsValuesAgainstSchema(
              snapshot.values,
              manifest.settingsSchema?.schema,
            );
            if (validationError) {
              const diagnostic = createSettingsErrorDiagnostic(extensionId, validationError);
              settingsDiagnostics.push(diagnostic);
              {
                const manifestContribs = contributionsFromManifest(manifest);
                settingsErrorEntries.push({
                  extensionId,
                  packageState: 'settings-error' as const,
                  stateReason: diagnostic.message,
                  packageMetadata: metadataFromManifest(manifest),
                  manifestContributions: manifestContribs,
                  contributionSummary: manifestContribs && manifestContribs.length > 0
                    ? computePackageContributionSummary(manifestContribs)
                    : null,
                });
              }
              return false;
            }
          } catch (err) {
            const diagnostic = createSettingsErrorDiagnostic(
              extensionId,
              err instanceof Error ? err.message : String(err),
            );
            settingsDiagnostics.push(diagnostic);
            {
              const manifestContribs = contributionsFromManifest(manifest);
              settingsErrorEntries.push({
                extensionId,
                packageState: 'settings-error' as const,
                stateReason: diagnostic.message,
                packageMetadata: metadataFromManifest(manifest),
                manifestContributions: manifestContribs,
                contributionSummary: manifestContribs && manifestContribs.length > 0
                  ? computePackageContributionSummary(manifestContribs)
                  : null,
              });
            }
            return false;
          }

          return true;
        });

        // 4. Load (includes dependency + conflict resolution)
        const loadResult = await loader.load(loadablePackages);

        if (cancelled) return;

        lastResolvedKeyRef.current = resolveKey;

        // ---- Resolve manifestContributions for load result entries ----
        // ExtensionLoadEntry does not carry manifest contributions, so we
        // resolve them from the input-metadata map. For conflicting extension
        // IDs (both direct and installed forms), we use the conflict-resolution
        // result to determine which form won or lost.
        function resolveContributionsForLoadEntry(
          extId: string,
          packageState: string,
        ): { manifestContributions: readonly ExtensionContribution[] | null; contributionSummary: PackageContributionSummary | null } {
          const meta = inputMetaByExtId.get(extId);
          const conflictEntry = loadResult.conflictResolution?.entries.find(
            (ce) => ce.extensionId === extId,
          );

          let manifestContributions: readonly ExtensionContribution[] | null = null;

          if (meta) {
            if (conflictEntry && conflictEntry.hasConflict) {
              // For winner entries (loaded, incompatible, runtime-error): use winner's form.
              // For loser entries (duplicate, disabled-by-user): use the opposite form.
              if (packageState === 'duplicate' || packageState === 'disabled-by-user') {
                // Loser: opposite of winner
                manifestContributions = conflictEntry.winner === 'local'
                  ? meta.installed?.manifestContributions ?? null
                  : meta.direct?.manifestContributions ?? null;
              } else {
                // Winner (loaded, incompatible, runtime-error)
                manifestContributions = conflictEntry.winner === 'local'
                  ? meta.direct?.manifestContributions ?? null
                  : meta.installed?.manifestContributions ?? null;
              }
            } else {
              // No conflict: use whichever form exists (prefer direct over installed)
              manifestContributions = meta.direct?.manifestContributions
                ?? meta.installed?.manifestContributions
                ?? null;
            }
          }

          return {
            manifestContributions,
            contributionSummary: manifestContributions && manifestContributions.length > 0
              ? computePackageContributionSummary(manifestContributions)
              : null,
          };
        }

        // Derive packageStateEntries from loader result entries
        const packageStateEntries: PackageStateInventoryEntry[] =
          [
            ...invalidPackageStateEntries,
            ...settingsErrorEntries,
            ...loadResult.entries.map((entry) => {
              const resolved = resolveContributionsForLoadEntry(entry.extensionId, entry.packageState);
              return {
                extensionId: entry.extensionId,
                packageState: entry.packageState,
                stateReason: entry.stateReason,
                packageMetadata: entry.packageMetadata,
                manifestContributions: resolved.manifestContributions,
                contributionSummary: resolved.contributionSummary,
              };
            }),
          ];

        setState({
          resolvedExtensions: loadResult.loadedExtensions,
          diagnostics: [
            ...validation.diagnostics,
            ...settingsDiagnostics,
            ...loadResult.diagnostics,
          ],
          loaderResult: loadResult,
          error: null,
          packageStateEntries: Object.freeze(packageStateEntries),
        });
      } catch (err) {
        if (cancelled) return;
        setState((prev) => ({
          ...prev,
          error: err instanceof Error ? err : new Error(String(err)),
        }));
      } finally {
        if (!cancelled) {
          setIsResolving(false);
        }
      }
    }

    resolve();

    return () => {
      cancelled = true;
    };
  }, [directKey, refreshKey]);

  return {
    resolvedExtensions: state.resolvedExtensions,
    diagnostics: state.diagnostics,
    isResolving,
    loaderResult: state.loaderResult,
    error: state.error,
    packageStateEntries: state.packageStateEntries,
  };
}
