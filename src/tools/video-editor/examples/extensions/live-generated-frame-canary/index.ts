/**
 * live-generated-frame-canary — M11 generated-frame live-data canary.
 *
 * Exercises GenerationSession sample delivery for pending/refining/final
 * generated frames, explicit steering lineage, cancellation, and deterministic
 * bake refs through the public SDK only.
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  AgentToolContribution,
  AgentToolHandler,
  AgentToolInvocationRequest,
  DisposeHandle,
  ExtensionContext,
  GenerationSession,
  GenerationSessionLiveDelivery,
  LiveBakeResult,
  LiveChannelDescriptor,
  LiveSample,
  LiveSourceDiagnostic,
  ReighExtension,
  SteeringDecision,
  SteeringDecisionKind,
  ToolGenerationSessionResult,
  ToolResultDiagnostic,
} from '@reigh/editor-sdk';

const EXTENSION_ID = 'com.reigh.examples.live-generated-frame-canary';
const TOOL_ID = 'generated-frame.session';
const CONTRIBUTION_ID = 'generated-frame-session-contribution';
const PRODUCER_VERSION = '1.0.0';
const DEFAULT_WIDTH = 512;
const DEFAULT_HEIGHT = 512;

export type GeneratedFrameState = 'pending' | 'refining' | 'final';

export interface LiveGeneratedFrameCanaryOptions {
  readonly sessionId?: string;
  readonly sourceId?: string;
  readonly bindingId?: string;
  readonly previewClipId?: string;
  readonly width?: number;
  readonly height?: number;
  readonly prompt?: string;
  readonly model?: string;
  readonly seed?: string | number;
  readonly steeringKind?: SteeringDecisionKind;
  readonly generationIndex?: number;
  readonly parentRefs?: readonly string[];
  readonly takeId?: string;
  readonly now?: () => number;
  readonly onReady?: (controller: LiveGeneratedFrameCanaryController) => void;
}

export interface EmitGeneratedFrameOptions {
  readonly state: GeneratedFrameState;
  readonly progress: number;
  readonly frameIndex?: number;
  readonly takeId?: string;
  readonly src?: string;
  readonly accepted?: boolean;
}

export interface LiveGeneratedFrameSession extends GenerationSession {
  readonly sourceId: string;
  readonly producerChannelId: LiveChannelDescriptor;
  emitFrame(options: EmitGeneratedFrameOptions): boolean;
  emitPending(frameIndex?: number): boolean;
  emitRefining(frameIndex?: number): boolean;
  emitFinal(frameIndex?: number): boolean;
  acceptTake(takeId?: string): void;
}

export interface LiveGeneratedFrameCanaryController extends DisposeHandle {
  readonly toolId: string;
  readonly sourceId: string;
  readonly contribution: AgentToolContribution;
  getLastSession(): LiveGeneratedFrameSession | undefined;
  createSession(request?: Partial<AgentToolInvocationRequest>): ToolGenerationSessionResult;
  bakeAcceptedTake(ref?: string, takeId?: string): LiveBakeResult;
  bakeAsset(ref?: string): LiveBakeResult;
  bakeRenderMaterial(ref?: string): LiveBakeResult;
  createPreviewClip(channelId?: LiveChannelDescriptor): Record<string, unknown>;
}

function report(
  ctx: ExtensionContext,
  severity: LiveSourceDiagnostic['severity'],
  code: string,
  message: string,
  detail?: Record<string, unknown>,
): ToolResultDiagnostic {
  ctx.services.diagnostics.report({ severity, code, message, detail });
  return { severity, code, message, detail };
}

function readString(input: unknown, fallback: string): string {
  return typeof input === 'string' && input.length > 0 ? input : fallback;
}

function readNumber(input: unknown, fallback: number): number {
  return typeof input === 'number' && Number.isFinite(input) ? input : fallback;
}

function createSourceId(sessionId: string, explicit?: string): string {
  return explicit ?? `${EXTENSION_ID}:generated:${sessionId}`;
}

function createBindingId(sourceId: string, explicit?: string): string {
  return explicit ?? `${sourceId}:preview-binding`;
}

function createProducerChannelId(sessionId: string): LiveChannelDescriptor {
  return `${EXTENSION_ID}:producer:${sessionId}:frames` as LiveChannelDescriptor;
}

function createRefBase(sessionId: string, takeId?: string): string {
  return `${EXTENSION_ID}:${sessionId}${takeId ? `:${takeId}` : ''}`;
}

function createSteeringDecision(options: {
  sessionId: string;
  producerChannelId: LiveChannelDescriptor;
  kind: SteeringDecisionKind;
  generationIndex: number;
  parentRefs: readonly string[];
  prompt: string;
  model: string;
  seed: string | number;
}): SteeringDecision {
  const steerHash = [
    options.kind,
    options.sessionId,
    options.generationIndex,
    options.prompt,
    options.model,
    String(options.seed),
    options.parentRefs.join(','),
  ].join('|');

  return {
    kind: options.kind,
    sessionId: options.sessionId,
    lineage: {
      generationIndex: options.generationIndex,
      steerHash: `generated-frame-${hashString(steerHash)}`,
      parentRefs: options.parentRefs,
      producerVersion: PRODUCER_VERSION,
      provenance: {
        prompt: options.prompt,
        model: options.model,
        seed: options.seed,
        producerExtensionId: EXTENSION_ID,
        tags: ['generated-frame-canary', options.kind],
      },
      provenanceTags: ['generated-frame-canary', options.kind],
    },
    reason: `Canary ${options.kind} steering decision.`,
    replacementChannelId: options.kind === 'supersede' ? options.producerChannelId : undefined,
  };
}

function hashString(value: string): string {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}

function createPreviewClip(options: {
  sourceId: string;
  bindingId: string;
  clipId: string;
  channelId?: LiveChannelDescriptor;
  width: number;
  height: number;
}): Record<string, unknown> {
  const binding = {
    bindingId: options.bindingId,
    sourceId: options.sourceId,
    sourceKind: 'generated',
    channelId: options.channelId,
    ownerExtensionId: EXTENSION_ID,
    sampling: { mode: 'latest' },
    placeholder: {
      label: 'Generated Frame Canary',
      progress: 0,
    },
    metadata: {
      canary: 'live-generated-frame',
      preview: true,
    },
  };

  return {
    id: options.clipId,
    at: 0,
    duration: 2,
    track: 'V1',
    clipType: 'live-frame-preview',
    params: {
      livePreview: true,
      liveBindings: [binding],
      width: options.width,
      height: options.height,
    },
    app: {
      livePreview: true,
      live: {
        bindings: [binding],
      },
    },
  };
}

export function createLiveGeneratedFramePreviewClip(
  channelId?: LiveChannelDescriptor,
  options: Partial<LiveGeneratedFrameCanaryOptions> = {},
): Record<string, unknown> {
  const sessionId = options.sessionId ?? 'default';
  const sourceId = createSourceId(sessionId, options.sourceId);
  return createPreviewClip({
    sourceId,
    bindingId: createBindingId(sourceId, options.bindingId),
    clipId: options.previewClipId ?? `${sourceId}:preview`,
    channelId,
    width: options.width ?? DEFAULT_WIDTH,
    height: options.height ?? DEFAULT_HEIGHT,
  });
}

function createGeneratedFrameSession(options: {
  sessionId: string;
  sourceId: string;
  producerChannelId: LiveChannelDescriptor;
  width: number;
  height: number;
  prompt: string;
  model: string;
  seed: string | number;
  takeId: string;
  now: () => number;
  liveDelivery: GenerationSessionLiveDelivery;
}): LiveGeneratedFrameSession {
  const sampleListeners = new Set<(sample: LiveSample) => void>();
  const progressListeners = new Set<(progress: number, label?: string) => void>();
  const diagnostics: ToolResultDiagnostic[] = [];
  let progress = 0;
  let progressLabel = 'Pending generated frame';
  let cancelled = false;
  let done = false;
  let sequenceNumber = 0;
  let acceptedTakeId: string | undefined;

  const notifyProgress = () => {
    for (const listener of progressListeners) {
      listener(progress, progressLabel);
    }
  };

  const session: LiveGeneratedFrameSession = {
    id: options.sessionId,
    sourceId: options.sourceId,
    producerChannelId: options.producerChannelId,
    get progress() {
      return progress;
    },
    get progressLabel() {
      return progressLabel;
    },
    get cancelled() {
      return cancelled;
    },
    get done() {
      return done;
    },
    get diagnostics() {
      return diagnostics;
    },
    liveDelivery: options.liveDelivery,
    finalRefs: [`${createRefBase(options.sessionId, options.takeId)}:final-frame`],
    bakedRefs: [],
    onProgress(listener) {
      progressListeners.add(listener);
      return {
        dispose() {
          progressListeners.delete(listener);
        },
      };
    },
    cancel() {
      if (cancelled || done) return;
      cancelled = true;
      progressLabel = 'Cancelled';
      diagnostics.push({
        severity: 'info',
        code: 'live-generated-frame/cancelled',
        message: `Generated frame session ${options.sessionId} was cancelled.`,
        detail: { sessionId: options.sessionId, sourceId: options.sourceId },
      });
      notifyProgress();
    },
    getSampleChannel() {
      return options.producerChannelId;
    },
    onSample(listener) {
      sampleListeners.add(listener);
      return {
        dispose() {
          sampleListeners.delete(listener);
        },
      };
    },
    getSteeringLineage() {
      return options.liveDelivery.steeringDecision.lineage;
    },
    complete(result) {
      if (done || cancelled) return;
      done = true;
      progress = 100;
      progressLabel = 'Generation complete';
      const refs = Array.isArray(result?.bakedRefs)
        ? result?.bakedRefs.filter((ref): ref is string => typeof ref === 'string')
        : undefined;
      if (refs && refs.length > 0) {
        Object.defineProperty(session, 'bakedRefs', {
          configurable: true,
          value: Object.freeze(refs),
        });
      }
      notifyProgress();
    },
    emitFrame(frame) {
      if (cancelled || done) return false;
      progress = Math.max(0, Math.min(100, frame.progress));
      progressLabel = frame.state === 'final'
        ? 'Generated frame final'
        : frame.state === 'refining'
          ? 'Refining generated frame'
          : 'Pending generated frame';
      const frameIndex = frame.frameIndex ?? 0;
      const takeId = frame.takeId ?? acceptedTakeId ?? options.takeId;
      const accepted = frame.accepted ?? Boolean(acceptedTakeId && acceptedTakeId === takeId);
      const src = frame.src ?? `data:image/png;base64,GENERATED_${options.sessionId}_${takeId}_${frameIndex}_${frame.state}`;
      const sample: LiveSample = {
        channelId: options.producerChannelId,
        sequenceNumber,
        frame: {
          timestamp: options.now(),
          format: 'json',
          data: {
            src,
            state: frame.state,
            progress,
            frameIndex,
            takeId,
            accepted,
            width: options.width,
            height: options.height,
            prompt: options.prompt,
            model: options.model,
            seed: options.seed,
          },
          metadata: {
            canary: 'live-generated-frame',
            state: frame.state,
            frameIndex,
            takeId,
            accepted,
            width: options.width,
            height: options.height,
          },
        },
      };
      sequenceNumber += 1;
      for (const listener of sampleListeners) {
        listener(sample);
      }
      notifyProgress();
      return true;
    },
    emitPending(frameIndex = 0) {
      return session.emitFrame({ state: 'pending', progress: 10, frameIndex });
    },
    emitRefining(frameIndex = 0) {
      return session.emitFrame({ state: 'refining', progress: 65, frameIndex });
    },
    emitFinal(frameIndex = 0) {
      return session.emitFrame({ state: 'final', progress: 100, frameIndex, accepted: true });
    },
    acceptTake(takeId = options.takeId) {
      acceptedTakeId = takeId;
    },
  };

  return session;
}

export const liveGeneratedFrameCanaryContribution: AgentToolContribution = {
  id: CONTRIBUTION_ID as any,
  kind: 'agentTool',
  toolId: TOOL_ID,
  label: 'Live Generated Frame Canary',
  description: 'Produces pending/refining/final generated frame samples through GenerationSession live delivery.',
  resultFamilies: ['generation/session'],
  order: 40,
};

export function startLiveGeneratedFrameCanary(
  ctx: ExtensionContext,
  options: LiveGeneratedFrameCanaryOptions = {},
): LiveGeneratedFrameCanaryController {
  let disposed = false;
  let lastSession: LiveGeneratedFrameSession | undefined;
  let toolHandle: DisposeHandle | undefined;

  const createSession = (
    request: Partial<AgentToolInvocationRequest> = {},
  ): ToolGenerationSessionResult => {
    const input = request.input ?? {};
    const sessionId = readString(input.sessionId, options.sessionId ?? 'generated-frame-session-1');
    const width = readNumber(input.width, options.width ?? DEFAULT_WIDTH);
    const height = readNumber(input.height, options.height ?? DEFAULT_HEIGHT);
    const prompt = readString(input.prompt, options.prompt ?? 'canary generated frame');
    const model = readString(input.model, options.model ?? 'canary-frame-model');
    const seed = input.seed ?? options.seed ?? 1234;
    const takeId = readString(input.takeId, options.takeId ?? 'take-accepted');
    const steeringKind = readString(input.steeringKind, options.steeringKind ?? 'supersede') as SteeringDecisionKind;
    const generationIndex = readNumber(input.generationIndex, options.generationIndex ?? 1);
    const parentRefs = Array.isArray(input.parentRefs)
      ? input.parentRefs.filter((ref): ref is string => typeof ref === 'string' && ref.length > 0)
      : [...(options.parentRefs ?? [`${sessionId}:parent`])];
    const producerChannelId = createProducerChannelId(sessionId);
    const sourceId = createSourceId(sessionId, options.sourceId);
    const decision = createSteeringDecision({
      sessionId,
      producerChannelId,
      kind: steeringKind,
      generationIndex,
      parentRefs,
      prompt,
      model,
      seed: seed as string | number,
    });
    const liveDelivery: GenerationSessionLiveDelivery = {
      origin: 'agent-tool',
      sourceId,
      sourceLabel: 'Live Generated Frame Canary',
      channelKind: 'video',
      activeChannels: [producerChannelId],
      steeringDecision: decision,
      finalRefs: [`${createRefBase(sessionId, takeId)}:final-frame`],
      bakedRefs: [],
      metadata: {
        canary: 'live-generated-frame',
        prompt,
        model,
        seed,
        takeId,
      },
    };
    const session = createGeneratedFrameSession({
      sessionId,
      sourceId,
      producerChannelId,
      width,
      height,
      prompt,
      model,
      seed: seed as string | number,
      takeId,
      now: options.now ?? (() => Date.now()),
      liveDelivery,
    });
    lastSession = session;
    return {
      family: 'generation/session',
      session,
      liveDelivery,
      rationale: 'Deterministic generated-frame canary session with explicit steering lineage.',
      diagnostics: [
        {
          severity: 'info',
          code: 'live-generated-frame/session-created',
          message: `Generated frame canary session ${sessionId} created.`,
          detail: { sessionId, sourceId, steeringKind, generationIndex, takeId },
        },
      ],
    };
  };

  const handler: AgentToolHandler = (request) => {
    if (disposed) {
      return {
        family: 'generation/session',
        ...createSession(request),
        diagnostics: [
          report(
            ctx,
            'warning',
            'live-generated-frame/disposed',
            'Generated frame canary was invoked after disposal.',
          ),
        ],
      };
    }
    return createSession(request);
  };

  toolHandle = ctx.agentTools.registerTool(TOOL_ID, handler);
  ctx.services.diagnostics.report({
    severity: 'info',
    code: 'live-generated-frame/activated',
    message: 'Live generated frame canary registered its GenerationSession tool.',
  });

  const controller: LiveGeneratedFrameCanaryController = {
    toolId: TOOL_ID,
    get sourceId() {
      return lastSession?.sourceId ?? createSourceId(options.sessionId ?? 'generated-frame-session-1', options.sourceId);
    },
    contribution: liveGeneratedFrameCanaryContribution,
    getLastSession() {
      return lastSession;
    },
    createSession,
    bakeAcceptedTake(ref?: string, takeId?: string) {
      const session = lastSession;
      const selectedTakeId = takeId ?? options.takeId ?? 'take-accepted';
      return ctx.creative.sessions.bake({
        sourceId: session?.sourceId ?? createSourceId(options.sessionId ?? 'generated-frame-session-1', options.sourceId),
        takeId: selectedTakeId,
        targets: [{ kind: 'asset', ref: ref ?? `${createRefBase(session?.id ?? 'generated-frame-session-1', selectedTakeId)}:partial-asset` }],
      });
    },
    bakeAsset(ref?: string) {
      const session = lastSession;
      return ctx.creative.sessions.bake({
        sourceId: session?.sourceId ?? createSourceId(options.sessionId ?? 'generated-frame-session-1', options.sourceId),
        targets: [{ kind: 'asset', ref: ref ?? `${createRefBase(session?.id ?? 'generated-frame-session-1')}:asset` }],
      });
    },
    bakeRenderMaterial(ref?: string) {
      const session = lastSession;
      return ctx.creative.sessions.bake({
        sourceId: session?.sourceId ?? createSourceId(options.sessionId ?? 'generated-frame-session-1', options.sourceId),
        targets: [{
          kind: 'render-material',
          ref: ref ?? `${createRefBase(session?.id ?? 'generated-frame-session-1')}:material`,
          params: {
            producerExtensionId: EXTENSION_ID,
            producerVersion: PRODUCER_VERSION,
          },
        }],
      });
    },
    createPreviewClip(channelId?: LiveChannelDescriptor) {
      const sourceId = lastSession?.sourceId ?? createSourceId(options.sessionId ?? 'generated-frame-session-1', options.sourceId);
      return createPreviewClip({
        sourceId,
        bindingId: createBindingId(sourceId, options.bindingId),
        clipId: options.previewClipId ?? `${sourceId}:preview`,
        channelId,
        width: options.width ?? DEFAULT_WIDTH,
        height: options.height ?? DEFAULT_HEIGHT,
      });
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      toolHandle?.dispose();
      lastSession?.cancel();
    },
  };

  options.onReady?.(controller);
  return controller;
}

export function createLiveGeneratedFrameCanaryExtension(
  options: LiveGeneratedFrameCanaryOptions = {},
): ReighExtension {
  return defineExtension({
    manifest: {
      id: EXTENSION_ID as any,
      version: PRODUCER_VERSION,
      label: 'Live Generated Frame Canary',
      description: 'M11 canary for generated frame GenerationSession live samples, steering, bake, and deterministic refs.',
      apiVersion: 1,
      contributions: [liveGeneratedFrameCanaryContribution],
      messages: {
        'activation.started': 'Live Generated Frame Canary activating.',
        'activation.ready': 'Live Generated Frame Canary ready.',
        'activation.disposed': 'Live Generated Frame Canary disposed.',
      },
    } as any,
    activate(ctx) {
      return startLiveGeneratedFrameCanary(ctx, options);
    },
  });
}

export const liveGeneratedFrameCanaryExtension = createLiveGeneratedFrameCanaryExtension();

export default liveGeneratedFrameCanaryExtension;
