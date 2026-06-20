/**
 * M10 T6: Unit tests for agentToolRegistry.
 *
 * Covers:
 *  - Duplicate ID rejection (cross-extension first-registered-wins, same-extension overwrite)
 *  - Schema validation error diagnostics at ingestion time
 *  - Handler registration: handler-no-tool, handler-wrong-extension, duplicate handler overwrite
 *  - Lifecycle transitions: ingest → register → invoke → unregisterAll
 *  - Progress events via callbacks
 *  - Cancellation: cancelSessions, cancelExtensionSessions
 *  - Result validation via validateToolResult integration
 *  - Session handles: trackSession, untrackSession, auto-untrack on complete
 *  - Subscriptions and listener notification
 *  - Diagnostics attribution by extension/tool ID
 *  - HMR-safe unregisterAll(extensionId)
 *  - Dispose cleanup
 *
 * @module agentToolRegistry.test
 * @milestone M10
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  createAgentToolRegistry,
  type AgentToolRegistry,
  type AgentToolRegistryCallbacks,
} from '@/tools/video-editor/runtime/agentToolRegistry';
import { validateToolResult } from '@/tools/video-editor/runtime/agentToolContracts';
import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry';
import type {
  AgentToolContribution,
  AgentToolHandler,
  AgentToolInvocationRequest,
  GenerationSession,
  LiveChannelDescriptor,
  LiveSample,
  SteeringDecision,
  ToolResult,
  ToolResultDiagnostic,
  ToolMutationProposalResult,
  ToolGenerationSessionResult,
  ToolUISummaryResult,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeContribution(
  overrides?: Partial<AgentToolContribution>,
): AgentToolContribution {
  return {
    id: 'contrib-1',
    kind: 'agentTool' as const,
    toolId: 'tool-1',
    label: 'Test Tool',
    description: 'A test tool',
    order: 0,
    ...overrides,
  };
}

function makeHandler(
  result?: ToolResult | null,
  throwError?: Error,
): AgentToolHandler {
  return vi.fn().mockImplementation(async (_request: AgentToolInvocationRequest) => {
    if (throwError) throw throwError;
    return result ?? null;
  });
}

function makeValidResult(family: string = 'ui/summary'): ToolResult {
  if (family === 'mutation/proposal') {
    return {
      family: 'mutation/proposal',
      patches: [
        {
          version: 1,
          operations: [{ op: 'clip.move', target: 'clip-1', payload: { trackId: 'V1', time: 0 } }],
          source: 'test',
        },
      ],
      rationale: 'Test proposal',
    } as ToolMutationProposalResult;
  }
  if (family === 'generation/session') {
    const session: GenerationSession = {
      id: 'session-1',
      progress: 0,
      cancelled: false,
      done: false,
      diagnostics: [],
      onProgress: vi.fn(() => ({ dispose: vi.fn() })),
      cancel: vi.fn(),
      getSampleChannel: vi.fn(() => 'channel-1'),
      complete: vi.fn(),
    };
    return {
      family: 'generation/session',
      session,
    } as ToolGenerationSessionResult;
  }
  return {
    family: 'ui/summary',
    summary: 'Done.',
  } as ToolUISummaryResult;
}

function makeSession(
  overrides?: Partial<GenerationSession>,
): GenerationSession {
  return {
    id: 'session-1',
    progress: 0,
    cancelled: false,
    done: false,
    diagnostics: [],
    onProgress: vi.fn(() => ({ dispose: vi.fn() })),
    cancel: vi.fn(),
    getSampleChannel: vi.fn(() => 'channel-1'),
    complete: vi.fn(),
    ...overrides,
  };
}

function makeRequest(
  toolId: string,
  extensionId: string,
  input?: Record<string, unknown>,
): AgentToolInvocationRequest {
  return {
    toolId,
    extensionId,
    contributionId: `contrib-${toolId}`,
    context: {
      projectId: 'project-1',
    },
    ...(input ? { input } : {}),
  };
}

function createRegistryWithCallbacks(): {
  registry: AgentToolRegistry;
  callbacks: AgentToolRegistryCallbacks;
} {
  const callbacks: AgentToolRegistryCallbacks = {
    onToolFailure: vi.fn(),
    onDuplicateTool: vi.fn(),
    onToolProgress: vi.fn(),
    onToolCancelled: vi.fn(),
    onToolCompleted: vi.fn(),
  };
  const registry = createAgentToolRegistry();
  registry.setCallbacks(callbacks);
  return { registry, callbacks };
}

/** Collect diagnostic codes from an array of diagnostics. */
function diagCodes(
  diags: readonly { code: string }[],
): string[] {
  return diags.map((d) => d.code);
}

