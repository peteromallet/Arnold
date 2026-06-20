import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createExtensionContext,
  type AgentToolInvocationRequest,
  type AgentToolRegistrationService,
  type CreativeContext,
  type ExtensionContext,
  type LiveBakeResult,
  type LiveChannelDescriptor,
  type LiveSessionsService,
  type ReighExtension,
  type ToolGenerationSessionResult,
} from '@/sdk/index';
import {
  createLiveGeneratedFrameCanaryExtension,
  startLiveGeneratedFrameCanary,
  type LiveGeneratedFrameCanaryController,
  type LiveGeneratedFrameSession,
} from '@/tools/video-editor/examples/extensions/live-generated-frame-canary';
import {
  createAgentToolRegistry,
  type AgentToolRegistry,
} from '@/tools/video-editor/runtime/agentToolRegistry';
import {
  createLiveDataRegistry,
  type LiveDataRegistry,
} from '@/tools/video-editor/runtime/liveDataRegistry';

const EXTENSION_ID = 'com.reigh.examples.live-generated-frame-canary';
const TOOL_ID = 'generated-frame.session';

function makeSessions(registry: LiveDataRegistry, extensionId = EXTENSION_ID): LiveSessionsService {
  return {
    registerSource(source) {
      return registry.registerSourceWithOwner(source, extensionId);
    },
    getSource(sourceId) {
      return registry.getSource(sourceId);
    },
    listSources() {
      return registry.listSources();
    },
    openChannel(sourceId, kind, metadata) {
      return registry.openChannel(sourceId, kind, metadata);
    },
    closeChannel(channelId) {
      registry.closeChannel(channelId);
    },
    getChannelMetadata(channelId) {
      return registry.getChannelMetadata(channelId);
    },
    pushSample(channelId, frame) {
      registry.pushSample(channelId, frame);
    },
    subscribeSamples(channelId, listener) {
      return registry.subscribeSamples(channelId, listener);
    },
    bake(selection) {
      return registry.bake(selection);
    },
    removeLiveBindings(sourceId) {
      registry.removeLiveBindings(sourceId);
    },
    resolveBinding(bindingId) {
      return registry.resolveBinding(bindingId);
    },
    getBindingMetadata() {
      return registry.getBindingMetadata();
    },
    applySteeringDecision(decision) {
      registry.applySteeringDecision(decision);
    },
    getDiagnostics(sourceId) {
      return registry.getDiagnostics(sourceId);
    },
  };
}

function makeAgentTools(registry: AgentToolRegistry, extensionId = EXTENSION_ID): AgentToolRegistrationService {
  return {
    registerTool(toolId, handler) {
      return registry.registerTool(extensionId, toolId, handler);
    },
    async invokeProcess() {
      return {
        family: 'process',
        diagnostics: [{
          severity: 'info',
          code: 'agent-tool/process-not-available',
          message: 'Process invocation is not available in the generated-frame canary test.',
        }],
      };
    },
  };
}

function makeCtx(
  extension: ReighExtension,
  liveRegistry: LiveDataRegistry,
  agentRegistry: AgentToolRegistry,
): ExtensionContext {
  return createExtensionContext(
    extension,
    { sessions: makeSessions(liveRegistry) } as Partial<CreativeContext>,
    undefined,
    undefined,
    undefined,
    undefined,
    makeAgentTools(agentRegistry),
  );
}

function makeRequest(input: Record<string, unknown> = {}): AgentToolInvocationRequest {
  return {
    toolId: TOOL_ID,
    extensionId: EXTENSION_ID,
    contributionId: 'generated-frame-session-contribution',
    context: { projectId: 'project-canary' },
    input,
  };
}

function hostChannelFor(
  agentRegistry: AgentToolRegistry,
  sourceId: string,
): LiveChannelDescriptor {
  const channel = agentRegistry.getSnapshot().sessions[0]?.liveDelivery?.activeChannels
    .find((candidate) => candidate.startsWith(`${sourceId}:ch-`));
  expect(channel).toBeDefined();
  return channel as LiveChannelDescriptor;
}

function replacements(result: LiveBakeResult): any[] {
  return (result as unknown as { replacements: any[] }).replacements;
}

