/**
 * M11 live learn-mode mapping runtime.
 *
 * Captures the next sample on a selected source/channel as a generic mapping
 * candidate. The host owns the mapping table shape, but source-specific payload
 * interpretation remains extension-owned: this module stores sample metadata
 * only and never persists raw sample data.
 */

import type {
  DisposeHandle,
  LiveChannelDescriptor,
  LiveChannelMetadata,
  LiveSample,
  LiveSessionsService,
  LiveSource,
  LiveSourceDiagnostic,
} from '@reigh/editor-sdk';

export type LiveMappingStatus =
  | 'idle'
  | 'listening'
  | 'candidate'
  | 'mapped'
  | 'cancelled'
  | 'timed-out'
  | 'error';

export type LiveMappingTargetKind = 'clip' | 'effect' | 'material' | 'session' | 'custom';

export interface LiveMappingTarget {
  readonly kind: LiveMappingTargetKind;
  readonly ref: string;
  readonly parameterPath: string;
  readonly label?: string;
  readonly schema?: Record<string, unknown>;
}

export interface LiveMappingCandidate {
  readonly id: string;
  readonly sourceId: string;
  readonly sourceKind: LiveSource['kind'];
  readonly channelId: LiveChannelDescriptor;
  readonly channelKind: LiveChannelMetadata['kind'];
  readonly sequenceNumber: number;
  readonly sampleTimestamp: number;
  readonly sampleFormat: LiveSample['frame']['format'];
  readonly capturedAt: string;
  readonly frameMetadata?: Record<string, unknown>;
}

export interface LiveMappingTableEntry {
  readonly mappingId: string;
  readonly sourceId: string;
  readonly sourceKind: LiveSource['kind'];
  readonly channelId: LiveChannelDescriptor;
  readonly channelKind: LiveChannelMetadata['kind'];
  readonly target: LiveMappingTarget;
  readonly candidate: LiveMappingCandidate;
  readonly createdAt: string;
  readonly metadata?: Record<string, unknown>;
}

export interface LiveMappingTable {
  readonly version: 1;
  readonly entries: readonly LiveMappingTableEntry[];
}

export interface LiveMappingVisualState {
  readonly status: LiveMappingStatus;
  readonly learnMode: 'idle' | 'mapping';
  readonly sourceId?: string;
  readonly channelId?: LiveChannelDescriptor;
  readonly targetLabel?: string;
  readonly progress: number;
  readonly message: string;
}

export interface LiveMappingState {
  readonly id: string;
  readonly status: LiveMappingStatus;
  readonly sourceId: string;
  readonly channelId: LiveChannelDescriptor;
  readonly target: LiveMappingTarget;
  readonly startedAt: string;
  readonly timeoutMs: number;
  readonly candidate?: LiveMappingCandidate;
  readonly mapping?: LiveMappingTableEntry;
  readonly diagnostics: readonly LiveSourceDiagnostic[];
  readonly visual: LiveMappingVisualState;
}

export interface LiveMappingStartRequest {
  readonly id: string;
  readonly sourceId: string;
  readonly channelId: LiveChannelDescriptor;
  readonly target: LiveMappingTarget;
  readonly timeoutMs?: number;
  readonly now?: () => Date;
  readonly onStateChange?: (state: LiveMappingState) => void;
}

export interface LiveMappingAcceptOptions {
  readonly candidateId?: string;
  readonly mappingId?: string;
  readonly table?: LiveMappingTable;
  readonly metadata?: Record<string, unknown>;
  readonly now?: () => Date;
}

export interface LiveMappingAcceptResult {
  readonly success: boolean;
  readonly table: LiveMappingTable;
  readonly mapping?: LiveMappingTableEntry;
  readonly diagnostics: readonly LiveSourceDiagnostic[];
  readonly state: LiveMappingState;
}

export interface LiveMappingSession extends DisposeHandle {
  readonly id: string;
  getState(): LiveMappingState;
  cancel(reason?: string): LiveMappingState;
  acceptCandidate(options?: LiveMappingAcceptOptions): LiveMappingAcceptResult;
}

const DEFAULT_TIMEOUT_MS = 10_000;

export function createLiveMappingTable(
  entries: readonly LiveMappingTableEntry[] = [],
): LiveMappingTable {
  return Object.freeze({
    version: 1 as const,
    entries: Object.freeze([...entries]),
  });
}

