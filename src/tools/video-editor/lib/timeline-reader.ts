/**
 * TimelineReader — stable, read-only projection of timeline state.
 *
 * Exposes TimelineSnapshot summaries while hiding raw row/meta/registry
 * internals.  Extensions and proposal machinery consume this reader
 * instead of raw TimelineData, useTimelineCommit, or store internals.
 *
 * @publicContract
 */

import type {
  TimelineReader,
  TimelineSnapshot,
  TimelineClipSummary,
  TimelineTrackSummary,
  TimelineEffectSummary,
  TimelineTransitionSummary,
  TimelineLiveBindingSummary,
  TimelineAutomationSummary,
  TimelineMaterialRefSummary,
  TimelineSourceRefSummary,
  TimelineShaderSummary,
  TimelineRenderGroupSummary,
  TimelineOutputMetadata,
  ProjectExtensionRequirement,
  GeneratedObjectMeta,
  SourceMapEntry,
} from '@/sdk/index';

import { getCapabilityRequirements as sdkGetCapabilityRequirements } from '@/sdk/index';

import type { TimelineData, ClipMeta } from '@/tools/video-editor/lib/timeline-data';
import type {
  TimelineClip,
  TimelineClipShaderMetadata,
  TimelineShaderKeyframe,
  TimelinePostprocessShaderMetadata,
  TimelineLiveBindingResolutionStatus,
  TimelineLiveSourceKind,
  TimelineLiveSourceStatus,
} from '@/tools/video-editor/types/index';
import {
  scanTimelineLiveBindings,
  scanTimelineLiveUniformBindings,
  type TimelineLiveBindingRecord,
  type TimelineLiveUniformBindingRecord,
} from '@/tools/video-editor/lib/timeline-domain.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Determine whether an effect or transition object is managed by a
 * registered extension.  Mirrors {@link deriveManaged} for clips but
 * works on plain effect/transition records (which carry `app`,
 * `managedBy`, or `extensionId` keys).
 */
function deriveEffectManaged(
  obj: Record<string, unknown>,
  extensionIds: ReadonlySet<string>,
): { managed: boolean; managedBy?: string } {
  // Explicit managedBy key.
  if (
    typeof obj.managedBy === 'string' &&
    obj.managedBy.length > 0
  ) {
    return { managed: true, managedBy: obj.managedBy };
  }

  // Extension ID directly in the record.
  if (
    typeof obj.extensionId === 'string' &&
    extensionIds.has(obj.extensionId)
  ) {
    return { managed: true, managedBy: obj.extensionId };
  }

  // Check app sub-object.
  const app = obj.app;
  if (app && typeof app === 'object' && !Array.isArray(app)) {
    const appObj = app as Record<string, unknown>;
    if (
      typeof appObj.managedBy === 'string' &&
      appObj.managedBy.length > 0
    ) {
      return { managed: true, managedBy: appObj.managedBy };
    }
    for (const key of Object.keys(appObj)) {
      if (extensionIds.has(key)) {
        return { managed: true, managedBy: key };
      }
    }
  }

  return { managed: false };
}

/**
 * Compute clip duration in seconds from meta.
 * Mirrors the hold-vs-speed logic in timeline-data.ts.
 */
function computeClipDuration(meta: ClipMeta): number {
  if (typeof meta.hold === 'number') {
    return meta.hold;
  }
  const from = meta.from ?? 0;
  const to = meta.to ?? 0;
  const speed = meta.speed ?? 1;
  return to > from ? (to - from) / speed : 0;
}

/**
 * Determine whether a clip is managed by a registered extension.
 *
 * In M3 a clip is "managed" when its `app` record carries an
 * extension namespace (e.g. `app?.managedBy`), or when a
 * `source_uuid` / `generation` provenance link exists.
 */
function deriveManaged(
  clip: TimelineClip,
  extensionIds: ReadonlySet<string>,
): { managed: boolean; managedBy?: string } {
  // Explicit managedBy key in clip app data.
  if (clip.app && typeof clip.app.managedBy === 'string' && clip.app.managedBy.length > 0) {
    return { managed: true, managedBy: clip.app.managedBy };
  }

  // If the clip has an app key that matches a known extension ID,
  // treat it as managed.
  if (clip.app) {
    for (const key of Object.keys(clip.app)) {
      if (extensionIds.has(key)) {
        return { managed: true, managedBy: key };
      }
    }
  }

  // source_uuid linking to an extension.
  if (clip.source_uuid && extensionIds.has(clip.source_uuid)) {
    return { managed: true, managedBy: clip.source_uuid };
  }

  return { managed: false };
}

