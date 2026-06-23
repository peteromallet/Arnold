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
} from '@/tools/video-editor/runtime/extensionLoader';
import type { ExtensionPackRecord } from '@/tools/video-editor/runtime/extensionStateRepository';
import type { PackageStateInventoryEntry } from '@/tools/video-editor/runtime/extensionSurface';

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
    return useMemo<UseExtensionLoaderWiringResult>(() => ({
      resolvedExtensions: direct,
      diagnostics: [],
      isResolving: false,
      loaderResult: null,
      error: null,
      packageStateEntries: [],
    }), [direct]);
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

          bundleRefToInput.set(record.bundleContentRef, {
            kind: 'installed',
            packRecord: record,
            bundleContent: content,
          });
        }

        inputs.push(...bundleRefToInput.values());

        if (cancelled) return;

        // 3. Validate
        const validation = loader.validate(inputs);

        if (cancelled) return;

        const validPackages = validation.entries
          .filter((entry) => entry.valid && entry.validatedPackage)
          .map((entry) => entry.validatedPackage!);

        // 4. Load (includes dependency + conflict resolution)
        const loadResult = await loader.load(validPackages);

        if (cancelled) return;

        lastResolvedKeyRef.current = resolveKey;

        // Derive packageStateEntries from loader result entries
        const packageStateEntries: PackageStateInventoryEntry[] =
          loadResult.entries.map((entry) => ({
            extensionId: entry.extensionId,
            packageState: entry.packageState,
            stateReason: entry.stateReason,
            packageMetadata: entry.packageMetadata,
          }));

        setState({
          resolvedExtensions: loadResult.loadedExtensions,
          diagnostics: [
            ...validation.diagnostics,
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