function activateCanary(options: {
  now?: () => number;
} = {}): {
  extension: ReighExtension;
  liveRegistry: LiveDataRegistry;
  agentRegistry: AgentToolRegistry;
  ctx: ExtensionContext;
  controller: LiveGeneratedFrameCanaryController;
  dispose: () => void;
} {
  const liveRegistry = createLiveDataRegistry({ emitLifecycleDiagnostics: false });
  const agentRegistry = createAgentToolRegistry({ liveDataRegistry: liveRegistry });
  let controller: LiveGeneratedFrameCanaryController | undefined;
  const extension = createLiveGeneratedFrameCanaryExtension({
    now: options.now,
    onReady(next) {
      controller = next;
    },
  });

  for (const contribution of extension.manifest.contributions ?? []) {
    if (contribution.kind === 'agentTool') {
      agentRegistry.ingestAgentToolContribution(EXTENSION_ID, contribution);
    }
  }

  const ctx = makeCtx(extension, liveRegistry, agentRegistry);
  const handle = extension.activate(ctx);
  expect(controller).toBeDefined();

  return {
    extension,
    liveRegistry,
    agentRegistry,
    ctx,
    controller: controller!,
    dispose() {
      handle?.dispose();
      agentRegistry.dispose();
      liveRegistry.dispose();
    },
  };
}

