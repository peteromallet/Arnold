/**
 * Core manifest contracts for the Reigh Editor SDK.
 *
 * Stable public types and constants for extension manifest declarations,
 * contribution contracts, slot definitions, placement rules, manifest
 * validation, package validation, and the canonical ExtensionManifest type.
 *
 * @publicContract
 */

import type { ExtensionId, ContributionId } from './ids';
import { validateExtensionId, validateContributionId } from './ids';
import type { VideoContributionKind } from '@/sdk/video/families/contributionKinds';
import {
  VIDEO_CONTRIBUTION_KINDS,
  VIDEO_CONTRIBUTION_KINDS_SET,
} from '@/sdk/video/families/contributionKinds';
import type { ExtensionDiagnostic } from './diagnostics';
import type { IntegrityHash, InstalledExtensionMetadata, ExtensionDependency, MigrationDeclaration } from './packaging';
import type { ExtensionSettingsSchema } from './settings';
import type { ProcessManifestEntry } from './video/families/processes';

// M2b family contribution types (used in ExtensionManifest union)
import type { CommandContribution } from './video/families/commands';
import type { KeybindingContribution } from './video/families/keybindings';
import type { ContextMenuItemContribution } from './video/families/contextMenuItems';
import type { ParserContribution } from './video/families/parsers';
import type { OutputFormatContribution } from './video/families/outputFormats';
import type { SearchProviderContribution } from './video/families/searchProviders';
import type { MetadataFacetContribution } from './video/families/metadataFacet';
import type { AssetDetailSectionContribution } from './video/families/assetDetailSections';
import type { ProcessContribution } from './video/families/processes';
import type { EffectContribution } from './video/families/effects';
import type { TransitionContribution } from './video/families/transitions';
import type { ClipTypeContribution } from './video/families/clipTypeContributions';
import type { ShaderContribution } from './video/families/shaders';
import type { AgentToolContribution } from './video/families/agentTools';

// ---------------------------------------------------------------------------
// Contribution kind and slot name contracts
// ---------------------------------------------------------------------------

/**
 * Known contribution kinds. Reserved/inactive kinds are validated but not bridged.
 *
 * Alias of {@link VideoContributionKind} from `src/sdk/video/families/contributionKinds.ts`,
 * which is the single source of truth for the kind union.
 */
export type ContributionKind = VideoContributionKind;

/** Slot names the host shell recognizes. */
export type VideoEditorSlotName =
  | 'header'
  | 'toolbar'
  | 'leftPanel'
  | 'rightPanel'
  | 'codePanel'
  | 'writingPanel'
  | 'stagePanel'
  | 'timelineFooter'
  | 'statusBar'
  | 'dialogs'
  | 'assetPanel'
  | 'inspectorPanel';

/** A single contribution declaration inside an extension manifest. */
export interface ExtensionContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: ContributionKind;
  /** Lower values sort first. Default 0. */
  order?: number;
  /** Slot name — required when kind === 'slot'. */
  slot?: VideoEditorSlotName;
  /** Dialog layer when kind === 'dialog'. */
  layer?: 'modal' | 'overlay';
  /** Inspector placement when kind === 'inspectorSection'. */
  placement?: 'before-default' | 'after-default';
  /** Human-readable label for diagnostics / UI. */
  label?: string;
  /** Optional visibility predicate (evaluated by host). */
  when?: string;
  /** Reserved for future render provider descriptors. */
  render?: string;
  /** Reserved for future effect descriptors. */
  effectId?: string;
  /** Reserved for future transition descriptors. */
  transitionId?: string;
  /** Reserved for future clip-type descriptors. */
  clipTypeId?: string;
  /** M13: Shader identifier declared by the extension. */
  shaderId?: string;
  /** M6: Parser identifier declared by the extension. */
  parserId?: string;
  /** M6: Output format identifier declared by the extension. */
  outputFormatId?: string;
  /** M6: Search provider identifier declared by the extension. */
  searchProviderId?: string;
  /** M6: Metadata facet identifier declared by the extension. */
  metadataFacetId?: string;
  /** M6: Asset detail section identifier declared by the extension. */
  assetDetailSectionId?: string;
  /** M10: Agent tool identifier declared by the extension. */
  agentToolId?: string;
}

