import type {
  AssetMetadata,
  AssetMetadataConsent,
  AssetMetadataEnrichment,
  AssetMetadataEnrichmentClaim,
  AssetMetadataGPS,
  AssetMetadataIntegrity,
  AssetMetadataProvenance,
} from '../types/index.ts';

// ---------------------------------------------------------------------------
// Host-owned metadata field validators
// ---------------------------------------------------------------------------

const HOST_METADATA_KEYS = new Set([
  'integrity',
  'gps',
  'consent',
  'provenance',
  'enrichment',
  'extensions',
]);

const isValidString = (value: unknown): value is string =>
  typeof value === 'string' && value.length > 0;

const isOptionalString = (value: unknown): value is string | undefined =>
  value === undefined || isValidString(value);

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const isOptionalFiniteNumber = (value: unknown): value is number | undefined =>
  value === undefined || isFiniteNumber(value);

const isOptionalBoolean = (value: unknown): value is boolean | undefined =>
  value === undefined || typeof value === 'boolean';

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

const validateIntegrity = (input: unknown): AssetMetadataIntegrity | undefined => {
  if (!isPlainObject(input)) {
    return undefined;
  }

  const result: AssetMetadataIntegrity = {};
  let hasFields = false;

  const sha256 = input.sha256;
  if (isValidString(sha256)) {
    result.sha256 = sha256;
    hasFields = true;
  }

  const md5 = input.md5;
  if (isValidString(md5)) {
    result.md5 = md5;
    hasFields = true;
  }

  const crc32 = input.crc32;
  if (isValidString(crc32)) {
    result.crc32 = crc32;
    hasFields = true;
  }

  return hasFields ? result : undefined;
};

const validateGPS = (input: unknown): AssetMetadataGPS | undefined => {
  if (!isPlainObject(input)) {
    return undefined;
  }

  const result: AssetMetadataGPS = {};
  let hasFields = false;

  const latitude = input.latitude;
  if (isFiniteNumber(latitude)) {
    result.latitude = latitude;
    hasFields = true;
  }

  const longitude = input.longitude;
  if (isFiniteNumber(longitude)) {
    result.longitude = longitude;
    hasFields = true;
  }

  const altitude = input.altitude;
  if (isFiniteNumber(altitude)) {
    result.altitude = altitude;
    hasFields = true;
  }

  const horizontalAccuracy = input.horizontalAccuracy;
  if (isFiniteNumber(horizontalAccuracy)) {
    result.horizontalAccuracy = horizontalAccuracy;
    hasFields = true;
  }

  const timestamp = input.timestamp;
  if (isValidString(timestamp)) {
    result.timestamp = timestamp;
    hasFields = true;
  }

  return hasFields ? result : undefined;
};

const validateConsent = (input: unknown): AssetMetadataConsent | undefined => {
  if (!isPlainObject(input)) {
    return undefined;
  }

  const result: AssetMetadataConsent = {};
  let hasFields = false;

  if (typeof input.modelRelease === 'boolean') {
    result.modelRelease = input.modelRelease;
    hasFields = true;
  }

  if (typeof input.propertyRelease === 'boolean') {
    result.propertyRelease = input.propertyRelease;
    hasFields = true;
  }

  const rightsHolder = input.rightsHolder;
  if (isValidString(rightsHolder)) {
    result.rightsHolder = rightsHolder;
    hasFields = true;
  }

  const license = input.license;
  if (isValidString(license)) {
    result.license = license;
    hasFields = true;
  }

  const usageTerms = input.usageTerms;
  if (isValidString(usageTerms)) {
    result.usageTerms = usageTerms;
    hasFields = true;
  }

  return hasFields ? result : undefined;
};

const validateProvenance = (input: unknown): AssetMetadataProvenance | undefined => {
  if (!isPlainObject(input)) {
    return undefined;
  }

  const result: AssetMetadataProvenance = {};
  let hasFields = false;

  const importTimestamp = input.importTimestamp;
  if (isValidString(importTimestamp)) {
    result.importTimestamp = importTimestamp;
    hasFields = true;
  }

  const sourceUrl = input.sourceUrl;
  if (isValidString(sourceUrl)) {
    result.sourceUrl = sourceUrl;
    hasFields = true;
  }

  const sourceProvider = input.sourceProvider;
  if (isValidString(sourceProvider)) {
    result.sourceProvider = sourceProvider;
    hasFields = true;
  }

  const importedBy = input.importedBy;
  if (isValidString(importedBy)) {
    result.importedBy = importedBy;
    hasFields = true;
  }

  const originalFilename = input.originalFilename;
  if (isValidString(originalFilename)) {
    result.originalFilename = originalFilename;
    hasFields = true;
  }

  return hasFields ? result : undefined;
};