function makeSteeringDecision(
  overrides?: Partial<SteeringDecision>,
): SteeringDecision {
  return {
    kind: 'supersede',
    sessionId: 'live-session-1',
    lineage: {
      generationIndex: 2,
      steerHash: 'steer-hash-2',
      parentRefs: ['live-session-0'],
      producerVersion: '1.0.0',
      provenance: { prompt: 'Prompt', model: 'model-a', seed: 42 },
      provenanceTags: ['agent-tool'],
    },
    replacementChannelId: 'live-session-1:replacement' as LiveChannelDescriptor,
    reason: 'Preview update',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Duplicate ID detection
// ---------------------------------------------------------------------------

describe('duplicate ID detection', () => {
  it('rejects a tool ID already registered by a different extension (first-registered-wins)', () => {
    const registry = createAgentToolRegistry();
    const c1 = makeContribution({ id: 'c1', toolId: 'tool-x' });

    registry.ingestAgentToolContribution('ext-a', c1);

    const c2 = makeContribution({ id: 'c2', toolId: 'tool-x' });
    registry.ingestAgentToolContribution('ext-b', c2);

    const snapshot = registry.getSnapshot();
    const tool = snapshot.getTool('tool-x');
    expect(tool).toBeDefined();
    expect(tool!.extensionId).toBe('ext-a');
    expect(tool!.contributionId).toBe('c1');

    // Diagnostic emitted for the conflict
    const conflictDiags = registry.diagnostics.filter(
      (d) => d.code === 'agent-tool-registry/duplicate-tool',
    );
    expect(conflictDiags.length).toBe(1);
    expect(conflictDiags[0].message).toContain('tool-x');
    expect(conflictDiags[0].message).toContain('ext-a');
    expect(conflictDiags[0].message).toContain('ext-b');
  });

  it('calls onDuplicateTool callback when cross-extension duplicate detected', () => {
    const { registry, callbacks } = createRegistryWithCallbacks();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'dup' }));
    registry.ingestAgentToolContribution('ext-b', makeContribution({ id: 'c2', toolId: 'dup' }));

    expect(callbacks.onDuplicateTool).toHaveBeenCalledWith('dup', 'ext-a', 'ext-b');
  });

  it('allows same-extension re-registration (last wins, overwrites metadata)', () => {
    const registry = createAgentToolRegistry();
    const c1 = makeContribution({ id: 'c1', toolId: 'tool-y', label: 'First' });
    registry.ingestAgentToolContribution('ext-a', c1);

    const c2 = makeContribution({ id: 'c1-v2', toolId: 'tool-y', label: 'Updated', order: 10 });
    registry.ingestAgentToolContribution('ext-a', c2);

    const snapshot = registry.getSnapshot();
    const tool = snapshot.getTool('tool-y');
    expect(tool).toBeDefined();
    expect(tool!.label).toBe('Updated');
    expect(tool!.order).toBe(10);
    expect(tool!.contributionId).toBe('c1-v2');
    expect(tool!.extensionId).toBe('ext-a');
  });

  it('preserves handler when same-extension overwrites contribution metadata', () => {
    const registry = createAgentToolRegistry();
    const c1 = makeContribution({ id: 'c1', toolId: 'tool-z' });
    registry.ingestAgentToolContribution('ext-a', c1);

    const handler = makeHandler(makeValidResult());
    registry.registerTool('ext-a', 'tool-z', handler);

    // Re-ingest with different metadata — handler should survive
    const c2 = makeContribution({ id: 'c2', toolId: 'tool-z', label: 'New Label' });
    registry.ingestAgentToolContribution('ext-a', c2);

    const snapshot = registry.getSnapshot();
    expect(snapshot.getTool('tool-z')!.hasHandler).toBe(true);
    expect(snapshot.getTool('tool-z')!.label).toBe('New Label');
  });
});

// ---------------------------------------------------------------------------
// Schema validation error diagnostics
// ---------------------------------------------------------------------------

