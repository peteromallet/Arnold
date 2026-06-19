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
import type {
  EffectRegistryRecord,
  EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/types.ts';
import { transitionTypes as builtInTransitionTypes } from '@/tools/video-editor/effects/transitions.ts';
import type {
  CapabilityFinding,
  RenderBlocker,
  RenderBlockerReason,
  RenderCapability,
  RenderRoute,
} from '@/tools/video-editor/runtime/renderability.ts';

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
  /** Shared planner-compatible findings for export readiness. */
  readonly findings: readonly CapabilityFinding[];
  /** Shared planner-compatible blockers that prevent browser export. */
  readonly blockers: readonly RenderBlocker[];
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
  effectRegistrySnapshot?: EffectRegistrySnapshot;
  /** Extension-declared IDs (metadata only, not used for dispatch). */
  extensionEffectIds: ReadonlySet<string>;
  extensionTransitionIds: ReadonlySet<string>;
  extensionClipTypeIds: ReadonlySet<string>;
}

function buildAllKnown(
  builtIn: KnownIdCollection,
  extIds: InactiveKnownIds,
  effectRegistrySnapshot?: EffectRegistrySnapshot,
): AllKnownIds {
  return {
    clipTypes: builtIn.clipTypes,
    effectTypes: builtIn.effectTypes,
    transitionTypes: builtIn.transitionTypes,
    ...(effectRegistrySnapshot ? { effectRegistrySnapshot } : {}),
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
  effectRegistrySnapshot?: EffectRegistrySnapshot,
): ExportGuardResult {
  const diagnostics: ExportDiagnostic[] = [];
  const findings: CapabilityFinding[] = [];
  const blockers: RenderBlocker[] = [];
  const unknownClipTypes = new Set<string>();
  const unknownEffects = new Set<string>();
  const unknownTransitions = new Set<string>();

  if (config && config.clips.length > 0) {
    const allKnown = buildAllKnown(builtIn, extIds, effectRegistrySnapshot);

    for (const clip of config.clips) {
      scanClip(clip, allKnown, diagnostics, findings, blockers, unknownClipTypes, unknownEffects, unknownTransitions);
    }
  }

  // Sort diagnostics for determinism
  diagnostics.sort((a, b) => a.code.localeCompare(b.code) || a.message.localeCompare(b.message));
  findings.sort((a, b) => a.id.localeCompare(b.id));
  blockers.sort((a, b) => a.id.localeCompare(b.id));

  const hasBlockingErrors = diagnostics.some((d) => d.severity === 'error');

  return Object.freeze({
    diagnostics: Object.freeze(diagnostics),
    findings: Object.freeze(findings),
    blockers: Object.freeze(blockers),
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
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
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
  scanEffect(clip, 'entrance', known, diagnostics, findings, blockers, unknownEffects);

  // ---- exit effect ---------------------------------------------------------
  scanEffect(clip, 'exit', known, diagnostics, findings, blockers, unknownEffects);

  // ---- continuous effect ---------------------------------------------------
  scanEffect(clip, 'continuous', known, diagnostics, findings, blockers, unknownEffects);

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

/** Routes that the export guard checks independently for each registered effect. */
const GUARD_ROUTES: readonly RenderRoute[] = ['preview', 'browser-export', 'worker-export'] as const;

function scanEffect(
  clip: ResolvedTimelineClip,
  slot: EffectSlot,
  known: AllKnownIds,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
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

  const snapshotRecord = known.effectRegistrySnapshot?.get(effectType);
  if (!known.effectTypes.has(effectType) && !snapshotRecord) {
    const isExtDeclared = known.extensionEffectIds.has(effectType);
    const message = isExtDeclared
      ? `${capitalise(slot)} effect \"${effectType}\" is declared by an inactive extension and may not be available at export time.`
      : `${capitalise(slot)} effect \"${effectType}\" is not recognised. Ensure the required extension or registry is installed.`;

    diagnostics.push({
      severity: isExtDeclared ? 'warning' : 'error',
      code: 'export/unknown-effect-type',
      message,
      detail: { clipId: clip.id, effectType },
    });

    if (!isExtDeclared) {
      unknownEffects.add(effectType);
      pushEffectFindingAndBlocker(findings, blockers, {
        id: `export.effect.${clip.id}.${slot}.${effectType}.missing`,
        reason: 'missing-contribution',
        message,
        clipId: clip.id,
        effectType,
        slot,
        route: 'browser-export',
      });
    }
    return;
  }

  if (snapshotRecord) {
    scanEffectRecordRenderability(clip, slot, effectType, snapshotRecord, diagnostics, findings, blockers);
  }
}

function scanEffectRecordRenderability(
  clip: ResolvedTimelineClip,
  slot: EffectSlot,
  effectType: string,
  record: EffectRegistryRecord,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
): void {
  if (record.status !== 'active') {
    const message = `${capitalise(slot)} effect \"${effectType}\" is registered but inactive and cannot be used for export or preview.`;
    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-effect',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        effectType,
        effectStatus: record.status,
        provenance: record.provenance,
      },
    });

    // Emit a blocker for every guarded route — an inactive effect can't be used anywhere.
    for (const route of GUARD_ROUTES) {
      pushEffectFindingAndBlocker(findings, blockers, {
        id: `export.effect.${clip.id}.${slot}.${effectType}.inactive.${route}`,
        reason: 'inactive-extension',
        message: `${capitalise(slot)} effect \"${effectType}\" on route \"${route}\" is registered but inactive.`,
        clipId: clip.id,
        effectType,
        slot,
        route,
        record,
      });
    }
    return;
  }

  // Check each guarded route independently.
  for (const route of GUARD_ROUTES) {
    const capability = record.renderability.capabilities.find((cap) => cap.route === route);

    if (!capability) {
      // No capability declared for this route — pass silently.
      continue;
    }

    if (capability.status === 'supported') {
      // Route is supported — pass silently.
      continue;
    }

    if (capability.status === 'unknown') {
      // Unknown support — emit a warning finding (non-blocking).
      const message = capability.message
        ?? `${capitalise(slot)} effect \"${effectType}\" has unknown support for ${route}.`;
      diagnostics.push({
        severity: 'warning',
        code: 'export/unknown-route-support',
        message,
        extensionId: record.ownerExtensionId,
        contributionId: record.contributionId,
        detail: {
          clipId: clip.id,
          effectType,
          renderRoute: route,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      findings.push({
        id: `export.effect.${clip.id}.${slot}.${effectType}.${route}.unknown`,
        severity: 'warning',
        route,
        reason: 'unknown',
        message,
        clipId: clip.id,
        ...(record.ownerExtensionId ? { extensionId: record.ownerExtensionId } : {}),
        ...(record.contributionId ? { contributionId: record.contributionId } : {}),
        detail: {
          effectType,
          slot,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      continue;
    }

    // status === 'blocked' — emit error diagnostic, finding, and blocker.
    const reason = capability.blockerReason ?? firstRouteBlockerReason(record, route) ?? 'route-unsupported';
    const message = capability.message
      ?? `${capitalise(slot)} effect \"${effectType}\" does not support ${route}.`;

    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-effect',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        effectType,
        renderRoute: route,
        blockerReason: reason,
        provenance: record.provenance,
      },
    });
    pushEffectFindingAndBlocker(findings, blockers, {
      id: `export.effect.${clip.id}.${slot}.${effectType}.${route}.${reason}`,
      reason,
      message,
      clipId: clip.id,
      effectType,
      slot,
      route,
      record,
    });
  }
}

function firstRouteBlockerReason(record: EffectRegistryRecord, route: RenderRoute): RenderBlockerReason | undefined {
  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
}

function pushEffectFindingAndBlocker(
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  input: {
    id: string;
    reason: RenderBlockerReason;
    message: string;
    clipId: string;
    effectType: string;
    slot: EffectSlot;
    route: RenderRoute;
    record?: EffectRegistryRecord;
  },
): void {
  const detail: Record<string, unknown> = {
    effectType: input.effectType,
    slot: input.slot,
  };
  if (input.record?.provenance) {
    detail.provenance = input.record.provenance;
  }
  const finding: CapabilityFinding = {
    id: input.id,
    severity: 'error',
    route: input.route,
    reason: input.reason,
    message: input.message,
    clipId: input.clipId,
    ...(input.record?.ownerExtensionId ? { extensionId: input.record.ownerExtensionId } : {}),
    ...(input.record?.contributionId ? { contributionId: input.record.contributionId } : {}),
    detail,
  };
  findings.push(finding);
  blockers.push({
    ...finding,
    severity: 'error',
    route: input.route,
    reason: input.reason,
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function capitalise(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}