// ---------------------------------------------------------------------------
// Runtime-inspectable contract constants
// ---------------------------------------------------------------------------

/**
 * All known contribution kinds as a runtime-inspectable readonly array.
 * Use this to enumerate valid kinds at runtime without relying on the
 * TypeScript type system alone.
 *
 * Re-export of {@link VIDEO_CONTRIBUTION_KINDS} from
 * `src/sdk/video/families/contributionKinds.ts`.
 */
export const KNOWN_CONTRIBUTION_KINDS: readonly ContributionKind[] = VIDEO_CONTRIBUTION_KINDS;

/** Set form of {@link KNOWN_CONTRIBUTION_KINDS} for fast lookups. */
export const KNOWN_CONTRIBUTION_KINDS_SET = VIDEO_CONTRIBUTION_KINDS_SET;

/**
 * All known slot names as a runtime-inspectable readonly array.
 */
export const KNOWN_SLOT_NAMES: readonly VideoEditorSlotName[] = [
  'header',
  'toolbar',
  'leftPanel',
  'rightPanel',
  'codePanel',
  'writingPanel',
  'stagePanel',
  'timelineFooter',
  'statusBar',
  'dialogs',
  'assetPanel',
  'inspectorPanel',
] as const;

/** Set form of {@link KNOWN_SLOT_NAMES} for fast lookups. */
export const KNOWN_SLOT_NAMES_SET: ReadonlySet<string> = new Set(KNOWN_SLOT_NAMES);

// ---- Placement value constants ----

/** Valid placement values for inspectorSection contributions. */
export const INSPECTOR_SECTION_PLACEMENTS: readonly string[] = [
  'before-default',
  'after-default',
] as const;

/** Valid placement values for panel contributions. */
export const PANEL_PLACEMENTS: readonly string[] = [
  'asset-panel',
] as const;

/** Valid placement values for assetDetailSection contributions. */
export const ASSET_DETAIL_SECTION_PLACEMENTS: readonly string[] = [
  'before-default',
  'after-default',
] as const;

/** Union of all valid placement values across contribution kinds. */
export const ALL_VALID_PLACEMENTS: readonly string[] = [
  'before-default',
  'after-default',
  'asset-panel',
] as const;

// ---------------------------------------------------------------------------
// Manifest validation contracts
// ---------------------------------------------------------------------------

/** Validation mode: 'dev' produces warnings, 'installed' produces strict errors. */
export type ManifestValidationMode = 'dev' | 'installed';

