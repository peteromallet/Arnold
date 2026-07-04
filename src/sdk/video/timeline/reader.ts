/**
 * TimelineReader — portable read-only timeline projection contracts.
 *
 * Exports TimelineSnapshot, lightweight summaries, TimelineReader, and
 * TimelineProposalInput.  All contracts are data-only; there are no
 * provider, runtime, mutation, or hook dependencies here.
 *
 * Host code (timeline-reader.ts, proposal-runtime.ts, useTimelineOps.ts)
 * imports these contracts and supplies the runtime behaviour.
 *
 * @publicContract
 */

import type { DeterminismStatus } from '@/sdk/video/rendering/renderability';
import type { ShaderMaterializerRequirementScope } from '@/sdk/video/rendering/capabilities';
import type { TimelinePatch } from './patch';
import type { ProjectExtensionRequirement } from '@/sdk/projectRequirements';
import type { SourceMapEntry, GeneratedObjectMeta } from './sourceMap';

// ---------------------------------------------------------------------------
// M12: Planner inspection contracts — effect, transition, live-binding,
// material-ref, source-ref, render-group, and output-metadata summaries
// ---------------------------------------------------------------------------

/**
 * M12: Lightweight effect summary extracted from a clip for planner inspection.
 *
 * Describes an effect applied to a clip without importing provider
 * stores or raw timeline rows.
 */
export interface TimelineEffectSummary {
  /** Unique identifier for this effect instance (e.g. `${clipId}.effect.${effectType}`). */
  id: string;
  /** The clip this effect belongs to. */
  clipId: string;
  /** The effect type identifier (e.g. 'fade_in', 'blur'). */
  effectType?: string;
  /** Effect parameters, when available. */
  params?: Record<string, unknown>;
  /** Whether this effect is managed by a registered extension. */
  managed?: boolean;
  /** Extension ID that manages this effect, if managed. */
  managedBy?: string;
}

/**
 * M12: Lightweight transition summary extracted from a clip for planner inspection.
 *
 * Describes a transition applied to a clip without importing provider
 * stores or raw timeline rows.
 */
export interface TimelineTransitionSummary {
  /** Unique identifier for this transition (e.g. `${clipId}.transition.${transitionType}`). */
  id: string;
  /** The clip this transition belongs to. */
  clipId: string;
  /** The transition type identifier (e.g. 'dissolve', 'wipe'). */
  transitionType?: string;
  /** Transition duration in seconds. */
  duration: number;
  /** Transition parameters, when available. */
  params?: Record<string, unknown>;
  /** Whether this transition is managed by a registered extension. */
  managed?: boolean;
  /** Extension ID that manages this transition, if managed. */
  managedBy?: string;
}

/**
 * M12: Lightweight live-binding summary extracted from clip metadata
 * for planner inspection.
 *
 * Live bindings connect a clip parameter to a live data source.
 * The planner uses these to detect live-unbaked or process-dependent
 * requirements.
 */
export interface TimelineLiveBindingSummary {
  /** Unique binding identifier. */
  bindingId: string;
  /** The clip this binding belongs to. */
  clipId: string;
  /** Source identifier for the live data source. */
  sourceId: string;
  /** Kind of live source (e.g. 'webcam', 'generated-frame', 'midi'). */
  sourceKind: string;
  /** Target kind for the resolved binding target, when known. */
  targetKind?: 'clip-param' | 'effect-param' | 'shader-uniform';
  /** Target parameter name on the clip, effect, or shader, when applicable. */
  targetParamName?: string;
  /** Effect contribution or instance identifier, when the binding targets an effect param. */
  targetEffectId?: string;
  /** Shader contribution identifier, when the binding targets a shader uniform. */
  targetMaterialId?: string;
  /** Canonical target-path detail, when available. */
  targetPath?: string;
  /** Owning extension ID when persisted alongside the binding metadata. */
  ownerExtensionId?: string;
  /** Resolution status of the binding, when known. */
  status?: string;
}

/**
 * M2: Lightweight automation summary extracted from automation clips for
 * planner and graph inspection.
 */
export interface TimelineAutomationSummary {
  /** Contribution ID referenced by the automation target. */
  contributionId: string;
  /** Legacy parameter path stored on the automation clip target. */
  parameterPath: string;
  /** Optional canonical target-path detail when persisted explicitly. */
  targetPath?: string;
  /** Number of keyframes carried by the automation clip. */
  keyframeCount: number;
  /** Whether the automation clip is enabled. */
  enabled: boolean;
}

