/**
 * Extension lifecycle contracts and helpers for the Reigh Editor SDK.
 *
 * Defines the public extension shape, activation contract, and
 * defineExtension() factory.  This module is free of host wiring —
 * no DOM, localStorage, console, React lifecycle, requestAnimationFrame,
 * or provider-service imports.
 *
 * @publicContract
 */

import type { ExtensionContext } from './context';
import type { DisposeHandle } from './dispose';
import { validateExtensionId, validateContributionId } from './ids';

// ExtensionManifest is still inline in src/sdk/index.ts because it depends
// on ~18 contribution type aliases that have not yet been extracted to
// canonical modules (M2b).  import type is erased at compile time and
// introduces no runtime dependency on the barrel.
import type { ExtensionManifest } from '../index';

// ---------------------------------------------------------------------------
// Extension lifecycle
// ---------------------------------------------------------------------------

/** An extension's activate function. */
export type ExtensionActivateFn = (ctx: ExtensionContext) => DisposeHandle | void;

/** The public extension shape returned by defineExtension(). */
export interface ReighExtension {
  readonly manifest: Readonly<ExtensionManifest>;
  readonly activate?: ExtensionActivateFn;
}

// ---------------------------------------------------------------------------
// defineExtension()
// ---------------------------------------------------------------------------

/** Options passed to defineExtension(). */
export interface DefineExtensionOptions {
  manifest: ExtensionManifest;
  activate?: ExtensionActivateFn;
}

function freezeManifestValue<T>(value: T): T {
  if (ArrayBuffer.isView(value) || value instanceof ArrayBuffer) {
    return value;
  }
  if (Array.isArray(value)) {
    return Object.freeze(value.map((item) => freezeManifestValue(item))) as T;
  }
  if (value && typeof value === 'object') {
    const frozenEntries = Object.entries(value as Record<string, unknown>).map(
      ([key, entry]) => [key, freezeManifestValue(entry)],
    );
    return Object.freeze(Object.fromEntries(frozenEntries)) as T;
  }
  return value;
}

/**
 * Create a frozen ReighExtension from a manifest and optional activate function.
 * Validates the extension ID and contribution IDs, and preserves literal IDs
 * through the returned object.
 */
export function defineExtension(options: DefineExtensionOptions): ReighExtension {
  const { manifest, activate } = options;

  // Validate extension ID
  const idErrors = validateExtensionId(manifest.id);
  if (idErrors.length > 0) {
    throw new Error(`Invalid extension ID "${manifest.id}": ${idErrors.join('; ')}`);
  }

  // Validate contribution IDs for uniqueness
  if (manifest.contributions && manifest.contributions.length > 0) {
    const seen = new Set<string>();
    for (const contribution of manifest.contributions) {
      const cErrors = validateContributionId(contribution.id);
      if (cErrors.length > 0) {
        throw new Error(
          `Invalid contribution ID "${contribution.id}" in extension "${manifest.id}": ${cErrors.join('; ')}`,
        );
      }
      if (seen.has(contribution.id)) {
        throw new Error(
          `Duplicate contribution ID "${contribution.id}" in extension "${manifest.id}"`,
        );
      }
      seen.add(contribution.id);
    }
  }

  // Freeze the manifest deeply so literal IDs are preserved and the shape is immutable
  const frozenManifest: ExtensionManifest = Object.freeze({
    ...manifest,
    contributions: manifest.contributions ? freezeManifestValue(manifest.contributions) : undefined,
    permissions: manifest.permissions ? freezeManifestValue(manifest.permissions) : undefined,
    processes: manifest.processes ? freezeManifestValue(manifest.processes) : undefined,
    dependsOn: manifest.dependsOn ? freezeManifestValue(manifest.dependsOn) : undefined,
    migrations: manifest.migrations ? freezeManifestValue(manifest.migrations) : undefined,
    settingsDefaults: manifest.settingsDefaults ? freezeManifestValue(manifest.settingsDefaults) : undefined,
    settingsSchema: manifest.settingsSchema ? freezeManifestValue(manifest.settingsSchema) : undefined,
    messages: manifest.messages ? freezeManifestValue(manifest.messages) : undefined,
  });

  const extension: ReighExtension = Object.freeze({
    manifest: frozenManifest,
    activate,
  });

  return extension;
}