/** Result of validating an extension manifest. */
export interface ManifestValidationResult {
  /** True when no blocking errors exist. */
  valid: boolean;
  /** Blocking diagnostics (strict errors in installed mode). */
  errors: readonly ExtensionDiagnostic[];
  /** Non-blocking diagnostics (warnings in dev mode, supplemental in installed mode). */
  warnings: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Access disclosures (declarative only until sandboxing exists)
// ---------------------------------------------------------------------------

export interface ExtensionPermissionDeclaration {
  /** Human-readable reason for the declared access. */
  reason: string;
  /** Declared posture: what the extension states it accesses. */
  posture?: {
    network?: boolean;
    filesystem?: boolean;
    env?: boolean;
    processes?: boolean;
  };
}

// ---------------------------------------------------------------------------
// Extension manifest
// ---------------------------------------------------------------------------

export interface ExtensionManifest {
  id: ExtensionId;
  /** Semver string, e.g. "1.0.0". */
  version: string;
  label: string;
  description?: string;
  /** API version this extension targets (currently 1). */
  apiVersion?: number;
  /** Contribution declarations. */
  contributions?: readonly (
    | ExtensionContribution
    | CommandContribution
    | KeybindingContribution
    | ContextMenuItemContribution
    // M6: parser, output format, search provider, metadata facet, asset detail section
    | ParserContribution
    | OutputFormatContribution
    | SearchProviderContribution
    | MetadataFacetContribution
    | AssetDetailSectionContribution
    // M12: trusted local processes
    | ProcessContribution
    // M7: trusted component effects
    | EffectContribution
    // M8: trusted component transitions
    | TransitionContribution
    // M9: contributed clip types
    | ClipTypeContribution
    // M13: shader/WebGL contributions
    | ShaderContribution
    // M10: agent tool contributions
    | AgentToolContribution
  )[];
  /** Declarative access disclosures; not runtime-enforced in V1. */
  permissions?: readonly ExtensionPermissionDeclaration[];
  /** Process declarations. */
  processes?: readonly ProcessManifestEntry[];
  /** Typed migration hooks (preferred); legacy Record<string, unknown>[] accepted. */
  migrations?: readonly (MigrationDeclaration | Record<string, unknown>)[];
  /** Human-readable comments. */
  comments?: string;
  /** Typed dependency declarations. */
  dependsOn?: readonly ExtensionDependency[];
  /** Renderability descriptors. */
  renderability?: Record<string, unknown>;
  /** Extension-scoped settings defaults applied when no stored value exists. */
  settingsDefaults?: Record<string, unknown>;
  /** Settings schema with version for migration tracking. */
  settingsSchema?: ExtensionSettingsSchema;
  /** Bundled i18n messages keyed by locale-neutral key. */
  messages?: Record<string, string>;
  /** Publisher identity (required for installed extensions). */
  publisher?: string;
  /** SPDX license identifier (recommended for installed extensions). */
  license?: string;
  /** Icon URL or data URI. */
  icon?: string;
}

// ---------------------------------------------------------------------------
// Installed extension package
// ---------------------------------------------------------------------------

/** A full installed extension package: manifest + bundle + tracked metadata. */
export interface InstalledExtensionPackage {
  metadata: InstalledExtensionMetadata;
  manifest: ExtensionManifest;
  /** Raw trusted bundle source (bundle.mjs content). */
  bundleContent: string;
}

// ---------------------------------------------------------------------------
// Manifest validation
// ---------------------------------------------------------------------------

/**
 * Validate an extension manifest against the expected contract.
 *
 * In 'dev' mode, missing installed-only fields emit warnings.
 * In 'installed' mode, missing required installed metadata fields
 * (integrity, publisher, license) emit blocking errors.
 *
 * Contribution ID uniqueness, ID format, version format, and
 * dependency posture are validated in both modes.
 */
export function validateManifest(
  manifest: ExtensionManifest,
  _mode?: ManifestValidationMode,
): ManifestValidationResult {
  const errors: ExtensionDiagnostic[] = [];
  const warnings: ExtensionDiagnostic[] = [];
  const mode: ManifestValidationMode = _mode ?? 'dev';

  const extId = manifest.id as string;

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  const isValidSemver = (v: string): boolean => /^\d+\.\d+\.\d+/.test(v);

  /** Basic semver-range check: accepts npm-style range strings. */
  const isValidSemverRange = (range: string): boolean => {
    // Accept common patterns: ^x.y.z, ~x.y.z, >=x.y.z, x.y.z - y.z.w, x, x.y
    return /^(\*|[\^~><=]*(?:\d+|\*|x)(?:\.(?:\d+|\*|x))?(?:\.(?:\d+|\*|x))?)(\s+(?:-?\s*)?[\^~><=]*(?:\d+|\*|x)(?:\.(?:\d+|\*|x))?(?:\.(?:\d+|\*|x))?)*(\s+\|\|\s+[\^~><=]*(?:\d+|\*|x)(?:\.(?:\d+|\*|x))?(?:\.(?:\d+|\*|x))?)*\s*$/.test(range.trim());
  };

  const pushErr = (code: string, message: string, contributionId?: string): void => {
    errors.push({
      severity: 'error',
      code,
      message,
      extensionId: extId,
      ...(contributionId ? { contributionId } : {}),
    });
  };

  const pushWarn = (code: string, message: string, contributionId?: string): void => {
    warnings.push({
      severity: 'warning',
      code,
      message,
      extensionId: extId,
      ...(contributionId ? { contributionId } : {}),
    });
  };

  // -----------------------------------------------------------------------
  // ID validation
  // -----------------------------------------------------------------------
  const idErrors = validateExtensionId(extId);
  for (const msg of idErrors) {
    pushErr('manifest/invalid-id', msg);
  }

  // -----------------------------------------------------------------------
  // Version validation
  // -----------------------------------------------------------------------
  if (!manifest.version || typeof manifest.version !== 'string') {
    pushErr('manifest/missing-version', 'Manifest must include a semver version string');
  } else if (!isValidSemver(manifest.version)) {
    pushErr('manifest/invalid-version', `Version "${manifest.version}" does not match semver format`);
  }

  // -----------------------------------------------------------------------
  // Label validation
  // -----------------------------------------------------------------------
  if (!manifest.label || typeof manifest.label !== 'string' || manifest.label.trim().length === 0) {
    pushErr('manifest/missing-label', 'Manifest must include a non-empty label');
  }

  // -----------------------------------------------------------------------
  // API version validation
  // -----------------------------------------------------------------------
  if (manifest.apiVersion !== undefined) {
    if (typeof manifest.apiVersion !== 'number' || !Number.isInteger(manifest.apiVersion) || manifest.apiVersion < 1) {
      pushErr('manifest/invalid-api-version', `apiVersion must be a positive integer, got ${manifest.apiVersion}`);
    }
  }

  // -----------------------------------------------------------------------
  // Contribution validation (ID uniqueness, kind, placement rules)
  // -----------------------------------------------------------------------
  if (manifest.contributions && manifest.contributions.length > 0) {
    const seen = new Set<string>();
    for (const contribution of manifest.contributions) {
      const cId = (contribution as unknown as Record<string, unknown>).id as string;
      const cErrors = validateContributionId(cId);
      for (const msg of cErrors) {
        pushErr('manifest/invalid-contribution-id', `Contribution "${cId}": ${msg}`, cId);
      }

      // ---- Contribution kind validation (extract early for scoped duplicate detection) ----
      const cKind = (contribution as unknown as Record<string, unknown>).kind as string | undefined;
      if (!cKind || typeof cKind !== 'string') {
        pushErr('manifest/missing-contribution-kind', `Contribution "${cId}" is missing a kind`, cId);
        // Duplicate detection for kindless entries still uses bare ID
        if (seen.has(cId)) {
          pushErr('manifest/duplicate-contribution-id', `Duplicate contribution ID "${cId}"`, cId);
        }
        seen.add(cId);
        continue; // cannot validate kind-specific rules without a kind
      }

      // Duplicate detection uses scoped key (kind:contributionId) — cross-kind
      // reuse of the same bare contributionId is valid (SD3).
      const scopedKey = `${cKind}:${cId}`;
      if (seen.has(scopedKey)) {
        pushErr('manifest/duplicate-contribution-id', `Duplicate contribution ID "${cId}" for kind "${cKind}"`, cId);
      }
      seen.add(scopedKey);
      if (!KNOWN_CONTRIBUTION_KINDS_SET.has(cKind)) {
        pushErr(
          'manifest/unknown-contribution-kind',
          `Contribution "${cId}" has unknown kind "${cKind}"; must be one of: ${KNOWN_CONTRIBUTION_KINDS.join(', ')}`,
          cId,
        );
        continue; // unknown kind — skip kind-specific placement rules
      }

      // ---- Kind-specific placement rules ----

      // Slot: must not specify placement
      if (cKind === 'slot') {
        const cPlacement = (contribution as unknown as Record<string, unknown>).placement;
        if (cPlacement !== undefined && cPlacement !== null) {
          pushErr(
            'manifest/slot-no-placement',
            `Slot contribution "${cId}" must not specify placement`,
            cId,
          );
        }
        // Validate slot name if present
        const cSlot = (contribution as unknown as Record<string, unknown>).slot;
        if (typeof cSlot === 'string' && !KNOWN_SLOT_NAMES_SET.has(cSlot)) {
          pushErr(
            'manifest/unknown-slot-name',
            `Slot contribution "${cId}" has unknown slot name "${cSlot}"; must be one of: ${KNOWN_SLOT_NAMES.join(', ')}`,
            cId,
          );
        }
      }

      // Panel: placement must be 'asset-panel' when specified
      if (cKind === 'panel') {
        const cPlacement = (contribution as unknown as Record<string, unknown>).placement as string | undefined;
        if (cPlacement !== undefined && cPlacement !== null) {
          if (!PANEL_PLACEMENTS.includes(cPlacement)) {
            pushErr(
              'manifest/invalid-panel-placement',
              `Panel contribution "${cId}" placement must be "asset-panel", got "${cPlacement}"`,
              cId,
            );
          }
        }
      }

      // InspectorSection: validate placement when present; host applies defaults
      if (cKind === 'inspectorSection') {
        const cPlacement = (contribution as unknown as Record<string, unknown>).placement as string | undefined;
        if (cPlacement !== undefined && cPlacement !== null) {
          if (!INSPECTOR_SECTION_PLACEMENTS.includes(cPlacement)) {
            pushErr(
              'manifest/invalid-inspector-placement',
              `InspectorSection contribution "${cId}" placement must be one of: ${INSPECTOR_SECTION_PLACEMENTS.join(', ')}, got "${cPlacement}"`,
              cId,
            );
          }
        }
      }

      // AssetDetailSection: title and placement are required
      if (cKind === 'assetDetailSection') {
        const adsContribution = contribution as { id: string; title?: unknown; placement?: unknown };
        if (!adsContribution.title || typeof adsContribution.title !== 'string' || adsContribution.title.trim().length === 0) {
          pushErr(
            'manifest/missing-asset-detail-title',
            `AssetDetailSection contribution "${cId}" must include a non-empty title`,
            cId,
          );
        }
        if (!adsContribution.placement || typeof adsContribution.placement !== 'string' || !ASSET_DETAIL_SECTION_PLACEMENTS.includes(adsContribution.placement)) {
          pushErr(
            'manifest/invalid-asset-detail-placement',
            `AssetDetailSection contribution "${cId}" must specify placement as one of: ${ASSET_DETAIL_SECTION_PLACEMENTS.join(', ')}, got "${String(adsContribution.placement ?? 'undefined')}"`,
            cId,
          );
        }
      }
    }
  }

  // -----------------------------------------------------------------------
  // Dependency validation
  // -----------------------------------------------------------------------
  if (manifest.dependsOn && manifest.dependsOn.length > 0) {
    for (const dep of manifest.dependsOn) {
      // Dependency ID validation
      const depIdErrors = validateExtensionId(dep.extensionId);
      for (const msg of depIdErrors) {
        pushErr('manifest/invalid-dependency-id', `Dependency "${dep.extensionId}": ${msg}`);
      }

      // Self-dependency check
      if (dep.extensionId === extId) {
        pushErr('manifest/self-dependency', `Extension "${extId}" declares a dependency on itself`);
      }

      // Posture validation
      if (dep.posture !== undefined && dep.posture !== 'required' && dep.posture !== 'optional') {
        pushErr(
          'manifest/invalid-dependency-posture',
          `Dependency "${dep.extensionId}" has invalid posture "${dep.posture}"; must be "required" or "optional"`,
        );
      }

      // optional vs posture consistency
      if (dep.optional === true && dep.posture === 'required') {
        pushWarn(
          'manifest/dependency-posture-mismatch',
          `Dependency "${dep.extensionId}" is marked optional=true but posture is "required"; posture takes precedence`,
        );
      }

      // Version range validation
      if (dep.versionRange !== undefined && typeof dep.versionRange === 'string' && dep.versionRange.length > 0) {
        if (!isValidSemverRange(dep.versionRange)) {
          pushWarn(
            'manifest/invalid-dependency-version-range',
            `Dependency "${dep.extensionId}" has an unrecognised version range "${dep.versionRange}"`,
          );
        }
      }
    }
  }

  // -----------------------------------------------------------------------
  // Settings schema validation
  // -----------------------------------------------------------------------
  if (manifest.settingsSchema) {
    const version = (manifest.settingsSchema as unknown as Record<string, unknown>).version;
    if (typeof version !== 'number' || !Number.isInteger(version) || version < 0) {
      pushErr(
        'manifest/invalid-settings-schema-version',
        `settingsSchema.version must be a non-negative integer, got ${version}`,
      );
    }
  }

  // -----------------------------------------------------------------------
  // Migration declarations validation
  // -----------------------------------------------------------------------
  const VALID_MIGRATION_KINDS: ReadonlySet<string> = new Set(['settings', 'contribution', 'manifest']);
  if (manifest.migrations && manifest.migrations.length > 0) {
    for (const migration of manifest.migrations) {
      // Legacy shape detection (plain object without 'kind')
      if (typeof migration !== 'object' || migration === null || !('kind' in migration)) {
        // In dev mode these are warnings; in installed mode typed declarations are required
        if (mode === 'installed') {
          pushErr(
            'manifest/legacy-migration-shape',
            'Migration entry lacks "kind"; typed MigrationDeclaration is required for installed extensions',
          );
        } else {
          pushWarn(
            'manifest/legacy-migration-shape',
            'Migration entry is a plain object without "kind"; typed MigrationDeclaration is preferred',
          );
        }
        break; // one diagnostic per manifest
      }

      const m = migration as Record<string, unknown>;

      // Validate kind
      if (!VALID_MIGRATION_KINDS.has(m.kind as string)) {
        pushErr(
          'manifest/invalid-migration-kind',
          `Migration kind "${m.kind}" is not valid; must be one of: settings, contribution, manifest`,
        );
      }

      // Validate fromVersion
      if (typeof m.fromVersion !== 'string' || !isValidSemver(m.fromVersion)) {
        pushErr(
          'manifest/invalid-migration-from-version',
          `Migration fromVersion "${m.fromVersion}" must be a valid semver`,
        );
      }

      // Validate toVersion
      if (typeof m.toVersion !== 'string' || !isValidSemver(m.toVersion)) {
        pushErr(
          'manifest/invalid-migration-to-version',
          `Migration toVersion "${m.toVersion}" must be a valid semver`,
        );
      }
    }
  }

  // -----------------------------------------------------------------------
  // Mode-specific checks: installed vs dev
  // -----------------------------------------------------------------------
  if (mode === 'installed') {
    // ---- Installed-mode required identity fields ----

    // Publisher is required for installed extensions
    if (!manifest.publisher || typeof manifest.publisher !== 'string' || manifest.publisher.trim().length === 0) {
      pushErr(
        'manifest/installed-missing-publisher',
        'Installed extensions must declare a publisher',
      );
    }

    // License is required for installed extensions
    if (!manifest.license || typeof manifest.license !== 'string' || manifest.license.trim().length === 0) {
      pushErr(
        'manifest/installed-missing-license',
        'Installed extensions must declare an SPDX license identifier',
      );
    }

    // Settings schema is recommended for installed extensions
    if (!manifest.settingsSchema) {
      pushWarn(
        'manifest/installed-missing-settings-schema',
        'Installed extensions should declare a settingsSchema for migration tracking',
      );
    }

    // Integrity is expected to be validated externally (on InstalledExtensionMetadata),
    // but if integrity is passed as a top-level field on manifest we validate the shape.
    const integrity = (manifest as unknown as Record<string, unknown>).integrity as IntegrityHash | undefined;
    if (integrity) {
      if (!integrity.algorithm || integrity.algorithm !== 'sha256') {
        pushErr(
          'manifest/installed-invalid-integrity-algorithm',
          `Integrity algorithm "${integrity.algorithm}" is not supported; only "sha256" is allowed`,
        );
      }
      if (!integrity.value || typeof integrity.value !== 'string' || integrity.value.trim().length === 0) {
        pushErr(
          'manifest/installed-missing-integrity-value',
          'Integrity hash value is required',
        );
      }
    }
  } else {
    // ---- Dev mode: compatibility warnings for legacy (M1/local) manifests ----

    // Warn about missing M14-required fields so extension authors see what will be
    // required for installed-pack compatibility.
    if (!manifest.publisher) {
      pushWarn(
        'manifest/dev-missing-publisher',
        'Publisher is not declared; installed extensions require a publisher',
      );
    }
    if (!manifest.license) {
      pushWarn(
        'manifest/dev-missing-license',
        'License is not declared; installed extensions require an SPDX license identifier',
      );
    }
    if (!manifest.settingsSchema) {
      pushWarn(
        'manifest/dev-missing-settings-schema',
        'settingsSchema is not declared; installed extensions should declare one for migration tracking',
      );
    }
  }

  // -----------------------------------------------------------------------
  return {
    valid: errors.length === 0,
    errors: Object.freeze([...errors]),
    warnings: Object.freeze([...warnings]),
  };
}

// ---------------------------------------------------------------------------
// Installed package validation
// ---------------------------------------------------------------------------

/**
 * Validate a full installed extension package.
 *
 * Checks package structure, metadata/manifest cross-references,
 * integrity hash presence, and delegates manifest-level validation
 * to {@link validateManifest} in 'installed' mode.
 */
export function validateInstalledPackage(
  pack: InstalledExtensionPackage,
): ManifestValidationResult {
  const errors: ExtensionDiagnostic[] = [];
  const warnings: ExtensionDiagnostic[] = [];

  const extId = pack.metadata?.extensionId as string ?? '(unknown)';

  const pushErr = (code: string, message: string): void => {
    errors.push({ severity: 'error', code, message, extensionId: extId });
  };

  // Structural checks
  if (!pack.metadata) {
    pushErr('package/missing-metadata', 'Installed package must include metadata');
    return { valid: false, errors: Object.freeze([...errors]), warnings: Object.freeze([...warnings]) };
  }

  if (!pack.manifest) {
    pushErr('package/missing-manifest', 'Installed package must include a manifest');
    return { valid: false, errors: Object.freeze([...errors]), warnings: Object.freeze([...warnings]) };
  }

  if (typeof pack.bundleContent !== 'string' || pack.bundleContent.trim().length === 0) {
    pushErr('package/missing-bundle', 'Installed package must include non-empty bundleContent');
  }

  // Cross-reference: metadata.extensionId === manifest.id
  if (pack.metadata.extensionId !== pack.manifest.id) {
    pushErr(
      'package/id-mismatch',
      `Metadata extensionId "${pack.metadata.extensionId}" does not match manifest.id "${pack.manifest.id}"`,
    );
  }

  // Cross-reference: metadata.version === manifest.version
  if (pack.metadata.version !== pack.manifest.version) {
    pushErr(
      'package/version-mismatch',
      `Metadata version "${pack.metadata.version}" does not match manifest.version "${pack.manifest.version}"`,
    );
  }

  // Integrity validation
  if (!pack.metadata.integrity) {
    pushErr('package/missing-integrity', 'Installed package metadata must include integrity hash');
  } else {
    if (!pack.metadata.integrity.algorithm || pack.metadata.integrity.algorithm !== 'sha256') {
      pushErr(
        'package/invalid-integrity-algorithm',
        `Integrity algorithm "${pack.metadata.integrity.algorithm}" is not supported; only "sha256" is allowed`,
      );
    }
    if (!pack.metadata.integrity.value || typeof pack.metadata.integrity.value !== 'string' || pack.metadata.integrity.value.trim().length === 0) {
      pushErr('package/missing-integrity-value', 'Integrity hash value is required');
    }
  }

  // Enabled must be boolean
  if (typeof pack.metadata.enabled !== 'boolean') {
    pushErr('package/invalid-enabled', 'Metadata enabled must be a boolean');
  }

  // Delegate to manifest validation in installed mode
  const manifestResult = validateManifest(pack.manifest, 'installed');
  for (const err of manifestResult.errors) {
    errors.push(err);
  }
  for (const warn of manifestResult.warnings) {
    warnings.push(warn);
  }

  return {
    valid: errors.length === 0,
    errors: Object.freeze([...errors]),
    warnings: Object.freeze([...warnings]),
  };
}
