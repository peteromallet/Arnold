/**
 * M11 live recording conversion.
 *
 * Converts provider-scoped scalar, controller, and audio-analysis samples into
 * deterministic keyframes or automation clips. This module is pure: callers
 * provide ring-buffer snapshots and own applying returned outputs through the
 * normal timeline mutation surfaces at explicit record/bake boundaries.
 */

import type {
  LiveChannelDescriptor,
  LiveChannelKind,
  LiveChannelMetadata,
  LiveSample,
  LiveSource,
  LiveSourceDiagnostic,
} from '@reigh/editor-sdk';
import {
  type AutomationRecorderOptions,
  type SamplePoint,
  recordAutomation,
} from '@/tools/video-editor/keyframes/index.ts';
import type {
  ClipKeyframe,
  ParameterDefinition,
  TimelineClip,
} from '@/tools/video-editor/types';

export interface LiveRecordingChannelInput {
  readonly metadata: LiveChannelMetadata;
  readonly samples: readonly LiveSample[];
}

export interface LiveRecordingClock {
  readonly sourceStartTimestampMs?: number;
  readonly timelineStartSeconds?: number;
  readonly timestampUnit?: 'milliseconds' | 'seconds';
  readonly playbackRate?: number;
}

export interface LiveRecordingSampleSelection {
  readonly timeRange?: readonly [startMs: number, endMs: number];
  readonly sampleRange?: readonly [startIndex: number, endIndex: number];
  readonly takeId?: string;
}

export interface LiveRecordingSourceMapping {
  readonly bindingId?: string;
  readonly sourceId: string;
  readonly channelId?: LiveChannelDescriptor;
  readonly sourcePath?: string;
  readonly target: LiveRecordingTarget;
  readonly parameter: ParameterDefinition;
  readonly recorderOptions?: AutomationRecorderOptions;
  readonly clock?: LiveRecordingClock;
  readonly selection?: LiveRecordingSampleSelection;
}

export type LiveRecordingTarget =
  | {
      readonly kind: 'keyframe';
      readonly clipId: string;
      readonly parameterPath: string;
    }
  | {
      readonly kind: 'automation';
      readonly clipId: string;
      readonly trackId: string;
      readonly contributionId: string;
      readonly parameterPath: string;
      readonly at?: number;
      readonly duration?: number;
      readonly enabled?: boolean;
    };

export interface LiveRecordingRequest {
  readonly source: LiveSource;
  readonly channels: readonly LiveRecordingChannelInput[];
  readonly mappings: readonly LiveRecordingSourceMapping[];
}

export interface LiveRecordingClockMetadata {
  readonly sourceTimestampUnit: 'milliseconds' | 'seconds';
  readonly sourceStartTimestampMs: number;
  readonly timelineStartSeconds: number;
  readonly playbackRate: number;
  readonly firstSourceTimestamp: number;
  readonly lastSourceTimestamp: number;
  readonly firstTimelineTime: number;
  readonly lastTimelineTime: number;
}

export interface LiveRecordingOutputMetadata {
  readonly sourceId: string;
  readonly channelIds: readonly LiveChannelDescriptor[];
  readonly bindingId?: string;
  readonly sourcePath?: string;
  readonly sampleCount: number;
  readonly keyframeCount: number;
  readonly inputHash: string;
  readonly clock: LiveRecordingClockMetadata;
}

export interface LiveRecordingKeyframeOutput {
  readonly kind: 'keyframe';
  readonly clipId: string;
  readonly parameterPath: string;
  readonly keyframes: readonly ClipKeyframe[];
  readonly metadata: LiveRecordingOutputMetadata;
}

export interface LiveRecordingAutomationClipOutput {
  readonly kind: 'automation';
  readonly clip: TimelineClip;
  readonly metadata: LiveRecordingOutputMetadata;
}

export type LiveRecordingOutput = LiveRecordingKeyframeOutput | LiveRecordingAutomationClipOutput;

