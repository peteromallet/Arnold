/**
 * Package manifest validation for extension loading and installation.
 *
 * Distinguishes two accepted package forms:
 *   1. Workspace source package: a local `reigh-extension.json` consumed as a
 *      `ReighExtension` object during development.
 *   2. Installed trusted bundle: an installed pack with `manifest.json` +
 *      `bundle.mjs` and integrity-tracked `InstalledExtensionMetadata`.
 *
 * Diagnostics produced by this module clearly separate:
 *   - Workspace source warnings (missing fields recommended for installation).
 *   - Installed-pack blockers (strict errors that prevent activation).
 */

import {
  validateManifest,
  validateInstalledPackage,
  validateExtensionId,
  validateContributionId,
} from '@reigh/editor-sdk';
import type {
  ExtensionManifest,
  ManifestValidationResult,
  ManifestValidationMode,
  InstalledExtensionPackage,
  ExtensionDiagnostic,
  IntegrityHash,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Package form discrimination
// ---------------------------------------------------------------------------

/** The two accepted package origins. */
export type PackageForm = 'workspace-source' | 'installed-bundle';

// ---------------------------------------------------------------------------
// Workspace source package
// ---------------------------------------------------------------------------

/**
 * A workspace source package: a local extension loaded from a
 * `reigh-extension.json` file during development.
 *
 * These are not installed and are not integrity-tracked. The only required
 * field is a `manifest` property, matching the shape accepted by
 * `defineExtension()`.
 */
export interface WorkspaceSourcePackage {
  readonly form: 'workspace-source';
  /** The manifest extracted from `reigh-extension.json`. */
  readonly manifest: ExtensionManifest;
  /** Informational: path to the source directory. */
  readonly sourcePath?: string;
}

// ---------------------------------------------------------------------------
// Installed bundle package
// ---------------------------------------------------------------------------

/**
 * An installed trusted bundle: a validated installed pack containing
 * `manifest.json` + `bundle.mjs` content plus integrity metadata.
 */
export interface InstalledBundlePackage {
  readonly form: 'installed-bundle';
  /** The full installed package. */
  readonly pack: InstalledExtensionPackage;
}

// ---------------------------------------------------------------------------
// Unified validated package
// ---------------------------------------------------------------------------

/** A package that has passed validation for its form. */
export type ValidatedPackage = WorkspaceSourcePackage | InstalledBundlePackage;

// ---------------------------------------------------------------------------
// Package validation result
// ---------------------------------------------------------------------------

/** Result of validating a package (either form). */
export interface PackageValidationResult {
  /** Derived package form. */
  readonly form: PackageForm;
  /** True when no blocking errors exist for this form. */
  readonly valid: boolean;
  /** Blocking diagnostics. */
  readonly errors: readonly ExtensionDiagnostic[];
  /** Non-blocking diagnostics. */
  readonly warnings: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Input discriminant helpers
// ---------------------------------------------------------------------------

/**
 * Heuristic: is `input` shaped like an installed extension package?
 *
 * Checks for the presence of both `metadata` (with `extensionId`) and
 * `manifest` properties.
 */
function isInstalledPackageShape(
  input: Record<string, unknown>,
): input is Record<string, unknown> & {
  metadata: Record<string, unknown>;
  manifest: Record<string, unknown>;
} {
  return (
    typeof input === 'object' &&
    input !== null &&
    typeof (input as any).metadata === 'object' &&
    (input as any).metadata !== null &&
    typeof (input as any).metadata.extensionId === 'string' &&
    typeof (input as any).manifest === 'object' &&
    (input as any).manifest !== null
  );
}

/**
 * Heuristic: is `input` shaped like a reigh-extension.json workspace source?
 *
 * Workspace source packages have a top-level `manifest` property without the
 * `metadata`/`bundleContent` fields of an installed pack.
 */
function isWorkspaceSourceShape(input: Record<string, unknown>): boolean {
  return (
    typeof input === 'object' &&
    input !== null &&
    typeof (input as any).manifest === 'object' &&
    (input as any).manifest !== null &&
    !isInstalledPackageShape(input)
  );
}

// ---------------------------------------------------------------------------
// Validation helpers
// ---------------------------------------------------------------------------

/**
 * Build a blocking error diagnostic for the given extension ID.
 */
function block(
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

/**
 * Build a non-blocking warning diagnostic for the given extension ID.
 */
function warn(
  extensionId: string,
  code: string,
  message: string,
  contributionId?: string,
): ExtensionDiagnostic {
  return Object.freeze({
    severity: 'warning' as const,
    code,
    message,
    extensionId,
    ...(contributionId ? { contributionId } : {}),
  });
}

/**
 * Build an info diagnostic for the given extension ID.
 */
function info(
  extensionId: string,
  code: string,
  message: string,
  contributionId?: string,
): ExtensionDiagnostic {
  return Object.freeze({
    severity: 'info' as const,
    code,
    message,
    extensionId,
    ...(contributionId ? { contributionId } : {}),
  });
}

// ---------------------------------------------------------------------------
// Workspace source package validation
// ---------------------------------------------------------------------------

/**
 * Validate a workspace source package (reigh-extension.json format).
 *
 * Workspace source packages use `validateManifest` in `'dev'` mode:
 * - Missing installed-only fields (publisher, license, settingsSchema) produce
 *   **warnings** rather than blocking errors.
 * - Only structural problems (invalid ID, missing version/label, invalid
 *   semver, duplicate contribution IDs) produce blocking errors.
 * - Manifest shape problems also produce errors.
 *
 * Returns a {@link PackageValidationResult} with `form: 'workspace-source'`.
 */
export function validateWorkspaceSourcePackage(
  raw: Record<string, unknown>,
  sourcePath?: string,
): PackageValidationResult {
  const errors: ExtensionDiagnostic[] = [];
  const warnings: ExtensionDiagnostic[] = [];

  // ---- Structural: must have a manifest property ----
  if (!raw.manifest || typeof raw.manifest !== 'object' || raw.manifest === null) {
    errors.push(
      block(
        '(unknown)',
        'package/workspace-missing-manifest',
        'Workspace source package must have a top-level "manifest" object',
      ),
    );
    return {
      form: 'workspace-source',
      valid: errors.length === 0,
      errors: Object.freeze([...errors]),
      warnings: Object.freeze([...warnings]),
    };
  }

  const manifest = raw.manifest as Record<string, unknown>;
  const extId = (typeof manifest.id === 'string' ? manifest.id : '(unknown)') as string;

  // ---- Validate extension ID format ----
  if (typeof manifest.id === 'string') {
    const idErrors = validateExtensionId(manifest.id as string);
    for (const msg of idErrors) {
      errors.push(block(extId, 'package/workspace-invalid-id', msg));
    }
  }

  // ---- Validate the manifest in dev mode ----
  const result = validateManifest(manifest as ExtensionManifest, 'dev');

  for (const err of result.errors) {
    errors.push(err);
  }
  for (const warnDiag of result.warnings) {
    warnings.push(warnDiag);
  }

  // ---- Additional workspace-source-specific checks ----

  // Warn if the workspace source package has top-level keys beyond 'manifest'
  // (e.g. legacy wrapper formats). This is advisory only.
  const knownKeys = new Set(['manifest']);
  for (const key of Object.keys(raw)) {
    if (!knownKeys.has(key)) {
      warnings.push(
        warn(
          extId,
          'package/workspace-extra-key',
          `Unexpected top-level key "${key}" in workspace source package; only "manifest" is used`,
        ),
      );
    }
  }

  // Source path informational
  if (sourcePath) {
    // Source path is informational — no diagnostic needed
  }

  return {
    form: 'workspace-source',
    valid: errors.length === 0,
    errors: Object.freeze([...errors]),
    warnings: Object.freeze([...warnings]),
  };
}

// ---------------------------------------------------------------------------
// Installed bundle package validation
// ---------------------------------------------------------------------------

/**
 * Validate an installed bundle package (manifest.json + bundle.mjs + metadata).
 *
 * Uses {@link validateInstalledPackage} from the SDK which runs
 * {@link validateManifest} in `'installed'` mode:
 * - Missing publisher, license, or integrity produce **blocking errors**.
 * - Missing settingsSchema produces a warning but does not block.
 * - Structural, version, dependency, and contribution ID uniqueness checks are
 *   always enforced as blocking errors.
 *
 * Also validates the `InstalledExtensionPackage` structure itself: metadata,
 * manifest, and bundleContent must all be present.
 *
 * Returns a {@link PackageValidationResult} with `form: 'installed-bundle'`.
 */
export function validateInstalledBundlePackage(
  pack: InstalledExtensionPackage,
): PackageValidationResult {
  const result = validateInstalledPackage(pack);

  return {
    form: 'installed-bundle',
    valid: result.valid,
    errors: result.errors,
    warnings: result.warnings,
  };
}

// ---------------------------------------------------------------------------
// Unified validatePackage
// ---------------------------------------------------------------------------

/**
 * Validate any package input, auto-detecting the form.
 *
 * - If the input has both `metadata` and `manifest` properties, it is treated
 *   as an installed bundle and validated with {@link validateInstalledBundlePackage}.
 * - If the input has a `manifest` property but no `metadata`, it is treated as
 *   a workspace source and validated with {@link validateWorkspaceSourcePackage}.
 * - Otherwise it is rejected as an unrecognised package shape.
 *
 * @param input A raw record that may be a workspace source or installed bundle.
 * @param sourcePath Optional source path for workspace source diagnostics.
 */
export function validatePackage(
  input: Record<string, unknown>,
  sourcePath?: string,
): PackageValidationResult {
  if (isInstalledPackageShape(input)) {
    // Treat as installed bundle
    return validateInstalledBundlePackage(input as unknown as InstalledExtensionPackage);
  }

  if (isWorkspaceSourceShape(input)) {
    // Treat as workspace source
    return validateWorkspaceSourcePackage(input, sourcePath);
  }

  // Unrecognised shape
  return {
    form: 'workspace-source', // default guess
    valid: false,
    errors: Object.freeze([
      block(
        '(unknown)',
        'package/unrecognised-shape',
        'Package input is neither a workspace source (reigh-extension.json) nor an installed bundle (metadata + manifest + bundleContent)',
      ),
    ]),
    warnings: Object.freeze([]),
  };
}

// ---------------------------------------------------------------------------
// Diagnostic classification helpers
// ---------------------------------------------------------------------------

/** Diagnostic codes that always block activation regardless of package form. */
const UNIVERSAL_BLOCK_CODES = new Set([
  'manifest/invalid-id',
  'manifest/missing-version',
  'manifest/invalid-version',
  'manifest/missing-label',
  'manifest/invalid-api-version',
  'manifest/invalid-contribution-id',
  'manifest/duplicate-contribution-id',
  'manifest/invalid-dependency-id',
  'manifest/self-dependency',
  'manifest/invalid-dependency-posture',
  'manifest/invalid-settings-schema-version',
  'manifest/invalid-migration-kind',
  'manifest/invalid-migration-from-version',
  'manifest/invalid-migration-to-version',
  'manifest/legacy-migration-shape', // only blocks in installed mode
  'package/missing-metadata',
  'package/missing-manifest',
  'package/missing-bundle',
  'package/id-mismatch',
  'package/version-mismatch',
  'package/missing-integrity',
  'package/invalid-integrity-algorithm',
  'package/missing-integrity-value',
  'package/invalid-enabled',
  'package/workspace-missing-manifest',
  'package/workspace-invalid-id',
  'package/unrecognised-shape',
]);

/** Diagnostic codes that only block in installed mode. */
const INSTALLED_ONLY_BLOCK_CODES = new Set([
  'manifest/installed-missing-publisher',
  'manifest/installed-missing-license',
  'manifest/installed-invalid-integrity-algorithm',
  'manifest/installed-missing-integrity-value',
]);

/** Diagnostic codes that are warnings in dev mode but errors in installed mode. */
const DEV_WARNING_INSTALLED_ERROR_CODES = new Set([
  'manifest/legacy-migration-shape', // warning in dev, error in installed
]);

/**
 * Return true if the diagnostic should block activation or installation.
 *
 * Blockers are always `severity: 'error'` diagnostics whose code signals a
 * hard requirement violation. Warnings and info diagnostics never block.
 */
export function isBlockingDiagnostic(diag: ExtensionDiagnostic): boolean {
  if (diag.severity !== 'error') return false;
  return UNIVERSAL_BLOCK_CODES.has(diag.code) || INSTALLED_ONLY_BLOCK_CODES.has(diag.code);
}

/**
 * Return true if the diagnostic is a workspace-source-only warning.
 *
 * These are diagnostics that appear as warnings in dev mode but become
 * blocking errors in installed mode. They signal that the package is missing
 * fields required for installation.
 */
export function isWorkspaceSourceWarning(diag: ExtensionDiagnostic): boolean {
  return (
    diag.severity === 'warning' &&
    (diag.code === 'manifest/dev-missing-publisher' ||
      diag.code === 'manifest/dev-missing-license' ||
      diag.code === 'manifest/dev-missing-settings-schema')
  );
}

/**
 * Return true if the diagnostic is an installed-pack blocker.
 *
 * These diagnostics only appear as blocking errors when validating in
 * `'installed'` mode and prevent installation or activation of an installed
 * bundle.
 */
export function isInstalledPackBlocker(diag: ExtensionDiagnostic): boolean {
  return diag.severity === 'error' && INSTALLED_ONLY_BLOCK_CODES.has(diag.code);
}

/**
 * Return true if the diagnostic is a contribution-ID uniqueness violation.
 */
export function isContributionIdDuplicate(diag: ExtensionDiagnostic): boolean {
  return diag.code === 'manifest/duplicate-contribution-id';
}

// ---------------------------------------------------------------------------
// Package form detection (standalone)
// ---------------------------------------------------------------------------

/**
 * Detect the package form from a raw input without full validation.
 *
 * Returns the detected form or `null` if the shape is unrecognised.
 */
export function detectPackageForm(
  input: Record<string, unknown>,
): PackageForm | null {
  if (isInstalledPackageShape(input)) return 'installed-bundle';
  if (isWorkspaceSourceShape(input)) return 'workspace-source';
  return null;
}
