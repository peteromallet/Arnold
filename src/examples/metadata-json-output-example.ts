/**
 * metadata-json-output-example — Compile-only output format that serializes
 * timeline identity, asset registry metadata, consent/provenance, deferred
 * enrichment records, and parser diagnostics into stable JSON.
 *
 * Demonstrates M6 compile-only output formats using only @reigh/editor-sdk:
 *   - An OutputFormatContribution with requiresRender: false
 *   - An OutputFormatHandler that produces deterministic metadata JSON
 *   - Stable key ordering for byte-identical output across executions
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  AssetMetadata,
  CompileOnlyOutputResult,
  DeferredEnrichmentRecord,
  DisposeHandle,
  ExtensionContext,
  OutputFormatContribution,
  OutputFormatContext,
  OutputFormatHandler,
  ReighExtension,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EXTENSION_ID = 'com.reigh.examples.metadata-json-output';

const FORMAT_ID = `${EXTENSION_ID}.metadata-json`;

// ---------------------------------------------------------------------------
// Stable JSON serialization helpers
// ---------------------------------------------------------------------------

/**
 * Recursively sort object keys alphabetically for deterministic serialization.
 *
 * Arrays are preserved in their original order; only plain-object keys are
 * sorted.  This ensures byte-identical output for the same input data.
 */
function stableSortKeys(value: unknown): unknown {
  if (value === null || typeof value !== 'object') {
    return value;
  }

  if (Array.isArray(value)) {
    return value.map(stableSortKeys);
  }

  // Plain object — sort keys alphabetically
  const sorted: Record<string, unknown> = {};
  const keys = Object.keys(value).sort();
  for (const key of keys) {
    sorted[key] = stableSortKeys((value as Record<string, unknown>)[key]);
  }
  return sorted;
}

/**
 * Serialize a value to stable JSON with sorted keys and no trailing newline.
 *
 * Uses JSON.stringify with a deterministic key order, 2-space indentation,
 * and no trailing whitespace to guarantee byte-identical output for the
 * same logical data.
 */
function stableStringify(value: unknown): string {
  const sorted = stableSortKeys(value);
  return JSON.stringify(sorted, null, 2);
}

// ---------------------------------------------------------------------------
// Output format contribution (declared in the extension manifest)
// ---------------------------------------------------------------------------

const contributions: readonly [OutputFormatContribution] = [
  {
    id: FORMAT_ID as any,
    kind: 'outputFormat',
    label: 'Metadata JSON Export',
    requiresRender: false,
    outputExtension: 'json',
    outputMimeType: 'application/json',
    description:
      'Serialize timeline identity, asset registry metadata, consent/provenance, deferred enrichment records, and parser diagnostics into stable JSON.',
    order: 10,
  },
];

// ---------------------------------------------------------------------------
// Metadata serialization helpers
// ---------------------------------------------------------------------------

/**
 * Serialize a single DeferredEnrichmentRecord to a stable plain object.
 *
 * Keys are emitted in a fixed order regardless of input key order.
 */
function serializeEnrichmentRecord(record: DeferredEnrichmentRecord): Record<string, unknown> {
  return {
    id: record.id,
    assetId: record.assetId,
    kind: record.kind,
    input: record.input ?? null,
    status: record.status,
    extensionId: record.extensionId,
    contributionId: record.contributionId ?? null,
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
    diagnostic: record.diagnostic ?? null,
    output: record.output ?? null,
  };
}

/**
 * Serialize a single asset's metadata to a stable plain object.
 *
 * Host-owned keys (integrity, gps, consent, provenance, enrichment) are
 * emitted first, followed by extension-owned namespaces.  Keys within
 * each section are sorted alphabetically.
 */