export interface LiveRecordingResult {
  readonly success: boolean;
  readonly outputs: readonly LiveRecordingOutput[];
  readonly diagnostics: readonly LiveSourceDiagnostic[];
}

export type LiveRecordingPassStatus = 'idle' | 'recording' | 'reviewing' | 'complete';

export type LiveRecordingTakeStatus = 'captured' | 'discarded' | 'accepted' | 'baked';

export interface LiveRecordingPassSource {
  readonly sourceId: string;
  readonly channelIds?: readonly LiveChannelDescriptor[];
}

export interface LiveRecordingTake {
  readonly id: string;
  readonly index: number;
  readonly status: LiveRecordingTakeStatus;
  readonly startedAt: string;
  readonly stoppedAt?: string;
  readonly sourceIds: readonly string[];
  readonly channelIds: readonly LiveChannelDescriptor[];
  readonly sampleCount: number;
  readonly bakedAt?: string;
  readonly outputRefs?: readonly string[];
}

export interface LiveRecordingPass {
  readonly id: string;
  readonly status: LiveRecordingPassStatus;
  readonly armedSources: readonly LiveRecordingPassSource[];
  readonly mappings: readonly LiveRecordingSourceMapping[];
  readonly takes: readonly LiveRecordingTake[];
  readonly activeTakeId?: string;
  readonly startedAt?: string;
  readonly stoppedAt?: string;
}

export interface LiveRecordingPassInit {
  readonly id: string;
  readonly armedSources: readonly LiveRecordingPassSource[];
  readonly mappings: readonly LiveRecordingSourceMapping[];
  readonly now?: string;
}

export interface LiveRecordingPassStartOptions {
  readonly takeId?: string;
  readonly startedAt?: string;
}

export interface LiveRecordingPassStopOptions {
  readonly stoppedAt?: string;
  readonly sourceIds?: readonly string[];
  readonly channelIds?: readonly LiveChannelDescriptor[];
  readonly sampleCount?: number;
}

export interface LiveRecordingPassTransitionResult {
  readonly success: boolean;
  readonly pass: LiveRecordingPass;
  readonly diagnostics: readonly LiveSourceDiagnostic[];
}

export interface LiveRecordingPassBakeResult {
  readonly success: boolean;
  readonly pass: LiveRecordingPass;
  readonly recording: LiveRecordingResult;
  readonly diagnostics: readonly LiveSourceDiagnostic[];
}

const RECORDABLE_CHANNEL_KINDS = new Set<LiveChannelKind>(['audio', 'midi', 'osc', 'data', 'control']);

export function createLiveRecordingPass(init: LiveRecordingPassInit): LiveRecordingPass {
  return freezePass({
    id: init.id,
    status: 'idle',
    armedSources: init.armedSources.map((source) => ({
      sourceId: source.sourceId,
      channelIds: source.channelIds ? Object.freeze([...source.channelIds]) : undefined,
    })),
    mappings: Object.freeze([...init.mappings]),
    takes: Object.freeze([]),
    startedAt: init.now,
  });
}

export function startLiveRecordingPass(
  pass: LiveRecordingPass,
  options: LiveRecordingPassStartOptions = {},
): LiveRecordingPassTransitionResult {
  if (pass.status === 'recording') {
    return transitionFailure(pass, 'live/recording-pass-already-active', `Recording pass "${pass.id}" is already recording.`);
  }
  if (pass.status === 'complete') {
    return transitionFailure(pass, 'live/recording-pass-complete', `Recording pass "${pass.id}" is complete.`);
  }

  const takeId = options.takeId ?? `take-${pass.takes.length + 1}`;
  if (pass.takes.some((take) => take.id === takeId)) {
    return transitionFailure(pass, 'live/recording-take-duplicate', `Recording take "${takeId}" already exists.`);
  }

  const startedAt = options.startedAt ?? new Date().toISOString();
  const nextTake: LiveRecordingTake = Object.freeze({
    id: takeId,
    index: pass.takes.length,
    status: 'captured',
    startedAt,
    sourceIds: Object.freeze([]),
    channelIds: Object.freeze([]),
    sampleCount: 0,
  });

  return transitionSuccess(freezePass({
    ...pass,
    status: 'recording',
    activeTakeId: takeId,
    startedAt: pass.startedAt ?? startedAt,
    stoppedAt: undefined,
    takes: Object.freeze([...pass.takes, nextTake]),
  }));
}

