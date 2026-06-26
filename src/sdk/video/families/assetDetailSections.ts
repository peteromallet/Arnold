/**
 * Asset detail section family contracts.
 *
 * Asset detail sections are named slots within the asset detail panel.
 * The host owns section placement, empty/error states, search result badges,
 * and provenance-chain rendering. Extensions provide section descriptors
 * to declare what metadata they surface.
 *
 * @module video/families/assetDetailSections
 * @publicContract
 */

import type { ContributionId } from '../../ids';

/**
 * M6: An asset detail section contribution declared in an extension manifest.
 *
 * Asset detail sections are named slots within the asset detail panel.
 * The host owns section placement, empty/error states, search result badges,
 * and provenance-chain rendering.  Extensions provide section descriptors
 * to declare what metadata they surface.
 */
export interface AssetDetailSectionContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'assetDetailSection';
  /** Human-readable section title. */
  title: string;
  /**
   * Placement within the asset detail panel.
   * - `before-default` — before host-owned metadata sections
   * - `after-default` — after host-owned metadata sections
   */
  placement: 'before-default' | 'after-default';
  /**
   * The metadata field paths this section reads.
   * The host uses these to determine section visibility and data binding.
   */
  fieldPaths?: readonly string[];
  /** Lower values sort first within their placement group. Default 0. */
  order?: number;
  /**
   * Optional visibility predicate (evaluated by host).
   * E.g. 'asset.metadata.integrity != null'.
   */
  when?: string;
}
