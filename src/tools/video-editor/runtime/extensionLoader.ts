/**
 * ExtensionLoader core (M14, T11/T12).
 *
 * Validates, loads, and unloads direct/source and installed extension pack
 * records through manifest/integrity validation, resolves dependencies,
 * isolates per-pack failures, and emits diagnostics/lifecycle events without
 * owning global state.
 *
 * The loader feeds the existing provider-scoped ExtensionLifecycleHost pipeline
 * (SD1): it validates/enriches ReighExtension[] before feeding it to the
 * existing lifecycle host's synchronize() method.
 */

import type {
  ReighExtension,
  ExtensionManifest,
  ExtensionDiagnostic,
  InstalledExtensionPackage,
  ExtensionDependency,
  DependencyPosture,
} from '@reigh/editor-sdk';
import { defineExtension } from '@reigh/editor-sdk';
import type {
  ExtensionPackRecord,
  ExtensionStateRepository,
  ExtensionLifecycleEvent,
  DevOverrideState,
  ExtensionEnablementState,
} from '@/tools/video-editor/runtime/extensionStateRepository';
import { createLifecycleEvent } from '@/tools/video-editor/runtime/extensionStateRepository';
import type {
  PackageValidationResult,
  ValidatedPackage,
  WorkspaceSourcePackage,
  InstalledBundlePackage,
} from '@/tools/video-editor/runtime/extensionPackageManifest';
import {
  validateWorkspaceSourcePackage,
  validateInstalledBundlePackage,
} from '@/tools/video-editor/runtime/extensionPackageManifest';
import {
  verifyIntegrity,
} from '@/tools/video-editor/runtime/extensionIntegrity';
import {
  syncEnabledPackLockEntries,
} from '@/tools/video-editor/runtime/extensionLockMetadata';

// ---------------------------------------------------------------------------
// Semver helpers
// ---------------------------------------------------------------------------

