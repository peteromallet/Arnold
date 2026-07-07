Reading additional input from stdin...
OpenAI Codex v0.137.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/reigh-app
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019f3a0c-4cd5-7071-ae8a-2c0b9c99f726
--------
user
# Codex Sense-Check: Permission Model Truth

Repo: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`

Run read-only. Do not edit files.

## Task

Investigate the current threat and best next move for the Reigh extension permission/trust model.

The criticism to evaluate:

> Manifests declare permissions that nothing enforces. Either enforce permissions at runtime through sandboxing/capability gating, or strip declarative theater and lean fully into the trusted-code model.

## What To Inspect

Prioritize current code over old docs:

- `src/sdk/index.ts`
- `config/contracts/reigh-extension.schema.json`
- `src/tools/video-editor/runtime/extensionManifest.ts`
- `src/tools/video-editor/runtime/extensionLoader.ts`
- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/extensionPackageManifest.ts`
- `src/tools/video-editor/components/ExtensionManager/**`
- `docs/extensions/compatibility.md`
- `docs/extensions/authoring.md`
- `docs/extensions/loading.md`
- `docs/extensions/phase4-readiness.md`
- `docs/video-editor/extension-platform-supported-deferred.md`
- `scripts/quality/**` relevant to extension claims
- checked-in example manifests under `src/tools/video-editor/examples/extensions/**/reigh-extension.json`

## Questions

1. What permission declarations exist today, and are any actually enforced?
2. Where could a user/developer reasonably infer false safety from manifest permissions?
3. Is real runtime enforcement/sandboxing feasible as a near-term foundation completion task, or should the pristine move be honesty-first docs/schema/UI?
4. What would a truly pristine permission/trust model look like for this codebase?
5. What is the smallest high-leverage plan to get there without overbuilding?

## Output

Markdown under 1800 words:

# Permission Model Truth
## Verdict
Say whether the criticism is valid and how severe the threat is.
## Current Code Reality
Concrete files and facts.
## Pristine End State
What the model should become.
## Recommended Work
Ranked actions, with "now" vs "later".
## Tests / Gates
Specific tests/scripts/docs checks needed.
## Biggest Trap
The tempting but wrong thing to do.
codex
I’ll keep this read-only and focus on current code first, then use the docs only to identify places that imply safety. Since this is a broad inspection task, I’m going to use the repo’s context-minimizing posture and dispatch focused read/search work where useful, then synthesize the conclusion here.
codex
The first broad search confirms one important thing already: a referenced `extensionManifest.ts` path no longer exists, while `extensionPackageManifest.ts` is the current manifest validator. I’m narrowing from the noisy repo-wide hits into the specific type definitions, schema, loader path, UI copy, and quality gates.
exec
/bin/zsh -lc "sed -n '1,260p' src/sdk/index.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
/**
 * @reigh/editor-sdk — Public SDK entrypoint
 *
 * Stable public types and helpers for trusted local extensions.
 * This module must NOT import from editor internals (DataProvider,
 * raw timeline ops, editor runtime contexts, or internal mutation APIs).
 *
 * @publicContract
 */

import { createExtensionSettingsService } from './extensionSettingsService';
import { runSettingsMigration, getManifestSettingsSchemaVersion } from './extensionSettingsMigration';

// ---------------------------------------------------------------------------
// ID validation
// ---------------------------------------------------------------------------

/** A non-empty string that uniquely identifies an extension or contribution. */
export type ExtensionId = string & { readonly __brand: 'ExtensionId' };

/** A non-empty string that uniquely identifies a contribution within an extension. */
export type ContributionId = string & { readonly __brand: 'ContributionId' };

const ID_RE = /^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)*$/i;

/**
 * Validate an extension or contribution ID.
 * Returns an array of error messages (empty = valid).
 */
export function validateExtensionId(id: string): string[] {
  const errors: string[] = [];
  if (typeof id !== 'string' || id.length === 0) {
    errors.push('ID must be a non-empty string');
    return errors;
  }
  if (id.length > 128) {
    errors.push('ID must be 128 characters or fewer');
  }
  if (!ID_RE.test(id)) {
    errors.push(
      "ID must match /^[a-z][a-z0-9_-]*(\\.[a-z][a-z0-9_-]*)*$/i " +
        '(lowercase start, dot-separated segments of letters/digits/hyphens/underscores)',
    );
  }
  return errors;
}

/**
 * Validate a contribution ID. Same rules as extension IDs.
 */
export function validateContributionId(id: string): string[] {
  return validateExtensionId(id);
}

// ---------------------------------------------------------------------------
// DisposeHandle
// ---------------------------------------------------------------------------

/** A handle returned by lifecycle methods that require cleanup. */
export interface DisposeHandle {
  /** Synchronous, idempotent, must not throw. */
  dispose(): void;
  /** Optional explicit resource management support. */
  readonly [Symbol.dispose]?: () => void;
}

// ---------------------------------------------------------------------------
// Diagnostics
// ---------------------------------------------------------------------------

export type DiagnosticSeverity = 'error' | 'warning' | 'info';

/**
 * Diagnostic provenance source.
 *
 * - `extension` — authored by a trusted local extension (the only source
 *   extensions themselves can produce).  The SDK pins this value for
 *   extension-reported diagnostics.
 * - `render` — emitted by the host render pipeline.
 * - `provider` — emitted by a host provider (editor runtime, etc.).
 *
 * Extensions MUST NOT set host-owned sources.
 */
export type DiagnosticSource = 'extension' | 'render' | 'provider';

/** The only diagnostic source extensions are permitted to use. */
export const DIAGNOSTIC_SOURCE_EXTENSION: DiagnosticSource = 'extension';

export interface ExtensionDiagnostic {
  severity: DiagnosticSeverity;
  code: string;
  message: string;
  extensionId?: string;
  contributionId?: string;
  /** The earliest milestone that is expected to activate this feature. */
  milestone?: string;
  /**
   * Diagnostic provenance source.
   * Extension-authored diagnostics always use {@link DIAGNOSTIC_SOURCE_EXTENSION}.
   */
  source?: DiagnosticSource;
  /** Additional structured detail (clip reference, effect ID, etc.). */
  detail?: Record<string, unknown>;
}

export interface DiagnosticSourceRange {
  startLine: number;
  startCol: number;
  endLine: number;
  endCol: number;
}

export interface Diagnostic extends ExtensionDiagnostic {
  id: string;
  sourceRange?: DiagnosticSourceRange;
  relatedRanges?: readonly DiagnosticSourceRange[];
}

export interface DiagnosticCollection {
  readonly snapshot: readonly Diagnostic[];
  publish(diagnostic: Diagnostic): void;
  remove(predicate: (diagnostic: Diagnostic) => boolean): void;
  /** Remove all diagnostics belonging to the given extension ID. */
  removeByExtensionId(extensionId: string): void;
  clear(): void;
  subscribe(listener: () => void): DisposeHandle;
  getSnapshot(): readonly Diagnostic[];
}

/** Default per-extension diagnostic capacity before oldest-first eviction. */
export const DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY = 100;

function freezeDiagnostic(diagnostic: Diagnostic): Diagnostic {
  return Object.freeze({
    ...diagnostic,
    ...(diagnostic.sourceRange ? { sourceRange: Object.freeze({ ...diagnostic.sourceRange }) } : {}),
    ...(diagnostic.relatedRanges
      ? { relatedRanges: Object.freeze(diagnostic.relatedRanges.map((range) => Object.freeze({ ...range }))) }
      : {}),
    ...(diagnostic.detail ? { detail: Object.freeze({ ...diagnostic.detail }) } : {}),
  });
}

export interface CreateDiagnosticCollectionOptions {
  /**
   * Maximum number of diagnostics allowed per extension ID.
   * When publishing a new diagnostic (not replacing an existing one by ID)
   * would exceed this limit, the oldest diagnostic for that extension is
   * evicted before the new one is added.
   * @default {@link DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY}
   */
  perExtensionCapacity?: number;
}

export function createDiagnosticCollection(
  initialDiagnostics: readonly Diagnostic[] = [],
  options: CreateDiagnosticCollectionOptions = {},
): DiagnosticCollection {
  const capacity = options.perExtensionCapacity ?? DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY;
  const diagnostics: Diagnostic[] = initialDiagnostics.map(freezeDiagnostic);
  const listeners = new Set<() => void>();
  let snapshot: readonly Diagnostic[] = Object.freeze([...diagnostics]);

  const publishSnapshot = () => {
    snapshot = Object.freeze([...diagnostics]);
    for (const listener of listeners) {
      listener();
    }
  };

  const evictOldestForExtension = (extensionId: string): void => {
    // Find the oldest (lowest index) diagnostic for this extension
    for (let i = 0; i < diagnostics.length; i += 1) {
      if (diagnostics[i].extensionId === extensionId) {
        diagnostics.splice(i, 1);
        return; // only evict one — the oldest
      }
    }
  };

  return {
    get snapshot(): readonly Diagnostic[] {
      return snapshot;
    },
    publish(diagnostic: Diagnostic): void {
      const frozen = freezeDiagnostic(diagnostic);
      const existingIndex = diagnostics.findIndex((item) => item.id === frozen.id);
      if (existingIndex >= 0) {
        // Replace in-place — does NOT count toward capacity
        diagnostics[existingIndex] = frozen;
      } else {
        // New diagnostic: enforce per-extension capacity
        const extId = frozen.extensionId;
        if (extId) {
          const extCount = diagnostics.reduce(
            (count, d) => count + (d.extensionId === extId ? 1 : 0),
            0,
          );
          if (extCount >= capacity) {
            evictOldestForExtension(extId);
          }
        }
        diagnostics.push(frozen);
      }
      publishSnapshot();
    },
    remove(predicate: (diagnostic: Diagnostic) => boolean): void {
      let changed = false;
      for (let index = diagnostics.length - 1; index >= 0; index -= 1) {
        if (predicate(diagnostics[index])) {
          diagnostics.splice(index, 1);
          changed = true;
        }
      }
      if (changed) {
        publishSnapshot();
      }
    },
    removeByExtensionId(extensionId: string): void {
      let changed = false;
      for (let index = diagnostics.length - 1; index >= 0; index -= 1) {
        if (diagnostics[index].extensionId === extensionId) {
          diagnostics.splice(index, 1);
          changed = true;
        }
      }
      if (changed) {
        publishSnapshot();
      }
    },
    clear(): void {
      if (diagnostics.length === 0) return;
      diagnostics.length = 0;
      publishSnapshot();
    },
    subscribe(listener: () => void): DisposeHandle {
      listeners.add(listener);
      return {
        dispose(): void {
          listeners.delete(listener);
        },
      };
    },
    getSnapshot(): readonly Diagnostic[] {
      return snapshot;
    },
  };
}

/**
 * An export-scoped diagnostic produced by the pre-render export guard.
 * Carries the same shape as {@link ExtensionDiagnostic} but uses
 * export-prefixed diagnostic codes (e.g. `export/unknown-clip-type`)
 * and includes timeline-specific detail (clip ID, effect name, etc.).
 */
