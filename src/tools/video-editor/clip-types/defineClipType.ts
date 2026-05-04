import type { ComponentType } from 'react';
import type {
  ParameterSchema,
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
  TimelineClip,
  TrackKind,
} from '@/tools/video-editor/types';

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export type ClipTypeHoldTiming = {
  defaultSeconds: number;
  minSeconds: number;
  maxSeconds: number;
  stepSeconds: number;
};

export type ClipTypeHoldSupport =
  | { kind: 'unsupported' }
  | ({ kind: 'supported' | 'required' } & ClipTypeHoldTiming);

export type ClipTypeSequenceParamKind = 'string' | 'asset-list';

export type ClipTypeSequenceParamDefinition = {
  key: string;
  label: string;
  kind: ClipTypeSequenceParamKind;
  description: string;
  required?: boolean;
  defaultValue?: string | readonly string[];
  options?: readonly string[];
  maxItems?: number;
  componentParam?: string;
};

export type ClipTypeParamsSchema =
  | {
    kind: 'none';
    params: readonly [];
  }
  | {
    kind: 'editor';
    params: ParameterSchema;
  }
  | {
    kind: 'sequence';
    params: readonly ClipTypeSequenceParamDefinition[];
  };

export const EMPTY_CLIP_TYPE_PARAMS_SCHEMA: ClipTypeParamsSchema = {
  kind: 'none',
  params: [],
};

export type ClipTypeCommandFact =
  | 'selection.cardinality'
  | 'selection.sameClipType'
  | 'track.kind'
  | 'asset.mediaType'
  | 'clip.hasAsset'
  | 'clip.hasText'
  | 'clip.hold.kind'
  | 'clip.isInPinnedShotGroup'
  | (string & {});

export type ClipTypeCommandOperator =
  | 'equals'
  | 'notEquals'
  | 'in'
  | 'notIn'
  | 'exists';

export type ClipTypeCommandConstraintValue =
  | string
  | number
  | boolean
  | readonly (string | number | boolean)[];

export type ClipTypeCommandConstraint = {
  fact: ClipTypeCommandFact;
  operator: ClipTypeCommandOperator;
  value?: ClipTypeCommandConstraintValue;
  rationale?: string;
};

export type ClipTypeCommandMetadata = {
  id: string;
  label: string;
  description?: string;
  requirements?: readonly ClipTypeCommandConstraint[];
  limitations?: readonly ClipTypeCommandConstraint[];
};

export type ClipTypePreviewRoute =
  | 'native-media'
  | 'native-audio'
  | 'native-text'
  | 'effect-layer'
  | 'sequence-component'
  | 'custom'
  | (string & {});

export type ClipTypeExportRoute =
  | 'client'
  | 'banodoco'
  | 'blocked'
  | 'custom'
  | (string & {});

export type ClipTypeRenderFeature =
  | 'overlay'
  | 'crop'
  | 'manual-bounds'
  | 'inline-text-edit'
  | 'lightbox'
  | 'waveform'
  | 'audio-only'
  | 'visual'
  | 'hold-duration'
  | (string & {});

export type ClipTypeRenderCapabilities = {
  previewRoute: ClipTypePreviewRoute;
  exportRoute: ClipTypeExportRoute;
  features?: readonly ClipTypeRenderFeature[];
  knownLimitations?: readonly string[];
};

type ClipTypeDefaultClipFields = Omit<TimelineClip, 'id' | 'at' | 'track' | 'params'>;

export type ClipTypeDefaults = {
  clip?: Partial<ClipTypeDefaultClipFields>;
  params?: Record<string, JsonValue>;
};

export type NormalizedClipTypeDefaults = {
  clip: Partial<ClipTypeDefaultClipFields>;
  params: Record<string, JsonValue>;
};

export type ClipTypeRuntimeContext = {
  clip?: TimelineClip;
  resolvedClip?: ResolvedTimelineClip;
  config?: ResolvedTimelineConfig;
  trackKind?: TrackKind;
  selectedClipIds?: readonly string[];
};

export type ClipTypeRenderAdapter<Props extends Record<string, unknown> = Record<string, unknown>> =
  ComponentType<Props>;

export type ClipTypeInspectorAdapter<Props extends Record<string, unknown> = Record<string, unknown>> =
  ComponentType<Props>;

export type ClipTypeTimelineDisplayAdapter = {
  getLabel?: (context: ClipTypeRuntimeContext) => string;
  getBadges?: (context: ClipTypeRuntimeContext) => readonly string[];
};

export type ClipTypeResizeAdapter = {
  policy?: 'none' | 'trim' | 'freeform' | 'hold-only' | 'custom';
  getMinDurationSeconds?: (context: ClipTypeRuntimeContext) => number | null;
  getMaxDurationSeconds?: (context: ClipTypeRuntimeContext) => number | null;
};

export type ClipTypeDragAdapter = {
  policy?: 'default' | 'disabled' | 'custom';
  allowsCrossTrack?: boolean;
  allowsNewTrackCreation?: boolean;
};