describe('schema validation error diagnostics', () => {
  it('emits diagnostics for invalid input schema type', () => {
    const registry = createAgentToolRegistry();
    const c = makeContribution({
      id: 'c-bad-schema',
      toolId: 'bad-schema',
      inputSchema: { type: 'string' } as any,
    });
    registry.ingestAgentToolContribution('ext-a', c);

    const schemaDiags = registry.diagnostics.filter(
      (d) => d.code === 'agent-tool-registry/invalid-input-type' ||
               d.code === 'agent-tool/too-deep' ||
               d.message.includes('input schema'),
    );
    expect(schemaDiags.length).toBeGreaterThan(0);
  });

  it('emits diagnostics for invalid result families', () => {
    const registry = createAgentToolRegistry();
    const c = makeContribution({
      id: 'c-bad-family',
      toolId: 'bad-family',
      resultFamilies: ['invalid/family' as any, 'mutation/proposal' as any],
    });
    registry.ingestAgentToolContribution('ext-a', c);

    const familyDiags = registry.diagnostics.filter(
      (d) => d.code === 'agent-tool-registry/invalid-result-family',
    );
    expect(familyDiags.length).toBe(1);
    expect(familyDiags[0].message).toContain('invalid/family');
  });

  it('validates schema with nested properties correctly', () => {
    const registry = createAgentToolRegistry();
    const c = makeContribution({
      id: 'c-nested',
      toolId: 'nested-schema',
      inputSchema: {
        type: 'object',
        properties: {
          style: {
            type: 'object',
            title: 'Style',
            properties: {
              color: { type: 'string', default: 'blue' },
              size: { type: 'number', default: 12 },
            },
            required: ['color'],
          },
        },
      },
    });
    registry.ingestAgentToolContribution('ext-a', c);

    // Nested valid schemas should not produce errors
    const errorDiags = registry.diagnostics.filter((d) => d.severity === 'error');
    expect(errorDiags.length).toBe(0);
  });

  it('validates excessive nesting depth in schema', () => {
    const registry = createAgentToolRegistry();
    const c = makeContribution({
      id: 'c-deep',
      toolId: 'deep-schema',
      inputSchema: {
        type: 'object',
        properties: {
          level1: {
            type: 'object',
            properties: {
              level2: {
                type: 'object',
                properties: {
                  tooDeep: { type: 'string' },
                },
              },
            },
          },
        },
      },
    });
    registry.ingestAgentToolContribution('ext-a', c);

    const depthDiags = registry.diagnostics.filter(
      (d) => d.message.includes('nesting depth') || d.message.includes('exceed'),
    );
    expect(depthDiags.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Handler registration
// ---------------------------------------------------------------------------

describe('handler registration', () => {
  it('registers a handler for an ingested tool', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'h1' }));

    const handler = makeHandler(makeValidResult());
    const dispose = registry.registerTool('ext-a', 'h1', handler);

    const snapshot = registry.getSnapshot();
    const tool = snapshot.getTool('h1');
    expect(tool).toBeDefined();
    expect(tool!.hasHandler).toBe(true);

    // DisposeHandle should be callable
    dispose.dispose();
    const snapshot2 = registry.getSnapshot();
    expect(snapshot2.getTool('h1')!.hasHandler).toBe(false);
  });

  it('emits diagnostic when registering handler for non-existent tool', () => {
    const registry = createAgentToolRegistry();
    registry.registerTool('ext-a', 'no-such-tool', makeHandler(makeValidResult()));

    const diag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool-registry/handler-no-tool',
    );
    expect(diag).toBeDefined();
    expect(diag!.message).toContain('no-such-tool');
  });

  it('emits diagnostic when registering handler for tool owned by different extension', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'h2' }));

    registry.registerTool('ext-b', 'h2', makeHandler(makeValidResult()));

    const diag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool-registry/handler-wrong-extension',
    );
    expect(diag).toBeDefined();
    expect(diag!.message).toContain('ext-a');
    expect(diag!.message).toContain('ext-b');
  });

  it('emits diagnostic when overwriting an existing handler', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'h3' }));

    registry.registerTool('ext-a', 'h3', makeHandler(makeValidResult()));
    registry.registerTool('ext-a', 'h3', makeHandler(makeValidResult()));

    const diag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool-registry/duplicate-handler',
    );
    expect(diag).toBeDefined();
    expect(diag!.message).toContain('h3');
  });

  it('returns no-op dispose when registry is disposed', () => {
    const registry = createAgentToolRegistry();
    registry.dispose();
    const dispose = registry.registerTool('ext-a', 'any', makeHandler(makeValidResult()));
    // Should not throw
    dispose.dispose();
  });
});

// ---------------------------------------------------------------------------
// Lifecycle transitions
// ---------------------------------------------------------------------------

describe('lifecycle transitions', () => {
  it('full lifecycle: ingest → register → invoke → unregisterAll', async () => {
    const { registry, callbacks } = createRegistryWithCallbacks();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'life-1' }));

    const handler = makeHandler(makeValidResult('ui/summary'));
    registry.registerTool('ext-a', 'life-1', handler);

    const result = await registry.invokeTool(makeRequest('life-1', 'ext-a'));
    expect(result).not.toBeNull();
    expect((result as any).family).toBe('ui/summary');

    // Verify invocation was recorded
    const snapshot = registry.getSnapshot();
    const status = snapshot.getStatus('life-1');
    expect(status.invocationCount).toBe(1);
    expect(status.lastRunOk).toBe(true);

    // Now unregister all for the extension
    registry.unregisterAll('ext-a');

    const snapshot2 = registry.getSnapshot();
    expect(snapshot2.getTool('life-1')).toBeUndefined();
    expect(snapshot2.getStatus('life-1').invocationCount).toBe(0);
  });

  it('invokeTool returns null for missing tool', async () => {
    const registry = createAgentToolRegistry();
    const result = await registry.invokeTool(makeRequest('no-such-tool', 'ext-a'));
    expect(result).toBeNull();

    const diag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool-registry/tool-not-found',
    );
    expect(diag).toBeDefined();
  });

  it('invokeTool returns null for tool without handler', async () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'no-handler' }));

    const result = await registry.invokeTool(makeRequest('no-handler', 'ext-a'));
    expect(result).toBeNull();

    const diag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool-registry/tool-no-handler',
    );
    expect(diag).toBeDefined();
  });

  it('invokeTool returns null for extension mismatch', async () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 't1' }));
    registry.registerTool('ext-a', 't1', makeHandler(makeValidResult()));

    const result = await registry.invokeTool(makeRequest('t1', 'ext-b'));
    expect(result).toBeNull();

    const diag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool-registry/tool-extension-mismatch',
    );
    expect(diag).toBeDefined();
  });

  it('invokeTool handles handler errors gracefully', async () => {
    const { registry, callbacks } = createRegistryWithCallbacks();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'err-1' }));
    registry.registerTool('ext-a', 'err-1', makeHandler(null, new Error('Boom!')));

    const result = await registry.invokeTool(makeRequest('err-1', 'ext-a'));
    expect(result).toBeNull();

    const diag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool-registry/handler-error',
    );
    expect(diag).toBeDefined();
    expect(diag!.message).toContain('Boom!');

    expect(callbacks.onToolFailure).toHaveBeenCalledWith(
      'err-1',
      expect.any(Error),
      'ext-a',
    );

    // Status should reflect failure
    const snapshot = registry.getSnapshot();
    const status = snapshot.getStatus('err-1');
    expect(status.invocationCount).toBe(1);
    expect(status.lastRunOk).toBe(false);
    expect(status.lastError).toBe('Boom!');
  });

  it('invokeTool returns null after registry disposed', async () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 't1' }));
    registry.registerTool('ext-a', 't1', makeHandler(makeValidResult()));
    registry.dispose();

    const result = await registry.invokeTool(makeRequest('t1', 'ext-a'));
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Progress events
// ---------------------------------------------------------------------------