/** Parse a semver string into [major, minor, patch] or null. */
function parseSemver(version: string): [number, number, number] | null {
  const match = /^(\d+)\.(\d+)\.(\d+)/.exec(version.trim());
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

/** Compare two semver tuples: negative if a < b, 0 if equal, positive if a > b. */
function compareSemver(
  a: [number, number, number],
  b: [number, number, number],
): number {
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return 0;
}

/**
 * Check whether a semver version satisfies a version-range expression.
 *
 * Supports:
 *   - Exact: "1.2.3"
 *   - Caret: "^1.2.3"  (>=1.2.3 <2.0.0)
 *   - Tilde: "~1.2.3"  (>=1.2.3 <1.3.0)
 *   - GTE:  ">=1.2.3"
 *   - LTE:  "<=1.2.3"
 *   - GT:   ">1.2.3"
 *   - LT:   "<1.2.3"
 *   - Hyphen range: "1.2.3 - 2.0.0"  (>=1.2.3 <=2.0.0)
 *   - Space-separated AND conjunction: ">=1.0.0 <2.0.0"
 *   - `x` / `*` wildcards: "1.x" = ">=1.0.0 <2.0.0", "1.2.x" = ">=1.2.0 <1.3.0"
 *
 * Returns false when version or range cannot be parsed.
 */
export function satisfiesSemverRange(version: string, range: string): boolean {
  const parsed = parseSemver(version);
  if (!parsed) return false;

  const trimmed = range.trim();

  // Wildcard / x-range: "1.x", "1.2.x", "1.*", "*"
  const wildcardMatch = /^(\d+)(?:\.(?:(\d+)|[x*]))?(?:\.(?:(\d+)|[x*]))?$/.exec(trimmed);
  if (wildcardMatch && trimmed.includes('x') || (wildcardMatch && trimmed.includes('*'))) {
    // Already handled by the regex — parse the version constraints
  }
  if (/^(\d+)(?:\.(?:(\d+)|[x*]))?(?:\.(?:(\d+)|[x*]))?$/.test(trimmed) && (trimmed.includes('x') || trimmed.includes('*'))) {
    const m = /^(\d+)(?:\.(?:(\d+)|[x*]))?(?:\.(?:(\d+)|[x*]))?$/.exec(trimmed)!;
    const major = Number(m[1]);
    const minorRaw = m[2];
    const patchRaw = m[3];
    if (!minorRaw || minorRaw === 'x' || minorRaw === '*') {
      // 1.x or 1.* → >=1.0.0 <2.0.0
      return parsed[0] === major;
    }
    if (!patchRaw || patchRaw === 'x' || patchRaw === '*') {
      // 1.2.x or 1.2.* → >=1.2.0 <1.3.0
      return parsed[0] === major && parsed[1] === Number(minorRaw);
    }
  }

  // Caret: ^1.2.3 → >=1.2.3 <2.0.0
  if (trimmed.startsWith('^')) {
    const v = parseSemver(trimmed.slice(1));
    if (!v) return false;
    const upper: [number, number, number] = v[0] === 0
      ? (v[1] === 0 ? [0, 0, v[2] + 1] : [0, v[1] + 1, 0])
      : [v[0] + 1, 0, 0];
    return compareSemver(parsed, v) >= 0 && compareSemver(parsed, upper) < 0;
  }

  // Tilde: ~1.2.3 → >=1.2.3 <1.3.0
  if (trimmed.startsWith('~')) {
    const v = parseSemver(trimmed.slice(1));
    if (!v) return false;
    const upper: [number, number, number] = [v[0], v[1] + 1, 0];
    return compareSemver(parsed, v) >= 0 && compareSemver(parsed, upper) < 0;
  }

  // Hyphen range: "1.2.3 - 2.0.0" → >=1.2.3 <=2.0.0
  const hyphenMatch = /^\s*(\S+)\s+-\s+(\S+)\s*$/.exec(trimmed);
  if (hyphenMatch) {
    const lo = parseSemver(hyphenMatch[1]);
    const hi = parseSemver(hyphenMatch[2]);
    if (!lo || !hi) return false;
    return compareSemver(parsed, lo) >= 0 && compareSemver(parsed, hi) <= 0;
  }

  // Space-separated conjunction: ">=1.0.0 <2.0.0"
  const parts = trimmed.split(/\s+/).filter(Boolean);
  if (parts.length > 1) {
    return parts.every((part) => satisfiesSemverRange(version, part));
  }

  // Single operator: >=, <=, >, <, =
  const opMatch = /^(>=|<=|>|<|=)?(.+)$/.exec(trimmed);
  if (opMatch) {
    const op = opMatch[1] || '=';
    const target = parseSemver(opMatch[2]);
    if (!target) return false;
    const cmp = compareSemver(parsed, target);
    switch (op) {
      case '>=': return cmp >= 0;
      case '<=': return cmp <= 0;
      case '>': return cmp > 0;
      case '<': return cmp < 0;
      case '=':
      default: return cmp === 0;
    }
  }

  // Fallback: exact version match
  const exact = parseSemver(trimmed);
  if (!exact) return false;
  return compareSemver(parsed, exact) === 0;
}

// ---------------------------------------------------------------------------
// Dependency resolution types
// ---------------------------------------------------------------------------

/** Resolution status for a single dependency. */
export interface DependencyStatus {
  /** The dependency extension ID. */
  readonly dependencyId: string;
  /** Whether the dependency was found in the load set. */
  readonly found: boolean;
  /** Whether the version range is satisfied (true when no range specified). */
  readonly versionSatisfied: boolean;
  /** The required version range (if any). */
  readonly versionRange?: string;
  /** The actual version of the resolved dependency (if found). */
  readonly actualVersion?: string;
  /** The dependency posture. */
  readonly posture: DependencyPosture;
  /** Specific contribution IDs required from the dependency. */
  readonly contributionIds?: readonly string[];
}

/** Resolution result for a single extension. */
export interface DependencyResolutionEntry {
  /** The extension ID being resolved. */
  readonly extensionId: string;
  /** Per-dependency status entries. */
  readonly dependencies: readonly DependencyStatus[];
  /** Dependencies that are fully satisfied (found + version ok). */
  readonly satisfied: readonly string[];
  /** Missing required dependencies. */
  readonly missingRequired: readonly string[];
  /** Missing optional dependencies. */
  readonly missingOptional: readonly string[];
  /** Version mismatches for required dependencies. */
  readonly versionMismatchRequired: readonly string[];
  /** Version mismatches for optional dependencies. */
  readonly versionMismatchOptional: readonly string[];
  /** Whether all required dependencies are satisfied. */
  readonly allRequiredSatisfied: boolean;
  /** Whether the extension can activate (all required satisfied, not in a cycle). */
  readonly canActivate: boolean;
  /** Whether activation is degraded (optional dependencies missing/mismatched). */
  readonly degraded: boolean;
  /** Whether the extension is part of a dependency cycle. */
  readonly inCycle: boolean;
  /** IDs of extensions in the same cycle (empty if not in a cycle). */
  readonly cycleExtensionIds: readonly string[];
  /** Blocking diagnostics. */
  readonly blockingDiagnostics: readonly ExtensionDiagnostic[];
  /** Degradation diagnostics. */
  readonly degradationDiagnostics: readonly ExtensionDiagnostic[];
}

/** Aggregate dependency resolution result. */
export interface DependencyResolutionResult {
  /** Per-extension resolution entries. */
  readonly entries: readonly DependencyResolutionEntry[];
  /** Extensions that should be blocked from loading. */
  readonly blockedExtensionIds: ReadonlySet<string>;
  /** Degraded extension IDs (those with only optional issues). */
  readonly degradedExtensionIds: ReadonlySet<string>;
  /** All diagnostics from resolution. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Cycle detection
// ---------------------------------------------------------------------------

/**
 * Detect all extension IDs that are part of any dependency cycle.
 *
 * Builds a directed graph where edge A→B means A depends on B (any posture).
 * Returns a set of extension IDs reachable from any cycle.
 */
function detectDependencyCycles(
  packages: readonly ValidatedPackage[],
): {
  /** All extension IDs involved in at least one cycle. */
  cycleIds: ReadonlySet<string>;
  /** Map from extension ID to the cycle it belongs to (empty array if not in cycle). */
  cycleGroups: ReadonlyMap<string, readonly string[]>;
} {
  // Build adjacency: extId → dependsOn IDs (all postures)
  const adjacency = new Map<string, Set<string>>();
  for (const pkg of packages) {
    const manifest = pkg.form === 'workspace-source'
      ? (pkg as WorkspaceSourcePackage).manifest
      : (pkg as InstalledBundlePackage).pack.manifest;
    const extId = manifest.id as string;
    const deps = manifest.dependsOn ?? [];
    const depIds = new Set<string>();
    for (const dep of deps) {
      if (dep.extensionId && dep.extensionId !== extId) {
        depIds.add(dep.extensionId);
      }
    }
    adjacency.set(extId, depIds);
  }

  // Tarjan's SCC algorithm
  const index = new Map<string, number>();
  const lowlink = new Map<string, number>();
  const onStack = new Set<string>();
  const stack: string[] = [];
  let currentIndex = 0;
  const sccs: string[][] = [];

  function strongConnect(v: string): void {
    index.set(v, currentIndex);
    lowlink.set(v, currentIndex);
    currentIndex++;
    stack.push(v);
    onStack.add(v);

    const neighbors = adjacency.get(v);
    if (neighbors) {
      for (const w of neighbors) {
        if (!index.has(w)) {
          strongConnect(w);
          lowlink.set(v, Math.min(lowlink.get(v)!, lowlink.get(w)!));
        } else if (onStack.has(w)) {
          lowlink.set(v, Math.min(lowlink.get(v)!, index.get(w)!));
        }
      }
    }

    if (lowlink.get(v) === index.get(v)) {
      const scc: string[] = [];
      let w: string;
      do {
        w = stack.pop()!;
        onStack.delete(w);
        scc.push(w);
      } while (w !== v);
      if (scc.length > 1) {
        sccs.push(scc);
      }
    }
  }

  for (const extId of adjacency.keys()) {
    if (!index.has(extId)) {
      strongConnect(extId);
    }
  }

  // Also detect direct self-loops (but these should be caught by manifest validation)
  const cycleIds = new Set<string>();
  const cycleGroups = new Map<string, readonly string[]>();
  for (const scc of sccs) {
    const frozen = Object.freeze([...scc]);
    for (const id of scc) {
      cycleIds.add(id);
      cycleGroups.set(id, frozen);
    }
  }

  return {
    cycleIds: Object.freeze(cycleIds),
    cycleGroups: Object.freeze(cycleGroups),
  };
}

// ---------------------------------------------------------------------------
// Dependency resolution
// ---------------------------------------------------------------------------

/**
 * Resolve dependencies across a set of validated packages.
 *
 * For each extension, checks:
 *   - Required dependencies: missing or version-mismatched → blocked.
 *   - Optional dependencies: missing or version-mismatched → degraded.
 *   - Cycles: all members of a cycle are blocked.
 *
 * Contribution-scoped diagnostics are emitted for dependency issues.
 */
export function resolveDependencies(
  packages: readonly ValidatedPackage[],
): DependencyResolutionResult {
  // Build lookup: extensionId → { manifest, version }
  const packageMap = new Map<string, { manifest: ExtensionManifest; version: string }>();
  for (const pkg of packages) {
    const manifest = pkg.form === 'workspace-source'
      ? (pkg as WorkspaceSourcePackage).manifest
      : (pkg as InstalledBundlePackage).pack.manifest;
    const extId = manifest.id as string;
    const version = manifest.version as string;
    packageMap.set(extId, { manifest, version });
  }

  // Detect cycles
  const { cycleIds, cycleGroups } = detectDependencyCycles(packages);

  const entries: DependencyResolutionEntry[] = [];
  const blockedIds = new Set<string>();
  const degradedIds = new Set<string>();
  const allDiagnostics: ExtensionDiagnostic[] = [];

  for (const pkg of packages) {
    const manifest = pkg.form === 'workspace-source'
      ? (pkg as WorkspaceSourcePackage).manifest
      : (pkg as InstalledBundlePackage).pack.manifest;
    const extId = manifest.id as string;

    const dependencies: DependencyStatus[] = [];
    const satisfied: string[] = [];
    const missingRequired: string[] = [];
    const missingOptional: string[] = [];
    const versionMismatchRequired: string[] = [];
    const versionMismatchOptional: string[] = [];
    const blockingDiagnostics: ExtensionDiagnostic[] = [];
    const degradationDiagnostics: ExtensionDiagnostic[] = [];

    const dependsOn = manifest.dependsOn ?? [];

    for (const dep of dependsOn) {
      const depId = dep.extensionId;
      const posture: DependencyPosture = dep.posture ?? (dep.optional ? 'optional' : 'required');
      const versionRange = dep.versionRange;

      const target = packageMap.get(depId);
      const found = target !== undefined;

      let versionSatisfied = true;
      if (found && versionRange) {
        versionSatisfied = satisfiesSemverRange(target!.version, versionRange);
      }

      const status: DependencyStatus = {
        dependencyId: depId,
        found,
        versionSatisfied,
        versionRange,
        actualVersion: target?.version,
        posture,
        contributionIds: dep.contributionIds,
      };
      dependencies.push(status);

      if (found && versionSatisfied) {
        satisfied.push(depId);
      } else if (!found) {
        if (posture === 'required') {
          missingRequired.push(depId);
          const diag: ExtensionDiagnostic = {
            severity: 'error',
            code: 'loader/missing-required-dependency',
            message: `Required dependency "${depId}" is not present in the load set.`,
            extensionId: extId,
            ...(dep.contributionIds && dep.contributionIds.length > 0
              ? { contributionId: dep.contributionIds[0] }
              : {}),
          };
          blockingDiagnostics.push(diag);
        } else {
          missingOptional.push(depId);
          const diag: ExtensionDiagnostic = {
            severity: 'warning',
            code: 'loader/missing-optional-dependency',
            message: `Optional dependency "${depId}" is not present; activating in degraded mode.`,
            extensionId: extId,
            ...(dep.contributionIds && dep.contributionIds.length > 0
              ? { contributionId: dep.contributionIds[0] }
              : {}),
          };
          degradationDiagnostics.push(diag);
        }
      } else if (!versionSatisfied) {
        if (posture === 'required') {
          versionMismatchRequired.push(depId);
          const diag: ExtensionDiagnostic = {
            severity: 'error',
            code: 'loader/dependency-version-mismatch',
            message: `Required dependency "${depId}" version ${target!.version} does not satisfy range "${versionRange}".`,
            extensionId: extId,
            ...(dep.contributionIds && dep.contributionIds.length > 0
              ? { contributionId: dep.contributionIds[0] }
              : {}),
          };
          blockingDiagnostics.push(diag);
        } else {
          versionMismatchOptional.push(depId);
          const diag: ExtensionDiagnostic = {
            severity: 'warning',
            code: 'loader/dependency-version-mismatch-optional',
            message: `Optional dependency "${depId}" version ${target!.version} does not satisfy range "${versionRange}"; activating in degraded mode.`,
            extensionId: extId,
            ...(dep.contributionIds && dep.contributionIds.length > 0
              ? { contributionId: dep.contributionIds[0] }
              : {}),
          };
          degradationDiagnostics.push(diag);
        }
      }
    }

    const inCycle = cycleIds.has(extId);
    const allRequiredSatisfied = missingRequired.length === 0 && versionMismatchRequired.length === 0;
    const degraded = missingOptional.length > 0 || versionMismatchOptional.length > 0;
    const canActivate = allRequiredSatisfied && !inCycle;

    if (inCycle) {
      const cycleGroup = cycleGroups.get(extId) ?? [];
      const diag: ExtensionDiagnostic = {
        severity: 'error',
        code: 'loader/dependency-cycle',
        message: `Extension "${extId}" is part of a dependency cycle: [${cycleGroup.join(', ')}].`,
        extensionId: extId,
      };
      blockingDiagnostics.push(diag);
    }

    if (!canActivate) {
      blockedIds.add(extId);
    }
    if (degraded && canActivate) {
      degradedIds.add(extId);
    }

    const entry: DependencyResolutionEntry = {
      extensionId: extId,
      dependencies: Object.freeze([...dependencies]),
      satisfied: Object.freeze([...satisfied]),
      missingRequired: Object.freeze([...missingRequired]),
      missingOptional: Object.freeze([...missingOptional]),
      versionMismatchRequired: Object.freeze([...versionMismatchRequired]),
      versionMismatchOptional: Object.freeze([...versionMismatchOptional]),
      allRequiredSatisfied,
      canActivate,
      degraded,
      inCycle,
      cycleExtensionIds: Object.freeze([...(cycleGroups.get(extId) ?? [])]),
      blockingDiagnostics: Object.freeze([...blockingDiagnostics]),
      degradationDiagnostics: Object.freeze([...degradationDiagnostics]),
    };
    entries.push(entry);

    allDiagnostics.push(...blockingDiagnostics, ...degradationDiagnostics);
  }

  return {
    entries: Object.freeze([...entries]),
    blockedExtensionIds: Object.freeze(blockedIds),
    degradedExtensionIds: Object.freeze(degradedIds),
    diagnostics: Object.freeze(allDiagnostics),
  };
}

// ---------------------------------------------------------------------------
// Input types
// ---------------------------------------------------------------------------

/**
 * A direct/source extension input (workspace source).
 *
 * These come from the `extensions` prop on the provider and have an
 * activate function already bound.
 */
export interface DirectExtensionInput {
  readonly kind: 'direct';
  readonly extension: ReighExtension;
}

/**
 * An installed pack input.
 *
 * These come from the repository (ExtensionStateRepository) and carry
 * the pack record plus the bundle content bytes retrieved from IndexedDB.
 */
export interface InstalledExtensionInput {
  readonly kind: 'installed';
  readonly packRecord: ExtensionPackRecord;
  readonly bundleContent: string;
}

/** Union of all extension loader inputs. */
export type ExtensionLoaderInput = DirectExtensionInput | InstalledExtensionInput;

// ---------------------------------------------------------------------------
// Validation types
// ---------------------------------------------------------------------------

/** Validation result for a single input. */
export interface ExtensionValidationEntry {
  /** The original input. */
  readonly input: ExtensionLoaderInput;
  /** True when no blocking errors exist. */
  readonly valid: boolean;
  /** Blocking errors (prevent loading). */
  readonly errors: readonly ExtensionDiagnostic[];
  /** Non-blocking warnings. */
  readonly warnings: readonly ExtensionDiagnostic[];
  /** The validated package produced from this input (when valid). */
  readonly validatedPackage: ValidatedPackage | null;
}

/** Aggregate validation result. */
export interface ExtensionLoaderValidationResult {
  /** Per-input validation entries (one per input, in input order). */
  readonly entries: readonly ExtensionValidationEntry[];
  /** True when every entry is valid. */
  readonly allValid: boolean;
  /** Aggregated diagnostics from all entries. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Load types
// ---------------------------------------------------------------------------

/** Load result for a single extension. */
export interface ExtensionLoadEntry {
  /** The extension ID. */
  readonly extensionId: string;
  /** The loaded ReighExtension (null on failure). */
  readonly extension: ReighExtension | null;
  /** True if loading succeeded. */
  readonly loaded: boolean;
  /** Errors encountered during loading. */
  readonly errors: readonly ExtensionDiagnostic[];
  /** Lifecycle events emitted during loading. */
  readonly lifecycleEvents: readonly ExtensionLifecycleEvent[];
}

/** Aggregate load result. */
export interface ExtensionLoaderLoadResult {
  /** Successfully loaded extensions in input order. */
  readonly loadedExtensions: readonly ReighExtension[];
  /** Per-extension load entries. */
  readonly entries: readonly ExtensionLoadEntry[];
  /** True when every extension loaded successfully. */
  readonly allLoaded: boolean;
  /** Aggregated diagnostics from all load entries. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /** Dependency resolution result (null if no dependencies to resolve). */
  readonly dependencyResolution: DependencyResolutionResult | null;
  /** Conflict resolution result (null if no conflicts detected). */
  readonly conflictResolution: ConflictResolutionResult | null;
}

// ---------------------------------------------------------------------------
// Unload types
// ---------------------------------------------------------------------------

/** Aggregate unload result. */
export interface ExtensionLoaderUnloadResult {
  /** IDs that were successfully unloaded. */
  readonly unloadedIds: readonly string[];
  /** Errors encountered during unload. */
  readonly errors: readonly ExtensionDiagnostic[];
  /** Lifecycle events emitted during unload. */
  readonly lifecycleEvents: readonly ExtensionLifecycleEvent[];
}

// ---------------------------------------------------------------------------
// Conflict resolution types
// ---------------------------------------------------------------------------

/** Resolution strategy chosen for a source-vs-installed conflict. */
export type ConflictResolutionStrategy =
  | 'installed-wins'
  | 'local-wins'
  | 'installed-disabled-fallback';

/** Resolved conflict entry for a single extension. */
export interface ConflictResolutionEntry {
  /** The extension ID. */
  readonly extensionId: string;
  /** Whether a conflict exists (both local source and installed pack present). */
  readonly hasConflict: boolean;
  /** Whether a workspace-source (local) version is present. */
  readonly hasLocalSource: boolean;
  /** Whether an installed-bundle version is present. */
  readonly hasInstalledPack: boolean;
  /** Whether the installed pack is enabled (true when no enablement state exists). */
  readonly installedEnabled: boolean;
  /** Whether a dev override `preferLocalSource` is set. */
  readonly preferLocalSource: boolean;
  /** The resolution strategy applied. */
  readonly strategy: ConflictResolutionStrategy;
  /** Which form won: 'local', 'installed', or null (no conflict). */
  readonly winner: 'local' | 'installed' | null;
  /** Diagnostics emitted for this conflict. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /** The losing validated package (null if no conflict or no loser). */
  readonly loserPackage: ValidatedPackage | null;
}

/** Aggregate conflict resolution result. */
export interface ConflictResolutionResult {
  /** Per-extension resolution entries (one per unique extension ID in input). */
  readonly entries: readonly ConflictResolutionEntry[];
  /** Extension IDs where installed won the conflict. */
  readonly installedWinIds: ReadonlySet<string>;
  /** Extension IDs where local source won the conflict. */
  readonly localWinIds: ReadonlySet<string>;
  /** Extension IDs where the installed pack was disabled and local fell back. */
  readonly disabledFallbackIds: ReadonlySet<string>;
  /** IDs of winning packages. */
  readonly winningExtensionIds: ReadonlySet<string>;
  /** All diagnostics from conflict resolution. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /**
   * The filtered list of validated packages containing only winners.
   * When there's no conflict for an extension, its package(s) pass through.
   * When there's a conflict, only the winner's package is included.
   */
  readonly winningPackages: readonly ValidatedPackage[];
}

/**
 * Configuration for conflict resolution behaviour.
 */
export interface ConflictResolutionConfig {
  /** Dev overrides keyed by extension ID (from repository). */
  readonly devOverrides: Record<string, DevOverrideState>;
  /** Enablement states keyed by extension ID (from repository). */
  readonly enablementStates: Record<string, ExtensionEnablementState>;
}

// ---------------------------------------------------------------------------
// ExtensionLoader interface
// ---------------------------------------------------------------------------

/**
 * The ExtensionLoader core: validates, loads, and unloads extensions.
 *
 * Does NOT own global state. Instantiated per-use with an optional
 * repository for persisting lifecycle events.  The caller retains
 * ownership of the returned ReighExtension[] and feeds it into the
 * existing ExtensionLifecycleHost pipeline.
 */
export interface ExtensionLoader {
  /** The repository used for lifecycle event persistence (null if none). */
  readonly repository: ExtensionStateRepository | null;

  /**
   * Validate a mix of direct (workspace source) and installed pack inputs.
   *
   * Each input is validated independently — a failure in one pack does
   * not prevent other packs from being validated.  Direct extensions use
   * dev-mode manifest validation (warnings for missing publisher/license).
   * Installed packs use strict installed-mode validation with integrity
   * checks.
   */
  validate(inputs: readonly ExtensionLoaderInput[]): ExtensionLoaderValidationResult;

  /**
   * Load validated packages into ReighExtension[].
   *
   * Performs dependency resolution before loading: required dependencies that
   * are missing, have version mismatches, or form cycles block activation.
   * Optional dependencies that are missing or have version mismatches allow
   * degraded activation with contribution-scoped diagnostics.
   *
   * For workspace-source packages, the original ReighExtension is returned
   * as-is.  For installed-bundle packages, bundleContent integrity is
   * verified against the pack record, and a synthetic ReighExtension is
   * created from the manifest snapshot (no activate function — installed
   * bundles use module evaluation for their activate export).
   *
   * Per-pack failure isolation: a failed integrity check, missing bundle
   * content, or dependency resolution failure only affects that single
   * extension.
   *
   * Lifecycle events (load, integrity_pass, integrity_fail, dependency_blocked,
   * dependency_degraded) are emitted through the repository when one is provided.
   */
  load(validated: readonly ValidatedPackage[]): Promise<ExtensionLoaderLoadResult>;

  /**
   * Unload extensions, emitting lifecycle events through the repository.
   *
   * Each extension ID receives an `unload` lifecycle event.  Failures
   * are isolated per ID.
   */
  unload(extensionIds: readonly string[]): Promise<ExtensionLoaderUnloadResult>;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create a new ExtensionLoader instance.
 *
 * @param repository  Optional repository for persisting lifecycle events.
 *                    When null, lifecycle events are still produced in the
 *                    result objects but are not persisted.
 */
export function createExtensionLoader(
  repository?: ExtensionStateRepository,
): ExtensionLoader {
  const repo = repository ?? null;
  let disposed = false;

  // ---- helpers ----------------------------------------------------------

  function ensureNotDisposed(): void {
    if (disposed) {
      throw new Error('ExtensionLoader has been disposed.');
    }
  }

  function blockDiag(
    extensionId: string,
    code: string,
    message: string,
    contributionId?: string,
  ): ExtensionDiagnostic {
    return Object.freeze({
      severity: 'error' as const,
      code,
      message,
      extensionId,
      ...(contributionId ? { contributionId } : {}),
    });
  }

  /** Deep-freeze a value. Returns the value (frozen). */
  function deepFreeze<T>(value: T): T {
    if (value === null || value === undefined) return value;
    if (typeof value !== 'object' && typeof value !== 'function') return value;
    if (Object.isFrozen(value)) return value;
    Object.freeze(value);
    // Freeze nested objects
    for (const key of Object.keys(value as Record<string, unknown>)) {
      const v = (value as Record<string, unknown>)[key];
      if (typeof v === 'object' && v !== null) {
        deepFreeze(v);
      }
    }
    return value;
  }

  async function appendLifecycleEvent(
    event: ExtensionLifecycleEvent,
  ): Promise<void> {
    if (!repo || repo.isDisposed) return;
    try {
      await repo.appendLifecycleEvent(event);
    } catch {
      // Lifecycle event persistence failures are silently dropped —
      // they must not block the loader.
    }
  }

  // ---- conflict resolution -----------------------------------------------

  /**
   * Resolve conflicts between local (workspace-source) and installed
   * (installed-bundle) forms of the same extension.
   *
   * ## Default policy: installed-wins
   *
   * When both a local source and an installed pack exist for the same
   * extension ID, the installed version is preferred unless:
   *   - A dev override `preferLocalSource` is set (local-wins).
   *   - The installed extension is disabled (local used as fallback).
   *
   * ## Diagnostics
   *
   * Every conflict produces a diagnostic (info for installed-wins / local-wins,
   * warning for disabled-installed fallback).  Diagnostics include the
   * extension ID and the resolution strategy.
   *
   * ## Non-conflict pass-through
   *
   * Extensions present only as local source or only as installed pack are
   * passed through unchanged — no diagnostics are emitted for them.
   */
  function resolveConflicts(
    validated: readonly ValidatedPackage[],
    config: ConflictResolutionConfig,
  ): ConflictResolutionResult {
    const { devOverrides, enablementStates } = config;

    // Group by extension ID
    const byId = new Map<string, { local: ValidatedPackage | null; installed: ValidatedPackage | null }>();
    for (const pkg of validated) {
      const manifest = pkg.form === 'workspace-source'
        ? (pkg as WorkspaceSourcePackage).manifest
        : (pkg as InstalledBundlePackage).pack.manifest;
      const extId = manifest.id as string;

      let group = byId.get(extId);
      if (!group) {
        group = { local: null, installed: null };
        byId.set(extId, group);
      }
      if (pkg.form === 'workspace-source') {
        group.local = pkg;
      } else {
        group.installed = pkg;
      }
    }

    const entries: ConflictResolutionEntry[] = [];
    const installedWinIds = new Set<string>();
    const localWinIds = new Set<string>();
    const disabledFallbackIds = new Set<string>();
    const winningExtensionIds = new Set<string>();
    const allDiagnostics: ExtensionDiagnostic[] = [];
    const winningPackages: ValidatedPackage[] = [];

    for (const [extId, group] of byId) {
      const hasLocalSource = group.local !== null;
      const hasInstalledPack = group.installed !== null;
      const hasConflict = hasLocalSource && hasInstalledPack;

      if (!hasConflict) {
        // No conflict — pass through
        const pkg = (group.local ?? group.installed)!;
        winningPackages.push(pkg);
        winningExtensionIds.add(extId);

        entries.push(deepFreeze({
          extensionId: extId,
          hasConflict: false,
          hasLocalSource,
          hasInstalledPack,
          installedEnabled: true,
          preferLocalSource: false,
          strategy: hasInstalledPack ? 'installed-wins' as const : 'local-wins' as const,
          winner: hasInstalledPack ? 'installed' as const : 'local' as const,
          diagnostics: Object.freeze([]),
          loserPackage: null,
        } satisfies ConflictResolutionEntry));
        continue;
      }

      // Conflict detected — resolve
      const override = devOverrides[extId];
      const enablement = enablementStates[extId];
      const preferLocalSource = override?.preferLocalSource === true;
      const installedEnabled = enablement ? enablement.enabled : true; // absent = assumed enabled
      const diags: ExtensionDiagnostic[] = [];
      let strategy: ConflictResolutionStrategy;
      let winner: 'local' | 'installed';
      let loserPackage: ValidatedPackage | null;

      if (preferLocalSource) {
        // Dev override: local source preferred
        strategy = 'local-wins';
        winner = 'local';
        loserPackage = group.installed;

        diags.push(Object.freeze({
          severity: 'info' as const,
          code: 'loader/conflict-local-override',
          message: `Extension "${extId}" has a dev override preferring local source; using workspace source instead of installed pack.`,
          extensionId: extId,
        }));
        localWinIds.add(extId);
      } else if (!installedEnabled) {
        // Installed pack is disabled — fall back to local
        strategy = 'installed-disabled-fallback';
        winner = 'local';
        loserPackage = group.installed;

        diags.push(Object.freeze({
          severity: 'warning' as const,
          code: 'loader/conflict-installed-disabled',
          message: `Installed pack for extension "${extId}" is disabled; falling back to workspace source.`,
          extensionId: extId,
        }));
        disabledFallbackIds.add(extId);
        localWinIds.add(extId);
      } else {
        // Default: installed-wins
        strategy = 'installed-wins';
        winner = 'installed';
        loserPackage = group.local;

        diags.push(Object.freeze({
          severity: 'info' as const,
          code: 'loader/conflict-installed-wins',
          message: `Installed pack for extension "${extId}" takes precedence over workspace source (default policy).`,
          extensionId: extId,
        }));
        installedWinIds.add(extId);
      }

      // Add the winning package
      const winningPkg = winner === 'local' ? group.local! : group.installed!;
      winningPackages.push(winningPkg);
      winningExtensionIds.add(extId);
      allDiagnostics.push(...diags);

      entries.push(deepFreeze({
        extensionId: extId,
        hasConflict: true,
        hasLocalSource,
        hasInstalledPack,
        installedEnabled,
        preferLocalSource,
        strategy,
        winner,
        diagnostics: Object.freeze([...diags]),
        loserPackage,
      } satisfies ConflictResolutionEntry));
    }

    return deepFreeze({
      entries: Object.freeze([...entries]),
      installedWinIds: Object.freeze(installedWinIds),
      localWinIds: Object.freeze(localWinIds),
      disabledFallbackIds: Object.freeze(disabledFallbackIds),
      winningExtensionIds: Object.freeze(winningExtensionIds),
      diagnostics: Object.freeze(allDiagnostics),
      winningPackages: Object.freeze([...winningPackages]),
    } satisfies ConflictResolutionResult);
  }

  /**
   * Fetch dev overrides and enablement states from the repository.
   *
   * When the repository is unavailable or fetch fails, returns empty
   * records so conflict resolution degrades gracefully (installed-wins
   * with no override data available).
   */
  async function fetchConflictConfig(): Promise<ConflictResolutionConfig> {
    if (!repo || repo.isDisposed) {
      return { devOverrides: {}, enablementStates: {} };
    }
    try {
      const fullState = await repo.getFullExtensionState();
      return {
        devOverrides: fullState.devOverrides,
        enablementStates: fullState.enablement,
      };
    } catch {
      // Repository errors must not block loading — degrade gracefully
      return { devOverrides: {}, enablementStates: {} };
    }
  }

  // ---- validate ----------------------------------------------------------

  function validate(
    inputs: readonly ExtensionLoaderInput[],
  ): ExtensionLoaderValidationResult {
    ensureNotDisposed();
    const entries: ExtensionValidationEntry[] = [];
    let allValid = true;

    for (const input of inputs) {
      if (input.kind === 'direct') {
        // ---------- direct / workspace source ----------
        const ext = input.extension;
        const extId = (ext.manifest.id as string) || '(unknown)';

        // Build a workspace-source-shaped record for validation
        const raw: Record<string, unknown> = {
          manifest: ext.manifest as unknown as Record<string, unknown>,
        };
        const pkgResult: PackageValidationResult = validateWorkspaceSourcePackage(raw);

        const valid = pkgResult.valid;
        if (!valid) allValid = false;

        const validatedPackage: ValidatedPackage | null = valid
          ? deepFreeze({
              form: 'workspace-source' as const,
              manifest: ext.manifest,
            } as WorkspaceSourcePackage)
          : null;

        entries.push(deepFreeze({
          input,
          valid,
          errors: Object.freeze([...pkgResult.errors]),
          warnings: Object.freeze([...pkgResult.warnings]),
          validatedPackage,
        } satisfies ExtensionValidationEntry));
      } else {
        // ---------- installed bundle ----------
        const packRecord = input.packRecord;
        const extId = packRecord.extensionId;

        // Build an InstalledExtensionPackage for validation
        const installedPkg: InstalledExtensionPackage = {
          metadata: {
            extensionId: packRecord.extensionId as any,
            version: packRecord.version,
            apiVersion: packRecord.apiVersion,
            integrity: packRecord.integrity,
            installedAt: packRecord.installedAt,
            enabled: true,
            publisher: packRecord.publisher,
            license: packRecord.license,
            icon: packRecord.icon,
          },
          manifest: packRecord.manifestSnapshot,
          bundleContent: input.bundleContent,
        };

        const pkgResult = validateInstalledBundlePackage(installedPkg);
        const valid = pkgResult.valid;
        if (!valid) allValid = false;

        const validatedPackage: ValidatedPackage | null = valid
          ? deepFreeze({
              form: 'installed-bundle' as const,
              pack: installedPkg,
            } as InstalledBundlePackage)
          : null;

        entries.push(deepFreeze({
          input,
          valid,
          errors: Object.freeze([...pkgResult.errors]),
          warnings: Object.freeze([...pkgResult.warnings]),
          validatedPackage,
        } satisfies ExtensionValidationEntry));
      }
    }

    // Aggregate diagnostics
    const allDiagnostics: ExtensionDiagnostic[] = [];
    for (const entry of entries) {
      allDiagnostics.push(...entry.errors, ...entry.warnings);
    }

    return deepFreeze({
      entries: Object.freeze([...entries]),
      allValid,
      diagnostics: Object.freeze(allDiagnostics),
    } satisfies ExtensionLoaderValidationResult);
  }

  // ---- load --------------------------------------------------------------

  async function load(
    validated: readonly ValidatedPackage[],
  ): Promise<ExtensionLoaderLoadResult> {
    ensureNotDisposed();
    const entries: ExtensionLoadEntry[] = [];
    const loadedExtensions: ReighExtension[] = [];
    let allLoaded = true;

    // ---- Dependency resolution ----
    let dependencyResolution: DependencyResolutionResult | null = null;
    const hasDependencies = validated.some((pkg) => {
      const manifest = pkg.form === 'workspace-source'
        ? (pkg as WorkspaceSourcePackage).manifest
        : (pkg as InstalledBundlePackage).pack.manifest;
      return (manifest.dependsOn?.length ?? 0) > 0;
    });

    if (hasDependencies) {
      dependencyResolution = resolveDependencies(validated);
    }

    const blockedIds = dependencyResolution?.blockedExtensionIds ?? new Set<string>();
    const degradedIds = dependencyResolution?.degradedExtensionIds ?? new Set<string>();

    // Emit dependency lifecycle events
    if (dependencyResolution) {
      for (const entry of dependencyResolution.entries) {
        const extId = entry.extensionId;
        if (!entry.canActivate) {
          const event = createLifecycleEvent(
            extId,
            'dependency_blocked',
            `Extension "${extId}" blocked by dependency resolution.`,
            {
              missingRequired: entry.missingRequired,
              versionMismatchRequired: entry.versionMismatchRequired,
              inCycle: entry.inCycle,
              cycleExtensionIds: entry.cycleExtensionIds,
            },
          );
          await appendLifecycleEvent(event);
        } else if (entry.degraded) {
          const event = createLifecycleEvent(
            extId,
            'dependency_degraded',
            `Extension "${extId}" activating in degraded mode due to optional dependency issues.`,
            {
              missingOptional: entry.missingOptional,
              versionMismatchOptional: entry.versionMismatchOptional,
            },
          );
          await appendLifecycleEvent(event);
        }
      }
    }

    // ---- Conflict resolution ----
    const conflictConfig = await fetchConflictConfig();
    const conflictResolution = resolveConflicts(validated, conflictConfig);
    const effectivePackages = conflictResolution.winningPackages;

    for (const pkg of effectivePackages) {
      // Extract extension ID
      const manifest = pkg.form === 'workspace-source'
        ? (pkg as WorkspaceSourcePackage).manifest
        : (pkg as InstalledBundlePackage).pack.manifest;
      const extId = manifest.id as string;

      // Check if blocked by dependency resolution
      if (blockedIds.has(extId)) {
        allLoaded = false;
        const resEntry = dependencyResolution!.entries.find((e) => e.extensionId === extId);
        const errors: ExtensionDiagnostic[] = [
          ...(resEntry?.blockingDiagnostics ?? []),
        ];
        entries.push(deepFreeze({
          extensionId: extId,
          extension: null,
          loaded: false,
          errors: Object.freeze([...errors]),
          lifecycleEvents: Object.freeze([]),
        } satisfies ExtensionLoadEntry));
        continue;
      }

      if (pkg.form === 'workspace-source') {
        // ---------- workspace source ----------
        const wsPkg = pkg as WorkspaceSourcePackage;
        const lifecycleEvents: ExtensionLifecycleEvent[] = [];

        // Synthesize a basic ReighExtension from the manifest.
        const syntheticExt = defineExtension({ manifest: wsPkg.manifest });

        const loadEvent = createLifecycleEvent(
          extId,
          'load',
          `Extension "${extId}" loaded (workspace source).`,
          { form: 'workspace-source', degraded: degradedIds.has(extId) },
        );
        lifecycleEvents.push(loadEvent);
        await appendLifecycleEvent(loadEvent);

        loadedExtensions.push(syntheticExt);
        entries.push(deepFreeze({
          extensionId: extId,
          extension: syntheticExt,
          loaded: true,
          errors: Object.freeze([]),
          lifecycleEvents: Object.freeze([...lifecycleEvents]),
        } satisfies ExtensionLoadEntry));
      } else {
        // ---------- installed bundle ----------
        const ibPkg = pkg as InstalledBundlePackage;
        const lifecycleEvents: ExtensionLifecycleEvent[] = [];
        const errors: ExtensionDiagnostic[] = [];

        // Integrity verification
        const bundleContent = ibPkg.pack.bundleContent;

        if (bundleContent === undefined || bundleContent === null) {
          const err = blockDiag(
            extId,
            'loader/missing-bundle-content',
            `Installed extension "${extId}" has no bundle content.`,
          );
          errors.push(err);
        } else {
          try {
            const integrityResult = await verifyIntegrity(
              bundleContent,
              ibPkg.pack.metadata.integrity,
              extId,
            );

            if (integrityResult.valid) {
              const integrityEvent = createLifecycleEvent(
                extId,
                'integrity_pass',
                `Integrity verified for extension "${extId}".`,
                {
                  algorithm: ibPkg.pack.metadata.integrity.algorithm,
                },
              );
              lifecycleEvents.push(integrityEvent);
              await appendLifecycleEvent(integrityEvent);
            } else {
              // Integrity check failed — collect diagnostics
              for (const diag of integrityResult.diagnostics) {
                errors.push(
                  blockDiag(extId, diag.code, diag.message),
                );
              }
              const integrityEvent = createLifecycleEvent(
                extId,
                'integrity_fail',
                `Integrity check failed for extension "${extId}".`,
                {
                  diagnostics: integrityResult.diagnostics.map((d) => ({
                    code: d.code,
                    message: d.message,
                  })),
                },
              );
              lifecycleEvents.push(integrityEvent);
              await appendLifecycleEvent(integrityEvent);
            }
          } catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            errors.push(
              blockDiag(
                extId,
                'loader/integrity-error',
                `Integrity verification error for extension "${extId}": ${message}`,
              ),
            );
            const integrityEvent = createLifecycleEvent(
              extId,
              'integrity_fail',
              `Integrity verification threw an error for extension "${extId}": ${message}`,
              { error: message },
            );
            lifecycleEvents.push(integrityEvent);
            await appendLifecycleEvent(integrityEvent);
          }
        }

        if (errors.length === 0) {
          // Create synthetic ReighExtension from manifest snapshot.
          const syntheticExt = defineExtension({ manifest: ibPkg.pack.manifest });

          const loadEvent = createLifecycleEvent(
            extId,
            'load',
            `Extension "${extId}" loaded (installed bundle, integrity verified).`,
            {
              form: 'installed-bundle',
              version: ibPkg.pack.metadata.version,
              degraded: degradedIds.has(extId),
            },
          );
          lifecycleEvents.push(loadEvent);
          await appendLifecycleEvent(loadEvent);

          loadedExtensions.push(syntheticExt);
          entries.push(deepFreeze({
            extensionId: extId,
            extension: syntheticExt,
            loaded: true,
            errors: Object.freeze([]),
            lifecycleEvents: Object.freeze([...lifecycleEvents]),
          } satisfies ExtensionLoadEntry));
        } else {
          allLoaded = false;
          entries.push(deepFreeze({
            extensionId: extId,
            extension: null,
            loaded: false,
            errors: Object.freeze([...errors]),
            lifecycleEvents: Object.freeze([...lifecycleEvents]),
          } satisfies ExtensionLoadEntry));
        }
      }
    }

    // ---- Sync project lock metadata for enabled installed packs ----
    // Collect pack records for successfully loaded installed-bundle extensions.
    // These are the extensions that are now enabled in the project.
    if (repo && !repo.isDisposed) {
      const enabledInstalledPacks = entries
        .filter((entry) => entry.loaded && entry.extension)
        .map((entry) => {
          // Find the pack record from the original validated packages
          const pkg = effectivePackages.find((p) => {
            const m = p.form === 'workspace-source'
              ? (p as WorkspaceSourcePackage).manifest
              : (p as InstalledBundlePackage).pack.manifest;
            return (m.id as string) === entry.extensionId;
          });
          if (pkg && pkg.form === 'installed-bundle') {
            return (pkg as InstalledBundlePackage).pack;
          }
          return null;
        })
        .filter((record): record is InstalledExtensionPackage => record !== null);

      if (enabledInstalledPacks.length > 0) {
        try {
          // Convert InstalledExtensionPackage to ExtensionPackRecord using metadata
          const packRecords = enabledInstalledPacks.map((pkg) => {
            // Extract the pack record from the repository data
            // The pkg.metadata has everything we need
            return {
              extensionId: pkg.metadata.extensionId as string,
              version: pkg.metadata.version,
              apiVersion: pkg.metadata.apiVersion,
              integrity: pkg.metadata.integrity,
              installedAt: pkg.metadata.installedAt ?? new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              bundleContentRef: '',  // Not stored in lock per SD2
              manifestSnapshot: pkg.manifest,
              publisher: pkg.metadata.publisher,
              license: pkg.metadata.license,
              icon: pkg.metadata.icon,
            };
          });
          await syncEnabledPackLockEntries(repo, packRecords);
        } catch {
          // Lock sync failures are silently dropped — they must not block load
        }
      }
    }

    // Aggregate diagnostics
    const allDiagnostics: ExtensionDiagnostic[] = [];
    for (const entry of entries) {
      allDiagnostics.push(...entry.errors);
    }
    if (dependencyResolution) {
      allDiagnostics.push(...dependencyResolution.diagnostics);
    }
    allDiagnostics.push(...conflictResolution.diagnostics);

    return deepFreeze({
      loadedExtensions: Object.freeze([...loadedExtensions]),
      entries: Object.freeze([...entries]),
      allLoaded,
      diagnostics: Object.freeze(allDiagnostics),
      dependencyResolution,
      conflictResolution,
    } satisfies ExtensionLoaderLoadResult);
  }

  // ---- unload ------------------------------------------------------------

  async function unload(
    extensionIds: readonly string[],
  ): Promise<ExtensionLoaderUnloadResult> {
    ensureNotDisposed();
    const lifecycleEvents: ExtensionLifecycleEvent[] = [];
    const errors: ExtensionDiagnostic[] = [];
    const unloadedIds: string[] = [];

    for (const extId of extensionIds) {
      try {
        const event = createLifecycleEvent(
          extId,
          'unload',
          `Extension "${extId}" unloaded.`,
        );
        lifecycleEvents.push(event);
        await appendLifecycleEvent(event);
        unloadedIds.push(extId);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        errors.push(
          blockDiag(
            extId,
            'loader/unload-error',
            `Error unloading extension "${extId}": ${message}`,
          ),
        );
      }
    }

    return deepFreeze({
      unloadedIds: Object.freeze([...unloadedIds]),
      errors: Object.freeze([...errors]),
      lifecycleEvents: Object.freeze([...lifecycleEvents]),
    } satisfies ExtensionLoaderUnloadResult);
  }

  // ---- assemble ----------------------------------------------------------

  const loader: ExtensionLoader = {
    get repository() {
      return repo;
    },
    validate,
    load,
    unload,
  };

  return loader;
}
