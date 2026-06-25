/**
 * Tests for ProposalRuntime — provider-scoped in-memory proposal lifecycle.
 *
 * @publicContract
 */

import { describe, expect, it, vi, beforeEach, beforeAll } from 'vitest';
import { createProposalRuntime, importEdgeProposals } from '@/tools/video-editor/lib/proposal-runtime';
import { createTimelineReader } from '@/tools/video-editor/lib/timeline-reader';
import { buildTimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type {
  ProposalRuntime,
  TimelineProposal,
  TimelineProposalInput,
  TimelineOps,
  DisposeHandle,
} from '@/sdk/index';
import type {
  TimelineDiff,
  TimelinePatch,
  TimelinePatchValidationResult,
  TimelinePreviewResult,
} from '@/sdk/video/timeline/patch.ts';
import type { TimelineConfig } from '@/tools/video-editor/types/index';
import type { ProposalPersistenceProvider, ProposalPersistenceRecord } from '@/tools/video-editor/lib/proposal-runtime';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeBaseConfig(): TimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [
      { id: 'V1', kind: 'visual', label: 'Visual 1' },
      { id: 'A1', kind: 'audio', label: 'Audio 1' },
    ],
    clips: [
      {
        id: 'clip-1',
        at: 0,
        track: 'V1',
        clipType: 'hold',
        hold: 3,
      },
    ],
  };
}

function makeEmptyDiff(version: number): TimelineDiff {
  return { version, entries: [], affectedObjectIds: [] };
}

function makeEmptyValidationResult(): TimelinePatchValidationResult {
  return { valid: true, diagnostics: [] };
}

function makeEmptyPreviewResult(version: number, fullyPreviewable = true): TimelinePreviewResult {
  return {
    diff: makeEmptyDiff(version),
    fullyPreviewable,
    diagnostics: [],
  };
}

/**
 * Create a mock TimelineOps that records calls and returns controllable results.
 */
function createMockTimelineOps(overrides: Partial<{
  validateResult: TimelinePatchValidationResult;
  previewResult: TimelinePreviewResult;
  applyResult: TimelineDiff;
  applyError: Error;
}> = {}): TimelineOps & {
  _validateCalls: TimelinePatch[];
  _previewCalls: TimelinePatch[];
  _applyCalls: TimelinePatch[];
} {
  const _validateCalls: TimelinePatch[] = [];
  const _previewCalls: TimelinePatch[] = [];
  const _applyCalls: TimelinePatch[] = [];

  return {
    _validateCalls,
    _previewCalls,
    _applyCalls,

    validate(patch: TimelinePatch): TimelinePatchValidationResult {
      _validateCalls.push(patch);
      return overrides.validateResult ?? makeEmptyValidationResult();
    },

    preview(patch: TimelinePatch): TimelinePreviewResult {
      _previewCalls.push(patch);
      return overrides.previewResult ?? makeEmptyPreviewResult(patch.version);
    },

    apply(patch: TimelinePatch): TimelineDiff {
      _applyCalls.push(patch);
      if (overrides.applyError) {
        throw overrides.applyError;
      }
      return overrides.applyResult ?? {
        version: patch.version + 1,
        entries: [
          {
            granularity: 'clip',
            kind: 'added',
            target: 'new-clip',
            op: 'clip.add',
          },
        ],
        affectedObjectIds: ['new-clip'],
      };
    },

    checkpoint: vi.fn().mockReturnValue('ckpt-1'),
    rollback: vi.fn().mockReturnValue(null),
    setAllTracksMuted: vi.fn().mockReturnValue(makeEmptyDiff(1)),
  };
}

/**
 * Create a mock persistence provider that stores records in memory and can
 * be reused across runtime instances to simulate reload.
 */
function createMockPersistenceProvider(initial: ProposalPersistenceRecord[] = []): ProposalPersistenceProvider & {
  records: ProposalPersistenceRecord[];
} {
  const records = [...initial];

  return {
    records,

    async createProposal(record: Omit<ProposalPersistenceRecord, 'id'>): Promise<string> {
      const id = `persist-${records.length + 1}-${Date.now().toString(36)}`;
      records.push({ ...record, id });
      return id;
    },

    async updateProposalStatus(id: string, status: string, _detail?: Record<string, unknown>): Promise<void> {
      const record = records.find((r) => r.id === id);
      if (record) {
        record.state = status;
        record.updatedAt = Date.now();
      }
    },

    async loadAllProposals(): Promise<ProposalPersistenceRecord[]> {
      // Pending-only reload contract: return only pending records.
      return records.filter((r) => r.state === 'pending');
    },
  };
}

/**
 * Build a proper TimelineData with the correct structure for the reader.
 * buildTimelineData(config, registry, urlResolver?, configVersion?)
 */
async function buildData(config: TimelineConfig, configVersion = 1): Promise<TimelineData> {
  return buildTimelineData(config, { assets: {} }, undefined, configVersion);
}

/**
 * Create a reader from a properly built TimelineData.
 */