function serializeAssetMetadata(
  assetKey: string,
  metadata: Readonly<AssetMetadata>,
): Record<string, unknown> {
  const result: Record<string, unknown> = { assetKey };

  if (metadata.integrity) {
    result.integrity = {
      algorithm: metadata.integrity.algorithm,
      hash: metadata.integrity.hash,
      size: metadata.integrity.size,
    };
  }

  if (metadata.gps) {
    const gps: Record<string, unknown> = {};
    if (metadata.gps.latitude !== undefined) gps.latitude = metadata.gps.latitude;
    if (metadata.gps.longitude !== undefined) gps.longitude = metadata.gps.longitude;
    if (metadata.gps.altitude !== undefined) gps.altitude = metadata.gps.altitude;
    if (metadata.gps.timestamp !== undefined) gps.timestamp = metadata.gps.timestamp;
    if (Object.keys(gps).length > 0) {
      result.gps = gps;
    }
  }

  if (metadata.consent) {
    const consent: Record<string, unknown> = {};
    if (metadata.consent.source !== undefined) consent.source = metadata.consent.source;
    if (metadata.consent.rightsNote !== undefined) consent.rightsNote = metadata.consent.rightsNote;
    if (metadata.consent.consentRecorded !== undefined) consent.consentRecorded = metadata.consent.consentRecorded;
    if (metadata.consent.consentTimestamp !== undefined) consent.consentTimestamp = metadata.consent.consentTimestamp;
    if (Object.keys(consent).length > 0) {
      result.consent = consent;
    }
  }

  if (metadata.provenance) {
    const provenance: Record<string, unknown> = {};
    if (metadata.provenance.origin !== undefined) provenance.origin = metadata.provenance.origin;
    if (metadata.provenance.derivedFromAssetId !== undefined) provenance.derivedFromAssetId = metadata.provenance.derivedFromAssetId;
    if (metadata.provenance.generated !== undefined) provenance.generated = metadata.provenance.generated;
    if (metadata.provenance.capturedAt !== undefined) provenance.capturedAt = metadata.provenance.capturedAt;
    if (metadata.provenance.importedAt !== undefined) provenance.importedAt = metadata.provenance.importedAt;
    if (Object.keys(provenance).length > 0) {
      result.provenance = provenance;
    }
  }

  // Deferred enrichment records
  if (metadata.enrichment && metadata.enrichment.length > 0) {
    result.enrichment = metadata.enrichment.map(serializeEnrichmentRecord);
  }

  // Extension-owned namespaces
  if (metadata.extensions) {
    const extNamespaces: Record<string, unknown> = {};
    const extKeys = Object.keys(metadata.extensions).sort();
    for (const extId of extKeys) {
      extNamespaces[extId] = metadata.extensions[extId];
    }
    if (Object.keys(extNamespaces).length > 0) {
      result.extensions = extNamespaces;
    }
  }

  return result;
}

/**
 * Serialize timeline identity metadata to a stable plain object.
 *
 * Includes project identity, version info, clip/track counts, and
 * the list of asset keys referenced by the timeline.
 */
function serializeTimelineIdentity(
  context: OutputFormatContext,
): Record<string, unknown> {
  const { timeline } = context;

  return {
    projectId: timeline.projectId,
    baseVersion: timeline.baseVersion,
    currentVersion: timeline.currentVersion,
    clipCount: timeline.clips.length,
    trackCount: timeline.tracks.length,
    assetKeyCount: timeline.assetKeys.length,
    assetKeys: [...timeline.assetKeys].sort(),
    clips: timeline.clips.map((clip) => ({
      id: clip.id,
      track: clip.track,
      at: clip.at,
      clipType: clip.clipType ?? null,
      duration: clip.duration,
      managed: clip.managed,
      managedBy: clip.managedBy ?? null,
    })),
    tracks: timeline.tracks.map((track) => ({
      id: track.id,
      kind: track.kind,
      label: track.label,
      muted: track.muted,
    })),
  };
}

/**
 * Build the complete metadata JSON payload.
 *
 * Top-level keys are emitted in a fixed order:
 *   1. exportInfo — identifies the export format, extension, and timestamp
 *   2. timeline — timeline identity metadata
 *   3. assets — asset registry metadata keyed by asset key
 *   4. enrichment — global enrichment summary across all assets
 *   5. diagnostics — parser diagnostics collected from asset metadata
 */
