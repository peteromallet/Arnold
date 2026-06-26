/**
 * Metadata Facet family module.
 *
 * Houses the MetadataFacetContribution manifest interface extracted from
 * the public barrel (src/sdk/index.ts).  Descriptor/value contracts
 * (MetadataFacetValueKind, MetadataFacetDescriptor) stay in
 * src/sdk/video/assets/metadata.ts as portable public contracts.
 *
 * @publicContract
 */

import type { ContributionId } from '../../ids';
import type { MetadataFacetValueKind } from '../assets/metadata';

/**
 * M6: A metadata facet contribution declared in an extension manifest.
 *
 * Metadata facets tell the host how to surface a metadata field
 * as a searchable/filterable facet in the asset panel.
 */
export interface MetadataFacetContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'metadataFacet';
  /**
   * Dot-separated path to the metadata field.
   * E.g. 'gps.latitude', 'integrity.algorithm', 'extensions.myExt.tags'.
   */
  fieldPath: string;
  /** Human-readable display name for the facet. */
  displayName: string;
  /** The value kind — determines rendering and filtering strategy. */
  valueKind: MetadataFacetValueKind;
  /** Lower values sort first. Default 0. */
  order?: number;
  /**
   * Aggregation posture hint for the host.
   * - `exact` — values should be surfaced individually
   * - `range` — numeric values can be bucketed
   * - `presence` — only show whether the field exists
   */
  aggregationPosture?: 'exact' | 'range' | 'presence';
  /**
   * Allowed values when `valueKind` is 'enum'.
   * The host uses this for dropdown/checkbox filter UI.
   */
  enumValues?: readonly string[];
}