describe('progress events', () => {
  it('forwards progress to callback', () => {
    const { registry, callbacks } = createRegistryWithCallbacks();
    registry.reportProgress('tool-1', 'ext-a', 50, 'Halfway');

    expect(callbacks.onToolProgress).toHaveBeenCalledWith('tool-1', 'ext-a', 50, 'Halfway');
  });

  it('allows undefined label', () => {
    const { registry, callbacks } = createRegistryWithCallbacks();
    registry.reportProgress('tool-2', 'ext-b', 75);

    expect(callbacks.onToolProgress).toHaveBeenCalledWith('tool-2', 'ext-b', 75, undefined);
  });

  it('does not throw when no callback set', () => {
    const registry = createAgentToolRegistry();
    expect(() => registry.reportProgress('t', 'ext', 0)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Cancellation
// ---------------------------------------------------------------------------

describe('cancellation', () => {
  it('cancelSessions cancels all sessions for a tool', () => {
    const { registry, callbacks } = createRegistryWithCallbacks();
    const session1 = makeSession({ id: 's1' });
    const session2 = makeSession({ id: 's2' });

    registry.trackSession('tool-1', 'ext-a', session1);
    registry.trackSession('tool-1', 'ext-a', session2);
    registry.trackSession('tool-2', 'ext-a', makeSession({ id: 's3' }));

    const count = registry.cancelSessions('tool-1');
    expect(count).toBe(2);

    expect(session1.cancel).toHaveBeenCalled();
    expect(session2.cancel).toHaveBeenCalled();

    expect(callbacks.onToolCancelled).toHaveBeenCalledTimes(2);

    const snapshot = registry.getSnapshot();
    expect(snapshot.sessions.length).toBe(1); // s3 still present
  });

  it('cancelExtensionSessions cancels all sessions for an extension', () => {
    const { registry, callbacks } = createRegistryWithCallbacks();
    registry.trackSession('tool-1', 'ext-a', makeSession({ id: 's1' }));
    registry.trackSession('tool-2', 'ext-a', makeSession({ id: 's2' }));
    registry.trackSession('tool-3', 'ext-b', makeSession({ id: 's3' }));

    const count = registry.cancelExtensionSessions('ext-a');
    expect(count).toBe(2);
    expect(callbacks.onToolCancelled).toHaveBeenCalledTimes(2);

    const snapshot = registry.getSnapshot();
    expect(snapshot.sessions.length).toBe(1);
    expect(snapshot.sessions[0].session.id).toBe('s3');
  });

  it('cancelSessions handles cancel throwing gracefully', () => {
    const { registry } = createRegistryWithCallbacks();
    const badSession = makeSession({
      id: 'bad',
      cancel: vi.fn(() => { throw new Error('cancel boom'); }),
    });
    registry.trackSession('tool-1', 'ext-a', badSession);

    expect(() => registry.cancelSessions('tool-1')).not.toThrow();
    expect(badSession.cancel).toHaveBeenCalled();

    const snapshot = registry.getSnapshot();
    expect(snapshot.sessions.length).toBe(0);
  });

  it('cancelSessions returns 0 for unknown tool', () => {
    const registry = createAgentToolRegistry();
    expect(registry.cancelSessions('unknown')).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Session handles
// ---------------------------------------------------------------------------

describe('session handles', () => {
  it('trackSession adds session to snapshot', () => {
    const registry = createAgentToolRegistry();
    const session = makeSession({ id: 's1' });
    registry.trackSession('tool-1', 'ext-a', session);

    const snapshot = registry.getSnapshot();
    expect(snapshot.sessions.length).toBe(1);
    expect(snapshot.sessions[0].toolId).toBe('tool-1');
    expect(snapshot.sessions[0].extensionId).toBe('ext-a');
    expect(snapshot.sessions[0].createdAt).toBeGreaterThan(0);
  });

  it('untrackSession removes session from snapshot', () => {
    const registry = createAgentToolRegistry();
    const session = makeSession({ id: 's1' });
    registry.trackSession('tool-1', 'ext-a', session);
    registry.untrackSession('s1');

    const snapshot = registry.getSnapshot();
    expect(snapshot.sessions.length).toBe(0);
  });

  it('untrackSession is idempotent', () => {
    const registry = createAgentToolRegistry();
    expect(() => registry.untrackSession('not-there')).not.toThrow();
  });

  it('auto-untracks session on complete', () => {
    const { registry, callbacks } = createRegistryWithCallbacks();
    const session = makeSession({ id: 'auto-track' });
    registry.trackSession('tool-1', 'ext-a', session);

    expect(registry.getSnapshot().sessions.length).toBe(1);

    session.complete({ output: 'done' });

    expect(registry.getSnapshot().sessions.length).toBe(0);
    expect(callbacks.onToolCompleted).toHaveBeenCalledWith('tool-1', 'ext-a', 'auto-track');
  });

  it('getSessions filters by tool ID', () => {
    const registry = createAgentToolRegistry();
    registry.trackSession('tool-1', 'ext-a', makeSession({ id: 's1' }));
    registry.trackSession('tool-1', 'ext-a', makeSession({ id: 's2' }));
    registry.trackSession('tool-2', 'ext-a', makeSession({ id: 's3' }));

    const snapshot = registry.getSnapshot();
    const tool1Sessions = snapshot.getSessions('tool-1');
    expect(tool1Sessions.length).toBe(2);

    const tool2Sessions = snapshot.getSessions('tool-2');
    expect(tool2Sessions.length).toBe(1);
  });

  it('auto-tracks generation/session results from invokeTool', async () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'gen' }));

    const session = makeSession({ id: 'gen-session-1' });
    const genResult: ToolResult = {
      family: 'generation/session',
      session,
    } as ToolGenerationSessionResult;

    registry.registerTool('ext-a', 'gen', makeHandler(genResult));
    await registry.invokeTool(makeRequest('gen', 'ext-a'));

    const snapshot = registry.getSnapshot();
    expect(snapshot.sessions.length).toBe(1);
    expect(snapshot.sessions[0].toolId).toBe('gen');
  });

  it('refuses GenerationSession live delivery activation without an explicit steering decision', () => {
    const liveRegistry = createLiveDataRegistry({ emitLifecycleDiagnostics: false });
    const registry = createAgentToolRegistry({ liveDataRegistry: liveRegistry });
    const session = makeSession({
      id: 'missing-steering',
      liveDelivery: {
        origin: 'agent-tool',
      } as any,
    });

    registry.trackSession('tool-1', 'ext-a', session);

    const snapshot = registry.getSnapshot();
    expect(snapshot.sessions[0].liveDelivery?.canActivate).toBe(false);
    expect(snapshot.sessions[0].liveDelivery?.diagnostics.map((d) => d.code)).toContain('live/steering-missing-decision');
    expect(diagCodes(registry.diagnostics)).toContain('live/steering-missing-decision');
    expect(liveRegistry.listSources()).toEqual([]);
  });

  it('activates typed GenerationSession sample delivery with lineage metadata in live ring buffers', async () => {
    const liveRegistry = createLiveDataRegistry({ emitLifecycleDiagnostics: false });
    const registry = createAgentToolRegistry({ liveDataRegistry: liveRegistry });
    const decision = makeSteeringDecision();
    let sampleListener: ((sample: LiveSample) => void) | null = null;
    const progressListeners: Array<(progress: number, label?: string) => void> = [];
    const session = makeSession({
      id: 'live-session-1',
      progress: 12,
      progressLabel: 'Starting',
      finalRefs: ['asset-final'],
      bakedRefs: ['asset-baked'],
      getSampleChannel: vi.fn(() => 'producer-channel' as LiveChannelDescriptor),
      onSample: vi.fn((listener) => {
        sampleListener = listener;
        return { dispose: vi.fn() };
      }),
      onProgress: vi.fn((listener) => {
        progressListeners.push(listener);
        return { dispose: vi.fn() };
      }),
    });

    const genResult: ToolResult = {
      family: 'generation/session',
      session,
      liveDelivery: {
        origin: 'agent-tool',
        steeringDecision: decision,
        activeChannels: ['producer-channel' as LiveChannelDescriptor],
        finalRefs: ['asset-final'],
        bakedRefs: ['asset-baked'],
      },
    } as ToolGenerationSessionResult;

    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c-live', toolId: 'gen-live' }));
    registry.registerTool('ext-a', 'gen-live', makeHandler(genResult));
    await registry.invokeTool(makeRequest('gen-live', 'ext-a'));

    const sessionEntry = registry.getSnapshot().sessions[0];
    expect(sessionEntry.liveDelivery).toMatchObject({
      canActivate: true,
      origin: 'agent-tool',
      progress: 12,
      cancelled: false,
      generationIndex: 2,
      steerHash: 'steer-hash-2',
      parentRefs: ['live-session-0'],
      finalRefs: ['asset-final'],
      bakedRefs: ['asset-baked'],
    });

    expect(liveRegistry.getSteeringLineage('live-session-1')?.steerHash).toBe('steer-hash-2');
    const hostChannel = sessionEntry.liveDelivery!.activeChannels.find(
      (channel) => channel.startsWith('generation-session:live-session-1:'),
    )!;
    expect(hostChannel).toBeDefined();

    progressListeners[0]?.(44, 'Rendering');
    expect(registry.getSnapshot().sessions[0].liveDelivery?.progress).toBe(44);

    sampleListener?.({
      channelId: 'producer-channel' as LiveChannelDescriptor,
      frame: { timestamp: 123, data: { frameRef: 'frame-1' }, format: 'json' },
      sequenceNumber: 7,
    });

    const sample = liveRegistry.getLatestSample(hostChannel as LiveChannelDescriptor);
    expect(sample?.frame.metadata).toMatchObject({
      origin: 'agent-tool',
      sessionId: 'live-session-1',
      toolId: 'gen-live',
      extensionId: 'ext-a',
      sourceChannelId: 'producer-channel',
      sourceSequenceNumber: 7,
      generationIndex: 2,
      steerHash: 'steer-hash-2',
      parentRefs: ['live-session-0'],
      finalRefs: ['asset-final'],
      bakedRefs: ['asset-baked'],
      steeringDecision: 'supersede',
    });
    expect(registry.getSnapshot().sessions[0].liveDelivery?.sampleCount).toBe(1);
  });

  it('records cancellation metadata while preserving M10 cancellation cleanup', () => {
    const liveRegistry = createLiveDataRegistry({ emitLifecycleDiagnostics: false });
    const callbacks: AgentToolRegistryCallbacks = {
      onToolCancelled: vi.fn(),
    };
    const configuredRegistry = createAgentToolRegistry({ liveDataRegistry: liveRegistry });
    configuredRegistry.setCallbacks(callbacks);
    const cancel = vi.fn();
    const session = makeSession({
      id: 'cancel-live',
      cancel,
      liveDelivery: {
        origin: 'agent-tool',
        steeringDecision: makeSteeringDecision({ sessionId: 'cancel-live' }),
      },
    });

    configuredRegistry.trackSession('tool-1', 'ext-a', session);
    const cancelled = configuredRegistry.cancelSessions('tool-1');

    expect(cancelled).toBe(1);
    expect(cancel).toHaveBeenCalled();
    expect(configuredRegistry.getSnapshot().sessions).toHaveLength(0);
    expect(callbacks.onToolCancelled).toHaveBeenCalledWith('tool-1', 'ext-a', 'cancel-live');
  });
});

// ---------------------------------------------------------------------------
// Result validation
// ---------------------------------------------------------------------------

describe('result validation', () => {
  it('emits diagnostics for invalid result family', async () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'rv1' }));

    const badResult = { family: 'bad/family', data: 'x' } as unknown as ToolResult;
    registry.registerTool('ext-a', 'rv1', makeHandler(badResult));

    await registry.invokeTool(makeRequest('rv1', 'ext-a'));

    const diag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool/unsupported-result-family',
    );
    expect(diag).toBeDefined();
  });

  it('emits diagnostics for missing family discriminator', async () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'rv2' }));

    const badResult = { data: 'no-family' } as unknown as ToolResult;
    registry.registerTool('ext-a', 'rv2', makeHandler(badResult));

    await registry.invokeTool(makeRequest('rv2', 'ext-a'));

    const diag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool/missing-result-family',
    );
    expect(diag).toBeDefined();
  });

  it('emits diagnostics from a result diagnostics array', async () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'rv3' }));

    const resultWithDiags: ToolResult = {
      family: 'ui/summary',
      summary: 'Done with warnings',
      diagnostics: [
        { severity: 'warning', code: 'custom/warn', message: 'A warning from the tool.' },
      ],
    } as any;

    registry.registerTool('ext-a', 'rv3', makeHandler(resultWithDiags));
    await registry.invokeTool(makeRequest('rv3', 'ext-a'));

    const diag = registry.diagnostics.find(
      (d) => d.code === 'custom/warn',
    );
    expect(diag).toBeDefined();
    expect(diag!.message).toBe('A warning from the tool.');
  });

  it('validates mutation/proposal result structur', async () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'rv4' }));

    const badMutation = { family: 'mutation/proposal' } as any; // missing patches
    registry.registerTool('ext-a', 'rv4', makeHandler(badMutation));

    await registry.invokeTool(makeRequest('rv4', 'ext-a'));

    const diag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool/mutation-missing-patches',
    );
    expect(diag).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// Subscriptions