export function startLiveMappingLearn(
  service: Pick<LiveSessionsService, 'getSource' | 'getChannelMetadata' | 'subscribeSamples'>,
  request: LiveMappingStartRequest,
): LiveMappingSession {
  const now = request.now ?? (() => new Date());
  const startedAt = now().toISOString();
  const timeoutMs = request.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const diagnostics = validateLiveMappingStart(service, request, timeoutMs);

  let source = service.getSource(request.sourceId);
  let channel = service.getChannelMetadata(request.channelId);
  let status: LiveMappingStatus = diagnostics.length > 0 ? 'error' : 'listening';
  let candidate: LiveMappingCandidate | undefined;
  let mapping: LiveMappingTableEntry | undefined;
  let subscription: DisposeHandle | undefined;
  let timeoutHandle: ReturnType<typeof globalThis.setTimeout> | undefined;
  let disposed = false;

  function snapshot(): LiveMappingState {
    const visual = makeVisualState({
      status,
      sourceId: request.sourceId,
      channelId: request.channelId,
      target: request.target,
      timeoutMs,
      hasCandidate: candidate !== undefined,
    });

    return Object.freeze({
      id: request.id,
      status,
      sourceId: request.sourceId,
      channelId: request.channelId,
      target: freezeTarget(request.target),
      startedAt,
      timeoutMs,
      candidate,
      mapping,
      diagnostics: Object.freeze([...diagnostics]),
      visual,
    });
  }

  function emitState(): LiveMappingState {
    const state = snapshot();
    request.onStateChange?.(state);
    return state;
  }

  function clearTimer(): void {
    if (timeoutHandle !== undefined) {
      globalThis.clearTimeout(timeoutHandle);
      timeoutHandle = undefined;
    }
  }

  function unsubscribe(): void {
    subscription?.dispose();
    subscription = undefined;
  }

  function finish(nextStatus: LiveMappingStatus, diagnostic?: LiveSourceDiagnostic): LiveMappingState {
    if (status === 'mapped' || status === 'cancelled' || status === 'timed-out' || status === 'error') {
      return snapshot();
    }
    status = nextStatus;
    if (diagnostic) diagnostics.push(diagnostic);
    clearTimer();
    unsubscribe();
    return emitState();
  }

  function capture(sample: LiveSample): void {
    if (status !== 'listening') return;
    if (sample.sequenceNumber < 0) {
      finish('error', makeDiagnostic(
        'warning',
        'live/learn-channel-closed',
        `Learn mapping "${request.id}" stopped because channel "${request.channelId}" closed.`,
        request.sourceId,
        request.channelId,
      ));
      return;
    }

    source = service.getSource(request.sourceId);
    channel = service.getChannelMetadata(request.channelId);
    if (!source || !channel) {
      finish('error', makeDiagnostic(
        'warning',
        'live/learn-source-unavailable',
        `Learn mapping "${request.id}" could not capture because its source or channel is unavailable.`,
        request.sourceId,
        request.channelId,
      ));
      return;
    }

    candidate = Object.freeze({
      id: `${request.id}:candidate:${sample.sequenceNumber}`,
      sourceId: request.sourceId,
      sourceKind: source.kind,
      channelId: request.channelId,
      channelKind: channel.kind,
      sequenceNumber: sample.sequenceNumber,
      sampleTimestamp: sample.frame.timestamp,
      sampleFormat: sample.frame.format,
      capturedAt: now().toISOString(),
      frameMetadata: sample.frame.metadata ? Object.freeze({ ...sample.frame.metadata }) : undefined,
    });
    status = 'candidate';
    clearTimer();
    unsubscribe();
    emitState();
  }

  if (status === 'listening') {
    subscription = service.subscribeSamples(request.channelId, capture);
    timeoutHandle = globalThis.setTimeout(() => {
      finish('timed-out', makeDiagnostic(
        'warning',
        'live/learn-timeout',
        `Learn mapping "${request.id}" timed out waiting for a sample.`,
        request.sourceId,
        request.channelId,
        { timeoutMs },
      ));
    }, timeoutMs);
  }

  emitState();

  return {
    id: request.id,
    getState(): LiveMappingState {
      return snapshot();
    },
    cancel(reason = 'cancelled'): LiveMappingState {
      if (status === 'mapped' || status === 'cancelled' || status === 'timed-out' || status === 'error') {
        return snapshot();
      }
      return finish('cancelled', makeDiagnostic(
        'info',
        'live/learn-cancelled',
        `Learn mapping "${request.id}" was cancelled.`,
        request.sourceId,
        request.channelId,
        { reason },
      ));
    },
    acceptCandidate(options: LiveMappingAcceptOptions = {}): LiveMappingAcceptResult {
      if (status !== 'candidate' || !candidate) {
        const diagnostic = makeDiagnostic(
          'warning',
          'live/learn-no-candidate',
          `Learn mapping "${request.id}" has no candidate to accept.`,
          request.sourceId,
          request.channelId,
        );
        diagnostics.push(diagnostic);
        return {
          success: false,
          table: options.table ?? createLiveMappingTable(),
          diagnostics: Object.freeze([diagnostic]),
          state: emitState(),
        };
      }

      if (options.candidateId && options.candidateId !== candidate.id) {
        const diagnostic = makeDiagnostic(
          'warning',
          'live/learn-candidate-mismatch',
          `Learn mapping "${request.id}" candidate "${options.candidateId}" is not the captured candidate.`,
          request.sourceId,
          request.channelId,
          { expectedCandidateId: candidate.id, candidateId: options.candidateId },
        );
        diagnostics.push(diagnostic);
        return {
          success: false,
          table: options.table ?? createLiveMappingTable(),
          diagnostics: Object.freeze([diagnostic]),
          state: emitState(),
        };
      }

      const acceptedAt = (options.now ?? now)().toISOString();
      mapping = Object.freeze({
        mappingId: options.mappingId ?? `${request.id}:mapping`,
        sourceId: candidate.sourceId,
        sourceKind: candidate.sourceKind,
        channelId: candidate.channelId,
        channelKind: candidate.channelKind,
        target: freezeTarget(request.target),
        candidate,
        createdAt: acceptedAt,
        metadata: options.metadata ? Object.freeze({ ...options.metadata }) : undefined,
      });
      status = 'mapped';
      clearTimer();
      unsubscribe();

      const table = createLiveMappingTable([...(options.table?.entries ?? []), mapping]);
      return {
        success: true,
        table,
        mapping,
        diagnostics: Object.freeze([]),
        state: emitState(),
      };
    },
    dispose(): void {
      if (disposed) return;
      disposed = true;
      clearTimer();
      unsubscribe();
    },
  };
}

