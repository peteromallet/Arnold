/**
 * M11 live bake planner.
 *
 * This module is intentionally pure: it reads registry snapshots and returns
 * deterministic replacement metadata, but it never mutates timeline config,
 * registry sources, bindings, or ring buffers. Callers own applying the
 * returned replacement refs through the normal timeline/provider surfaces.
 */

import type {
  LiveBakeResult,
  LiveBakeSelection,
  LiveBakeTarget,
  LiveChannelDescriptor,
  LiveChannelKind,
  LiveChannelMetadata,
  LiveSample,
  LiveSource,
  LiveSourceDiagnostic,
} from '@reigh/editor-sdk';
import type { RenderMaterialRef, RenderMaterialMediaKind } from './renderability';
import type {
  TimelineLiveDeterministicRef,
  TimelineLiveDeterministicRefKind,
  TimelineLiveBakeRange,
} from '@/tools/video-editor/types';

export interface LiveBakeChannelInput {
  readonly metadata: LiveChannelMetadata;
  readonly samples: readonly LiveSample[];
}

export interface LiveBakeRequest {
  readonly selection: LiveBakeSelection;
  readonly source: LiveSource;
  readonly channels: readonly LiveBakeChannelInput[];
  readonly bindingIds?: readonly string[];
}

export interface LiveBakeDeterministicReplacement {
  readonly bindingIds: readonly string[];
  readonly sourceId: string;
  readonly target: LiveBakeTarget;
  readonly outputRef: string;
  readonly deterministicRef: TimelineLiveDeterministicRef;
  readonly input: {
    readonly channelIds: readonly LiveChannelDescriptor[];
    readonly sampleCount: number;
    readonly firstTimestamp: number;
    readonly lastTimestamp: number;
    readonly inputHash: string;
    readonly formats: readonly string[];
    readonly range?: TimelineLiveBakeRange;
  };
  readonly renderMaterial?: RenderMaterialRef;
}

export interface LiveBakePlannerResult extends LiveBakeResult {
  readonly replacements: readonly LiveBakeDeterministicReplacement[];
}

interface PreparedBakeInput {
  readonly channels: readonly LiveBakeChannelInput[];
  readonly samples: readonly LiveSample[];
  readonly firstTimestamp: number;
  readonly lastTimestamp: number;
  readonly inputHash: string;
  readonly formats: readonly string[];
  readonly range?: TimelineLiveBakeRange;
}

const TARGET_TO_REF_KIND: Record<LiveBakeTarget['kind'], TimelineLiveDeterministicRefKind> = {
  asset: 'asset',
  keyframe: 'keyframe',
  automation: 'automation',
  clip: 'clip',
  sidecar: 'sidecar',
  'render-material': 'render-material',
};

const VISUAL_CHANNEL_KINDS = new Set<LiveChannelKind>(['video', 'image']);
const AUDIO_OR_CONTROL_CHANNEL_KINDS = new Set<LiveChannelKind>(['audio', 'control', 'data']);

