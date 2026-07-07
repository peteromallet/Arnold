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
  CompositionGraph,
  ContributionKind,
  ExtensionContribution,
} from '@reigh/editor-sdk';
import {
  getVideoFamilyDefinition,
  getVideoFamilyLegacyBridgeStatus,
} from '@reigh/editor-sdk';
import { BUILTIN_CLIP_TYPES } from '@/sdk/video/timeline/clipTypes.ts';
import type { ResolvedTimelineClip, ResolvedTimelineConfig, TimelineConfig } from '@/tools/video-editor/types/index.ts';
import {
  getTimelineClipShader,
  getTimelinePostprocessShader,
  scanTimelineLiveBindings,
  type TimelineLiveBindingRecord,
} from '@/tools/video-editor/lib/timeline-domain.ts';
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
import {
  shaderMissingMaterializerBlockerMessage,
  type ShaderMaterializerRequirementScope,
} from '@/tools/video-editor/runtime/renderability.ts';
import {
  COMPOSITION_DIAGNOSTIC_CODE,
  isBlockingTargetCompositionDiagnosticCode,
  isBlockingM5CompositionDiagnosticCode,
  m5CompositionBlockerReason,
  isBlockingReferenceCompositionDiagnosticCode,
  referenceCompositionBlockerReason,
  isDeterministicCaptureConversionDiagnosticCode,
  isEffectDiagnosticCode,
  isTransitionDiagnosticCode,
} from '@/tools/video-editor/runtime/composition/diagnostics.ts';
import {
  projectProcessResultContracts,
  type ProcessResultAttachRecord,
} from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import { validateShaderComposition } from '@/tools/video-editor/runtime/composition/shaderValidation.ts';
import type { TransitionRegistryRecord, TransitionRegistrySnapshot } from '@/tools/video-editor/transitions/registry/types.ts';
import type {
  ClipTypeRegistryRecord,
  ClipTypeRegistrySnapshot,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';

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

function getContributionRuntimeStatus(kind: ContributionKind): {
  readonly legacyBridgeStatus: string | null;
  readonly isBridged: boolean;
} {
  const family = getVideoFamilyDefinition(kind);
  return {
    legacyBridgeStatus: getVideoFamilyLegacyBridgeStatus(kind),
    isBridged: family?.executionMaturity === 'runtime-bridged' ||
      family?.executionMaturity === 'host-integrated' ||
      family?.executionMaturity === 'public-supported',
  };
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

interface ProcessAttachEvidenceIndex {
  readonly attachedMaterialRefIds: ReadonlySet<string>;
  readonly attachedArtifactIds: ReadonlySet<string>;
  readonly attachedShaderContributionKeys: ReadonlySet<string>;
}

const LEGACY_EXPORT_GRAPH_COMPATIBILITY_BLOCKER_ID = 'exportGuard.compositionGraph.legacy-shader-ref-compatibility';
const GRAPH_TARGET_BLOCKER_ROUTES: readonly RenderRoute[] = ['browser-export', 'worker-export'];

function shaderContributionKey(
  extensionId: string | undefined,
  contributionId: string | undefined,
): string | undefined {
  if (!extensionId || !contributionId) {
    return undefined;
  }
  return `${extensionId}:${contributionId}`;
}

function createProcessAttachEvidenceIndex(
  records: readonly ProcessResultAttachRecord[] | undefined,
): ProcessAttachEvidenceIndex {
  const attachedMaterialRefIds = new Set<string>();
  const attachedArtifactIds = new Set<string>();
  const attachedShaderContributionKeys = new Set<string>();

  for (const record of records ?? []) {
    if (record.status !== 'completed') {
      continue;
    }

    const projection = projectProcessResultContracts(record);
    for (const materialRef of projection.materialRefs) {
      attachedMaterialRefIds.add(materialRef.id);
      const key = shaderContributionKey(
        materialRef.producerExtensionId,
        typeof materialRef.provenance?.contributionId === 'string'
          ? materialRef.provenance.contributionId
          : undefined,
      );
      if (key) {
        attachedShaderContributionKeys.add(key);
      }
    }

    for (const artifact of projection.artifacts) {
      attachedArtifactIds.add(artifact.id);
    }
  }

  return Object.freeze({
    attachedMaterialRefIds: Object.freeze(attachedMaterialRefIds),
    attachedArtifactIds: Object.freeze(attachedArtifactIds),
    attachedShaderContributionKeys: Object.freeze(attachedShaderContributionKeys),
  });
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
 * Collect extension-declared known IDs from contributions whose kind should
 * remain visible as inactive metadata to the export guard.
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
    // Preserve the current clipType declared-ID bypass under the maturity
    // model: clipType is runtime-bridged in the registry, but declared IDs
    // still feed metadata-only export diagnostics when the runtime registry
    // does not have an active clip-type record yet.
    if (contrib.kind === 'clipType') {
      if (contrib.clipTypeId) {
        clipTypeIds.add(contrib.clipTypeId);
      }
      continue;
    }

    const runtimeStatus = getContributionRuntimeStatus(contrib.kind);
    if (runtimeStatus.isBridged || runtimeStatus.legacyBridgeStatus === null) continue;

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
  transitionRegistrySnapshot?: TransitionRegistrySnapshot;
  clipTypeRegistrySnapshot?: ClipTypeRegistrySnapshot;
  /** Extension-declared IDs (metadata only, not used for dispatch). */
  extensionEffectIds: ReadonlySet<string>;
  extensionTransitionIds: ReadonlySet<string>;
  extensionClipTypeIds: ReadonlySet<string>;
}

function buildAllKnown(
  builtIn: KnownIdCollection,
  extIds: InactiveKnownIds,
  effectRegistrySnapshot?: EffectRegistrySnapshot,
  transitionRegistrySnapshot?: TransitionRegistrySnapshot,
  clipTypeRegistrySnapshot?: ClipTypeRegistrySnapshot,
): AllKnownIds {
  return {
    clipTypes: builtIn.clipTypes,
    effectTypes: builtIn.effectTypes,
    transitionTypes: builtIn.transitionTypes,
    ...(effectRegistrySnapshot ? { effectRegistrySnapshot } : {}),
    ...(transitionRegistrySnapshot ? { transitionRegistrySnapshot } : {}),
    ...(clipTypeRegistrySnapshot ? { clipTypeRegistrySnapshot } : {}),
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
  transitionRegistrySnapshot?: TransitionRegistrySnapshot,
  clipTypeRegistrySnapshot?: ClipTypeRegistrySnapshot,
  compositionGraph?: CompositionGraph,
  processResultAttachRecords?: readonly ProcessResultAttachRecord[],
): ExportGuardResult {
  const diagnostics: ExportDiagnostic[] = [];
  const findings: CapabilityFinding[] = [];
  const blockers: RenderBlocker[] = [];
  const unknownClipTypes = new Set<string>();
  const unknownEffects = new Set<string>();
  const unknownTransitions = new Set<string>();
  const processAttachEvidence = createProcessAttachEvidenceIndex(processResultAttachRecords);

  if (config && config.clips.length > 0) {
    scanLiveBindingExportBlockers(config, diagnostics, findings, blockers);
    scanCompositionGraphTargetExportBlockers(
      diagnostics,
      findings,
      blockers,
      compositionGraph,
      processAttachEvidence,
    );
    scanCompositionGraphM5ExportBlockers(diagnostics, findings, blockers, compositionGraph);
    scanTimelineShaderExportBlockers(
      config,
      diagnostics,
      findings,
      blockers,
      compositionGraph,
      processAttachEvidence,
    );
    pushLegacyGraphCompatibilityFindingsAndBlockers(config, findings, blockers, compositionGraph);

    const allKnown = buildAllKnown(builtIn, extIds, effectRegistrySnapshot, transitionRegistrySnapshot, clipTypeRegistrySnapshot);

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

function scanLiveBindingExportBlockers(
  config: ResolvedTimelineConfig,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
): void {
  const liveScan = scanTimelineLiveBindings(config as TimelineConfig);

  for (const record of liveScan.bindings) {
    if (!record.blocksExport) {
      continue;
    }
    pushLiveBindingFindingAndBlocker(diagnostics, findings, blockers, record);
  }
}

function hasLegacyTimelineShaderStorage(config: ResolvedTimelineConfig | null | undefined): boolean {
  if (!config) return false;
  if (getTimelinePostprocessShader(config)) return true;
  return config.clips.some((clip) => Boolean(getTimelineClipShader(clip)));
}

function graphShaderSummaries(
  compositionGraph: CompositionGraph | undefined,
) {
  if (!compositionGraph) {
    return undefined;
  }

  const validation = validateShaderComposition(undefined, compositionGraph);
  return validation.shaders && validation.shaders.length > 0
    ? validation.shaders
    : undefined;
}

function hasTimelineShaderMetadata(
  config: ResolvedTimelineConfig | null | undefined,
  compositionGraph?: CompositionGraph,
): boolean {
  if (compositionGraph) {
    return Boolean(graphShaderSummaries(compositionGraph)?.some((shader) => shader.enabled !== false));
  }

  return hasLegacyTimelineShaderStorage(config);
}

export { hasTimelineShaderMetadata };

function targetCompositionExportCode(code: string): ExportDiagnostic['code'] | undefined {
  if (isBlockingReferenceCompositionDiagnosticCode(code)) {
    return 'export/unresolved-ref';
  }

  switch (code) {
    case COMPOSITION_DIAGNOSTIC_CODE.INVALID_TARGET_PATH:
      return 'export/invalid-target-path';
    case COMPOSITION_DIAGNOSTIC_CODE.UNSUPPORTED_RESERVED_TARGET:
      return 'export/unsupported-reserved-target';
    case COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_TARGET_REF:
      return 'export/unknown-target-ref';
    case COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_UNIFORM:
      return 'export/unknown-uniform';
    case COMPOSITION_DIAGNOSTIC_CODE.NON_BINDABLE_TARGET:
      return 'export/non-bindable-target';
    case COMPOSITION_DIAGNOSTIC_CODE.TARGET_VALUE_TYPE_ERROR:
      return 'export/target-value-type-error';
    case COMPOSITION_DIAGNOSTIC_CODE.TARGET_INTERPOLATION_GAP:
      return 'export/target-interpolation-gap';
    case COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_CONVERSION_FAILED:
      return 'export/deterministic-capture-conversion-failed';
    case COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_TARGET_PATH_UNRESOLVABLE:
      return 'export/deterministic-capture-target-path-unresolvable';
    case COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_VALUE_NORMALIZATION_FAILED:
      return 'export/deterministic-capture-value-normalization-failed';
    case COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_TIMING_FAILED:
      return 'export/deterministic-capture-timing-failed';
    case COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_PROVENANCE_MISMATCH:
      return 'export/deterministic-capture-provenance-mismatch';
    default:
      return undefined;
  }
}

function targetCompositionBlockerReason(code: string): RenderBlockerReason {
  if (isBlockingReferenceCompositionDiagnosticCode(code)) {
    return referenceCompositionBlockerReason(
      code as Parameters<typeof referenceCompositionBlockerReason>[0],
    ) as RenderBlockerReason;
  }

  switch (code) {
    case COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_TARGET_REF:
      return 'missing-contribution';
    case COMPOSITION_DIAGNOSTIC_CODE.UNSUPPORTED_RESERVED_TARGET:
      return 'inactive-extension';
    case COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_CONVERSION_FAILED:
      return 'live-unbaked';
    case COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_TARGET_PATH_UNRESOLVABLE:
      return 'live-unbaked';
    case COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_VALUE_NORMALIZATION_FAILED:
      return 'live-unbaked';
    case COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_TIMING_FAILED:
      return 'live-unbaked';
    case COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_PROVENANCE_MISMATCH:
      return 'live-unbaked';
    default:
      return 'unknown';
  }
}

function scanCompositionGraphTargetExportBlockers(
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  compositionGraph?: CompositionGraph,
  processAttachEvidence?: ProcessAttachEvidenceIndex,
): void {
  if (!compositionGraph?.diagnostics.length) {
    return;
  }

  compositionGraph.diagnostics.forEach((diagnostic, diagnosticIndex) => {
    if (!isBlockingTargetCompositionDiagnosticCode(diagnostic.code)) {
      return;
    }

    const exportCode = targetCompositionExportCode(diagnostic.code);
    if (!exportCode) {
      return;
    }

    if (
      (
        typeof diagnostic.detail?.materialRefId === 'string'
        && processAttachEvidence?.attachedMaterialRefIds.has(diagnostic.detail.materialRefId)
      )
      || (
        typeof diagnostic.detail?.captureRef === 'string'
        && processAttachEvidence?.attachedArtifactIds.has(diagnostic.detail.captureRef)
      )
    ) {
      return;
    }

    // Extract conversion metadata for deterministic capture diagnostics.
    // These are kept separate from material live-only diagnostics — material
    // codes are not in BLOCKING_TARGET_COMPOSITION_DIAGNOSTIC_CODES so they
    // never reach this block.
    const isCaptureConversion = isDeterministicCaptureConversionDiagnosticCode(diagnostic.code);
    const captureRef = isCaptureConversion && typeof diagnostic.detail?.captureRef === 'string'
      ? diagnostic.detail.captureRef
      : undefined;
    const provenanceHash = isCaptureConversion && typeof diagnostic.detail?.provenanceHash === 'string'
      ? diagnostic.detail.provenanceHash
      : undefined;

    const detail = {
      source: 'composition-graph',
      graphDiagnosticCode: diagnostic.code,
      ...(diagnostic.detail ?? {}),
      ...(captureRef ? { captureRef } : {}),
      ...(provenanceHash ? { provenanceHash } : {}),
    };
    const extensionId = diagnostic.extensionId
      ?? (diagnostic.detail?.extensionId as string | undefined);
    const contributionId = diagnostic.contributionId
      ?? (diagnostic.detail?.contributionId as string | undefined);
    const clipId = typeof diagnostic.detail?.clipId === 'string'
      ? diagnostic.detail.clipId
      : undefined;
    const reason = targetCompositionBlockerReason(diagnostic.code);

    diagnostics.push({
      severity: 'error',
      code: exportCode,
      message: diagnostic.message,
      extensionId,
      contributionId,
      detail: clipId ? { clipId, ...detail } : detail,
    });

    for (const route of GRAPH_TARGET_BLOCKER_ROUTES) {
      const finding: CapabilityFinding = {
        id: `export.compositionGraph.${diagnostic.code}.${diagnosticIndex}.${route}`,
        severity: 'error',
        route,
        reason,
        message: diagnostic.message,
        ...(clipId ? { clipId } : {}),
        ...(extensionId ? { extensionId } : {}),
        ...(contributionId ? { contributionId } : {}),
        detail,
      };
      findings.push(finding);
      blockers.push({
        ...finding,
        severity: 'error',
        route,
        reason,
      });
    }
  });
}

// ---------------------------------------------------------------------------
// M5 (Effect / Transition) composition graph diagnostics → export blockers
// ---------------------------------------------------------------------------

/**
 * Map an M5 composition diagnostic code to a canonical export diagnostic code.
 */
function m5CompositionExportCode(code: string): string | undefined {
  if (isEffectDiagnosticCode(code)) {
    return 'export/effect-unresolved-ref';
  }
  if (isTransitionDiagnosticCode(code)) {
    return 'export/transition-unresolved-ref';
  }
  return undefined;
}

/**
 * Scan composition graph diagnostics for blocking M5 (effect / transition)
 * diagnostic codes and funnel them into export diagnostics, findings, and
 * blockers.
 *
 * Non-blocking M5 codes (warnings) are also surfaced as findings but do NOT
 * produce blockers — they are informational only and do not prevent export.
 */
function scanCompositionGraphM5ExportBlockers(
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  compositionGraph?: CompositionGraph,
): void {
  if (!compositionGraph?.diagnostics.length) {
    return;
  }

  compositionGraph.diagnostics.forEach((diagnostic, diagnosticIndex) => {
    const code = diagnostic.code;
    if (!isEffectDiagnosticCode(code) && !isTransitionDiagnosticCode(code)) {
      return;
    }

    const exportCode = m5CompositionExportCode(code);
    if (!exportCode) {
      return;
    }

    const isBlocking = isBlockingM5CompositionDiagnosticCode(code);
    const severity: 'error' | 'warning' = isBlocking ? 'error' : 'warning';
    const reason = isBlocking
      ? (m5CompositionBlockerReason(code as Parameters<typeof m5CompositionBlockerReason>[0]) as RenderBlockerReason)
      : 'unknown';

    const detail = {
      source: 'composition-graph',
      graphDiagnosticCode: code,
      ...(diagnostic.detail ?? {}),
      diagnosticKind: isEffectDiagnosticCode(code) ? 'effect' : 'transition',
    };
    const extensionId = diagnostic.extensionId
      ?? (diagnostic.detail?.extensionId as string | undefined);
    const contributionId = diagnostic.contributionId
      ?? (diagnostic.detail?.contributionId as string | undefined);
    const clipId = typeof diagnostic.detail?.clipId === 'string'
      ? diagnostic.detail.clipId
      : undefined;

    diagnostics.push({
      severity,
      code: exportCode,
      message: diagnostic.message,
      extensionId,
      contributionId,
      detail: clipId ? { clipId, ...detail } : detail,
    });

    for (const route of GRAPH_TARGET_BLOCKER_ROUTES) {
      const finding: CapabilityFinding = {
        id: `export.compositionGraph.${code}.${diagnosticIndex}.${route}`,
        severity,
        route,
        reason,
        message: diagnostic.message,
        ...(clipId ? { clipId } : {}),
        ...(extensionId ? { extensionId } : {}),
        ...(contributionId ? { contributionId } : {}),
        detail,
      };
      findings.push(finding);

      if (isBlocking) {
        blockers.push({
          ...finding,
          severity: 'error',
          route,
          reason,
        });
      }
    }
  });
}

function scanTimelineShaderExportBlockers(
  _config: ResolvedTimelineConfig,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  compositionGraph?: CompositionGraph,
  processAttachEvidence?: ProcessAttachEvidenceIndex,
): void {
  if (!compositionGraph) {
    return;
  }

  for (const shader of graphShaderSummaries(compositionGraph) ?? []) {
    if (shader.enabled === false) continue;
    if (processAttachEvidence?.attachedShaderContributionKeys.has(
      shaderContributionKey(shader.extensionId, shader.contributionId) ?? '',
    )) {
      continue;
    }
    pushShaderMaterializerFindingAndBlocker(diagnostics, findings, blockers, {
      shaderId: shader.shaderId,
      extensionId: shader.extensionId,
      contributionId: shader.contributionId,
      scope: shader.scope,
      clipId: shader.scope === 'clip' ? shader.clipId : undefined,
      source: 'composition-graph',
    });
  }
}

function pushLegacyGraphCompatibilityFindingsAndBlockers(
  config: ResolvedTimelineConfig,
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  compositionGraph: CompositionGraph | undefined,
): void {
  if (compositionGraph || !hasLegacyTimelineShaderStorage(config)) {
    return;
  }

  for (const route of GRAPH_TARGET_BLOCKER_ROUTES) {
    const finding: CapabilityFinding = {
      id: `${LEGACY_EXPORT_GRAPH_COMPATIBILITY_BLOCKER_ID}.${route}`,
      severity: 'error',
      route,
      reason: 'unknown',
      message:
        'CompositionGraph was not provided; export shader/ref decisions require graph authority before export.',
      detail: {
        source: 'composition-graph-compatibility',
        compatibilityMode: 'legacy-shader-ref',
        renderRoute: route,
      },
    };
    findings.push(finding);
    blockers.push({
      ...finding,
      severity: 'error',
      route,
      reason: 'unknown',
    });
  }
}

function pushShaderMaterializerFindingAndBlocker(
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  input: {
    readonly shaderId: string;
    readonly extensionId: string;
    readonly contributionId: string;
    readonly scope: ShaderMaterializerRequirementScope;
    readonly clipId?: string;
    readonly source: 'composition-graph';
  },
): void {
  const routes: readonly RenderRoute[] = ['browser-export', 'worker-export'];

  for (const route of routes) {
    const message = shaderMissingMaterializerBlockerMessage(input.shaderId, input.scope, input.clipId);
    const id = `export.shader.${input.scope}.${input.clipId ?? 'timeline'}.${input.shaderId}.${route}.missing-materializer`;
    const detail = {
      shaderId: input.shaderId,
      shaderScope: input.scope,
      renderRoute: route,
      ...(input.clipId ? { clipId: input.clipId } : {}),
    };

    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-shader',
      message,
      extensionId: input.extensionId,
      contributionId: input.contributionId,
      detail,
    });

    const finding: CapabilityFinding = {
      id,
      severity: 'error',
      route,
      reason: 'missing-material',
      message,
      ...(input.clipId ? { clipId: input.clipId } : {}),
      extensionId: input.extensionId,
      contributionId: input.contributionId,
      detail: {
        shaderId: input.shaderId,
        shaderScope: input.scope,
        source: input.source,
      },
    };
    findings.push(finding);
    blockers.push({
      ...finding,
      severity: 'error',
      route,
      reason: 'missing-material',
    });
  }
}

function liveBindingStatusMessage(record: TimelineLiveBindingRecord): string {
  const bindingId = record.binding.bindingId;
  switch (record.status) {
    case 'active':
      return `Live binding "${bindingId}" is active and must be baked or removed before export.`;
    case 'inactive':
      return `Live binding "${bindingId}" references an inactive source and must be baked or removed before export.`;
    case 'missing':
      return `Live binding "${bindingId}" references a missing source and must be baked or removed before export.`;
    case 'disposed':
      return `Live binding "${bindingId}" references a disposed source and must be baked or removed before export.`;
    case 'orphaned':
      return `Live binding "${bindingId}" references an orphaned source and must be baked or removed before export.`;
    case 'partiallyBaked':
      return `Live binding "${bindingId}" is partially baked; unresolved ranges must be baked or removed before export.`;
    case 'malformed':
      return `Live binding metadata on clip "${record.clipId}" is malformed and blocks export until fixed or removed.`;
    case 'resolved':
      return `Live binding "${bindingId}" has deterministic replacement metadata.`;
  }
}

function pushLiveBindingFindingAndBlocker(
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  record: TimelineLiveBindingRecord,
): void {
  const deterministicRefKinds = Array.from(new Set([
    ...(Array.isArray(record.binding.deterministicRefs)
      ? record.binding.deterministicRefs.map((ref) => ref.kind)
      : []),
    ...(Array.isArray(record.binding.bake?.deterministicRefs)
      ? record.binding.bake.deterministicRefs.map((ref) => ref.kind)
      : []),
  ])).sort();
  const message = liveBindingStatusMessage(record);
  const id = `export.liveBinding.${record.clipId}.${record.binding.bindingId}.${record.status}`;
  const detail = {
    bindingId: record.binding.bindingId,
    sourceId: record.binding.sourceId,
    sourceKind: record.binding.sourceKind,
    resolutionStatus: record.status,
    bakeStatus: record.binding.bake?.status,
    deterministicRefKinds,
    path: record.path,
    diagnostics: record.diagnostics.map((diagnostic) => ({
      code: diagnostic.code,
      message: diagnostic.message,
      severity: diagnostic.severity,
    })),
  };

  diagnostics.push({
    severity: 'error',
    code: 'export/live-binding-unresolved',
    message,
    detail: {
      clipId: record.clipId,
      ...detail,
    },
  });

  const finding: CapabilityFinding = {
    id,
    severity: 'error',
    route: 'browser-export',
    reason: 'live-unbaked',
    message,
    clipId: record.clipId,
    detail,
  };
  findings.push(finding);
  blockers.push({
    ...finding,
    severity: 'error',
    route: 'browser-export',
    reason: 'live-unbaked',
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
    // 1) Built-in / trusted clip types — fast path, no registry scan needed.
    if (known.clipTypes.has(clip.clipType)) {
      // Known built-in — pass through to effect/transition scanning.
    }
    // 2) Check the clip-type registry snapshot for contributed clip types.
    else {
      const snapshotRecord = known.clipTypeRegistrySnapshot?.get(clip.clipType);

      if (snapshotRecord) {
        // Clip type is registered — scan its status and capabilities.
        scanClipTypeRecordRenderability(clip, clip.clipType, snapshotRecord, diagnostics, findings, blockers);
      } else {
        // Clip type is NOT in the registry snapshot — check extension-declared fallback.
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

          // Emit shared blocker vocabulary for truly unknown clip types.
          pushClipTypeFindingAndBlocker(findings, blockers, {
            id: `export.clipType.${clip.id}.${clip.clipType}.missing`,
            reason: 'missing-contribution',
            message: `Clip type "${clip.clipType}" is not recognised. Ensure the required extension or registry is installed.`,
            clipId: clip.id,
            clipType: clip.clipType,
            route: 'browser-export',
          });
        }
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
    const snapshotRecord = known.transitionRegistrySnapshot?.get(tType);

    // Check built-in + registry
    if (!known.transitionTypes.has(tType) && !snapshotRecord) {
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
        pushTransitionFindingAndBlocker(findings, blockers, {
          id: `export.transition.${clip.id}.${tType}.missing`,
          reason: 'missing-contribution',
          message: `Transition "${tType}" is not recognised. Ensure the required extension or registry is installed.`,
          clipId: clip.id,
          transitionType: tType,
          route: 'browser-export',
        });
      }
      return;
    }

    // Registry-based scanning
    if (snapshotRecord) {
      scanTransitionRecordRenderability(clip, tType, snapshotRecord, diagnostics, findings, blockers);
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
      ? `${capitalise(slot)} effect "${effectType}" is declared by an inactive extension and may not be available at export time.`
      : `${capitalise(slot)} effect "${effectType}" is not recognised. Ensure the required extension or registry is installed.`;

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
    const message = `${capitalise(slot)} effect "${effectType}" is registered but inactive and cannot be used for export or preview.`;
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
        message: `${capitalise(slot)} effect "${effectType}" on route "${route}" is registered but inactive.`,
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
        ?? `${capitalise(slot)} effect "${effectType}" has unknown support for ${route}.`;
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
      ?? `${capitalise(slot)} effect "${effectType}" does not support ${route}.`;

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
// Transition scan helpers (T15)
// ---------------------------------------------------------------------------

/** Routes that the export guard checks independently for each registered transition. */
const TRANSITION_GUARD_ROUTES: readonly RenderRoute[] = ['preview', 'browser-export', 'worker-export'] as const;

function scanTransitionRecordRenderability(
  clip: ResolvedTimelineClip,
  transitionType: string,
  record: TransitionRegistryRecord,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
): void {
  if (record.status !== 'active') {
    const message = `Transition "${transitionType}" is registered but inactive and cannot be used for export or preview.`;
    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-transition',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        transitionType,
        transitionStatus: record.status,
        provenance: record.provenance,
      },
    });

    for (const route of TRANSITION_GUARD_ROUTES) {
      pushTransitionFindingAndBlocker(findings, blockers, {
        id: `export.transition.${clip.id}.${transitionType}.inactive.${route}`,
        reason: 'inactive-extension',
        message: `Transition "${transitionType}" on route "${route}" is registered but inactive.`,
        clipId: clip.id,
        transitionType,
        route,
        record,
      });
    }
    return;
  }

  for (const route of TRANSITION_GUARD_ROUTES) {
    const capability = record.renderability.capabilities.find((cap) => cap.route === route);

    if (!capability) {
      // No capability declared for this route — this is a blocker for worker-export by default
      if (route === 'worker-export') {
        const message = `Transition "${transitionType}" does not declare ${route} support. Worker export is blocked by default.`;
        diagnostics.push({
          severity: 'error',
          code: 'export/unrenderable-transition',
          message,
          extensionId: record.ownerExtensionId,
          contributionId: record.contributionId,
          detail: {
            clipId: clip.id,
            transitionType,
            renderRoute: route,
            blockerReason: 'route-unsupported',
            provenance: record.provenance,
          },
        });
        pushTransitionFindingAndBlocker(findings, blockers, {
          id: `export.transition.${clip.id}.${transitionType}.${route}.route-unsupported`,
          reason: 'route-unsupported',
          message,
          clipId: clip.id,
          transitionType,
          route,
          record,
        });
      }
      continue;
    }

    if (capability.status === 'supported') continue;

    if (capability.status === 'unknown') {
      const message = capability.message
        ?? `Transition "${transitionType}" has unknown support for ${route}.`;
      diagnostics.push({
        severity: 'warning',
        code: 'export/unknown-route-support',
        message,
        extensionId: record.ownerExtensionId,
        contributionId: record.contributionId,
        detail: {
          clipId: clip.id,
          transitionType,
          renderRoute: route,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      findings.push({
        id: `export.transition.${clip.id}.${transitionType}.${route}.unknown`,
        severity: 'warning',
        route,
        reason: 'unknown',
        message,
        clipId: clip.id,
        ...(record.ownerExtensionId ? { extensionId: record.ownerExtensionId } : {}),
        ...(record.contributionId ? { contributionId: record.contributionId } : {}),
        detail: {
          transitionType,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      continue;
    }

    // status === 'blocked'
    const reason = capability.blockerReason ?? firstTransitionRouteBlockerReason(record, route) ?? 'route-unsupported';
    const message = capability.message
      ?? `Transition "${transitionType}" does not support ${route}.`;

    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-transition',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        transitionType,
        renderRoute: route,
        blockerReason: reason,
        provenance: record.provenance,
      },
    });
    pushTransitionFindingAndBlocker(findings, blockers, {
      id: `export.transition.${clip.id}.${transitionType}.${route}.${reason}`,
      reason,
      message,
      clipId: clip.id,
      transitionType,
      route,
      record,
    });
  }
}

function firstTransitionRouteBlockerReason(record: TransitionRegistryRecord, route: RenderRoute): RenderBlockerReason | undefined {
  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
}

function pushTransitionFindingAndBlocker(
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  input: {
    id: string;
    reason: RenderBlockerReason;
    message: string;
    clipId: string;
    transitionType: string;
    route: RenderRoute;
    record?: TransitionRegistryRecord;
  },
): void {
  const detail: Record<string, unknown> = {
    transitionType: input.transitionType,
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
// Clip-type registry scan helpers
// ---------------------------------------------------------------------------

/** Routes that the export guard checks independently for each registered clip type. */
const CLIP_TYPE_GUARD_ROUTES: readonly RenderRoute[] = ['preview', 'browser-export', 'worker-export'] as const;

function scanClipTypeRecordRenderability(
  clip: ResolvedTimelineClip,
  clipType: string,
  record: ClipTypeRegistryRecord,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
): void {
  if (record.status !== 'active') {
    const message = `Clip type "${clipType}" is registered but inactive and cannot be used for export or preview.`;
    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-clip-type',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        clipType,
        clipTypeStatus: record.status,
        provenance: record.provenance,
      },
    });

    // Emit a blocker for every guarded route — an inactive clip type can't be used anywhere.
    for (const route of CLIP_TYPE_GUARD_ROUTES) {
      pushClipTypeFindingAndBlocker(findings, blockers, {
        id: `export.clipType.${clip.id}.${clipType}.inactive.${route}`,
        reason: 'inactive-extension',
        message: `Clip type "${clipType}" on route "${route}" is registered but inactive.`,
        clipId: clip.id,
        clipType,
        route,
        record,
      });
    }
    return;
  }

  // Active record — check each guarded route independently.
  for (const route of CLIP_TYPE_GUARD_ROUTES) {
    const capability = record.renderability.capabilities.find((cap) => cap.route === route);

    if (!capability) {
      // No capability declared for this route — pass silently (like effects).
      continue;
    }

    if (capability.status === 'supported') {
      // Route is supported — pass silently.
      continue;
    }

    if (capability.status === 'unknown') {
      // Unknown support — emit a warning finding (non-blocking).
      const message = capability.message
        ?? `Clip type "${clipType}" has unknown support for ${route}.`;
      diagnostics.push({
        severity: 'warning',
        code: 'export/unknown-route-support',
        message,
        extensionId: record.ownerExtensionId,
        contributionId: record.contributionId,
        detail: {
          clipId: clip.id,
          clipType,
          renderRoute: route,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      findings.push({
        id: `export.clipType.${clip.id}.${clipType}.${route}.unknown`,
        severity: 'warning',
        route,
        reason: 'unknown',
        message,
        clipId: clip.id,
        ...(record.ownerExtensionId ? { extensionId: record.ownerExtensionId } : {}),
        ...(record.contributionId ? { contributionId: record.contributionId } : {}),
        detail: {
          clipType,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      continue;
    }

    // status === 'blocked' — emit error diagnostic, finding, and blocker.
    const reason = capability.blockerReason ?? firstClipTypeRouteBlockerReason(record, route) ?? 'route-unsupported';
    const message = capability.message
      ?? `Clip type "${clipType}" does not support ${route}.`;

    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-clip-type',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        clipType,
        renderRoute: route,
        blockerReason: reason,
        provenance: record.provenance,
      },
    });
    pushClipTypeFindingAndBlocker(findings, blockers, {
      id: `export.clipType.${clip.id}.${clipType}.${route}.${reason}`,
      reason,
      message,
      clipId: clip.id,
      clipType,
      route,
      record,
    });
  }
}

function firstClipTypeRouteBlockerReason(record: ClipTypeRegistryRecord, route: RenderRoute): RenderBlockerReason | undefined {
  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
}

function pushClipTypeFindingAndBlocker(
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  input: {
    id: string;
    reason: RenderBlockerReason;
    message: string;
    clipId: string;
    clipType: string;
    route: RenderRoute;
    record?: ClipTypeRegistryRecord;
  },
): void {
  const detail: Record<string, unknown> = {
    clipType: input.clipType,
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