export interface ExportDiagnostic extends ExtensionDiagnostic {
  /** The diagnostic code is always an export-prefixed string. */
  code: `export/${string}`;
  /** Timeline-scoped detail such as clip ID, effect/transition name. */
  detail?: Record<string, unknown> & {

exec
/bin/zsh -lc "sed -n '1,260p' config/contracts/reigh-extension.schema.json" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "sed -n '1,260p' src/tools/video-editor/runtime/extensionLoader.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://reigh.ai/contracts/reigh-extension.schema.json",
  "title": "Reigh Extension Manifest",
  "description": "Frozen manifest contract for Reigh editor extensions. Validates contribution kind enums, discriminated shapes, placement rules, and rejects unknown top-level collections.",
  "type": "object",
  "required": ["id", "version", "label"],
  "additionalProperties": false,
  "properties": {
    "id": {
      "type": "string",
      "description": "Extension ID — non-empty, lowercase start, dot-separated segments of letters/digits/hyphens/underscores, max 128 chars.",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[a-z][a-z0-9_-]*(\\.[a-z][a-z0-9_-]*)*$"
    },
    "version": {
      "type": "string",
      "description": "Semver version string (e.g. '1.0.0').",
      "pattern": "^\\d+\\.\\d+\\.\\d+"
    },
    "label": {
      "type": "string",
      "description": "Human-readable extension label.",
      "minLength": 1
    },
    "description": {
      "type": "string",
      "description": "Optional description of the extension."
    },
    "apiVersion": {
      "type": "integer",
      "description": "API version this extension targets (positive integer).",
      "minimum": 1
    },
    "contributions": {
      "type": "array",
      "description": "Contribution declarations.",
      "items": {
        "$ref": "#/definitions/Contribution"
      }
    },
    "permissions": {
      "type": "array",
      "description": "Descriptive permission metadata.",
      "items": {
        "$ref": "#/definitions/ExtensionPermissionDeclaration"
      }
    },
    "processes": {
      "type": "array",
      "description": "Process declarations.",
      "items": {
        "$ref": "#/definitions/ProcessManifestEntry"
      }
    },
    "migrations": {
      "type": "array",
      "description": "Typed migration hooks or legacy record entries."
    },
    "comments": {
      "type": "string",
      "description": "Human-readable comments."
    },
    "dependsOn": {
      "type": "array",
      "description": "Typed dependency declarations.",
      "items": {
        "$ref": "#/definitions/ExtensionDependency"
      }
    },
    "renderability": {
      "type": "object",
      "description": "Renderability descriptors."
    },
    "settingsDefaults": {
      "type": "object",
      "description": "Extension-scoped settings defaults."
    },
    "settingsSchema": {
      "$ref": "#/definitions/ExtensionSettingsSchema"
    },
    "messages": {
      "type": "object",
      "description": "Bundled i18n messages keyed by locale-neutral key.",
      "additionalProperties": {
        "type": "string"
      }
    },
    "publisher": {
      "type": "string",
      "description": "Publisher identity."
    },
    "license": {
      "type": "string",
      "description": "SPDX license identifier."
    },
    "icon": {
      "type": "string",
      "description": "Icon URL or data URI."
    }
  },

  "definitions": {
    "ContributionId": {
      "type": "string",
      "description": "Contribution ID — same rules as extension ID.",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[a-z][a-z0-9_-]*(\\.[a-z][a-z0-9_-]*)*$"
    },

    "ContributionKind": {
      "type": "string",
      "description": "Known contribution kinds matching the SDK ContributionKind enum.",
      "enum": [
        "slot",
        "dialog",
        "panel",
        "inspectorSection",
        "timelineOverlay",
        "command",
        "keybinding",
        "contextMenuItem",
        "parser",
        "outputFormat",
        "searchProvider",
        "metadataFacet",
        "assetDetailSection",
        "process",
        "effect",
        "transition",
        "clipType",
        "shader",
        "automation",
        "agentTool",
        "agent"
      ]
    },

    "SlotName": {
      "type": "string",
      "description": "Slot names recognized by the host shell.",
      "enum": [
        "header",
        "toolbar",
        "leftPanel",
        "rightPanel",
        "codePanel",
        "writingPanel",
        "stagePanel",
        "timelineFooter",
        "statusBar",
        "dialogs",
        "assetPanel",
        "inspectorPanel"
      ]
    },

    "Contribution": {
      "oneOf": [
        { "$ref": "#/definitions/SlotContribution" },
        { "$ref": "#/definitions/DialogContribution" },
        { "$ref": "#/definitions/PanelContribution" },
        { "$ref": "#/definitions/InspectorSectionContribution" },
        { "$ref": "#/definitions/TimelineOverlayContribution" },
        { "$ref": "#/definitions/CommandContribution" },
        { "$ref": "#/definitions/KeybindingContribution" },
        { "$ref": "#/definitions/ContextMenuItemContribution" },
        { "$ref": "#/definitions/ParserContribution" },
        { "$ref": "#/definitions/OutputFormatContribution" },
        { "$ref": "#/definitions/SearchProviderContribution" },
        { "$ref": "#/definitions/MetadataFacetContribution" },
        { "$ref": "#/definitions/AssetDetailSectionContribution" },
        { "$ref": "#/definitions/ProcessContribution" },
        { "$ref": "#/definitions/EffectContribution" },
        { "$ref": "#/definitions/TransitionContribution" },
        { "$ref": "#/definitions/ClipTypeContribution" },
        { "$ref": "#/definitions/ShaderContribution" },
        { "$ref": "#/definitions/AutomationContribution" },
        { "$ref": "#/definitions/AgentToolContribution" },
        { "$ref": "#/definitions/AgentContribution" }
      ]
    },

    "SlotContribution": {
      "type": "object",
      "description": "Slot contribution: renders into a named host shell slot. Must NOT specify placement.",
      "required": ["id", "kind"],
      "additionalProperties": false,
      "properties": {
        "id": { "$ref": "#/definitions/ContributionId" },
        "kind": { "const": "slot" },
        "order": { "type": "number", "description": "Lower values sort first. Default 0." },
        "slot": { "$ref": "#/definitions/SlotName" },
        "label": { "type": "string" },
        "when": { "type": "string" }
      }
    },

    "DialogContribution": {
      "type": "object",
      "description": "Dialog contribution: renders into a named dialog layer.",
      "required": ["id", "kind"],
      "additionalProperties": false,
      "properties": {
        "id": { "$ref": "#/definitions/ContributionId" },
        "kind": { "const": "dialog" },
        "order": { "type": "number" },
        "layer": { "enum": ["modal", "overlay"] },
        "label": { "type": "string" },
        "when": { "type": "string" }
      }
    },

    "PanelContribution": {
      "type": "object",
      "description": "Panel contribution: placement must be 'asset-panel' when specified.",
      "required": ["id", "kind"],
      "additionalProperties": false,
      "properties": {
        "id": { "$ref": "#/definitions/ContributionId" },
        "kind": { "const": "panel" },
        "order": { "type": "number" },
        "placement": {
          "type": "string",
          "description": "Panel placement is limited to 'asset-panel'.",
          "enum": ["asset-panel"]
        },
        "label": { "type": "string" },
        "when": { "type": "string" }
      }
    },

    "InspectorSectionContribution": {
      "type": "object",
      "description": "Inspector section contribution: placement 'before-default' or 'after-default'.",
      "required": ["id", "kind"],
      "additionalProperties": false,
      "properties": {
        "id": { "$ref": "#/definitions/ContributionId" },
        "kind": { "const": "inspectorSection" },
        "order": { "type": "number" },
        "placement": {
          "type": "string",
          "enum": ["before-default", "after-default"]
        },
        "label": { "type": "string" },
        "when": { "type": "string" }
      }
    },

    "TimelineOverlayContribution": {
      "type": "object",
      "description": "Timeline overlay contribution: renders over the timeline surface.",
      "required": ["id", "kind"],
      "additionalProperties": false,
      "properties": {
        "id": { "$ref": "#/definitions/ContributionId" },
        "kind": { "const": "timelineOverlay" },

 succeeded in 0ms:
/**
 * ExtensionLoader core (M14, T11/T12).
 *
 * Validates, loads, and unloads direct/source and installed extension pack
 * records through manifest/integrity validation, resolves dependencies,
 * isolates per-pack failures, and emits diagnostics/lifecycle events without
 * owning global state.
 *
 * The loader feeds the existing provider-scoped ExtensionLifecycleHost pipeline
 * (SD1): it validates/enriches ReighExtension[] before feeding it to the
 * existing lifecycle host's synchronize() method.
 */

import type {
  ReighExtension,
  ExtensionManifest,
  ExtensionDiagnostic,
  InstalledExtensionPackage,
  ExtensionDependency,
  DependencyPosture,
} from '@reigh/editor-sdk';
import { defineExtension } from '@reigh/editor-sdk';
import type {
  ExtensionPackRecord,
  ExtensionStateRepository,
  ExtensionLifecycleEvent,
  DevOverrideState,
  ExtensionEnablementState,
} from '@/tools/video-editor/runtime/extensionStateRepository';
import { createLifecycleEvent } from '@/tools/video-editor/runtime/extensionStateRepository';
import type {
  PackageValidationResult,
  ValidatedPackage,
  WorkspaceSourcePackage,
  InstalledBundlePackage,
} from '@/tools/video-editor/runtime/extensionPackageManifest';
import {
  validateWorkspaceSourcePackage,
  validateInstalledBundlePackage,
} from '@/tools/video-editor/runtime/extensionPackageManifest';
import {
  verifyIntegrity,
} from '@/tools/video-editor/runtime/extensionIntegrity';
import {
  syncEnabledPackLockEntries,
} from '@/tools/video-editor/runtime/extensionLockMetadata';

// ---------------------------------------------------------------------------
// Semver helpers
// ---------------------------------------------------------------------------

/** Parse a semver string into [major, minor, patch] or null. */
function parseSemver(version: string): [number, number, number] | null {
  const match = /^(\d+)\.(\d+)\.(\d+)/.exec(version.trim());
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

/** Compare two semver tuples: negative if a < b, 0 if equal, positive if a > b. */
function compareSemver(
  a: [number, number, number],
  b: [number, number, number],
): number {
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return 0;
}

/**
 * Check whether a semver version satisfies a version-range expression.
 *
 * Supports:
 *   - Exact: "1.2.3"
 *   - Caret: "^1.2.3"  (>=1.2.3 <2.0.0)
 *   - Tilde: "~1.2.3"  (>=1.2.3 <1.3.0)
 *   - GTE:  ">=1.2.3"
 *   - LTE:  "<=1.2.3"
 *   - GT:   ">1.2.3"
 *   - LT:   "<1.2.3"
 *   - Hyphen range: "1.2.3 - 2.0.0"  (>=1.2.3 <=2.0.0)
 *   - Space-separated AND conjunction: ">=1.0.0 <2.0.0"
 *   - `x` / `*` wildcards: "1.x" = ">=1.0.0 <2.0.0", "1.2.x" = ">=1.2.0 <1.3.0"
 *
 * Returns false when version or range cannot be parsed.
 */
export function satisfiesSemverRange(version: string, range: string): boolean {
  const parsed = parseSemver(version);
  if (!parsed) return false;

  const trimmed = range.trim();

  // Wildcard / x-range: "1.x", "1.2.x", "1.*", "*"
  const wildcardMatch = /^(\d+)(?:\.(?:(\d+)|[x*]))?(?:\.(?:(\d+)|[x*]))?$/.exec(trimmed);
  if (wildcardMatch && trimmed.includes('x') || (wildcardMatch && trimmed.includes('*'))) {
    // Already handled by the regex — parse the version constraints
  }
  if (/^(\d+)(?:\.(?:(\d+)|[x*]))?(?:\.(?:(\d+)|[x*]))?$/.test(trimmed) && (trimmed.includes('x') || trimmed.includes('*'))) {
    const m = /^(\d+)(?:\.(?:(\d+)|[x*]))?(?:\.(?:(\d+)|[x*]))?$/.exec(trimmed)!;
    const major = Number(m[1]);
    const minorRaw = m[2];
    const patchRaw = m[3];
    if (!minorRaw || minorRaw === 'x' || minorRaw === '*') {
      // 1.x or 1.* → >=1.0.0 <2.0.0
      return parsed[0] === major;
    }
    if (!patchRaw || patchRaw === 'x' || patchRaw === '*') {
      // 1.2.x or 1.2.* → >=1.2.0 <1.3.0
      return parsed[0] === major && parsed[1] === Number(minorRaw);
    }
  }

  // Caret: ^1.2.3 → >=1.2.3 <2.0.0
  if (trimmed.startsWith('^')) {
    const v = parseSemver(trimmed.slice(1));
    if (!v) return false;
    const upper: [number, number, number] = v[0] === 0
      ? (v[1] === 0 ? [0, 0, v[2] + 1] : [0, v[1] + 1, 0])
      : [v[0] + 1, 0, 0];
    return compareSemver(parsed, v) >= 0 && compareSemver(parsed, upper) < 0;
  }

  // Tilde: ~1.2.3 → >=1.2.3 <1.3.0
  if (trimmed.startsWith('~')) {
    const v = parseSemver(trimmed.slice(1));
    if (!v) return false;
    const upper: [number, number, number] = [v[0], v[1] + 1, 0];
    return compareSemver(parsed, v) >= 0 && compareSemver(parsed, upper) < 0;
  }

  // Hyphen range: "1.2.3 - 2.0.0" → >=1.2.3 <=2.0.0
  const hyphenMatch = /^\s*(\S+)\s+-\s+(\S+)\s*$/.exec(trimmed);
  if (hyphenMatch) {
    const lo = parseSemver(hyphenMatch[1]);
    const hi = parseSemver(hyphenMatch[2]);
    if (!lo || !hi) return false;
    return compareSemver(parsed, lo) >= 0 && compareSemver(parsed, hi) <= 0;
  }

  // Space-separated conjunction: ">=1.0.0 <2.0.0"
  const parts = trimmed.split(/\s+/).filter(Boolean);
  if (parts.length > 1) {
    return parts.every((part) => satisfiesSemverRange(version, part));
  }

  // Single operator: >=, <=, >, <, =
  const opMatch = /^(>=|<=|>|<|=)?(.+)$/.exec(trimmed);
  if (opMatch) {
    const op = opMatch[1] || '=';
    const target = parseSemver(opMatch[2]);
    if (!target) return false;
    const cmp = compareSemver(parsed, target);
    switch (op) {
      case '>=': return cmp >= 0;
      case '<=': return cmp <= 0;
      case '>': return cmp > 0;
      case '<': return cmp < 0;
      case '=':
      default: return cmp === 0;
    }
  }

  // Fallback: exact version match
  const exact = parseSemver(trimmed);
  if (!exact) return false;
  return compareSemver(parsed, exact) === 0;
}

// ---------------------------------------------------------------------------
// Dependency resolution types
// ---------------------------------------------------------------------------

/** Resolution status for a single dependency. */
export interface DependencyStatus {
  /** The dependency extension ID. */
  readonly dependencyId: string;
  /** Whether the dependency was found in the load set. */
  readonly found: boolean;
  /** Whether the version range is satisfied (true when no range specified). */
  readonly versionSatisfied: boolean;
  /** The required version range (if any). */
  readonly versionRange?: string;
  /** The actual version of the resolved dependency (if found). */
  readonly actualVersion?: string;
  /** The dependency posture. */
  readonly posture: DependencyPosture;
  /** Specific contribution IDs required from the dependency. */
  readonly contributionIds?: readonly string[];
}

/** Resolution result for a single extension. */
export interface DependencyResolutionEntry {
  /** The extension ID being resolved. */
  readonly extensionId: string;
  /** Per-dependency status entries. */
  readonly dependencies: readonly DependencyStatus[];
  /** Dependencies that are fully satisfied (found + version ok). */
  readonly satisfied: readonly string[];
  /** Missing required dependencies. */
  readonly missingRequired: readonly string[];
  /** Missing optional dependencies. */
  readonly missingOptional: readonly string[];
  /** Version mismatches for required dependencies. */
  readonly versionMismatchRequired: readonly string[];
  /** Version mismatches for optional dependencies. */
  readonly versionMismatchOptional: readonly string[];
  /** Whether all required dependencies are satisfied. */
  readonly allRequiredSatisfied: boolean;
  /** Whether the extension can activate (all required satisfied, not in a cycle). */
  readonly canActivate: boolean;
  /** Whether activation is degraded (optional dependencies missing/mismatched). */
  readonly degraded: boolean;
  /** Whether the extension is part of a dependency cycle. */
  readonly inCycle: boolean;
  /** IDs of extensions in the same cycle (empty if not in a cycle). */
  readonly cycleExtensionIds: readonly string[];
  /** Blocking diagnostics. */
  readonly blockingDiagnostics: readonly ExtensionDiagnostic[];
  /** Degradation diagnostics. */
  readonly degradationDiagnostics: readonly ExtensionDiagnostic[];
}

/** Aggregate dependency resolution result. */
export interface DependencyResolutionResult {
  /** Per-extension resolution entries. */
  readonly entries: readonly DependencyResolutionEntry[];
  /** Extensions that should be blocked from loading. */
  readonly blockedExtensionIds: ReadonlySet<string>;
  /** Degraded extension IDs (those with only optional issues). */
  readonly degradedExtensionIds: ReadonlySet<string>;
  /** All diagnostics from resolution. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Cycle detection
// ---------------------------------------------------------------------------

/**
 * Detect all extension IDs that are part of any dependency cycle.
 *
 * Builds a directed graph where edge A→B means A depends on B (any posture).
 * Returns a set of extension IDs reachable from any cycle.
 */
function detectDependencyCycles(
  packages: readonly ValidatedPackage[],
): {
  /** All extension IDs involved in at least one cycle. */
  cycleIds: ReadonlySet<string>;
  /** Map from extension ID to the cycle it belongs to (empty array if not in cycle). */
  cycleGroups: ReadonlyMap<string, readonly string[]>;
} {
  // Build adjacency: extId → dependsOn IDs (all postures)
  const adjacency = new Map<string, Set<string>>();
  for (const pkg of packages) {
    const manifest = pkg.form === 'workspace-source'
      ? (pkg as WorkspaceSourcePackage).manifest
      : (pkg as InstalledBundlePackage).pack.manifest;
    const extId = manifest.id as string;
    const deps = manifest.dependsOn ?? [];

exec
/bin/zsh -lc "sed -n '1,520p' src/tools/video-editor/runtime/extensionPackageManifest.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
/**
 * Package manifest validation for extension loading and installation.
 *
 * Distinguishes two accepted package forms:
 *   1. Workspace source package: a local `reigh-extension.json` consumed as a
 *      `ReighExtension` object during development.
 *   2. Installed trusted bundle: an installed pack with `manifest.json` +
 *      `bundle.mjs` and integrity-tracked `InstalledExtensionMetadata`.
 *
 * Diagnostics produced by this module clearly separate:
 *   - Workspace source warnings (missing fields recommended for installation).
 *   - Installed-pack blockers (strict errors that prevent activation).
 */

import {
  validateManifest,
  validateInstalledPackage,
  validateExtensionId,
  validateContributionId,
} from '@reigh/editor-sdk';
import type {
  ExtensionManifest,
  ManifestValidationResult,
  ManifestValidationMode,
  InstalledExtensionPackage,
  ExtensionDiagnostic,
  IntegrityHash,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Package form discrimination
// ---------------------------------------------------------------------------

/** The two accepted package origins. */
export type PackageForm = 'workspace-source' | 'installed-bundle';

// ---------------------------------------------------------------------------
// Workspace source package
// ---------------------------------------------------------------------------

/**
 * A workspace source package: a local extension loaded from a
 * `reigh-extension.json` file during development.
 *
 * These are not installed and are not integrity-tracked. The only required
 * field is a `manifest` property, matching the shape accepted by
 * `defineExtension()`.
 */
export interface WorkspaceSourcePackage {
  readonly form: 'workspace-source';
  /** The manifest extracted from `reigh-extension.json`. */
  readonly manifest: ExtensionManifest;
  /** Informational: path to the source directory. */
  readonly sourcePath?: string;
}

// ---------------------------------------------------------------------------
// Installed bundle package
// ---------------------------------------------------------------------------

/**
 * An installed trusted bundle: a validated installed pack containing
 * `manifest.json` + `bundle.mjs` content plus integrity metadata.
 */
export interface InstalledBundlePackage {
  readonly form: 'installed-bundle';
  /** The full installed package. */
  readonly pack: InstalledExtensionPackage;
}

// ---------------------------------------------------------------------------
// Unified validated package
// ---------------------------------------------------------------------------

/** A package that has passed validation for its form. */
export type ValidatedPackage = WorkspaceSourcePackage | InstalledBundlePackage;

// ---------------------------------------------------------------------------
// Package validation result
// ---------------------------------------------------------------------------

/** Result of validating a package (either form). */
export interface PackageValidationResult {
  /** Derived package form. */
  readonly form: PackageForm;
  /** True when no blocking errors exist for this form. */
  readonly valid: boolean;
  /** Blocking diagnostics. */
  readonly errors: readonly ExtensionDiagnostic[];
  /** Non-blocking diagnostics. */
  readonly warnings: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Input discriminant helpers
// ---------------------------------------------------------------------------

/**
 * Heuristic: is `input` shaped like an installed extension package?
 *
 * Checks for the presence of both `metadata` (with `extensionId`) and
 * `manifest` properties.
 */
function isInstalledPackageShape(
  input: Record<string, unknown>,
): input is Record<string, unknown> & {
  metadata: Record<string, unknown>;
  manifest: Record<string, unknown>;
} {
  return (
    typeof input === 'object' &&
    input !== null &&
    typeof (input as any).metadata === 'object' &&
    (input as any).metadata !== null &&
    typeof (input as any).metadata.extensionId === 'string' &&
    typeof (input as any).manifest === 'object' &&
    (input as any).manifest !== null
  );
}

/**
 * Heuristic: is `input` shaped like a reigh-extension.json workspace source?
 *
 * Workspace source packages have a top-level `manifest` property without the
 * `metadata`/`bundleContent` fields of an installed pack.
 */
function isWorkspaceSourceShape(input: Record<string, unknown>): boolean {
  return (
    typeof input === 'object' &&
    input !== null &&
    typeof (input as any).manifest === 'object' &&
    (input as any).manifest !== null &&
    !isInstalledPackageShape(input)
  );
}

// ---------------------------------------------------------------------------
// Validation helpers
// ---------------------------------------------------------------------------

/**
 * Build a blocking error diagnostic for the given extension ID.
 */
function block(
  extensionId: string,
  code: string,
  message: string,
  contributionId?: string,
): ExtensionDiagnostic {
  return Object.freeze({
    severity: 'error' as const,
    code,
    message,
    extensionId,
    ...(contributionId ? { contributionId } : {}),
  });
}

/**
 * Build a non-blocking warning diagnostic for the given extension ID.
 */
function warn(
  extensionId: string,
  code: string,
  message: string,
  contributionId?: string,
): ExtensionDiagnostic {
  return Object.freeze({
    severity: 'warning' as const,
    code,
    message,
    extensionId,
    ...(contributionId ? { contributionId } : {}),
  });
}

/**
 * Build an info diagnostic for the given extension ID.
 */
function info(
  extensionId: string,
  code: string,
  message: string,
  contributionId?: string,
): ExtensionDiagnostic {
  return Object.freeze({
    severity: 'info' as const,
    code,
    message,
    extensionId,
    ...(contributionId ? { contributionId } : {}),
  });
}

// ---------------------------------------------------------------------------
// Workspace source package validation
// ---------------------------------------------------------------------------

/**
 * Validate a workspace source package (reigh-extension.json format).
 *
 * Workspace source packages use `validateManifest` in `'dev'` mode:
 * - Missing installed-only fields (publisher, license, settingsSchema) produce
 *   **warnings** rather than blocking errors.
 * - Only structural problems (invalid ID, missing version/label, invalid
 *   semver, duplicate contribution IDs) produce blocking errors.
 * - Manifest shape problems also produce errors.
 *
 * Returns a {@link PackageValidationResult} with `form: 'workspace-source'`.
 */
export function validateWorkspaceSourcePackage(
  raw: Record<string, unknown>,
  sourcePath?: string,
): PackageValidationResult {
  const errors: ExtensionDiagnostic[] = [];
  const warnings: ExtensionDiagnostic[] = [];

  // ---- Structural: must have a manifest property ----
  if (!raw.manifest || typeof raw.manifest !== 'object' || raw.manifest === null) {
    errors.push(
      block(
        '(unknown)',
        'package/workspace-missing-manifest',
        'Workspace source package must have a top-level "manifest" object',
      ),
    );
    return {
      form: 'workspace-source',
      valid: errors.length === 0,
      errors: Object.freeze([...errors]),
      warnings: Object.freeze([...warnings]),
    };
  }

  const manifest = raw.manifest as Record<string, unknown>;
  const extId = (typeof manifest.id === 'string' ? manifest.id : '(unknown)') as string;

  // ---- Validate extension ID format ----
  if (typeof manifest.id === 'string') {
    const idErrors = validateExtensionId(manifest.id as string);
    for (const msg of idErrors) {
      errors.push(block(extId, 'package/workspace-invalid-id', msg));
    }
  }

  // ---- Validate the manifest in dev mode ----
  const result = validateManifest(manifest as ExtensionManifest, 'dev');

  for (const err of result.errors) {
    errors.push(err);
  }
  for (const warnDiag of result.warnings) {
    warnings.push(warnDiag);
  }

  // ---- Additional workspace-source-specific checks ----

  // Warn if the workspace source package has top-level keys beyond 'manifest'
  // (e.g. legacy wrapper formats). This is advisory only.
  const knownKeys = new Set(['manifest']);
  for (const key of Object.keys(raw)) {
    if (!knownKeys.has(key)) {
      warnings.push(
        warn(
          extId,
          'package/workspace-extra-key',
          `Unexpected top-level key "${key}" in workspace source package; only "manifest" is used`,
        ),
      );
    }
  }

  // Source path informational
  if (sourcePath) {
    // Source path is informational — no diagnostic needed
  }

  return {
    form: 'workspace-source',
    valid: errors.length === 0,
    errors: Object.freeze([...errors]),
    warnings: Object.freeze([...warnings]),
  };
}

// ---------------------------------------------------------------------------
// Installed bundle package validation
// ---------------------------------------------------------------------------

/**
 * Validate an installed bundle package (manifest.json + bundle.mjs + metadata).
 *
 * Uses {@link validateInstalledPackage} from the SDK which runs
 * {@link validateManifest} in `'installed'` mode:
 * - Missing publisher, license, or integrity produce **blocking errors**.
 * - Missing settingsSchema produces a warning but does not block.
 * - Structural, version, dependency, and contribution ID uniqueness checks are
 *   always enforced as blocking errors.
 *
 * Also validates the `InstalledExtensionPackage` structure itself: metadata,
 * manifest, and bundleContent must all be present.
 *
 * Returns a {@link PackageValidationResult} with `form: 'installed-bundle'`.
 */
export function validateInstalledBundlePackage(
  pack: InstalledExtensionPackage,
): PackageValidationResult {
  const result = validateInstalledPackage(pack);

  return {
    form: 'installed-bundle',
    valid: result.valid,
    errors: result.errors,
    warnings: result.warnings,
  };
}

// ---------------------------------------------------------------------------
// Unified validatePackage
// ---------------------------------------------------------------------------

/**
 * Validate any package input, auto-detecting the form.
 *
 * - If the input has both `metadata` and `manifest` properties, it is treated
 *   as an installed bundle and validated with {@link validateInstalledBundlePackage}.
 * - If the input has a `manifest` property but no `metadata`, it is treated as
 *   a workspace source and validated with {@link validateWorkspaceSourcePackage}.
 * - Otherwise it is rejected as an unrecognised package shape.
 *
 * @param input A raw record that may be a workspace source or installed bundle.
 * @param sourcePath Optional source path for workspace source diagnostics.
 */
export function validatePackage(
  input: Record<string, unknown>,
  sourcePath?: string,
): PackageValidationResult {
  if (isInstalledPackageShape(input)) {
    // Treat as installed bundle
    return validateInstalledBundlePackage(input as unknown as InstalledExtensionPackage);
  }

  if (isWorkspaceSourceShape(input)) {
    // Treat as workspace source
    return validateWorkspaceSourcePackage(input, sourcePath);
  }

  // Unrecognised shape
  return {
    form: 'workspace-source', // default guess
    valid: false,
    errors: Object.freeze([
      block(
        '(unknown)',
        'package/unrecognised-shape',
        'Package input is neither a workspace source (reigh-extension.json) nor an installed bundle (metadata + manifest + bundleContent)',
      ),
    ]),
    warnings: Object.freeze([]),
  };
}

// ---------------------------------------------------------------------------
// Diagnostic classification helpers
// ---------------------------------------------------------------------------

/** Diagnostic codes that always block activation regardless of package form. */
const UNIVERSAL_BLOCK_CODES = new Set([
  'manifest/invalid-id',
  'manifest/missing-version',
  'manifest/invalid-version',
  'manifest/missing-label',
  'manifest/invalid-api-version',
  'manifest/invalid-contribution-id',
  'manifest/duplicate-contribution-id',
  'manifest/invalid-dependency-id',
  'manifest/self-dependency',
  'manifest/invalid-dependency-posture',
  'manifest/invalid-settings-schema-version',
  'manifest/invalid-migration-kind',
  'manifest/invalid-migration-from-version',
  'manifest/invalid-migration-to-version',
  'manifest/legacy-migration-shape', // only blocks in installed mode
  'package/missing-metadata',
  'package/missing-manifest',
  'package/missing-bundle',
  'package/id-mismatch',
  'package/version-mismatch',
  'package/missing-integrity',
  'package/invalid-integrity-algorithm',
  'package/missing-integrity-value',
  'package/invalid-enabled',
  'package/workspace-missing-manifest',
  'package/workspace-invalid-id',
  'package/unrecognised-shape',
]);

/** Diagnostic codes that only block in installed mode. */
const INSTALLED_ONLY_BLOCK_CODES = new Set([
  'manifest/installed-missing-publisher',
  'manifest/installed-missing-license',
  'manifest/installed-invalid-integrity-algorithm',
  'manifest/installed-missing-integrity-value',
]);

/** Diagnostic codes that are warnings in dev mode but errors in installed mode. */
const DEV_WARNING_INSTALLED_ERROR_CODES = new Set([
  'manifest/legacy-migration-shape', // warning in dev, error in installed
]);

/**
 * Return true if the diagnostic should block activation or installation.
 *
 * Blockers are always `severity: 'error'` diagnostics whose code signals a
 * hard requirement violation. Warnings and info diagnostics never block.
 */
export function isBlockingDiagnostic(diag: ExtensionDiagnostic): boolean {
  if (diag.severity !== 'error') return false;
  return UNIVERSAL_BLOCK_CODES.has(diag.code) || INSTALLED_ONLY_BLOCK_CODES.has(diag.code);
}

/**
 * Return true if the diagnostic is a workspace-source-only warning.
 *
 * These are diagnostics that appear as warnings in dev mode but become
 * blocking errors in installed mode. They signal that the package is missing
 * fields required for installation.
 */
export function isWorkspaceSourceWarning(diag: ExtensionDiagnostic): boolean {
  return (
    diag.severity === 'warning' &&
    (diag.code === 'manifest/dev-missing-publisher' ||
      diag.code === 'manifest/dev-missing-license' ||
      diag.code === 'manifest/dev-missing-settings-schema')
  );
}

/**
 * Return true if the diagnostic is an installed-pack blocker.
 *
 * These diagnostics only appear as blocking errors when validating in
 * `'installed'` mode and prevent installation or activation of an installed
 * bundle.
 */
export function isInstalledPackBlocker(diag: ExtensionDiagnostic): boolean {
  return diag.severity === 'error' && INSTALLED_ONLY_BLOCK_CODES.has(diag.code);
}

/**
 * Return true if the diagnostic is a contribution-ID uniqueness violation.
 */
export function isContributionIdDuplicate(diag: ExtensionDiagnostic): boolean {
  return diag.code === 'manifest/duplicate-contribution-id';
}

// ---------------------------------------------------------------------------
// Package form detection (standalone)
// ---------------------------------------------------------------------------

/**
 * Detect the package form from a raw input without full validation.
 *
 * Returns the detected form or `null` if the shape is unrecognised.
 */
export function detectPackageForm(
  input: Record<string, unknown>,
): PackageForm | null {
  if (isInstalledPackageShape(input)) return 'installed-bundle';
  if (isWorkspaceSourceShape(input)) return 'workspace-source';
  return null;
}

exec
/bin/zsh -lc 'rg -n "export interface ExtensionManifest|type ExtensionPermission|Permission|permissions|capability|capabilities|sandbox|trusted|validateManifest|defineExtension|InstalledExtensionPackage|ExtensionContext|createExtensionContext" src/sdk/index.ts' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
4: * Stable public types and helpers for trusted local extensions.
76: * - `extension` — authored by a trusted local extension (the only source
390:  // M12: trusted local process descriptors
812:   * Optional description of the search provider capabilities
834: * stronger capability.
867: * stronger capability.
898: * Contributed clip types are trusted local browser-preview components
925: * M9: A trusted local component registered by an extension as a clip renderer.
933: * M9: A trusted local component registered by an extension as a clip inspector.
986:   * Register a trusted local renderer and optional inspector for a clip type.
1681:/** M12: Declarative environment field for trusted local process configuration. */
1692:/** M12: Operation a trusted local process exposes to tools, render routes, or export formats. */
1704:/** M12: Declarative trusted-local process specification. */
1717:  capabilities?: IntegrationCapabilities;
1857:  /** Permission state for this source. */
1858:  readonly permission?: LiveSourcePermission;
1945:// --- Live permissions ---
1948: * Permission state for a live source.
1955:export type LivePermissionState = 'prompt' | 'granted' | 'denied' | 'unavailable';
1958: * Permission metadata for a live source.
1960:export interface LiveSourcePermission {
1962:  readonly state: LivePermissionState;
2429:// Permission metadata (descriptive until sandboxing exists)
2432:export interface ExtensionPermissionDeclaration {
2499:/** Metadata recorded when an extension is installed as a trusted bundle. */
2525:export interface InstalledExtensionPackage {
2528:  /** Raw trusted bundle source (bundle.mjs content). */
2555:export function validateManifest(
2930: * to {@link validateManifest} in 'installed' mode.
2933:  pack: InstalledExtensionPackage,
3000:  const manifestResult = validateManifest(pack.manifest, 'installed');
3020:export interface ExtensionManifest {
3040:    // M12: trusted local processes
3042:    // M7: trusted component effects
3044:    // M8: trusted component transitions
3054:  permissions?: readonly ExtensionPermissionDeclaration[];
3344: * A trusted local component registered by an extension as an effect.
3347: * export contexts unless the owning contribution declares stronger capability.
3408:   * Register a trusted local component as an effect.
3428: * A trusted local renderer registered by an extension as a transition.
3431: * export contexts unless the owning contribution declares stronger capability.
3492:   * Register a trusted local renderer as a transition.
3512:export interface ExtensionContext {
3535:  /** M7: Effect registration service for trusted component effects. */
3537:  /** M8: Transition registration service for trusted component transitions. */
3579:// ExtensionContext factory
3583: * Create a concrete ExtensionContext for a given extension.
3597:export function createExtensionContext(
3606:): ExtensionContext {
3608:  const manifest = extension.manifest; // Already frozen by defineExtension
3907:  } as ExtensionContext;
3924:  const frozenCtx: ExtensionContext = Object.freeze(ctx);
3932: * Symbol key for host-service disposal attached to every ExtensionContext.
3941: * attached to an ExtensionContext. Safe to call on contexts that lack the
3944:export function disposeExtensionContextServices(ctx: ExtensionContext): void {
3960:export type ExtensionActivateFn = (ctx: ExtensionContext) => DisposeHandle | void;
3962:/** The public extension shape returned by defineExtension(). */
3969:// defineExtension()
3972:/** Options passed to defineExtension(). */
3999:export function defineExtension(options: DefineExtensionOptions): ReighExtension {
4031:    permissions: manifest.permissions ? freezeManifestValue(manifest.permissions) : undefined,
4174:// M12: Planner requirement contracts — capability requirements, source refs,
4175:// route-fit metadata, capability versioning, and integration capabilities
4179: * M12: Version descriptor for a capability or contribution declaration.
4195: * M12: Source reference for a capability requirement.
4197: * Identifies where a capability requirement originates so planners
4202:  /** The kind of source that produced this capability. */
4208:  /** Version of the capability declaration, when known. */
4213: * M12: Route-fit metadata describing how well a capability maps to a route.
4222:  /** Whether the capability supports, blocks, degrades, or is unknown for this route. */
4231: * M12: A single capability requirement produced by the planner.
4236: * record consumed by TimelineReader capability inspection and
4246:  /** Required capabilities for this route (e.g. 'browser-export', 'worker-export'). */
4252:  /** Version of the capability declaration, when known. */
4261: * M12: Minimal integration capabilities consumed by TimelineReader and
4264: * Aggregates capability requirements, source references, and route
4265: * summaries so planners can consume a single normalized capabilities
4269:  /** Extension that owns these capabilities, when scoped to a single extension. */
4271:  /** Contribution that owns these capabilities, when scoped to a single contribution. */
4273:  /** Routes covered by these capabilities. */
4275:  /** Aggregate determinism posture across all capabilities. */
4277:  /** Individual capability requirements collected during planning. */
4278:  readonly capabilityRequirements: readonly CapabilityRequirement[];
4279:  /** Source references for all capabilities in this integration record. */
4962:// M12: getCapabilityRequirements — provider-free capability inspection
4966: * M12: Derive capability requirements from a TimelineSnapshot.

exec
/bin/zsh -lc "sed -n '2400,3070p' src/sdk/index.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "sed -n '3510,3935p' src/sdk/index.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
  resolveBinding(bindingId: string): LiveBindingResolution;

  /**
   * Get aggregate live binding metadata.
   * The pure binding scanner produces this aggregate, which is the
   * source of truth for unresolved live references.
   */
  getBindingMetadata(): LiveBindingMetadata;

  // ── Steering ──────────────────────────────────────────────────────

  /**
   * Apply a steering decision to a GenerationSession.
   *
   * The steering resolver must always return an explicit supersede,
   * fork, or reject. GenerationSession live sample delivery must not
   * activate without complete steering lineage.
   */
  applySteeringDecision(decision: SteeringDecision): void;

  // ── Diagnostics ───────────────────────────────────────────────────

  /**
   * Get diagnostics for all sources or a specific source.
   */
  getDiagnostics(sourceId?: string): readonly LiveSourceDiagnostic[];
}

// ---------------------------------------------------------------------------
// Permission metadata (descriptive until sandboxing exists)
// ---------------------------------------------------------------------------

export interface ExtensionPermissionDeclaration {
  /** Human-readable reason the permission is requested. */
  reason: string;
  /** Declared posture: what the extension states it accesses. */
  posture?: {
    network?: boolean;
    filesystem?: boolean;
    env?: boolean;
    processes?: boolean;
  };
}

// ---------------------------------------------------------------------------
// M14: Packaging, integrity, settings-schema, and dependency contracts
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

/** Settings schema descriptor with version for migration tracking. */
export interface ExtensionSettingsSchema {
  /** Monotonic version number; increments when the settings shape changes. */
  version: number;
  /** Optional JSON Schema-like shape descriptor (subset). */
  schema?: Record<string, unknown>;
}

/** Supported integrity algorithms. */
export type IntegrityAlgorithm = 'sha256';

/** An SRI-style integrity hash. */
export interface IntegrityHash {
  algorithm: IntegrityAlgorithm;
  /** Base64-encoded hash value (without algorithm prefix). */
  value: string;
}

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

/** A full installed extension package: manifest + bundle + tracked metadata. */
export interface InstalledExtensionPackage {
  metadata: InstalledExtensionMetadata;
  manifest: ExtensionManifest;
  /** Raw trusted bundle source (bundle.mjs content). */
  bundleContent: string;
}

/** Validation mode: 'dev' produces warnings, 'installed' produces strict errors. */
export type ManifestValidationMode = 'dev' | 'installed';

/** Result of validating an extension manifest. */
export interface ManifestValidationResult {
  /** True when no blocking errors exist. */
  valid: boolean;
  /** Blocking diagnostics (strict errors in installed mode). */
  errors: readonly ExtensionDiagnostic[];
  /** Non-blocking diagnostics (warnings in dev mode, supplemental in installed mode). */
  warnings: readonly ExtensionDiagnostic[];
}

/**
 * Validate an extension manifest against the expected contract.
 *
 * In 'dev' mode, missing installed-only fields emit warnings.
 * In 'installed' mode, missing required installed metadata fields
 * (integrity, publisher, license) emit blocking errors.
 *
 * Contribution ID uniqueness, ID format, version format, and
 * dependency posture are validated in both modes.
 */
export function validateManifest(
  manifest: ExtensionManifest,
  _mode?: ManifestValidationMode,
): ManifestValidationResult {
  const errors: ExtensionDiagnostic[] = [];
  const warnings: ExtensionDiagnostic[] = [];
  const mode: ManifestValidationMode = _mode ?? 'dev';

  const extId = manifest.id as string;

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  const isValidSemver = (v: string): boolean => /^\d+\.\d+\.\d+/.test(v);

  /** Basic semver-range check: accepts npm-style range strings. */
  const isValidSemverRange = (range: string): boolean => {
    // Accept common patterns: ^x.y.z, ~x.y.z, >=x.y.z, x.y.z - y.z.w, x, x.y
    return /^(\*|[\^~><=]*(?:\d+|\*|x)(?:\.(?:\d+|\*|x))?(?:\.(?:\d+|\*|x))?)(\s+(?:-?\s*)?[\^~><=]*(?:\d+|\*|x)(?:\.(?:\d+|\*|x))?(?:\.(?:\d+|\*|x))?)*(\s+\|\|\s+[\^~><=]*(?:\d+|\*|x)(?:\.(?:\d+|\*|x))?(?:\.(?:\d+|\*|x))?)*\s*$/.test(range.trim());
  };

  const pushErr = (code: string, message: string, contributionId?: string): void => {
    errors.push({
      severity: 'error',
      code,
      message,
      extensionId: extId,
      ...(contributionId ? { contributionId } : {}),
    });
  };

  const pushWarn = (code: string, message: string, contributionId?: string): void => {
    warnings.push({
      severity: 'warning',
      code,
      message,
      extensionId: extId,
      ...(contributionId ? { contributionId } : {}),
    });
  };

  // -----------------------------------------------------------------------
  // ID validation
  // -----------------------------------------------------------------------
  const idErrors = validateExtensionId(extId);
  for (const msg of idErrors) {
    pushErr('manifest/invalid-id', msg);
  }

  // -----------------------------------------------------------------------
  // Version validation
  // -----------------------------------------------------------------------
  if (!manifest.version || typeof manifest.version !== 'string') {
    pushErr('manifest/missing-version', 'Manifest must include a semver version string');
  } else if (!isValidSemver(manifest.version)) {
    pushErr('manifest/invalid-version', `Version "${manifest.version}" does not match semver format`);
  }

  // -----------------------------------------------------------------------
  // Label validation
  // -----------------------------------------------------------------------
  if (!manifest.label || typeof manifest.label !== 'string' || manifest.label.trim().length === 0) {
    pushErr('manifest/missing-label', 'Manifest must include a non-empty label');
  }

  // -----------------------------------------------------------------------
  // API version validation
  // -----------------------------------------------------------------------
  if (manifest.apiVersion !== undefined) {
    if (typeof manifest.apiVersion !== 'number' || !Number.isInteger(manifest.apiVersion) || manifest.apiVersion < 1) {
      pushErr('manifest/invalid-api-version', `apiVersion must be a positive integer, got ${manifest.apiVersion}`);
    }
  }

  // -----------------------------------------------------------------------
  // Contribution validation (ID uniqueness, kind, placement rules)
  // -----------------------------------------------------------------------
  if (manifest.contributions && manifest.contributions.length > 0) {
    const seen = new Set<string>();
    for (const contribution of manifest.contributions) {
      const cId = (contribution as any).id as string;
      const cErrors = validateContributionId(cId);
      for (const msg of cErrors) {
        pushErr('manifest/invalid-contribution-id', `Contribution "${cId}": ${msg}`, cId);
      }
      if (seen.has(cId)) {
        pushErr('manifest/duplicate-contribution-id', `Duplicate contribution ID "${cId}"`, cId);
      }
      seen.add(cId);

      // ---- Contribution kind validation ----
      const cKind = (contribution as any).kind as string | undefined;
      if (!cKind || typeof cKind !== 'string') {
        pushErr('manifest/missing-contribution-kind', `Contribution "${cId}" is missing a kind`, cId);
        continue; // cannot validate kind-specific rules without a kind
      }
      if (!KNOWN_CONTRIBUTION_KINDS_SET.has(cKind)) {
        pushErr(
          'manifest/unknown-contribution-kind',
          `Contribution "${cId}" has unknown kind "${cKind}"; must be one of: ${KNOWN_CONTRIBUTION_KINDS.join(', ')}`,
          cId,
        );
        continue; // unknown kind — skip kind-specific placement rules
      }

      // ---- Kind-specific placement rules ----

      // Slot: must not specify placement
      if (cKind === 'slot') {
        const cPlacement = (contribution as any).placement;
        if (cPlacement !== undefined && cPlacement !== null) {
          pushErr(
            'manifest/slot-no-placement',
            `Slot contribution "${cId}" must not specify placement`,
            cId,
          );
        }
        // Validate slot name if present
        const cSlot = (contribution as any).slot;
        if (cSlot !== undefined && cSlot !== null && !KNOWN_SLOT_NAMES_SET.has(cSlot)) {
          pushErr(
            'manifest/unknown-slot-name',
            `Slot contribution "${cId}" has unknown slot name "${cSlot}"; must be one of: ${KNOWN_SLOT_NAMES.join(', ')}`,
            cId,
          );
        }
      }

      // Panel: placement must be 'asset-panel' when specified
      if (cKind === 'panel') {
        const cPlacement = (contribution as any).placement as string | undefined;
        if (cPlacement !== undefined && cPlacement !== null) {
          if (!PANEL_PLACEMENTS.includes(cPlacement)) {
            pushErr(
              'manifest/invalid-panel-placement',
              `Panel contribution "${cId}" placement must be "asset-panel", got "${cPlacement}"`,
              cId,
            );
          }
        }
      }

      // InspectorSection: validate placement when present; host applies defaults
      if (cKind === 'inspectorSection') {
        const cPlacement = (contribution as any).placement as string | undefined;
        if (cPlacement !== undefined && cPlacement !== null) {
          if (!INSPECTOR_SECTION_PLACEMENTS.includes(cPlacement)) {
            pushErr(
              'manifest/invalid-inspector-placement',
              `InspectorSection contribution "${cId}" placement must be one of: ${INSPECTOR_SECTION_PLACEMENTS.join(', ')}, got "${cPlacement}"`,
              cId,
            );
          }
        }
      }

      // AssetDetailSection: title and placement are required
      if (cKind === 'assetDetailSection') {
        const adsContribution = contribution as { id: string; title?: unknown; placement?: unknown };
        if (!adsContribution.title || typeof adsContribution.title !== 'string' || adsContribution.title.trim().length === 0) {
          pushErr(
            'manifest/missing-asset-detail-title',
            `AssetDetailSection contribution "${cId}" must include a non-empty title`,
            cId,
          );
        }
        if (!adsContribution.placement || typeof adsContribution.placement !== 'string' || !ASSET_DETAIL_SECTION_PLACEMENTS.includes(adsContribution.placement)) {
          pushErr(
            'manifest/invalid-asset-detail-placement',
            `AssetDetailSection contribution "${cId}" must specify placement as one of: ${ASSET_DETAIL_SECTION_PLACEMENTS.join(', ')}, got "${String(adsContribution.placement ?? 'undefined')}"`,
            cId,
          );
        }
      }
    }
  }

  // -----------------------------------------------------------------------
  // Dependency validation
  // -----------------------------------------------------------------------
  if (manifest.dependsOn && manifest.dependsOn.length > 0) {
    for (const dep of manifest.dependsOn) {
      // Dependency ID validation
      const depIdErrors = validateExtensionId(dep.extensionId);
      for (const msg of depIdErrors) {
        pushErr('manifest/invalid-dependency-id', `Dependency "${dep.extensionId}": ${msg}`);
      }

      // Self-dependency check
      if (dep.extensionId === extId) {
        pushErr('manifest/self-dependency', `Extension "${extId}" declares a dependency on itself`);
      }

      // Posture validation
      if (dep.posture !== undefined && dep.posture !== 'required' && dep.posture !== 'optional') {
        pushErr(
          'manifest/invalid-dependency-posture',
          `Dependency "${dep.extensionId}" has invalid posture "${dep.posture}"; must be "required" or "optional"`,
        );
      }

      // optional vs posture consistency
      if (dep.optional === true && dep.posture === 'required') {
        pushWarn(
          'manifest/dependency-posture-mismatch',
          `Dependency "${dep.extensionId}" is marked optional=true but posture is "required"; posture takes precedence`,
        );
      }

      // Version range validation
      if (dep.versionRange !== undefined && typeof dep.versionRange === 'string' && dep.versionRange.length > 0) {
        if (!isValidSemverRange(dep.versionRange)) {
          pushWarn(
            'manifest/invalid-dependency-version-range',
            `Dependency "${dep.extensionId}" has an unrecognised version range "${dep.versionRange}"`,
          );
        }
      }
    }
  }

  // -----------------------------------------------------------------------
  // Settings schema validation
  // -----------------------------------------------------------------------
  if (manifest.settingsSchema) {
    const version = (manifest.settingsSchema as any).version;
    if (typeof version !== 'number' || !Number.isInteger(version) || version < 0) {
      pushErr(
        'manifest/invalid-settings-schema-version',
        `settingsSchema.version must be a non-negative integer, got ${version}`,
      );
    }
  }

  // -----------------------------------------------------------------------
  // Migration declarations validation
  // -----------------------------------------------------------------------
  const VALID_MIGRATION_KINDS: ReadonlySet<string> = new Set(['settings', 'contribution', 'manifest']);
  if (manifest.migrations && manifest.migrations.length > 0) {
    for (const migration of manifest.migrations) {
      // Legacy shape detection (plain object without 'kind')
      if (typeof migration !== 'object' || migration === null || !('kind' in migration)) {
        // In dev mode these are warnings; in installed mode typed declarations are required
        if (mode === 'installed') {
          pushErr(
            'manifest/legacy-migration-shape',
            'Migration entry lacks "kind"; typed MigrationDeclaration is required for installed extensions',
          );
        } else {
          pushWarn(
            'manifest/legacy-migration-shape',
            'Migration entry is a plain object without "kind"; typed MigrationDeclaration is preferred',
          );
        }
        break; // one diagnostic per manifest
      }

      const m = migration as Record<string, unknown>;

      // Validate kind
      if (!VALID_MIGRATION_KINDS.has(m.kind as string)) {
        pushErr(
          'manifest/invalid-migration-kind',
          `Migration kind "${m.kind}" is not valid; must be one of: settings, contribution, manifest`,
        );
      }

      // Validate fromVersion
      if (typeof m.fromVersion !== 'string' || !isValidSemver(m.fromVersion)) {
        pushErr(
          'manifest/invalid-migration-from-version',
          `Migration fromVersion "${m.fromVersion}" must be a valid semver`,
        );
      }

      // Validate toVersion
      if (typeof m.toVersion !== 'string' || !isValidSemver(m.toVersion)) {
        pushErr(
          'manifest/invalid-migration-to-version',
          `Migration toVersion "${m.toVersion}" must be a valid semver`,
        );
      }
    }
  }

  // -----------------------------------------------------------------------
  // Mode-specific checks: installed vs dev
  // -----------------------------------------------------------------------
  if (mode === 'installed') {
    // ---- Installed-mode required identity fields ----

    // Publisher is required for installed extensions
    if (!manifest.publisher || typeof manifest.publisher !== 'string' || manifest.publisher.trim().length === 0) {
      pushErr(
        'manifest/installed-missing-publisher',
        'Installed extensions must declare a publisher',
      );
    }

    // License is required for installed extensions
    if (!manifest.license || typeof manifest.license !== 'string' || manifest.license.trim().length === 0) {
      pushErr(
        'manifest/installed-missing-license',
        'Installed extensions must declare an SPDX license identifier',
      );
    }

    // Settings schema is recommended for installed extensions
    if (!manifest.settingsSchema) {
      pushWarn(
        'manifest/installed-missing-settings-schema',
        'Installed extensions should declare a settingsSchema for migration tracking',
      );
    }

    // Integrity is expected to be validated externally (on InstalledExtensionMetadata),
    // but if integrity is passed as a top-level field on manifest we validate the shape.
    const integrity = (manifest as any).integrity as IntegrityHash | undefined;
    if (integrity) {
      if (!integrity.algorithm || integrity.algorithm !== 'sha256') {
        pushErr(
          'manifest/installed-invalid-integrity-algorithm',
          `Integrity algorithm "${integrity.algorithm}" is not supported; only "sha256" is allowed`,
        );
      }
      if (!integrity.value || typeof integrity.value !== 'string' || integrity.value.trim().length === 0) {
        pushErr(
          'manifest/installed-missing-integrity-value',
          'Integrity hash value is required',
        );
      }
    }
  } else {
    // ---- Dev mode: compatibility warnings for legacy (M1/local) manifests ----

    // Warn about missing M14-required fields so extension authors see what will be
    // required for installed-pack compatibility.
    if (!manifest.publisher) {
      pushWarn(
        'manifest/dev-missing-publisher',
        'Publisher is not declared; installed extensions require a publisher',
      );
    }
    if (!manifest.license) {
      pushWarn(
        'manifest/dev-missing-license',
        'License is not declared; installed extensions require an SPDX license identifier',
      );
    }
    if (!manifest.settingsSchema) {
      pushWarn(
        'manifest/dev-missing-settings-schema',
        'settingsSchema is not declared; installed extensions should declare one for migration tracking',
      );
    }
  }

  // -----------------------------------------------------------------------
  return {
    valid: errors.length === 0,
    errors: Object.freeze([...errors]),
    warnings: Object.freeze([...warnings]),
  };
}

// ---------------------------------------------------------------------------
// Installed package validation
// ---------------------------------------------------------------------------

/**
 * Validate a full installed extension package.
 *
 * Checks package structure, metadata/manifest cross-references,
 * integrity hash presence, and delegates manifest-level validation
 * to {@link validateManifest} in 'installed' mode.
 */
export function validateInstalledPackage(
  pack: InstalledExtensionPackage,
): ManifestValidationResult {
  const errors: ExtensionDiagnostic[] = [];
  const warnings: ExtensionDiagnostic[] = [];

  const extId = pack.metadata?.extensionId as string ?? '(unknown)';

  const pushErr = (code: string, message: string): void => {
    errors.push({ severity: 'error', code, message, extensionId: extId });
  };

  const pushWarn = (code: string, message: string): void => {
    warnings.push({ severity: 'warning', code, message, extensionId: extId });
  };

  // Structural checks
  if (!pack.metadata) {
    pushErr('package/missing-metadata', 'Installed package must include metadata');
    return { valid: false, errors: Object.freeze([...errors]), warnings: Object.freeze([...warnings]) };
  }

  if (!pack.manifest) {
    pushErr('package/missing-manifest', 'Installed package must include a manifest');
    return { valid: false, errors: Object.freeze([...errors]), warnings: Object.freeze([...warnings]) };
  }

  if (typeof pack.bundleContent !== 'string' || pack.bundleContent.trim().length === 0) {
    pushErr('package/missing-bundle', 'Installed package must include non-empty bundleContent');
  }

  // Cross-reference: metadata.extensionId === manifest.id
  if (pack.metadata.extensionId !== pack.manifest.id) {
    pushErr(
      'package/id-mismatch',
      `Metadata extensionId "${pack.metadata.extensionId}" does not match manifest.id "${pack.manifest.id}"`,
    );
  }

  // Cross-reference: metadata.version === manifest.version
  if (pack.metadata.version !== pack.manifest.version) {
    pushErr(
      'package/version-mismatch',
      `Metadata version "${pack.metadata.version}" does not match manifest.version "${pack.manifest.version}"`,
    );
  }

  // Integrity validation
  if (!pack.metadata.integrity) {
    pushErr('package/missing-integrity', 'Installed package metadata must include integrity hash');
  } else {
    if (!pack.metadata.integrity.algorithm || pack.metadata.integrity.algorithm !== 'sha256') {
      pushErr(
        'package/invalid-integrity-algorithm',
        `Integrity algorithm "${pack.metadata.integrity.algorithm}" is not supported; only "sha256" is allowed`,
      );
    }
    if (!pack.metadata.integrity.value || typeof pack.metadata.integrity.value !== 'string' || pack.metadata.integrity.value.trim().length === 0) {
      pushErr('package/missing-integrity-value', 'Integrity hash value is required');
    }
  }

  // Enabled must be boolean
  if (typeof pack.metadata.enabled !== 'boolean') {
    pushErr('package/invalid-enabled', 'Metadata enabled must be a boolean');
  }

  // Delegate to manifest validation in installed mode
  const manifestResult = validateManifest(pack.manifest, 'installed');
  for (const err of manifestResult.errors) {
    errors.push(err);
  }
  for (const warn of manifestResult.warnings) {
    warnings.push(warn);
  }

  return {
    valid: errors.length === 0,
    errors: Object.freeze([...errors]),
    warnings: Object.freeze([...warnings]),
  };
}


// ---------------------------------------------------------------------------
// Extension manifest
// ---------------------------------------------------------------------------

export interface ExtensionManifest {
  id: ExtensionId;
  /** Semver string, e.g. "1.0.0". */
  version: string;
  label: string;
  description?: string;
  /** API version this extension targets (currently 1). */
  apiVersion?: number;
  /** Contribution declarations. */
  contributions?: readonly (
    | ExtensionContribution
    | CommandContribution
    | KeybindingContribution
    | ContextMenuItemContribution
    // M6: parser, output format, search provider, metadata facet, asset detail section
    | ParserContribution
    | OutputFormatContribution
    | SearchProviderContribution
    | MetadataFacetContribution
    | AssetDetailSectionContribution
    // M12: trusted local processes
    | ProcessContribution
    // M7: trusted component effects
    | EffectContribution
    // M8: trusted component transitions
    | TransitionContribution
    // M9: contributed clip types
    | ClipTypeContribution
    // M13: shader/WebGL contributions
    | ShaderContribution
    // M10: agent tool contributions
    | AgentToolContribution
  )[];
  /** Descriptive permission metadata. */
  permissions?: readonly ExtensionPermissionDeclaration[];
  /** Process declarations. */
  processes?: readonly ProcessManifestEntry[];
  /** Typed migration hooks (preferred); legacy Record<string, unknown>[] accepted. */
  migrations?: readonly (MigrationDeclaration | Record<string, unknown>)[];
  /** Human-readable comments. */
  comments?: string;
  /** Typed dependency declarations. */
  dependsOn?: readonly ExtensionDependency[];
  /** Renderability descriptors. */
  renderability?: Record<string, unknown>;
  /** Extension-scoped settings defaults applied when no stored value exists. */
  settingsDefaults?: Record<string, unknown>;
  /** Settings schema with version for migration tracking. */
  settingsSchema?: ExtensionSettingsSchema;
  /** Bundled i18n messages keyed by locale-neutral key. */
  messages?: Record<string, string>;

 succeeded in 0ms:
 * timeline store, or internal mutation escape hatch.
 */
export interface ExtensionContext {
  /** Current API version (1 in M1). */
  readonly apiVersion: number;
  /** Readonly extension metadata. */
  readonly extension: {
    readonly id: ExtensionId;
    readonly version: string;
    readonly label: string;
    readonly description?: string;
    readonly manifest: Readonly<ExtensionManifest>;
  };
  /** Host chrome services. */
  readonly chrome: ExtensionChromeService;
  /** Scoped services. */
  readonly services: {
    readonly settings: ExtensionSettingsService;
    readonly i18n: ExtensionI18nService;
    readonly diagnostics: ExtensionDiagnosticsService;
  };
  /** Reserved creative context stubs — throw typed \"not implemented until Mx\". */
  readonly creative: CreativeContext;
  /** M4: Command registration service for imperative handler binding. */
  readonly commands: ExtensionCommandService;
  /** M7: Effect registration service for trusted component effects. */
  readonly effects: EffectRegistrationService;
  /** M8: Transition registration service for trusted component transitions. */
  readonly transitions: TransitionRegistrationService;
  /** M9: Clip-type registration service for contributed clip types. */
  readonly clipTypes: ClipTypeRegistrationService;
  /** M13: Shader registration service for dedicated WebGL shader passes. */
  readonly shaders: ShaderRegistrationService;
  /** M10: Agent tool registration service for host-mediated agent tools. */
  readonly agentTools: AgentToolRegistrationService;
}

// ---------------------------------------------------------------------------
// Editor shell root registry (module-level, set by host shell on mount)
// ---------------------------------------------------------------------------

/**
 * The currently-mounted editor shell root element, if any.
 * Set by the host shell component via {@link setEditorShellRoot} and
 * consumed by the chrome service's `focus()` and `announce()` methods.
 */
let _editorShellRoot: HTMLElement | null = null;

/**
 * Register (or clear) the editor shell root element.
 *
 * The host shell component should call this on mount with its outermost
 * DOM element and on unmount with `null`.  The chrome service's
 * `focus()` and `announce()` methods are no-ops (with diagnostics)
 * when no root is set.
 */
export function setEditorShellRoot(element: HTMLElement | null): void {
  _editorShellRoot = element;
}

/**
 * Return the currently-registered editor shell root element, or `null`
 * if no shell is mounted.
 */
export function getEditorShellRoot(): HTMLElement | null {
  return _editorShellRoot;
}

// ---------------------------------------------------------------------------
// ExtensionContext factory
// ---------------------------------------------------------------------------

/**
 * Create a concrete ExtensionContext for a given extension.
 *
 * Exposes only the approved M1 members:
 * - `apiVersion: 1`
 * - Readonly extension metadata
 * - `chrome` (toast, progress, subscribe, focus, announce)
 * - `services.settings` (localStorage-backed, scoped per extension)
 * - `services.i18n` (minimal t() scaffolding)
 * - `services.diagnostics` (in-memory structured diagnostic reporting)
 * - `creative` stubs that throw typed ExtensionNotImplementedError
 *
 * No raw DataProvider, applyEdit, timeline store, or internal mutation
 * escape hatch is exposed.
 */
export function createExtensionContext(
  extension: ReighExtension,
  creativeOverrides?: Partial<CreativeContext>,
  commands?: ExtensionCommandService,
  effects?: EffectRegistrationService,
  transitions?: TransitionRegistrationService,
  clipTypes?: ClipTypeRegistrationService,
  agentTools?: AgentToolRegistrationService,
  shaders?: ShaderRegistrationService,
): ExtensionContext {
  const extensionId = extension.manifest.id as string;
  const manifest = extension.manifest; // Already frozen by defineExtension

  // ---- diagnostics service ------------------------------------------------
  const diagnosticsList: ExtensionDiagnostic[] = [];
  const diagnosticsService: ExtensionDiagnosticsService = {
    report(diag: Omit<ExtensionDiagnostic, 'extensionId' | 'source'>): void {
      const full: ExtensionDiagnostic = Object.freeze({
        ...diag,
        extensionId,
        source: DIAGNOSTIC_SOURCE_EXTENSION,
      });
      diagnosticsList.push(full);
    },
    get diagnostics(): readonly ExtensionDiagnostic[] {
      return diagnosticsList;
    },
  };

  // ---- settings service (injectable factory, localStorage-backed) -----------
  const { service: settingsService, dispose: disposeSettings } =
    createExtensionSettingsService(extensionId, manifest);

  // ---- i18n service (with manifest message bundle fallback) ----------------
  const messages: Record<string, string> | undefined =
    manifest.messages as Record<string, string> | undefined;

  const i18nService: ExtensionI18nService = {
    t(key: string, replacements?: Record<string, string | number>): string {
      // Resolve from message bundle first, fall back to key verbatim
      let resolved = messages?.[key] ?? key;
      if (replacements) {
        for (const [k, v] of Object.entries(replacements)) {
          const placeholder = '{{' + k + '}}';
          while (resolved.includes(placeholder)) {
            resolved = resolved.replace(placeholder, String(v));
          }
        }
      }
      return resolved;
    },
  };

  // ---- chrome service (with subscription cleanup) --------------------------
  const subscribers = new Map<
    string,
    Set<(payload: unknown) => void>
  >();

  // ---- aria-live host node (created lazily on first announce) -------------
  let _ariaLiveHost: HTMLElement | null = null;

  /** Get or create the aria-live container inside the shell root. */
  function getOrCreateAriaLiveHost(politeness: 'polite' | 'assertive'): HTMLElement | null {
    const root = _editorShellRoot;
    if (!root) return null;

    if (_ariaLiveHost && root.contains(_ariaLiveHost)) {
      _ariaLiveHost.setAttribute('aria-live', politeness);
      return _ariaLiveHost;
    }

    // Clear stale reference if node was removed
    _ariaLiveHost = null;

    const host = document.createElement('div');
    host.setAttribute('data-video-editor-aria-live', '');
    host.setAttribute('aria-live', politeness);
    host.setAttribute('aria-atomic', 'true');
    host.className = 'sr-only';
    root.appendChild(host);
    _ariaLiveHost = host;
    return host;
  }

  const chromeService: ExtensionChromeService = {
    toast(message: string, severity: DiagnosticSeverity = 'info'): void {
      // Host-visible toast — dispatched via console + subscriber in dev
      if (typeof console !== 'undefined') {
        const fn = severity === 'error' ? console.error : severity === 'warning' ? console.warn : console.log;
        fn(`[Extension ${extensionId}] ${message}`);
      }
      // Notify toast subscribers
      const subs = subscribers.get('toast');
      if (subs) {
        subs.forEach((handler) => {
          try {
            handler({ message, severity });
          } catch {
            // subscriber errors are silently dropped
          }
        });
      }
    },
    progress(percent: number, label?: string): void {
      const subs = subscribers.get('progress');
      if (subs) {
        subs.forEach((handler) => {
          try {
            handler({ percent, label } as ChromeProgressPayload);
          } catch {
            // subscriber errors are silently dropped
          }
        });
      }
    },
    subscribe<E extends ChromeEvent>(
      event: E,
      handler: (payload: ChromeEventPayload<E>) => void,
    ): DisposeHandle {
      if (!subscribers.has(event)) {
        subscribers.set(event, new Set());
      }
      const eventSubs = subscribers.get(event)!;
      eventSubs.add(handler as (payload: unknown) => void);

      return {
        dispose(): void {
          eventSubs.delete(handler as (payload: unknown) => void);
        },
      };
    },
    focus(selector: string): void {
      const root = _editorShellRoot;
      if (!root) {
        diagnosticsService.report({
          severity: 'warning',
          code: 'chrome/focus-no-shell',
          message: `Cannot focus "${selector}": no editor shell root is mounted.`,
        });
        return;
      }

      // Try to find the element within the shell root
      const element = root.querySelector(selector);
      if (element instanceof HTMLElement) {
        try {
          element.focus();
        } catch {
          // focus() may throw on non-focusable elements in some environments
          diagnosticsService.report({
            severity: 'warning',
            code: 'chrome/focus-not-focusable',
            message: `Cannot focus "${selector}": element is not focusable.`,
          });
        }
        return;
      }

      // Not found in shell root — check if it exists in the document
      // (indicating a portal target or out-of-shell element)
      if (document.querySelector(selector)) {
        diagnosticsService.report({
          severity: 'warning',
          code: 'chrome/focus-out-of-shell',
          message: `Cannot focus "${selector}": element found outside the editor shell root (possible portal target).`,
        });
        return;
      }

      // Not found anywhere
      diagnosticsService.report({
        severity: 'warning',
        code: 'chrome/focus-missing-selector',
        message: `Cannot focus "${selector}": no matching element found.`,
      });
    },
    announce(message: string, politeness: 'polite' | 'assertive' = 'polite'): void {
      const host = getOrCreateAriaLiveHost(politeness);
      if (!host) {
        // Fallback: log to console when no shell root is mounted
        if (typeof console !== 'undefined') {
          console.log(`[Extension ${extensionId} announce] ${message}`);
        }
        return;
      }

      // Clear first so repeated identical messages are re-announced
      host.textContent = '';
      // Force a reflow so the clear takes effect before setting new text.
      // Use requestAnimationFrame so assistive tech registers the change.
      requestAnimationFrame(() => {
        host.textContent = message;
      });
    },
  };

  /** Clean up all chrome event subscribers. */
  function disposeChromeSubscriptions(): void {
    subscribers.clear();
  }

  // ---- creative context (stubs with optional live overrides) --------------
  const creative = createCreativeContext(creativeOverrides);

  // ---- commands service (optional, wired by provider) -----------------------
  const commandsService: ExtensionCommandService = commands ?? {
    registerCommand(_commandId: string, _handler: CommandHandler, _options?: CommandRegistrationOptions): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'commands/not-wired',
        message: `Cannot register command "${_commandId}" — the CommandRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
  };

  // ---- effects service (optional, wired by provider) ------------------------
  const effectsService: EffectRegistrationService = effects ?? {
    registerComponent(_effectId: string, _component: EffectComponent, _options?: EffectRegistrationOptions): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'effects/not-wired',
        message: `Cannot register effect component "${_effectId}" — the EffectRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
  };

  // ---- transitions service (optional, wired by provider) --------------------
  const transitionsService: TransitionRegistrationService = transitions ?? {
    registerRenderer(_transitionId: string, _renderer: TransitionRenderer, _options?: TransitionRegistrationOptions): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'transitions/not-wired',
        message: `Cannot register transition renderer "${_transitionId}" — the TransitionRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
  };

  // ---- clipTypes service (optional, wired by provider) -----------------------
  const clipTypesService: ClipTypeRegistrationService = clipTypes ?? {
    registerClipType(_clipTypeId: string, _renderer: ClipRenderer, _inspector?: ClipInspector, _options?: ClipTypeRegistrationOptions): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'clipTypes/not-wired',
        message: `Cannot register clip type "${_clipTypeId}" — the ClipTypeRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
  };

  // ---- shaders service (optional, wired by provider) ------------------------
  const shadersService: ShaderRegistrationService = shaders ?? {
    registerShader(_shaderId: string, _source: ShaderSourceDescriptor, _options?: ShaderRegistrationOptions): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'shaders/not-wired',
        message: `Cannot register shader "${_shaderId}" — the ShaderRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
  };

  // ---- agentTools service (optional, wired by provider) ----------------------
  const agentToolsService: AgentToolRegistrationService = agentTools ?? {
    registerTool(_toolId: string, _handler: AgentToolHandler): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'agentTools/not-wired',
        message: `Cannot register agent tool "${_toolId}" — the AgentToolRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
    async invokeProcess(_toolId: string, _config: ProcessSpawnConfig): Promise<ToolProcessResult> {
      return {
        family: 'process',
        diagnostics: [{
          severity: 'info',
          code: 'agent-tool/process-not-available',
          message: `Process invocation for tool "${_toolId}" is not available until M12.`,
        }],
      };
    },
  };

  // ---- assemble, attach dispose, then freeze -------------------------------
  const ctx = {
    apiVersion: 1,
    extension: {
      id: manifest.id,
      version: manifest.version,
      label: manifest.label,
      description: manifest.description,
      manifest,
    },
    chrome: chromeService,
    services: {
      settings: settingsService,
      i18n: i18nService,
      diagnostics: diagnosticsService,
    },
    creative,
    commands: commandsService,
    effects: effectsService,
    transitions: transitionsService,
    clipTypes: clipTypesService,
    shaders: shadersService,
    agentTools: agentToolsService,
  } as ExtensionContext;

  // Attach host-service disposal so the lifecycle can clean up settings
  // (localStorage keys) and chrome subscriptions without the extension
  // author needing to know about internal service state.
  // Must be attached BEFORE freezing.
  Object.defineProperty(ctx, CONTEXT_DISPOSE_SYMBOL, {
    value: function disposeHostServices(): void {
      disposeSettings();
      disposeChromeSubscriptions();
    },
    writable: false,
    enumerable: false,
    configurable: false,
  });

  // Freeze after property definition so the Symbol key is included.
  const frozenCtx: ExtensionContext = Object.freeze(ctx);
  Object.freeze(frozenCtx.extension);
  Object.freeze(frozenCtx.services);

  return frozenCtx;
}

/**
 * Symbol key for host-service disposal attached to every ExtensionContext.
 * The runtime lifecycle calls this during deactivation/disposal to clean up
 * localStorage keys, chrome event subscribers, and any future host-owned
 * service state scoped to this extension activation.

exec
/bin/zsh -lc "sed -n '3970,4050p' src/sdk/index.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
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

// ---------------------------------------------------------------------------
// Contribution kind bridging
// ---------------------------------------------------------------------------

exec
/bin/zsh -lc "rg -n '\"permissions\"|ExtensionPermissionDeclaration|network|filesystem|camera|microphone|clipboard|process|localTimeline|project|mediaLibrary' config/contracts/reigh-extension.schema.json src/tools/video-editor/examples/extensions -S" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
config/contracts/reigh-extension.schema.json:43:    "permissions": {
config/contracts/reigh-extension.schema.json:47:        "$ref": "#/definitions/ExtensionPermissionDeclaration"
config/contracts/reigh-extension.schema.json:50:    "processes": {
config/contracts/reigh-extension.schema.json:130:        "process",
config/contracts/reigh-extension.schema.json:367:      "description": "M12: Route/process requirements for a render-dependent output format.",
config/contracts/reigh-extension.schema.json:379:        "processId": { "type": "string" },
config/contracts/reigh-extension.schema.json:490:      "description": "M12: Process contribution — trusted local process descriptor.",
config/contracts/reigh-extension.schema.json:495:        "kind": { "const": "process" },
config/contracts/reigh-extension.schema.json:579:            { "type": "string", "enum": ["color", "alpha", "effect", "post-process", "compute"] },
config/contracts/reigh-extension.schema.json:584:                "kind": { "type": "string", "enum": ["color", "alpha", "effect", "post-process", "compute"] },
config/contracts/reigh-extension.schema.json:727:              "process",
config/contracts/reigh-extension.schema.json:751:    "ExtensionPermissionDeclaration": {
src/tools/video-editor/examples/extensions/flagship-local/index.ts:210:        op: 'project-data.write',
src/tools/video-editor/examples/extensions/flagship-local/index.ts:360:        'enabling it in a shared project.',
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:231:  // Build a copilot-authored project-data patch to demonstrate proposal output
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:243:        op: 'project-data.write',
src/tools/video-editor/examples/extensions/flagship-local/reigh-extension.json:98:      "warning.trustedLocal": "⚠️ Trusted-local extension: this extension executes with full browser-renderer privileges. Review the extension source before enabling it in a shared project.",
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:326:          op: 'project-data.write',
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:353:          op: 'project-data.write',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:2: * postprocess-shader-canary - M13 timeline postprocess WebGL shader canary.
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:4: * Exercises the public shader SDK path for timeline-scope postprocess shaders:
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:23:export const POSTPROCESS_SHADER_CANARY_EXTENSION_ID = 'com.reigh.examples.postprocess-shader-canary';
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:24:export const POSTPROCESS_SHADER_CANARY_SHADER_ID = 'shader.postprocessCanary.scanline';
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:25:export const POSTPROCESS_SHADER_CANARY_CONTRIBUTION_ID = 'postprocess-shader-canary';
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:26:export const POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID = 'shader.postprocessCanary.diagnostic';
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:27:export const POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID = 'postprocess-shader-canary-diagnostic';
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:30:export interface PostprocessShaderCanaryOptions {
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:32:  readonly onReady?: (controller: PostprocessShaderCanaryController) => void;
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:35:export interface PostprocessShaderCanaryController extends DisposeHandle {
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:169:export const postprocessShaderCanaryContribution: ShaderContribution = {
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:173:  label: 'Postprocess Shader Canary',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:174:  description: 'Preview-only timeline postprocess WebGL shader canary with editable uniforms.',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:176:    kind: 'postprocess',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:188:export const postprocessShaderDiagnosticContribution: ShaderContribution = {
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:192:  label: 'Postprocess Shader Canary Diagnostic',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:193:  description: 'Deliberately invalid postprocess shader contribution used to prove diagnostic surfacing.',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:194:  pass: 'postprocess',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:201:export function startPostprocessShaderCanary(
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:203:  options: PostprocessShaderCanaryOptions = {},
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:204:): PostprocessShaderCanaryController {
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:212:      label: postprocessShaderCanaryContribution.label,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:213:      pass: postprocessShaderCanaryContribution.pass,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:216:      fallback: postprocessShaderCanaryContribution.fallback,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:225:        label: postprocessShaderDiagnosticContribution.label,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:226:        pass: postprocessShaderDiagnosticContribution.pass,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:227:        uniforms: postprocessShaderDiagnosticContribution.uniforms,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:228:        fallback: postprocessShaderDiagnosticContribution.fallback,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:235:    code: 'postprocess-shader-canary/activated',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:236:    message: 'Postprocess shader canary registered through ctx.shaders.',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:243:  const controller: PostprocessShaderCanaryController = {
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:246:    contribution: postprocessShaderCanaryContribution,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:248:    diagnosticContribution: postprocessShaderDiagnosticContribution,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:262:export function createPostprocessShaderCanaryExtension(
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:263:  options: PostprocessShaderCanaryOptions = {},
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:269:      label: 'Postprocess Shader Canary',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:270:      description: 'M13 canary for timeline postprocess WebGL shader registration, uniforms, diagnostics, preview, and planner behavior.',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:273:        postprocessShaderCanaryContribution,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:274:        postprocessShaderDiagnosticContribution,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:277:        'activation.started': 'Postprocess Shader Canary activating.',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:278:        'activation.ready': 'Postprocess Shader Canary ready.',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:279:        'activation.disposed': 'Postprocess Shader Canary disposed.',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:283:      return startPostprocessShaderCanary(ctx, options);
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:288:export const postprocessShaderCanaryExtension = createPostprocessShaderCanaryExtension();
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:290:export default postprocessShaderCanaryExtension;
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:3:    "id": "com.reigh.examples.postprocess-shader-canary",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:5:    "label": "Postprocess Shader Canary",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:6:    "description": "M13 canary for timeline postprocess WebGL shader registration, uniforms, diagnostics, preview, and planner behavior.",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:10:        "id": "postprocess-shader-canary",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:12:        "shaderId": "shader.postprocessCanary.scanline",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:13:        "label": "Postprocess Shader Canary",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:14:        "description": "Preview-only timeline postprocess WebGL shader canary with editable uniforms.",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:16:          "kind": "postprocess",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:113:        "id": "postprocess-shader-canary-diagnostic",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:115:        "shaderId": "shader.postprocessCanary.diagnostic",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:116:        "label": "Postprocess Shader Canary Diagnostic",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:117:        "description": "Deliberately invalid postprocess shader contribution used to prove diagnostic surfacing.",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:118:        "pass": "postprocess",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:136:      "activation.started": "Postprocess Shader Canary activating.",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:137:      "activation.ready": "Postprocess Shader Canary ready.",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:138:      "activation.disposed": "Postprocess Shader Canary disposed."
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:316:        'Webcam permission was denied or the camera could not be opened.',
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:207:        family: 'process',
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:210:          code: 'agent-tool/process-not-available',
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:239:    project: {},
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:355:    context: { projectId: 'project-integration' },
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:86:        family: 'process',
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:89:          code: 'agent-tool/process-not-available',
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:118:    context: { projectId: 'project-canary' },
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:17:  createPostprocessShaderCanaryExtension,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:18:  type PostprocessShaderCanaryController,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:19:} from '@/tools/video-editor/examples/extensions/postprocess-shader-canary';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:28:import { createTimelinePostprocessShaderMetadata } from '@/tools/video-editor/lib/shader-catalog.ts';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:29:import { PostprocessShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:213:  controller: PostprocessShaderCanaryController;
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:216:  const extension = createPostprocessShaderCanaryExtension({
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:237:  const controller = handle as PostprocessShaderCanaryController;
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:270:      shaderPostprocess: createTimelinePostprocessShaderMetadata(record),
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:277:  const shader = config.app?.shaderPostprocess!;
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:279:    projectId: 'project-postprocess-shader-canary',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:295:      id: `postprocess:shader:${shader.shaderId}`,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:297:      scope: 'postprocess',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:311:describe('postprocess-shader-canary extension', () => {
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:333:      pass: { kind: 'postprocess', inputTextureUniform: 'u_composite' },
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:397:    const shader = config.app!.shaderPostprocess!;
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:401:      scope: 'postprocess',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:424:        postprocessShader={shader}
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:435:    expect(applyEdit.mock.calls[0][0].resolvedConfig.app.shaderPostprocess).toEqual(expect.objectContaining({
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:444:      <PostprocessShaderPreviewCanvas
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:451:        testId="canary-postprocess-preview"
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:455:    expect(screen.getByTestId('canary-postprocess-preview')).toHaveAttribute(
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:457:      'postprocess',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:459:    expect(screen.getByTestId('canary-postprocess-preview')).toHaveAttribute(
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:473:      <PostprocessShaderPreviewCanvas
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:480:        testId="canary-postprocess-preview-next"
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:497:        message: `Shader "${POSTPROCESS_SHADER_CANARY_SHADER_ID}" cannot export because no shader materializer produced RenderMaterial for postprocess.`,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:139:    projectId: 'project-shader-canary',

codex
The SDK is explicit in one place: `ExtensionPermissionDeclaration` is labeled “descriptive until sandboxing exists.” I’m checking whether that honesty survives into schema, docs, UI, examples, and runtime behavior.
exec
/bin/zsh -lc "sed -n '740,790p' config/contracts/reigh-extension.schema.json" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
      "required": ["id", "kind"],
      "additionalProperties": false,
      "properties": {
        "id": { "$ref": "#/definitions/ContributionId" },
        "kind": { "const": "agent" },
        "order": { "type": "number" },
        "label": { "type": "string" },
        "when": { "type": "string" }
      }
    },

    "ExtensionPermissionDeclaration": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "permission": { "type": "string" },
        "reason": { "type": "string" }
      }
    },

    "ProcessManifestEntry": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": { "type": "string" },
        "label": { "type": "string" },
        "spec": { "type": "object" }
      }
    },

    "ExtensionDependency": {
      "type": "object",
      "required": ["extensionId"],
      "additionalProperties": false,
      "properties": {
        "extensionId": { "type": "string" },
        "versionRange": { "type": "string" },
        "posture": {
          "type": "string",
          "enum": ["required", "optional"]
        },
        "optional": { "type": "boolean" }
      }
    },

    "ExtensionSettingsSchema": {
      "type": "object",
      "required": ["version"],
      "additionalProperties": true,
      "properties": {
        "version": {

exec
/bin/zsh -lc 'rg --files src/tools/video-editor/components/ExtensionManager src/tools/video-editor/runtime | sort' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx
src/tools/video-editor/components/ExtensionManager/ExtensionManagerErrorBoundary.tsx
src/tools/video-editor/components/ExtensionManager/ExtensionTrustWarningBanner.tsx
src/tools/video-editor/components/ExtensionManager/index.ts
src/tools/video-editor/runtime/ContributionErrorBoundary.test.tsx
src/tools/video-editor/runtime/ContributionErrorBoundary.tsx
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx
src/tools/video-editor/runtime/VideoEditorDialogHost.tsx
src/tools/video-editor/runtime/agentToolContracts.test.ts
src/tools/video-editor/runtime/agentToolContracts.ts
src/tools/video-editor/runtime/agentToolInvocationAdapters.ts
src/tools/video-editor/runtime/agentToolInvocationService.ts
src/tools/video-editor/runtime/agentToolRegistry.test.ts
src/tools/video-editor/runtime/agentToolRegistry.ts
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts
src/tools/video-editor/runtime/clipTypeRegistrationService.ts
src/tools/video-editor/runtime/commandPredicates.test.ts
src/tools/video-editor/runtime/commandPredicates.ts
src/tools/video-editor/runtime/commandRegistry.test.ts
src/tools/video-editor/runtime/commandRegistry.ts
src/tools/video-editor/runtime/diagnosticCollectionSync.ts
src/tools/video-editor/runtime/effectRegistrationService.test.ts
src/tools/video-editor/runtime/effectRegistrationService.ts
src/tools/video-editor/runtime/exportGuard.test.ts
src/tools/video-editor/runtime/exportGuard.ts
src/tools/video-editor/runtime/extensionIntegrity.test.ts
src/tools/video-editor/runtime/extensionIntegrity.ts
src/tools/video-editor/runtime/extensionLifecycle.test.ts
src/tools/video-editor/runtime/extensionLifecycle.ts
src/tools/video-editor/runtime/extensionLoader.test.ts
src/tools/video-editor/runtime/extensionLoader.ts
src/tools/video-editor/runtime/extensionLockMetadata.test.ts
src/tools/video-editor/runtime/extensionLockMetadata.ts
src/tools/video-editor/runtime/extensionMigration.test.ts
src/tools/video-editor/runtime/extensionMigration.ts
src/tools/video-editor/runtime/extensionPackageManifest.test.ts
src/tools/video-editor/runtime/extensionPackageManifest.ts
src/tools/video-editor/runtime/extensionPersistenceCache.test.ts
src/tools/video-editor/runtime/extensionPersistenceCache.ts
src/tools/video-editor/runtime/extensionReferenceReport.test.ts
src/tools/video-editor/runtime/extensionReferenceReport.ts
src/tools/video-editor/runtime/extensionRendererRegistry.test.ts
src/tools/video-editor/runtime/extensionRendererRegistry.ts
src/tools/video-editor/runtime/extensionSettings.test.ts
src/tools/video-editor/runtime/extensionSettings.ts
src/tools/video-editor/runtime/extensionStateRepository.test.ts
src/tools/video-editor/runtime/extensionStateRepository.ts
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.test.ts
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.ts
src/tools/video-editor/runtime/extensionStateRepositoryProvider.test.ts
src/tools/video-editor/runtime/extensionStateRepositoryProvider.ts
src/tools/video-editor/runtime/extensionSurface.test.ts
src/tools/video-editor/runtime/extensionSurface.ts
src/tools/video-editor/runtime/liveBake.test.ts
src/tools/video-editor/runtime/liveBake.ts
src/tools/video-editor/runtime/liveDataRegistry.test.ts
src/tools/video-editor/runtime/liveDataRegistry.ts
src/tools/video-editor/runtime/liveMapping.test.ts
src/tools/video-editor/runtime/liveMapping.ts
src/tools/video-editor/runtime/livePermissions.test.ts
src/tools/video-editor/runtime/livePermissions.ts
src/tools/video-editor/runtime/liveRecording.test.ts
src/tools/video-editor/runtime/liveRecording.ts
src/tools/video-editor/runtime/liveSteering.test.ts
src/tools/video-editor/runtime/liveSteering.ts
src/tools/video-editor/runtime/outputFormatRegistry.test.ts
src/tools/video-editor/runtime/outputFormatRegistry.ts
src/tools/video-editor/runtime/ports.ts
src/tools/video-editor/runtime/processCommandRegistration.test.ts
src/tools/video-editor/runtime/processCommandRegistration.ts
src/tools/video-editor/runtime/renderPlanner.test.ts
src/tools/video-editor/runtime/renderPlanner.ts
src/tools/video-editor/runtime/renderability.test.ts
src/tools/video-editor/runtime/renderability.ts
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts
src/tools/video-editor/runtime/shaderRegistrationService.ts
src/tools/video-editor/runtime/transitionRegistrationService.ts
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts
src/tools/video-editor/runtime/useVideoEditorRenderContext.ts

exec
/bin/zsh -lc 'rg -n "permissions|permission|sandbox|trusted|trust|descriptive|enforc|capability|security|full browser|renderer privileges|review.*source|safe|unsafe|install|enable|disable" src/tools/video-editor/components/ExtensionManager docs/extensions docs/video-editor/extension-platform-supported-deferred.md scripts/quality src/tools/video-editor/examples/extensions -S' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
docs/video-editor/extension-platform-supported-deferred.md:61:| S-015 | HMR-safe re-registration and stale component cleanup | **supported** | CR:M5-003; provider-scoped lifecycle with `DisposeHandle` |
docs/video-editor/extension-platform-supported-deferred.md:62:| S-016 | Activation/deactivation wrapped in visible console grouping | **supported** | DOC:extensions-trust-envelope.md§4; `console.groupCollapsed`/`console.groupEnd` in lifecycle host |
docs/video-editor/extension-platform-supported-deferred.md:63:| S-017 | Lifecycle teardown failures captured as diagnostics, never thrown | **supported** | DOC:extensions-trust-envelope.md§2 (Dispose row); `lifecycle/teardown-error` diagnostics |
docs/video-editor/extension-platform-supported-deferred.md:84:| S-030 | Safe insert/update/delete/reorder clips and update tracks/assets through `TimelineOps` | **supported** | CR:M3-001; TEST:timeline-patch.test.ts (241 tests); DOC:timeline-patch-operations.md§3 |
docs/video-editor/extension-platform-supported-deferred.md:103:### 2.6 Provider-Scoped Registry & Trusted Loader
docs/video-editor/extension-platform-supported-deferred.md:110:| S-063 | Renderability metadata available to export guards | **supported** | CR:M5-006; `RenderCapability`, `ContributionRenderability`, `RenderBlocker` in `src/sdk/index.ts` |
docs/video-editor/extension-platform-supported-deferred.md:123:| S-075 | Render-dependent output formats declared early appear disabled with diagnostics | **supported** | CR:M6-006; `requiresRender: true` → disabled/reserved |
docs/video-editor/extension-platform-supported-deferred.md:131:| S-081 | Effect renders in preview and responds to Fast Refresh | **supported** | CR:M7-002; HMR-safe provider-scoped registry |
docs/video-editor/extension-platform-supported-deferred.md:161:| S-111 | Tool registry is provider-scoped and HMR-safe | **supported** | CR:M10-003; provider-scoped registry pattern |
docs/video-editor/extension-platform-supported-deferred.md:200:| S-150 | V1 trust envelope documented and honest (trusted-local execution) | **supported** | CR:X-003; DOC:extensions-trust-envelope.md |
docs/video-editor/extension-platform-supported-deferred.md:215:| D-001 | User-facing extension manager UI (install, enable/disable, settings edit) | **deferred** | CR:M14-001; BLOCKER:B-001 |
docs/video-editor/extension-platform-supported-deferred.md:216:| D-002 | Persisted enablement, settings, failed load, contribution cleanup | **deferred** | CR:M14-003; BLOCKER:B-001 |
docs/video-editor/extension-platform-supported-deferred.md:217:| D-003 | Integrity mismatch prevents installation/activation | **deferred** | CR:M14-004; BLOCKER:B-001; DOC:extensions-trust-envelope.md§6 (planned M4–M5) |
docs/video-editor/extension-platform-supported-deferred.md:220:| D-006 | Local-source-to-installed-pack migration (settings/data preservation) | **deferred** | CR:M14-007; BLOCKER:B-001 |
docs/video-editor/extension-platform-supported-deferred.md:221:| D-007 | Manager trust warnings and extension requirements/lock metadata for installed packs | **deferred** | CR:M14-008; BLOCKER:B-001; DOC:extensions-trust-envelope.md |
docs/video-editor/extension-platform-supported-deferred.md:224:| D-010 | Conflict override UI, dependency tree badges, uninstall reference report | **deferred** | CR:M14-011; BLOCKER:B-001 |
docs/video-editor/extension-platform-supported-deferred.md:230:| D-020 | Full render planner implementation with capability/blocker reports | **deferred** | CR:M12-001; BLOCKER:B-002 |
docs/video-editor/extension-platform-supported-deferred.md:243:| D-030 | Live data frontend state coverage (permission, error, bake-ready) for canary sources | **deferred** | CR:M11-006; BLOCKER:B-003 |
docs/video-editor/extension-platform-supported-deferred.md:250:| D-037 | Lifecycle cleanup on permission failure | **deferred** | CR:M11-005; BLOCKER:B-003 |
docs/video-editor/extension-platform-supported-deferred.md:269:| D-050 | Command registry tests: `when` predicates, disabled commands, target context, mutation failure | **deferred** | CR:M4-003; DEFER:D-001 |
docs/video-editor/extension-platform-supported-deferred.md:314:| D-100 | Stub materializer capability finding for blocked export when no renderer route exists | **deferred** | CR:M13-005; `shaderMissingMaterializerBlockerMessage` exported but materializer not implemented |
docs/video-editor/extension-platform-supported-deferred.md:325:### 3.12 Permissions & Sandboxing
docs/video-editor/extension-platform-supported-deferred.md:329:| D-120 | Runtime permission enforcement (network, filesystem, env, processes gating) | **deferred** | DOC:extensions-trust-envelope.md§3; ABSENCE:grep -r 'permission enforcement' src/tools/video-editor/runtime/ |
docs/video-editor/extension-platform-supported-deferred.md:330:| D-121 | Sandboxed extension execution (iframe, Worker, ShadowRealm isolation) | **deferred** | DOC:extensions-trust-envelope.md§§5-6; ABSENCE:grep -r 'sandbox' src/tools/video-editor/runtime/; planned M4–M5 |
docs/video-editor/extension-platform-supported-deferred.md:331:| D-122 | Dynamic package loading (npm / CDN / `import()` for extension code) | **deferred** | DOC:extensions-trust-envelope.md§2; ABSENCE:grep -r 'CDN.*extension' src/tools/video-editor/runtime/; extensions statically bundled with host |
docs/video-editor/extension-platform-supported-deferred.md:341:| D-133 | Schema capability registry tests (supported widgets, unsupported diagnostics, validation, custom widget placeholder) | **deferred** | CR:M2-007; concept documented; dedicated registry tests not identified |
docs/video-editor/extension-platform-supported-deferred.md:357:| Sandboxed execution (iframe/Worker/ShadowRealm) | DOC:extensions-trust-envelope.md§5 |
docs/video-editor/extension-platform-supported-deferred.md:361:### 4.2 Active V1 trust model
docs/video-editor/extension-platform-supported-deferred.md:365:| Execution context | Same-thread, same-origin JavaScript in the browser | DOC:extensions-trust-envelope.md§7 |
docs/video-editor/extension-platform-supported-deferred.md:366:| Isolation | None | DOC:extensions-trust-envelope.md§1 |
docs/video-editor/extension-platform-supported-deferred.md:367:| Permission enforcement | Descriptive only (no runtime gating) | DOC:extensions-trust-envelope.md§3 |
docs/video-editor/extension-platform-supported-deferred.md:368:| Lifecycle visibility | Console groups + structured diagnostics + export guard | DOC:extensions-trust-envelope.md§7 |
docs/video-editor/extension-platform-supported-deferred.md:369:| Error containment | Contribution-level error boundaries; activation throws → `failed` state + diagnostics | DOC:extensions-trust-envelope.md§5 |
docs/video-editor/extension-platform-supported-deferred.md:370:| Source vetting | Human review required; no automated integrity checks in V1 | DOC:extensions-trust-envelope.md§7 |
docs/video-editor/extension-platform-supported-deferred.md:412:| Permissions & Sandboxing | 4 |
docs/video-editor/extension-platform-supported-deferred.md:424:| B-001 | D-001 through D-010 (M14) | Extension manager UI, persistence, integrity, migration, dependency management are core to installed-pack experience |
docs/video-editor/extension-platform-supported-deferred.md:445:| [extensions-trust-envelope.md](./extensions-trust-envelope.md) | V1 trusted-local execution model and permission posture |
docs/video-editor/extension-platform-supported-deferred.md:457:| 2026-06-20 | Initial supported/deferred matrix for M15. Derived from contract-recheck matrix (122 rows, 70 pass, 52 gap), provider compatibility matrix, trust envelope, shader execution model, and frontend closure checklist. |
scripts/quality/check-schema-drift.mjs:9:const enforce =
scripts/quality/check-schema-drift.mjs:10:  args.has('--enforce') ||
scripts/quality/check-schema-drift.mjs:11:  process.env.SLOT_FIRST_SCHEMA_DRIFT_ENFORCE === '1' ||
scripts/quality/check-schema-drift.mjs:12:  process.env.CI_SLOT_FIRST_ENFORCE === '1';
scripts/quality/check-schema-drift.mjs:123:  if (enforce) {
scripts/quality/check-schema-drift.mjs:127:  console.warn(`${message} M0 audit mode skipped drift enforcement.`);
scripts/quality/check-schema-drift.mjs:138:  if (enforce) {
scripts/quality/check-schema-drift.mjs:146:  console.warn('[schema-drift] audit mode is inactive in M0; M4 flips enforcement.');
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:4: * Demonstrates the webcam path from browser permission to provider-scoped
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:285:    permission: {
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:315:        'live-webcam/permission-denied',
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:316:        'Webcam permission was denied or the camera could not be opened.',
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:433:      description: 'M11 canary for webcam permission, frame channels, live preview, bake, and cleanup.',
src/tools/video-editor/examples/extensions/live-webcam-canary/reigh-extension.json:6:    "description": "M11 canary for webcam permission, frame channels, live preview, bake, cleanup, and export-blocking live bindings.",
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:228:    clipId: options.previewClipId ?? `${sourceId}:preview`,
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:564:        clipId: options.previewClipId ?? `${sourceId}:preview`,
scripts/quality/check-supabase-rls.mjs:32:const rlsEnabledTables = new Set();
scripts/quality/check-supabase-rls.mjs:57:  const enableRlsPattern =
scripts/quality/check-supabase-rls.mjs:58:    /alter table\s+(?:if exists\s+)?(?:"?public"?\.)?"?([a-z0-9_]+)"?\s+enable row level security\b/gim;
scripts/quality/check-supabase-rls.mjs:59:  for (const match of normalizedSql.matchAll(enableRlsPattern)) {
scripts/quality/check-supabase-rls.mjs:60:    rlsEnabledTables.add(match[1].toLowerCase());
scripts/quality/check-supabase-rls.mjs:73:  if (!rlsEnabledTables.has(tableName)) {
scripts/quality/check-supabase-rls.mjs:75:      `${tableName} (${origin.reason}) was introduced in ${origin.file} without any ENABLE ROW LEVEL SECURITY coverage in migrations.`,
src/tools/video-editor/examples/extensions/flagship-local/index.ts:2: * flagship-local-extension — Flagship trusted-local extension example.
src/tools/video-editor/examples/extensions/flagship-local/index.ts:12: *   - Trusted-local safety-warning copy emitted on activation
src/tools/video-editor/examples/extensions/flagship-local/index.ts:15: *   - M7 trusted component-effect registration with parameter schema
src/tools/video-editor/examples/extensions/flagship-local/index.ts:16: *   - M8 trusted component-transition registration with pure renderer
src/tools/video-editor/examples/extensions/flagship-local/index.ts:50:// M7: Trusted component-effect parameter schema
src/tools/video-editor/examples/extensions/flagship-local/index.ts:102:// M8: Trusted component-transition parameter schema
src/tools/video-editor/examples/extensions/flagship-local/index.ts:269:      'Flagship trusted-local extension example demonstrating the full M1 SDK surface.',
src/tools/video-editor/examples/extensions/flagship-local/index.ts:290:      // ---- M7 trusted component-effect contribution ------------------------
src/tools/video-editor/examples/extensions/flagship-local/index.ts:344:      'toolbar.enabled': true,
src/tools/video-editor/examples/extensions/flagship-local/index.ts:357:      'warning.trustedLocal':
src/tools/video-editor/examples/extensions/flagship-local/index.ts:358:        '⚠️ Trusted-local extension: this extension executes with full ' +
src/tools/video-editor/examples/extensions/flagship-local/index.ts:359:        'browser-renderer privileges. Review the extension source before ' +
src/tools/video-editor/examples/extensions/flagship-local/index.ts:377:    // --- Emit the trusted-local warning on every activation --------------
src/tools/video-editor/examples/extensions/flagship-local/index.ts:378:    const trustedWarning = ctx.services.i18n.t('warning.trustedLocal');
src/tools/video-editor/examples/extensions/flagship-local/index.ts:379:    warn(ctx, 'flagship/trusted-local-warning', trustedWarning);
src/tools/video-editor/examples/extensions/flagship-local/index.ts:392:    const toolbarEnabled = setting(ctx, 'toolbar.enabled', true);
src/tools/video-editor/examples/extensions/flagship-local/index.ts:400:        `toolbar.enabled=${toolbarEnabled}, ` +
src/tools/video-editor/examples/extensions/flagship-local/index.ts:435:    // --- M7: Trusted component-effect registration ----------------------
src/tools/video-editor/examples/extensions/flagship-local/index.ts:451:    // --- M8: Trusted component-transition registration ------------------
src/tools/video-editor/components/ExtensionManager/ExtensionManagerErrorBoundary.tsx:13:import { ExtensionTrustWarningBanner } from './ExtensionTrustWarningBanner';
src/tools/video-editor/components/ExtensionManager/ExtensionManagerErrorBoundary.tsx:43:      <ExtensionTrustWarningBanner />
src/tools/video-editor/components/ExtensionManager/ExtensionManagerErrorBoundary.tsx:59:      <ExtensionTrustWarningBanner />
src/tools/video-editor/components/ExtensionManager/ExtensionManagerErrorBoundary.tsx:86:      <ExtensionTrustWarningBanner />
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:97:    putEnablementState: vi.fn().mockResolvedValue(undefined),
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:98:    getEnablementState: vi.fn().mockResolvedValue(null),
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:99:    getAllEnablementStates: vi.fn().mockResolvedValue([]),
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:100:    deleteEnablementState: vi.fn().mockResolvedValue(undefined),
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:116:      enablement: {},
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:129:describe('ExtensionManager — enable/disable controls', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:135:    it('shows an enable/disable toggle for loaded packages when repository is provided', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:147:      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:149:      expect(toggle).toHaveTextContent('Enabled');
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:152:    it('shows toggle as Disabled for disabled-by-user packages', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:156:          { extensionId: 'ext.a', packageState: 'disabled-by-user', label: 'Package A' },
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:164:      const toggle = screen.getByRole('button', { name: /enable ext\.a/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:166:      expect(toggle).toHaveTextContent('Disabled');
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:259:  describe('putEnablementState calls', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:260:    it('calls putEnablementState with enabled=false and user-facing reason when disabling a loaded package', async () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:275:      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:279:        expect(repo.putEnablementState).toHaveBeenCalledTimes(1);
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:282:      const callArg = (repo.putEnablementState as ReturnType<typeof vi.fn>).mock.calls[0][0];
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:284:      expect(callArg.enabled).toBe(false);
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:285:      expect(callArg.toggleReason).toBe('User disabled via extension manager');
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:289:    it('calls putEnablementState with enabled=true and user-facing reason when enabling a disabled package', async () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:296:          { extensionId: 'ext.a', packageState: 'disabled-by-user', label: 'Package A' },
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:304:      const toggle = screen.getByRole('button', { name: /enable ext\.a/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:308:        expect(repo.putEnablementState).toHaveBeenCalledTimes(1);
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:311:      const callArg = (repo.putEnablementState as ReturnType<typeof vi.fn>).mock.calls[0][0];
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:313:      expect(callArg.enabled).toBe(true);
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:314:      expect(callArg.toggleReason).toBe('User enabled via extension manager');
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:317:    it('triggers refresh after successful enablement state save', async () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:332:      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:342:    it('shows Saving… state and disables the button while save is in flight', async () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:345:      // Make putEnablementState never resolve so we can observe the saving state
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:347:      repo.putEnablementState = vi.fn().mockImplementation(
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:361:      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:364:      // Button should now show saving state and be disabled
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:369:      const savingButton = screen.getByRole('button', { name: /saving ext\.a enablement state/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:370:      expect(savingButton).toBeDisabled();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:385:      repo.putEnablementState = vi.fn().mockImplementation(() => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:403:      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:412:      const retryButton = screen.getByRole('button', { name: /retry saving ext\.a enablement state/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:418:      // Now the toggle should be the disable button again
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:423:      const newToggle = screen.getByRole('button', { name: /disable ext\.a/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:428:        expect(repo.putEnablementState).toHaveBeenCalledTimes(2);
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:433:  describe('disabled packages remain visible and inspectable (SD3)', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:434:    it('renders disabled-by-user packages with full metadata, state badge, and reason', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:439:            extensionId: 'ext.disabled',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:440:            packageState: 'disabled-by-user',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:441:            stateReason: 'User disabled via extension manager',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:442:            label: 'Disabled Package',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:445:            description: 'A disabled test package',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:455:      expect(screen.getByText('Disabled Package')).toBeInTheDocument();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:458:      expect(screen.getByText('A disabled test package')).toBeInTheDocument();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:460:      // State badge (there are two "Disabled" texts: one in the toggle button, one in the badge)
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:461:      const disabledTexts = screen.getAllByText('Disabled');
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:462:      expect(disabledTexts.length).toBeGreaterThanOrEqual(2);
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:465:      expect(screen.getByText('User disabled via extension manager')).toBeInTheDocument();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:467:      // Enable toggle is present
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:468:      expect(screen.getByRole('button', { name: /enable ext\.disabled/i })).toBeInTheDocument();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:508:        { extensionId: 'ext.disabled', packageState: 'disabled-by-user', stateReason: 'User disabled via extension manager', label: 'Disabled Pkg' },
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:511:        { extensionId: 'ext.dup', packageState: 'duplicate', stateReason: 'Installed pack takes precedence', label: 'Dupe Pkg' },
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:526:      expect(screen.getByText('Disabled Pkg')).toBeInTheDocument();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:533:      // All state badges present (note: "Disabled" appears in both the toggle button and badge)
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:535:      expect(screen.getAllByText('Disabled').length).toBeGreaterThanOrEqual(1);
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:544:      expect(screen.getByText('User disabled via extension manager')).toBeInTheDocument();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:547:      expect(screen.getByText('Installed pack takes precedence')).toBeInTheDocument();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:554:      expect(screen.getByText('1 disabled')).toBeInTheDocument();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:586:      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:593:      repo.putEnablementState = vi.fn().mockRejectedValue(new Error('Boom'));
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:605:      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:618:// Persistent trust warning tests (T10)
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:621:describe('ExtensionManager — persistent trust warning', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:626:  function expectTrustWarningVisible() {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:627:    const warning = screen.getByRole('note', { name: 'Extension trust warning' });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:629:    expect(warning).toHaveTextContent('Extensions run as trusted, unsandboxed code.');
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:630:    expect(warning).toHaveTextContent('Manifest permissions are declarative and are not enforced at runtime.');
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:633:  it('shows the trust warning during loading state', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:637:    expectTrustWarningVisible();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:640:  it('shows the trust warning in empty inventory state', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:650:    expectTrustWarningVisible();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:653:  it('shows the trust warning above populated package inventory', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:665:    expectTrustWarningVisible();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:668:  it('keeps the trust warning visible when a package detail section is expanded', async () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:687:    expectTrustWarningVisible();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:706:          { extensionId: 'ext.b', packageState: 'disabled-by-user', label: 'Package B' },
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:719:    it('renders settings section for disabled-by-user packages (SD3 visibility)', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:722:        extensionId: 'ext.disabled',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:731:            extensionId: 'ext.disabled',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:732:            packageState: 'disabled-by-user',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:733:            label: 'Disabled Package',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:734:            stateReason: 'User disabled via extension manager',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:743:      // Settings toggle should be present on the disabled package
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1113:    it('cancel is disabled when no changes have been made', async () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1144:      expect(cancelBtn).toBeDisabled();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1203:      repo.deleteSettingsSnapshot = vi.fn().mockRejectedValue(new Error('Permission denied'));
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1229:        expect(screen.getByText(/Settings error: Permission denied/)).toBeInTheDocument();
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1353:      fireEvent.change(rawEditor, { target: { value: '{"other":"safe"}' } });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1398:      fireEvent.change(rawEditor, { target: { value: '{"mode":"safe"}' } });
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1407:        values: { mode: 'safe' },
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1603:    it('shows diagnostic badges for disabled-by-user packages (SD3 visibility)', () => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1605:        makeDiagnostic({ extensionId: 'ext.disabled', severity: 'error', code: 'E001', message: 'error' }),
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1610:          { extensionId: 'ext.disabled', packageState: 'disabled-by-user', label: 'Disabled Pkg', stateReason: 'User disabled' },
src/tools/video-editor/examples/extensions/flagship-local/FlagshipEffectComponent.tsx:2: * FlagshipEffectComponent — Flagship trusted-local component effect example.
src/tools/video-editor/examples/extensions/flagship-local/FlagshipEffectComponent.tsx:5: * registered as a trusted component effect via ctx.effects.registerComponent().
src/tools/video-editor/examples/extensions/flagship-local/FlagshipEffectComponent.tsx:62:  // Animate intensity when enabled
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:6: *   - Return exportPlanFindings (CapabilityFinding-shaped records)
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:44:// Finding shape (compatible with CapabilityFinding from renderability.ts)
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:366:  // Convert findings to plain records (CapabilityFinding-compatible shape)
src/tools/video-editor/components/ExtensionManager/ExtensionTrustWarningBanner.tsx:3:export function ExtensionTrustWarningBanner() {
src/tools/video-editor/components/ExtensionManager/ExtensionTrustWarningBanner.tsx:8:      aria-label="Extension trust warning"
src/tools/video-editor/components/ExtensionManager/ExtensionTrustWarningBanner.tsx:9:      data-video-editor-extension-trust-warning="true"
src/tools/video-editor/components/ExtensionManager/ExtensionTrustWarningBanner.tsx:14:          <div className="font-medium text-yellow-100">Trusted extension code</div>
src/tools/video-editor/components/ExtensionManager/ExtensionTrustWarningBanner.tsx:16:            Extensions run as trusted, unsandboxed code. Manifest permissions are declarative and are not enforced at runtime.
scripts/quality/check-extension-example-readiness.mjs:9: * example files are safe to reference in author-contract docs and quickstart
scripts/quality/check-extension-example-readiness.mjs:12: * ## What this gate enforces
scripts/quality/check-extension-example-readiness.mjs:37: * The gate always writes a JSON record of docs-safe example IDs to stdout
scripts/quality/check-extension-example-readiness.mjs:40: *   {"docsSafeExampleIds":["toolbar-example","command-extension",…]}
scripts/quality/check-extension-example-readiness.mjs:648:const docsSafeExampleIds = new Set();
scripts/quality/check-extension-example-readiness.mjs:678:        // Don't disqualify from docs-safe in audit mode for import issues
scripts/quality/check-extension-example-readiness.mjs:688:    docsSafeExampleIds.add(exampleId);
scripts/quality/check-extension-example-readiness.mjs:727:        docsSafeExampleIds.add(exampleId);
scripts/quality/check-extension-example-readiness.mjs:763:      docsSafeExampleIds.add(exampleId);
scripts/quality/check-extension-example-readiness.mjs:882:const sortedIds = [...docsSafeExampleIds].sort();
scripts/quality/check-extension-example-readiness.mjs:884:  docsSafeExampleIds: sortedIds,
scripts/quality/check-extension-example-readiness.mjs:889:    totalSafe: sortedIds.length,
scripts/quality/check-extension-example-readiness.mjs:911:      `${sortedIds.length} docs-safe example(s), ${warnings.length} warning(s).`,
src/tools/video-editor/examples/extensions/flagship-local/reigh-extension.json:6:    "description": "Flagship trusted-local extension example demonstrating the SDK surface: activation lifecycle, toolbar and status-bar slot UI, settings with defaults, diagnostics, chrome toast/progress scaffolding, trusted-local safety warnings, command/keybinding/context-menu contributions, active transition contribution (M8 wipe), component effect (M7 glow), and future inactive contribution declarations (clipType, parser, agentTool).",
src/tools/video-editor/examples/extensions/flagship-local/reigh-extension.json:90:      "toolbar.enabled": true,
src/tools/video-editor/examples/extensions/flagship-local/reigh-extension.json:98:      "warning.trustedLocal": "⚠️ Trusted-local extension: this extension executes with full browser-renderer privileges. Review the extension source before enabling it in a shared project.",
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:149:    enableVertexAttribArray: vi.fn(),
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:300:      enabled: shader.enabled !== false,
src/tools/video-editor/components/ExtensionManager/index.ts:2:export { ExtensionTrustWarningBanner } from './ExtensionTrustWarningBanner';
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:161:      enabled: shader.enabled !== false,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:262:        disabled: false,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:268:        disabled: true,
scripts/quality/check-slot-first-health.mjs:6:const enforce =
scripts/quality/check-slot-first-health.mjs:7:  args.has('--enforce') ||
scripts/quality/check-slot-first-health.mjs:8:  process.env.SLOT_FIRST_HEALTH_ENFORCE === '1' ||
scripts/quality/check-slot-first-health.mjs:9:  process.env.CI_SLOT_FIRST_ENFORCE === '1';
scripts/quality/check-slot-first-health.mjs:63:if (enforce && (!hasDbTarget || !hasDbTool)) {
scripts/quality/check-slot-first-health.mjs:64:  console.error('[slot-first-health] FAIL: enforcement requires DB connection details and psql or Supabase CLI.');
scripts/quality/check-test-fixture-legacy.mjs:8:const enforce =
scripts/quality/check-test-fixture-legacy.mjs:9:  args.has('--enforce') ||
scripts/quality/check-test-fixture-legacy.mjs:10:  process.env.SLOT_FIRST_FIXTURE_LEGACY_ENFORCE === '1' ||
scripts/quality/check-test-fixture-legacy.mjs:11:  process.env.CI_SLOT_FIRST_ENFORCE === '1';
scripts/quality/check-test-fixture-legacy.mjs:51:  if (enforce) {
scripts/quality/check-test-fixture-legacy.mjs:59:  console.warn(`${heading} M0 audit mode is inactive; M4 flips enforcement.`);
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:5: * status badges, metadata, state reasons, and per-package enable/disable
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:6: * controls backed by ExtensionStateRepository.putEnablementState.
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:9: * the host; does not add external package resolution, install, update,
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:12: * Visibility principle (SD3): Disabled packages remain visible and
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:43:  ExtensionEnablementState,
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:48:import { ExtensionTrustWarningBanner } from './ExtensionTrustWarningBanner';
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:64:  'disabled-by-user': {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:65:    label: 'Disabled',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:273:// Enable/disable save state
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:278:const DISABLE_REASON = 'User disabled via extension manager';
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:279:const ENABLE_REASON = 'User enabled via extension manager';
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:846:              disabled={!isDirty}
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:847:              className="inline-flex items-center gap-1 rounded bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-medium text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:857:              disabled={!isDirty}
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:858:              className="inline-flex items-center gap-1 rounded bg-muted/50 border border-border px-2 py-0.5 text-[10px] font-medium text-muted-foreground hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:955:              disabled={!rawJsonDirty}
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:956:              className="inline-flex items-center gap-1 rounded bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-medium text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:966:              disabled={!rawJsonDirty}
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:967:              className="inline-flex items-center gap-1 rounded bg-muted/50 border border-border px-2 py-0.5 text-[10px] font-medium text-muted-foreground hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1025:  const isToggleable = packageState === 'loaded' || packageState === 'disabled-by-user';
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1026:  const isCurrentlyEnabled = packageState === 'loaded';
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1053:    const newEnabled = !isCurrentlyEnabled;
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1054:    const reason = newEnabled ? ENABLE_REASON : DISABLE_REASON;
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1057:    const enablementState: ExtensionEnablementState = {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1059:      enabled: newEnabled,
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1068:      await repository.putEnablementState(enablementState);
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1073:      setSaveError(err instanceof Error ? err.message : 'Failed to save enablement state');
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1075:  }, [extensionId, isCurrentlyEnabled, onToggleRequest, repository]);
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1164:              disabled={saveState === 'saving'}
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1165:              className="inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors hover:bg-muted/60 disabled:cursor-not-allowed disabled:opacity-50"
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1168:                  ? `Saving ${extensionId} enablement state`
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1170:                    ? `Retry saving ${extensionId} enablement state`
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1171:                    : isCurrentlyEnabled
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1172:                      ? `Disable ${extensionId}`
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1173:                      : `Enable ${extensionId}`
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1182:              ) : isCurrentlyEnabled ? (
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1185:                  <span className="text-emerald-400">Enabled</span>
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1190:                  <span className="text-zinc-400">Disabled</span>
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1305:      'disabled-by-user': 0,
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1339:      {counts['disabled-by-user'] > 0 && (
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1342:          {counts['disabled-by-user']} disabled
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1434:        <ExtensionTrustWarningBanner />
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:1452:      <ExtensionTrustWarningBanner />
scripts/quality/check-sdk-public-exports.mjs:15: *   --release              Full enforcement: any unlisted internal re-export
scripts/quality/check-sdk-public-exports.mjs:485:      `These are warnings only in audit mode. Use --release for strict enforcement.`,
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:126:function installMediaMocks(options: { getUserMedia?: ReturnType<typeof vi.fn> } = {}) {
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:293:    provenance: 'trusted-loader',
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:385:    const media = installMediaMocks();
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:38:function installMediaMocks(options: {
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:196:  it('publishes permission diagnostics and stops cleanup before any frame channel remains', async () => {
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:198:    installMediaMocks({ getUserMedia });
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:210:        code: 'live-webcam/permission-denied',
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:218:    const media = installMediaMocks();
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:282:    const media = installMediaMocks();
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:341:    const hmrMedia = installMediaMocks();
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:367:    const disposeAllMedia = installMediaMocks();
scripts/quality/check-frontend-closure-matrix.mjs:10: *  3. State coverage (empty / loading / error / disabled) is documented.
scripts/quality/check-frontend-closure-matrix.mjs:109:const UI_STATE_NAMES = ['empty', 'loading', 'error', 'disabled'];
scripts/quality/check-frontend-closure-matrix.mjs:366:        /^\s*[-*]\s*\*\*(Empty|Loading|Error|Disabled):\*\*\s*(.+)/i,
scripts/quality/check-frontend-closure-matrix.mjs:543:    // descriptive or reference a directory / test runner pattern).
scripts/quality/run-slot-pgtap.mjs:10:const enforce =
scripts/quality/run-slot-pgtap.mjs:11:  args.has('--enforce') ||
scripts/quality/run-slot-pgtap.mjs:12:  process.env.SLOT_FIRST_PGTAP_ENFORCE === '1' ||
scripts/quality/run-slot-pgtap.mjs:13:  process.env.CI_SLOT_FIRST_ENFORCE === '1';
scripts/quality/run-slot-pgtap.mjs:63:  if (enforce) {
scripts/quality/run-slot-pgtap.mjs:64:    console.error(`${message} Install psql or unset enforcement for M0 audit mode.`);
scripts/quality/run-slot-pgtap.mjs:73:  if (enforce) {
scripts/quality/check-extension-deferred-claims.mjs:11: * (marketplace, cloud loading, sandbox enforcement, remote package install,
scripts/quality/check-extension-deferred-claims.mjs:87:    term: 'sandbox enforcement',
scripts/quality/check-extension-deferred-claims.mjs:88:    pattern: 'sandbox|iframe.*extension|Worker.*extension|ShadowRealm',
scripts/quality/check-extension-deferred-claims.mjs:91:      'Sandboxed execution (iframe/Worker/ShadowRealm) is deferred in V1',
scripts/quality/check-extension-deferred-claims.mjs:94:    term: 'remote package install',
scripts/quality/check-extension-deferred-claims.mjs:95:    pattern: 'npm\\s+install|dynamic\\s+import.*extension|CDN.*extension|remote.*package',

exec
/bin/zsh -lc 'find src/tools/video-editor/examples/extensions -name reigh-extension.json -maxdepth 3 -print | sort' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
src/tools/video-editor/examples/extensions/agent-tools-canary/reigh-extension.json
src/tools/video-editor/examples/extensions/agent-tools-copilot/reigh-extension.json
src/tools/video-editor/examples/extensions/agent-tools-export/reigh-extension.json
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json
src/tools/video-editor/examples/extensions/flagship-local/reigh-extension.json
src/tools/video-editor/examples/extensions/live-generated-frame-canary/reigh-extension.json
src/tools/video-editor/examples/extensions/live-webcam-canary/reigh-extension.json
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json

exec
/bin/zsh -lc "sed -n '1,260p' docs/extensions/loading.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
# Extension Loading Persistence

M2 stores extension state through the active video-editor `DataProvider`.

Providers opt in by implementing `createExtensionPersistenceService(scope, diagnostics)`.
The scope is always `{ userId, timelineId }`, and every persisted state record,
settings snapshot, and proposal belongs to that pair.

The service exposes three surfaces:

- `stateRepository` for installed pack records, enablement, lifecycle events,
  dev overrides, settings snapshots, and lock metadata.
- Settings facade methods (`putSettings`, `getSettings`, `getAllSettings`,
  `deleteSettings`) over the repository settings snapshot model.
- Proposal storage (`createProposal`, `getProposal`, `updateProposalStatus`,
  `queryProposals`) as the M3 foundation.

Hydration happens before runtime repository use. Browser-local and Supabase
providers hydrate into the shared cache-backed repository, then reads are served
from memory. Writes update memory immediately and flush asynchronously.

Hydration failures fail closed. Corrupt or future-version snapshots emit
diagnostics and expose no partial extension state. The direct-extension fast path
is preserved: when no repository or provider service exists, direct extensions
load without requiring persistence.

Settings snapshots carry `schemaVersion`. Compatible versions hydrate normally;
future unknown versions fail closed. Any migration must be explicit in the cache
layer before a newer schema is accepted.

Proposal storage is intentionally small in M2: create, read, status update, and
query. Marketplace install/update/uninstall workflows and proposal policy
execution are out of scope until later milestones.

exec
/bin/zsh -lc "sed -n '1,240p' docs/extensions/authoring.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
# Extension Authoring

This guide documents extension-authored behavior for the Reigh M4 runtime:
diagnostic scoping, capacity and eviction, settings schema requirements, SchemaForm
V1 field support, and lifecycle cleanup expectations.

## Diagnostics

### Provenance and Source Scoping

Every diagnostic emitted by extension code carries `source: 'extension'`
(`DIAGNOSTIC_SOURCE_EXTENSION`).  Extensions **cannot** set host-owned diagnostic
sources (`'render'`, `'provider'`, or any future host source).  The
`ExtensionDiagnosticsService.report()` method omits both `extensionId` and
`source` from its caller-facing type signature and always writes
`source: DIAGNOSTIC_SOURCE_EXTENSION` at runtime — making host-source spoofing
impossible at both the TypeScript and runtime levels.

When a provider synchronizes extension diagnostics into its own diagnostic
collection via `diagnosticCollectionSync`, the top-level `Diagnostic.source`
remains `'extension'`.  Any finer-grained provenance the extension placed in
`detail.source` (e.g. `'fragment'` for a shader stage) is preserved in
`detail.diagnosticSource` so provider-side cleanup scoping (`removeByExtensionId`)
does not touch host-owned diagnostic sources.

### Per-Extension Capacity and Eviction

Each diagnostic collection enforces a **per-extension capacity** (default 100,
configurable via `CreateDiagnosticCollectionOptions.perExtensionCapacity`).
When publishing a new diagnostic for an extension would exceed that limit, the
**oldest diagnostic for that extension** is evicted before the new one is added.
Replacing a diagnostic by its existing ID does not count against the capacity.

The default constant is exported as `DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY`
(`100`).  Extension authors do not need to configure this; it is a host-side
guard against unbounded diagnostic growth.

### Scoped Removal

Providers call `DiagnosticCollection.removeByExtensionId(extensionId)` when an
extension is disabled or unloaded.  This removes only diagnostics where
`source === 'extension'` and `extensionId` matches — host-owned diagnostics and
diagnostics from other extensions are never affected.  The method is idempotent
(calling it multiple times is safe) and notifies subscribers once per removal.

## Settings

### Settings Schema Declaration

Extensions declare their settings shape via `manifest.settingsSchema`, which
must be a JSON Schema object with `type: 'object'` and a non-empty `properties`
map.  The `adaptManifestSettingsSchema()` adapter converts this into a
`StandardSchema` consumable by `SchemaForm`.  If the manifest schema is
missing, malformed, or not an object type, the adapter returns `null` for the
schema and emits diagnostic entries that providers surface through the active
diagnostic collection.

Supported JSON Schema keywords per property:

- `type` (`'string'`, `'number'`, `'integer'`, `'boolean'`)
- `title`, `description`
- `default`
- `enum` (rendered as a select dropdown)
- `minimum`, `maximum`
- `minLength`, `maxLength`, `pattern` (string fields)
- `required` (via the schema-level `required` array)

`'integer'` is mapped to SchemaForm's `number` type (the widget layer
distinguishes integer vs. float via step constraints).

### Atomic Save

Settings saves are **atomic**: the `ExtensionSettingsService.set()` method
compiles the full manifest schema with Ajv, builds a candidate state that
merges defaults → snapshot → localStorage overrides → the pending key-value
pair, validates the entire candidate against the schema, and only writes to
localStorage when validation passes.  An invalid save is silently blocked with
**zero partial mutation** — existing overrides are preserved exactly as they
were before the failed save attempt.

When no schema is declared (permissive mode), all saves are accepted.

## SchemaForm V1 Field Support

### Supported Primitive Fields

SchemaForm V1 renders these field types with native host widgets:

| Type | Widget | Constraints Honored |
| --- | --- | --- |
| `string` | `<input type="text">` | `minLength`, `maxLength`, `pattern`, `required` |
| `number` / `integer` | `<NumberInput>` / `<Slider>` | `minimum`, `maximum`, `step`, `required` |
| `boolean` | `<Switch>` | `required` (visual indicator only) |
| `select` / `enum` | Radix UI `<Select>` dropdown | `required` |
| `color` | `<input type="color">` (hex picker) | `required` |

All supported fields receive accessible metadata: `<label>` with deterministic
`id` (`schema-form-{name}-label`), `<description>` with
`aria-describedby` wiring, required markers (`*` with `aria-label="required"`),
`aria-required` on native inputs, and `aria-invalid` + error message ID chaining
when validation fails.

### Unsupported Schema Shapes

SchemaForm V1 explicitly detects and renders **read-only diagnostic placeholders**
for the following JSON Schema constructs.  These placeholders are non-mutating
and display a descriptive diagnostic code:

| Shape | Diagnostic Code | Behavior |
| --- | --- | --- |
| `array` / `items` | `schema/unsupported-array` | Read-only placeholder |
| Nested `object` with `properties` | `schema/unsupported-nested-object` | Read-only placeholder |
| `$ref` | `schema/unsupported-$ref` | Read-only placeholder |
| `oneOf` | `schema/unsupported-oneOf` | Read-only placeholder |
| `anyOf` | `schema/unsupported-anyOf` | Read-only placeholder |
| `allOf` | `schema/unsupported-allOf` | Read-only placeholder |
| Conditional (`if`/`then`/`else`) | `schema/unsupported-conditional` | Read-only placeholder |

Unsupported shapes do **not** accept input, do **not** produce values in save
payloads, and emit a `warning`-severity diagnostic through the host's
diagnostic collection so extension authors can see which fields need migration.

### Validation and Error Focus

`SchemaForm` exposes a `SchemaFormHandle` imperative interface via
`forwardRef`.  The `validateAndFocus()` method:

1. Validates every field against its constraints.
2. Focuses the **first invalid field's widget** DOM element.
3. Falls back to focusing an **error summary** when no individual field element
   is available.
4. Returns `true` when all fields pass, `false` otherwise.

This is used by the `ExtensionSettingsPanel` save flow: on save click,
`validateAndFocus()` is called; if it returns `false`, the save is blocked and
the first invalid field receives focus.

## Lifecycle Cleanup

### Disable / Unload Cleanup

When an extension is disabled or unloaded, the `ExtensionLifecycleHost` invokes
the `onLifecycleDisposed` callback registered by the provider.  The shared
cleanup contract guarantees:

1. **Diagnostics**: `removeExtensionDiagnosticsFromCollection(extensionId)` is
   called, which uses `DiagnosticCollection.removeByExtensionId()` to scope
   removal to extension-authored diagnostics only.  Host-owned diagnostics
   (those without an `extensionId` or with `source !== 'extension'`) survive
   the cleanup.

2. **Settings UI state**: `clearExtensionSettingsFromLocalStorage(extensionId)`
   clears all localStorage keys under the `reigh.ext.{extensionId}.` prefix.
   This resets the extension's settings-derived UI state without touching
   settings data for unrelated extensions.

3. **Contribution registries**: Each lifecycle-owned contribution registry
   (effects, transitions, shaders, clip types) calls its scoped
   `unregisterOwner(extensionId)` or `unregisterAll(extensionId)` method.
   Only the disposed extension's entries are removed; unrelated extensions
   are unaffected.

4. **Commands and keybindings**: `commandRegistry.unregisterAll(extensionId)`
   removes the extension's commands, keybindings, context menu items, and
   invocation history (`runStatuses`).  Other extensions' command registrations
   and history are preserved.

5. **Render boundaries**: `ContributionErrorBoundary` instances with a
   `recoveryKey` prop reset only when the key changes, preventing infinite
   crash→recover→crash loops.  On disable, the boundary detaches cleanly.

### Re-Enable

After disable+cleanup, an extension can be re-enabled.  All cleanup is scoped,
so re-enable produces:

- **No duplicate** diagnostic entries, command registrations, keybindings,
  context menu items, or contribution registry records.
- **Fresh** lifecycle state (inactive → activating → active) with a new
  diagnostics service and contribution registrations.
- **Persisted settings** that survive disable/re-enable cycles (settings
  cleanup only happens through explicit user action, not automatic lifecycle).

### Provider Parity

Both `EditorRuntimeProvider` and `VideoEditorProvider` implement the same
cleanup contract via `ExtensionLifecycleHost.onLifecycleDisposed()`.  Every
contribution family (effects, transitions, shaders, clip types, commands,
keybindings) behaves identically across both providers.

exec
/bin/zsh -lc "sed -n '1,220p' docs/extensions/phase4-readiness.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
# Phase 4 Extension Readiness Gate

Date: 2026-06-23
Scope: readiness review before public contribution-family promotion.

This artifact is the Phase 4 gate requested by the extension manager milestone.
It reconciles current runtime behavior, render/export planning, trust posture,
and the roadmap/ticket backlog without editing the roadmap or ticket source
documents.

## Current Code Anchors

- The roadmap and ticket backlog still name
  `src/tools/video-editor/runtime/contributionFamilies.ts` as the contribution
  family matrix. That file is not present in this checkout. The current
  runtime family sources are `src/sdk/index.ts`, which defines
  `ContributionKind`, `KNOWN_CONTRIBUTION_KINDS`,
  `CONTRIBUTION_KIND_MILESTONE`, and `contributionKindNotYetBridged()`, and
  `src/tools/video-editor/runtime/extensionSurface.ts`, which normalizes active
  or reserved contributions into provider/runtime descriptors.
- `src/tools/video-editor/runtime/extensionSurface.ts` currently bridges or
  surfaces reserved descriptors for output formats, processes, shaders, and
  agent tools. Output formats are turned into planner metadata with route
  requirements, process requirements, blockers, next actions, sidecars, and
  capability metadata. Process descriptors are surfaced as planner-visible
  declarations without starting a runtime process.
- `src/tools/video-editor/lib/renderRouter.ts` remains the route decision
  adapter for user render clicks. It converts native, themed, generated
  Remotion module, and contributed clip content into `CapabilityRequirement`
  entries, calls `planRender()`, and returns a planner-backed route decision.
- `src/tools/video-editor/runtime/renderPlanner.ts` is the canonical render
  readiness reducer. It consumes timeline snapshot requirements, explicit
  requirements, output format descriptors, process descriptors, shader
  descriptors, material refs/statuses, render groups, request constraints, and
  diagnostics, then returns route plans, blockers, diagnostics, next actions,
  and `canBrowserExport`/`canWorkerExport`.

## Render Planner Participation Contract

Any Phase 4 family that can affect preview, export, generated artifacts, or
determinism must participate in planning through stable capability metadata
before it can be promoted to public support.

Required contract:

1. Each promoted family must expose provider-free planner inspection data. The
   planner must not import live registries, component implementations, provider
   stores, or extension package handles.
2. Each render-relevant contribution must declare one or more route-level
   `CapabilityRequirement` records or a descriptor that `planRender()` can
   convert into equivalent requirements.
3. Unsupported, preview-only, live-unbaked, missing-material, stale-material,
   process-dependent, missing-contribution, and route-unsupported states must
   produce actionable `RenderBlocker` records rather than silent fallback.
4. Route decisions must remain planner-backed. For clip routing,
   `renderRouter.ts` already indexes contributed clip records by `clipTypeId`,
   allows browser export only when the contribution explicitly declares a
   supported browser-export capability, and blocks worker conflicts for
   contributed code.
5. Output-format and process families must keep using planner descriptors
   rather than invoking providers directly from the planner. Current
   `extensionSurface.ts` output-format descriptors are the model: route
   requirements, process requirements, blockers, next actions, sidecars, and
   capability metadata are data, not execution.
6. Shader and render-material families must distinguish preview from export.
   Current `renderPlanner.ts` shader materializer handling discovers
   materializer routes, emits process-dependent blockers/next actions, and
   keeps unresolved material refs from silently exporting.
7. Diagnostics published from planner findings must remain source-scoped so
   Extension Manager and diagnostics surfaces can show package/family blockers
   without confusing them with extension-authored runtime diagnostics.

Promotion is blocked for any family whose content can render, mutate timeline
state, invoke processes, consume live data, or produce export artifacts without
planner-visible requirements and failure states.

## Trust And Sandbox Posture

Phase 4 must continue the current explicit trust posture:

- Extension code runs as trusted, unsandboxed code in the host environment.
- Manifest permissions are declarative metadata only; they are not runtime
  enforcement, sandbox isolation, code signing, or a permission broker.
- The Extension Manager warning introduced in Phase 3 is therefore a product
  requirement, not just documentation. It must stay visible during loading,
  empty, populated, selected-package, and error states.
- Public promotion of arbitrary code families such as effects, transitions,
  clip types, agent tools, local processes, shaders, and sidecars is blocked
  until the accepted posture is either "trusted/signed local packages only" or
  a real sandbox/permission broker exists.
- If Phase 4 proceeds under trusted-local assumptions, every affected doc,
  manager surface, example, and compatibility table must avoid implying iframe
  isolation, runtime permission enforcement, marketplace review, or safe
  third-party execution.

## Per-Family Promotion Checklist

Apply this checklist to each family before changing compatibility status to
supported.

| Gate | Requirement |
| --- | --- |
| Manifest/schema | `config/contracts/reigh-extension.schema.json` accepts exactly the supported shape and rejects unknown or deferred fields. |
| Public SDK | `src/sdk/index.ts` exports stable types and public helpers only; examples do not import internals. |
| Runtime normalization | `extensionSurface.ts` or the owning runtime module converts manifest declarations into immutable provider-scoped descriptors with extension ID, contribution ID, order, disabled state, and diagnostics. |
| Lifecycle cleanup | Disable/unload unregisters renderers, commands, keybindings, diagnostics, settings-derived UI state, live channels, process handles, or shader resources owned by the extension. |
| Persistence posture | Any persisted state has provider-backed semantics or an explicit unsupported diagnostic. Settings/proposals must survive reload only where providers claim conformance. |
| Settings/parameters | Parameter schemas render through SchemaForm or an equivalent host-owned primitive, with unsupported shapes diagnosed and non-corrupting. |
| Diagnostics | Loader, runtime, planner, and extension-authored diagnostics are scoped by extension ID and contribution ID where applicable, bounded, and cleaned up. |
| Render planning | Preview/export capability, determinism, material/process requirements, and blockers are visible to `planRender()` before execution. |
| UI integration | Picker, inspector, manager, diagnostics, empty/loading/error/disabled states, and provenance labels are present where the family is visible. |
| Tests | Unit, provider/lifecycle, render planner, negative schema/runtime, and browser acceptance coverage prove supported and failure paths. |
| Docs/examples | Authoring, loading, compatibility, examples, and release gates agree on support status and trust posture. |

Family-specific readiness:

| Family | Minimum readiness before support |
| --- | --- |
| Asset parser | Permission/declaration checks, parser failure diagnostics, safe asset metadata enrichment, query/filter API boundaries, and export/bake posture. |
| Effect | Trusted/signed package decision, parameter SchemaForm, picker/inspector provenance, preview errors, serialization/reload, and planner blockers for preview-only or unsupported export. |
| Transition | Provider-scoped registry, selector/inspector parameters, missing/disabled repair behavior, serialization/reload, render coverage, and export blockers. |
| Clip type | Sequence-backed subset first, insertion/inspection/rendering, serialization/reload, duplicate/missing/blocked capability failures, and planner participation through `renderRouter.ts`/`planRender()`. |
| Keyframes | Minimal model, commands/proposals, migration, interpolation tests, and deterministic preview/export delivery. |
| Agent tool | Proposal-first destructive behavior, backend dispatch registry, permission declarations, result-family validation, persisted proposals, and disabled/failure diagnostics. |
| Live data | Source lifecycle, permission state, bounded ring buffer, bake-to-deterministic asset/material workflow, steering lineage, and unbaked export blockers. |
| Render material | Public material/capability declarations, artifact manifest integration, material status tracking, and planner blockers/next actions. |
| Process/sidecar | Trusted local process model, command/env/cwd policy, JSON-RPC protocol, health/log/cancel/shutdown behavior, manager health UI, and explicit trust warnings. |
| Shader/WebGL | Source/uniform/texture schema, compile diagnostics, deterministic preview canaries, context-loss fallback, materializer/export route posture, and honest export blockers. |

## Roadmap And Ticket Reconciliation

This table records what must be reconciled after review. It intentionally does
not edit `docs/extensions/reigh-extension-layer-roadmap-v2.md` or
`docs/extensions/reigh-extension-layer-tickets.md`.

| Source item | Current status | Reconciliation needed before Phase 4 |
| --- | --- | --- |
| Roadmap Phase 1 acceptance cites `runtime/contributionFamilies.ts` | Stale path in this checkout; contribution kind data currently lives in `src/sdk/index.ts`, and runtime descriptor normalization lives in `extensionSurface.ts`. | Update roadmap/ticket references after review, or restore a generated/owned contribution-family matrix file if that remains the intended gate. |
| Roadmap Phase 4 "Contribution Families And Render Hardening" | Correctly identifies asset parsers, effects, transitions, clip types, keyframes, agent tools, live data, render materials, sidecars/processes, and shaders as the next higher-power families. | Keep this sequencing, but require the checklist above and planner participation before any family moves to supported. |
| EXT-030 AssetParserContribution | Planned. | Add explicit render/export/bake posture and diagnostics requirements to the ticket if asset parser output can affect timeline materialization. |
| EXT-031 EffectContribution | Planned as trusted/signed packages. | Preserve trusted/signed wording, add manager trust warning coverage, and require planner blockers for preview-only effects. |
| EXT-032 TransitionContribution | Planned. | Add route capability metadata and fallback/repair behavior to prevent silent export differences. |
| EXT-033 ClipTypeContribution | Planned as a sequence-backed subset. | Keep subset scope; require `renderRouter.ts` contributed clip records and `planRender()` blockers before support. |
| EXT-034 Keyframes | Planned. | Treat as timeline data/model work first, not an extension family shortcut; require proposal/migration/render interpolation gates. |
| EXT-035 Render planner integration | Planned. | Promote this from a later hardening ticket to a prerequisite for every render-relevant family. |
| EXT-036 AgentToolContribution | Planned. | Block until proposal persistence and backend dispatch registry are stable; no direct destructive mutation by default. |
| EXT-037 Live data | Planned. | Block until bake/export semantics are accepted; unbaked live bindings must block export. |
| EXT-038 RenderMaterialContribution | Planned. | Tie directly to planner material refs/statuses, artifact manifests, and next actions. |
| EXT-039 Process/sidecar runtime | Planned as trusted local runtime. | Require separate trust approval, process policy, health UI, cancellation, and shutdown tests before public exposure. |
| EXT-040 Shader/WebGL bridge | Planned. | Keep behind render materialization posture and deterministic preview/export blocker tests. |
| EXT-041 Final docs/examples/validation | Planned. | Must include this readiness checklist as a closure matrix input, plus compatibility drift checks across schema, SDK, runtime, docs, examples, and tests. |

## Phase 4 Entry Decision

Phase 4 should not start as broad parallel family implementation. The next
accepted action should be either:

1. Fix the stale `contributionFamilies.ts` reference by restoring or replacing
   the family matrix gate, then update roadmap/ticket docs after review; or
2. Begin EXT-035-style render planner integration as a prerequisite slice for
   the first selected family, with this document as the acceptance checklist.

Until one of those paths is accepted, the readiness decision is: Phase 4 is
prepared but not cleared for public family promotion.

exec
/bin/zsh -lc "sed -n '1,160p' docs/extensions/compatibility.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
# Extension Provider Compatibility

Extension persistence support is determined by a provider factory plus the
shared conformance suite. Static capability flags are descriptive only.

| Provider | State | Settings | Proposals | Notes |
| --- | --- | --- | --- | --- |
| InMemoryDataProvider | Supported | Supported | Supported | Test-only baseline for conformance. |
| Browser-local provider | Supported | Supported | Supported | Uses localStorage for small snapshots and IndexedDB for proposals. |
| SupabaseDataProvider | Supported | Supported | Supported | Uses scoped extension tables with user/timeline filters. |
| AstridBridgeDataProvider | Unsupported in M2 | Unsupported in M2 | Unsupported in M2 | Emits normalized unsupported diagnostics. |

Unsupported providers must use the normalized diagnostics helper and emit:

- `provider_capability_extension_state_unsupported`
- `provider_capability_extension_settings_unsupported`
- `provider_capability_extension_proposals_unsupported`

Proposal storage has M2 limits. It is persistence only: proposals can be created,
read, status-updated, and queried, but no M3 policy execution, marketplace
review flow, install/update/uninstall orchestration, or cleanup worker is added
by this milestone.

Provider implementations must keep all extension data scoped by `userId` and
`timelineId`, and must pass
`src/tools/video-editor/data/conformance/extensionPersistenceConformance.ts`
before advertising support.

## M4: Diagnostic Scoping and Cleanup

### Extension-Authored Diagnostic Source

All extension-authored diagnostics carry `source: 'extension'`
(`DIAGNOSTIC_SOURCE_EXTENSION`).  The `ExtensionDiagnosticsService.report()`
interface prevents extensions from setting host-owned sources (`'render'`,
`'provider'`).  Runtime enforcement guarantees `source` is always
`'extension'` for extension-authored diagnostics — host-source spoofing is
impossible at both the TypeScript and runtime layers.

Providers synchronize extension diagnostics into their diagnostic collection
via `extensionDiagnosticToCollectionDiagnostic()`, which preserves the
`DIAGNOSTIC_SOURCE_EXTENSION` source and stashes any caller-provided
`detail.source` into `detail.diagnosticSource`.

### Per-Extension Diagnostic Capacity

Every `DiagnosticCollection` enforces `DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY`
(100) with **oldest-first eviction** per extension ID.  When publishing a new
diagnostic would exceed the capacity for a given extension, the oldest
diagnostic for that extension is evicted before the new one is added.
Replacement by existing ID does not count against the capacity.  The capacity
is configurable via `CreateDiagnosticCollectionOptions.perExtensionCapacity`.

### Scoped Diagnostic Removal

Providers must use `DiagnosticCollection.removeByExtensionId(extensionId)` for
cleanup on extension disable/unload.  This method removes only diagnostics
where `source === 'extension'` and `extensionId` matches, leaving host-owned
diagnostics intact.  The method is idempotent and notifies subscribers once.

## M4: Extension Settings

### SchemaForm V1 Supported Primitives

SchemaForm V1 renders these JSON Schema types natively:

- `string` (text input) — `minLength`, `maxLength`, `pattern`, `required`
- `number` / `integer` (NumberInput / Slider) — `minimum`, `maximum`, `step`, `required`
- `boolean` (Switch toggle) — `required`
- `enum` (Select dropdown) — `required`
- `color` (hex color picker) — `required`

`'integer'` is mapped to SchemaForm's `number` type internally.

### Unsupported Schema Shapes

SchemaForm V1 explicitly detects unsupported shapes and renders **read-only,
non-mutating** diagnostic placeholders.  Detected shapes:

- `array` / `items` — diagnostic code `schema/unsupported-array`
- Nested `object` with `properties` — `schema/unsupported-nested-object`
- `$ref` — `schema/unsupported-$ref`
- `oneOf` / `anyOf` / `allOf` — `schema/unsupported-oneOf`, etc.
- Conditional schemas (`if`/`then`/`else`) — `schema/unsupported-conditional`

Each placeholder emits a `warning`-severity diagnostic through the host
diagnostic collection.  Unsupported fields do not produce values in save
payloads.

### Atomic Save Behavior

`ExtensionSettingsService.set()` validates the full candidate state against
the compiled Ajv schema before writing.  Invalid saves are silently blocked
with **zero partial mutation** — existing overrides are preserved.  In
permissive mode (no schema), all saves are accepted.

### Settings-Derived UI State Reset

On extension disable/unload, providers call
`clearExtensionSettingsFromLocalStorage(extensionId)` to clear all localStorage
keys under the `reigh.ext.{extensionId}.` prefix.  This resets settings-derived
UI state without affecting unrelated extensions.

## M4: Lifecycle Cleanup Contract

### Shared Cleanup via onLifecycleDisposed

Both `EditorRuntimeProvider` and `VideoEditorProvider` register an
`onLifecycleDisposed` callback with `ExtensionLifecycleHost`.  When an
extension is disabled or unloaded, the callback executes the following scoped
cleanup:

1. **Diagnostics**: `removeExtensionDiagnosticsFromCollection(extensionId)` —
   uses `removeByExtensionId` for source-scoped removal.
2. **Settings UI**: `clearExtensionSettingsFromLocalStorage(extensionId)` —
   clears localStorage settings keys.
3. **Contribution registries**: Each lifecycle-owned registry calls its scoped
   `unregisterOwner(extensionId)` or `unregisterAll(extensionId)`.
4. **Commands**: `commandRegistry.unregisterAll(extensionId)` removes commands,
   keybindings, context menu items, and invocation history.

All cleanup is scoped to the target extension; unrelated extension state is
never affected.

### Crash Recovery

`ContributionErrorBoundary` supports a `recoveryKey` prop.  When provided, the
boundary resets error state only on explicit key change, preventing infinite
crash→recover→crash loops.  Legacy behavior (children-change reset) is
preserved when `recoveryKey` is absent.

### Re-Enable After Cleanup

Re-enabling an extension after disable/unload produces no duplicate
registrations, diagnostics, keybindings, or context menu items.  Persisted
settings survive disable/re-enable cycles; settings-derived UI state is reset
on disable only when the provider explicitly calls the cleanup helper.

Providers must verify these invariants through the shared extension lifecycle
test suite (`extensionLifecycle.test.ts`) and provider-level integration tests.

codex
Docs and UI are more honest than the criticism implies: there is a dedicated manager warning and a deferred matrix saying runtime permission enforcement is absent. The remaining issue appears to be a contract mismatch and possible “permissions” naming/copy that could still look like a browser-style permission system.
exec
/bin/zsh -lc "sed -n '1,80p' src/tools/video-editor/components/ExtensionManager/ExtensionTrustWarningBanner.tsx" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
import { AlertTriangle } from 'lucide-react';

export function ExtensionTrustWarningBanner() {
  return (
    <div
      className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-200"
      role="note"
      aria-label="Extension trust warning"
      data-video-editor-extension-trust-warning="true"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-400" aria-hidden="true" />
        <div className="min-w-0">
          <div className="font-medium text-yellow-100">Trusted extension code</div>
          <div className="mt-0.5 text-yellow-200/80">
            Extensions run as trusted, unsandboxed code. Manifest permissions are declarative and are not enforced at runtime.
          </div>
        </div>
      </div>
    </div>
  );
}

exec
/bin/zsh -lc "sed -n '1420,1470p' src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "sed -n '560,640p' src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
    it('renders empty state when no packages in inventory', () => {
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([]),
        extensionStateRepository: null,
        triggerExtensionRefresh: undefined,
      });

      render(<ExtensionManager />);

      expect(screen.getByText('No packages in inventory.')).toBeInTheDocument();
    });
  });

  describe('data attributes', () => {
    it('sets data-video-editor-extension-toggle on toggleable packages', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
      expect(toggle).toHaveAttribute('data-video-editor-extension-toggle', 'ext.a');
    });

    it('sets data-video-editor-extension-save-error when save fails', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.putEnablementState = vi.fn().mockRejectedValue(new Error('Boom'));

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
      await user.click(toggle);

      await waitFor(() => {
        const errorEl = document.querySelector('[data-video-editor-extension-save-error="ext.a"]');
        expect(errorEl).toBeInTheDocument();
        expect(errorEl).toHaveTextContent('Failed to save: Boom');
      });
    });
  });
});

// ---------------------------------------------------------------------------
// Persistent trust warning tests (T10)
// ---------------------------------------------------------------------------

describe('ExtensionManager — persistent trust warning', () => {
  beforeEach(() => {
    mockUseVideoEditorRuntime.mockReset();
  });

  function expectTrustWarningVisible() {
    const warning = screen.getByRole('note', { name: 'Extension trust warning' });
    expect(warning).toBeInTheDocument();
    expect(warning).toHaveTextContent('Extensions run as trusted, unsandboxed code.');
    expect(warning).toHaveTextContent('Manifest permissions are declarative and are not enforced at runtime.');
  }

  it('shows the trust warning during loading state', () => {
    render(<ManagerLoadingState />);

    expect(screen.getByText('Loading extensions…')).toBeInTheDocument();
    expectTrustWarningVisible();
  });

  it('shows the trust warning in empty inventory state', () => {

 succeeded in 0ms:
      );
      map.set(entry.extensionId, {
        errorCount: extDiags.filter((d) => d.severity === 'error').length,
        warningCount: extDiags.filter((d) => d.severity === 'warning').length,
        infoCount: extDiags.filter((d) => d.severity === 'info').length,
        diagnostics: extDiags,
      });
    }
    return map;
  }, [allDiagnostics, packageStateInventory]);

  if (packageStateInventory.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <ExtensionTrustWarningBanner />
        <div
          className="flex flex-col items-center justify-center gap-3 py-8 text-muted-foreground"
          role="status"
          aria-label="No packages in inventory"
        >
          <Zap className="h-8 w-8 opacity-40" />
          <span className="text-sm">No packages in inventory.</span>
          <span className="text-xs text-muted-foreground/60">
            Extensions supplied by the host will appear here.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <ExtensionTrustWarningBanner />
      <ManagerSummaryBar entries={packageStateInventory} />
      <div className="flex flex-col gap-2">
        {packageStateInventory.map((entry) => (
          <PackageCard
            key={entry.extensionId}
            entry={entry}
            contributionSummary={
              contributionSummaries.get(entry.extensionId) ?? null
            }
            repository={extensionStateRepository ?? null}
            onToggleRequest={triggerExtensionRefresh ?? (() => {})}
            manifest={manifestLookup.get(entry.extensionId) ?? null}
            diagnosticSummary={packageDiagnostics.get(entry.extensionId)}
          />
        ))}
      </div>
    </div>
  );

exec
/bin/zsh -lc "sed -n '320,375p' docs/video-editor/extension-platform-supported-deferred.md && sed -n '360,372p' docs/video-editor/extension-platform-supported-deferred.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-110 | `clip.split` and `clip.slice` operation families | **deferred** | CR:M3-016; reserved with `{ reserved: true, deferred: true }` warnings; DOC:timeline-patch-operations.md§4 |
| D-111 | Overlay shader composition surface (V1 has vocabulary only) | **deferred** | CR:M13-002; DOC:shader-execution-model.md (overlay vocabulary reserved, no V1 surface) |

### 3.12 Permissions & Sandboxing

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-120 | Runtime permission enforcement (network, filesystem, env, processes gating) | **deferred** | DOC:extensions-trust-envelope.md§3; ABSENCE:grep -r 'permission enforcement' src/tools/video-editor/runtime/ |
| D-121 | Sandboxed extension execution (iframe, Worker, ShadowRealm isolation) | **deferred** | DOC:extensions-trust-envelope.md§§5-6; ABSENCE:grep -r 'sandbox' src/tools/video-editor/runtime/; planned M4–M5 |
| D-122 | Dynamic package loading (npm / CDN / `import()` for extension code) | **deferred** | DOC:extensions-trust-envelope.md§2; ABSENCE:grep -r 'CDN.*extension' src/tools/video-editor/runtime/; extensions statically bundled with host |
| D-123 | Marketplace, cloud loading, or third-party extension registry | **unsupported** | CR:X-006; consistently OUT of scope for all milestones; ABSENCE:grep -r 'marketplace' src/sdk/ |

### 3.13 Structural Deferrals

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-130 | Proposal UI component tests (previewable, non-previewable, accepted, rejected, stale) | **deferred** | CR:M3-006; proposal-runtime.test.ts covers runtime; dedicated UI tests not identified |
| D-131 | DSL/compiler canary reading `CreativeContext.timeline`, storing source/source-map, emitting `TimelineProposal` | **deferred** | CR:M3-013; `SourceMapRuntime` exists; explicit DSL canary test not identified |
| D-132 | Proposal diff rendering, source-map navigation from diff/diagnostic UI, stale badges | **deferred** | CR:M3-015; infrastructure exists; dedicated rendering tests not identified |
| D-133 | Schema capability registry tests (supported widgets, unsupported diagnostics, validation, custom widget placeholder) | **deferred** | CR:M2-007; concept documented; dedicated registry tests not identified |
| D-134 | Extension status drawer: active extension IDs, contribution inventory, diagnostics, current blockers | **deferred** | CR:M2-009; skeletal concept; M14 owns full manager UI |
| D-135 | Subscription cleanup dedicated tests (leaked listener prevention) | **deferred** | CR:M2-002; `DisposeHandle` infrastructure exists; dedicated leak tests not identified |

---

## 4. V1 Scope Boundaries

### 4.1 Explicitly out-of-scope for V1

These behaviors are documented as unsupported across all milestones and have no active implementation path:

| Behavior | Evidence |
|---|---|
| Marketplace / extension registry | ABSENCE:grep -r 'marketplace' src/sdk/; CR:X-006 |
| Cloud extension loading | ABSENCE:grep -r 'cloud.*extension' src/tools/video-editor/runtime/ |
| Sandboxed execution (iframe/Worker/ShadowRealm) | DOC:extensions-trust-envelope.md§5 |
| Theme contributions | ABSENCE:grep -r 'theme.*contribution' src/sdk/index.ts |
| Public CRDT collaboration primitives | ABSENCE:grep -r 'CRDT' src/sdk/index.ts |

### 4.2 Active V1 trust model

| Concern | V1 Answer | Evidence |
|---|---|---|
| Execution context | Same-thread, same-origin JavaScript in the browser | DOC:extensions-trust-envelope.md§7 |
| Isolation | None | DOC:extensions-trust-envelope.md§1 |
| Permission enforcement | Descriptive only (no runtime gating) | DOC:extensions-trust-envelope.md§3 |
| Lifecycle visibility | Console groups + structured diagnostics + export guard | DOC:extensions-trust-envelope.md§7 |
| Error containment | Contribution-level error boundaries; activation throws → `failed` state + diagnostics | DOC:extensions-trust-envelope.md§5 |
| Source vetting | Human review required; no automated integrity checks in V1 | DOC:extensions-trust-envelope.md§7 |

---

## 5. Matrix Statistics


### 4.2 Active V1 trust model

| Concern | V1 Answer | Evidence |
|---|---|---|
| Execution context | Same-thread, same-origin JavaScript in the browser | DOC:extensions-trust-envelope.md§7 |
| Isolation | None | DOC:extensions-trust-envelope.md§1 |
| Permission enforcement | Descriptive only (no runtime gating) | DOC:extensions-trust-envelope.md§3 |
| Lifecycle visibility | Console groups + structured diagnostics + export guard | DOC:extensions-trust-envelope.md§7 |
| Error containment | Contribution-level error boundaries; activation throws → `failed` state + diagnostics | DOC:extensions-trust-envelope.md§5 |
| Source vetting | Human review required; no automated integrity checks in V1 | DOC:extensions-trust-envelope.md§7 |

---

exec
/bin/zsh -lc "rg -n \"manifest\\.permissions|permissions\\?|ExtensionPermissionDeclaration|permission enforcement|posture\\?\" src config docs scripts -S" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
config/contracts/registry.json:370:        "ExtensionPermissionDeclaration",
config/contracts/reigh-extension.schema.json:47:        "$ref": "#/definitions/ExtensionPermissionDeclaration"
config/contracts/reigh-extension.schema.json:751:    "ExtensionPermissionDeclaration": {
src/sdk/index.ts:2432:export interface ExtensionPermissionDeclaration {
src/sdk/index.ts:2436:  posture?: {
src/sdk/index.ts:2462:  posture?: DependencyPosture;
src/sdk/index.ts:3054:  permissions?: readonly ExtensionPermissionDeclaration[];
src/sdk/index.ts:4031:    permissions: manifest.permissions ? freezeManifestValue(manifest.permissions) : undefined,
src/sdk/index.ts:4152:  posture?: 'required' | 'optional';
src/sdk/__tests__/sdk-boundary.test.ts:3297:  ExtensionPermissionDeclaration,
src/sdk/__tests__/sdk-boundary.test.ts:3539:  it('ExtensionPermissionDeclaration shape is constructable', () => {
src/sdk/__tests__/sdk-boundary.test.ts:3540:    const perm: ExtensionPermissionDeclaration = {
src/sdk/__tests__/sdk-boundary.test.ts:3545:    expect(perm.posture?.network).toBe(true);
src/sdk/boundary.test.ts:45:  ExtensionPermissionDeclaration,
src/sdk/index.test.ts:299:    expect(Object.isFrozen(ext.manifest.permissions!)).toBe(true);
src/sdk/index.test.ts:300:    expect(Object.isFrozen(ext.manifest.permissions![0])).toBe(true);
src/sdk/smoke/extensionSmoke.ts:11: * loaders, or permission enforcement — it is a pure, inert, statically-
src/sdk/smoke/extensionSmoke.test.ts:224:    expect(ext.manifest.permissions).toBeUndefined();
src/examples/surface-coverage.ts:38:  ExtensionPermissionDeclaration,
src/examples/surface-coverage.ts:103:/** Demonstrate ExtensionPermissionDeclaration (reserved, descriptive only). */
src/examples/surface-coverage.ts:104:const examplePermission: ExtensionPermissionDeclaration = {

codex
The only production read of `manifest.permissions` I found is freezing it in `defineExtension`; no loader, normalizer, context factory, registry, process adapter, or manager code gates behavior on it. The JSON schema is also drifted from the SDK shape, which is a concrete source of confusion.
exec
/bin/zsh -lc "sed -n '3280,3560p' src/sdk/__tests__/sdk-boundary.test.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
  ExtensionChromeService,
  ChromeEvent,
  ChromeToastPayload,
  ChromeProgressPayload,
  ChromeEventPayload,
  ExtensionI18nService,
  MigrationHookKind,
  MigrationDeclaration,
  ExtensionDependency,
  DependencyPosture,
  ExtensionSettingsSchema,
  IntegrityAlgorithm,
  IntegrityHash,
  InstalledExtensionMetadata,
  InstalledExtensionPackage,
  ManifestValidationMode,
  ManifestValidationResult,
  ExtensionPermissionDeclaration,
} from '@reigh/editor-sdk';

describe('SDK diagnostics types are importable from @reigh/editor-sdk', () => {
  it('DiagnosticSeverity covers error, warning, info', () => {
    const severities: DiagnosticSeverity[] = ['error', 'warning', 'info'];
    expect(severities).toHaveLength(3);
  });

  it('DiagnosticSourceRange is constructable', () => {
    const range: DiagnosticSourceRange = {
      startLine: 10,
      startCol: 5,
      endLine: 15,
      endCol: 20,
    };
    expect(range.startLine).toBe(10);
    expect(range.endCol).toBe(20);
  });

  it('Diagnostic is constructable', () => {
    const diag: Diagnostic = {
      id: 'diag-1',
      severity: 'error',
      code: 'test/error',
      message: 'Test diagnostic',
      extensionId: 'com.test.ext',
      sourceRange: { startLine: 1, startCol: 1, endLine: 1, endCol: 10 },
      relatedRanges: [{ startLine: 2, startCol: 1, endLine: 2, endCol: 5 }],
      detail: { clipId: 'clip-1' },
    };
    expect(diag.id).toBe('diag-1');
    expect(diag.sourceRange?.startLine).toBe(1);
    expect(diag.relatedRanges).toHaveLength(1);
  });

  it('ExportDiagnostic has export/-prefixed codes', () => {
    const diag: ExportDiagnostic = {
      severity: 'warning',
      code: 'export/unknown-clip-type',
      message: 'Clip type not registered for export',
      detail: { clipId: 'clip-1', clipType: 'custom-clip' },
    };
    expect(diag.code).toBe('export/unknown-clip-type');
    expect(diag.detail?.clipId).toBe('clip-1');
    expect(diag.detail?.clipType).toBe('custom-clip');
  });

  it('ExportDiagnostic detail includes shader scope fields', () => {
    const diag: ExportDiagnostic = {
      severity: 'error',
      code: 'export/missing-shader-materializer',
      message: 'Shader has no materializer for export route',
      detail: {
        shaderId: 'shader.glow',
        shaderScope: 'clip' as ShaderMaterializerRequirementScope,
      },
    };
    expect(diag.detail?.shaderId).toBe('shader.glow');
    expect(diag.detail?.shaderScope).toBe('clip');
  });

  it('ExtensionDiagnosticsService interface shape is correct', () => {
    const svc: ExtensionDiagnosticsService = {
      report(_diag) {},
      diagnostics: [],
    };
    expect(typeof svc.report).toBe('function');
    expect(Array.isArray(svc.diagnostics)).toBe(true);
  });

  it('ExtensionChromeService interface shape is correct', () => {
    const svc: ExtensionChromeService = {
      toast(_msg, _severity) {},
      progress(_percent, _label) {},
      subscribe(_event, _handler) { return { dispose() {} }; },
      focus(_selector) {},
      announce(_message, _politeness) {},
    };
    expect(typeof svc.toast).toBe('function');
    expect(typeof svc.progress).toBe('function');
    expect(typeof svc.subscribe).toBe('function');
    expect(typeof svc.focus).toBe('function');
    expect(typeof svc.announce).toBe('function');
  });

  it('ChromeEvent covers toast, progress, save, renderStatus', () => {
    const events: ChromeEvent[] = ['toast', 'progress', 'save', 'renderStatus'];
    expect(events).toHaveLength(4);
  });

  it('ChromeEventPayload maps toast to ChromeToastPayload', () => {
    const payload: ChromeEventPayload<'toast'> = {
      message: 'Hello',
      severity: 'info',
    };
    expect(payload.message).toBe('Hello');
    expect(payload.severity).toBe('info');
  });

  it('ChromeEventPayload maps progress to ChromeProgressPayload', () => {
    const payload: ChromeEventPayload<'progress'> = {
      percent: 75,
      label: 'Exporting...',
    };
    expect(payload.percent).toBe(75);
    expect(payload.label).toBe('Exporting...');
  });

  it('ExtensionI18nService interface shape is correct', () => {
    const svc: ExtensionI18nService = {
      t(key, _replacements) { return key; },
    };
    expect(typeof svc.t).toBe('function');
    expect(svc.t('hello')).toBe('hello');
  });
});

describe('SDK migration types are importable from @reigh/editor-sdk', () => {
  it('MigrationHookKind covers settings, contribution, manifest', () => {
    const kinds: MigrationHookKind[] = ['settings', 'contribution', 'manifest'];
    expect(kinds).toHaveLength(3);
  });

  it('MigrationDeclaration shape is constructable', () => {
    const migration: MigrationDeclaration = {
      kind: 'settings',
      fromVersion: '1.0.0',
      toVersion: '2.0.0',
      handler: 'migrateSettings',
      description: 'Migrate settings from v1 to v2',
    };
    expect(migration.kind).toBe('settings');
    expect(migration.fromVersion).toBe('1.0.0');
    expect(migration.toVersion).toBe('2.0.0');
    expect(migration.handler).toBe('migrateSettings');
  });
});

describe('SDK packaging types are importable from @reigh/editor-sdk', () => {
  it('DependencyPosture covers required and optional', () => {
    const postures: DependencyPosture[] = ['required', 'optional'];
    expect(postures).toHaveLength(2);
  });

  it('ExtensionDependency shape is constructable', () => {
    const dep: ExtensionDependency = {
      extensionId: 'com.example.lib',
      versionRange: '^1.0.0',
      posture: 'required',
    };
    expect(dep.extensionId).toBe('com.example.lib');
    expect(dep.versionRange).toBe('^1.0.0');
    expect(dep.posture).toBe('required');
  });

  it('ExtensionDependency with optional and contributionIds is constructable', () => {
    const dep: ExtensionDependency = {
      extensionId: 'com.example.optional',
      versionRange: '>=1.0.0',
      optional: true,
      posture: 'optional',
      contributionIds: ['toolbar-main'],
    };
    expect(dep.optional).toBe(true);
    expect(dep.contributionIds).toEqual(['toolbar-main']);
  });

  it('IntegrityAlgorithm is only sha256', () => {
    const algo: IntegrityAlgorithm = 'sha256';
    expect(algo).toBe('sha256');
  });

  it('IntegrityHash shape is constructable', () => {
    const hash: IntegrityHash = {
      algorithm: 'sha256',
      value: 'dGVzdC1oYXNo',
    };
    expect(hash.algorithm).toBe('sha256');
    expect(hash.value).toBe('dGVzdC1oYXNo');
  });

  it('ExtensionSettingsSchema shape is constructable', () => {
    const schema: ExtensionSettingsSchema = {
      version: 1,
      schema: { type: 'object', properties: {} },
    };
    expect(schema.version).toBe(1);
    expect(schema.schema?.type).toBe('object');
  });

  it('InstalledExtensionMetadata shape is constructable', () => {
    const meta: InstalledExtensionMetadata = {
      extensionId: 'com.example.ext' as ExtensionId,
      version: '1.0.0',
      integrity: { algorithm: 'sha256', value: 'abc' },
      enabled: true,
      publisher: 'Example Corp',
      license: 'MIT',
    };
    expect(meta.extensionId).toBe('com.example.ext');
    expect(meta.enabled).toBe(true);
    expect(meta.publisher).toBe('Example Corp');
  });

  it('InstalledExtensionPackage shape is constructable', () => {
    const pkg: InstalledExtensionPackage = {
      metadata: {
        extensionId: 'com.example.ext' as ExtensionId,
        version: '1.0.0',
        integrity: { algorithm: 'sha256', value: 'abc' },
        enabled: true,
      },
      manifest: {
        id: 'com.example.ext' as ExtensionId,
        version: '1.0.0',
        label: 'Test Extension',
        publisher: 'Example Corp',
        license: 'MIT',
      },
      bundleContent: 'export function activate() {}',
    };
    expect(pkg.metadata.extensionId).toBe('com.example.ext');
    expect(pkg.manifest.id).toBe('com.example.ext');
    expect(pkg.bundleContent).toContain('export function activate');
  });

  it('ManifestValidationMode covers dev and installed', () => {
    const modes: ManifestValidationMode[] = ['dev', 'installed'];
    expect(modes).toHaveLength(2);
  });

  it('ManifestValidationResult shape is constructable', () => {
    const result: ManifestValidationResult = {
      valid: true,
      errors: [],
      warnings: [],
    };
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('ExtensionPermissionDeclaration shape is constructable', () => {
    const perm: ExtensionPermissionDeclaration = {
      reason: 'Needs network access for API calls',
      posture: { network: true },
    };
    expect(perm.reason).toContain('network');
    expect(perm.posture?.network).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// M10: Internal agent tool types are NOT leaked through @reigh/editor-sdk
// ---------------------------------------------------------------------------

describe('M10: internal agent tool types are NOT re-exported from @reigh/editor-sdk', () => {
  const M10_INTERNAL_FORBIDDEN = [
    'agentToolRegistry',
    'AgentToolRegistry',
    'registerAgentTool',
    'resolveAgentTool',
    'executeAgentTool',
    'AgentToolExecutor',

exec
/bin/zsh -lc "sed -n '280,310p' src/sdk/index.test.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "sed -n '90,112p' src/examples/surface-coverage.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
      }),
    ).toThrow(/Invalid contribution ID/);
  });

  it('freezes nested arrays (permissions, processes, dependsOn) when provided', () => {
    const manifestWithAll: ExtensionManifest = {
      ...validManifest,
      permissions: [{ reason: 'testing', posture: { network: true } }],
      processes: [
        {
          id: 'proc1',
          label: 'Test process',
          spawn: { command: 'echo', args: ['hello'] },
          protocol: 'stdio-jsonrpc',
        },
      ],
      dependsOn: [{ extensionId: 'com.other.lib', versionRange: '^1.0.0' }],
    };
    const ext = defineExtension({ manifest: manifestWithAll });
    expect(Object.isFrozen(ext.manifest.permissions!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.permissions![0])).toBe(true);
    expect(Object.isFrozen(ext.manifest.processes!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.processes![0])).toBe(true);
    expect(Object.isFrozen(ext.manifest.dependsOn!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.dependsOn![0])).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Contribution kind bridging
// ---------------------------------------------------------------------------

 succeeded in 0ms:
  env: { NODE_ENV: 'development' },
  cwd: '/tmp',
};

/** Demonstrate ProcessManifestEntry (reserved, descriptive only). */
const exampleProcessManifest: ProcessManifestEntry = {
  id: 'coverage-process',
  label: 'Coverage helper process',
  spawn: exampleProcessSpawn,
  protocol: 'stdio-jsonrpc',
  restartPolicy: 'on-failure',
};

/** Demonstrate ExtensionPermissionDeclaration (reserved, descriptive only). */
const examplePermission: ExtensionPermissionDeclaration = {
  reason: 'Network access for fetching project assets.',
  posture: { network: true },
};

/** Demonstrate ProjectExtensionRequirement shape. */
const exampleProjectReq: ProjectExtensionRequirement = {
  extensionId: 'com.example.dependency',
  versionRange: '>=1.0.0',

exec
/bin/zsh -lc "sed -n '1,80p' src/sdk/smoke/extensionSmoke.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
/**
 * Production-bundled smoke extension.
 *
 * Returns a statically-defined ReighExtension when the inert query parameter
 * `?extensionSmoke=1` is present.  The extension registers a tiny slot/status
 * contribution with a stable `data-testid`-equivalent identifier so E2E and
 * integration tests can verify the extension activation surface without
 * loading real user extensions.
 *
 * This module is intentionally free of dynamic imports, sandbox promises,
 * loaders, or permission enforcement — it is a pure, inert, statically-
 * bundled opt-in test hook.
 *
 * @publicContract
 */

import { defineExtension } from '@reigh/editor-sdk';
import type { ReighExtension } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** The query-parameter name that triggers the smoke extension. */
export const EXTENSION_SMOKE_QUERY_PARAM = 'extensionSmoke';

/** The value that activates the smoke extension. */
export const EXTENSION_SMOKE_ACTIVE_VALUE = '1';

/** Stable contribution ID used as a test anchor (data-testid equivalent). */
export const EXTENSION_SMOKE_CONTRIBUTION_ID = 'extension-smoke-status';

// ---------------------------------------------------------------------------
// Smoke extension (lazily created, frozen by defineExtension)
// ---------------------------------------------------------------------------

let _smokeExtension: ReighExtension | undefined;

function createSmokeExtension(): ReighExtension {
  return defineExtension({
    manifest: {
      id: 'com.reigh.smoke.extension-smoke' as any,
      version: '1.0.0',
      label: 'Production Smoke Extension',
      description:
        'Inert smoke extension activated via ?extensionSmoke=1. ' +
        'Provides a stable status-bar contribution for test hooks.',
      apiVersion: 1,
      contributions: [
        {
          id: EXTENSION_SMOKE_CONTRIBUTION_ID as any,
          kind: 'slot',
          slot: 'statusBar',
          order: 9999, // Sort last so it never collides visually
          label: 'Extension Smoke',
        },
      ],
    },
    activate() {
      // No-op: this extension is purely a static slot declaration for
      // integration smoke-test hooks.  It intentionally performs no
      // host mutations, service registrations, or chrome subscriptions.
      return { dispose() {} };
    },
  });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Parse a search-params source and return the smoke extension if the
 * `?extensionSmoke=1` trigger is present.
 *
 * Accepts a `URLSearchParams` instance, a raw query string (with or
 * without leading `?`), or `undefined`/`null` (returns null).
 *
 * @returns The frozen smoke extension, or `null` when the trigger is absent.
 */

exec
/bin/zsh -lc "sed -n '1,150p' scripts/quality/check-extension-deferred-claims.mjs" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
#!/usr/bin/env node
/**
 * M15 Deferred-Claims Absence Gate
 *
 * Loads the canonical supported/deferred matrix
 * (`docs/video-editor/extension-platform-supported-deferred.md`) and verifies
 * that every deferred / unsupported claim backed by an ABSENCE check is
 * **actually absent** from the active SDK and runtime code.
 *
 * Additionally, the script covers a fixed list of **risky deferred terms**
 * (marketplace, cloud loading, sandbox enforcement, remote package install,
 * theme activation, CRDT) and cross-validates deferred rows against the
 * contract-recheck blocker/deferral entries.
 *
 * ## Modes
 *
 *   --audit   (default)  Report presence violations and missing coverage as
 *                        warnings.  Only exit non-zero when the matrix itself
 *                        cannot be parsed.
 *
 *   --release            Presence violations become hard failures.  Every
 *                        risky term MUST be covered by at least one deferred
 *                        or unsupported row with an ABSENCE check.
 *
 * ## Cross-validation
 *
 * Every deferred row MUST either:
 *   - Have ABSENCE evidence that maps to a verifiable search, OR
 *   - Be linked to a blocker/deferral entry in the contract-recheck matrix.
 *
 * Rows that satisfy neither are reported as uncovered in both modes.
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';
import {
  loadContractMatrix,
  isDeferred,
  isUnsupported,
} from './lib/extension-contract-matrix.mjs';

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');

const SUPPORTED_DEFERRED_PATH = resolve(
  repoRoot,
  'docs/video-editor/extension-platform-supported-deferred.md',
);

const LABEL = '[deferred-claims]';

// ---------------------------------------------------------------------------
// Risky deferred terms — every one MUST be covered by a deferred/unsupported
// row with an ABSENCE check, or be documented as out-of-scope in §4.1.
// ---------------------------------------------------------------------------

/**
 * @typedef {object} RiskyTerm
 * @property {string} term        – human-readable label
 * @property {string} pattern     – regex to search for in code
 * @property {string} searchPath  – repo-relative directory to search
 * @property {string} description – what violation would mean
 */

/** @type {RiskyTerm[]} */
const RISKY_TERMS = [
  {
    term: 'marketplace',
    pattern: 'marketplace',
    searchPath: 'src/sdk',
    description:
      'Marketplace / third-party extension registry is unsupported in V1',
  },
  {
    term: 'cloud extension loading',
    pattern: 'cloud.*extension|extension.*cloud',
    searchPath: 'src/tools/video-editor/runtime',
    description: 'Cloud extension loading is out-of-scope for V1',
  },
  {
    term: 'sandbox enforcement',
    pattern: 'sandbox|iframe.*extension|Worker.*extension|ShadowRealm',
    searchPath: 'src/tools/video-editor/runtime',
    description:
      'Sandboxed execution (iframe/Worker/ShadowRealm) is deferred in V1',
  },
  {
    term: 'remote package install',
    pattern: 'npm\\s+install|dynamic\\s+import.*extension|CDN.*extension|remote.*package',
    searchPath: 'src/tools/video-editor/runtime',
    description:
      'Dynamic package loading (npm/CDN/import() for extensions) is deferred in V1',
  },
  {
    term: 'theme activation',
    pattern: 'theme.*contribution|ThemeContribution',
    searchPath: 'src/sdk',
    description: 'Theme contributions are unsupported in V1',
  },
  {
    term: 'CRDT primitives',
    pattern: '\\bCRDT\\b',
    searchPath: 'src/sdk',
    description:
      'Public CRDT collaboration primitives are out-of-scope for V1',
  },
];

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

const args = new Set(process.argv.slice(2));

/** @type {'audit' | 'release'} */
let mode = 'audit';
if (args.has('--release')) {
  mode = 'release';
} else if (args.has('--audit')) {
  mode = 'audit';
}

const isRelease = mode === 'release';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Run a ripgrep search and return matching lines (or empty array).
 * @param {string} pattern – regex pattern
 * @param {string} searchPath – absolute directory path
 * @returns {string[]}
 */
function grep(pattern, searchPath) {
  try {
    const result = execSync(
      `rg --line-number --no-heading --max-count 100 "${pattern}" "${searchPath}"`,
      {
        encoding: 'utf8',
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: 30_000,
      },
    );

exec
/bin/zsh -lc "sed -n '250,380p' src/tools/video-editor/runtime/extensionLoader.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
  /** Map from extension ID to the cycle it belongs to (empty array if not in cycle). */
  cycleGroups: ReadonlyMap<string, readonly string[]>;
} {
  // Build adjacency: extId → dependsOn IDs (all postures)
  const adjacency = new Map<string, Set<string>>();
  for (const pkg of packages) {
    const manifest = pkg.form === 'workspace-source'
      ? (pkg as WorkspaceSourcePackage).manifest
      : (pkg as InstalledBundlePackage).pack.manifest;
    const extId = manifest.id as string;
    const deps = manifest.dependsOn ?? [];
    const depIds = new Set<string>();
    for (const dep of deps) {
      if (dep.extensionId && dep.extensionId !== extId) {
        depIds.add(dep.extensionId);
      }
    }
    adjacency.set(extId, depIds);
  }

  // Tarjan's SCC algorithm
  const index = new Map<string, number>();
  const lowlink = new Map<string, number>();
  const onStack = new Set<string>();
  const stack: string[] = [];
  let currentIndex = 0;
  const sccs: string[][] = [];

  function strongConnect(v: string): void {
    index.set(v, currentIndex);
    lowlink.set(v, currentIndex);
    currentIndex++;
    stack.push(v);
    onStack.add(v);

    const neighbors = adjacency.get(v);
    if (neighbors) {
      for (const w of neighbors) {
        if (!index.has(w)) {
          strongConnect(w);
          lowlink.set(v, Math.min(lowlink.get(v)!, lowlink.get(w)!));
        } else if (onStack.has(w)) {
          lowlink.set(v, Math.min(lowlink.get(v)!, index.get(w)!));
        }
      }
    }

    if (lowlink.get(v) === index.get(v)) {
      const scc: string[] = [];
      let w: string;
      do {
        w = stack.pop()!;
        onStack.delete(w);
        scc.push(w);
      } while (w !== v);
      if (scc.length > 1) {
        sccs.push(scc);
      }
    }
  }

  for (const extId of adjacency.keys()) {
    if (!index.has(extId)) {
      strongConnect(extId);
    }
  }

  // Also detect direct self-loops (but these should be caught by manifest validation)
  const cycleIds = new Set<string>();
  const cycleGroups = new Map<string, readonly string[]>();
  for (const scc of sccs) {
    const frozen = Object.freeze([...scc]);
    for (const id of scc) {
      cycleIds.add(id);
      cycleGroups.set(id, frozen);
    }
  }

  return {
    cycleIds: Object.freeze(cycleIds),
    cycleGroups: Object.freeze(cycleGroups),
  };
}

// ---------------------------------------------------------------------------
// Dependency resolution
// ---------------------------------------------------------------------------

/**
 * Resolve dependencies across a set of validated packages.
 *
 * For each extension, checks:
 *   - Required dependencies: missing or version-mismatched → blocked.
 *   - Optional dependencies: missing or version-mismatched → degraded.
 *   - Cycles: all members of a cycle are blocked.
 *
 * Contribution-scoped diagnostics are emitted for dependency issues.
 */
export function resolveDependencies(
  packages: readonly ValidatedPackage[],
): DependencyResolutionResult {
  // Build lookup: extensionId → { manifest, version }
  const packageMap = new Map<string, { manifest: ExtensionManifest; version: string }>();
  for (const pkg of packages) {
    const manifest = pkg.form === 'workspace-source'
      ? (pkg as WorkspaceSourcePackage).manifest
      : (pkg as InstalledBundlePackage).pack.manifest;
    const extId = manifest.id as string;
    const version = manifest.version as string;
    packageMap.set(extId, { manifest, version });
  }

  // Detect cycles
  const { cycleIds, cycleGroups } = detectDependencyCycles(packages);

  const entries: DependencyResolutionEntry[] = [];
  const blockedIds = new Set<string>();
  const degradedIds = new Set<string>();
  const allDiagnostics: ExtensionDiagnostic[] = [];

  for (const pkg of packages) {
    const manifest = pkg.form === 'workspace-source'
      ? (pkg as WorkspaceSourcePackage).manifest
      : (pkg as InstalledBundlePackage).pack.manifest;
    const extId = manifest.id as string;

    const dependencies: DependencyStatus[] = [];
    const satisfied: string[] = [];
    const missingRequired: string[] = [];
    const missingOptional: string[] = [];
    const versionMismatchRequired: string[] = [];

exec
/bin/zsh -lc 'rg -n "permissions|ExtensionPermissionDeclaration|trust|sandbox|declarative|enforced" scripts/quality -S' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
scripts/quality/check-extension-deferred-claims.mjs:11: * (marketplace, cloud loading, sandbox enforcement, remote package install,
scripts/quality/check-extension-deferred-claims.mjs:87:    term: 'sandbox enforcement',
scripts/quality/check-extension-deferred-claims.mjs:88:    pattern: 'sandbox|iframe.*extension|Worker.*extension|ShadowRealm',

exec
/bin/zsh -lc "for f in src/tools/video-editor/examples/extensions/*/reigh-extension.json; do rg -n '\"permissions\"|\"permission\"|\"trusted|Trusted|sandbox|privileges|review' \""'$f"; done' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
6:    "description": "Fake long-running generation canary demonstrating the M10 agent tool SDK surface: progress reporting, cancellation, preview-only GenerationSession, placeholder sample channel, proposal-ready output, fake baked asset/material refs, and diagnostics.",
14:        "description": "Fake long-running generation tool that exercises progress reporting, cancellation, and preview-only sample channels through GenerationSession.",
6:    "description": "M13 canary for clip-local WebGL shader registration, uniforms, diagnostics, preview, picker, and planner behavior.",
14:        "description": "Preview-only clip-local WebGL shader canary with editable uniforms and clip-frame texture input.",
10:        "id": "flagship-mark-review-command",
18:        "id": "flagship-mark-review-keybinding",
25:        "id": "flagship-mark-review-menu",
98:      "warning.trustedLocal": "⚠️ Trusted-local extension: this extension executes with full browser-renderer privileges. Review the extension source before enabling it in a shared project.",
102:      "command.markReview.ready": "Flagship review marker command registered.",
103:      "command.markReview.done": "Flagship review marker stored."
6:    "description": "M11 canary for webcam permission, frame channels, live preview, bake, cleanup, and export-blocking live bindings.",
10:        "id": "live-webcam-canary-preview",
12:        "clipTypeId": "live-frame-preview",
13:        "label": "Live Webcam Preview",
14:        "description": "Preview clip metadata that reads the latest webcam frame channel sample through the built-in live-frame-preview renderer.",
6:    "description": "M13 canary for timeline postprocess WebGL shader registration, uniforms, diagnostics, preview, and planner behavior.",
14:        "description": "Preview-only timeline postprocess WebGL shader canary with editable uniforms.",

exec
/bin/zsh -lc 'rg -n "validateWorkspaceSourcePackage|validateInstalledBundlePackage|verifyIntegrity|defineExtension|activate|bundleContent|trusted|permission|sandbox" src/tools/video-editor/runtime/extensionLoader.ts -S' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
22:import { defineExtension } from '@reigh/editor-sdk';
38:  validateWorkspaceSourcePackage,
39:  validateInstalledBundlePackage,
42:  verifyIntegrity,
209:  /** Whether the extension can activate (all required satisfied, not in a cycle). */
528: * activate function already bound.
544:  readonly bundleContent: string;
633:   * packages that did not activate (disabled, invalid, incompatible,
658:  /** Per-extension load entries (includes non-activated packages). */
786:   * as-is.  For installed-bundle packages, bundleContent integrity is
788:   * created from the manifest snapshot (no activate function — installed
789:   * bundles use module evaluation for their activate export).
1086:        const pkgResult: PackageValidationResult = validateWorkspaceSourcePackage(raw);
1124:          bundleContent: input.bundleContent,
1127:        const pkgResult = validateInstalledBundlePackage(installedPkg);
1180:   * Build a load entry for a package that was not activated.
1206:   * Build a load entry for a package that activated successfully.
1366:        const syntheticExt = defineExtension({ manifest: wsPkg.manifest });
1405:          // This installed pack is disabled. Emit a non-activated entry.
1418:        const bundleContent = ibPkg.pack.bundleContent;
1420:        if (bundleContent === undefined || bundleContent === null) {
1429:            const integrityResult = await verifyIntegrity(
1430:              bundleContent,
1489:          const syntheticExt = defineExtension({ manifest: ibPkg.pack.manifest });
1605:              bundleContentRef: '',  // Not stored in lock per SD2

exec
/bin/zsh -lc "sed -n '760,820p' src/tools/video-editor/runtime/extensionLoader.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
 * existing ExtensionLifecycleHost pipeline.
 */
export interface ExtensionLoader {
  /** The repository used for lifecycle event persistence (null if none). */
  readonly repository: ExtensionStateRepository | null;

  /**
   * Validate a mix of direct (workspace source) and installed pack inputs.
   *
   * Each input is validated independently — a failure in one pack does
   * not prevent other packs from being validated.  Direct extensions use
   * dev-mode manifest validation (warnings for missing publisher/license).
   * Installed packs use strict installed-mode validation with integrity
   * checks.
   */
  validate(inputs: readonly ExtensionLoaderInput[]): ExtensionLoaderValidationResult;

  /**
   * Load validated packages into ReighExtension[].
   *
   * Performs dependency resolution before loading: required dependencies that
   * are missing, have version mismatches, or form cycles block activation.
   * Optional dependencies that are missing or have version mismatches allow
   * degraded activation with contribution-scoped diagnostics.
   *
   * For workspace-source packages, the original ReighExtension is returned
   * as-is.  For installed-bundle packages, bundleContent integrity is
   * verified against the pack record, and a synthetic ReighExtension is
   * created from the manifest snapshot (no activate function — installed
   * bundles use module evaluation for their activate export).
   *
   * Per-pack failure isolation: a failed integrity check, missing bundle
   * content, or dependency resolution failure only affects that single
   * extension.
   *
   * Lifecycle events (load, integrity_pass, integrity_fail, dependency_blocked,
   * dependency_degraded) are emitted through the repository when one is provided.
   */
  load(validated: readonly ValidatedPackage[]): Promise<ExtensionLoaderLoadResult>;

  /**
   * Unload extensions, emitting lifecycle events through the repository.
   *
   * Each extension ID receives an `unload` lifecycle event.  Failures
   * are isolated per ID.
   */
  unload(extensionIds: readonly string[]): Promise<ExtensionLoaderUnloadResult>;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create a new ExtensionLoader instance.
 *
 * @param repository  Optional repository for persisting lifecycle events.
 *                    When null, lifecycle events are still produced in the
 *                    result objects but are not persisted.
 */
export function createExtensionLoader(

exec
/bin/zsh -lc "sed -n '1340,1505p' src/tools/video-editor/runtime/extensionLoader.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
          reasonParts.push(`Missing required dependencies: ${(resEntry?.missingRequired ?? []).join(', ')}`);
        }
        if ((resEntry?.versionMismatchRequired?.length ?? 0) > 0) {
          reasonParts.push(`Version mismatch for required dependencies: ${(resEntry?.versionMismatchRequired ?? []).join(', ')}`);
        }
        const reason = reasonParts.length > 0
          ? reasonParts.join('. ')
          : `Extension "${extId}" is incompatible with the current load set.`;

        entries.push(makeFailedEntry(
          extId,
          Object.freeze([...errors]),
          'incompatible',
          reason,
          metadata,
          Object.freeze([]),
        ));
        continue;
      }

      if (pkg.form === 'workspace-source') {
        // ---------- workspace source ----------
        const wsPkg = pkg as WorkspaceSourcePackage;
        const lifecycleEvents: ExtensionLifecycleEvent[] = [];

        // Synthesize a basic ReighExtension from the manifest.
        const syntheticExt = defineExtension({ manifest: wsPkg.manifest });

        const loadEvent = createLifecycleEvent(
          extId,
          'load',
          `Extension "${extId}" loaded (workspace source).`,
          { form: 'workspace-source', degraded: degradedIds.has(extId) },
        );
        lifecycleEvents.push(loadEvent);
        await appendLifecycleEvent(loadEvent);

        loadedExtensions.push(syntheticExt);

        const degradedReason = degradedIds.has(extId)
          ? `Loaded (degraded) — optional dependencies missing or mismatched.`
          : 'Loaded successfully.';

        entries.push(makeActivatedEntry(
          extId,
          syntheticExt,
          'loaded',
          degradedReason,
          metadata,
          Object.freeze([...lifecycleEvents]),
        ));
      } else {
        // ---------- installed bundle ----------
        const ibPkg = pkg as InstalledBundlePackage;
        const lifecycleEvents: ExtensionLifecycleEvent[] = [];
        const errors: ExtensionDiagnostic[] = [];

        // Check enablement state for non-conflict disabled packages.
        // If the installed pack is explicitly disabled and there's no
        // local source to conflict with, we must still surface the
        // disabled state.
        const enablementState = conflictConfig.enablementStates[extId];
        const isDisabled = enablementState && !enablementState.enabled;

        if (isDisabled) {
          // This installed pack is disabled. Emit a non-activated entry.
          const reason = enablementState.toggleReason
            || 'User disabled this package.';
          entries.push(makeNonActivatedEntry(
            extId,
            'disabled-by-user',
            reason,
            metadata,
          ));
          continue;
        }

        // Integrity verification
        const bundleContent = ibPkg.pack.bundleContent;

        if (bundleContent === undefined || bundleContent === null) {
          const err = blockDiag(
            extId,
            'loader/missing-bundle-content',
            `Installed extension "${extId}" has no bundle content.`,
          );
          errors.push(err);
        } else {
          try {
            const integrityResult = await verifyIntegrity(
              bundleContent,
              ibPkg.pack.metadata.integrity,
              extId,
            );

            if (integrityResult.valid) {
              const integrityEvent = createLifecycleEvent(
                extId,
                'integrity_pass',
                `Integrity verified for extension "${extId}".`,
                {
                  algorithm: ibPkg.pack.metadata.integrity.algorithm,
                },
              );
              lifecycleEvents.push(integrityEvent);
              await appendLifecycleEvent(integrityEvent);
            } else {
              // Integrity check failed — collect diagnostics
              for (const diag of integrityResult.diagnostics) {
                errors.push(
                  blockDiag(extId, diag.code, diag.message),
                );
              }
              const integrityEvent = createLifecycleEvent(
                extId,
                'integrity_fail',
                `Integrity check failed for extension "${extId}".`,
                {
                  diagnostics: integrityResult.diagnostics.map((d) => ({
                    code: d.code,
                    message: d.message,
                  })),
                },
              );
              lifecycleEvents.push(integrityEvent);
              await appendLifecycleEvent(integrityEvent);
            }
          } catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            errors.push(
              blockDiag(
                extId,
                'loader/integrity-error',
                `Integrity verification error for extension "${extId}": ${message}`,
              ),
            );
            const integrityEvent = createLifecycleEvent(
              extId,
              'integrity_fail',
              `Integrity verification threw an error for extension "${extId}": ${message}`,
              { error: message },
            );
            lifecycleEvents.push(integrityEvent);
            await appendLifecycleEvent(integrityEvent);
          }
        }

        if (errors.length === 0) {
          // Create synthetic ReighExtension from manifest snapshot.
          const syntheticExt = defineExtension({ manifest: ibPkg.pack.manifest });

          const loadEvent = createLifecycleEvent(
            extId,
            'load',
            `Extension "${extId}" loaded (installed bundle, integrity verified).`,
            {
              form: 'installed-bundle',
              version: ibPkg.pack.metadata.version,
              degraded: degradedIds.has(extId),
            },
          );
          lifecycleEvents.push(loadEvent);
          await appendLifecycleEvent(loadEvent);

          loadedExtensions.push(syntheticExt);


exec
/bin/zsh -lc "sed -n '1040,1150p' src/tools/video-editor/runtime/extensionLoader.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
      winningPackages: Object.freeze([...winningPackages]),
    } satisfies ConflictResolutionResult);
  }

  /**
   * Fetch dev overrides and enablement states from the repository.
   *
   * When the repository is unavailable or fetch fails, returns empty
   * records so conflict resolution degrades gracefully (installed-wins
   * with no override data available).
   */
  async function fetchConflictConfig(): Promise<ConflictResolutionConfig> {
    if (!repo || repo.isDisposed) {
      return { devOverrides: {}, enablementStates: {} };
    }
    try {
      const fullState = await repo.getFullExtensionState();
      return {
        devOverrides: fullState.devOverrides,
        enablementStates: fullState.enablement,
      };
    } catch {
      // Repository errors must not block loading — degrade gracefully
      return { devOverrides: {}, enablementStates: {} };
    }
  }

  // ---- validate ----------------------------------------------------------

  function validate(
    inputs: readonly ExtensionLoaderInput[],
  ): ExtensionLoaderValidationResult {
    ensureNotDisposed();
    const entries: ExtensionValidationEntry[] = [];
    let allValid = true;

    for (const input of inputs) {
      if (input.kind === 'direct') {
        // ---------- direct / workspace source ----------
        const ext = input.extension;
        const extId = (ext.manifest.id as string) || '(unknown)';

        // Build a workspace-source-shaped record for validation
        const raw: Record<string, unknown> = {
          manifest: ext.manifest as unknown as Record<string, unknown>,
        };
        const pkgResult: PackageValidationResult = validateWorkspaceSourcePackage(raw);

        const valid = pkgResult.valid;
        if (!valid) allValid = false;

        const validatedPackage: ValidatedPackage | null = valid
          ? deepFreeze({
              form: 'workspace-source' as const,
              manifest: ext.manifest,
            } as WorkspaceSourcePackage)
          : null;

        entries.push(deepFreeze({
          input,
          valid,
          errors: Object.freeze([...pkgResult.errors]),
          warnings: Object.freeze([...pkgResult.warnings]),
          validatedPackage,
        } satisfies ExtensionValidationEntry));
      } else {
        // ---------- installed bundle ----------
        const packRecord = input.packRecord;
        const extId = packRecord.extensionId;

        // Build an InstalledExtensionPackage for validation
        const installedPkg: InstalledExtensionPackage = {
          metadata: {
            extensionId: packRecord.extensionId as any,
            version: packRecord.version,
            apiVersion: packRecord.apiVersion,
            integrity: packRecord.integrity,
            installedAt: packRecord.installedAt,
            enabled: true,
            publisher: packRecord.publisher,
            license: packRecord.license,
            icon: packRecord.icon,
          },
          manifest: packRecord.manifestSnapshot,
          bundleContent: input.bundleContent,
        };

        const pkgResult = validateInstalledBundlePackage(installedPkg);
        const valid = pkgResult.valid;
        if (!valid) allValid = false;

        const validatedPackage: ValidatedPackage | null = valid
          ? deepFreeze({
              form: 'installed-bundle' as const,
              pack: installedPkg,
            } as InstalledBundlePackage)
          : null;

        entries.push(deepFreeze({
          input,
          valid,
          errors: Object.freeze([...pkgResult.errors]),
          warnings: Object.freeze([...pkgResult.warnings]),
          validatedPackage,
        } satisfies ExtensionValidationEntry));
      }
    }

    // Aggregate diagnostics
    const allDiagnostics: ExtensionDiagnostic[] = [];
    for (const entry of entries) {

exec
/bin/zsh -lc "sed -n '515,555p' src/tools/video-editor/runtime/extensionLoader.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
    degradedExtensionIds: Object.freeze(degradedIds),
    diagnostics: Object.freeze(allDiagnostics),
  };
}

// ---------------------------------------------------------------------------
// Input types
// ---------------------------------------------------------------------------

/**
 * A direct/source extension input (workspace source).
 *
 * These come from the `extensions` prop on the provider and have an
 * activate function already bound.
 */
export interface DirectExtensionInput {
  readonly kind: 'direct';
  readonly extension: ReighExtension;
}

/**
 * An installed pack input.
 *
 * These come from the repository (ExtensionStateRepository) and carry
 * the pack record plus the bundle content bytes retrieved from IndexedDB.
 */
export interface InstalledExtensionInput {
  readonly kind: 'installed';
  readonly packRecord: ExtensionPackRecord;
  readonly bundleContent: string;
}

/** Union of all extension loader inputs. */
export type ExtensionLoaderInput = DirectExtensionInput | InstalledExtensionInput;

// ---------------------------------------------------------------------------
// Validation types
// ---------------------------------------------------------------------------

/** Validation result for a single input. */
export interface ExtensionValidationEntry {

exec
/bin/zsh -lc 'rg -n "permissions|capabilit|process|trusted|sandbox|route|blocker|reserved|deferred" src/tools/video-editor/runtime/extensionSurface.ts -S' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
32:  RenderRoute,
34:  RenderBlockerReason,
38:  IntegrationCapabilities,
39:  CapabilityRequirement,
40:  CapabilitySourceRef,
41:  ProcessContribution,
42:  ProcessSpec,
43:  ProcessOperationSpec,
146:  /** M12: Normalized process descriptors, declaration-only until host runtime activation. */
147:  processes: readonly VideoEditorProcessDescriptor[];
203:  /** Planner-visible routes declared by render-dependent output formats. */
204:  availableRoutes: readonly RenderRoute[];
205:  /** Render route/process requirements for planner-owned execution. */
206:  routeRequirements: readonly VideoEditorRouteRequirementDescriptor[];
207:  /** Process requirements referenced by this output format. */
208:  processRequirements: readonly VideoEditorProcessRequirementDescriptor[];
209:  /** Declaration-time blockers that the planner should surface before execution. */
210:  blockers: readonly VideoEditorPlannerBlockerDescriptor[];
213:  /** Aggregated capability metadata derived from the output declaration. */
214:  capabilities?: IntegrationCapabilities;
221:/** A normalized route requirement record consumed by render planning. */
222:export interface VideoEditorRouteRequirementDescriptor {
223:  routes: readonly RenderRoute[];
224:  requiredCapabilities: readonly string[];
225:  processId?: string;
231:/** A normalized process dependency declared by an output or route. */
232:export interface VideoEditorProcessRequirementDescriptor {
233:  processId: string;
235:  requiredCapabilities: readonly string[];
238:/** Declaration-time blocker metadata surfaced to the planner and UI. */
239:export interface VideoEditorPlannerBlockerDescriptor {
243:  route?: RenderRoute;
244:  reason: RenderBlockerReason;
249:/** Planner next-action metadata for resolving route/process/material blockers. */
251:  kind: 'select-route' | 'start-process' | 'resolve-blocker';
253:  route?: RenderRoute;
254:  processId?: string;
259:/** A normalized trusted-local process descriptor produced by runtime normalization. */
260:export interface VideoEditorProcessDescriptor {
264:  processId: string;
267:  spec: ProcessSpec;
268:  protocol: ProcessSpec['protocol'];
269:  operations: readonly ProcessOperationSpec[];
270:  availableRoutes: readonly RenderRoute[];
271:  capabilities?: IntegrationCapabilities;
272:  requiredBy: readonly CapabilitySourceRef[];
273:  blockers: readonly VideoEditorPlannerBlockerDescriptor[];
311:// M7: Trusted component effect descriptors
332:// M8: Trusted component transition descriptors
403:export interface InactiveReservedContribution {
423:  readonly inactiveReserved: readonly InactiveReservedContribution[];
432:  /** M12: Process descriptors, declaration-only until host runtime activation. */
433:  readonly processes: readonly VideoEditorProcessDescriptor[];
490:const EMPTY_PROCESSES: readonly VideoEditorProcessDescriptor[] = Object.freeze([]);
519:  processes: EMPTY_PROCESSES,
534: *   the extension list is empty or all contributions are inactive/reserved.
538: *   from reserved future kinds (effect, transition, clipType, parser, agentTool,
539: *   agent) and collects the latter as inactive reserved metadata.
541: *   contribution ID alphabetically. (Built-in priority is reserved for a
588:  const inactiveReserved: InactiveReservedContribution[] = [];
592:  // M6: Collect contributions that are reserved for execution but still
593:  // need to be surfaced as disabled/reserved descriptors in the runtime config.
594:  const m6ReservedOutputFormats: CollectedContribution[] = [];
595:  const m6ReservedSearchProviders: CollectedContribution[] = [];
596:  const m12ReservedProcesses: CollectedContribution[] = [];
644:          inactiveReserved.push({
679:          inactiveReserved.push({
701:      // M6: OutputFormat and SearchProvider are reserved for execution but
707:        // Add to inactive reserved for diagnostics
708:        inactiveReserved.push({
719:            `is reserved for ${notYetBridged}.`,
728:        // Collect into the appropriate M6 reserved list for later projection
730:          m6ReservedOutputFormats.push({ contribution: contrib, extensionId: extId });
732:          m6ReservedSearchProviders.push({ contribution: contrib, extensionId: extId });
736:      if (notYetBridged !== null && contrib.kind === 'process') {
737:        inactiveReserved.push({
748:            `is reserved for ${notYetBridged}.`,
756:        m12ReservedProcesses.push({ contribution: contrib, extensionId: extId });
760:        inactiveReserved.push({
771:            `is reserved for ${notYetBridged}.`,
999:  // ---- Phase 4b: project M6 reserved contributions --------------------------
1002:  for (const { contribution, extensionId } of m6ReservedOutputFormats) {
1006:    const routeRequirements = buildRouteRequirements(renderDescriptor);
1007:    const processRequirements = buildProcessRequirements(renderDescriptor);
1008:    const blockers = buildOutputFormatBlockers(extensionId, contribution.id as string, of, renderDescriptor);
1009:    const nextActions = buildOutputFormatNextActions(of, renderDescriptor, blockers);
1010:    const capabilities = buildOutputFormatCapabilities(extensionId, contribution.id as string, of, renderDescriptor, blockers);
1022:      availableRoutes: Object.freeze([...(renderDescriptor?.routes ?? [])]),
1023:      routeRequirements,
1024:      processRequirements,
1025:      blockers,
1027:      capabilities,
1044:  // Process: surfaced as planner-visible declarations without runtime spawn.
1045:  const processDescriptors: VideoEditorProcessDescriptor[] = [];
1046:  for (const { contribution, extensionId } of m12ReservedProcesses) {
1047:    const processContrib = contribution as unknown as ProcessContribution;
1048:    const spec = processContrib.spec;
1050:    const availableRoutes = Object.freeze(
1051:      Array.from(new Set(operations.flatMap((operation) => operation.routes ?? []))),
1053:    processDescriptors.push({
1057:      processId: spec.id,
1058:      label: processContrib.label ?? spec.label ?? spec.id,
1063:      availableRoutes,
1064:      capabilities: spec.capabilities,
1066:      blockers: Object.freeze([]),
1069:          kind: 'start-process',
1070:          label: `Start ${processContrib.label ?? spec.label ?? spec.id}`,
1071:          processId: spec.id,
1072:          message: 'Process execution is host-owned and must be activated before route planning can dispatch operations.',
1078:  processDescriptors.sort((a, b) => {
1090:  for (const { contribution, extensionId } of m6ReservedSearchProviders) {
1114:  /** Whether any contributions — bridged or M6-reserved — affect the config. */
1123:    processDescriptors.length > 0 ||
1145:        processes: Object.freeze(processDescriptors),
1160:    inactiveReserved: Object.freeze(inactiveReserved),
1169:    processes: Object.freeze(processDescriptors),
1186:function buildRouteRequirements(
1188:): readonly VideoEditorRouteRequirementDescriptor[] {
1193:      routes: Object.freeze([...renderDescriptor.routes]),
1194:      requiredCapabilities: Object.freeze([...(renderDescriptor.requiredCapabilities ?? [])]),
1195:      processId: renderDescriptor.processId,
1203:function buildProcessRequirements(
1205:): readonly VideoEditorProcessRequirementDescriptor[] {
1206:  if (!renderDescriptor?.processId) return Object.freeze([]);
1210:      processId: renderDescriptor.processId,
1212:      requiredCapabilities: Object.freeze([...(renderDescriptor.requiredCapabilities ?? [])]),
1217:function buildOutputFormatBlockers(
1222:): readonly VideoEditorPlannerBlockerDescriptor[] {
1226:    kind: 'resolve-blocker',
1227:    label: 'Add render route requirements',
1228:    message: 'Render-dependent output formats must declare render routes before planning can execute them.',
1236:      reason: 'route-unsupported',
1237:      message: `Output format "${contribution.label ?? contributionId}" requires render planning but did not declare route requirements.`,
1246:  blockers: readonly VideoEditorPlannerBlockerDescriptor[],
1249:  if (blockers[0]?.nextAction) return Object.freeze([blockers[0].nextAction]);
1252:  if (renderDescriptor?.processId) {
1254:      kind: 'start-process',
1255:      label: `Start process ${renderDescriptor.processId}`,
1256:      processId: renderDescriptor.processId,
1262:  for (const route of renderDescriptor?.routes ?? []) {
1264:      kind: 'select-route',
1265:      label: `Plan ${route}`,
1266:      route,
1267:      processId: renderDescriptor?.processId,
1276:function buildOutputFormatCapabilities(
1281:  blockers: readonly VideoEditorPlannerBlockerDescriptor[],
1282:): IntegrationCapabilities | undefined {
1283:  const sourceRef: CapabilitySourceRef = Object.freeze({
1293:      routes: Object.freeze([]),
1295:      capabilityRequirements: Object.freeze([]),
1302:  const routes = Object.freeze([...(renderDescriptor?.routes ?? [])]);
1304:  const requiredCapabilities = Object.freeze([...(renderDescriptor?.requiredCapabilities ?? [])]);
1305:  const routeFit = renderDescriptor
1308:        route: 'sidecar-export' as const,
1310:        reason: 'route-unsupported' as const,
1311:        message: blockers[0]?.message,
1314:  const capabilityRequirements: CapabilityRequirement[] = routes.map((route) => Object.freeze({
1315:    id: `${extensionId}.${contributionId}.${route}`,
1317:    route,
1318:    requiredCapabilities,
1320:    routeFit: Object.freeze({
1321:      route,
1329:    capabilityRequirements.push(Object.freeze({
1332:      route: 'sidecar-export',
1333:      requiredCapabilities: Object.freeze([]),
1335:      routeFit,
1336:      findings: Object.freeze(blockers.map((blocker) => Object.freeze({
1337:        id: blocker.id,
1339:        route: blocker.route,
1340:        reason: blocker.reason,
1341:        message: blocker.message,
1342:        extensionId: blocker.extensionId,
1343:        contributionId: blocker.contributionId,
1352:    routes,
1354:    capabilityRequirements: Object.freeze(capabilityRequirements),
1356:    fullySupported: blockers.length === 0,
1357:    anyBlocked: blockers.length > 0,
1366:  inactiveReserved: Object.freeze([]),
1371:  processes: EMPTY_PROCESSES,
1453:  readonly shaderScope?: 'clip' | 'postprocess';

codex
# Permission Model Truth

## Verdict

The criticism is valid, but the immediate threat is mostly **trust/UI honesty**, not a hidden partial sandbox. Current code already says extensions are trusted and unsandboxed in several places, including the Extension Manager. The remaining problem is that `permissions` still exists as a manifest/API concept and can be mistaken for enforceable browser-style permissions.

Severity: **medium now**, **high if third-party/marketplace loading is promoted without resolving this**.

## Current Code Reality

`src/sdk/index.ts` defines `ExtensionPermissionDeclaration` as “descriptive until sandboxing exists.” Its shape is:

- `reason: string`
- `posture?: { network?: boolean; filesystem?: boolean; env?: boolean; processes?: boolean }`

`ExtensionManifest.permissions` only gets deep-frozen by `defineExtension()`. I found no runtime path that gates activation, context services, network, process, filesystem, env, DOM, localStorage, or contribution registration based on `manifest.permissions`.

`config/contracts/reigh-extension.schema.json` allows `permissions`, but its shape is drifted from the SDK: schema accepts `{ permission?: string, reason?: string }`, not SDK `posture`. That is a concrete contract bug.

`src/tools/video-editor/runtime/extensionLoader.ts` enforces manifest/package concerns: ID/version/label, dependencies, installed publisher/license, enablement state, and installed bundle integrity. It does not enforce permissions.

`src/tools/video-editor/runtime/extensionSurface.ts` normalizes contributions and planner-visible capabilities/process descriptors. Those are render/planning capabilities, not security capabilities.

`ExtensionContext` is capability-shaped in the API sense: extensions only receive host services like settings, diagnostics, commands, effects, transitions, clip types, shaders, and agent tools. Some services enforce narrow invariants, such as diagnostic source pinning and extension-scoped settings/cleanup. But the extension code itself runs same-thread/same-origin, so those are not a sandbox.

`ExtensionManager` is honest: `ExtensionTrustWarningBanner` says extensions run as trusted, unsandboxed code and manifest permissions are not runtime-enforced. Tests assert this warning appears in loading, empty, populated, and expanded states.

Docs are mostly honest too. `docs/video-editor/extension-platform-supported-deferred.md` explicitly marks runtime permission enforcement and sandboxed execution as deferred, and states “Permission enforcement: Descriptive only.”

Checked-in example manifests do not appear to declare manifest `permissions`. `flagship-local` includes a trusted-local warning message. `live-webcam-canary` mentions browser webcam permission, but that is browser media permission state, not manifest permission enforcement.

## Pristine End State

Pick one model and make it impossible to misunderstand.

Best near-term model: **trusted-local code with access disclosures**.

- Rename/deprecate manifest `permissions` as security language.
- Replace with `accessDisclosures` or `declaredAccess`, explicitly non-enforcing.
- Keep runtime enforcement claims out of schema/docs/UI unless backed by code.
- Keep installed bundles as reviewed/integrity-tracked/trusted packages, not “safe” packages.
- Treat render/process/capability metadata as planner/runtime routing metadata, not security permission metadata.
- Require Extension Manager to show the trusted-local banner plus any access disclosures in plain language.

Longer-term model, if Reigh wants real third-party safety: isolated execution plus a host broker. That means iframe/Worker/SES-like isolation, message-passed SDK, CSP/import restrictions, brokered network/process/storage APIs, revocation, and tests proving denied capabilities fail. Same-thread JavaScript cannot reliably enforce network/DOM/global access.

## Recommended Work

Now:

1. **Fix the contract drift**: align schema with SDK, or better, replace `permissions` with explicitly descriptive `accessDisclosures`.
2. **Deprecate `permissions` wording** in public docs/schema comments. If retained for compatibility, mark it legacy/declarative/non-enforcing everywhere.
3. **Add a quality gate** that fails if docs or UI imply permission enforcement, sandboxing, marketplace safety, or safe third-party execution outside the deferred matrix.
4. **Add schema/SDK tests** proving the manifest access-disclosure shape matches across `src/sdk/index.ts` and `config/contracts/reigh-extension.schema.json`.
5. **Surface disclosures in Extension Manager** under the trust warning, labeled as “Declared by extension, not enforced.”

Later:

1. Design a real permission broker only for host-mediated APIs first, especially processes/sidecars and agent tools.
2. Do not attempt network/filesystem/env enforcement until extension execution is isolated.
3. If marketplace loading becomes a goal, make sandbox/signing/review a hard prerequisite.

## Tests / Gates

- SDK/schema parity test for manifest access fields.
- Negative docs gate: banned phrases like “requires permission,” “permission granted,” “sandboxed,” “safe third-party,” unless paired with explicit deferred/non-enforced language.
- Extension Manager tests for trust warning plus disclosure rendering.
- Loader/runtime test proving access declarations do not affect activation until a real broker exists.
- Later broker tests: denied process/network/storage capability cannot be invoked.

## Biggest Trap

The tempting wrong move is to add more declarative permission names and maybe block a few host APIs, then call it enforcement. In same-thread trusted browser code, that would deepen the false-safety problem. Either build isolation and a broker, or be brutally clear that this is trusted local code with non-enforced disclosures.
tokens used
101,818
# Permission Model Truth

## Verdict

The criticism is valid, but the immediate threat is mostly **trust/UI honesty**, not a hidden partial sandbox. Current code already says extensions are trusted and unsandboxed in several places, including the Extension Manager. The remaining problem is that `permissions` still exists as a manifest/API concept and can be mistaken for enforceable browser-style permissions.

Severity: **medium now**, **high if third-party/marketplace loading is promoted without resolving this**.

## Current Code Reality

`src/sdk/index.ts` defines `ExtensionPermissionDeclaration` as “descriptive until sandboxing exists.” Its shape is:

- `reason: string`
- `posture?: { network?: boolean; filesystem?: boolean; env?: boolean; processes?: boolean }`

`ExtensionManifest.permissions` only gets deep-frozen by `defineExtension()`. I found no runtime path that gates activation, context services, network, process, filesystem, env, DOM, localStorage, or contribution registration based on `manifest.permissions`.

`config/contracts/reigh-extension.schema.json` allows `permissions`, but its shape is drifted from the SDK: schema accepts `{ permission?: string, reason?: string }`, not SDK `posture`. That is a concrete contract bug.

`src/tools/video-editor/runtime/extensionLoader.ts` enforces manifest/package concerns: ID/version/label, dependencies, installed publisher/license, enablement state, and installed bundle integrity. It does not enforce permissions.

`src/tools/video-editor/runtime/extensionSurface.ts` normalizes contributions and planner-visible capabilities/process descriptors. Those are render/planning capabilities, not security capabilities.

`ExtensionContext` is capability-shaped in the API sense: extensions only receive host services like settings, diagnostics, commands, effects, transitions, clip types, shaders, and agent tools. Some services enforce narrow invariants, such as diagnostic source pinning and extension-scoped settings/cleanup. But the extension code itself runs same-thread/same-origin, so those are not a sandbox.

`ExtensionManager` is honest: `ExtensionTrustWarningBanner` says extensions run as trusted, unsandboxed code and manifest permissions are not runtime-enforced. Tests assert this warning appears in loading, empty, populated, and expanded states.

Docs are mostly honest too. `docs/video-editor/extension-platform-supported-deferred.md` explicitly marks runtime permission enforcement and sandboxed execution as deferred, and states “Permission enforcement: Descriptive only.”

Checked-in example manifests do not appear to declare manifest `permissions`. `flagship-local` includes a trusted-local warning message. `live-webcam-canary` mentions browser webcam permission, but that is browser media permission state, not manifest permission enforcement.

## Pristine End State

Pick one model and make it impossible to misunderstand.

Best near-term model: **trusted-local code with access disclosures**.

- Rename/deprecate manifest `permissions` as security language.
- Replace with `accessDisclosures` or `declaredAccess`, explicitly non-enforcing.
- Keep runtime enforcement claims out of schema/docs/UI unless backed by code.
- Keep installed bundles as reviewed/integrity-tracked/trusted packages, not “safe” packages.
- Treat render/process/capability metadata as planner/runtime routing metadata, not security permission metadata.
- Require Extension Manager to show the trusted-local banner plus any access disclosures in plain language.

Longer-term model, if Reigh wants real third-party safety: isolated execution plus a host broker. That means iframe/Worker/SES-like isolation, message-passed SDK, CSP/import restrictions, brokered network/process/storage APIs, revocation, and tests proving denied capabilities fail. Same-thread JavaScript cannot reliably enforce network/DOM/global access.

## Recommended Work

Now:

1. **Fix the contract drift**: align schema with SDK, or better, replace `permissions` with explicitly descriptive `accessDisclosures`.
2. **Deprecate `permissions` wording** in public docs/schema comments. If retained for compatibility, mark it legacy/declarative/non-enforcing everywhere.
3. **Add a quality gate** that fails if docs or UI imply permission enforcement, sandboxing, marketplace safety, or safe third-party execution outside the deferred matrix.
4. **Add schema/SDK tests** proving the manifest access-disclosure shape matches across `src/sdk/index.ts` and `config/contracts/reigh-extension.schema.json`.
5. **Surface disclosures in Extension Manager** under the trust warning, labeled as “Declared by extension, not enforced.”

Later:

1. Design a real permission broker only for host-mediated APIs first, especially processes/sidecars and agent tools.
2. Do not attempt network/filesystem/env enforcement until extension execution is isolated.
3. If marketplace loading becomes a goal, make sandbox/signing/review a hard prerequisite.

## Tests / Gates

- SDK/schema parity test for manifest access fields.
- Negative docs gate: banned phrases like “requires permission,” “permission granted,” “sandboxed,” “safe third-party,” unless paired with explicit deferred/non-enforced language.
- Extension Manager tests for trust warning plus disclosure rendering.
- Loader/runtime test proving access declarations do not affect activation until a real broker exists.
- Later broker tests: denied process/network/storage capability cannot be invoked.

## Biggest Trap

The tempting wrong move is to add more declarative permission names and maybe block a few host APIs, then call it enforcement. In same-thread trusted browser code, that would deepen the false-safety problem. Either build isolation and a broker, or be brutally clear that this is trusted local code with non-enforced disclosures.
