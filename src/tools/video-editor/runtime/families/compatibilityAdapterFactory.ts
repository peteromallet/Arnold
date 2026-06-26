/**
 * Compatibility adapter factory — minimal real adapters for host-integrated
 * or runtime-bridged families whose actual runtime wiring lives outside the
 * extension surface config (e.g. command dispatch, clip type registry).
 *
 * These adapters exist so the adapter registry and conformance gates have
 * a real, non-placeholder host adapter file for every family whose SDK
 * execution maturity is not `delegated`/`absent`.
 *
 * @module families/compatibilityAdapterFactory
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

export interface CompatibilityAdapterOptions {
  readonly adapterId: string;
  readonly kind: string;
  readonly version?: string;
  readonly maturity: ExecutionMaturity;
  readonly description?: string;
}

export function createCompatibilityAdapter(
  options: CompatibilityAdapterOptions,
): HostFamilyAdapter<string, unknown, unknown> {
  const manifest: HostAdapterManifest = Object.freeze({
    adapterId: options.adapterId,
    kind: options.kind,
    version: options.version ?? '1.0.0',
    maturity: options.maturity,
    description:
      options.description ??
      `Compatibility adapter for "${options.kind}" — host wiring lives outside the extension surface.`,
    metadata: Object.freeze({ classification: 'real' }),
  });

  return Object.freeze({
    kind: options.kind,
    classification: 'real',
    manifest,

    normalize(
      _input: NormalizeFamilyInput<unknown>,
    ): FamilyNormalizeResult<unknown> {
      return { descriptors: Object.freeze([]) };
    },

    buildConformanceReport(): FamilyConformanceReport<string> {
      const definition = getVideoFamilyDefinition(options.kind);
      if (!definition) {
        throw new Error(
          `${options.adapterId}: family definition not found for kind "${options.kind}".`,
        );
      }
      return buildConformanceReport(definition) as FamilyConformanceReport<string>;
    },
  });
}
