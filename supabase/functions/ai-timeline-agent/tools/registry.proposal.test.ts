/**
 * M10 T11: Edge unit tests for ai-timeline-agent proposal mode.
 *
 * Covers:
 *  - Supported command conversion to proposal patches
 *  - Validation diagnostics for unsupported / unparseable commands
 *  - Stale base rejection metadata (version snapshot)
 *  - Failed conversion diagnostics
 *  - Unchanged apply-mode persistence semantics (apply mode still saves)
 *
 * @module registry.proposal.test
 * @milestone M10
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

// Hoist mocks before the module import so they take effect during loading.
const registryMocks = vi.hoisted(() => ({
  loadTimelineState: vi.fn(),
  saveTimelineConfigVersioned: vi.fn(),
}));
vi.mock('../db.ts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../db.ts')>();
  return {
    ...actual,
    loadTimelineState: (...args: unknown[]) => registryMocks.loadTimelineState(...args),
    saveTimelineConfigVersioned: (...args: unknown[]) =>
      registryMocks.saveTimelineConfigVersioned(...args),
  };
});

import { executeCommand } from './registry.ts';
import type {
  TimelineConfig,
  AssetRegistry,
} from '../../../../src/tools/video-editor/types/index.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeConfig(
  tracks: { id: string; label: string; kind: string }[] = [],
): TimelineConfig {
  return { clips: [], tracks } as unknown as TimelineConfig;
}

function makeRegistry(
  assets: Record<string, { duration?: number }> = {},
): AssetRegistry {
  return { assets } as unknown as AssetRegistry;
}

function makeState(
  overrides?: Partial<{
    config: TimelineConfig;
    configVersion: number;
    registry: AssetRegistry;
    projectId: string;
    shotNamesById: Record<string, string>;
  }>,
) {
  return {
    config: overrides?.config ?? makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    configVersion: overrides?.configVersion ?? 5,
    registry: overrides?.registry ?? makeRegistry(),
    projectId: overrides?.projectId ?? 'project-1',
    shotNamesById: overrides?.shotNamesById ?? {},
  } as unknown as import('../types.ts').TimelineState;
}

function makeSupabaseAdmin() {
  return {
    rpc: () => ({
      maybeSingle: async () => ({ data: null, error: null }),
    }),
  } as unknown as import('../types.ts').SupabaseAdmin;
}

beforeEach(() => {
  registryMocks.loadTimelineState.mockReset();
  registryMocks.saveTimelineConfigVersioned.mockReset();
});

// ---------------------------------------------------------------------------
// Supported command conversion to proposal patches
// ---------------------------------------------------------------------------

describe('proposal mode — supported command conversion', () => {
  it('converts a move command string to proposal result', async () => {
    const state = makeState({
      config: {
        clips: [
          { id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 10 },
        ],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
    });
    const result = await executeCommand(
      { command: 'move clip-1 2.5', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('not applied');
    expect(result.result).toContain('Base version: 5');
    expect(result.result).toContain('Patches: 1');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
    // Config should be returned unchanged
    expect(result.config).toBe(state.config);
  });

  it('converts a split command string to proposal result', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 10 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
      configVersion: 3,
    });
    const result = await executeCommand(
      { command: 'split clip-1 4.0', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('Split clip "clip-1"');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
    expect(result.config).toBe(state.config);
  });

  it('converts a trim command string to proposal result', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 10 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
    });
    const result = await executeCommand(
      { command: 'trim clip-1 --from 2 --to 8', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('Update clip "clip-1"');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('converts a delete command string to proposal result', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 5 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
    });
    const result = await executeCommand(
      { command: 'delete clip-1', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('Delete clip "clip-1"');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('converts a set command string to proposal result', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 10 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
    });
    const result = await executeCommand(
      { command: 'set clip-1 speed 2', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('Update clip "clip-1"');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('converts an add-text command string to proposal result', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      { command: 'add-text V1 3 5 hello world', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('Add clip to track "V1"');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('converts a set-text command string to proposal result', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'text', text: 'old' }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
    });
    const result = await executeCommand(
      { command: 'set-text clip-1 new text', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('new text');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('converts a duplicate command string to proposal result', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 5 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
    });
    const result = await executeCommand(
      { command: 'duplicate clip-1 2', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('Add clip to track "clip-1"');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('rejects set-params as unsupported string command (parser does not recognize it)', async () => {
    // set-params and set-theme are not in the string command parser union.
    // They only work via transaction input in proposal mode.
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 10 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
    });
    const result = await executeCommand(
      { command: 'set-params clip-1 {"opacity":0.5}', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    // Parser returns error for unknown command
    expect(result.result).toContain('Unknown command');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('rejects set-theme as unsupported string command (parser does not recognize it)', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      { command: 'set-theme dark', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    // Parser returns error for unknown command
    expect(result.result).toContain('Unknown command');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('converts set-params via transaction in proposal mode', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 10 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
      configVersion: 8,
    });
    const result = await executeCommand(
      {
        transaction: {
          commands: [
            { type: 'set-params', payload: { clipId: 'clip-1', params: { opacity: 0.5 } } },
          ],
        },
        mode: 'proposal',
      },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('Base version: 8');
    expect(result.result).toContain('Patches: 1');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('converts set-theme via transaction in proposal mode', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 9,
    });
    const result = await executeCommand(
      {
        transaction: {
          commands: [
            { type: 'set-theme', payload: { themeId: 'dark' } },
          ],
        },
        mode: 'proposal',
      },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('Base version: 9');
    expect(result.result).toContain('Patches: 1');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('converts a transaction with supported commands to proposal result', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 7,
    });
    const supabaseAdmin = makeSupabaseAdmin();

    const result = await executeCommand(
      {
        transaction: {
          transactionId: 'tx-proposal',
          commands: [
            {
              type: 'add-text',
              payload: { track: 'V1', at: 0, duration: 2, text: 'hello' },
            },
            {
              type: 'add-text',
              payload: { track: 'V1', at: 3, duration: 2, text: 'world' },
            },
          ],
        },
        mode: 'proposal',
      },
      state,
      'timeline-1',
      supabaseAdmin,
    );

    expect(result.result).toContain('PROPOSAL');
    expect(result.result).toContain('Base version: 7');
    expect(result.result).toContain('Patches: 2');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
    expect(result.config).toBe(state.config);
  });

  it('handles proposal mode via string input with mode property (needs valid clip)', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 10 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
    });
    const result = await executeCommand(
      { command: 'move clip-1 1.0', mode: 'proposal' } as any,
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Read-only commands in proposal mode
// ---------------------------------------------------------------------------

describe('proposal mode — read-only commands', () => {
  it('executes view command and returns read-only prefix', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      { command: 'view', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL MODE — read-only, no patches');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('executes query command and returns read-only prefix', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      { command: 'query', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL MODE — read-only, no patches');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('executes find-issues command and returns read-only prefix', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      { command: 'find-issues', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL MODE — read-only, no patches');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Validation diagnostics for unsupported / unparseable commands
// ---------------------------------------------------------------------------

describe('proposal mode — validation diagnostics', () => {
  it('rejects unsupported command types with diagnostic', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      { command: 'generate a cat', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('Proposal mode does not support command type');
    expect(result.result).toContain('generate');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('rejects unsupported command types in transactions with diagnostic', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      {
        transaction: {
          commands: [
            {
              type: 'unknown-cmd',
              payload: {},
            },
          ],
        },
        mode: 'proposal',
      },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('Proposal mode does not support command type');
    expect(result.result).toContain('unknown-cmd');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('returns error for unparseable command string', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      { command: '', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    // Empty or invalid command should produce an error message
    expect(typeof result.result).toBe('string');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('returns error for missing clip in validation', async () => {
    const state = makeState({
      config: {
        clips: [],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
      configVersion: 2,
    });
    const result = await executeCommand(
      { command: 'move missing-clip 5', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('not found');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('returns comprehensive list of supported commands in rejection message', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      { command: 'undo', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('Proposal mode does not support command type');
    expect(result.result).toContain('Supported types:');
    expect(result.result).toContain('move');
    expect(result.result).toContain('split');
    expect(result.result).toContain('trim');
    expect(result.result).toContain('delete');
    expect(result.result).toContain('set');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Stale base rejection metadata
// ---------------------------------------------------------------------------

describe('proposal mode — stale base rejection metadata', () => {
  it('captures base version in proposal result text', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 42,
    });
    const result = await executeCommand(
      { command: 'move clip-1 1.0', mode: 'proposal' },
      {
        ...state,
        config: {
          ...state.config,
          clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 5 }],
        } as unknown as TimelineConfig,
      },
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('Base version: 42');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('returns config as-is (stale base is not mutated)', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 5 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
      configVersion: 10,
    });
    const originalConfig = state.config;
    const result = await executeCommand(
      { command: 'delete clip-1', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.config).toBe(originalConfig);
    expect(state.config).toBe(originalConfig);
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('does not modify state.configVersion in proposal mode', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 5 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
      configVersion: 15,
    });
    await executeCommand(
      { command: 'move clip-1 2.0', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(state.configVersion).toBe(15);
  });
});

// ---------------------------------------------------------------------------
// Failed conversion diagnostics
// ---------------------------------------------------------------------------

describe('proposal mode — failed conversion diagnostics', () => {
  it('returns error message when no command or transaction provided', async () => {
    const state = makeState();
    const result = await executeCommand(
      { mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('Proposal mode requires a command string or transaction object');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('returns error for error-typed parsed command', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    // A command that parses to an error type
    const result = await executeCommand(
      { command: '   ', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    // Whitespace-only should trigger an error
    expect(typeof result.result).toBe('string');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Unchanged apply-mode persistence semantics
// ---------------------------------------------------------------------------

describe('proposal mode — unchanged apply-mode persistence', () => {
  it('apply mode still saves timeline config (unchanged behavior)', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 1,
    });
    const supabaseAdmin = makeSupabaseAdmin();
    registryMocks.saveTimelineConfigVersioned.mockResolvedValue(2);

    const result = await executeCommand(
      {
        transaction: {
          commands: [
            {
              type: 'add-text',
              payload: { track: 'V1', at: 3, duration: 2, text: 'hello' },
            },
          ],
        },
        mode: 'apply',
      },
      state,
      'timeline-1',
      supabaseAdmin,
    );

    expect(result.result).toContain('Applied');
    expect(registryMocks.saveTimelineConfigVersioned).toHaveBeenCalled();
    expect(state.configVersion).toBe(2);
  });

  it('validate mode does not save (unchanged behavior)', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      {
        transaction: {
          transactionId: 'tx-val',
          commands: [
            {
              type: 'add-text',
              payload: { track: 'V1', at: 3, duration: 2, text: 'hello' },
            },
          ],
        },
        mode: 'validate',
      },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('Validated');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('dry_run mode does not save (unchanged behavior)', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      {
        transaction: {
          transactionId: 'tx-dry',
          commands: [
            {
              type: 'add-text',
              payload: { track: 'V1', at: 3, duration: 2, text: 'hello' },
            },
          ],
        },
        mode: 'dry_run',
      },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('Dry ran');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('proposal mode and apply mode produce different output prefixes', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 1,
    });
    const supabaseAdmin = makeSupabaseAdmin();
    registryMocks.saveTimelineConfigVersioned.mockResolvedValue(2);

    const proposalResult = await executeCommand(
      {
        transaction: {
          commands: [
            {
              type: 'add-text',
              payload: { track: 'V1', at: 3, duration: 2, text: 'hello' },
            },
          ],
        },
        mode: 'proposal',
      },
      state,
      'timeline-1',
      supabaseAdmin,
    );
    expect(proposalResult.result).toContain('PROPOSAL');
    expect(proposalResult.result).toContain('not applied');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();

    // Reset and test apply mode
    const applyState = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 1,
    });
    registryMocks.saveTimelineConfigVersioned.mockResolvedValue(2);

    const applyResult = await executeCommand(
      {
        transaction: {
          commands: [
            {
              type: 'add-text',
              payload: { track: 'V1', at: 3, duration: 2, text: 'hello' },
            },
          ],
        },
        mode: 'apply',
      },
      applyState,
      'timeline-1',
      supabaseAdmin,
    );
    expect(applyResult.result).toContain('Applied');
    expect(registryMocks.saveTimelineConfigVersioned).toHaveBeenCalled();
  });

  it('proposal mode does not mutate state config', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 5 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
      configVersion: 3,
    });
    const clipsBefore = [...state.config.clips];
    const versionBefore = state.configVersion;

    await executeCommand(
      { command: 'move clip-1 0.5', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    // State must be unchanged
    expect(state.config.clips).toEqual(clipsBefore);
    expect(state.configVersion).toBe(versionBefore);
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('apply mode still handles string commands normally (preserves single summary)', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 1,
    });
    const supabaseAdmin = makeSupabaseAdmin();
    registryMocks.saveTimelineConfigVersioned.mockResolvedValue(2);

    const result = await executeCommand(
      'add-text V1 0 2 hello',
      state,
      'timeline-1',
      supabaseAdmin,
    );

    // Single string command in apply mode preserves the single summary (not "Applied X/Y")
    expect(result.result).toContain('Added text clip');
    expect(registryMocks.saveTimelineConfigVersioned).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// M3: Structured proposal envelope — object shape, not just text
// ---------------------------------------------------------------------------

describe('proposal mode — structured proposal envelope', () => {
  it('returns a proposals array alongside the result text', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 5 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
      configVersion: 5,
    });
    const result = await executeCommand(
      { command: 'move clip-1 2.0', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    // Currently the result is a flat ToolResult with text in .result.
    // The M3 contract requires a structured proposals envelope so the
    // client can render ProposalPanel without parsing text.
    // This expectation will fail until the edge returns structured data.
    expect(result).toHaveProperty('proposals');
    expect(Array.isArray((result as any).proposals)).toBe(true);
  });

  it('each proposal in the envelope has id, source, state, and patch', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 5 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
      configVersion: 3,
    });
    const result = await executeCommand(
      { command: 'delete clip-1', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    const proposals = (result as any).proposals;
    if (!proposals || proposals.length === 0) {
      // When structured envelopes are implemented, this will pass.
      // Until then the test documents the expected contract.
      expect(proposals).toBeDefined();
      expect(proposals.length).toBeGreaterThanOrEqual(1);
      return;
    }

    const p = proposals[0];
    expect(typeof p.id).toBe('string');
    expect(typeof p.source).toBe('string');
    expect(p.state).toBe('pending');
    expect(p.patch).toBeDefined();
    expect(typeof p.patch.version).toBe('number');
    expect(Array.isArray(p.patch.operations)).toBe(true);
  });

  it('proposal envelope includes baseVersion and rationale', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 10 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
      configVersion: 7,
    });
    const result = await executeCommand(
      { command: 'trim clip-1 --from 2 --to 8', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    const proposals = (result as any).proposals;
    if (!proposals || proposals.length === 0) {
      expect(proposals).toBeDefined();
      return;
    }

    const p = proposals[0];
    expect(typeof p.baseVersion).toBe('number');
    expect(p.baseVersion).toBe(7);
    expect(typeof p.rationale).toBe('string');
    expect(p.rationale.length).toBeGreaterThan(0);
  });

  it('proposal envelope omits config mutation (config returned as-is)', async () => {
    const state = makeState({
      config: {
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'media', from: 0, to: 5 }],
        tracks: [{ id: 'V1', label: 'V1', kind: 'visual' }],
      } as unknown as TimelineConfig,
      configVersion: 4,
    });
    const originalConfig = state.config;
    const result = await executeCommand(
      { command: 'move clip-1 1.5', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    // The returned config must be the original (unchanged).
    expect(result.config).toBe(originalConfig);
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();

    // If structured proposals exist, they should NOT contain a mutated config
    const proposals = (result as any).proposals;
    if (proposals && proposals.length > 0) {
      for (const p of proposals) {
        expect(p).not.toHaveProperty('config');
      }
    }
  });
});

// ---------------------------------------------------------------------------
// M3: create_shot blocked in proposal mode
// ---------------------------------------------------------------------------

const createShotMocks = vi.hoisted(() => ({
  createShotWithGenerations: vi.fn(),
}));

describe('proposal mode — create_shot blocked', () => {
  beforeEach(() => {
    createShotMocks.createShotWithGenerations.mockReset();
  });

  it('returns a blocked/rejected result when create_shot is invoked in proposal mode', async () => {
    // create_shot is dispatched through executeToolCall in loop.ts, not
    // executeCommand.  We import executeToolCall and mock the clips
    // dependency so we can verify the proposal-mode gate.
    vi.mock('../tools/clips.ts', () => ({
      createShotWithGenerations: createShotMocks.createShotWithGenerations,
    }));

    const { executeToolCall } = await import('../loop.ts');

    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 1,
    });

    // Invoke a create_shot tool call.  Without proposal_policy gating,
    // this would execute normally.  With proposal_policy='always',
    // it should return a blocked/rejected result.
    // The current code does not check proposal_policy for create_shot,
    // so this expectation will fail until M3 wires the gate.
    const result = await executeToolCall(
      {
        id: 'tc-1',
        name: 'create_shot',
        args: { shot_name: 'Test Shot', generation_ids: ['gen-1'] },
        parseError: null,
      },
      state,
      makeSupabaseAdmin(),
      'timeline-1',
    );

    // create_shot should NOT have been called when proposal mode is active
    // (once the gate is wired).  Currently this fails because no gate exists.
    expect(createShotMocks.createShotWithGenerations).not.toHaveBeenCalled();

    // Result should indicate the operation was blocked, not executed
    expect(result.result).toContain('blocked');
  });

  it('does not mutate database rows when create_shot is blocked in proposal mode', async () => {
    vi.mock('../tools/clips.ts', () => ({
      createShotWithGenerations: createShotMocks.createShotWithGenerations,
    }));

    const { executeToolCall } = await import('../loop.ts');

    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 1,
    });

    await executeToolCall(
      {
        id: 'tc-1',
        name: 'create_shot',
        args: { shot_name: 'Test Shot', generation_ids: ['gen-1'] },
        parseError: null,
      },
      state,
      makeSupabaseAdmin(),
      'timeline-1',
    );

    // No database writes should have occurred
    expect(createShotMocks.createShotWithGenerations).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// M3: Non-timeline side-effect tools remain operational in proposal mode
// ---------------------------------------------------------------------------

describe('proposal mode — non-timeline side-effect tools', () => {
  it('allows read-only query commands in proposal mode without blocking', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
    });
    const result = await executeCommand(
      { command: 'view', mode: 'proposal' },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    // Read-only commands still work and return timeline info
    expect(result.result).toContain('PROPOSAL MODE');
    expect(result.result).toContain('read-only');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it('does not save timeline config for non-timeline tool results in proposal mode', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 1,
    });

    // Even for commands that would normally mutate in apply mode,
    // proposal mode must not save.
    const result = await executeCommand(
      {
        transaction: {
          commands: [
            {
              type: 'set-theme',
              payload: { themeId: 'dark' },
            },
          ],
        },
        mode: 'proposal',
      },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
    expect(result.config).toBe(state.config);
  });

  it('classifies set_theme and set_theme_overrides as proposal-safe', async () => {
    const state = makeState({
      config: makeConfig([{ id: 'V1', label: 'V1', kind: 'visual' }]),
      configVersion: 2,
    });

    // set_theme should be converted to a proposal patch, not applied
    const result = await executeCommand(
      {
        transaction: {
          commands: [
            { type: 'set-theme-overrides', payload: { overrides: { spacing: 'compact' } } },
          ],
        },
        mode: 'proposal',
      },
      state,
      'timeline-1',
      makeSupabaseAdmin(),
    );

    expect(result.result).toContain('PROPOSAL');
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });
});