export function bakeLiveSource(request: LiveBakeRequest): LiveBakePlannerResult {
  const selectionErrors = validateSelection(request.selection);
  const prepared = selectionErrors.length === 0 ? prepareBakeInput(request) : undefined;
  const diagnostics: LiveSourceDiagnostic[] = [...selectionErrors];

  if (prepared && prepared.samples.length === 0) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/bake-empty-selection',
      `Live bake for source "${request.source.id}" has no samples to materialize.`,
      request.source.id,
    ));
  }

  if (diagnostics.some((diagnostic) => diagnostic.severity === 'error')) {
    return {
      sourceId: request.selection.sourceId,
      targets: request.selection.targets.map((target) => ({
        target,
        outputRef: '',
        diagnostics,
      })),
      diagnostics,
      success: false,
      replacements: [],
    };
  }

  if (!prepared) {
    return {
      sourceId: request.selection.sourceId,
      targets: [],
      diagnostics,
      success: false,
      replacements: [],
    };
  }

  const replacements: LiveBakeDeterministicReplacement[] = [];
  const targetResults: LiveBakePlannerResult['targets'] = request.selection.targets.map((target) => {
    const targetDiagnostics = validateTargetCompatibility(target, prepared);
    if (targetDiagnostics.some((diagnostic) => diagnostic.severity === 'error')) {
      return { target, outputRef: '', diagnostics: targetDiagnostics };
    }

    const replacement = createReplacement(request, target, prepared);
    replacements.push(replacement);

    return {
      target,
      outputRef: replacement.outputRef,
      diagnostics: [
        createDiagnostic(
          'info',
          'live/bake-target-complete',
          `Live bake target "${target.kind}:${target.ref}" produced deterministic replacement metadata.`,
          request.source.id,
          {
            replacement: replacement.deterministicRef,
            input: replacement.input,
            renderMaterial: replacement.renderMaterial,
          },
        ),
      ],
    };
  });

  const allTargetDiagnostics = targetResults.flatMap((target) => target.diagnostics ?? []);
  const targetErrors = allTargetDiagnostics.filter((diagnostic) => diagnostic.severity === 'error');

  if (targetErrors.length > 0) {
    return {
      sourceId: request.selection.sourceId,
      targets: targetResults,
      diagnostics: targetErrors,
      success: false,
      replacements: [],
    };
  }

  const completeDiagnostic = createDiagnostic(
    'info',
    'live/bake-complete',
    `Live bake for source "${request.source.id}" produced ${replacements.length} deterministic replacement(s).`,
    request.source.id,
    {
      replacements: replacements.map((replacement) => ({
        target: replacement.target,
        outputRef: replacement.outputRef,
        deterministicRef: replacement.deterministicRef,
        input: replacement.input,
      })),
    },
  );

  return {
    sourceId: request.selection.sourceId,
    targets: targetResults,
    diagnostics: [completeDiagnostic],
    success: true,
    replacements,
  };
}

function validateSelection(selection: LiveBakeSelection): LiveSourceDiagnostic[] {
  const diagnostics: LiveSourceDiagnostic[] = [];

  if (selection.targets.length === 0) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/bake-no-targets',
      'Live bake requires at least one deterministic target.',
      selection.sourceId,
    ));
  }

  validateRangeTuple(selection.timeRange, 'timeRange', selection.sourceId, diagnostics);
  validateRangeTuple(selection.frameRange, 'frameRange', selection.sourceId, diagnostics);
  validateRangeTuple(selection.sampleRange, 'sampleRange', selection.sourceId, diagnostics);

  if (selection.takeId !== undefined && (typeof selection.takeId !== 'string' || selection.takeId.length === 0)) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/bake-invalid-range',
      'Live bake takeId must be a non-empty string when provided.',
      selection.sourceId,
      { takeId: selection.takeId },
    ));
  }

  return diagnostics;
}

function prepareBakeInput(request: LiveBakeRequest): PreparedBakeInput {
  const selectedChannelIds = new Set(request.selection.channelIds ?? []);
  const channels = request.channels.filter((channel) => (
    selectedChannelIds.size === 0 || selectedChannelIds.has(channel.metadata.channelId)
  )).map((channel) => ({
    metadata: channel.metadata,
    samples: filterSamplesForSelection(channel.samples, request.selection),
  }));
  const samples = channels.flatMap((channel) => channel.samples);
  const timestamps = samples.map((sample) => sample.frame.timestamp);
  const formats = Array.from(new Set(samples.map((sample) => sample.frame.format))).sort();
  const range = createBakeRange(request.selection);

  return {
    channels,
    samples,
    firstTimestamp: timestamps.length > 0 ? Math.min(...timestamps) : 0,
    lastTimestamp: timestamps.length > 0 ? Math.max(...timestamps) : 0,
    inputHash: stableHash({
      sourceId: request.source.id,
      channels: channels.map((channel) => ({
        channelId: channel.metadata.channelId,
        kind: channel.metadata.kind,
        samples: channel.samples.map(serializeSampleForHash),
      })),
      range,
    }),
    formats,
    range,
  };
}

function validateRangeTuple(
  value: readonly [number, number] | undefined,
  name: 'timeRange' | 'frameRange' | 'sampleRange',
  sourceId: string,
  diagnostics: LiveSourceDiagnostic[],
): void {
  if (value === undefined) return;

  const [start, end] = value;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/bake-invalid-range',
      `Live bake ${name} must contain finite ascending bounds.`,
      sourceId,
      { [name]: value },
    ));
  }
}