export function stopLiveRecordingPass(
  pass: LiveRecordingPass,
  options: LiveRecordingPassStopOptions = {},
): LiveRecordingPassTransitionResult {
  if (pass.status !== 'recording' || !pass.activeTakeId) {
    return transitionFailure(pass, 'live/recording-pass-not-active', `Recording pass "${pass.id}" is not recording.`);
  }

  const activeTake = pass.takes.find((take) => take.id === pass.activeTakeId);
  if (!activeTake) {
    return transitionFailure(pass, 'live/recording-take-missing', `Recording pass "${pass.id}" has no active take.`);
  }

  const stoppedAt = options.stoppedAt ?? new Date().toISOString();
  const sourceIds = options.sourceIds ?? pass.armedSources.map((source) => source.sourceId);
  const channelIds = options.channelIds ?? pass.armedSources.flatMap((source) => source.channelIds ?? []);
  const takes = pass.takes.map((take) => take.id === activeTake.id
    ? Object.freeze({
      ...take,
      stoppedAt,
      sourceIds: Object.freeze([...sourceIds]),
      channelIds: Object.freeze([...channelIds]),
      sampleCount: options.sampleCount ?? take.sampleCount,
    })
    : take);

  return transitionSuccess(freezePass({
    ...pass,
    status: 'reviewing',
    activeTakeId: undefined,
    stoppedAt,
    takes: Object.freeze(takes),
  }));
}

export function acceptLiveRecordingTake(
  pass: LiveRecordingPass,
  takeId: string,
): LiveRecordingPassTransitionResult {
  return setTakeReviewStatus(pass, takeId, 'accepted');
}

export function discardLiveRecordingTake(
  pass: LiveRecordingPass,
  takeId: string,
): LiveRecordingPassTransitionResult {
  return setTakeReviewStatus(pass, takeId, 'discarded');
}

export function bakeLiveRecordingPassTake(
  pass: LiveRecordingPass,
  request: Pick<LiveRecordingRequest, 'source' | 'channels'>,
  takeId: string,
): LiveRecordingPassBakeResult {
  const take = pass.takes.find((candidate) => candidate.id === takeId);
  if (!take) {
    const diagnostic = createDiagnostic(
      'error',
      'live/recording-take-not-found',
      `Recording take "${takeId}" was not found.`,
      request.source.id,
      undefined,
      { passId: pass.id, takeId },
    );
    return {
      success: false,
      pass,
      recording: { success: false, outputs: Object.freeze([]), diagnostics: Object.freeze([diagnostic]) },
      diagnostics: Object.freeze([diagnostic]),
    };
  }

  if (take.status === 'discarded' || take.status === 'baked') {
    const diagnostic = createDiagnostic(
      'error',
      take.status === 'discarded' ? 'live/recording-take-discarded' : 'live/recording-take-already-baked',
      `Recording take "${takeId}" is ${take.status} and cannot be baked.`,
      request.source.id,
      undefined,
      { passId: pass.id, takeId, status: take.status },
    );
    return {
      success: false,
      pass,
      recording: { success: false, outputs: Object.freeze([]), diagnostics: Object.freeze([diagnostic]) },
      diagnostics: Object.freeze([diagnostic]),
    };
  }

  const recording = bakeLiveRecording({
    source: request.source,
    channels: request.channels,
    mappings: pass.mappings.map((mapping) => ({
      ...mapping,
      selection: {
        ...mapping.selection,
        takeId,
      },
    })),
  });

  if (!recording.success) {
    return {
      success: false,
      pass,
      recording,
      diagnostics: recording.diagnostics,
    };
  }

  const outputRefs = recording.outputs.map((output) => (
    output.kind === 'keyframe'
      ? `${output.clipId}:${output.parameterPath}`
      : output.clip.id
  ));
  const bakedAt = new Date().toISOString();
  const nextPass = freezePass({
    ...pass,
    status: 'complete',
    stoppedAt: pass.stoppedAt ?? bakedAt,
    takes: Object.freeze(pass.takes.map((candidate) => candidate.id === takeId
      ? Object.freeze({
        ...candidate,
        status: 'baked' as const,
        bakedAt,
        outputRefs: Object.freeze(outputRefs),
      })
      : candidate)),
  });

  return {
    success: true,
    pass: nextPass,
    recording,
    diagnostics: recording.diagnostics,
  };
}