function buildMetadataPayload(context: OutputFormatContext): Record<string, unknown> {
  const { timeline, assets, extensionId, contributionId } = context;

  // Export info
  const exportInfo: Record<string, unknown> = {
    format: 'metadata-json',
    version: '1.0.0',
    extensionId,
    contributionId,
    exportedAt: new Date().toISOString(),
  };

  // Timeline identity
  const timelineSection = serializeTimelineIdentity(context);

  // Asset registry metadata (sorted by asset key)
  const assetKeys = [...assets.keys()].sort();
  const assetsSection: Record<string, unknown> = {};
  for (const key of assetKeys) {
    const meta = assets.get(key);
    if (meta) {
      assetsSection[key] = serializeAssetMetadata(key, meta);
    }
  }

  // Global enrichment summary
  const enrichmentRecords: DeferredEnrichmentRecord[] = [];
  const enrichmentByStatus: Record<string, number> = {};
  for (const key of assetKeys) {
    const meta = assets.get(key);
    if (meta?.enrichment) {
      for (const record of meta.enrichment) {
        enrichmentRecords.push(record);
        enrichmentByStatus[record.status] = (enrichmentByStatus[record.status] ?? 0) + 1;
      }
    }
  }
  const enrichmentSection: Record<string, unknown> = {
    totalRecords: enrichmentRecords.length,
    byStatus: enrichmentByStatus,
    records: enrichmentRecords.map(serializeEnrichmentRecord),
  };

  // Parser diagnostics collected from asset metadata
  const diagnostics: unknown[] = [];
  for (const record of enrichmentRecords) {
    if (record.status === 'failed' || record.status === 'expired') {
      diagnostics.push({
        enrichmentRecordId: record.id,
        assetId: record.assetId,
        status: record.status,
        kind: record.kind,
        diagnostic: record.diagnostic ?? null,
      });
    }
  }

  return {
    exportInfo,
    timeline: timelineSection,
    assets: assetsSection,
    enrichment: enrichmentSection,
    diagnostics,
  };
}

// ---------------------------------------------------------------------------
// Output format handler
// ---------------------------------------------------------------------------

/**
 * Compile-only handler that produces stable metadata JSON.
 *
 * Receives read-only timeline and asset data through the
 * {@link OutputFormatContext}, serializes them into a deterministic
 * JSON payload with sorted keys, and returns the result as a
 * {@link CompileOnlyOutputResult}.
 *
 * The handler is synchronous — no async work is needed for metadata
 * serialization.
 */
const metadataJsonHandler: OutputFormatHandler = (
  context: OutputFormatContext,
): CompileOnlyOutputResult => {
  const payload = buildMetadataPayload(context);
  const json = stableStringify(payload);
  const encoder = new TextEncoder();
  const data = encoder.encode(json);

  const timestamp = new Date()
    .toISOString()
    .replace(/[:.]/g, '-')
    .replace('T', '_')
    .slice(0, 19); // YYYY-MM-DD_HH-mm-ss

  return {
    data,
    mimeType: 'application/json',
    filename: `metadata-export_${context.extensionId}_${timestamp}.json`,
    hasBlockingErrors: false,
    diagnostics: [],
  };
};

// ---------------------------------------------------------------------------
// Extension definition
// ---------------------------------------------------------------------------

export const metadataJsonOutputExtension: ReighExtension = defineExtension({
  manifest: {
    id: EXTENSION_ID as any,
    version: '1.0.0',
    label: 'Metadata JSON Output Example',
    description:
      'Adds a compile-only output format that serializes timeline identity, asset registry metadata, consent/provenance, deferred enrichment records, and parser diagnostics into stable JSON.',
    apiVersion: 1,
    contributions,
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    // Output format handlers are registered imperatively during activate().
    // The host's export registry associates handlers with the contribution
    // IDs declared in the manifest.  In M6 the registration surface is
    // exposed through ctx.creative.export or a dedicated export registry;
    // the exact registration API depends on the host runtime version.
    //
    // Example registration (pseudo-code for host API):
    //   return ctx.creative.export.registerOutputFormat(FORMAT_ID, metadataJsonHandler);
    //
    // For now, the handler is exported directly so consumers can wire it
    // themselves.

    return {
      dispose() {
        // No-op: handler lifecycle is managed by the host.
      },
    };
  },
});

// Re-export the handler so consumers can wire it without reaching into
// the extension internals.
export { metadataJsonHandler };