function createBakeRange(selection: LiveBakeSelection): TimelineLiveBakeRange | undefined {
  const range: TimelineLiveBakeRange = {};
  if (selection.timeRange) {
    range.start = selection.timeRange[0];
    range.end = selection.timeRange[1];
  }
  if (selection.frameRange) {
    range.startFrame = selection.frameRange[0];
    range.endFrame = selection.frameRange[1];
  }
  if (selection.sampleRange) {
    range.startSample = selection.sampleRange[0];
    range.endSample = selection.sampleRange[1];
  }
  if (selection.takeId) {
    range.takeId = selection.takeId;
  }

  return Object.keys(range).length > 0 ? range : undefined;
}

function filterSamplesForSelection(
  samples: readonly LiveSample[],
  selection: LiveBakeSelection,
): readonly LiveSample[] {
  return samples.filter((sample) => (
    matchesTimeRange(sample, selection.timeRange)
    && matchesSampleRange(sample, selection.sampleRange)
    && matchesFrameRange(sample, selection.frameRange)
    && matchesTakeId(sample, selection.takeId)
  ));
}

function matchesTimeRange(sample: LiveSample, range: LiveBakeSelection['timeRange']): boolean {
  return !range || (sample.frame.timestamp >= range[0] && sample.frame.timestamp <= range[1]);
}

function matchesSampleRange(sample: LiveSample, range: LiveBakeSelection['sampleRange']): boolean {
  return !range || (sample.sequenceNumber >= range[0] && sample.sequenceNumber <= range[1]);
}

function matchesFrameRange(sample: LiveSample, range: LiveBakeSelection['frameRange']): boolean {
  if (!range) return true;
  const frameIndex = getSampleFrameIndex(sample);
  return frameIndex !== undefined && frameIndex >= range[0] && frameIndex <= range[1];
}

function matchesTakeId(sample: LiveSample, takeId: LiveBakeSelection['takeId']): boolean {
  if (!takeId) return true;
  return getSampleTakeId(sample) === takeId;
}

function getSampleFrameIndex(sample: LiveSample): number | undefined {
  const metadata = sample.frame.metadata;
  const data = isRecord(sample.frame.data) ? sample.frame.data : undefined;
  return numberFromUnknown(
    metadata?.frameIndex
      ?? metadata?.frameNumber
      ?? metadata?.frame
      ?? data?.frameIndex
      ?? data?.frameNumber
      ?? data?.frame,
  );
}

function getSampleTakeId(sample: LiveSample): string | undefined {
  const metadata = sample.frame.metadata;
  const data = isRecord(sample.frame.data) ? sample.frame.data : undefined;
  const takeId = metadata?.takeId ?? data?.takeId;
  return typeof takeId === 'string' ? takeId : undefined;
}