/**
 * Well-known key under which GeneratedObjectMeta is stored
 * in clip / track / asset app data.
 */
const GENERATED_META_KEY = '__generated__';

/**
 * Extract GeneratedObjectMeta from an object's app record if present.
 * The app record may carry arbitrary extension data; we only extract
 * the well-known `__generated__` key.
 */
function extractGeneratedMeta(
  app: Record<string, unknown> | undefined,
): GeneratedObjectMeta | undefined {
  if (!app) return undefined;
  const raw = app[GENERATED_META_KEY];
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return undefined;
  const g = raw as Record<string, unknown>;
  if (typeof g.extensionId !== 'string') return undefined;
  const meta: GeneratedObjectMeta = {
    extensionId: g.extensionId,
  };
  if (typeof g.contributionId === 'string') meta.contributionId = g.contributionId;
  if (g.provenance !== undefined && typeof g.provenance === 'object' && !Array.isArray(g.provenance)) {
    meta.provenance = g.provenance as Record<string, unknown>;
  }
  if (typeof g.generatedAt === 'number') meta.generatedAt = g.generatedAt;
  if (typeof g.sourceMapEntryId === 'string') meta.sourceMapEntryId = g.sourceMapEntryId;
  return meta;
}

function getStringField(
  value: Record<string, unknown> | undefined,
  keys: readonly string[],
): string | undefined {
  if (!value) return undefined;
  for (const key of keys) {
    const field = value[key];
    if (typeof field === 'string' && field.length > 0) return field;
  }
  return undefined;
}

function collectLiveBindingRecords(data: TimelineData): TimelineLiveBindingRecord[] {
  const records = [...scanTimelineLiveBindings(data.config).bindings];
  const seen = new Set(records.map((record) => `${record.clipId}:${record.binding.bindingId}`));

  for (const clip of data.config.clips) {
    const appLiveBindings = clip.app?.liveBindings;
    if (!Array.isArray(appLiveBindings)) continue;

    for (const rawBinding of appLiveBindings) {
      if (!rawBinding || typeof rawBinding !== 'object' || Array.isArray(rawBinding)) {
        continue;
      }
      const binding = rawBinding as Record<string, unknown>;
      if (typeof binding.bindingId !== 'string' || binding.bindingId.length === 0) {
        continue;
      }
      const key = `${clip.id}:${binding.bindingId}`;
      if (seen.has(key)) continue;

      seen.add(key);
      records.push({
        binding: {
          bindingId: binding.bindingId,
          sourceId: typeof binding.sourceId === 'string' ? binding.sourceId : '',
          sourceKind: (typeof binding.sourceKind === 'string'
            ? binding.sourceKind
            : 'custom') as TimelineLiveSourceKind,
          ...(typeof binding.channelId === 'string' ? { channelId: binding.channelId } : {}),
          ...(typeof binding.targetParamName === 'string'
            ? { targetParamName: binding.targetParamName }
            : {}),
          ...(typeof binding.targetEffectId === 'string'
            ? { targetEffectId: binding.targetEffectId }
            : {}),
          ...(typeof binding.targetPath === 'string'
            ? { targetPath: binding.targetPath }
            : {}),
          ...(typeof binding.ownerExtensionId === 'string'
            ? { ownerExtensionId: binding.ownerExtensionId }
            : {}),
          ...(typeof binding.sourceStatus === 'string'
            ? { sourceStatus: binding.sourceStatus as TimelineLiveSourceStatus }
            : {}),
          ...(typeof binding.resolutionStatus === 'string'
            ? {
                resolutionStatus:
                  binding.resolutionStatus as TimelineLiveBindingResolutionStatus,
              }
            : {}),
        },
        clipId: clip.id,
        path: `clips.${clip.id}.app.liveBindings`,
        status:
          typeof binding.resolutionStatus === 'string'
            ? (binding.resolutionStatus as TimelineLiveBindingResolutionStatus)
            : 'active',
        diagnostics: Object.freeze([]),
        blocksExport: binding.resolutionStatus !== 'resolved',
      });
    }
  }

  return records;
}