async function invokeSession(
  agentRegistry: AgentToolRegistry,
  input: Record<string, unknown> = {},
): Promise<ToolGenerationSessionResult> {
  const result = await agentRegistry.invokeTool(makeRequest(input));
  expect(result).toEqual(expect.objectContaining({ family: 'generation/session' }));
  return result as ToolGenerationSessionResult;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('live-generated-frame-canary extension', () => {
  it('streams pending, refining, and final generated frame samples through GenerationSession live delivery', async () => {
    let now = 1000;
    const test = activateCanary({ now: () => {
      now += 10;
      return now;
    } });

    const result = await invokeSession(test.agentRegistry, {
      sessionId: 'session-supersede',
      steeringKind: 'supersede',
      generationIndex: 3,
      parentRefs: ['session-parent'],
      takeId: 'take-main',
      prompt: 'make a canary frame',
      model: 'deterministic-canary',
      seed: 77,
    });
    const session = result.session as LiveGeneratedFrameSession;
    const sourceId = 'com.reigh.examples.live-generated-frame-canary:generated:session-supersede';
    const hostChannel = hostChannelFor(test.agentRegistry, sourceId);

    expect(test.liveRegistry.getSource(sourceId)).toEqual(expect.objectContaining({
      id: sourceId,
      kind: 'generated',
      metadata: expect.objectContaining({
        generationIndex: 3,
        parentRefs: ['session-parent'],
      }),
    }));

    expect(session.emitPending(0)).toBe(true);
    expect(session.emitRefining(0)).toBe(true);
    expect(session.emitFinal(0)).toBe(true);

    expect(test.liveRegistry.getSource(sourceId)).toEqual(expect.objectContaining({
      status: 'active',
    }));
    expect(test.liveRegistry.getSampleCount(hostChannel)).toBe(3);
    expect(test.liveRegistry.getLatestSample(hostChannel)?.frame).toEqual(expect.objectContaining({
      timestamp: 1030,
      format: 'json',
      data: expect.objectContaining({
        state: 'final',
        progress: 100,
        frameIndex: 0,
        takeId: 'take-main',
        accepted: true,
      }),
      metadata: expect.objectContaining({
        state: 'final',
        frameIndex: 0,
        takeId: 'take-main',
        accepted: true,
        origin: 'agent-tool',
        sessionId: 'session-supersede',
        toolId: TOOL_ID,
        extensionId: EXTENSION_ID,
        sourceChannelId: session.producerChannelId,
        generationIndex: 3,
        parentRefs: ['session-parent'],
        steeringDecision: 'supersede',
      }),
    }));
    expect(test.agentRegistry.getSnapshot().sessions[0].liveDelivery).toEqual(expect.objectContaining({
      canActivate: true,
      progress: 100,
      sampleCount: 3,
      generationIndex: 3,
      parentRefs: ['session-parent'],
    }));

    test.dispose();
  });

  it('cancels live generated frame sessions and stops further sample delivery', async () => {
    const test = activateCanary({ now: () => 2000 });
    const result = await invokeSession(test.agentRegistry, { sessionId: 'session-cancel' });
    const session = result.session as LiveGeneratedFrameSession;
    const sourceId = 'com.reigh.examples.live-generated-frame-canary:generated:session-cancel';
    const hostChannel = hostChannelFor(test.agentRegistry, sourceId);

    expect(test.agentRegistry.cancelSessions(TOOL_ID)).toBe(1);
    expect(session.cancelled).toBe(true);
    expect(session.emitFinal(0)).toBe(false);
    expect(test.liveRegistry.getSampleCount(hostChannel)).toBe(0);
    expect(test.agentRegistry.getSnapshot().sessions).toHaveLength(0);
    expect(session.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'info',
        code: 'live-generated-frame/cancelled',
      }),
    ]);

    test.dispose();
  });

  it('supports fork steering while reject steering blocks live activation without silent fallback', async () => {
    const fork = activateCanary({ now: () => 3000 });
    await invokeSession(fork.agentRegistry, {
      sessionId: 'session-fork',
      steeringKind: 'fork',
      generationIndex: 4,
      parentRefs: ['session-supersede'],
    });
    const forkSourceId = 'com.reigh.examples.live-generated-frame-canary:generated:session-fork';
    const forkSession = fork.agentRegistry.getSnapshot().sessions[0];
    expect(fork.liveRegistry.getSource(forkSourceId)).toBeDefined();
    expect(forkSession.liveDelivery).toEqual(expect.objectContaining({
      canActivate: true,
      generationIndex: 4,
      parentRefs: ['session-supersede'],
      steeringDecision: expect.objectContaining({ kind: 'fork' }),
    }));
    fork.dispose();

    const reject = activateCanary({ now: () => 4000 });
    await invokeSession(reject.agentRegistry, {
      sessionId: 'session-reject',
      steeringKind: 'reject',
      generationIndex: 5,
      parentRefs: ['session-fork'],
    });
    const rejectSourceId = 'com.reigh.examples.live-generated-frame-canary:generated:session-reject';
    const rejectSession = reject.agentRegistry.getSnapshot().sessions[0];
    expect(reject.liveRegistry.getSource(rejectSourceId)).toBeUndefined();
    expect(rejectSession.liveDelivery).toEqual(expect.objectContaining({
      canActivate: false,
      generationIndex: 5,
      diagnostics: expect.arrayContaining([
        expect.objectContaining({ code: 'live/steering-rejected' }),
      ]),
    }));
    expect(reject.agentRegistry.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({ code: 'live/steering-rejected' }),
    ]));
    reject.dispose();
  });

  it('partially bakes accepted takes and fully bakes deterministic asset and RenderMaterial refs', async () => {
    const test = activateCanary({ now: () => 5000 });
    const result = await invokeSession(test.agentRegistry, {
      sessionId: 'session-bake',
      takeId: 'take-a',
    });
    const session = result.session as LiveGeneratedFrameSession;

    session.acceptTake('take-a');
    expect(session.emitFrame({
      state: 'final',
      progress: 100,
      frameIndex: 0,
      takeId: 'take-a',
      accepted: true,
    })).toBe(true);
    expect(session.emitFrame({
      state: 'final',
      progress: 100,
      frameIndex: 1,
      takeId: 'take-b',
      accepted: false,
    })).toBe(true);

    const partial = test.controller.bakeAcceptedTake('generated-take-a-asset', 'take-a');
    expect(partial.success).toBe(true);
    expect(replacements(partial)[0]).toEqual(expect.objectContaining({
      outputRef: 'generated-take-a-asset',
      input: expect.objectContaining({
        sampleCount: 1,
        range: expect.objectContaining({ takeId: 'take-a' }),
      }),
      deterministicRef: expect.objectContaining({
        kind: 'asset',
        ref: 'generated-take-a-asset',
        range: expect.objectContaining({ takeId: 'take-a' }),
        metadata: {
          liveBake: expect.objectContaining({
            sourceKind: 'generated',
            targetKind: 'asset',
            partial: true,
            sampleCount: 1,
          }),
        },
      }),
    }));

    const asset = test.controller.bakeAsset('generated-full-asset');
    const material = test.controller.bakeRenderMaterial('generated-full-material');
    expect(asset.success).toBe(true);
    expect(material.success).toBe(true);
    expect(replacements(asset)[0].deterministicRef).toEqual(expect.objectContaining({
      kind: 'asset',
      ref: 'generated-full-asset',
      metadata: {
        liveBake: expect.objectContaining({
          sourceKind: 'generated',
          targetKind: 'asset',
          partial: false,
          sampleCount: 2,
        }),
      },
    }));
    expect(replacements(material)[0].renderMaterial).toEqual(expect.objectContaining({
      id: 'generated-full-material',
      mediaKind: 'video',
      producerExtensionId: EXTENSION_ID,
      producerVersion: '1.0.0',
      determinism: 'deterministic',
      replacementPolicy: 'replace-live-ref',
    }));
    expect(replacements(test.controller.bakeAsset('generated-full-asset'))[0].input.inputHash)
      .toBe(replacements(asset)[0].input.inputHash);

    test.dispose();
  });
});
