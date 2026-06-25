/**
 * Canonical timeline config signature helpers shared by the SDK and host.
 *
 * These helpers intentionally stay data-only: they hash persisted timeline
 * config state and resolved config projections without depending on host
 * runtime services, URL resolvers, or editor stores.
 *
 * @publicContract
 */

/**
 * JSON-serializable timeline payload accepted by `getConfigSignature`.
 *
 * The helper only relies on object structure because callers may pass either
 * persisted timeline config data or host-resolved timeline projections.
 */
export type TimelineConfigSignatureInput = Record<string, unknown>;

/** Asset-registry payload accepted by `getStableConfigSignature`. */
export type StableTimelineAssetRegistryInput = Record<string, unknown>;

/**
 * Persisted inputs accepted by `getStableConfigSignature`.
 *
 * `registry` is optional to preserve the historical host helper behavior where
 * callers could hash config-only snapshots.
 */
export interface StableTimelineConfigSignatureInput {
  config: TimelineConfigSignatureInput;
  registry?: StableTimelineAssetRegistryInput;
}

/** Serialize a timeline payload exactly as-is for quick identity checks. */
export const getConfigSignature = (
  config: TimelineConfigSignatureInput,
): string => JSON.stringify(config);

const normalizeForStableJson = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map((item) => {
      const normalized = normalizeForStableJson(item);
      return normalized === undefined ? null : normalized;
    });
  }

  if (value && typeof value === 'object') {
    return Object.keys(value)
      .sort()
      .reduce<Record<string, unknown>>((acc, key) => {
        const normalized = normalizeForStableJson((value as Record<string, unknown>)[key]);
        if (normalized !== undefined) {
          acc[key] = normalized;
        }
        return acc;
      }, {});
  }

  return value;
};

/** Serialize persisted config plus registry with stable object-key ordering. */
export const getStableConfigSignature = (
  config: TimelineConfigSignatureInput,
  registry?: StableTimelineAssetRegistryInput,
): string => {
  const stableInput: StableTimelineConfigSignatureInput = { config, registry };
  return JSON.stringify(normalizeForStableJson(stableInput));
};