function collectLiveUniformBindingRecords(data: TimelineData): TimelineLiveUniformBindingRecord[] {
  const records = [...scanTimelineLiveUniformBindings(data.config).bindings];
  const seen = new Set(records.map((record) => `${record.clipId}:${record.binding.bindingId}`));

  for (const clip of data.config.clips) {
    const appLiveUniformBindings = clip.app?.liveUniformBindings;
    if (!Array.isArray(appLiveUniformBindings)) continue;

    for (const rawBinding of appLiveUniformBindings) {
      if (!rawBinding || typeof rawBinding !== 'object' || Array.isArray(rawBinding)) {
        continue;
      }
      const binding = rawBinding as Record<string, unknown>;
      if (typeof binding.bindingId !== 'string' || binding.bindingId.length === 0) {
        continue;
      }
      const key = `${clip.id}:${binding.bindingId}`;
      if (seen.has(key)) continue;

      const mapping = binding.mapping;
      if (!mapping || typeof mapping !== 'object' || Array.isArray(mapping)) {
        continue;
      }

      const uniform = (mapping as Record<string, unknown>).uniform;
      if (typeof uniform !== 'string' || uniform.length === 0) {
        continue;
      }

      seen.add(key);
      records.push({
        binding: {
          bindingId: binding.bindingId,
          sourceId: typeof binding.sourceId === 'string' ? binding.sourceId : '',
          sourceKind: (typeof binding.sourceKind === 'string'
            ? binding.sourceKind
            : 'custom') as TimelineLiveSourceKind,
          ...(typeof binding.channelId === 'string' ? { channelId: binding.channelId } : {}),
          ...(typeof binding.targetMaterialId === 'string'
            ? { targetMaterialId: binding.targetMaterialId }
            : {}),
          ...(typeof binding.targetParamName === 'string'
            ? { targetParamName: binding.targetParamName }
            : {}),
          ...(typeof binding.targetPath === 'string'
            ? { targetPath: binding.targetPath }
            : {}),
          mapping: {
            ...(mapping as Record<string, unknown>),
            uniform,
          } as TimelineLiveUniformBindingRecord['binding']['mapping'],
        },
        clipId: clip.id,
        path: `clips.${clip.id}.app.liveUniformBindings`,
        diagnostics: Object.freeze([]),
      });
    }
  }

  return records;
}

function isClipShaderMetadata(value: unknown): value is TimelineClipShaderMetadata {
  return Boolean(
    value
    && typeof value === 'object'
    && !Array.isArray(value)
    && (value as Record<string, unknown>).scope === 'clip'
    && typeof (value as Record<string, unknown>).shaderId === 'string'
    && typeof (value as Record<string, unknown>).extensionId === 'string'
    && typeof (value as Record<string, unknown>).contributionId === 'string',
  );
}

function isPostprocessShaderMetadata(value: unknown): value is TimelinePostprocessShaderMetadata {
  return Boolean(
    value
    && typeof value === 'object'
    && !Array.isArray(value)
    && (value as Record<string, unknown>).scope === 'postprocess'
    && typeof (value as Record<string, unknown>).shaderId === 'string'
    && typeof (value as Record<string, unknown>).extensionId === 'string'
    && typeof (value as Record<string, unknown>).contributionId === 'string',
  );
}

function canonicalizeShaderUniformPath(parameterPath: string): string | undefined {
  const trimmed = parameterPath.trim();
  if (trimmed.length === 0) {
    return undefined;
  }

  const uniform = trimmed.startsWith('uniforms.') ? trimmed.slice('uniforms.'.length) : trimmed;
  return uniform.length > 0 ? `uniforms.${uniform}` : undefined;
}

function isShaderKeyframeValue(value: unknown): value is TimelineShaderKeyframe['value'] {
  if (
    typeof value === 'number'
    || typeof value === 'string'
    || typeof value === 'boolean'
  ) {
    return true;
  }

  return Array.isArray(value) && value.every((entry) => typeof entry === 'number' && Number.isFinite(entry));
}