/** M4: JSON-serializable shader-uniform keyframe values carried in summaries. */
export type TimelineShaderKeyframeValue =
  | number
  | string
  | boolean
  | readonly number[];

/** M4: A single shader-uniform keyframe using the existing M3b fields. */
export interface TimelineShaderKeyframe {
  /** Time in seconds. */
  time: number;
  /** JSON-serializable uniform value. */
  value: TimelineShaderKeyframeValue;
  /** Interpolation mode from this keyframe to the next. */
  interpolation: 'linear' | 'hold';
}

/**
 * M12: Lightweight material-ref summary extracted from clip data
 * for planner inspection.
 *
 * Material refs point at assets or generated materials consumed by a clip.
 */
export interface TimelineMaterialRefSummary {
  /** Unique identifier for this material ref. */
  id: string;
  /** The clip that consumes this material. */
  clipId: string;
  /** Asset key in the timeline registry, when the material is an asset. */
  assetKey?: string;
  /** Media kind of the referenced material. */
  mediaKind?: string;
  /** Determinism posture for this material ref. */
  determinism?: DeterminismStatus;
  /** Render group this material contributes to, when part of a multi-pass group. */
  renderGroupId?: string;
  /** Pass name this material contributes, when known. */
  passName?: string;
  /** Whether this material can be composited into a render group. */
  composable?: boolean;
}

/** M12: Render pass descriptor used by multi-pass render groups. */
export interface TimelineRenderPassSummary {
  /** Stable pass identifier within a render group. */
  id: string;
  /** Human-readable or process-declared pass name. */
  passName: string;
  /** Whether the group is blocked when this pass is missing or stale. */
  required: boolean;
  /** Whether this pass is composable into the final render group. */
  composable: boolean;
  /** Material ref currently satisfying this pass, if resolved. */
  materialRefId?: string;
  /** Current pass status from the planner/material registry projection. */
  status?: 'missing' | 'stale' | 'resolved' | 'optional';
}

/**
 * M12: Lightweight source-ref summary extracted from clip provenance
 * for planner inspection.
 *
 * Source refs identify timeline inputs without exposing provider rows,
 * live registry state, or extension store handles.
 */
export interface TimelineSourceRefSummary {
  /** Unique identifier for this source ref. */
  id: string;
  /** The clip that carries this source provenance. */
  clipId: string;
  /** Kind of source provenance represented by this ref. */
  sourceKind: 'asset' | 'generation' | 'extension' | 'provider' | 'unknown';
  /** Raw timeline source UUID, when available. */
  sourceUuid?: string;
  /** Generation identifier, when available. */
  generationId?: string;
  /** Extension that owns this source ref, when known. */
  extensionId?: string;
  /** Determinism posture for this source ref. */
  determinism?: DeterminismStatus;
}

/**
 * M12: Lightweight render-group summary extracted from timeline data
 * for planner inspection.
 *
 * Render groups collect clips that should be rendered together
 * (e.g. pinned shot groups).
 */
export interface TimelineRenderGroupSummary {
  /** Unique group identifier. */
  id: string;
  /** Clip IDs that belong to this render group. */
  clipIds: readonly string[];
  /** Type of the render group, when known. */
  groupType?: string;
  /** Required and optional passes that make up this render group. */
  passes?: readonly TimelineRenderPassSummary[];
  /** Required pass names, mirrored for compact planner checks. */
  requiredPasses?: readonly string[];
}

/**
 * M12: Output metadata extracted from the timeline config.
 *
 * Describes the target output resolution, FPS, and file settings
 * so the planner can validate format compatibility.
 */
export interface TimelineOutputMetadata {
  /** Output resolution string (e.g. '1920x1080'). */
  resolution: string;
  /** Frames per second. */
  fps: number;
  /** Target output filename. */
  file: string;
  /** Background color or null, when available. */
  background?: string | null;
  /** Background scale factor, when available. */
  backgroundScale?: number | null;
}

// ---------------------------------------------------------------------------
// M3: TimelineSnapshot / TimelineReader
// ---------------------------------------------------------------------------

/**
 * Stable, read-only projection of timeline state for extensions and proposal
 * machinery. Never exposes raw internal rows, provider handles, or mutation
 * engine internals.
 */