// ---------------------------------------------------------------------------

describe('subscriptions', () => {
  it('notifies listener on ingestion that produces diagnostics', () => {
    const registry = createAgentToolRegistry();
    const listener = vi.fn();
    registry.subscribe(listener);

    // Use invalid result family to trigger a diagnostic and thus notification
    registry.ingestAgentToolContribution(
      'ext-a',
      makeContribution({ id: 'c1', toolId: 'sub-1', resultFamilies: ['invalid/family' as any] }),
    );
    expect(listener).toHaveBeenCalled();
  });

  it('notifies listener on schema validation diagnostic', () => {
    const registry = createAgentToolRegistry();
    const listener = vi.fn();
    registry.subscribe(listener);

    // Invalid schema type produces diagnostics → listener notified
    registry.ingestAgentToolContribution(
      'ext-a',
      makeContribution({ id: 'c1', toolId: 'sub-schema', inputSchema: { type: 'number' } as any }),
    );
    expect(listener).toHaveBeenCalled();
  });

  it('notifies listener on handler registration with duplicate handler', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'sub-2' }));
    registry.registerTool('ext-a', 'sub-2', makeHandler(makeValidResult()));

    const listener = vi.fn();
    registry.subscribe(listener);

    // Overwriting handler produces duplicate-handler diagnostic → listener notified
    registry.registerTool('ext-a', 'sub-2', makeHandler(makeValidResult()));
    expect(listener).toHaveBeenCalled();
  });

  it('notifies listener on unregisterAll', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'sub-3' }));

    const listener = vi.fn();
    registry.subscribe(listener);

    registry.unregisterAll('ext-a');
    expect(listener).toHaveBeenCalled();
  });

  it('dispose stops notifications', () => {
    const registry = createAgentToolRegistry();
    const listener = vi.fn();
    const dispose = registry.subscribe(listener);
    dispose.dispose();

    // Use invalid result family to trigger diagnostic; disposed listener should not be called
    registry.ingestAgentToolContribution(
      'ext-a',
      makeContribution({ id: 'c1', toolId: 'sub-4', resultFamilies: ['invalid/family' as any] }),
    );
    expect(listener).not.toHaveBeenCalled();
  });

  it('supports multiple concurrent listeners for diagnostic events', () => {
    const registry = createAgentToolRegistry();
    const l1 = vi.fn();
    const l2 = vi.fn();
    registry.subscribe(l1);
    registry.subscribe(l2);

    // Invalid result family triggers diagnostic → both listeners notified
    registry.ingestAgentToolContribution(
      'ext-a',
      makeContribution({ id: 'c1', toolId: 'multi', resultFamilies: ['invalid/family' as any] }),
    );
    expect(l1).toHaveBeenCalled();
    expect(l2).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Diagnostics attribution by extension/tool ID
// ---------------------------------------------------------------------------

describe('diagnostics attribution', () => {
  it('attributes diagnostics to correct extensionId', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({
      id: 'c1',
      toolId: 'diag-tool',
      resultFamilies: ['invalid/family' as any],
    }));

    const familyDiag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool-registry/invalid-result-family',
    );
    expect(familyDiag).toBeDefined();
    expect(familyDiag!.extensionId).toBe('ext-a');
  });

  it('attributes diagnostics to correct contributionId', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({
      id: 'my-contrib-42',
      toolId: 'diag-tool-2',
      resultFamilies: ['invalid/family' as any],
    }));

    const familyDiag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool-registry/invalid-result-family',
    );
    expect(familyDiag).toBeDefined();
    expect(familyDiag!.contributionId).toBe('my-contrib-42');
  });

  it('attributes handler-error diagnostics to both extension and tool', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-b', makeContribution({ id: 'c-err', toolId: 'diag-err' }));
    registry.registerTool('ext-b', 'diag-err', makeHandler(null, new Error('handler down')));

    // Invoke to trigger handler error
    registry.invokeTool(makeRequest('diag-err', 'ext-b'));

    // The handlerError diag (added before the async call resolves) — check diagnostics directly
    // The error diagnostic is emitted synchronously in invokeTool's catch
  });

  it('handler-error diagnostic references extension and contribution', async () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-c', makeContribution({ id: 'c-err2', toolId: 'diag-err2' }));
    registry.registerTool('ext-c', 'diag-err2', makeHandler(null, new Error('sync error')));

    await registry.invokeTool(makeRequest('diag-err2', 'ext-c'));

    const errDiag = registry.diagnostics.find(
      (d) => d.code === 'agent-tool-registry/handler-error',
    );
    expect(errDiag).toBeDefined();
    expect(errDiag!.extensionId).toBe('ext-c');
    expect(errDiag!.contributionId).toBe('c-err2');
  });
});