function extractShaderKeyframes(
  rawKeyframes: TimelineClipShaderMetadata['keyframes'] | TimelinePostprocessShaderMetadata['keyframes'],
): TimelineShaderSummary['keyframes'] | undefined {
  if (!rawKeyframes || typeof rawKeyframes !== 'object' || Array.isArray(rawKeyframes)) {
    return undefined;
  }

  const canonical: Record<string, TimelineShaderKeyframe[]> = {};
  for (const [parameterPath, entries] of Object.entries(rawKeyframes)) {
    const targetPath = canonicalizeShaderUniformPath(parameterPath);
    if (!targetPath || !Array.isArray(entries)) {
      continue;
    }

    const keyframes = entries.flatMap((entry) => {
      if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
        return [];
      }

      const time = (entry as { time?: unknown }).time;
      const value = (entry as { value?: unknown }).value;
      const interpolation = (entry as { interpolation?: unknown }).interpolation;
      if (
        typeof time !== 'number'
        || !Number.isFinite(time)
        || !isShaderKeyframeValue(value)
        || (interpolation !== 'linear' && interpolation !== 'hold')
      ) {
        return [];
      }

      return [{
        time,
        value: Array.isArray(value) ? [...value] : value,
        interpolation,
      }];
    });

    if (keyframes.length > 0) {
      canonical[targetPath] = keyframes;
    }
  }

  return Object.keys(canonical).length > 0 ? canonical : undefined;
}

function extractAutomationSummary(
  rawParams: Record<string, unknown> | undefined,
): TimelineAutomationSummary | undefined {
  if (!rawParams) return undefined;

  const target = rawParams.target;
  if (!target || typeof target !== 'object' || Array.isArray(target)) {
    return undefined;
  }

  const targetObj = target as Record<string, unknown>;
  if (
    typeof targetObj.contributionId !== 'string'
    || targetObj.contributionId.length === 0
    || typeof targetObj.parameterPath !== 'string'
    || targetObj.parameterPath.length === 0
  ) {
    return undefined;
  }

  const keyframes = rawParams.keyframes;
  if (!Array.isArray(keyframes)) {
    return undefined;
  }

  const enabled = rawParams.enabled;
  if (enabled !== undefined && typeof enabled !== 'boolean') {
    return undefined;
  }

  return {
    contributionId: targetObj.contributionId,
    parameterPath: targetObj.parameterPath,
    ...(typeof targetObj.targetPath === 'string' && targetObj.targetPath.length > 0
      ? { targetPath: targetObj.targetPath }
      : {}),
    keyframeCount: keyframes.length,
    enabled: enabled !== false,
  };
}

// ---------------------------------------------------------------------------
// createTimelineReader
// ---------------------------------------------------------------------------

export interface TimelineReaderOptions {
  /**
   * The current timeline data to project.
   * Can be a static snapshot or a getter that returns the latest state.
   */
  data: TimelineData | (() => TimelineData);

  /**
   * Project identifier, when available from the host / provider.
   */
  projectId?: string | null;

  /**
   * Extension requirements for this project.
   * Extracted from project metadata (e.g. TimelineConfig.app or a
   * project-level manifest).
   */
  extensionRequirements?: readonly ProjectExtensionRequirement[];
}

/**
 * Create a TimelineReader from TimelineData and optional project metadata.
 *
 * The reader hides raw row/meta/registry internals and only exposes
 * stable TimelineSnapshot projections suitable for extension and
 * proposal code.
 */