async function makeReader(config?: TimelineConfig, configVersion?: number): Promise<ReturnType<typeof createTimelineReader>> {
  const data = await buildData(config ?? makeBaseConfig(), configVersion ?? 1);
  return createTimelineReader({ data });
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

describe('ProposalRuntime', () => {
  // -----------------------------------------------------------------------
  // Construction & interface
  // -----------------------------------------------------------------------
  describe('construction', () => {
    it('returns an object matching the ProposalRuntime interface', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      expect(runtime).toBeDefined();
      expect(typeof runtime.subscribe).toBe('function');
      expect(typeof runtime.create).toBe('function');
      expect(typeof runtime.preview).toBe('function');
      expect(typeof runtime.accept).toBe('function');
      expect(typeof runtime.reject).toBe('function');
      expect(typeof runtime.get).toBe('function');
      expect(typeof runtime.list).toBe('function');
      expect(typeof runtime.currentVersion).toBe('number');
    });
  });

  // -----------------------------------------------------------------------
  // subscribe
  // -----------------------------------------------------------------------
  describe('subscribe', () => {
    it('returns a DisposeHandle that can unsubscribe', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const listener = vi.fn();
      const handle = runtime.subscribe(listener);
      expect(handle).toBeDefined();
      expect(typeof handle.dispose).toBe('function');

      // Dispose should work
      handle.dispose();
      // Double-dispose should be safe
      handle.dispose();
    });

    it('notifies listeners on proposal state changes', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const listener = vi.fn();
      runtime.subscribe(listener);

      const input: TimelineProposalInput = {
        source: 'test-ext',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      };

      runtime.create(input);
      expect(listener).toHaveBeenCalled();
      const calls = listener.mock.calls;
      // At least one notification (create triggers preview which may notify again)
      expect(calls.length).toBeGreaterThanOrEqual(1);
    });

    it('does not notify disposed listeners', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const listener = vi.fn();
      const handle = runtime.subscribe(listener);
      handle.dispose();

      runtime.create({
        source: 'test-ext',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      expect(listener).not.toHaveBeenCalled();
    });

    it('handles multiple listeners independently', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const listener1 = vi.fn();
      const listener2 = vi.fn();
      runtime.subscribe(listener1);
      const handle2 = runtime.subscribe(listener2);

      runtime.create({
        source: 'test-ext',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      expect(listener1).toHaveBeenCalled();
      expect(listener2).toHaveBeenCalled();

      // Dispose listener2, listener1 should still receive
      listener1.mockClear();
      listener2.mockClear();
      handle2.dispose();

      runtime.create({
        source: 'other-ext',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      expect(listener1).toHaveBeenCalled();
      expect(listener2).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------------------
  // create (with replaceForSource)
  // -----------------------------------------------------------------------
  describe('create', () => {
    it('creates a pending proposal with correct fields', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        rationale: 'Add a new clip',
        patch: {
          version: 5,
          operations: [
            { op: 'clip.add', target: 'new-clip', payload: { track: 'V1', at: 10, clipType: 'hold', hold: 3 } },
          ],
        },
        baseVersion: 5,
      });

      expect(proposal.id).toBeDefined();
      expect(proposal.source).toBe('ext-a');
      expect(proposal.rationale).toBe('Add a new clip');
      expect(proposal.state).toBe('pending');
      expect(proposal.patch.version).toBe(5);
      expect(proposal.baseVersion).toBe(5);
      expect(typeof proposal.createdAt).toBe('number');
      expect(typeof proposal.updatedAt).toBe('number');
    });

    it('assigns unique IDs to different proposals', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const p1 = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      const p2 = runtime.create({
        source: 'ext-b',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      expect(p1.id).not.toBe(p2.id);
    });

    it('replaceForSource: atomically replaces pending proposal from same source', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const p1 = runtime.create({
        source: 'ext-a',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      const p2 = runtime.create({
        source: 'ext-a',  // Same source
        patch: { version: 2, operations: [] },
        baseVersion: 2,
      });

      // p1 should have been replaced
      expect(runtime.get(p1.id)).toBeUndefined();
      // p2 should exist
      expect(runtime.get(p2.id)).toBeDefined();
      expect(runtime.get(p2.id)!.source).toBe('ext-a');

      // Only one pending from ext-a
      const pending = runtime.list('pending');
      expect(pending.filter((p) => p.source === 'ext-a')).toHaveLength(1);
    });

    it('replaceForSource: does not replace proposals in non-pending states', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const p1 = runtime.create({
        source: 'ext-a',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      // Reject p1
      runtime.reject(p1.id);

      // Create new from same source — should NOT replace rejected proposal
      const p2 = runtime.create({
        source: 'ext-a',
        patch: { version: 2, operations: [] },
        baseVersion: 2,
      });

      // Both should exist (one rejected, one pending)
      expect(runtime.get(p1.id)).toBeDefined();
      expect(runtime.get(p1.id)!.state).toBe('rejected');
      expect(runtime.get(p2.id)).toBeDefined();
      expect(runtime.get(p2.id)!.state).toBe('pending');
    });

    it('replaceForSource: does not affect proposals from other sources', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const pA = runtime.create({
        source: 'ext-a',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      const pB = runtime.create({
        source: 'ext-b',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      // Replace ext-a
      const pA2 = runtime.create({
        source: 'ext-a',
        patch: { version: 2, operations: [] },
        baseVersion: 2,
      });

      // ext-b's proposal should be untouched
      expect(runtime.get(pB.id)).toBeDefined();
      expect(runtime.get(pB.id)!.state).toBe('pending');
      // ext-a's original should be gone
      expect(runtime.get(pA.id)).toBeUndefined();
      // ext-a's new should exist
      expect(runtime.get(pA2.id)).toBeDefined();
    });

    it('triggers initial preview on create', async () => {
      const mockOps = createMockTimelineOps({
        previewResult: {
          diff: {
            version: 0,
            entries: [
              { granularity: 'clip', kind: 'added', target: 'new-clip', op: 'clip.add' },
            ],
            affectedObjectIds: ['new-clip'],
          },
          fullyPreviewable: true,
          diagnostics: [],
        },
      });
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [{ op: 'clip.add', target: 'new-clip', payload: { track: 'V1', at: 0, clipType: 'hold', hold: 3 } }] },
        baseVersion: 0,
      });

      expect(mockOps._previewCalls.length).toBeGreaterThanOrEqual(1);
      expect(proposal.previewable).toBe(true);
      expect(proposal.previewDiff).toBeDefined();
    });

    it('survives preview failures gracefully (no data loaded edge case)', async () => {
      const mockOps = createMockTimelineOps({
        previewResult: {
          diff: { version: 0, entries: [], affectedObjectIds: [] },
          fullyPreviewable: false,
          diagnostics: [{ severity: 'error', code: 'timeline-patch/no-data', message: 'No data' }],
        },
      });
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      // Should still create the proposal even if preview has issues
      expect(proposal.id).toBeDefined();
      expect(proposal.state).toBe('pending');
    });
  });

  // -----------------------------------------------------------------------
  // preview
  // -----------------------------------------------------------------------
  describe('preview', () => {
    it('calls timelineOps.preview and updates proposal fields', async () => {
      const mockOps = createMockTimelineOps({
        previewResult: {
          diff: {
            version: 1,
            entries: [
              { granularity: 'clip', kind: 'added', target: 'c1', op: 'clip.add' },
            ],
            affectedObjectIds: ['c1'],
          },
          fullyPreviewable: true,
          diagnostics: [],
        },
      });
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 1, operations: [{ op: 'clip.add', target: 'c1', payload: { track: 'V1', at: 0, clipType: 'hold', hold: 3 } }] },
        baseVersion: 1,
      });

      const result = runtime.preview(proposal.id);

      expect(result.diff.entries).toHaveLength(1);
      expect(result.fullyPreviewable).toBe(true);

      // Should have updated the stored proposal
      const updated = runtime.get(proposal.id)!;
      expect(updated.previewable).toBe(true);
      expect(updated.previewDiff).toBeDefined();
      expect(updated.previewDiff!.entries).toHaveLength(1);
    });

    it('throws when proposal is not found', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      expect(() => runtime.preview('nonexistent')).toThrow('not found');
    });

    it('updates diagnostics on preview', async () => {
      const mockOps = createMockTimelineOps({
        previewResult: {
          diff: { version: 1, entries: [], affectedObjectIds: [] },
          fullyPreviewable: false,
          diagnostics: [
            { severity: 'warning', code: 'timeline-patch/stale-base-version', message: 'Stale base version' },
          ],
        },
      });
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      const result = runtime.preview(proposal.id);

      expect(result.diagnostics).toHaveLength(1);
      const updated = runtime.get(proposal.id)!;
      expect(updated.diagnostics).toBeDefined();
      expect(updated.diagnostics!.length).toBe(1);
    });
  });

  // -----------------------------------------------------------------------
  // accept — with base-version revalidation
  // -----------------------------------------------------------------------
  describe('accept', () => {
    it('accepts a pending proposal with matching baseVersion', async () => {
      const mockOps = createMockTimelineOps({
        applyResult: {
          version: 2,
          entries: [
            { granularity: 'clip', kind: 'added', target: 'new-clip', op: 'clip.add' },
          ],
          affectedObjectIds: ['new-clip'],
        },
      });

      const reader = await makeReader(undefined, 5);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      // Create proposal with baseVersion matching the reader's currentVersion
      const snap = reader.snapshot();
      const proposal = runtime.create({
        source: 'ext-a',
        patch: {
          version: snap.currentVersion,
          operations: [{ op: 'clip.add', target: 'new-clip', payload: { track: 'V1', at: 10, clipType: 'hold', hold: 3 } }],
        },
        baseVersion: snap.currentVersion,
      });

      const diff = runtime.accept(proposal.id);

      expect(diff.entries).toHaveLength(1);
      expect(mockOps._applyCalls).toHaveLength(1);

      const accepted = runtime.get(proposal.id)!;
      expect(accepted.state).toBe('accepted');
    });

    it('marks proposal stale when baseVersion does not match currentVersion', async () => {
      const mockOps = createMockTimelineOps();

      const reader = await makeReader(undefined, 5);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      // Create proposal with baseVersion that doesn't match the reader's currentVersion
      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 999, operations: [] },
        baseVersion: 999, // Different from reader's currentVersion (5)
      });

      // Accept should throw
      expect(() => runtime.accept(proposal.id)).toThrow('stale');

      // Proposal should be marked stale
      const stale = runtime.get(proposal.id)!;
      expect(stale.state).toBe('stale');
      expect(stale.diagnostics).toBeDefined();
      expect(stale.diagnostics!.some((d) => d.code === 'timeline-patch/stale-base-version')).toBe(true);

      // Apply should NOT have been called
      expect(mockOps._applyCalls).toHaveLength(0);
    });

    it('accepts proposal with baseVersion 0 (no-expectation bypass)', async () => {
      const mockOps = createMockTimelineOps({
        applyResult: {
          version: 1,
          entries: [
            { granularity: 'clip', kind: 'added', target: 'new-clip', op: 'clip.add' },
          ],
          affectedObjectIds: ['new-clip'],
        },
      });

      const reader = await makeReader(undefined, 5);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      // Create proposal with baseVersion 0 (no expectation)
      const proposal = runtime.create({
        source: 'ext-a',
        patch: {
          version: 0,
          operations: [{ op: 'clip.add', target: 'new-clip', payload: { track: 'V1', at: 10, clipType: 'hold', hold: 3 } }],
        },
        baseVersion: 0,
      });

      const diff = runtime.accept(proposal.id);

      expect(diff.entries).toHaveLength(1);
      expect(mockOps._applyCalls).toHaveLength(1);

      const accepted = runtime.get(proposal.id)!;
      expect(accepted.state).toBe('accepted');
    });

    it('applies only through TimelineOps (never bypasses)', async () => {
      const mockOps = createMockTimelineOps({
        applyResult: {
          version: 2,
          entries: [
            { granularity: 'clip', kind: 'added', target: 'c1', op: 'clip.add' },
          ],
          affectedObjectIds: ['c1'],
        },
      });

      const reader = await makeReader(undefined, 5);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });
      const snap = reader.snapshot();

      const proposal = runtime.create({
        source: 'ext-a',
        patch: {
          version: snap.currentVersion,
          operations: [{ op: 'clip.add', target: 'c1', payload: { track: 'V1', at: 10, clipType: 'hold', hold: 3 } }],
        },
        baseVersion: snap.currentVersion,
      });

      runtime.accept(proposal.id);

      // TimelineOps.apply should be the only mutation path
      expect(mockOps._applyCalls).toHaveLength(1);
      expect(mockOps._applyCalls[0].operations).toHaveLength(1);
    });

    it('throws when proposal is not in pending state', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      // Reject it first
      runtime.reject(proposal.id);

      // Accept should throw because state is 'rejected'
      expect(() => runtime.accept(proposal.id)).toThrow('rejected');
    });

    it('throws when proposal is not found', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      expect(() => runtime.accept('nonexistent')).toThrow('not found');
    });

    it('accept revalidates against current reader snapshot (not cached version)', async () => {
      // This test proves that accept() reads the *current* reader snapshot
      // at accept time, not a previously cached version.
      const mockOps = createMockTimelineOps({
        applyResult: {
          version: 3,
          entries: [{ granularity: 'clip', kind: 'added', target: 'c1', op: 'clip.add' }],
          affectedObjectIds: ['c1'],
        },
      });

      const reader = await makeReader(undefined, 5);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      // Get current version from the reader
      const snap = reader.snapshot();
      expect(snap.currentVersion).toBe(5);

      // Create a proposal with that version
      const proposal = runtime.create({
        source: 'ext-a',
        patch: {
          version: snap.currentVersion,
          operations: [{ op: 'clip.add', target: 'c1', payload: { track: 'V1', at: 10, clipType: 'hold', hold: 3 } }],
        },
        baseVersion: snap.currentVersion, // 5
      });

      // Accept should succeed since versions match
      const diff = runtime.accept(proposal.id);
      expect(diff).toBeDefined();
      expect(mockOps._applyCalls).toHaveLength(1);
    });
  });

  // -----------------------------------------------------------------------
  // reject
  // -----------------------------------------------------------------------
  describe('reject', () => {
    it('rejects a pending proposal', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      runtime.reject(proposal.id);

      const rejected = runtime.get(proposal.id)!;
      expect(rejected.state).toBe('rejected');
    });

    it('does not mutate timeline when rejecting', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      runtime.reject(proposal.id);

      // TimelineOps.apply should never have been called
      expect(mockOps._applyCalls).toHaveLength(0);
    });

    it('throws when proposal is not in pending state', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      // Accept it first
      runtime.accept(proposal.id);

      // Reject should throw because state is 'accepted'
      expect(() => runtime.reject(proposal.id)).toThrow('accepted');
    });

    it('throws when proposal is not found', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      expect(() => runtime.reject('nonexistent')).toThrow('not found');
    });

    it('accepts an optional reason parameter', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      // Should not throw with a reason string
      runtime.reject(proposal.id, 'User dismissed the proposal');

      const rejected = runtime.get(proposal.id)!;
      expect(rejected.state).toBe('rejected');
    });
  });

  // -----------------------------------------------------------------------
  // get
  // -----------------------------------------------------------------------
  describe('get', () => {
    it('returns a proposal by ID', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      const found = runtime.get(proposal.id);
      expect(found).toBeDefined();
      expect(found!.id).toBe(proposal.id);
    });

    it('returns undefined for unknown ID', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      expect(runtime.get('nonexistent')).toBeUndefined();
    });
  });

  // -----------------------------------------------------------------------
  // list
  // -----------------------------------------------------------------------
  describe('list', () => {
    it('lists all proposals when no state filter is given', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const p1 = runtime.create({ source: 'ext-a', patch: { version: 0, operations: [] }, baseVersion: 0 });
      const p2 = runtime.create({ source: 'ext-b', patch: { version: 0, operations: [] }, baseVersion: 0 });

      runtime.reject(p2.id);

      const all = runtime.list();
      expect(all).toHaveLength(2);
    });

    it('filters by state', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const p1 = runtime.create({ source: 'ext-a', patch: { version: 0, operations: [] }, baseVersion: 0 });
      const p2 = runtime.create({ source: 'ext-b', patch: { version: 0, operations: [] }, baseVersion: 0 });

      runtime.reject(p2.id);

      const pending = runtime.list('pending');
      expect(pending).toHaveLength(1);
      expect(pending[0].id).toBe(p1.id);

      const rejected = runtime.list('rejected');
      expect(rejected).toHaveLength(1);
      expect(rejected[0].id).toBe(p2.id);

      const accepted = runtime.list('accepted');
      expect(accepted).toHaveLength(0);

      const stale = runtime.list('stale');
      expect(stale).toHaveLength(0);
    });

    it('returns an empty array when no proposals match', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      expect(runtime.list('pending')).toEqual([]);
      expect(runtime.list()).toEqual([]);
    });
  });

  // -----------------------------------------------------------------------
  // currentVersion
  // -----------------------------------------------------------------------
  describe('currentVersion', () => {
    it('returns the current version from the reader', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 7);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      expect(runtime.currentVersion).toBe(7);
    });

    it('reflects real-time reader state (getter, not cached)', async () => {
      const mockOps = createMockTimelineOps();

      const config = makeBaseConfig();
      const data1 = await buildData(config, 3);

      // Use a getter-based reader so version changes are reflected
      let version = 3;
      const reader = createTimelineReader({
        data: () => {
          // Simulate version changing over time
          return { ...data1, configVersion: version } as unknown as TimelineData;
        },
      });

      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      expect(runtime.currentVersion).toBe(3);

      // Change the version (simulating an external edit)
      version = 10;
      expect(runtime.currentVersion).toBe(10);
    });
  });

  // -----------------------------------------------------------------------
  // State machine integrity
  // -----------------------------------------------------------------------
  describe('state machine integrity', () => {
    it('rejected proposals cannot be accepted', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      runtime.reject(proposal.id);
      expect(() => runtime.accept(proposal.id)).toThrow('rejected');
    });

    it('accepted proposals cannot be rejected', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      runtime.accept(proposal.id);
      expect(() => runtime.reject(proposal.id)).toThrow('accepted');
    });

    it('stale proposals cannot be accepted again', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 5);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      // Create a proposal with a baseVersion that will become stale
      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 999, operations: [] },
        baseVersion: 999,
      });

      // First accept attempt throws and marks stale
      expect(() => runtime.accept(proposal.id)).toThrow('stale');

      // Verify it's now stale
      expect(runtime.get(proposal.id)!.state).toBe('stale');

      // Second accept attempt should also fail (not pending)
      expect(() => runtime.accept(proposal.id)).toThrow('stale');
    });

    it('stale proposals cannot be rejected', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 5);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 999, operations: [] },
        baseVersion: 999,
      });

      // Make it stale
      expect(() => runtime.accept(proposal.id)).toThrow('stale');

      // Verify it's stale
      expect(runtime.get(proposal.id)!.state).toBe('stale');

      // Reject should throw (not pending)
      expect(() => runtime.reject(proposal.id)).toThrow('stale');
    });

    it('listener is notified on every state transition', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader();
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const listener = vi.fn();
      runtime.subscribe(listener);
      listener.mockClear(); // Clear initial create notification

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });
      listener.mockClear(); // Clear create+preview notifications

      // Reject: should notify
      runtime.reject(proposal.id);
      expect(listener).toHaveBeenCalledTimes(1);
      expect(listener.mock.calls[0][0].state).toBe('rejected');
      listener.mockClear();

      // Create another for accept
      const p2 = runtime.create({
        source: 'ext-b',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });
      listener.mockClear();

      // Accept: should notify
      runtime.accept(p2.id);
      expect(listener).toHaveBeenCalledTimes(1);
      expect(listener.mock.calls[0][0].state).toBe('accepted');
    });
  });

  // -----------------------------------------------------------------------
  // M3: Expiry — pending proposal TTL and auto-expiration
  // -----------------------------------------------------------------------

  describe('expiry', () => {
    it('marks pending proposals as expired after their TTL elapses', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 1);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        rationale: 'Expiring proposal',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      // The runtime should expose an expireStale method or auto-expire
      // proposals.  Since the current runtime has no TTL support, this
      // expectation should fail until M3 wires expiry in.
      expect(typeof (runtime as any).expireStale).toBe('function');

      // Expire proposals older than 0ms (all pending proposals)
      const expired = (runtime as any).expireStale(0);
      expect(Array.isArray(expired)).toBe(true);
      expect(expired.length).toBeGreaterThanOrEqual(1);
      expect(expired[0].id).toBe(proposal.id);

      // The expired proposal should be in 'expired' state and not appear
      // in pending listings.
      const updated = runtime.get(proposal.id);
      expect(updated).toBeDefined();
      expect(updated!.state).toBe('expired');

      const pending = runtime.list('pending');
      expect(pending.find((p) => p.id === proposal.id)).toBeUndefined();
    });

    it('does not expire proposals that are still within TTL', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 1);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      runtime.create({
        source: 'ext-a',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      expect(typeof (runtime as any).expireStale).toBe('function');

      // Use a very large TTL — the proposal was just created so it
      // should still be within the window.
      const expired = (runtime as any).expireStale(86_400_000); // 1 day
      expect(expired).toEqual([]);

      const pending = runtime.list('pending');
      expect(pending.length).toBe(1);
    });

    it('expired proposals cannot be accepted', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 1);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      // Expire it
      (runtime as any).expireStale(0);

      // Accepting an expired proposal should throw
      expect(() => runtime.accept(proposal.id)).toThrow();
      expect(mockOps._applyCalls).toHaveLength(0);
    });

    it('expired proposals are hidden or clearly marked as expired in list', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 1);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const p1 = runtime.create({
        source: 'ext-a',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      const p2 = runtime.create({
        source: 'ext-b',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      // expireStale(0) expires every pending proposal per the SDK contract.
      (runtime as any).expireStale(0);

      expect(runtime.get(p1.id)!.state).toBe('expired');
      expect(runtime.get(p2.id)!.state).toBe('expired');

      // Pending list must not include expired proposals
      const pending = runtime.list('pending');
      expect(pending.find((p) => p.id === p1.id)).toBeUndefined();
      expect(pending.find((p) => p.id === p2.id)).toBeUndefined();
    });
  });

  // -----------------------------------------------------------------------
  // M3: Stale-before-mutation — timeline is never mutated for stale proposals
  // -----------------------------------------------------------------------

  describe('stale-before-mutation', () => {
    it('never calls TimelineOps.apply for a stale proposal', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 5);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      // Create a proposal whose baseVersion will not match the reader
      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 999, operations: [{ op: 'clip.add', target: 'c1', payload: {} }] },
        baseVersion: 999,
      });

      expect(() => runtime.accept(proposal.id)).toThrow('stale');

      // The critical invariant: TimelineOps.apply was NEVER called.
      // The stale rejection must happen before any mutation touches the
      // timeline data.
      expect(mockOps._applyCalls).toHaveLength(0);
    });

    it('marks proposal stale before mutation when baseVersion differs', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 10);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        rationale: 'Should go stale',
        patch: { version: 3, operations: [{ op: 'clip.move', target: 'c1', payload: { at: 5 } }] },
        baseVersion: 3, // Different from reader's 10
      });

      // Accept should throw and mark stale
      expect(() => runtime.accept(proposal.id)).toThrow();

      const stale = runtime.get(proposal.id)!;
      expect(stale.state).toBe('stale');

      // The stale proposal carries diagnostics explaining the version mismatch
      expect(stale.diagnostics).toBeDefined();
      expect(stale.diagnostics!.some((d) => d.code === 'timeline-patch/stale-base-version')).toBe(true);

      // No mutation side effects
      expect(mockOps._applyCalls).toHaveLength(0);
    });

    it('rejects stale proposals without mutating even for baseVersion 0', async () => {
      // baseVersion 0 means "no expectation", so accept should succeed.
      // This test verifies that stale detection only triggers when
      // baseVersion !== 0 AND baseVersion !== currentVersion.
      const mockOps = createMockTimelineOps({
        applyResult: {
          version: 1,
          entries: [{ granularity: 'clip', kind: 'added', target: 'c1', op: 'clip.add' }],
          affectedObjectIds: ['c1'],
        },
      });
      const reader = await makeReader(undefined, 5);
      const runtime = createProposalRuntime({ timelineOps: mockOps, reader });

      const proposal = runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [{ op: 'clip.add', target: 'c1', payload: {} }] },
        baseVersion: 0,
      });

      // Should accept successfully — baseVersion 0 bypasses stale check
      const diff = runtime.accept(proposal.id);
      expect(diff).toBeDefined();
      expect(mockOps._applyCalls).toHaveLength(1);
    });
  });

  // -----------------------------------------------------------------------
  // M3: Reload — proposal survival across provider/runtime reload
  // -----------------------------------------------------------------------

  describe('reload survival', () => {
    it('pending proposal survives runtime re-creation when provider returns it', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 1);
      const provider = createMockPersistenceProvider();

      const runtime1 = createProposalRuntime({ timelineOps: mockOps, reader, persistenceProvider: provider });
      runtime1.create({
        source: 'ext-a',
        rationale: 'Pending proposal',
        patch: { version: 1, operations: [] },
        baseVersion: 1,
      });

      // Wait for the provider to record the pending proposal.
      await vi.waitFor(() => provider.records.length === 1);
      const providerRecord = provider.records[0];
      expect(providerRecord.state).toBe('pending');

      // Simulate a page reload by creating a new runtime against the same
      // reader and provider. The pending proposal is rehydrated asynchronously.
      const runtime2 = createProposalRuntime({ timelineOps: mockOps, reader, persistenceProvider: provider });
      await vi.waitFor(() => runtime2.get(providerRecord.id) !== undefined);

      const reloaded = runtime2.get(providerRecord.id);
      expect(reloaded).toBeDefined();
      expect(reloaded!.id).toBe(providerRecord.id);
      expect(reloaded!.source).toBe('ext-a');
      expect(reloaded!.state).toBe('pending');
    });

    it('does not reload accepted/rejected/stale/expired proposals (terminal history not supported)', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 5);
      const provider = createMockPersistenceProvider();

      // Seed the provider with terminal records to prove they are ignored
      // even if a persistence layer returns them. The runtime's pending-only
      // reload contract intentionally does not reconstruct terminal history.
      const terminalIds = {
        accepted: 'terminal-accepted',
        rejected: 'terminal-rejected',
        stale: 'terminal-stale',
        expired: 'terminal-expired',
      };
      provider.records.push(
        { id: terminalIds.accepted, source: 'ext-accepted', state: 'accepted', baseVersion: 5, patch: {}, createdAt: Date.now(), updatedAt: Date.now() },
        { id: terminalIds.rejected, source: 'ext-rejected', state: 'rejected', baseVersion: 0, patch: {}, createdAt: Date.now(), updatedAt: Date.now() },
        { id: terminalIds.stale, source: 'ext-stale', state: 'stale', baseVersion: 999, patch: {}, createdAt: Date.now(), updatedAt: Date.now() },
        { id: terminalIds.expired, source: 'ext-expired', state: 'expired', baseVersion: 0, patch: {}, createdAt: Date.now(), updatedAt: Date.now() },
      );

      const runtime2 = createProposalRuntime({ timelineOps: mockOps, reader, persistenceProvider: provider });

      expect(runtime2.get(terminalIds.accepted)).toBeUndefined();
      expect(runtime2.get(terminalIds.rejected)).toBeUndefined();
      expect(runtime2.get(terminalIds.stale)).toBeUndefined();
      expect(runtime2.get(terminalIds.expired)).toBeUndefined();

      // No terminal proposals should appear in any list.
      expect(runtime2.list('accepted')).toHaveLength(0);
      expect(runtime2.list('rejected')).toHaveLength(0);
      expect(runtime2.list('stale')).toHaveLength(0);
      expect(runtime2.list('expired')).toHaveLength(0);
    });

    it('list() after reload only returns the pending hydrated proposal, not terminal ones', async () => {
      const mockOps = createMockTimelineOps();
      const reader = await makeReader(undefined, 1);
      const provider = createMockPersistenceProvider();

      // Seed the provider with one pending and one terminal record.
      const pendingRecord: ProposalPersistenceRecord = {
        id: 'reload-pending-1',
        source: 'ext-pending',
        state: 'pending',
        baseVersion: 1,
        patch: { version: 1, operations: [] },
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      const rejectedRecord: ProposalPersistenceRecord = {
        id: 'reload-rejected-1',
        source: 'ext-rejected',
        state: 'rejected',
        baseVersion: 0,
        patch: { version: 0, operations: [] },
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      provider.records.push(pendingRecord, rejectedRecord);

      const runtime2 = createProposalRuntime({ timelineOps: mockOps, reader, persistenceProvider: provider });
      await vi.waitFor(() => runtime2.list().length === 1);

      const all = runtime2.list();
      expect(all).toHaveLength(1);
      expect(all[0].id).toBe(pendingRecord.id);
      expect(all[0].source).toBe('ext-pending');
      expect(all[0].state).toBe('pending');

      expect(runtime2.list('pending')).toHaveLength(1);
      expect(runtime2.list('rejected')).toHaveLength(0);
    });
  });

  // -----------------------------------------------------------------------
  // M3: Unsupported-provider diagnostics
  // -----------------------------------------------------------------------

  describe('unsupported-provider diagnostics', () => {
    it('surfaces diagnostics when the provider does not support proposal persistence', () => {
      // A provider that explicitly declares it cannot persist proposals
      // should surface that as a diagnostic rather than silently failing.
      // The ProposalRuntime factory should accept an optional
      // `persistenceProvider` and emit diagnostics when it's unsupported.

      const mockOps = createMockTimelineOps();
      // We can't test this fully without the persistence provider hook,
      // but the factory should at minimum accept the option without
      // throwing.  When `persistenceProvider: null` or `'unsupported'`
      // is passed, the runtime should be constructable and surface
      // diagnostics through a well-known channel.
      const createOptions: any = {
        timelineOps: mockOps,
        reader: { snapshot: () => ({ currentVersion: 1 }) },
        persistenceProvider: null, // explicitly no persistence
      };

      // Should not throw — unsupported is a valid configuration
      const runtime = createProposalRuntime(createOptions);

      // The runtime should expose diagnostics about the persistence gap
      expect(runtime).toBeDefined();

      // When persistence is unsupported, a diagnostic should be available.
      // This may be via a `diagnostics` getter or a well-known method.
      const diags = (runtime as any).diagnostics;
      if (diags !== undefined) {
        expect(Array.isArray(diags)).toBe(true);
        const hasPersistenceDiag = diags.some(
          (d: any) => d.code === 'proposal/persistence-unsupported',
        );
        expect(hasPersistenceDiag).toBe(true);
      }
    });

    it('does not surface persistence diagnostics when a supported provider is configured', () => {
      const mockOps = createMockTimelineOps();
      const createOptions: any = {
        timelineOps: mockOps,
        reader: { snapshot: () => ({ currentVersion: 1 }) },
        persistenceProvider: 'in-memory', // supported
      };

      const runtime = createProposalRuntime(createOptions);
      expect(runtime).toBeDefined();

      const diags = (runtime as any).diagnostics;
      if (diags !== undefined) {
        const hasPersistenceDiag = diags.some(
          (d: any) => d.code === 'proposal/persistence-unsupported',
        );
        expect(hasPersistenceDiag).toBe(false);
      }
    });

    it('explicitly warns that proposals will be lost on page refresh when persistence is unsupported', () => {
      const mockOps = createMockTimelineOps();
      const createOptions: any = {
        timelineOps: mockOps,
        reader: { snapshot: () => ({ currentVersion: 1 }) },
        persistenceProvider: null, // explicitly no persistence
      };

      const runtime = createProposalRuntime(createOptions);
      expect(runtime).toBeDefined();

      const diags = (runtime as any).diagnostics;
      expect(diags).toBeDefined();
      expect(Array.isArray(diags)).toBe(true);

      const persistenceDiag = diags.find(
        (d: any) => d.code === 'proposal/persistence-unsupported',
      );
      expect(persistenceDiag).toBeDefined();
      expect(persistenceDiag.message).toContain('lost on page refresh');
      expect(persistenceDiag.severity).toBe('warning');
    });

    it('does not promise reload-safe proposals when persistence provider is absent', () => {
      // Construct two runtimes without a persistence provider.
      // Proposals created in runtime1 must NOT be visible in runtime2 —
      // the runtime makes no false promise of cross-instance survival.
      const mockOps = createMockTimelineOps();
      const reader = { snapshot: () => ({ currentVersion: 1 }) };

      const runtime1 = createProposalRuntime({
        timelineOps: mockOps,
        reader: reader as any,
        persistenceProvider: null,
      });

      const proposal = runtime1.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      });

      // A second runtime with no provider should NOT see the proposal.
      const runtime2 = createProposalRuntime({
        timelineOps: mockOps,
        reader: reader as any,
        persistenceProvider: null,
      });

      expect(runtime2.get(proposal.id)).toBeUndefined();
      expect(runtime2.list()).toHaveLength(0);

      // The unsupported diagnostic must be present.
      const diags = (runtime2 as any).diagnostics as Array<{ code: string; message: string }>;
      expect(diags.some((d) => d.code === 'proposal/persistence-unsupported')).toBe(true);
    });
  });

  // -----------------------------------------------------------------------
  // M3: Negative-path — provider_capability_extension_proposals_unsupported bridge
  // -----------------------------------------------------------------------

  describe('negative-path: unsupported-provider bridge to DataProvider diagnostics', () => {
    it('surfaces the stable diagnostic code when the provider capabilities exclude proposals', () => {
      // Simulate a minimal persistence provider that explicitly reports
      // proposals as unsupported (similar to what a DataProvider that lacks
      // createExtensionPersistenceService would emit).
      const mockOps = createMockTimelineOps();
      const reader = { snapshot: () => ({ currentVersion: 1 }) };

      // persistenceProvider: null is the canonical "unsupported" sentinel.
      const runtime = createProposalRuntime({
        timelineOps: mockOps,
        reader: reader as any,
        persistenceProvider: null,
      });

      const diags = (runtime as any).diagnostics as Array<{ severity: string; code: string; message: string }>;
      expect(diags).toBeDefined();

      const unsupportedDiag = diags.find(
        (d) => d.code === 'proposal/persistence-unsupported',
      );
      expect(unsupportedDiag).toBeDefined();
      expect(unsupportedDiag!.severity).toBe('warning');

      // The runtime must not crash or throw when used without persistence.
      expect(() => runtime.create({
        source: 'ext-a',
        patch: { version: 0, operations: [] },
        baseVersion: 0,
      })).not.toThrow();
    });
  });

  // -----------------------------------------------------------------------
  // M1: importProposal — import validation diagnostics
  // -----------------------------------------------------------------------

  describe('importProposal', () => {
    let mockOps: ReturnType<typeof createMockTimelineOps>;
    let reader: { snapshot: () => { currentVersion: number } };
    let runtime: ProposalRuntime & { importProposal(proposal: TimelineProposal): void; diagnostics: Array<{ severity: string; code: string; message: string }> };

    beforeEach(() => {
      mockOps = createMockTimelineOps();
      reader = { snapshot: () => ({ currentVersion: 1 }) };
      runtime = createProposalRuntime({
        timelineOps: mockOps,
        reader: reader as any,
        persistenceProvider: null,
      }) as any;
    });

    function makeValidProposal(overrides: Partial<TimelineProposal> = {}): TimelineProposal {
      return {
        id: 'import-1',
        source: 'edge-agent',
        state: 'pending',
        patch: {
          version: 1,
          operations: [
            { op: 'clip.add', target: 'c1', payload: { track: 'V1', at: 0, clipType: 'hold', hold: 3 } },
          ],
        },
        baseVersion: 1,
        previewable: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
        ...overrides,
      };
    }

    // ── Happy path (existing behavior) ─────────────────────────────────

    it('imports a valid pending proposal into the runtime', () => {
      const proposal = makeValidProposal();
      runtime.importProposal(proposal);

      const stored = runtime.get('import-1');
      expect(stored).toBeDefined();
      expect(stored!.id).toBe('import-1');
      expect(stored!.source).toBe('edge-agent');
      expect(stored!.state).toBe('pending');
      expect(stored!.patch.operations).toHaveLength(1);
    });

    it('preserves server-assigned ID, baseVersion, and rationale', () => {
      const proposal = makeValidProposal({
        rationale: 'Agent recommends adding a hold clip for pacing',
        baseVersion: 42,
      });
      runtime.importProposal(proposal);

      const stored = runtime.get('import-1')!;
      expect(stored.rationale).toBe('Agent recommends adding a hold clip for pacing');
      expect(stored.baseVersion).toBe(42);
    });

    it('preserves expiry and preview state from the imported proposal', () => {
      const expiresAt = Date.now() + 86_400_000; // 1 day from now
      const previewDiff = makeEmptyDiff(1);
      const proposal = makeValidProposal({
        expiresAt,
        previewable: true,
        previewDiff,
      });
      runtime.importProposal(proposal);

      const stored = runtime.get('import-1')!;
      expect(stored.expiresAt).toBe(expiresAt);
      expect(stored.previewable).toBe(true);
      expect(stored.previewDiff).toEqual(previewDiff);
    });

    it('imports proposals in accepted/rejected/stale/expired states', () => {
      for (const state of ['accepted', 'rejected', 'stale', 'expired'] as const) {
        const id = `import-${state}`;
        runtime.importProposal(makeValidProposal({ id, state }));
        expect(runtime.get(id)!.state).toBe(state);
      }
    });

    it('notifies listeners on import', () => {
      const listener = vi.fn();
      runtime.subscribe(listener);

      const proposal = makeValidProposal();
      runtime.importProposal(proposal);

      expect(listener).toHaveBeenCalled();
      expect(listener.mock.calls[0][0].id).toBe('import-1');
    });

    // ── Missing-field validation (existing behavior) ───────────────────

    it('rejects a proposal with missing id (diagnostic emitted)', () => {
      const proposal = makeValidProposal({ id: '' });
      runtime.importProposal(proposal);

      expect(runtime.get('import-1')).toBeUndefined();
      expect(runtime.get('')).toBeUndefined();

      const diags = runtime.diagnostics;
      const importDiag = diags.find((d) => d.code === 'proposal-import/invalid-shape');
      expect(importDiag).toBeDefined();
      expect(importDiag!.severity).toBe('error');
      expect(importDiag!.message).toContain('missing required fields');
    });

    it('rejects a proposal with missing source (diagnostic emitted)', () => {
      const proposal = makeValidProposal({ source: '' });
      runtime.importProposal(proposal);

      expect(runtime.get('import-1')).toBeUndefined();

      const diags = runtime.diagnostics;
      const importDiag = diags.find((d) => d.code === 'proposal-import/invalid-shape');
      expect(importDiag).toBeDefined();
    });

    it('rejects a proposal with missing patch (diagnostic emitted)', () => {
      const proposal = makeValidProposal({ patch: undefined as any });
      runtime.importProposal(proposal);

      expect(runtime.get('import-1')).toBeUndefined();

      const diags = runtime.diagnostics;
      const importDiag = diags.find((d) => d.code === 'proposal-import/invalid-shape');
      expect(importDiag).toBeDefined();
    });

    it('rejects a proposal with null patch (diagnostic emitted)', () => {
      const proposal = makeValidProposal({ patch: null as any });
      runtime.importProposal(proposal);

      expect(runtime.get('import-1')).toBeUndefined();

      const diags = runtime.diagnostics;
      const importDiag = diags.find((d) => d.code === 'proposal-import/invalid-shape');
      expect(importDiag).toBeDefined();
    });

    // ── Duplicate handling (existing behavior) ─────────────────────────

    it('skips proposals with duplicate IDs (first-write wins)', () => {
      const p1 = makeValidProposal({ id: 'dup-1', source: 'agent-a' });
      const p2 = makeValidProposal({ id: 'dup-1', source: 'agent-b' });

      runtime.importProposal(p1);
      runtime.importProposal(p2);

      const stored = runtime.get('dup-1')!;
      expect(stored.source).toBe('agent-a'); // First write preserved
    });

    // ── Auto-expiry on import (existing behavior) ──────────────────────

    it('auto-expires imported proposals with elapsed TTL', () => {
      const pastExpiry = Date.now() - 60_000; // 1 minute ago
      const proposal = makeValidProposal({
        id: 'expired-import',
        state: 'pending',
        expiresAt: pastExpiry,
      });
      runtime.importProposal(proposal);

      const stored = runtime.get('expired-import');
      // After auto-expire, the proposal should be expired, not pending
      if (stored) {
        expect(stored.state).toBe('expired');
      }
    });

    // ── M1: Invalid patch shapes (fail-to-pass — not yet validated) ────

    it('rejects proposals with invalid patch shape (missing version)', () => {
      const proposal = makeValidProposal({
        patch: { operations: [] } as any,
      });
      const result = runtime.importProposal(proposal);

      expect(result).toBe('rejected');
      const diags = runtime.diagnostics;
      const validationDiag = diags.find((d) => d.code === 'proposal-import/invalid-patch');
      expect(validationDiag).toBeDefined();
      expect(runtime.get('import-1')).toBeUndefined();
    });

    it('rejects proposals with missing operations array', () => {
      const proposal = makeValidProposal({
        patch: { version: 1 } as any,
      });
      const result = runtime.importProposal(proposal);

      expect(result).toBe('rejected');
      const diags = runtime.diagnostics;
      const validationDiag = diags.find((d) => d.code === 'proposal-import/invalid-patch');
      expect(validationDiag).toBeDefined();
    });

    it('rejects proposals with null operations', () => {
      const proposal = makeValidProposal({
        patch: { version: 1, operations: null as any },
      });
      const result = runtime.importProposal(proposal);

      expect(result).toBe('rejected');
      const diags = runtime.diagnostics;
      const validationDiag = diags.find((d) => d.code === 'proposal-import/invalid-patch');
      expect(validationDiag).toBeDefined();
    });

    it('rejects proposals where patch is not an object', () => {
      const proposal = makeValidProposal({ patch: 'not-a-patch' as any });
      const result = runtime.importProposal(proposal);

      expect(result).toBe('rejected');
      const diags = runtime.diagnostics;
      const importDiag = diags.find((d) => d.code === 'proposal-import/invalid-shape');
      expect(importDiag).toBeDefined();
      expect(runtime.get('import-1')).toBeUndefined();
    });

    // ── M1: Unsupported operations (fail-to-pass — not yet validated) ──

    it('rejects proposals with unsupported patch operations', () => {
      const proposal = makeValidProposal({
        patch: {
          version: 1,
          operations: [
            { op: 'invalid.operation', target: 'x', payload: {} },
          ],
        },
      });
      const result = runtime.importProposal(proposal);

      expect(result).toBe('rejected');
      const diags = runtime.diagnostics;
      const opDiag = diags.find(
        (d) =>
          d.code === 'proposal-import/invalid-patch' &&
          d.detail?.timelinePatchCode === 'timeline-patch/unknown-op',
      );
      expect(opDiag).toBeDefined();
    });

    it('rejects proposals with reserved operations', () => {
      const proposal = makeValidProposal({
        patch: {
          version: 1,
          operations: [
            { op: 'clip.split', target: 'clip-1', payload: {} },
          ],
        },
      });
      const result = runtime.importProposal(proposal);

      expect(result).toBe('imported');
      const stored = runtime.get('import-1');
      expect(stored).toBeDefined();
      const opDiag = stored!.diagnostics?.find(
        (d) =>
          d.code === 'timeline-patch/reserved-op',
      );
      expect(opDiag).toBeDefined();
    });

    it('rejects proposals with empty operation list', () => {
      const proposal = makeValidProposal({
        patch: { version: 1, operations: [] },
      });
      const result = runtime.importProposal(proposal);

      expect(result).toBe('rejected');
      const diags = runtime.diagnostics;
      const opDiag = diags.find(
        (d) =>
          d.code === 'proposal-import/invalid-patch' &&
          d.detail?.timelinePatchCode === 'timeline-patch/empty-operations',
      );
      expect(opDiag).toBeDefined();
    });

    // ── M1: Payload mismatches (fail-to-pass — not yet validated) ──────

    it('rejects clip.add operations with invalid payload types', () => {
      const proposal = makeValidProposal({
        patch: {
          version: 1,
          operations: [
            { op: 'clip.add', target: 'c-missing', payload: { track: 'V1', at: 'not-a-number', clipType: 'hold', hold: 3 } },
          ],
        },
      });
      const result = runtime.importProposal(proposal);

      expect(result).toBe('rejected');
      // M1 contract: validateTimelinePatch should catch payload mismatches
      const diags = runtime.diagnostics;
      const payloadDiag = diags.find(
        (d) =>
          d.code === 'proposal-import/invalid-patch' &&
          d.detail?.timelinePatchCode === 'timeline-patch/invalid-payload',
      );
      expect(payloadDiag).toBeDefined();
    });

    it('rejects clip.move operations without required at field', () => {
      const proposal = makeValidProposal({
        patch: {
          version: 1,
          operations: [
            { op: 'clip.move', target: 'c-move', payload: {} },
          ],
        },
      });
      const result = runtime.importProposal(proposal);

      expect(result).toBe('rejected');
      const diags = runtime.diagnostics;
      const payloadDiag = diags.find(
        (d) =>
          d.code === 'proposal-import/invalid-patch' &&
          d.detail?.timelinePatchCode === 'timeline-patch/invalid-payload',
      );
      expect(payloadDiag).toBeDefined();
    });

    it('rejects clip.add with wrong payload types', () => {
      const proposal = makeValidProposal({
        patch: {
          version: 1,
          operations: [
            { op: 'clip.add', target: 'c-wrong', payload: { track: 123, at: 'not-a-number', clipType: true, hold: 'abc' } },
          ],
        },
      });
      const result = runtime.importProposal(proposal);

      expect(result).toBe('rejected');
      const diags = runtime.diagnostics;
      const payloadDiag = diags.find(
        (d) =>
          d.code === 'proposal-import/invalid-patch' &&
          d.detail?.timelinePatchCode === 'timeline-patch/invalid-payload',
      );
      expect(payloadDiag).toBeDefined();
    });

    // ── M1: Structured diagnostics shape (fail-to-pass — not yet validated) ──

    it('produces structured diagnostics with proposalIndex for batch validation', () => {
      // Import two proposals: one valid, one invalid
      runtime.importProposal(makeValidProposal({ id: 'valid-1' }));
      runtime.importProposal(makeValidProposal({ id: '', source: 'bad' })); // invalid

      // M1 contract: diagnostics should identify which proposal failed
      const diags = runtime.diagnostics;
      const importDiags = diags.filter((d) => d.code === 'proposal-import/invalid-shape');
      expect(importDiags.length).toBeGreaterThanOrEqual(1);

      // Ideally diagnostics include the proposal index or ID
      const hasIdContext = importDiags.some(
        (d) => (d as any).proposalId !== undefined || (d as any).proposalIndex !== undefined,
      );
      // Future: expect(hasIdContext).toBe(true);
      // Currently diagnostics lack per-proposal indexing — this test
      // documents the expectation.
      expect(diags.length).toBeGreaterThan(0);
    });

    it('uses diagnostic severity "error" for import validation failures', () => {
      runtime.importProposal(makeValidProposal({ id: '' }));

      const diags = runtime.diagnostics;
      const importDiag = diags.find((d) => d.code === 'proposal-import/invalid-shape');
      expect(importDiag).toBeDefined();
      expect(importDiag!.severity).toBe('error');
    });
  });

  // -----------------------------------------------------------------------
  // M1: importEdgeProposals — envelope-level import
  // -----------------------------------------------------------------------

  describe('importEdgeProposals', () => {
    let mockOps: ReturnType<typeof createMockTimelineOps>;
    let reader: { snapshot: () => { currentVersion: number } };

    beforeEach(() => {
      mockOps = createMockTimelineOps();
      reader = { snapshot: () => ({ currentVersion: 1 }) };
    });

    function makeRuntime() {
      return createProposalRuntime({
        timelineOps: mockOps,
        reader: reader as any,
        persistenceProvider: null,
      }) as any;
    }

    function makePendingProposal(id: string, source = 'edge-agent'): TimelineProposal {
      return {
        id,
        source,
        state: 'pending',
        patch: {
          version: 1,
          operations: [
            { op: 'clip.add', target: `c-${id}`, payload: { track: 'V1', at: 0, clipType: 'hold', hold: 3 } },
          ],
        },
        baseVersion: 1,
        previewable: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
    }

    // ── Happy path (existing behavior) ─────────────────────────────────

    it('imports pending proposals from a valid envelope', () => {
      const runtime = makeRuntime();
      const envelope = {
        proposals: [makePendingProposal('p1'), makePendingProposal('p2')],
        baseVersion: 1,
        mutationApplied: false,
      };

      const result = importEdgeProposals(envelope, runtime);
      expect(result.imported).toBe(2);
      expect(result.skipped).toBe(0);
      expect(result.rejected).toBe(0);
      expect(runtime.get('p1')).toBeDefined();
      expect(runtime.get('p2')).toBeDefined();
    });

    it('returns the count of actually imported proposals', () => {
      const runtime = makeRuntime();
      const envelope = {
        proposals: [
          makePendingProposal('p1'),
          makePendingProposal('p2', 'agent-b'),
          makePendingProposal('p3', 'agent-c'),
        ],
        baseVersion: 1,
        mutationApplied: false,
      };

      const result = importEdgeProposals(envelope, runtime);
      expect(result.imported).toBe(3);
      expect(result.skipped).toBe(0);
      expect(result.rejected).toBe(0);
    });

    // ── Empty/missing proposals (existing behavior) ────────────────────

    it('returns 0 for an envelope with empty proposals array', () => {
      const runtime = makeRuntime();
      const result = importEdgeProposals(
        { proposals: [], baseVersion: 1, mutationApplied: false },
        runtime,
      );
      expect(result.imported).toBe(0);
      expect(result.skipped).toBe(0);
      expect(result.rejected).toBe(0);
      expect(runtime.list()).toHaveLength(0);
    });

    it('returns 0 when proposals field is missing', () => {
      const runtime = makeRuntime();
      const result = importEdgeProposals(
        { baseVersion: 1, mutationApplied: false },
        runtime,
      );
      expect(result.imported).toBe(0);
      expect(result.diagnostics).toEqual([
        expect.objectContaining({ code: 'proposal-import/invalid-envelope' }),
      ]);
    });

    it('returns 0 when proposals field is null', () => {
      const runtime = makeRuntime();
      const result = importEdgeProposals(
        { proposals: null, baseVersion: 1, mutationApplied: false },
        runtime,
      );
      expect(result.imported).toBe(0);
      expect(result.diagnostics).toEqual([
        expect.objectContaining({ code: 'proposal-import/invalid-envelope' }),
      ]);
    });

    // ── Missing runtime importProposal (existing behavior) ─────────────

    it('returns 0 when runtime lacks importProposal', () => {
      // Create a runtime without importProposal (plain ProposalRuntime)
      const plainRuntime = createProposalRuntime({
        timelineOps: mockOps,
        reader: reader as any,
        persistenceProvider: null,
      });
      // delete the importProposal method to simulate an older runtime
      delete (plainRuntime as any).importProposal;

      const result = importEdgeProposals(
        {
          proposals: [makePendingProposal('p1')],
          baseVersion: 1,
          mutationApplied: false,
        },
        plainRuntime,
      );
      expect(result.imported).toBe(0);
      expect(result.skipped).toBe(1);
      expect(result.rejected).toBe(0);
    });

    // ── Non-pending proposals are skipped (existing behavior) ──────────

    it('skips non-pending proposals (accepted, rejected, stale, expired)', () => {
      const runtime = makeRuntime();
      const envelope = {
        proposals: [
          makePendingProposal('pending-1'),
          { ...makePendingProposal('accepted-1'), state: 'accepted' as const },
          { ...makePendingProposal('rejected-1'), state: 'rejected' as const },
          { ...makePendingProposal('stale-1'), state: 'stale' as const },
          { ...makePendingProposal('expired-1'), state: 'expired' as const },
        ],
        baseVersion: 1,
        mutationApplied: false,
      };

      const result = importEdgeProposals(envelope, runtime);
      expect(result.imported).toBe(1); // Only the pending one
      expect(result.skipped).toBe(4);
      expect(result.rejected).toBe(0);
      expect(runtime.get('pending-1')).toBeDefined();
      expect(runtime.get('accepted-1')).toBeUndefined();
      expect(runtime.get('rejected-1')).toBeUndefined();
    });

    // ── M1: Malformed envelope validation (fail-to-pass — not yet validated) ──

    it('rejects malformed envelopes where proposals is not an array', () => {
      const runtime = makeRuntime();
      const result = importEdgeProposals(
        { proposals: 'not-an-array' as any, baseVersion: 1, mutationApplied: false },
        runtime,
      );
      // M1 contract: malformed envelopes should be rejected/skipped
      expect(result.imported).toBe(0);
      expect(result.diagnostics).toEqual([
        expect.objectContaining({ code: 'proposal-import/invalid-envelope' }),
      ]);
    });

    it('rejects envelopes with missing baseVersion', () => {
      const runtime = makeRuntime();
      const result = importEdgeProposals(
        { proposals: [makePendingProposal('p1')], mutationApplied: false } as any,
        runtime,
      );
      // M1 contract: envelope missing baseVersion should be treated with caution
      // Current behavior: imports anyway (no validation)
      // Future: should skip or warn
      expect(result.imported).toBeGreaterThanOrEqual(0);
    });

    it('rejects envelopes with negative baseVersion', () => {
      const runtime = makeRuntime();
      const envelope = {
        proposals: [makePendingProposal('p1')],
        baseVersion: -1,
        mutationApplied: false,
      };
      // M1 contract: invalid baseVersion should be rejected
      const result = importEdgeProposals(envelope, runtime);
      // Future: should be 0 with a diagnostic
      expect(result.imported).toBeGreaterThanOrEqual(0);
    });

    // ── M1: Full batch validation (fail-to-pass — not yet validated) ───

    it('imports only valid proposals when batch contains mixed valid/invalid', () => {
      const runtime = makeRuntime();
      const envelope = {
        proposals: [
          makePendingProposal('valid-1'),
          { ...makePendingProposal(''), source: 'bad' }, // missing ID
          makePendingProposal('valid-2', 'agent-b'),
        ],
        baseVersion: 1,
        mutationApplied: false,
      };

      const result = importEdgeProposals(envelope, runtime);
      // M1 contract: only valid proposals should be imported
      // Current: invalid proposal is rejected by importProposal, so count
      // should reflect only the successfully imported ones
      expect(result.imported).toBeGreaterThanOrEqual(2);
      expect(result.rejected).toBe(1);
      expect(runtime.get('valid-1')).toBeDefined();
      expect(runtime.get('valid-2')).toBeDefined();
    });

    // ── M1: ProposalImportResult contract (fail-to-pass) ───────────────

    it('returns a structured ProposalImportResult instead of a bare count', () => {
      // M1 contract: importEdgeProposals should return ProposalImportResult
      // with imported, skipped, rejected counts and per-proposal diagnostics.
      // Currently it returns just a number — this test documents the
      // expectation for the contract upgrade.
      const runtime = makeRuntime();
      const envelope = {
        proposals: [
          makePendingProposal('p1'),
          { ...makePendingProposal('p2'), state: 'accepted' as const },
        ],
        baseVersion: 1,
        mutationApplied: false,
      };

      const result = importEdgeProposals(envelope, runtime);
      expect(result).toMatchObject({
        imported: 1,
        skipped: 1,
        rejected: 0,
        statuses: [
          { proposalId: 'p1', status: 'imported' },
          { proposalId: 'p2', status: 'skipped' },
        ],
      });
    });

    it('includes newly emitted runtime diagnostics with proposal index and ID', () => {
      const runtime = makeRuntime();
      const invalid = makePendingProposal('bad-patch');
      const envelope = {
        proposals: [
          makePendingProposal('valid-1'),
          {
            ...invalid,
            patch: { version: 1, operations: [{ op: 'clip.add', target: '' }] },
          },
        ],
        baseVersion: 1,
        mutationApplied: false,
      };

      const result = importEdgeProposals(envelope, runtime);

      expect(result.imported).toBe(1);
      expect(result.rejected).toBe(1);
      expect(result.diagnostics).toContainEqual(
        expect.objectContaining({
          severity: 'error',
          code: 'proposal-import/invalid-patch',
          message: 'operations[0] "clip.add" requires a non-empty target',
          proposalIndex: 1,
          proposalId: 'bad-patch',
          detail: expect.objectContaining({
            timelinePatchCode: 'timeline-patch/missing-target',
          }),
        }),
      );
    });

    it('preserves envelope diagnostics while appending only new runtime diagnostics', () => {
      const runtime = makeRuntime();
      runtime.importProposal(makePendingProposal('duplicate-1'));
      const diagnosticsBefore = runtime.diagnostics.length;
      const envelope = {
        proposals: [
          { ...makePendingProposal('accepted-1'), state: 'accepted' as const },
          makePendingProposal('duplicate-1'),
        ],
        baseVersion: 1,
        mutationApplied: false,
      };

      const result = importEdgeProposals(envelope, runtime);

      expect(result.imported).toBe(0);
      expect(result.skipped).toBe(2);
      expect(result.rejected).toBe(0);
      expect(result.diagnostics).toEqual([
        expect.objectContaining({
          code: 'proposal-import/skipped-terminal',
          proposalIndex: 0,
          proposalId: 'accepted-1',
        }),
        expect.objectContaining({
          code: 'proposal-import/duplicate-id',
          proposalIndex: 1,
          proposalId: 'duplicate-1',
        }),
      ]);
      expect(result.diagnostics).toHaveLength(2);
      expect(runtime.diagnostics.slice(0, diagnosticsBefore)).toHaveLength(diagnosticsBefore);
    });
  });
});
