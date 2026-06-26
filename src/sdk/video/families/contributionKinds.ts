/**
 * Video contribution kind authority.
 *
 * Single source of truth for the `VideoContributionKind` union, its
 * runtime-inspectable array, and lookup set.  Public SDK exports
 * (`ContributionKind`, `KNOWN_CONTRIBUTION_KINDS`,
 * `KNOWN_CONTRIBUTION_KINDS_SET`) are aliases / re-exports of the
 * symbols defined here.
 *
 * Descriptor interfaces (ExtensionContribution, etc.) remain in
 * `src/sdk/manifest.ts` alongside the barrel re-exports.
 *
 * @publicContract
 */

/** Known contribution kinds. Reserved/inactive kinds are validated but not bridged. */
export type VideoContributionKind =
  | 'slot'
  | 'dialog'
  | 'panel'
  | 'inspectorSection'
  | 'timelineOverlay'
  // M4: commands, keybindings, context menus
  | 'command'
  | 'keybinding'
  | 'contextMenuItem'
  // M6: parser, output format, search provider, metadata facet, asset detail section
  | 'parser'
  | 'outputFormat'
  | 'searchProvider'
  | 'metadataFacet'
  | 'assetDetailSection'
  // M12: trusted local process descriptors
  | 'process'
  // M7-M9: effect, transition, clip type, automation (bridged in their milestones)
  | 'effect'
  | 'transition'
  | 'clipType'
  // M13: dedicated shader/WebGL contributions
  | 'shader'
  // M9: automation clip type (host-owned)
  | 'automation'
  // M10: agent tool contributions (host-mediated, proposal-backed)
  | 'agentTool'
  // Reserved — not yet bridged
  | 'agent';

/**
 * All known contribution kinds as a runtime-inspectable readonly array.
 * Use this to enumerate valid kinds at runtime without relying on the
 * TypeScript type system alone.
 */
export const VIDEO_CONTRIBUTION_KINDS: readonly VideoContributionKind[] = [
  'slot',
  'dialog',
  'panel',
  'inspectorSection',
  'timelineOverlay',
  'command',
  'keybinding',
  'contextMenuItem',
  'parser',
  'outputFormat',
  'searchProvider',
  'metadataFacet',
  'assetDetailSection',
  'process',
  'effect',
  'transition',
  'clipType',
  'shader',
  'automation',
  'agentTool',
  'agent',
] as const;

/** Set form of {@link VIDEO_CONTRIBUTION_KINDS} for fast lookups. */
export const VIDEO_CONTRIBUTION_KINDS_SET: ReadonlySet<string> = new Set(VIDEO_CONTRIBUTION_KINDS);