export function bakeLiveRecording(request: LiveRecordingRequest): LiveRecordingResult {
  const outputs: LiveRecordingOutput[] = [];
  const diagnostics: LiveSourceDiagnostic[] = [];

  for (const mapping of request.mappings) {
    const mappingDiagnostics = validateMapping(mapping);
    diagnostics.push(...mappingDiagnostics);
    if (mappingDiagnostics.some((diagnostic) => diagnostic.severity === 'error')) {
      continue;
    }

    const channels = selectChannels(request, mapping);
    if (channels.length === 0) {
      diagnostics.push(createDiagnostic(
        'error',
        'live/recording-channel-not-found',
        `No live recording channel matched mapping "${mapping.bindingId ?? mapping.target.parameterPath}".`,
        mapping.sourceId,
        mapping.channelId,
        { mapping },
      ));
      continue;
    }

    const incompatibleChannel = channels.find((channel) => !RECORDABLE_CHANNEL_KINDS.has(channel.metadata.kind));
    if (incompatibleChannel) {
      diagnostics.push(createDiagnostic(
        'error',
        'live/recording-incompatible-channel',
        `Live recording channel "${incompatibleChannel.metadata.channelId}" is not a scalar/controller/audio-analysis stream.`,
        mapping.sourceId,
        incompatibleChannel.metadata.channelId,
        { kind: incompatibleChannel.metadata.kind },
      ));
      continue;
    }

    const selectedSamples = channels.flatMap((channel) => (
      channel.samples
        .filter((sample) => sampleMatchesSelection(sample, mapping.selection))
        .map((sample) => ({ sample, channelId: channel.metadata.channelId }))
    ));
    const samplePoints = selectedSamples.flatMap(({ sample }) => {
      const value = extractMappedValue(sample, mapping);
      if (value === undefined) return [];
      return [{
        time: sampleTimelineTime(sample, mapping.clock),
        value,
      }];
    });

    if (selectedSamples.length === 0) {
      diagnostics.push(createDiagnostic(
        'error',
        'live/recording-empty-selection',
        `Live recording mapping "${mapping.bindingId ?? mapping.target.parameterPath}" has no samples to record.`,
        mapping.sourceId,
        mapping.channelId,
      ));
      continue;
    }

    if (samplePoints.length === 0) {
      diagnostics.push(createDiagnostic(
        'error',
        'live/recording-empty-values',
        `Live recording mapping "${mapping.bindingId ?? mapping.target.parameterPath}" did not resolve any serializable sample values.`,
        mapping.sourceId,
        mapping.channelId,
        { sourcePath: mapping.sourcePath },
      ));
      continue;
    }

    const recording = recordAutomation(samplePoints, mapping.parameter, mapping.recorderOptions);
    diagnostics.push(...recording.diagnostics.map((diagnostic) => ({
      severity: diagnostic.severity,
      code: `live/${diagnostic.code}`,
      message: diagnostic.message,
      sourceId: mapping.sourceId,
      channelId: mapping.channelId,
      detail: {
        ...diagnostic.detail,
        bindingId: mapping.bindingId,
        parameterPath: mapping.target.parameterPath,
      },
    } satisfies LiveSourceDiagnostic)));

    if (recording.keyframeCount === 0) {
      diagnostics.push(createDiagnostic(
        'error',
        'live/recording-no-keyframes',
        `Live recording mapping "${mapping.bindingId ?? mapping.target.parameterPath}" produced no deterministic keyframes.`,
        mapping.sourceId,
        mapping.channelId,
      ));
      continue;
    }

    const metadata = createOutputMetadata(
      request.source,
      mapping,
      selectedSamples,
      samplePoints,
      recording.keyframes,
    );
    outputs.push(createOutput(mapping, recording.keyframes, metadata));
  }

  const hasErrors = diagnostics.some((diagnostic) => diagnostic.severity === 'error');
  return {
    success: !hasErrors,
    outputs: Object.freeze(hasErrors ? [] : outputs),
    diagnostics: Object.freeze(diagnostics),
  };
}

