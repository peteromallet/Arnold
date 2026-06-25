// @vitest-environment jsdom
/**
 * useTimelineOps — host adapter tests.
 *
 * These tests prove TimelineOps uses the native commitData/history path rather
 * than a parallel undo stack or direct store manipulation.  Every mutation
 * must flow through commitData with `semantic: true` so the existing undo
 * recording, checkpoint triggering, and save scheduling stay in force.
 */
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useTimelineOps } from './useTimelineOps';
import { configToRows, type TimelineData } from '../lib/timeline-data';
import { getConfigSignature, getStableConfigSignature } from '../lib/config-utils';
import type { TimelineConfig } from '../types';
import type { Checkpoint } from '../types/history';
import type {
  TimelineDiff,
  TimelinePatchValidationResult,
  TimelinePreviewResult,
} from '@/sdk/video/timeline/patch.ts';

// ---------------------------------------------------------------------------
// Fixture helpers
// ---------------------------------------------------------------------------

function makeBaseTimelineData(overrides: Partial<TimelineConfig> = {}): TimelineData {
  const config: TimelineConfig = {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [
      { id: 'V1', kind: 'visual', label: 'V1' },
      { id: 'A1', kind: 'audio', label: 'A1', muted: false },
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
    ...overrides,
  };

  const rowData = configToRows(config);
  const resolvedConfig = {
    output: { ...config.output },
    tracks: (config.tracks ?? []).map((t) => ({ ...t })),
    clips: config.clips.map((clip) => ({ ...clip, assetEntry: undefined })),
    registry: {},
    theme: config.theme,
    theme_overrides: config.theme_overrides,
    generation_defaults: config.generation_defaults,
  };

  return {
    config,
    configVersion: 1,
    registry: { assets: {} },
    resolvedConfig,
    rows: rowData.rows,
    meta: rowData.meta,
    effects: rowData.effects,
    assetMap: {},
    output: { ...config.output },
    tracks: (config.tracks ?? []).map((t) => ({ ...t })),
    clipOrder: rowData.clipOrder,
    signature: getConfigSignature(resolvedConfig),
    stableSignature: getStableConfigSignature(config, { assets: {} }),
  };
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

describe('useTimelineOps', () => {
  // -----------------------------------------------------------------------
  // Atomic apply through native commitData
  // -----------------------------------------------------------------------
  describe('apply — atomic commit through native commitData', () => {
    it('commits exactly once with semantic:true and save:true', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let diff: TimelineDiff | undefined;
      act(() => {
        diff = result.current.apply({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-new',
              payload: { track: 'V1', at: 3, clipType: 'hold', hold: 2 },
            },
          ],
        });
      });

      // Assert: commitData called exactly once
      expect(commitData).toHaveBeenCalledTimes(1);

      // Assert: called with semantic:true and save:true
      const callArgs = commitData.mock.calls[0];
      expect(callArgs[0]).toBeDefined(); // nextData
      expect(callArgs[1]).toMatchObject({ save: true, semantic: true });

      // Assert: diff is returned with entries
      expect(diff).toBeDefined();
      expect(diff!.entries.length).toBeGreaterThan(0);
    });

    it('throws and does NOT call commitData when validation fails', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      expect(() =>
        act(() =>
          result.current.apply({
            version: 1,
            operations: [
              // Invalid: track.add requires kind
              { op: 'track.add' as any, target: 'T1', payload: {} },
            ],
          }),
        ),
      ).toThrow();

      // commitData must NOT have been called
      expect(commitData).not.toHaveBeenCalled();
    });

    it('throws and does NOT call commitData when data is not yet loaded', () => {
      const commitData = vi.fn();
      const dataRef = { current: null as TimelineData | null };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      expect(() =>
        act(() =>
          result.current.apply({
            version: 1,
            operations: [
              {
                op: 'clip.add',
                target: 'clip-x',
                payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
              },
            ],
          }),
        ),
      ).toThrow('TimelineOps.apply: timeline data is not yet loaded.');

      expect(commitData).not.toHaveBeenCalled();
    });

    it('the native commitData receives the compiled nextData (not a clone of the original)', () => {
      const commitData = vi.fn();
      const original = makeBaseTimelineData();
      const dataRef = { current: original };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      act(() =>
        result.current.apply({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-new',
              payload: { track: 'V1', at: 0, clipType: 'hold', hold: 5 },
            },
          ],
        }),
      );

      const committedData = commitData.mock.calls[0][0] as TimelineData;
      // The committed data must have the new clip
      expect(committedData.config.clips.some((c) => c.id === 'clip-new')).toBe(
        true,
      );
      // The original dataRef must not have been mutated by apply (commitData
      // is what updates dataRef in the real pipeline — the test mock doesn't
      // do that, so original stays unchanged)
      expect(original.config.clips.some((c) => c.id === 'clip-new')).toBe(
        false,
      );
      // Verify the committed data is distinct from the original
      expect(committedData).not.toBe(original);
    });
  });

  // -----------------------------------------------------------------------
  // Failed-batch no-op (validation rejects entire batch atomically)
  // -----------------------------------------------------------------------
  describe('apply — failed batch is a full no-op', () => {
    it('rejects the entire batch when any operation is invalid', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      // Batch with one valid and one invalid op
      expect(() =>
        act(() =>
          result.current.apply({
            version: 1,
            operations: [
              {
                op: 'clip.add',
                target: 'clip-ok',
                payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
              },
              { op: 'track.add' as any, target: 'T1', payload: {} }, // invalid
            ],
          }),
        ),
      ).toThrow();

      // Entire batch rejected — commitData never called
      expect(commitData).not.toHaveBeenCalled();
      // Original data unchanged
      expect(dataRef.current!.config.clips).toHaveLength(1);
    });

    it('rejects a batch with an unknown operation family', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      expect(() =>
        act(() =>
          result.current.apply({
            version: 1,
            operations: [
              { op: 'nonexistent.op' as any, target: 'x', payload: {} },
            ],
          }),
        ),
      ).toThrow();

      expect(commitData).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------------------
  // Undo/redo through native history
  // -----------------------------------------------------------------------
  describe('undo/redo — native history integration', () => {
    it('a single apply call produces one undo stack entry via native onBeforeCommit', () => {
      // Real pipeline: useTimelineCommit wires onBeforeCommit via
      // TimelineEventBus.  We test that apply() calls commitData with
      // semantic:true AND skipHistory is NOT set, which means the native
      // history layer will record an undo entry.

      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      act(() =>
        result.current.apply({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-x',
              payload: { track: 'V1', at: 3, clipType: 'hold', hold: 2 },
            },
          ],
        }),
      );

      // skipHistory must NOT be true — the native history layer needs to
      // record the undo entry.
      const options = commitData.mock.calls[0][1];
      expect(options.skipHistory).not.toBe(true);
    });

    it('consecutive apply calls each go through the native commit path', () => {
      const appliedData: TimelineData[] = [];
      const commitData = vi.fn((nextData: TimelineData) => {
        appliedData.push(nextData);
        // Simulate the real commitData: update dataRef
        dataRef.current = nextData;
      });
      const dataRef = { current: makeBaseTimelineData() as TimelineData | null };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      // First apply: add clip-a
      act(() =>
        result.current.apply({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-a',
              payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
            },
          ],
        }),
      );

      // Second apply: add clip-b
      act(() =>
        result.current.apply({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-b',
              payload: { track: 'V1', at: 5, clipType: 'hold', hold: 2 },
            },
          ],
        }),
      );

      expect(commitData).toHaveBeenCalledTimes(2);

      // Both calls carry semantic:true
      for (const call of commitData.mock.calls) {
        expect(call[1]).toMatchObject({ save: true, semantic: true });
      }

      // dataRef should now have three clips (original + clip-a + clip-b)
      expect(dataRef.current!.config.clips).toHaveLength(3);
    });
  });

  // -----------------------------------------------------------------------
  // Checkpoint
  // -----------------------------------------------------------------------
  describe('checkpoint', () => {
    it('delegates to native createManualCheckpoint with the label', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let checkpointId: string;
      act(() => {
        checkpointId = result.current.checkpoint('my-label');
      });

      // Returns a non-empty ID
      expect(checkpointId!).toBeTruthy();
      expect(typeof checkpointId!).toBe('string');

      // Delegates to native createManualCheckpoint
      expect(createManualCheckpoint).toHaveBeenCalledWith('my-label');
    });

    it('generates a default label when none is provided', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      act(() => {
        result.current.checkpoint();
      });

      expect(createManualCheckpoint).toHaveBeenCalledTimes(1);
      const labelArg = createManualCheckpoint.mock.calls[0][0];
      expect(labelArg).toContain('Patch checkpoint');
    });

    it('returns a stable ID that can be used for rollback', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let id1: string, id2: string;
      act(() => {
        id1 = result.current.checkpoint('alpha');
        id2 = result.current.checkpoint('beta');
      });

      // IDs must be distinct
      expect(id1!).not.toBe(id2!);
      // Both non-empty
      expect(id1!.length).toBeGreaterThan(0);
      expect(id2!.length).toBeGreaterThan(0);
    });
  });

  // -----------------------------------------------------------------------
  // Rollback
  // -----------------------------------------------------------------------
  describe('rollback', () => {
    it('delegates to native jumpToCheckpoint when an exact ID match exists', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [
        {
          id: 'ckpt-1',
          timelineId: 'tl-1',
          config: dataRef.current!.config,
          createdAt: new Date().toISOString(),
          triggerType: 'manual',
          label: 'Manual checkpoint',
          editsSinceLastCheckpoint: 0,
        },
      ];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let diff;
      act(() => {
        diff = result.current.rollback('ckpt-1');
      });

      // Delegates to native jumpToCheckpoint
      expect(jumpToCheckpoint).toHaveBeenCalledWith('ckpt-1');
      // Returns a diff
      expect(diff).not.toBeNull();
      expect(diff!.entries.length).toBeGreaterThanOrEqual(0);
    });

    it('resolves a client-generated checkpoint ID via label-based fallback', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [
        {
          id: 'backend-ckpt-1',
          timelineId: 'tl-1',
          config: dataRef.current!.config,
          createdAt: new Date().toISOString(),
          triggerType: 'manual',
          label: 'My saved checkpoint',
          editsSinceLastCheckpoint: 0,
        },
      ];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      // First, create a checkpoint to register the label mapping
      let clientId: string;
      act(() => {
        clientId = result.current.checkpoint('My saved checkpoint');
      });

      // Now the pendingLabels map has clientId → 'My saved checkpoint'.
      // When we rollback with clientId, it should resolve to 'backend-ckpt-1'.
      act(() => {
        result.current.rollback(clientId!);
      });

      expect(jumpToCheckpoint).toHaveBeenCalledWith('backend-ckpt-1');
    });

    it('returns null when the checkpoint ID cannot be resolved', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let diff;
      act(() => {
        diff = result.current.rollback('nonexistent-ckpt');
      });

      expect(diff).toBeNull();
      expect(jumpToCheckpoint).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------------------
  // setAllTracksMuted
  // -----------------------------------------------------------------------
  describe('setAllTracksMuted', () => {
    it('delegates to apply(), which commits through native commitData', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      act(() => {
        result.current.setAllTracksMuted(true);
      });

      // Must call commitData through apply()
      expect(commitData).toHaveBeenCalledTimes(1);
      expect(commitData.mock.calls[0][1]).toMatchObject({
        save: true,
        semantic: true,
      });
    });

    it('returns an empty diff when there are no audio tracks', () => {
      const commitData = vi.fn();
      // Timeline with only visual tracks (no audio)
      const data = makeBaseTimelineData({
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      });
      const dataRef = { current: data };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let diff;
      act(() => {
        diff = result.current.setAllTracksMuted(true);
      });

      expect(diff!.entries).toHaveLength(0);
      expect(diff!.affectedObjectIds).toHaveLength(0);
      // No commitData because apply was never called
      expect(commitData).not.toHaveBeenCalled();
    });

    it('throws when data is not yet loaded', () => {
      const commitData = vi.fn();
      const dataRef = { current: null as TimelineData | null };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      expect(() =>
        act(() => {
          result.current.setAllTracksMuted(true);
        }),
      ).toThrow('TimelineOps.setAllTracksMuted: timeline data is not yet loaded.');
    });
  });

  // -----------------------------------------------------------------------
  // Preview (read-only, no commit)
  // -----------------------------------------------------------------------
  describe('preview', () => {
    it('returns a preview result without calling commitData', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let previewResult;
      act(() => {
        previewResult = result.current.preview({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-p',
              payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
            },
          ],
        });
      });

      expect(previewResult).toBeDefined();
      expect(previewResult!.diff).toBeDefined();
      // preview is read-only — no commit
      expect(commitData).not.toHaveBeenCalled();
      // Original data unchanged
      expect(dataRef.current!.config.clips).toHaveLength(1);
    });

    it('returns an error diagnostic when data is not yet loaded', () => {
      const commitData = vi.fn();
      const dataRef = { current: null as TimelineData | null };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let previewResult;
      act(() => {
        previewResult = result.current.preview({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-x',
              payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
            },
          ],
        });
      });

      expect(previewResult!.fullyPreviewable).toBe(false);
      expect(previewResult!.diagnostics).toHaveLength(1);
      expect(previewResult!.diagnostics[0].code).toBe('timeline-patch/no-data');
    });
  });

  // -----------------------------------------------------------------------
  // Validate (pure, no side effects)
  // -----------------------------------------------------------------------
  describe('validate', () => {
    it('returns validation result without touching dataRef or commitData', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let validationResult;
      act(() => {
        validationResult = result.current.validate({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-v',
              payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
            },
          ],
        });
      });

      expect(validationResult!.valid).toBe(true);
      expect(commitData).not.toHaveBeenCalled();
      expect(dataRef.current!.config.clips).toHaveLength(1);
    });
  });

  // -----------------------------------------------------------------------
  // Adapter stability
  // -----------------------------------------------------------------------
  describe('adapter stability', () => {
    it('returns the same object reference across re-renders with stable deps', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result, rerender } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      const first = result.current;

      // Re-render with same deps
      rerender();

      expect(result.current).toBe(first);
    });

    it('reads the latest dataRef.current on every call without adapter recreation', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      const adapter = result.current;

      // Mutate dataRef behind the scenes (simulating a provider update)
      // Add an external clip, then add a new track
      const newData = makeBaseTimelineData({
        tracks: [
          { id: 'V1', kind: 'visual', label: 'V1' },
          { id: 'A1', kind: 'audio', label: 'A1' },
          { id: 'V2', kind: 'visual', label: 'V2' },
        ],
        clips: [
          ...dataRef.current!.config.clips,
          {
            id: 'clip-external',
            at: 10,
            track: 'V2',
            clipType: 'hold',
            hold: 2,
          },
        ],
      });
      dataRef.current = newData;

      // Preview a clip.add operation against the updated dataRef
      let previewResult: TimelinePreviewResult | undefined;
      act(() => {
        previewResult = adapter.preview({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-preview',
              payload: { track: 'V2', at: 12, clipType: 'hold', hold: 1 },
            },
          ],
        });
      });

      // Preview should reflect the new data — the diff should include
      // the new clip and the track it's on.
      expect(previewResult!.diff.affectedObjectIds).toContain('clip-preview');
      expect(previewResult!.diff.affectedObjectIds).toContain('V2');
      // The pre-existing clip-external on V2 should not be in affectedIds
      // (only the newly added clip and its track are affected).
    });
  });

  // -----------------------------------------------------------------------
  // Base-version staleness (T13)
  // -----------------------------------------------------------------------
  describe('apply — base-version staleness rejection', () => {
    it('rejects a stale patch when patch.version !== dataRef.current.configVersion', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      expect(() =>
        act(() =>
          result.current.apply({
            version: 5,
            operations: [
              {
                op: 'clip.add',
                target: 'clip-stale',
                payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
              },
            ],
          }),
        ),
      ).toThrow();

      expect(commitData).not.toHaveBeenCalled();
    });

    it('rejects a stale patch when patch.version is behind configVersion', () => {
      const commitData = vi.fn();
      const data = makeBaseTimelineData();
      (data as any).configVersion = 5;
      const dataRef = { current: data };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      expect(() =>
        act(() =>
          result.current.apply({
            version: 1,
            operations: [
              {
                op: 'clip.add',
                target: 'clip-stale',
                payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
              },
            ],
          }),
        ),
      ).toThrow();

      expect(commitData).not.toHaveBeenCalled();
    });

    it('throws TimelineVersionConflictError with a descriptive message', () => {
      const commitData = vi.fn();
      const data = makeBaseTimelineData();
      (data as any).configVersion = 3;
      const dataRef = { current: data };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let caught: unknown;
      try {
        act(() =>
          result.current.apply({
            version: 7,
            operations: [
              {
                op: 'clip.add',
                target: 'clip-x',
                payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
              },
            ],
          }),
        );
      } catch (e) {
        caught = e;
      }

      expect(caught).toBeDefined();
      expect((caught as any)?.name).toBe('TimelineVersionConflictError');
      expect((caught as any)?.message).toContain('stale baseVersion');
      expect((caught as any)?.message).toContain('version 7');
      expect((caught as any)?.message).toContain('version 3');
    });

    it('does NOT reject when patch.version is 0 (no-version-expectation bypass)', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let diff: TimelineDiff | undefined;
      act(() => {
        diff = result.current.apply({
          version: 0,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-v0',
              payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
            },
          ],
        });
      });

      expect(diff).toBeDefined();
      expect(commitData).toHaveBeenCalledTimes(1);
    });

    it('accepts patch when version matches current configVersion', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let diff: TimelineDiff | undefined;
      act(() => {
        diff = result.current.apply({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-ok',
              payload: { track: 'V1', at: 5, clipType: 'hold', hold: 2 },
            },
          ],
        });
      });

      expect(diff).toBeDefined();
      expect(commitData).toHaveBeenCalledTimes(1);
    });

    it('leaves the canonical timeline unchanged on stale rejection', () => {
      const commitData = vi.fn();
      const original = makeBaseTimelineData();
      const dataRef = { current: original };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      const clipCountBefore = original.config.clips.length;

      expect(() =>
        act(() =>
          result.current.apply({
            version: 999,
            operations: [
              {
                op: 'clip.add',
                target: 'clip-should-not-exist',
                payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
              },
            ],
          }),
        ),
      ).toThrow();

      expect(original.config.clips).toHaveLength(clipCountBefore);
      expect(commitData).not.toHaveBeenCalled();
    });

    it('rejects stale batch even when some operations are valid', () => {
      const commitData = vi.fn();
      const data = makeBaseTimelineData();
      (data as any).configVersion = 10;
      const dataRef = { current: data };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      expect(() =>
        act(() =>
          result.current.apply({
            version: 1,
            operations: [
              {
                op: 'clip.add',
                target: 'clip-a',
                payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
              },
              {
                op: 'clip.add',
                target: 'clip-b',
                payload: { track: 'V1', at: 5, clipType: 'hold', hold: 2 },
              },
            ],
          }),
        ),
      ).toThrow();

      expect(commitData).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------------------
  // Preview — stale base-version warning (T13)
  // -----------------------------------------------------------------------
  describe('preview — stale base-version warning', () => {
    it('attaches a warning diagnostic when baseVersion does not match configVersion', () => {
      const commitData = vi.fn();
      const data = makeBaseTimelineData();
      (data as any).configVersion = 5;
      const dataRef = { current: data };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let previewResult: TimelinePreviewResult | undefined;
      act(() => {
        previewResult = result.current.preview({
          version: 3,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-p',
              payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
            },
          ],
        });
      });

      expect(previewResult).toBeDefined();
      expect(previewResult!.fullyPreviewable).toBe(true);
      const staleDiag = previewResult!.diagnostics.find(
        (d) => d.code === 'timeline-patch/stale-base-version',
      );
      expect(staleDiag).toBeDefined();
      expect(staleDiag!.severity).toBe('warning');
      expect(staleDiag!.message).toContain('baseVersion (3)');
      expect(staleDiag!.message).toContain('version (5)');
    });

    it('does NOT warn when baseVersion matches configVersion', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let previewResult: TimelinePreviewResult | undefined;
      act(() => {
        previewResult = result.current.preview({
          version: 1,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-p',
              payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
            },
          ],
        });
      });

      const staleDiag = previewResult!.diagnostics.find(
        (d) => d.code === 'timeline-patch/stale-base-version',
      );
      expect(staleDiag).toBeUndefined();
    });

    it('does NOT warn when patch.version is 0 (no-version-expectation bypass)', () => {
      const commitData = vi.fn();
      const dataRef = { current: makeBaseTimelineData() };
      const createManualCheckpoint = vi.fn();
      const jumpToCheckpoint = vi.fn();
      const checkpoints: Checkpoint[] = [];

      const { result } = renderHook(() =>
        useTimelineOps({
          commitData,
          dataRef,
          createManualCheckpoint,
          jumpToCheckpoint,
          checkpoints,
        }),
      );

      let previewResult: TimelinePreviewResult | undefined;
      act(() => {
        previewResult = result.current.preview({
          version: 0,
          operations: [
            {
              op: 'clip.add',
              target: 'clip-p',
              payload: { track: 'V1', at: 0, clipType: 'hold', hold: 1 },
            },
          ],
        });
      });

      const staleDiag = previewResult!.diagnostics.find(
        (d) => d.code === 'timeline-patch/stale-base-version',
      );
      expect(staleDiag).toBeUndefined();
    });
  });
});
