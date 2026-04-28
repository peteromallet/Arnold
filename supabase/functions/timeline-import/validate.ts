// deno-lint-ignore-file
import type { TimelineImportBody } from "./types.ts";

interface ValidatedPayload {
  ok: true;
  timeline: Record<string, unknown>;
  assetRegistry: Record<string, unknown> | null;
}

interface ValidationFailure {
  ok: false;
  error: string;
}

/**
 * Body-level validation that complements the Zod TimelineConfig parse in
 * `handler.ts`. We separate the timeline schema (which the Zod parse owns)
 * from the asset_registry envelope (which is Reigh-specific).
 */
export function validateTimelinePayload(
  body: TimelineImportBody,
): ValidatedPayload | ValidationFailure {
  if (!isPlainObject(body.timeline)) {
    return { ok: false, error: "timeline must be a JSON object" };
  }
  const assetRegistryRaw = body.asset_registry;
  let assetRegistry: Record<string, unknown> | null = null;
  if (assetRegistryRaw !== undefined && assetRegistryRaw !== null) {
    if (!isPlainObject(assetRegistryRaw)) {
      return { ok: false, error: "asset_registry must be a JSON object" };
    }
    const assets = (assetRegistryRaw as Record<string, unknown>).assets;
    if (!isPlainObject(assets)) {
      return { ok: false, error: "asset_registry.assets must be an object" };
    }
    for (const [key, entry] of Object.entries(assets)) {
      if (!isPlainObject(entry)) {
        return { ok: false, error: `asset_registry.assets[${key}] must be an object` };
      }
    }
    assetRegistry = assetRegistryRaw as Record<string, unknown>;
  }
  return {
    ok: true,
    timeline: body.timeline as Record<string, unknown>,
    assetRegistry,
  };
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
