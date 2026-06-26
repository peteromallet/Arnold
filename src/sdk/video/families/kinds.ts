/**
 * Temporary compatibility re-export.
 *
 * `src/sdk/video/families/contributionKinds.ts` is now the canonical
 * home for `VideoContributionKind`, `VIDEO_CONTRIBUTION_KINDS`, and
 * `VIDEO_CONTRIBUTION_KINDS_SET`.  This module re-exports those symbols
 * so existing importers are not broken during the transition.
 *
 * New code should import directly from `./contributionKinds`.
 *
 * @deprecated Import from `./contributionKinds` instead.
 */

export type { VideoContributionKind } from './contributionKinds';
export { VIDEO_CONTRIBUTION_KINDS, VIDEO_CONTRIBUTION_KINDS_SET } from './contributionKinds';