const validateEnrichmentClaim = (input: unknown): AssetMetadataEnrichmentClaim | null => {
  if (!isPlainObject(input)) {
    return null;
  }

  if (!isValidString(input.claimId) || !isValidString(input.parserId) || !isValidString(input.timestamp)) {
    return null;
  }

  const claim: AssetMetadataEnrichmentClaim = {
    claimId: input.claimId,
    parserId: input.parserId,
    timestamp: input.timestamp,
  };

  const field = input.field;
  if (isOptionalString(field)) {
    claim.field = field;
  }

  const summary = input.summary;
  if (isOptionalString(summary)) {
    claim.summary = summary;
  }

  return claim;
};

const validateEnrichment = (input: unknown): AssetMetadataEnrichment | undefined => {
  if (!isPlainObject(input)) {
    return undefined;
  }

  const result: AssetMetadataEnrichment = {};
  let hasFields = false;

  const pending = input.pending;
  if (isOptionalFiniteNumber(pending) && (pending as number) >= 0) {
    result.pending = pending;
    hasFields = true;
  }

  const failed = input.failed;
  if (isOptionalFiniteNumber(failed) && (failed as number) >= 0) {
    result.failed = failed;
    hasFields = true;
  }

  const claims = input.claims;
  if (Array.isArray(claims)) {
    const validatedClaims = claims
      .map(validateEnrichmentClaim)
      .filter((claim): claim is AssetMetadataEnrichmentClaim => claim !== null);
    if (validatedClaims.length > 0) {
      result.claims = validatedClaims;
      hasFields = true;
    }
  }

  return hasFields ? result : undefined;
};

const validateExtensions = (input: unknown): Record<string, unknown> | undefined => {
  if (isPlainObject(input)) {
    const filtered: Record<string, unknown> = {};
    let hasEntries = false;
    for (const [key, value] of Object.entries(input)) {
      if (isValidString(key) && value !== undefined) {
        filtered[key] = value;
        hasEntries = true;
      }
    }
    return hasEntries ? filtered : undefined;
  }
  return undefined;
};

// ---------------------------------------------------------------------------
// Public validation entry point
// ---------------------------------------------------------------------------

/**
 * Validates and normalizes an asset metadata object.
 *
 * Only known host-owned top-level keys (`integrity`, `gps`, `consent`,
 * `provenance`, `enrichment`, `extensions`) are preserved; any unknown keys
 * at the metadata top-level are silently stripped. Extension-owned metadata
 * under `extensions[extensionId]` is kept as-is (opaque to the host).
 *
 * Returns `undefined` when the input is not a plain object or when no valid
 * metadata fields remain after validation.
 */
export const validateAssetMetadata = (input: unknown): AssetMetadata | undefined => {
  if (!isPlainObject(input)) {
    return undefined;
  }

  const result: AssetMetadata = {};
  let hasFields = false;

  const integrity = validateIntegrity(input.integrity);
  if (integrity) {
    result.integrity = integrity;
    hasFields = true;
  }

  const gps = validateGPS(input.gps);
  if (gps) {
    result.gps = gps;
    hasFields = true;
  }

  const consent = validateConsent(input.consent);
  if (consent) {
    result.consent = consent;
    hasFields = true;
  }

  const provenance = validateProvenance(input.provenance);
  if (provenance) {
    result.provenance = provenance;
    hasFields = true;
  }

  const enrichment = validateEnrichment(input.enrichment);
  if (enrichment) {
    result.enrichment = enrichment;
    hasFields = true;
  }

  const extensions = validateExtensions(input.extensions);
  if (extensions) {
    result.extensions = extensions;
    hasFields = true;
  }

  // Reject any unknown top-level metadata keys (they are silently stripped).
  // Only the six known keys above are ever included in the result.

  return hasFields ? result : undefined;
};
