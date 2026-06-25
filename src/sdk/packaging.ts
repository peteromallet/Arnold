/**
 * Core packaging contracts for the Reigh Editor SDK.
 *
 * Stable public types for extension dependency management, integrity
 * verification, migration declarations, and installed-package metadata.
 *
 * NOTE: InstalledExtensionPackage remains inline in index.ts because it
 * depends on ExtensionManifest, which is still defined in index.ts
 * (blocked on extraction of ~18 contribution type aliases to canonical
 * modules).  Once ExtensionManifest moves to manifest.ts, InstalledExtensionPackage
 * can move here with a direct import from '../manifest'.
 *
 * @publicContract
 */

import type { ExtensionId } from './ids';

// ---------------------------------------------------------------------------
// Dependency contracts
// ---------------------------------------------------------------------------

/** Posture of a dependency: required blocks activation, optional degrades. */
export type DependencyPosture = 'required' | 'optional';

/** A typed dependency declared by an extension. */
export interface ExtensionDependency {
  /** Extension ID this dependency references. */
  extensionId: string;
  /** Semver range (e.g. "^1.2.0", ">=2.0.0 <3.0.0"). */
  versionRange?: string;
  /** Specific contribution IDs required from the dependency. */
  contributionIds?: readonly string[];
  /** Whether this dependency was originally declared as optional. */
  optional?: boolean;
  /** Dependency posture: required blocks activation, optional allows degraded activation. */
  posture?: DependencyPosture;
}

// ---------------------------------------------------------------------------
// Integrity contracts
// ---------------------------------------------------------------------------

/** Supported integrity algorithms. */
export type IntegrityAlgorithm = 'sha256';

/** An SRI-style integrity hash. */
export interface IntegrityHash {
  algorithm: IntegrityAlgorithm;
  /** Base64-encoded hash value (without algorithm prefix). */
  value: string;
}

// ---------------------------------------------------------------------------
// Migration contracts
// ---------------------------------------------------------------------------

/** Kinds of migration hooks an extension may declare. */
export type MigrationHookKind = 'settings' | 'contribution' | 'manifest';

/** A typed migration declaration for extension upgrades. */
export interface MigrationDeclaration {
  kind: MigrationHookKind;
  /** Semver of the source version being migrated from. */
  fromVersion: string;
  /** Semver of the target version being migrated to. */
  toVersion: string;
  /** Handler identifier (module export name or inline function name). */
  handler?: string;
  /** Human-readable description of the migration. */
  description?: string;
}

// ---------------------------------------------------------------------------
// Installed-package metadata
// ---------------------------------------------------------------------------

/** Metadata recorded when an extension is installed as a trusted bundle. */
export interface InstalledExtensionMetadata {
  extensionId: ExtensionId;
  version: string;
  apiVersion?: number;
  /** Required: SHA-256 SRI integrity of the installed bundle. */
  integrity: IntegrityHash;
  /** ISO 8601 timestamp of installation. */
  installedAt?: string;
  /** Whether the extension is currently enabled. */
  enabled: boolean;
  /** Settings schema version at install time. */
  settingsSchemaVersion?: number;
  /** Resolved dependency graph at install time. */
  dependencies?: readonly ExtensionDependency[];
  /** Stored extension-scoped settings keyed by key. */
  settings?: Record<string, unknown>;
  /** Optional publisher identity for installed extensions. */
  publisher?: string;
  /** Optional SPDX license identifier. */
  license?: string;
  /** Optional icon URL or data URI. */
  icon?: string;
}