function numberFromUnknown(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function validateTargetCompatibility(
  target: LiveBakeTarget,
  input: PreparedBakeInput,
): LiveSourceDiagnostic[] {
  const channelKinds = new Set(input.channels.map((channel) => channel.metadata.kind));
  const hasVisual = Array.from(channelKinds).some((kind) => VISUAL_CHANNEL_KINDS.has(kind));
  const hasAudioOrControl = Array.from(channelKinds).some((kind) => AUDIO_OR_CONTROL_CHANNEL_KINDS.has(kind));

  if ((target.kind === 'keyframe' || target.kind === 'automation') && !hasAudioOrControl) {
    return [createDiagnostic(
      'error',
      'live/bake-incompatible-target',
      `Live bake target "${target.kind}" requires audio, control, or data samples.`,
      undefined,
      { target, channelKinds: Array.from(channelKinds) },
    )];
  }

  if ((target.kind === 'asset' || target.kind === 'clip') && !hasVisual && !channelKinds.has('audio')) {
    return [createDiagnostic(
      'error',
      'live/bake-incompatible-target',
      `Live bake target "${target.kind}" requires visual or audio samples.`,
      undefined,
      { target, channelKinds: Array.from(channelKinds) },
    )];
  }

  return [];
}

function createReplacement(
  request: LiveBakeRequest,
  target: LiveBakeTarget,
  input: PreparedBakeInput,
): LiveBakeDeterministicReplacement {
  const outputRef = target.ref;
  const channelIds = input.channels.map((channel) => channel.metadata.channelId);
  const sampleCount = input.samples.length;
  const metadata = {
    liveBake: {
      sourceId: request.source.id,
      sourceKind: request.source.kind,
      targetKind: target.kind,
      channelIds,
      sampleCount,
      firstTimestamp: input.firstTimestamp,
      lastTimestamp: input.lastTimestamp,
      inputHash: input.inputHash,
      formats: input.formats,
      range: input.range,
      partial: input.range !== undefined,
    },
  };
  const deterministicRef: TimelineLiveDeterministicRef = {
    kind: TARGET_TO_REF_KIND[target.kind],
    ref: outputRef,
    range: input.range,
    metadata,
  };
  const renderMaterial = target.kind === 'render-material'
    ? createRenderMaterialRef(request, target, input, outputRef)
    : undefined;

  return {
    bindingIds: Object.freeze([...(request.bindingIds ?? [])]),
    sourceId: request.source.id,
    target,
    outputRef,
    deterministicRef,
    input: Object.freeze({
      channelIds: Object.freeze(channelIds),
      sampleCount,
      firstTimestamp: input.firstTimestamp,
      lastTimestamp: input.lastTimestamp,
      inputHash: input.inputHash,
      formats: Object.freeze([...input.formats]),
      range: input.range ? Object.freeze({ ...input.range }) : undefined,
    }),
    renderMaterial,
  };
}

function createRenderMaterialRef(
  request: LiveBakeRequest,
  target: LiveBakeTarget,
  input: PreparedBakeInput,
  outputRef: string,
): RenderMaterialRef {
  const mediaKind = inferRenderMaterialMediaKind(input.channels);
  return {
    id: outputRef,
    mediaKind,
    locator: {
      kind: 'provider',
      uri: `live-bake://${encodeURIComponent(request.source.id)}/${encodeURIComponent(outputRef)}`,
      contentSha256: input.inputHash,
    },
    producerExtensionId: typeof target.params?.producerExtensionId === 'string'
      ? target.params.producerExtensionId
      : undefined,
    producerVersion: typeof target.params?.producerVersion === 'string'
      ? target.params.producerVersion
      : undefined,
    determinism: 'deterministic',
    replacementPolicy: 'replace-live-ref',
  };
}

function inferRenderMaterialMediaKind(channels: readonly LiveBakeChannelInput[]): RenderMaterialMediaKind {
  const kinds = new Set(channels.map((channel) => channel.metadata.kind));
  if (kinds.has('video')) return 'video';
  if (kinds.has('image')) return 'image';
  if (kinds.has('audio')) return 'audio';
  if (kinds.has('control')) return 'json';
  return 'json';
}

function createDiagnostic(
  severity: LiveSourceDiagnostic['severity'],
  code: string,
  message: string,
  sourceId?: string,
  detail?: Record<string, unknown>,
): LiveSourceDiagnostic {
  return {
    severity,
    code,
    message,
    sourceId,
    detail,
  };
}

function serializeSampleForHash(sample: LiveSample): unknown {
  return {
    channelId: sample.channelId,
    sequenceNumber: sample.sequenceNumber,
    timestamp: sample.frame.timestamp,
    format: sample.frame.format,
    data: serializeDataForHash(sample.frame.data),
    metadata: sample.frame.metadata,
  };
}

function serializeDataForHash(data: LiveSample['frame']['data']): unknown {
  if (data instanceof Uint8Array) {
    return { type: 'Uint8Array', bytes: Array.from(data) };
  }
  if (data instanceof ArrayBuffer) {
    return { type: 'ArrayBuffer', bytes: Array.from(new Uint8Array(data)) };
  }
  return data;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function stableHash(value: unknown): string {
  const text = JSON.stringify(sortObject(value));
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return `fnv1a-${(hash >>> 0).toString(16).padStart(8, '0')}`;
}

function sortObject(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortObject);
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return Object.keys(record).sort().reduce<Record<string, unknown>>((acc, key) => {
      acc[key] = sortObject(record[key]);
      return acc;
    }, {});
  }
  return value;
}
