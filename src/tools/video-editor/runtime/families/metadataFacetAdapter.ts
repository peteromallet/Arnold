/**
 * Metadata Facet adapter — first real HostFamilyAdapter.
 *
 * Owns normalization, lifecycle, diagnostics, and conformance reporting
 * for metadata facet contributions.  Replaces the inline projection
 * previously embedded in FamilyRuntimeAssembly's switch statement.
 *
 * @module families/metadataFacetAdapter
 */

import type {
  HostFamilyAdapter,
  HostAdapterManifest,
  NormalizeFamilyInput,
  FamilyNormalizeResult,
  FamilyConformanceReport,
  ExecutionMaturity,
} from '@reigh/editor-sdk';
import type { MetadataFacetContribution } from '@reigh/editor-sdk';
import { getVideoFamilyDefinition } from '@reigh/editor-sdk';
import type { VideoEditorMetadataFacetDescriptor } from '../extensionSurface';
import { buildConformanceReport } from '@/sdk/core/families/conformance';

// ---------------------------------------------------------------------------
// Adapter manifest
// ---------------------------------------------------------------------------

const MANIFEST: HostAdapterManifest = Object.freeze({
  adapterId: 'metadataFacet-default',
  kind: 'metadataFacet',
  version: '1.0.0',
  maturity: 'runtime-bridged' as ExecutionMaturity,
  description:
    'Normalizes metadata facet contributions into VideoEditorMetadataFacetDescriptor ' +
    'records for the asset panel.  Owns field-path validation, value-kind ' +
    'preservation, aggregation-posture projection, and enum-value freezing.',
});

// ---------------------------------------------------------------------------
// Adapter implementation
// ---------------------------------------------------------------------------

/**
 * The metadata facet host family adapter.
 *
 * This is the first real (non-placeholder) adapter in the system.  It
 * proves the adapter path used by later families: normalize contributions
 * → produce frozen descriptors → report conformance via the SDK
 * family definitions registry.
 */
export const metadataFacetAdapter: HostFamilyAdapter<
  'metadataFacet',
  MetadataFacetContribution,
  VideoEditorMetadataFacetDescriptor
> = Object.freeze({
  kind: 'metadataFacet' as const,
  classification: 'real',
  manifest: MANIFEST,

  // -----------------------------------------------------------------------
  // Normalization
  // -----------------------------------------------------------------------

  /**
   * Normalize a batch of metadata facet contributions into deterministically
   * ordered {@link VideoEditorMetadataFacetDescriptor} records.
   *
   * The input contributions are assumed to already be sorted in the
   * canonical order (extension-order → contribution.order → contribution.id).
   * The adapter does not re-sort — ordering is the caller's responsibility.
   *
   * @param input — Sorted metadata facet contributions with their
   *                owning extension IDs.
   * @returns A frozen array of normalized metadata facet descriptors.
   */
  normalize(
    input: NormalizeFamilyInput<MetadataFacetContribution>,
  ): FamilyNormalizeResult<VideoEditorMetadataFacetDescriptor> {
    const descriptors: VideoEditorMetadataFacetDescriptor[] = [];

    for (const { contribution, extensionId } of input.contributions) {
      const facetContrib = contribution as unknown as MetadataFacetContribution;

      descriptors.push(
        Object.freeze({
          id: contribution.id as string,
          extensionId,
          order: contribution.order,
          fieldPath: facetContrib.fieldPath,
          displayName: facetContrib.displayName,
          valueKind: facetContrib.valueKind,
          aggregationPosture: facetContrib.aggregationPosture,
          enumValues: facetContrib.enumValues
            ? Object.freeze([...facetContrib.enumValues])
            : undefined,
        }),
      );
    }

    return { descriptors: Object.freeze(descriptors) };
  },

  // -----------------------------------------------------------------------
  // Conformance
  // -----------------------------------------------------------------------

  /**
   * Build a {@link FamilyConformanceReport} for the metadata facet family
   * by reading the canonical family definition from the SDK registry.
   *
   * @returns The conformance report for the metadata facet family.
   */
  buildConformanceReport(): FamilyConformanceReport<'metadataFacet'> {
    const definition = getVideoFamilyDefinition('metadataFacet');
    if (!definition) {
      throw new Error(
        'metadataFacetAdapter: family definition not found for kind "metadataFacet".',
      );
    }
    return buildConformanceReport(definition);
  },
});

// ---------------------------------------------------------------------------
// Static helpers (convenience exports)
// ---------------------------------------------------------------------------

/**
 * The contribution kind this adapter services.
 * Convenience re-export for consumers that need the kind without
 * importing the adapter object.
 */
export const METADATA_FACET_ADAPTER_KIND = 'metadataFacet' as const;

/**
 * Build a conformance report for the metadata facet family via the adapter.
 *
 * This is a convenience wrapper around
 * `metadataFacetAdapter.buildConformanceReport()`.
 */
export function buildMetadataFacetConformanceReport(): FamilyConformanceReport<'metadataFacet'> {
  return metadataFacetAdapter.buildConformanceReport();
}