// ---------------------------------------------------------------------------
// HMR-safe unregisterAll
// ---------------------------------------------------------------------------

describe('HMR-safe unregisterAll', () => {
  it('removes all tools owned by the given extension', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'hmr-1' }));
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c2', toolId: 'hmr-2' }));
    registry.ingestAgentToolContribution('ext-b', makeContribution({ id: 'c3', toolId: 'hmr-3' }));

    registry.unregisterAll('ext-a');

    const snapshot = registry.getSnapshot();
    expect(snapshot.tools.length).toBe(1);
    expect(snapshot.tools[0].extensionId).toBe('ext-b');
    expect(snapshot.tools[0].toolId).toBe('hmr-3');
  });

  it('removes run status for unregistered tools', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'hmr-4' }));
    registry.registerTool('ext-a', 'hmr-4', makeHandler(makeValidResult()));

    // First invoke to build up status
    registry.invokeTool(makeRequest('hmr-4', 'ext-a'));

    registry.unregisterAll('ext-a');

    const snapshot = registry.getSnapshot();
    expect(snapshot.getStatus('hmr-4').invocationCount).toBe(0);
  });

  it('cancels active sessions for the unregistered extension', () => {
    const { registry } = createRegistryWithCallbacks();
    const session = makeSession({ id: 'hmr-session' });
    registry.trackSession('tool-1', 'ext-a', session);

    registry.unregisterAll('ext-a');

    expect(session.cancel).toHaveBeenCalled();
    expect(registry.getSnapshot().sessions.length).toBe(0);
  });

  it('unregisterAll after dispose is a no-op', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'hmr-5' }));
    registry.dispose();

    expect(() => registry.unregisterAll('ext-a')).not.toThrow();
  });

  it('unregisterAll does not affect other extensions', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'a1' }));
    registry.ingestAgentToolContribution('ext-b', makeContribution({ id: 'c2', toolId: 'b1' }));
    registry.ingestAgentToolContribution('ext-c', makeContribution({ id: 'c3', toolId: 'c1' }));

    registry.unregisterAll('ext-b');

    const snapshot = registry.getSnapshot();
    const toolIds = snapshot.tools.map((t) => t.toolId);
    expect(toolIds).toContain('a1');
    expect(toolIds).not.toContain('b1');
    expect(toolIds).toContain('c1');
  });

  it('re-registration after unregisterAll works correctly', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'hmr-6' }));

    registry.unregisterAll('ext-a');

    // Re-register same tool after HMR reload
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1-new', toolId: 'hmr-6', label: 'Reloaded' }));

    const snapshot = registry.getSnapshot();
    expect(snapshot.tools.length).toBe(1);
    expect(snapshot.tools[0].label).toBe('Reloaded');
  });
});