export function createTimelineReader(
  options: TimelineReaderOptions,
): TimelineReader {
  const getData: () => TimelineData =
    typeof options.data === 'function' ? options.data : () => options.data;

  const projectId = options.projectId ?? null;
  const extensionRequirements: readonly ProjectExtensionRequirement[] =
    options.extensionRequirements ?? [];

  // Pre-compute the set of known extension IDs for managed-by detection.
  const knownExtensionIds: ReadonlySet<string> = new Set(
    extensionRequirements.map((r) => r.extensionId),
  );

  return {
    snapshot(): TimelineSnapshot {
      const data = getData();
      const { config, configVersion, registry, meta: metaMap } = data;

      // ── Clips ──────────────────────────────────────────────────────
      const clipSummaries: TimelineClipSummary[] = [];
      const effectSummaries: TimelineEffectSummary[] = [];
      const transitionSummaries: TimelineTransitionSummary[] = [];
      const liveBindingSummaries: TimelineLiveBindingSummary[] = [];
      const automationSummaries: TimelineAutomationSummary[] = [];
      const materialRefSummaries: TimelineMaterialRefSummary[] = [];
      const sourceRefSummaries: TimelineSourceRefSummary[] = [];
      const shaderSummaries: TimelineShaderSummary[] = [];
      const liveBindingsByClip = new Map<string, TimelineLiveBindingRecord[]>();
      const liveUniformBindingsByClip = new Map<string, TimelineLiveUniformBindingRecord[]>();

      for (const record of collectLiveBindingRecords(data)) {
        const records = liveBindingsByClip.get(record.clipId) ?? [];
        records.push(record);
        liveBindingsByClip.set(record.clipId, records);
      }

      for (const record of collectLiveUniformBindingRecords(data)) {
        const records = liveUniformBindingsByClip.get(record.clipId) ?? [];
        records.push(record);
        liveUniformBindingsByClip.set(record.clipId, records);
      }

      for (const clip of config.clips) {
        const clipMeta = metaMap[clip.id];
        if (!clipMeta) continue;

        const { managed, managedBy } = deriveManaged(clip, knownExtensionIds);

        const generatedMeta: GeneratedObjectMeta | undefined =
          extractGeneratedMeta(clip.app);

        // Legacy shader storage is read here only to project snapshot.shaders;
        // planner/export readiness must use CompositionGraph authority.
        const clipShader = isClipShaderMetadata(clip.app?.shader)
          ? clip.app.shader
          : undefined;
        if (clipShader) {
          const clipShaderKeyframes = extractShaderKeyframes(clipShader.keyframes);
          shaderSummaries.push({
            id: `${clip.id}:shader:${clipShader.shaderId}`,
            shaderId: clipShader.shaderId,
            scope: 'clip',
            clipId: clip.id,
            extensionId: clipShader.extensionId,
            contributionId: clipShader.contributionId,
            enabled: clipShader.enabled !== false,
            ...(clipShaderKeyframes
              ? { keyframes: clipShaderKeyframes }
              : {}),
          });
        }

        // ── Extract effects ──────────────────────────────────────────
        const clipEffects: TimelineEffectSummary[] = [];
        const rawEffects = clipMeta.effects ?? clip.effects;
        if (rawEffects) {
          if (Array.isArray(rawEffects)) {
            for (let ei = 0; ei < rawEffects.length; ei += 1) {
              const eff = rawEffects[ei];
              if (!eff || typeof eff !== 'object') continue;
              const effectObj = eff as Record<string, unknown>;
              const effectType =
                typeof effectObj.type === 'string'
                  ? effectObj.type
                  : typeof effectObj.effectId === 'string'
                    ? effectObj.effectId
                    : undefined;
              const effectId = `${clip.id}.effect.${effectType ?? `unnamed.${ei}`}`;
              const effectManaged = deriveEffectManaged(
                effectObj,
                knownExtensionIds,
              );
              clipEffects.push({
                id: effectId,
                clipId: clip.id,
                effectType,
                params:
                  effectObj.params !== undefined &&
                  typeof effectObj.params === 'object' &&
                  !Array.isArray(effectObj.params)
                    ? (effectObj.params as Record<string, unknown>)
                    : undefined,
                ...(effectManaged.managed
                  ? { managed: true, managedBy: effectManaged.managedBy }
                  : {}),
              });
              effectSummaries.push(clipEffects[clipEffects.length - 1]);
            }
          } else if (typeof rawEffects === 'object') {
            // Record<string, number> — effect names to intensity
            for (const [effectName, intensity] of Object.entries(
              rawEffects as Record<string, unknown>,
            )) {
              if (typeof intensity !== 'number') continue;
              const effectId = `${clip.id}.effect.${effectName}`;
              const effectEntry: TimelineEffectSummary = {
                id: effectId,
                clipId: clip.id,
                effectType: effectName,
                params: { intensity },
              };
              clipEffects.push(effectEntry);
              effectSummaries.push(effectEntry);
            }
          }
        }

        // ── Extract transition ───────────────────────────────────────
        let clipTransition: TimelineTransitionSummary | undefined;
        const rawTransition = clipMeta.transition ?? clip.transition;
        if (rawTransition && typeof rawTransition === 'object') {
          const tObj = rawTransition as Record<string, unknown>;
          const transitionType =
            typeof tObj.type === 'string' ? tObj.type : undefined;
          const transitionDuration =
            typeof tObj.duration === 'number'
              ? tObj.duration
              : 0;
          const transitionManaged = deriveEffectManaged(
            tObj,
            knownExtensionIds,
          );
          clipTransition = {
            id: `${clip.id}.transition.${transitionType ?? 'unknown'}`,
            clipId: clip.id,
            transitionType,
            duration: transitionDuration,
            params:
              tObj.params !== undefined &&
              typeof tObj.params === 'object' &&
              !Array.isArray(tObj.params)
                ? (tObj.params as Record<string, unknown>)
                : undefined,
            ...(transitionManaged.managed
              ? { managed: true, managedBy: transitionManaged.managedBy }
              : {}),
          };
          transitionSummaries.push(clipTransition);
        }

        // ── Extract live bindings ────────────────────────────────────
        const clipLiveBindings: TimelineLiveBindingSummary[] = [];
        for (const record of liveBindingsByClip.get(clip.id) ?? []) {
          const binding: TimelineLiveBindingSummary = {
            bindingId: record.binding.bindingId,
            clipId: clip.id,
            sourceId: record.binding.sourceId,
            sourceKind: record.binding.sourceKind,
            ...(record.binding.targetEffectId !== undefined
              ? { targetEffectId: record.binding.targetEffectId }
              : {}),
            ...(record.binding.targetPath !== undefined
              ? { targetPath: record.binding.targetPath }
              : {}),
            ...(record.binding.ownerExtensionId !== undefined
              ? { ownerExtensionId: record.binding.ownerExtensionId }
              : {}),
            ...(record.binding.targetEffectId !== undefined
              ? { targetKind: 'effect-param' as const }
              : record.binding.targetParamName !== undefined || record.binding.targetPath !== undefined
                ? { targetKind: 'clip-param' as const }
                : {}),
            ...(record.binding.targetParamName !== undefined
              ? { targetParamName: record.binding.targetParamName }
              : {}),
            status: record.status,
          };
          clipLiveBindings.push(binding);
          liveBindingSummaries.push(binding);
        }

        for (const record of liveUniformBindingsByClip.get(clip.id) ?? []) {
          const targetPath =
            typeof record.binding.targetPath === 'string' && record.binding.targetPath.length > 0
              ? record.binding.targetPath
              : `uniforms.${record.binding.mapping.uniform}`;
          const binding: TimelineLiveBindingSummary = {
            bindingId: record.binding.bindingId,
            clipId: clip.id,
            sourceId: record.binding.sourceId,
            sourceKind: record.binding.sourceKind,
            targetKind: 'shader-uniform',
            ...(record.binding.targetMaterialId !== undefined
              ? { targetMaterialId: record.binding.targetMaterialId }
              : {}),
            targetParamName: record.binding.mapping.uniform,
            targetPath,
            status: 'resolved',
          };
          clipLiveBindings.push(binding);
          liveBindingSummaries.push(binding);
        }

        // ── Extract automation summary ───────────────────────────────
        const clipAutomationSummaries: TimelineAutomationSummary[] = [];
        if (clip.clipType === 'automation') {
          const automation = extractAutomationSummary(
            (clipMeta.params ?? clip.params) as Record<string, unknown> | undefined,
          );
          if (automation) {
            clipAutomationSummaries.push(automation);
            automationSummaries.push(automation);
          }
        }

        // ── Extract material refs ────────────────────────────────────
        const clipMaterialRefs: TimelineMaterialRefSummary[] = [];
        if (clipMeta.asset) {
          clipMaterialRefs.push({
            id: `material.asset.${clipMeta.asset}.${clip.id}`,
            clipId: clip.id,
            assetKey: clipMeta.asset,
            mediaKind: 'unknown',
            determinism: 'deterministic',
          });
          materialRefSummaries.push(clipMaterialRefs[0]);
        }
        // Check for generation material refs
        if (clipMeta.generation) {
          clipMaterialRefs.push({
            id: `material.generation.${clip.id}`,
            clipId: clip.id,
            mediaKind: 'unknown',
            determinism: 'process-dependent',
          });
          materialRefSummaries.push(clipMaterialRefs[clipMaterialRefs.length - 1]);
        }

        // ── Extract source refs ──────────────────────────────────────
        const clipSourceRefs: TimelineSourceRefSummary[] = [];
        if (clipMeta.source_uuid) {
          const sourceRef: TimelineSourceRefSummary = {
            id: `source.${clipMeta.source_uuid}.${clip.id}`,
            clipId: clip.id,
            sourceKind: knownExtensionIds.has(clipMeta.source_uuid)
              ? 'extension'
              : 'unknown',
            sourceUuid: clipMeta.source_uuid,
            ...(knownExtensionIds.has(clipMeta.source_uuid)
              ? { extensionId: clipMeta.source_uuid }
              : {}),
            determinism: knownExtensionIds.has(clipMeta.source_uuid)
              ? 'preview-only'
              : 'unknown',
          };
          clipSourceRefs.push(sourceRef);
          sourceRefSummaries.push(sourceRef);
        }
        if (clipMeta.generation) {
          const generation = clipMeta.generation as Record<string, unknown>;
          const generationId = getStringField(generation, ['id', 'generationId', 'uuid']);
          const extensionId = getStringField(generation, ['extensionId', 'providerId']);
          const sourceRef: TimelineSourceRefSummary = {
            id: `source.generation.${generationId ?? clip.id}`,
            clipId: clip.id,
            sourceKind: extensionId ? 'extension' : 'generation',
            ...(generationId ? { generationId } : {}),
            ...(extensionId ? { extensionId } : {}),
            determinism: 'process-dependent',
          };
          clipSourceRefs.push(sourceRef);
          sourceRefSummaries.push(sourceRef);
        }

        clipSummaries.push({
          id: clip.id,
          track: clip.track,
          at: clip.at,
          clipType: clip.clipType,
          duration: computeClipDuration(clipMeta),
          managed,
          ...(managedBy !== undefined ? { managedBy } : {}),
          ...(generatedMeta !== undefined ? { generatedMeta } : {}),
          ...(clipEffects.length > 0 ? { effects: clipEffects } : {}),
          ...(clipTransition !== undefined ? { transition: clipTransition } : {}),
          ...(clipLiveBindings.length > 0
            ? { liveBindings: clipLiveBindings }
            : {}),
          ...(clipAutomationSummaries.length > 0
            ? { automation: clipAutomationSummaries }
            : {}),
          ...(clipMaterialRefs.length > 0
            ? { materialRefs: clipMaterialRefs }
            : {}),
          ...(clipSourceRefs.length > 0
            ? { sourceRefs: clipSourceRefs }
            : {}),
        });
      }

      // ── Tracks ─────────────────────────────────────────────────────
      const trackSummaries: TimelineTrackSummary[] = (config.tracks ?? []).map(
        (track) => {
          const trackGeneratedMeta: GeneratedObjectMeta | undefined =
            extractGeneratedMeta(track.app);
          return {
            id: track.id,
            kind: track.kind,
            label: track.label,
            muted: track.muted ?? false,
            ...(track.app !== undefined ? { app: track.app } : {}),
            ...(trackGeneratedMeta !== undefined ? { generatedMeta: trackGeneratedMeta } : {}),
          };
        },
      );

      // ── Asset keys ─────────────────────────────────────────────────
      const assetKeys: string[] = Object.keys(registry.assets ?? {});

      // ── App data ───────────────────────────────────────────────────
      const app: Record<string, unknown> = config.app !== undefined
        ? { ...config.app }
        : {};
      // Legacy shader storage is read here only to project snapshot.shaders;
      // planner/export readiness must use CompositionGraph authority.
      const postprocessShader = isPostprocessShaderMetadata(app.shaderPostprocess)
        ? app.shaderPostprocess
        : undefined;
      if (postprocessShader) {
        const postprocessShaderKeyframes = extractShaderKeyframes(postprocessShader.keyframes);
        shaderSummaries.push({
          id: `postprocess:shader:${postprocessShader.shaderId}`,
          shaderId: postprocessShader.shaderId,
          scope: 'postprocess',
          extensionId: postprocessShader.extensionId,
          contributionId: postprocessShader.contributionId,
          enabled: postprocessShader.enabled !== false,
          ...(postprocessShaderKeyframes
            ? { keyframes: postprocessShaderKeyframes }
            : {}),
        });
      }

      // ── Source-map entries ─────────────────────────────────────────
      const sourceMapEntries: SourceMapEntry[] = [];
      for (const [, extData] of Object.entries(app)) {
        if (!extData || typeof extData !== 'object' || Array.isArray(extData)) continue;
        const extObj = extData as Record<string, unknown>;
        for (const [key, value] of Object.entries(extObj)) {
          if (!key.startsWith('__sm__:') || !value || typeof value !== 'object') continue;
          const entry = value as Record<string, unknown>;
          if (typeof entry.id !== 'string' || typeof entry.source !== 'string') continue;
          sourceMapEntries.push({
            id: entry.id as string,
            source: entry.source as string,
            targetId: entry.targetId as string,
            targetGranularity: entry.targetGranularity as SourceMapEntry['targetGranularity'],
            sourceUri: entry.sourceUri as string,
            sourceStartLine: typeof entry.sourceStartLine === 'number' ? entry.sourceStartLine : 0,
            sourceStartColumn: typeof entry.sourceStartColumn === 'number' ? entry.sourceStartColumn : 0,
            sourceEndLine: typeof entry.sourceEndLine === 'number' ? entry.sourceEndLine : 0,
            sourceEndColumn: typeof entry.sourceEndColumn === 'number' ? entry.sourceEndColumn : 0,
            stale: entry.stale === true,
            ...(entry.meta !== undefined && typeof entry.meta === 'object' ? { meta: entry.meta as Record<string, unknown> } : {}),
          });
        }
      }

      // ── Render groups ─────────────────────────────────────────────
      const renderGroups: TimelineRenderGroupSummary[] = [];
      const pinnedGroups = config.pinnedShotGroups;
      if (pinnedGroups && Array.isArray(pinnedGroups)) {
        for (const group of pinnedGroups) {
          if (!group || typeof group !== 'object') continue;
          const clipIds: string[] = [];
          if (Array.isArray(group.clipIds)) {
            for (const cid of group.clipIds) {
              if (typeof cid === 'string') clipIds.push(cid);
            }
          }
          if (clipIds.length > 0) {
            renderGroups.push({
              id: `${group.shotId}:${group.trackId}`,
              clipIds,
              groupType: group.mode ?? 'pinned-shot-group',
            });
          }
        }
      }

      // ── Output metadata ───────────────────────────────────────────
      const output: TimelineOutputMetadata | undefined = config.output
        ? {
            resolution: config.output.resolution,
            fps: config.output.fps,
            file: config.output.file,
            background: config.output.background ?? null,
            backgroundScale: config.output.background_scale ?? null,
          }
        : undefined;

      return {
        projectId,
        baseVersion: configVersion,
        currentVersion: configVersion,
        extensionRequirements,
        clips: clipSummaries,
        tracks: trackSummaries,
        assetKeys,
        app,
        sourceMapEntries:
          sourceMapEntries.length > 0 ? sourceMapEntries : undefined,
        effects:
          effectSummaries.length > 0 ? effectSummaries : undefined,
        transitions:
          transitionSummaries.length > 0 ? transitionSummaries : undefined,
        liveBindings:
          liveBindingSummaries.length > 0 ? liveBindingSummaries : undefined,
        automations:
          automationSummaries.length > 0 ? automationSummaries : undefined,
        materialRefs:
          materialRefSummaries.length > 0 ? materialRefSummaries : undefined,
        sourceRefs:
          sourceRefSummaries.length > 0 ? sourceRefSummaries : undefined,
        shaders:
          shaderSummaries.length > 0 ? shaderSummaries : undefined,
        renderGroups:
          renderGroups.length > 0 ? renderGroups : undefined,
        outputMetadata: output,
      };
    },
  };
}

// ---------------------------------------------------------------------------
// Re-export getCapabilityRequirements from timeline-reader for planner
// convenience.  The canonical implementation lives in @/sdk/index.ts so it
// stays provider-free.
// ---------------------------------------------------------------------------
export { sdkGetCapabilityRequirements as getCapabilityRequirements };
