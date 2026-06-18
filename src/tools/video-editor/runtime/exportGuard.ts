/**
 * Export diagnostics model: pre-render scan that collects built-in known IDs
 * from clip registries, effect type arrays, the dynamic effect registry, and
 * transition types, then compares the resolved timeline config against those
 * known IDs to produce structured {@link ExportDiagnostic} entries.
 *
 * Extension-declared known IDs (from inactive reserved contributions) are
 * collected as metadata only — no extension render dispatch is added.
 *
 * @module exportGuard
 */

import type {
  ExportDiagnostic,
  ContributionKind,
  ExtensionContribution,
} from '@reigh/editor-sdk';
import { contributionKindNotYetBridged } from '@reigh/editor-sdk';
import { BUILTIN_CLIP_TYPES } from '@/tools/video-editor/types/index.ts';
import type { ResolvedTimelineClip, ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';
import { TRUSTED_CLIP_TYPES } from '@/tools/video-editor/clip-types/registry.ts';
import {
  entranceEffectTypes,
  exitEffectTypes,
  continuousEffectTypes,
  getEffectRegistry,
} from '@/tools/video-editor/effects/index.tsx';
import { transitionTypes as builtInTransitionTypes } from '@/tools/video-editor/effects/transitions.ts';

// ---------------------------------------------------------------------------
// Known ID collections
// ---------------------------------------------------------------------------

/**
 * Immutable snapshot of all built-in (host-owned) known IDs used during
 * export validation.
 */
export interface KnownIdCollection {
  /** All known clip type IDs (built-in + trusted sequence). */
  readonly clipTypes: ReadonlySet<string>;
  /** All known effect IDs (entrance + exit + continuous built-ins). */
  readonly effectTypes: ReadonlySet<string>;
  /** All known transition type IDs. */
  readonly transitionTypes: ReadonlySet<string>;
}

/**
 * Extension-declared known IDs collected from inactive reserved contributions.
 * These are treated as metadata only — no render dispatch is triggered.
 */
export interface InactiveKnownIds {
  /** Effect IDs declared by inactive extension contributions. */
  readonly effectIds: ReadonlySet<string>;
  /** Transition IDs declared by inactive extension contributions. */
  readonly transitionIds: ReadonlySet<string>;
  /** Clip-type IDs declared by inactive extension contributions. */
  readonly clipTypeIds: ReadonlySet<string>;
}

// ---------------------------------------------------------------------------
// Export guard result
// ---------------------------------------------------------------------------

/**
 * The result of an export guard scan over a resolved timeline config.
 */
export interface ExportGuardResult {
  /** Structured diagnostics for every unknown/unavailable ID found. */
  readonly diagnostics: readonly ExportDiagnostic[];
  /** Clip types used in the timeline that are not in any known set. */
  readonly unknownClipTypes: readonly string[];
  /** Effect types used in the timeline that are not in any known set. */
  readonly unknownEffects: readonly string[];
  /** Transition types used in the timeline that are not in any known set. */
  readonly unknownTransitions: readonly string[];
  /** Extension-declared known IDs collected as inactive metadata. */
  readonly inactiveExtensionIds: InactiveKnownIds;
  /** Whether any blocking error diagnostics were emitted. */
  readonly hasBlockingErrors: boolean;
}

// ---------------------------------------------------------------------------
// Built-in ID collection
// ---------------------------------------------------------------------------

/**
 * Collect every built-in known ID from the host-owned registries:
 * - `BUILTIN_CLIP_TYPES` (media, hold, text, effect-layer)
 * - `TRUSTED_CLIP_TYPES` (image-jump, title-card, section-hook, etc.)
 * - `entranceEffectTypes` / `exitEffectTypes` / `continuousEffectTypes`
 * - The current dynamic effect registry's `listAll()` set
 * - `transitionTypes` from `effects/transitions.ts`
 */
export function collectBuiltInKnownIds(): KnownIdCollection {
  // ---- clip types -----------------------------------------------------------
  const clipTypes = new Set<string>([
    ...BUILTIN_CLIP_TYPES,
    ...TRUSTED_CLIP_TYPES,
  ]);

  // ---- effect types ---------------------------------------------------------
  const effectTypes = new Set<string>([
    ...entranceEffectTypes,
    ...exitEffectTypes,
    ...continuousEffectTypes,
  ]);

  // Dynamic effect registry — merge any dynamically registered effects
  try {
    const registry = getEffectRegistry();
    for (const id of registry.listAll()) {
      effectTypes.add(id);
    }
  } catch {
    // Effect registry not yet initialised — built-in set is sufficient
  }

  // ---- transition types -----------------------------------------------------
  const transitionTypes = new Set(builtInTransitionTypes);

  return Object.freeze({
    clipTypes: Object.freeze(clipTypes),
    effectTypes: Object.freeze(effectTypes),
    transitionTypes: Object.freeze(transitionTypes),
  });
}

// ---------------------------------------------------------------------------
// Extension-declared known IDs (inactive metadata only)
// ---------------------------------------------------------------------------

/**
 * Collect extension-declared known IDs from contributions whose kind is not
 * yet bridged in M1 (effect, transition, clipType, parser, agentTool, agent).
 *
 * The IDs are returned as metadata only — no extension render dispatch is
 * triggered.  Callers should pass the full list of contributions and this
 * function will filter to only those that are inactive (not-yet-bridged).
 *
 * @param contributions - All extension contributions (from active extensions).
 */
export function collectExtensionDeclaredIds(
  contributions: readonly ExtensionContribution[],
): InactiveKnownIds {
  const effectIds = new Set<string>();
  const transitionIds = new Set<string>();
  const clipTypeIds = new Set<string>();

  for (const contrib of contributions) {
    // Only consider contributions whose kind is not yet bridged
    const notBridged = contributionKindNotYetBridged(contrib.kind);
    if (notBridged === null) continue; // Already bridged — skip

    switch (contrib.kind) {
      case 'effect':
        if (contrib.effectId) {
          effectIds.add(contrib.effectId);
        }
        break;
      case 'transition':
        if (contrib.transitionId) {
          transitionIds.add(contrib.transitionId);
        }
        break;
      case 'clipType':
        if (contrib.clipTypeId) {
          clipTypeIds.add(contrib.clipTypeId);
        }
        break;
    }
  }

  return Object.freeze({
    effectIds: Object.freeze(effectIds),
    transitionIds: Object.freeze(transitionIds),
    clipTypeIds: Object.freeze(clipTypeIds),
  });
}

// ---------------------------------------------------------------------------
// Timeline scan
// ---------------------------------------------------------------------------

/**
 * The all-known union used during export validation.  Built-in IDs are
 * authoritative; extension-declared IDs are collected but NOT treated as
 * "known" for the purpose of render dispatch — they are surfaced as metadata
 * only so the host can decide whether to warn or block.
 */
interface AllKnownIds {
  clipTypes: ReadonlySet<string>;
  effectTypes: ReadonlySet<string>;
  transitionTypes: ReadonlySet<string>;
  /** Extension-declared IDs (metadata only, not used for dispatch). */
  extensionEffectIds: ReadonlySet<string>;
  extensionTransitionIds: ReadonlySet<string>;
  extensionClipTypeIds: ReadonlySet<string>;
}

function buildAllKnown(
  builtIn: KnownIdCollection,
  extIds: InactiveKnownIds,
): AllKnownIds {
  return {
    clipTypes: builtIn.clipTypes,
    effectTypes: builtIn.effectTypes,
    transitionTypes: builtIn.transitionTypes,
    extensionEffectIds: extIds.effectIds,
    extensionTransitionIds: extIds.transitionIds,
    extensionClipTypeIds: extIds.clipTypeIds,
  };
}

/**
 * Scan a resolved timeline config against built-in known IDs and collect
 * structured {@link ExportDiagnostic} entries for every unknown clip type,
 * effect, or transition.
 *
 * Extension-declared IDs are included as inactive metadata in the result but
 * do **not** gate render dispatch — the host receives them so it can surface
 * appropriate warnings (e.g. "effect X is declared by an inactive extension").
 *
 * @param config - The resolved timeline config to scan (null/empty = no diagnostics).
 * @param builtIn - Built-in known IDs from {@link collectBuiltInKnownIds}.
 * @param extIds - Extension-declared known IDs from {@link collectExtensionDeclaredIds}.
 */
export function scanExportConfig(
  config: ResolvedTimelineConfig | null,
  builtIn: KnownIdCollection,
  extIds: InactiveKnownIds,
): ExportGuardResult {
  const diagnostics: ExportDiagnostic[] = [];
  const unknownClipTypes = new Set<string>();
  const unknownEffects = new Set<string>();
  const unknownTransitions = new Set<string>();

  if (config && config.clips.length > 0) {
    const allKnown = buildAllKnown(builtIn, extIds);

    for (const clip of config.clips) {
      scanClip(clip, allKnown, diagnostics, unknownClipTypes, unknownEffects, unknownTransitions);
    }
  }

  // Sort diagnostics for determinism
  diagnostics.sort((a, b) => a.code.localeCompare(b.code) || a.message.localeCompare(b.message));

  const hasBlockingErrors = diagnostics.some((d) => d.severity === 'error');

  return Object.freeze({
    diagnostics: Object.freeze(diagnostics),
    unknownClipTypes: Object.freeze([...unknownClipTypes].sort()),
    unknownEffects: Object.freeze([...unknownEffects].sort()),
    unknownTransitions: Object.freeze([...unknownTransitions].sort()),
    inactiveExtensionIds: extIds,
    hasBlockingErrors,
  });
}

// ---------------------------------------------------------------------------
// Per-clip scan
// ---------------------------------------------------------------------------

function scanClip(
  clip: ResolvedTimelineClip,
  known: AllKnownIds,
  diagnostics: ExportDiagnostic[],
  unknownClipTypes: Set<string>,
  unknownEffects: Set<string>,
  unknownTransitions: Set<string>,
): void {
  // ---- clip type -----------------------------------------------------------
  if (clip.clipType) {
    if (!known.clipTypes.has(clip.clipType)) {
      const isExtDeclared = known.extensionClipTypeIds.has(clip.clipType);

      diagnostics.push({
        severity: isExtDeclared ? 'warning' : 'error',
        code: 'export/unknown-clip-type',
        message: isExtDeclared
          ? `Clip type "${clip.clipType}" is declared by an inactive extension and may not be available at export time.`
          : `Clip type "${clip.clipType}" is not recognised. Ensure the required extension or registry is installed.`,
        detail: { clipId: clip.id, clipType: clip.clipType },
      });

      if (!isExtDeclared) {
        unknownClipTypes.add(clip.clipType);
      }
    }
  }

  // ---- entrance effect -----------------------------------------------------
  scanEffect(clip, 'entrance', known, diagnostics, unknownEffects);

  // ---- exit effect ---------------------------------------------------------
  scanEffect(clip, 'exit', known, diagnostics, unknownEffects);

  // ---- continuous effect ---------------------------------------------------
  scanEffect(clip, 'continuous', known, diagnostics, unknownEffects);

  // ---- transition ----------------------------------------------------------
  if (clip.transition?.type) {
    const tType = clip.transition.type;
    if (!known.transitionTypes.has(tType)) {
      const isExtDeclared = known.extensionTransitionIds.has(tType);

      diagnostics.push({
        severity: isExtDeclared ? 'warning' : 'error',
        code: 'export/unknown-transition-type',
        message: isExtDeclared
          ? `Transition "${tType}" is declared by an inactive extension and may not be available at export time.`
          : `Transition "${tType}" is not recognised. Ensure the required extension or registry is installed.`,
        detail: { clipId: clip.id, transitionType: tType },
      });

      if (!isExtDeclared) {
        unknownTransitions.add(tType);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Effect scan helper
// ---------------------------------------------------------------------------

type EffectSlot = 'entrance' | 'exit' | 'continuous';

function scanEffect(
  clip: ResolvedTimelineClip,
  slot: EffectSlot,
  known: AllKnownIds,
  diagnostics: ExportDiagnostic[],
  unknownEffects: Set<string>,
): void {
  // The effect can be stored as `ClipEntrance | ClipExit | ClipContinuous`
  // or as `TimelineEffect[] | Record<string, number>` in `effects`.
  const effect = clip[slot];
  if (!effect) return;

  let effectType: string | undefined;

  if (typeof effect === 'object' && 'type' in effect && typeof (effect as Record<string, unknown>).type === 'string') {
    effectType = (effect as Record<string, unknown>).type as string;
  }

  if (!effectType) return;

  if (!known.effectTypes.has(effectType)) {
    const isExtDeclared = known.extensionEffectIds.has(effectType);

    diagnostics.push({
      severity: isExtDeclared ? 'warning' : 'error',
      code: 'export/unknown-effect-type',
      message: isExtDeclared
        ? `${capitalise(slot)} effect "${effectType}" is declared by an inactive extension and may not be available at export time.`
        : `${capitalise(slot)} effect "${effectType}" is not recognised. Ensure the required extension or registry is installed.`,
      detail: { clipId: clip.id, effectType },
    });

    if (!isExtDeclared) {
      unknownEffects.add(effectType);
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function capitalise(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}
