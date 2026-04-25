import { quantizeFrameCount } from '@/shared/lib/media/videoUtils';
import type { TravelGuidanceMode } from '@/shared/lib/tasks/travelGuidance';

export const MODEL_IDS = ['wan-2.2', 'ltx-2.3', 'ltx-2.3-fast'] as const;

export type SelectedModel = typeof MODEL_IDS[number];
export type ExecutionMode = 'vace' | 'i2v';
export type ModelFamily = 'wan' | 'ltx';
export type ContinuationStrategy = 'guide_overlap_masked' | 'prefix_video_source' | 'svi_latent_chaining';

export interface ModelSpec {
  id: SelectedModel;
  modelFamily: ModelFamily;
  defaultWorkerModelName: string;
  frameStep: number;
  fps: number;
  defaultFrames: number;
  maxFrames: number;
  defaultSteps: number;
  stepRange: [number, number];
  defaultGuidanceScale?: number;
  ui: {
    motionPresets: boolean;
    turboMode: boolean;
    advancedMode: boolean;
    inferenceSteps: boolean;
    guidanceScale: boolean;
  };
  supportsPhaseConfig: boolean;
  supportsMotionFields: boolean;
  continuationByExecutionMode: Partial<Record<ExecutionMode, ContinuationStrategy>>;
  supportedGuidanceModes: TravelGuidanceMode[];
  resolutionTier: 'standard' | 'hd';
  loraFamily: string;
}

export interface ResolvedContinuationPolicy {
  enabled: boolean;
  strategy?: ContinuationStrategy;
  overlapFrames: number;
  maxOutputFrames: number;
}

export interface ResolvedGenerationPolicy {
  travelMode: ExecutionMode;
  continuation: ResolvedContinuationPolicy;
  frameOverlap: number;
}

interface ResolveGenerationPolicyIntent {
  smoothContinuations: boolean;
  requestedExecutionMode: ExecutionMode;
  guidanceKind?: string;
  hasStructureVideo?: boolean;
}

const DEFAULT_FRAME_OVERLAP = 10;

const CONTINUATION_LIMITS: Record<
  ContinuationStrategy,
  { overlapFrames: number; maxOutputFrames: number }
> = {
  guide_overlap_masked: {
    overlapFrames: 10,
    maxOutputFrames: 77,
  },
  prefix_video_source: {
    overlapFrames: 25,     // 8×3+1: 3 latent frames + initial frame (LTX 8n+1 rule)
    maxOutputFrames: 217,
  },
  svi_latent_chaining: {
    overlapFrames: 4,
    maxOutputFrames: 77,
  },
};

const WAN_GUIDANCE_MODES: TravelGuidanceMode[] = ['flow', 'canny', 'depth', 'raw', 'uni3c'];
const DISTILLED_LTX_GUIDANCE_MODES: TravelGuidanceMode[] = ['video', 'pose', 'depth', 'canny', 'cameraman'];

export const MODEL_SPEC_REGISTRY: Record<SelectedModel, ModelSpec> = {
  'wan-2.2': {
    id: 'wan-2.2',
    modelFamily: 'wan',
    defaultWorkerModelName: 'wan_2_2_i2v_lightning_baseline_2_2_2',
    frameStep: 4,
    fps: 16,
    defaultFrames: 61,
    maxFrames: 81,
    defaultSteps: 6,
    stepRange: [6, 6],
    ui: {
      motionPresets: true,
      turboMode: true,
      advancedMode: true,
      inferenceSteps: false,
      guidanceScale: false,
    },
    supportsPhaseConfig: true,
    supportsMotionFields: true,
    continuationByExecutionMode: {
      vace: 'guide_overlap_masked',
      i2v: 'svi_latent_chaining',
    },
    supportedGuidanceModes: WAN_GUIDANCE_MODES,
    resolutionTier: 'standard',
    loraFamily: 'Wan 2.1 14b',
  },
  'ltx-2.3': {
    id: 'ltx-2.3',
    modelFamily: 'ltx',
    defaultWorkerModelName: 'ltx2_22B',
    frameStep: 8,
    fps: 24,
    defaultFrames: 97,
    maxFrames: 241,
    defaultSteps: 30,
    stepRange: [8, 50],
    defaultGuidanceScale: 3,
    ui: {
      motionPresets: false,
      turboMode: false,
      advancedMode: false,
      inferenceSteps: true,
      guidanceScale: true,
    },
    supportsPhaseConfig: false,
    supportsMotionFields: false,
    continuationByExecutionMode: {
      i2v: 'prefix_video_source',
    },
    supportedGuidanceModes: [],
    resolutionTier: 'hd',
    loraFamily: 'LTX 2.3',
  },
  'ltx-2.3-fast': {
    id: 'ltx-2.3-fast',
    modelFamily: 'ltx',
    defaultWorkerModelName: 'ltx2_22B_distilled_1_1',
    frameStep: 8,
    fps: 24,
    defaultFrames: 97,
    maxFrames: 241,
    defaultSteps: 8,
    stepRange: [4, 16],
    defaultGuidanceScale: 3,
    ui: {
      motionPresets: false,
      turboMode: false,
      advancedMode: false,
      inferenceSteps: true,
      guidanceScale: true,
    },
    supportsPhaseConfig: false,
    supportsMotionFields: false,
    continuationByExecutionMode: {
      i2v: 'prefix_video_source',
    },
    supportedGuidanceModes: DISTILLED_LTX_GUIDANCE_MODES,
    resolutionTier: 'hd',
    loraFamily: 'LTX 2.3',
  },
};