function validateLiveMappingStart(
  service: Pick<LiveSessionsService, 'getSource' | 'getChannelMetadata'>,
  request: LiveMappingStartRequest,
  timeoutMs: number,
): LiveSourceDiagnostic[] {
  const diagnostics: LiveSourceDiagnostic[] = [];

  if (!request.id.trim()) {
    diagnostics.push(makeDiagnostic(
      'error',
      'live/learn-invalid-request',
      'Learn mapping requires a non-empty id.',
      request.sourceId,
      request.channelId,
    ));
  }

  if (!request.target.ref.trim() || !request.target.parameterPath.trim()) {
    diagnostics.push(makeDiagnostic(
      'error',
      'live/learn-invalid-target',
      'Learn mapping requires a target ref and parameter path.',
      request.sourceId,
      request.channelId,
      { targetKind: request.target.kind },
    ));
  }

  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    diagnostics.push(makeDiagnostic(
      'error',
      'live/learn-invalid-timeout',
      'Learn mapping timeout must be a positive finite number.',
      request.sourceId,
      request.channelId,
      { timeoutMs },
    ));
  }

  const source = service.getSource(request.sourceId);
  if (!source) {
    diagnostics.push(makeDiagnostic(
      'error',
      'live/learn-source-not-found',
      `Learn mapping source "${request.sourceId}" was not found.`,
      request.sourceId,
      request.channelId,
    ));
  }

  const channel = service.getChannelMetadata(request.channelId);
  if (!channel) {
    diagnostics.push(makeDiagnostic(
      'error',
      'live/learn-channel-not-found',
      `Learn mapping channel "${request.channelId}" was not found.`,
      request.sourceId,
      request.channelId,
    ));
  } else if (channel.sourceId !== request.sourceId) {
    diagnostics.push(makeDiagnostic(
      'error',
      'live/learn-channel-source-mismatch',
      `Learn mapping channel "${request.channelId}" does not belong to source "${request.sourceId}".`,
      request.sourceId,
      request.channelId,
      { channelSourceId: channel.sourceId },
    ));
  }

  return diagnostics;
}

function makeVisualState(input: {
  readonly status: LiveMappingStatus;
  readonly sourceId: string;
  readonly channelId: LiveChannelDescriptor;
  readonly target: LiveMappingTarget;
  readonly timeoutMs: number;
  readonly hasCandidate: boolean;
}): LiveMappingVisualState {
  const learnMode = input.status === 'listening' || input.status === 'candidate' ? 'mapping' : 'idle';
  const progress = input.status === 'listening'
    ? 0
    : input.status === 'candidate' || input.status === 'mapped'
      ? 1
      : 0;

  return Object.freeze({
    status: input.status,
    learnMode,
    sourceId: input.sourceId,
    channelId: input.channelId,
    targetLabel: input.target.label,
    progress,
    message: visualMessage(input.status, input.timeoutMs, input.hasCandidate),
  });
}

function visualMessage(status: LiveMappingStatus, timeoutMs: number, hasCandidate: boolean): string {
  switch (status) {
    case 'listening':
      return `Waiting for the next sample (${timeoutMs} ms timeout).`;
    case 'candidate':
      return hasCandidate ? 'Mapping candidate captured.' : 'Waiting for candidate selection.';
    case 'mapped':
      return 'Mapping accepted.';
    case 'cancelled':
      return 'Mapping cancelled.';
    case 'timed-out':
      return 'Mapping timed out.';
    case 'error':
      return 'Mapping could not start.';
    case 'idle':
      return 'Mapping idle.';
  }
}

function freezeTarget(target: LiveMappingTarget): LiveMappingTarget {
  return Object.freeze({
    ...target,
    schema: target.schema ? Object.freeze({ ...target.schema }) : undefined,
  });
}

function makeDiagnostic(
  severity: LiveSourceDiagnostic['severity'],
  code: string,
  message: string,
  sourceId?: string,
  channelId?: LiveChannelDescriptor,
  detail?: Record<string, unknown>,
): LiveSourceDiagnostic {
  return { severity, code, message, sourceId, channelId, detail };
}
