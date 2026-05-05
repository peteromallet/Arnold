// Fork-to-DB bundled-source extraction for SequenceCreatorPanel.
//
// MVP scope (FLAG-006):
// - Only LOCAL_SEQUENCE_REGISTRY entries can be forked. Their source TSX
//   lives in-tree under src/tools/video-editor/sequences/components/, so
//   Vite's `?raw` static-import suffix can hand us the file contents at
//   build time without round-tripping through the network or filesystem.
// - For pure npm-package theme entries (e.g. cta-card from
//   timeline-theme-2rp), we don't have an in-tree source mirror, so the
//   helper returns a `cannot-fork` result with a user-facing reason. The
//   panel surfaces that as inline copy ("Cannot fork yet — this sequence's
//   source isn't bundled in-tree").
// - LOCAL_SEQUENCE_REGISTRY entries don't have sibling schema.json /
//   defaults.json triplets (unlike the timeline-theme-2rp build pipeline).
//   We surface a minimal placeholder schema/defaults so the edge function
//   can run; the model is encouraged to refine the schema during fork.
//   This is acknowledged in FLAG-006 — full schema bundling is a follow-up.

// `?raw` imports are static — Vite enumerates these at build time.
import imageJumpSource from './components/ImageJumpSequence.tsx?raw';
import titleCardSource from './components/TitleCardSequence.tsx?raw';

export interface BundledComponentSource {
  status: 'available';
  code: string;
  schema: object;
  defaults: object;
}

export interface BundledComponentSourceUnavailable {
  status: 'cannot-fork';
  reason: string;
}

export type GetBundledComponentSourceResult =
  | BundledComponentSource
  | BundledComponentSourceUnavailable;

const PLACEHOLDER_SCHEMA = {
  type: 'object',
  properties: {} as Record<string, unknown>,
} as const;
const PLACEHOLDER_DEFAULTS: Record<string, unknown> = {};

const LOCAL_SOURCES: Record<string, string> = {
  'image-jump': imageJumpSource as unknown as string,
  'title-card': titleCardSource as unknown as string,
};

/**
 * Resolve the in-tree source TSX for a theme-bundled sequence component.
 * Returns `{ status: 'cannot-fork', reason }` when the clipType isn't in
 * LOCAL_SEQUENCE_REGISTRY (e.g. pure npm-package entries from theme-2rp).
 *
 * Schema/defaults note: LOCAL_SEQUENCE_REGISTRY entries don't ship sibling
 * schema.json/defaults.json files (FLAG-006). The placeholder schema lets
 * the edge function start the fork conversation; the model is expected to
 * propose a real schema during the first generation. Real schema bundling
 * is tracked as a follow-up.
 */
export function getBundledComponentSource(clipType: string): GetBundledComponentSourceResult {
  const code = LOCAL_SOURCES[clipType];
  if (!code) {
    return {
      status: 'cannot-fork',
      reason:
        `Cannot fork yet — this sequence's source isn't bundled in-tree (clipType: ${clipType}). ` +
        'Only local sequence components can currently be customised.',
    };
  }
  return {
    status: 'available',
    code,
    schema: PLACEHOLDER_SCHEMA,
    defaults: PLACEHOLDER_DEFAULTS,
  };
}