export interface TimelineSnapshot {
  /** Project identifier, when available. */
  projectId: string | null;
  /**
   * Base version for concurrency control. This is the version the snapshot
   * was taken at; proposals based on this snapshot must revalidate against
   * the current reader version before acceptance.
   */
  baseVersion: number;
  /**
   * Current version at the time the snapshot was taken. Equal to baseVersion
   * when there are no uncommitted local edits.
   */
  currentVersion: number;
  /** Extensions referenced by this project with version-range constraints. */
  extensionRequirements: readonly ProjectExtensionRequirement[];
  /** Ordered list of clip summaries (ID, track, at, clipType, duration). */
  clips: readonly TimelineClipSummary[];
  /** Ordered list of track summaries (ID, kind, label, muted). */
  tracks: readonly TimelineTrackSummary[];
  /** Asset keys present in the timeline. */
  assetKeys: readonly string[];
  /** Extension-owned app data (project-data) keyed by extension ID. */
  app: Record<string, unknown>;
  /**
   * Source-map entries extracted from extension project-data.
   * Each entry maps a timeline object to a source location.
   */
  sourceMapEntries?: readonly SourceMapEntry[];
  /** M12: Ordered list of effect summaries extracted from clips. */
  effects?: readonly TimelineEffectSummary[];
  /** M12: Ordered list of transition summaries extracted from clips. */
  transitions?: readonly TimelineTransitionSummary[];
  /** M12: Live-binding summaries extracted from clip metadata. */
  liveBindings?: readonly TimelineLiveBindingSummary[];
  /** M2: Automation summaries extracted from automation clips. */
  automations?: readonly TimelineAutomationSummary[];
  /** M12: Material-ref summaries extracted from clip data. */
  materialRefs?: readonly TimelineMaterialRefSummary[];
  /** M12: Source-ref summaries extracted from clip provenance. */
  sourceRefs?: readonly TimelineSourceRefSummary[];
  /** M13: Shader metadata persisted on clips or timeline postprocess app data. */
  shaders?: readonly TimelineShaderSummary[];
  /** M12: Render-group summaries extracted from timeline data. */
  renderGroups?: readonly TimelineRenderGroupSummary[];
  /** M12: Output metadata extracted from the timeline config. */
  outputMetadata?: TimelineOutputMetadata;
}

/** Lightweight clip summary for TimelineSnapshot projection. */
export interface TimelineClipSummary {
  id: string;
  track: string;
  at: number;
  clipType?: string;
  /** Duration in frames (derived from to-from or hold). */
  duration: number;
  /** True when this clip is managed by a registered extension. */
  managed: boolean;
  /** Extension ID that manages this clip, if managed. */
  managedBy?: string;
  /** Generated-object metadata attached by the owning extension, if any. */
  generatedMeta?: GeneratedObjectMeta;
  /** M12: Effects applied to this clip. */
  effects?: readonly TimelineEffectSummary[];
  /** M12: Transition applied to this clip, if any. */
  transition?: TimelineTransitionSummary;
  /** M12: Live bindings attached to this clip. */
  liveBindings?: readonly TimelineLiveBindingSummary[];
  /** M2: Automation summaries attached to this automation clip. */
  automation?: readonly TimelineAutomationSummary[];
  /** M12: Material refs consumed by this clip. */
  materialRefs?: readonly TimelineMaterialRefSummary[];
  /** M12: Source refs carried by this clip. */
  sourceRefs?: readonly TimelineSourceRefSummary[];
}

/** Lightweight track summary for TimelineSnapshot projection. */
export interface TimelineTrackSummary {
  id: string;
  kind: 'visual' | 'audio';
  label: string;
  muted: boolean;
  /** Extension-owned app data attached to this track. */
  app?: Record<string, unknown>;
  /** Generated-object metadata attached by the owning extension, if any. */
  generatedMeta?: GeneratedObjectMeta;
}

/** Lightweight shader metadata summary for provider-free planner inspection. */
export interface TimelineShaderSummary {
  id: string;
  shaderId: string;
  scope: ShaderMaterializerRequirementScope;
  clipId?: string;
  extensionId: string;
  contributionId: string;
  enabled: boolean;
  /** M4: Canonical shader-uniform keyframes keyed by `uniforms.<name>`. */
  keyframes?: Readonly<Record<string, readonly TimelineShaderKeyframe[]>>;
}

/**
 * Read-only timeline reader exposed to host and extension code.
 * Provides stable snapshots without exposing internal stores.
 */
export interface TimelineReader {
  /** Take a point-in-time snapshot of the current timeline state. */
  snapshot(): TimelineSnapshot;
}

// ---------------------------------------------------------------------------
// TimelineProposalInput
// ---------------------------------------------------------------------------

/** Input for creating a new proposal. */
export interface TimelineProposalInput {
  source: string;
  rationale?: string;
  patch: TimelinePatch;
  baseVersion: number;
}