function setTakeReviewStatus(
  pass: LiveRecordingPass,
  takeId: string,
  status: 'accepted' | 'discarded',
): LiveRecordingPassTransitionResult {
  if (pass.status === 'recording') {
    return transitionFailure(pass, 'live/recording-pass-active-review', `Recording pass "${pass.id}" must stop before take review.`);
  }

  const take = pass.takes.find((candidate) => candidate.id === takeId);
  if (!take) {
    return transitionFailure(pass, 'live/recording-take-not-found', `Recording take "${takeId}" was not found.`);
  }
  if (take.status === 'baked') {
    return transitionFailure(pass, 'live/recording-take-already-baked', `Recording take "${takeId}" is already baked.`);
  }

  return transitionSuccess(freezePass({
    ...pass,
    status: 'reviewing',
    takes: Object.freeze(pass.takes.map((candidate) => candidate.id === takeId
      ? Object.freeze({ ...candidate, status })
      : candidate)),
  }));
}

function transitionSuccess(pass: LiveRecordingPass): LiveRecordingPassTransitionResult {
  return {
    success: true,
    pass,
    diagnostics: Object.freeze([]),
  };
}

function transitionFailure(pass: LiveRecordingPass, code: string, message: string): LiveRecordingPassTransitionResult {
  const diagnostic = createDiagnostic('error', code, message, undefined, undefined, { passId: pass.id });
  return {
    success: false,
    pass,
    diagnostics: Object.freeze([diagnostic]),
  };
}

function freezePass(pass: LiveRecordingPass): LiveRecordingPass {
  return Object.freeze({
    ...pass,
    armedSources: Object.freeze(pass.armedSources.map((source) => Object.freeze({
      sourceId: source.sourceId,
      channelIds: source.channelIds ? Object.freeze([...source.channelIds]) : undefined,
    }))),
    mappings: Object.freeze([...pass.mappings]),
    takes: Object.freeze(pass.takes.map((take) => Object.freeze({
      ...take,
      sourceIds: Object.freeze([...take.sourceIds]),
      channelIds: Object.freeze([...take.channelIds]),
      outputRefs: take.outputRefs ? Object.freeze([...take.outputRefs]) : undefined,
    }))),
  });
}

function validateMapping(mapping: LiveRecordingSourceMapping): LiveSourceDiagnostic[] {
  const diagnostics: LiveSourceDiagnostic[] = [];
  if (!mapping.sourceId) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/recording-invalid-mapping',
      'Live recording mapping requires a sourceId.',
    ));
  }
  if (!mapping.target.parameterPath) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/recording-invalid-mapping',
      'Live recording mapping requires a target parameter path.',
      mapping.sourceId,
      mapping.channelId,
    ));
  }
  if (!mapping.parameter.name) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/recording-invalid-mapping',
      'Live recording mapping requires a parameter definition name.',
      mapping.sourceId,
      mapping.channelId,
    ));
  }
  validateRange(mapping.selection?.timeRange, 'timeRange', mapping, diagnostics);
  validateRange(mapping.selection?.sampleRange, 'sampleRange', mapping, diagnostics);
  return diagnostics;
}

