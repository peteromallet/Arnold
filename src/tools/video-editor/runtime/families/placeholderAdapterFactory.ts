/**
 * Placeholder adapter factory — wraps pure projectors as delegated
 * HostFamilyAdapter instances.
 *
 * Placeholder adapters own the normalization path for families whose
 * execution maturity is `delegated` but that still surface runtime
 * descriptors (delegated-but-projectable).  They carry the full
 * {@link HostFamilyAdapter} contract so the adapter coordinator,
 * conformance aggregation, and family runtime assembly can treat them
 * uniformly with real adapters.
 *
 * Every placeholder adapter's manifest maturity is `'delegated'` and
 * its manifest includes a description that marks it as a placeholder.
 *
 * @module families/placeholderAdapterFactory
 */

import type {
  HostFamilyAdapter,
  HostAdapterManifest,
  NormalizeFamilyInput,
  FamilyNormalizeResult,
  FamilyConformanceReport,
  ExecutionMaturity,
} from '@reigh/editor-sdk';
import { getVideoFamilyDefinition } from '@reigh/editor-sdk';
import { buildConformanceReport } from '@/sdk/core/families/conformance';

// ---------------------------------------------------------------------------
// Factory options
// ---------------------------------------------------------------------------

/**
 * Options for {@link createPlaceholderAdapter}.
 */
export interface PlaceholderAdapterOptions {
  /** Human-readable description for the adapter manifest. */
  readonly description?: string;

  /** Semver version string. Defaults to `'0.0.0-placeholder'`. */
  readonly version?: string;

  /** The owner team or system responsible for this delegated family. */
  readonly owner?: string;

  /** Why this family is delegated (e.g. 'awaiting real adapter implementation'). */
  readonly reason?: string;

  /** Expiration date for the delegated posture (ISO-8601 date string,
   *  milestone like `M4`, or `'never'`).  Defaults to `'M4'`. */
  readonly expiration?: string;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create a placeholder {@link HostFamilyAdapter} that wraps a pure
 * projector function.
 *
 * Placeholder adapters are used for families whose execution maturity is
 * `delegated` but that still surface runtime descriptors.  They satisfy
 * the full adapter contract so that the rest of the host pipeline
 * (coordinator, conformance aggregation, assembly) can treat them
 * identically to real adapters.
 *
 * The returned adapter is frozen.
 *
 * @typeParam Kind        — The contribution kind string literal.
 * @typeParam TContribution — The contribution shape for this family.
 * @typeParam TDescriptor — The descriptor type produced by the projector.
 *
 * @param kind      — The contribution kind this adapter services.
 * @param projector — A pure function that converts sorted contributions
 *                    into a frozen descriptor array.
 * @param options   — Optional manifest overrides and delegation metadata.
 * @returns A frozen {@link HostFamilyAdapter} with `delegated` maturity.
 */
export function createPlaceholderAdapter<
  Kind extends string,
  TContribution,
  TDescriptor,
>(
  kind: Kind,
  projector: (
    input: NormalizeFamilyInput<TContribution>,
  ) => FamilyNormalizeResult<TDescriptor>,
  options?: PlaceholderAdapterOptions,
): HostFamilyAdapter<Kind, TContribution, TDescriptor> {
  const owner = options?.owner ?? 'video-editor-runtime';
  const reason =
    options?.reason ?? 'awaiting real adapter implementation';
  const expiration = options?.expiration ?? 'M4';

  const manifest: HostAdapterManifest = Object.freeze({
    adapterId: `${kind}-placeholder`,
    kind,
    version: options?.version ?? '0.0.0-placeholder',
    maturity: 'delegated' as ExecutionMaturity,
    description:
      options?.description ??
      `Placeholder adapter for "${kind}" — delegated projection.`,
    metadata: Object.freeze({
      classification: 'placeholder',
      owner,
      reason,
      expiration,
    }),
  });

  const adapter: HostFamilyAdapter<Kind, TContribution, TDescriptor> = {
    kind,
    classification: 'placeholder',
    manifest,

    /**
     * Normalize a batch of contributions into descriptors by delegating
     * to the projector function.
     *
     * The projector is expected to return a frozen descriptor array.
     */
    normalize(input: NormalizeFamilyInput<TContribution>): FamilyNormalizeResult<TDescriptor> {
      return projector(input);
    },

    /**
     * Build a conformance report for this placeholder adapter's family
     * by reading the canonical family definition from the SDK registry.
     */
    buildConformanceReport(): FamilyConformanceReport<Kind> {
      const definition = getVideoFamilyDefinition(kind);
      if (!definition) {
        throw new Error(
          `Placeholder adapter for "${kind}": family definition not found.`,
        );
      }
      return buildConformanceReport(definition) as FamilyConformanceReport<Kind>;
    },
  };

  return Object.freeze(adapter);
}

// ---------------------------------------------------------------------------
// Convenience re-exports
// ---------------------------------------------------------------------------

/**
 * Build a placeholder adapter ID for a given kind.
 * Useful for consumers that need to reference the adapter without
 * creating one.
 */
export function placeholderAdapterId(kind: string): string {
  return `${kind}-placeholder`;
}