export type ClipTypeDescriptorInput = {
  id: string;
  label?: string;
  description?: string;
  hold?: ClipTypeHoldSupport;
  paramsSchema?: ClipTypeParamsSchema;
  defaults?: ClipTypeDefaults;
  render?: ClipTypeRenderAdapter;
  Inspector?: ClipTypeInspectorAdapter;
  timelineDisplay?: ClipTypeTimelineDisplayAdapter;
  resize?: ClipTypeResizeAdapter;
  drag?: ClipTypeDragAdapter;
  commands?: readonly ClipTypeCommandMetadata[];
  renderCapabilities: ClipTypeRenderCapabilities;
};

export const CLIP_TYPE_RUNTIME_FIELD_KEYS = [
  'render',
  'Inspector',
  'timelineDisplay',
  'resize',
  'drag',
] as const;

export type ClipTypeRuntimeFieldKey = (typeof CLIP_TYPE_RUNTIME_FIELD_KEYS)[number];

export type ClipTypeDescriptor = Omit<ClipTypeDescriptorInput, 'hold' | 'paramsSchema' | 'defaults'> & {
  hold: ClipTypeHoldSupport;
  paramsSchema: ClipTypeParamsSchema;
  defaults: NormalizedClipTypeDefaults;
};

export type ClipTypeManifest = Omit<ClipTypeDescriptor, ClipTypeRuntimeFieldKey>;

const cloneJsonValue = <T extends JsonValue>(value: T): T => {
  if (Array.isArray(value)) {
    return value.map((item) => cloneJsonValue(item)) as T;
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, nested]) => [key, cloneJsonValue(nested)]),
    ) as T;
  }
  return value;
};

const getParamsSchemaDefaults = (
  paramsSchema: ClipTypeParamsSchema,
): Record<string, JsonValue> => {
  if (paramsSchema.kind === 'none') {
    return {};
  }
  if (paramsSchema.kind === 'editor') {
    return paramsSchema.params.reduce<Record<string, JsonValue>>((defaults, param) => {
      if (param.default !== undefined) {
        defaults[param.name] = cloneJsonValue(param.default as JsonValue);
      }
      return defaults;
    }, {});
  }
  return paramsSchema.params.reduce<Record<string, JsonValue>>((defaults, param) => {
    if (param.defaultValue !== undefined) {
      defaults[param.key] = cloneJsonValue(param.defaultValue as JsonValue);
    }
    return defaults;
  }, {});
};

const normalizeHold = (hold: ClipTypeHoldSupport | undefined): ClipTypeHoldSupport => {
  return hold ?? { kind: 'unsupported' };
};

const normalizeDefaults = (
  id: string,
  hold: ClipTypeHoldSupport,
  paramsSchema: ClipTypeParamsSchema,
  defaults: ClipTypeDefaults | undefined,
): NormalizedClipTypeDefaults => {
  const clipDefaults: Partial<ClipTypeDefaultClipFields> = {
    ...(defaults?.clip ?? {}),
    clipType: id,
  };
  if (hold.kind !== 'unsupported' && clipDefaults.hold === undefined) {
    clipDefaults.hold = hold.defaultSeconds;
  }

  return {
    clip: clipDefaults,
    params: {
      ...getParamsSchemaDefaults(paramsSchema),
      ...Object.fromEntries(
        Object.entries(defaults?.params ?? {}).map(([key, value]) => [key, cloneJsonValue(value)]),
      ),
    },
  };
};

const normalizeClipTypeDescriptor = (
  descriptor: ClipTypeDescriptorInput,
): ClipTypeDescriptor => {
  const hold = normalizeHold(descriptor.hold);
  const paramsSchema = descriptor.paramsSchema ?? EMPTY_CLIP_TYPE_PARAMS_SCHEMA;
  return {
    ...descriptor,
    hold,
    paramsSchema,
    defaults: normalizeDefaults(descriptor.id, hold, paramsSchema, descriptor.defaults),
  };
};

export const isEditorParamsSchema = (
  paramsSchema: ClipTypeParamsSchema,
): paramsSchema is Extract<ClipTypeParamsSchema, { kind: 'editor' }> => {
  return paramsSchema.kind === 'editor';
};

export const isSequenceParamsSchema = (
  paramsSchema: ClipTypeParamsSchema,
): paramsSchema is Extract<ClipTypeParamsSchema, { kind: 'sequence' }> => {
  return paramsSchema.kind === 'sequence';
};

export const isEmptyParamsSchema = (
  paramsSchema: ClipTypeParamsSchema,
): paramsSchema is Extract<ClipTypeParamsSchema, { kind: 'none' }> => {
  return paramsSchema.kind === 'none';
};

export const defineClipType = <
  const TDescriptor extends ClipTypeDescriptorInput,
>(
  descriptor: TDescriptor,
): ClipTypeDescriptor & TDescriptor => {
  return normalizeClipTypeDescriptor(descriptor) as ClipTypeDescriptor & TDescriptor;
};

export const toClipTypeManifest = (
  descriptor: ClipTypeDescriptorInput,
): ClipTypeManifest => {
  const normalized = normalizeClipTypeDescriptor(descriptor);
  const {
    render: _render,
    Inspector: _Inspector,
    timelineDisplay: _timelineDisplay,
    resize: _resize,
    drag: _drag,
    ...manifest
  } = normalized;
  return manifest;
};