function validateRange(
  range: readonly [number, number] | undefined,
  name: string,
  mapping: LiveRecordingSourceMapping,
  diagnostics: LiveSourceDiagnostic[],
): void {
  if (!range) return;
  const [start, end] = range;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/recording-invalid-range',
      `Live recording ${name} must contain finite ascending bounds.`,
      mapping.sourceId,
      mapping.channelId,
      { [name]: range },
    ));
  }
}

function selectChannels(
  request: LiveRecordingRequest,
  mapping: LiveRecordingSourceMapping,
): readonly LiveRecordingChannelInput[] {
  return request.channels.filter((channel) => (
    channel.metadata.sourceId === mapping.sourceId
      && (!mapping.channelId || channel.metadata.channelId === mapping.channelId)
  ));
}

function sampleMatchesSelection(
  sample: LiveSample,
  selection: LiveRecordingSampleSelection | undefined,
): boolean {
  if (!selection) return true;
  if (selection.timeRange && (
    sample.frame.timestamp < selection.timeRange[0] || sample.frame.timestamp > selection.timeRange[1]
  )) {
    return false;
  }
  if (selection.sampleRange && (
    sample.sequenceNumber < selection.sampleRange[0] || sample.sequenceNumber > selection.sampleRange[1]
  )) {
    return false;
  }
  if (selection.takeId && getSampleTakeId(sample) !== selection.takeId) {
    return false;
  }
  return true;
}

function extractMappedValue(
  sample: LiveSample,
  mapping: LiveRecordingSourceMapping,
): SamplePoint['value'] | undefined {
  const data = sample.frame.data;
  if (!isRecord(data)) return undefined;

  const value = mapping.sourcePath
    ? readPath(data, mapping.sourcePath)
    : inferDefaultSampleValue(data, mapping.parameter.type);

  return typeof value === 'number' || typeof value === 'string' || typeof value === 'boolean'
    ? value
    : undefined;
}

function inferDefaultSampleValue(data: Record<string, unknown>, parameterType: ParameterDefinition['type']): unknown {
  if (parameterType === 'boolean') {
    return data.value ?? data.onset ?? data.triggered ?? data.active;
  }
  if (parameterType === 'number') {
    return data.value ?? data.scalar ?? data.knob ?? data.rms ?? data.amplitude ?? data.level;
  }
  return data.value ?? data.scalar;
}

function sampleTimelineTime(sample: LiveSample, clock: LiveRecordingClock | undefined): number {
  const timestampUnit = clock?.timestampUnit ?? 'milliseconds';
  const sourceStart = clock?.sourceStartTimestampMs ?? 0;
  const timelineStart = clock?.timelineStartSeconds ?? 0;
  const playbackRate = clock?.playbackRate ?? 1;
  const timestampSeconds = timestampUnit === 'seconds'
    ? sample.frame.timestamp - sourceStart
    : (sample.frame.timestamp - sourceStart) / 1000;
  return timelineStart + (timestampSeconds * playbackRate);
}