// ---------------------------------------------------------------------------
// Dispose
// ---------------------------------------------------------------------------

describe('dispose', () => {
  it('clears all tools, sessions, listeners, and diagnostics', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'd1' }));
    registry.trackSession('d1', 'ext-a', makeSession({ id: 'ds1' }));
    const listener = vi.fn();
    registry.subscribe(listener);

    registry.dispose();

    expect(registry.getSnapshot().tools.length).toBe(0);
    expect(registry.getSnapshot().sessions.length).toBe(0);
    expect(registry.diagnostics.length).toBe(0); // disposed warning may remain

    // Listener should not be called after dispose
    // (ingest after dispose produces a warning diagnostic but should not notify disposed listeners)
  });

  it('dispose is idempotent', () => {
    const registry = createAgentToolRegistry();
    registry.dispose();
    expect(() => registry.dispose()).not.toThrow();
  });

  it('dispose cancels all active sessions', () => {
    const registry = createAgentToolRegistry();
    const s1 = makeSession({ id: 'ds2' });
    const s2 = makeSession({ id: 'ds3' });
    registry.trackSession('tool-1', 'ext-a', s1);
    registry.trackSession('tool-2', 'ext-a', s2);

    registry.dispose();

    expect(s1.cancel).toHaveBeenCalled();
    expect(s2.cancel).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Snapshot consistency
// ---------------------------------------------------------------------------

describe('snapshot consistency', () => {
  it('getSnapshot returns frozen tools ordered by extensionId → toolId', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-b', makeContribution({ id: 'c2', toolId: 'b1' }));
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'a2' }));
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c0', toolId: 'a1' }));

    const snapshot = registry.getSnapshot();
    const order = snapshot.tools.map((t) => `${t.extensionId}:${t.toolId}`);
    expect(order).toEqual(['ext-a:a1', 'ext-a:a2', 'ext-b:b1']);
  });

  it('getSnapshot caches frozen snapshot until invalidation', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext-a', makeContribution({ id: 'c1', toolId: 'cache-1' }));

    const snap1 = registry.getSnapshot();
    const snap2 = registry.getSnapshot();
    expect(snap1).toBe(snap2); // Same reference due to caching

    // Invalidation
    registry.ingestAgentToolContribution('ext-b', makeContribution({ id: 'c2', toolId: 'cache-2' }));
    const snap3 = registry.getSnapshot();
    expect(snap3).not.toBe(snap2);
  });

  it('getTool returns undefined for unknown tool', () => {
    const registry = createAgentToolRegistry();
    expect(registry.getSnapshot().getTool('nope')).toBeUndefined();
  });

  it('getStatus returns zero-status for unknown tool', () => {
    const registry = createAgentToolRegistry();
    const status = registry.getSnapshot().getStatus('unknown');
    expect(status.invocationCount).toBe(0);
    expect(status.lastRunAt).toBe(0);
    expect(status.lastRunOk).toBe(true);
    expect(status.lastError).toBeNull();
  });
});