export function isSelectedModel(value: unknown): value is SelectedModel {
  return typeof value === 'string' && Object.prototype.hasOwnProperty.call(MODEL_SPEC_REGISTRY, value);
}

export function coerceSelectedModel(value: unknown): SelectedModel {
  return isSelectedModel(value) ? value : 'wan-2.2';
}

export function getModelSpec(modelId?: SelectedModel | null): ModelSpec {
  return MODEL_SPEC_REGISTRY[coerceSelectedModel(modelId)];
}

const LEGACY_WORKER_MODEL_ALIASES: Record<string, SelectedModel> = {
  ltx2_22B_distilled: 'ltx-2.3-fast',
};

export function resolveSelectedModelFromModelName(modelName?: string | null): SelectedModel {
  if (!modelName) {
    return 'wan-2.2';
  }

  const matchedEntry = (Object.entries(MODEL_SPEC_REGISTRY) as Array<[SelectedModel, ModelSpec]>)
    .find(([, spec]) => spec.defaultWorkerModelName === modelName);

  if (matchedEntry) {
    return matchedEntry[0];
  }

  return LEGACY_WORKER_MODEL_ALIASES[modelName] ?? 'wan-2.2';
}

export function getInferenceStepRange(model: SelectedModel): { min: number; max: number } {
  const [min, max] = getModelSpec(model).stepRange;
  return { min, max };
}

function resolveExecutionMode(
  spec: ModelSpec,
  intent: ResolveGenerationPolicyIntent,
): ExecutionMode {
  if (spec.modelFamily === 'ltx') {
    return 'i2v';
  }

  if (intent.guidanceKind === 'uni3c') {
    return 'i2v';
  }

  if (
    intent.guidanceKind === 'flow'
    || intent.guidanceKind === 'canny'
    || intent.guidanceKind === 'depth'
    || intent.guidanceKind === 'raw'
  ) {
    return 'vace';
  }

  return intent.requestedExecutionMode;
}

export function resolveContinuationPolicy(
  spec: ModelSpec,
  intent: ResolveGenerationPolicyIntent,
): ResolvedContinuationPolicy {
  const executionMode = resolveExecutionMode(spec, intent);
  const strategy = intent.smoothContinuations
    ? spec.continuationByExecutionMode[executionMode]
    : undefined;

  if (!strategy) {
    return {
      enabled: false,
      overlapFrames: DEFAULT_FRAME_OVERLAP,
      maxOutputFrames: spec.maxFrames,
    };
  }

  return {
    enabled: true,
    strategy,
    overlapFrames: CONTINUATION_LIMITS[strategy].overlapFrames,
    maxOutputFrames: CONTINUATION_LIMITS[strategy].maxOutputFrames,
  };
}

export function clampFrameCountToPolicy(
  frames: number,
  spec: ModelSpec,
  intent: ResolveGenerationPolicyIntent,
  minFrames: number = 9,
): number {
  const { maxOutputFrames } = resolveContinuationPolicy(spec, intent);
  const safeFrames = Number.isFinite(frames) ? frames : spec.defaultFrames;
  return Math.min(
    quantizeFrameCount(Math.max(safeFrames, minFrames), minFrames, spec.frameStep),
    maxOutputFrames,
  );
}

export function resolveGenerationPolicy(
  spec: ModelSpec,
  intent: ResolveGenerationPolicyIntent,
): ResolvedGenerationPolicy {
  const travelMode = resolveExecutionMode(spec, intent);
  const continuation = resolveContinuationPolicy(spec, intent);

  return {
    travelMode,
    continuation,
    frameOverlap: continuation.overlapFrames,
  };
}