function createOutputMetadata(
  source: LiveSource,
  mapping: LiveRecordingSourceMapping,
  selectedSamples: readonly { sample: LiveSample; channelId: LiveChannelDescriptor }[],
  samplePoints: readonly SamplePoint[],
  keyframes: readonly ClipKeyframe[],
): LiveRecordingOutputMetadata {
  const sourceTimestamps = selectedSamples.map(({ sample }) => sample.frame.timestamp);
  const timelineTimes = samplePoints.map((sample) => sample.time);
  const channelIds = Array.from(new Set(selectedSamples.map(({ channelId }) => channelId))).sort() as LiveChannelDescriptor[];
  const clock = mapping.clock ?? {};
  const timestampUnit = clock.timestampUnit ?? 'milliseconds';
  const sourceStart = clock.sourceStartTimestampMs ?? 0;
  const timelineStart = clock.timelineStartSeconds ?? 0;
  const playbackRate = clock.playbackRate ?? 1;

  return Object.freeze({
    sourceId: source.id,
    channelIds: Object.freeze(channelIds),
    bindingId: mapping.bindingId,
    sourcePath: mapping.sourcePath,
    sampleCount: selectedSamples.length,
    keyframeCount: keyframes.length,
    inputHash: stableHash({
      sourceId: source.id,
      sourceKind: source.kind,
      target: mapping.target,
      parameter: mapping.parameter,
      recorderOptions: mapping.recorderOptions,
      clock: mapping.clock,
      selection: mapping.selection,
      samples: selectedSamples.map(({ sample, channelId }) => ({
        channelId,
        sequenceNumber: sample.sequenceNumber,
        timestamp: sample.frame.timestamp,
        data: sample.frame.data,
        metadata: sample.frame.metadata,
      })),
      keyframes,
    }),
    clock: Object.freeze({
      sourceTimestampUnit: timestampUnit,
      sourceStartTimestampMs: sourceStart,
      timelineStartSeconds: timelineStart,
      playbackRate,
      firstSourceTimestamp: Math.min(...sourceTimestamps),
      lastSourceTimestamp: Math.max(...sourceTimestamps),
      firstTimelineTime: Math.min(...timelineTimes),
      lastTimelineTime: Math.max(...timelineTimes),
    }),
  });
}

function createOutput(
  mapping: LiveRecordingSourceMapping,
  keyframes: readonly ClipKeyframe[],
  metadata: LiveRecordingOutputMetadata,
): LiveRecordingOutput {
  if (mapping.target.kind === 'keyframe') {
    return Object.freeze({
      kind: 'keyframe',
      clipId: mapping.target.clipId,
      parameterPath: mapping.target.parameterPath,
      keyframes: Object.freeze([...keyframes]),
      metadata,
    });
  }

  const at = mapping.target.at ?? metadata.clock.firstTimelineTime;
  const duration = mapping.target.duration
    ?? Math.max(0, metadata.clock.lastTimelineTime - at);

  return Object.freeze({
    kind: 'automation',
    clip: Object.freeze({
      id: mapping.target.clipId,
      at,
      track: mapping.target.trackId,
      clipType: 'automation',
      hold: duration,
      params: Object.freeze({
        target: Object.freeze({
          contributionId: mapping.target.contributionId,
          parameterPath: mapping.target.parameterPath,
        }),
        keyframes: Object.freeze([...keyframes]),
        enabled: mapping.target.enabled !== false,
        liveRecording: metadata,
      }),
      app: Object.freeze({
        liveRecording: metadata,
      }),
    }),
    metadata,
  });
}

function getSampleTakeId(sample: LiveSample): string | undefined {
  const metadata = sample.frame.metadata;
  const data = isRecord(sample.frame.data) ? sample.frame.data : undefined;
  const takeId = metadata?.takeId ?? data?.takeId;
  return typeof takeId === 'string' ? takeId : undefined;
}

function readPath(value: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, segment) => {
    if (!isRecord(acc)) return undefined;
    return acc[segment];
  }, value);
}

function createDiagnostic(
  severity: LiveSourceDiagnostic['severity'],
  code: string,
  message: string,
  sourceId?: string,
  channelId?: LiveChannelDescriptor,
  detail?: Record<string, unknown>,
): LiveSourceDiagnostic {
  return {
    severity,
    code,
    message,
    sourceId,
    channelId,
    detail,
  };
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
  if (value instanceof Uint8Array) {
    return { type: 'Uint8Array', bytes: Array.from(value) };
  }
  if (value instanceof ArrayBuffer) {
    return { type: 'ArrayBuffer', bytes: Array.from(new Uint8Array(value)) };
  }
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
