/**
 * Core manifest contracts for the Reigh Editor SDK.
 *
 * Stable public types and constants for extension manifest declarations,
 * contribution contracts, slot definitions, and placement rules.
 *
 * NOTE: ExtensionManifest remains inline in index.ts until its dependency
 * types (CommandContribution, KeybindingContribution, etc.) are extracted
 * to canonical modules. At that point ExtensionManifest can move here
 * with direct imports from the canonical sources.
 *
 * @publicContract
 */

import type { ExtensionId, ContributionId } from './ids';
import type { VideoContributionKind } from '@/sdk/video/families/kinds';
import {
  VIDEO_CONTRIBUTION_KINDS,
  VIDEO_CONTRIBUTION_KINDS_SET,
} from '@/sdk/video/families/kinds';
import type { ExtensionDiagnostic } from './diagnostics';

// ---------------------------------------------------------------------------
// Contribution kind and slot name contracts
// ---------------------------------------------------------------------------

/**
 * Known contribution kinds. Reserved/inactive kinds are validated but not bridged.
 *
 * Alias of {@link VideoContributionKind} from `src/sdk/video/families/kinds.ts`,
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
 * `src/sdk/video/families/kinds.ts`.
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
