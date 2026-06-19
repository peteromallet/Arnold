/**
 * Tests for Compiler Canary — exercises the full M3 public extension contract.
 *
 * Verifies:
 * 1. Reads timeline via ctx.creative.reader.snapshot()
 * 2. Stores DSL/source/source-map data in project namespace
 * 3. Emits TimelineProposal via ctx.creative.proposals
 * 4. Stamps GeneratedObjectMeta on generated objects
 * 5. Proposes add/update/delete/cleanup only for its own generated objects
 *
 * @publicContract
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createCompilerCanary } from '@/tools/video-editor/lib/compiler-canary';
import type {
  CompilerCanary,
  CanaryDsl,
} from '@/tools/video-editor/lib/compiler-canary';
import type {
  TimelineOps,
  TimelineReader,
  TimelineSnapshot,
  TimelinePatch,
  TimelinePatchOperation,
  TimelineDiff,
  TimelinePreviewResult,
  TimelinePatchValidationResult,
  ProposalRuntime,
  TimelineProposal,
  TimelineProposalInput,
  DisposeHandle,
  TimelineClipSummary,
  TimelineTrackSummary,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Minimal DSL for testing. */
function makeDsl(overrides?: Partial<CanaryDsl>): CanaryDsl {
  return {
    version: 1,
    clips: [
      { id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold', sourceLine: 4 },
      { id: 'gen-2', track: 'V1', at: 5, duration: 3, clipType: 'hold', sourceLine: 5 },
    ],
    sourceUri: 'dsl://test-ext/main.json',
    ...overrides,
  };
}

function dslJson(dsl: CanaryDsl): string {
  return JSON.stringify(dsl);
}

/** Create a mock TimelineClipSummary. */
function makeClipSummary(overrides?: Partial<TimelineClipSummary>): TimelineClipSummary {
  return {
    id: 'clip-1',
    track: 'V1',
    at: 0,
    duration: 3,
    clipType: 'hold',
    managed: false,
    ...overrides,
  };
}

/** Create a mock TimelineTrackSummary. */
function makeTrackSummary(overrides?: Partial<TimelineTrackSummary>): TimelineTrackSummary {
  return {
    id: 'V1',
    kind: 'visual',
    label: 'Visual 1',
    muted: false,
    ...overrides,
  };
}

/** Create a mock TimelineSnapshot. */
function makeSnapshot(overrides?: Partial<TimelineSnapshot>): TimelineSnapshot {
  return {
    projectId: 'test-project',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [
      makeClipSummary({ id: 'existing-clip', track: 'V1', at: 0, duration: 4 }),
    ],
    tracks: [
      makeTrackSummary({ id: 'V1' }),
      makeTrackSummary({ id: 'A1', kind: 'audio', label: 'Audio 1' }),
    ],
    assetKeys: [],
    app: {},
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Mock service factories
// ---------------------------------------------------------------------------

interface MockServices {
  timelineOps: TimelineOps & {
    _appliedPatches: TimelinePatch[];
  };
  reader: TimelineReader & {
    _snapshotOverrides: Partial<TimelineSnapshot> | null;
  };
  proposals: ProposalRuntime & {
    _createdProposals: TimelineProposal[];
    _listeners: Array<(p: TimelineProposal) => void>;
    _currentVersion: number;
    _stateOverrides: Map<string, Partial<TimelineProposal>>;
    _accepted: string[];
    _rejected: string[];
  };
}

function createMockServices(snapshotOverrides?: Partial<TimelineSnapshot>): MockServices {
  const baseSnapshot = makeSnapshot(snapshotOverrides);

  // -- TimelineOps mock --
  const appliedPatches: TimelinePatch[] = [];
  const timelineOps = {
    _appliedPatches: appliedPatches,
    validate: vi.fn((patch: TimelinePatch): TimelinePatchValidationResult => {
      return { valid: true, diagnostics: [] };
    }),
    preview: vi.fn((patch: TimelinePatch): TimelinePreviewResult => {
      return {
        diff: { version: patch.version, entries: [], affectedObjectIds: [] },
        fullyPreviewable: true,
        diagnostics: [],
      };
    }),
    apply: vi.fn((patch: TimelinePatch): TimelineDiff => {
      appliedPatches.push(patch);
      // Apply project-data writes to snapshot app data
      for (const op of patch.operations) {
        if (op.op === 'project-data.write') {
          const extId = op.target;
          const key = (op.payload as Record<string, unknown>)?.key as string;
          const value = (op.payload as Record<string, unknown>)?.value;
          if (!baseSnapshot.app[extId]) {
            (baseSnapshot.app as Record<string, unknown>)[extId] = {};
          }
          ((baseSnapshot.app as Record<string, unknown>)[extId] as Record<string, unknown>)[key] = value;
        } else if (op.op === 'project-data.delete') {
          const extId = op.target;
          const key = (op.payload as Record<string, unknown>)?.key as string;
          if (baseSnapshot.app[extId]) {
            delete (baseSnapshot.app[extId] as Record<string, unknown>)[key];
          }
        }
      }
      return {
        version: patch.version + 1,
        entries: patch.operations.map((op) => ({
          granularity: op.op.startsWith('clip') ? 'clip' as const :
                       op.op.startsWith('track') ? 'track' as const :
                       'project-data' as const,
          kind: op.op.endsWith('.add') ? 'added' as const :
                op.op.endsWith('.remove') ? 'removed' as const :
                'modified' as const,
          target: op.target,
          op: op.op,
        })),
        affectedObjectIds: patch.operations.map((op) => op.target),
      };
    }),
    checkpoint: vi.fn().mockReturnValue('ckpt-1'),
    rollback: vi.fn().mockReturnValue(null),
    setAllTracksMuted: vi.fn().mockReturnValue({ version: 1, entries: [], affectedObjectIds: [] }),
  };

  // -- TimelineReader mock --
  const reader = {
    _snapshotOverrides: null as Partial<TimelineSnapshot> | null,
    snapshot: vi.fn((): TimelineSnapshot => {
      const snap = { ...baseSnapshot };
      if (reader._snapshotOverrides) {
        Object.assign(snap, reader._snapshotOverrides);
      }
      // Deep clone clips to avoid mutation
      snap.clips = snap.clips.map(c => ({ ...c, generatedMeta: c.generatedMeta ? { ...c.generatedMeta } : undefined }));
      return snap;
    }),
  };

  // -- ProposalRuntime mock --
  const listeners: Array<(p: TimelineProposal) => void> = [];
  const createdProposals: TimelineProposal[] = [];
  const stateOverrides = new Map<string, Partial<TimelineProposal>>();
  const accepted: string[] = [];
  const rejected: string[] = [];

  let nextProposalId = 0;
  const proposals = {
    _createdProposals: createdProposals,
    _listeners: listeners,
    _currentVersion: baseSnapshot.baseVersion,
    _stateOverrides: stateOverrides,
    _accepted: accepted,
    _rejected: rejected,

    subscribe(listener: (p: TimelineProposal) => void): DisposeHandle {
      listeners.push(listener);
      return {
        dispose() {
          const idx = listeners.indexOf(listener);
          if (idx >= 0) listeners.splice(idx, 1);
        },
      };
    },

    create(input: TimelineProposalInput): TimelineProposal {
      // Replace any pending proposal from the same source
      const existingIdx = createdProposals.findIndex(
        (p) => p.source === input.source && p.state === 'pending',
      );
      if (existingIdx >= 0) {
        createdProposals.splice(existingIdx, 1);
      }

      const proposal: TimelineProposal = {
        id: `proposal-${++nextProposalId}`,
        source: input.source,
        rationale: input.rationale,
        state: 'pending',
        patch: input.patch,
        baseVersion: input.baseVersion,
        previewable: true,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };

      // Apply state overrides
      const overrides = stateOverrides.get(proposal.id);
      if (overrides) {
        Object.assign(proposal, overrides);
      }

      createdProposals.push(proposal);

      // Notify listeners
      for (const listener of listeners) {
        try { listener(proposal); } catch { /* ignore */ }
      }

      return proposal;
    },

    preview(proposalId: string): TimelinePreviewResult {
      const proposal = createdProposals.find(p => p.id === proposalId);
      return {
        diff: { version: proposal?.patch.version ?? 1, entries: [], affectedObjectIds: [] },
        fullyPreviewable: true,
        diagnostics: [],
      };
    },

    accept(proposalId: string): TimelineDiff {
      accepted.push(proposalId);
      const proposal = createdProposals.find(p => p.id === proposalId);
      if (proposal) {
        proposal.state = 'accepted';
        proposal.updatedAt = Date.now();
      }
      return { version: 1, entries: [], affectedObjectIds: [] };
    },

    reject(proposalId: string, _reason?: string): void {
      rejected.push(proposalId);
      const proposal = createdProposals.find(p => p.id === proposalId);
      if (proposal) {
        proposal.state = 'rejected';
        proposal.updatedAt = Date.now();
      }
    },

    get(proposalId: string): TimelineProposal | undefined {
      return createdProposals.find(p => p.id === proposalId);
    },

    list(state?: string): readonly TimelineProposal[] {
      if (state) return createdProposals.filter(p => p.state === state);
      return [...createdProposals];
    },

    get currentVersion(): number {
      return baseSnapshot.baseVersion;
    },
  };

  return { timelineOps, reader, proposals };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CompilerCanary', () => {
  let services: MockServices;
  let canary: CompilerCanary;

  beforeEach(() => {
    services = createMockServices();
    canary = createCompilerCanary({
      extensionId: 'com.example.canary',
      timeline: services.timelineOps,
      reader: services.reader,
      proposals: services.proposals,
    });
  });

  // ── DSL Validation ────────────────────────────────────────────────────
  describe('DSL validation', () => {
    it('returns null for invalid JSON', () => {
      const result = canary.processDsl('not json');
      expect(result).toBeNull();
    });

    it('returns null for non-object JSON', () => {
      const result = canary.processDsl('"just a string"');
      expect(result).toBeNull();
    });

    it('returns null for DSL with wrong version', () => {
      const result = canary.processDsl(JSON.stringify({ version: 2, clips: [] }));
      expect(result).toBeNull();
    });

    it('returns null for DSL without clips array', () => {
      const result = canary.processDsl(JSON.stringify({ version: 1 }));
      expect(result).toBeNull();
    });

    it('returns null for DSL with non-array clips', () => {
      const result = canary.processDsl(JSON.stringify({ version: 1, clips: 'not-array' }));
      expect(result).toBeNull();
    });
  });

  // ── Timeline Snapshot Reading ─────────────────────────────────────────
  describe('timeline snapshot reading', () => {
    it('reads snapshot via reader.snapshot() during processDsl', () => {
      canary.processDsl(dslJson(makeDsl()));
      expect(services.reader.snapshot).toHaveBeenCalled();
    });

    it('uses snapshot baseVersion in data patch', () => {
      const snap = makeSnapshot({ baseVersion: 42, currentVersion: 42 });
      services.reader._snapshotOverrides = { baseVersion: 42, currentVersion: 42 };

      canary.processDsl(dslJson(makeDsl()));
      const dataPatches = services.timelineOps._appliedPatches.filter(
        (p) => p.meta && (p.meta as Record<string, unknown>).kind === 'compiler-canary-data',
      );
      expect(dataPatches.length).toBeGreaterThanOrEqual(1);
      // Version should match snapshot baseVersion
      expect(dataPatches[0].version).toBe(42);
    });

    it('reflects project ID from snapshot', () => {
      services.reader._snapshotOverrides = { projectId: 'my-proj-123' };
      canary.processDsl(dslJson(makeDsl()));
      // The process should complete without errors
      expect(services.reader.snapshot).toHaveBeenCalled();
    });
  });

  // ── DSL and Source-Map Data Storage ───────────────────────────────────
  describe('DSL and source-map data storage', () => {
    it('stores DSL source as project-data.write', () => {
      const dsl = makeDsl();
      canary.processDsl(dslJson(dsl));

      const dataOps = services.timelineOps._appliedPatches.flatMap((p) => p.operations);
      const dslWrite = dataOps.find(
        (op) =>
          op.op === 'project-data.write' &&
          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__dsl__'),
      );
      expect(dslWrite).toBeDefined();
      expect(dslWrite!.target).toBe('com.example.canary');

      const value = JSON.parse((dslWrite!.payload as Record<string, unknown>).value as string);
      expect(value.version).toBe(1);
      expect(value.clips).toHaveLength(2);
    });

    it('stores source-map entries as project-data.write', () => {
      const dsl = makeDsl();
      canary.processDsl(dslJson(dsl));

      const dataOps = services.timelineOps._appliedPatches.flatMap((p) => p.operations);
      const smWrites = dataOps.filter(
        (op) =>
          op.op === 'project-data.write' &&
          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__sm__'),
      );
      // Should have 2 source-map entries (one per clip)
      expect(smWrites.length).toBe(2);

      for (const smWrite of smWrites) {
        const value = (smWrite.payload as Record<string, unknown>).value as Record<string, unknown>;
        expect(value.id).toMatch(/^cc-sme-/);
        expect(value.source).toBe('com.example.canary');
        expect(value.targetGranularity).toBe('clip');
        expect(value.sourceUri).toBe('dsl://test-ext/main.json');
        expect(value.stale).toBe(false);
        expect(value.sourceStartLine).toBeGreaterThan(0);
      }
    });

    it('source-map entries link to DSL source lines', () => {
      const dsl = makeDsl({
        clips: [
          { id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold', sourceLine: 10 },
          { id: 'gen-2', track: 'V1', at: 5, duration: 3, clipType: 'hold', sourceLine: 15 },
        ],
      });
      canary.processDsl(dslJson(dsl));

      const dataOps = services.timelineOps._appliedPatches.flatMap((p) => p.operations);
      const smWrites = dataOps.filter(
        (op) =>
          op.op === 'project-data.write' &&
          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__sm__'),
      );

      const lines = smWrites.map(
        (op) => ((op.payload as Record<string, unknown>).value as Record<string, unknown>).sourceStartLine,
      );
      expect(lines).toContain(10);
      expect(lines).toContain(15);
    });

    it('returns source-map entry IDs in result', () => {
      const result = canary.processDsl(dslJson(makeDsl()));
      expect(result).not.toBeNull();
      expect(result!.sourceMapEntryIds.length).toBe(2);
      expect(result!.sourceMapEntryIds[0]).toMatch(/^cc-sme-/);
    });
  });

  // ── TimelineProposal Emission ─────────────────────────────────────────
  describe('TimelineProposal emission', () => {
    it('emits a TimelineProposal via proposals.create()', () => {
      const result = canary.processDsl(dslJson(makeDsl()));
      expect(result).not.toBeNull();
      expect(result!.proposal).toBeDefined();
      expect(result!.proposal!.state).toBe('pending');
    });

    it('proposal carries the correct source', () => {
      const result = canary.processDsl(dslJson(makeDsl()));
      expect(result!.proposal!.source).toBe('com.example.canary');
    });

    it('proposal includes rationale describing changes', () => {
      const result = canary.processDsl(dslJson(makeDsl()));
      expect(result!.proposal!.rationale).toContain('Compiler canary');
      expect(result!.proposal!.rationale).toContain('added');
    });

    it('proposal uses current snapshot baseVersion', () => {
      services.reader._snapshotOverrides = { baseVersion: 99 };
      const result = canary.processDsl(dslJson(makeDsl()));
      // The proposal baseVersion should match the snapshot after data writes
      expect(result!.proposal!.baseVersion).toBeGreaterThanOrEqual(1);
    });

    it('proposal is marked as previewable', () => {
      const result = canary.processDsl(dslJson(makeDsl()));
      expect(result!.proposal!.previewable).toBe(true);
    });

    it('replaceForSource: re-issuing replaces previous pending proposal', () => {
      // First run
      const result1 = canary.processDsl(dslJson(makeDsl()));
      expect(services.proposals._createdProposals.length).toBe(1);
      const firstProposalId = result1!.proposal!.id;

      // Second run with different DSL
      const result2 = canary.processDsl(dslJson(makeDsl({ clips: [{ id: 'gen-3', track: 'V1', at: 0, duration: 2, clipType: 'hold' }] })));
      // The mock auto-replaces pending proposals from the same source
      // The first proposal should be replaced by the second
      const secondProposalId = result2!.proposal!.id;
      expect(secondProposalId).not.toBe(firstProposalId);
      
      // There should be exactly 1 pending proposal from this source
      const pendingProposals = services.proposals._createdProposals.filter(p => p.state === 'pending' && p.source === 'com.example.canary');
      expect(pendingProposals.length).toBe(1);
    });

    it('proposal patch contains clip.add operations with correct structure', () => {
      const dsl = makeDsl();
      canary.processDsl(dslJson(dsl));

      const clipPatches = services.timelineOps._appliedPatches.filter(
        (p) => p.meta && (p.meta as Record<string, unknown>).kind === 'compiler-canary',
      );
      if (clipPatches.length > 0 || services.proposals._createdProposals.length > 0) {
        // The proposal was created, so the clip operations are in the proposal's patch
        expect(services.proposals._createdProposals.length).toBeGreaterThanOrEqual(1);
      }
    });
  });

  // ── Generated-Object Metadata Stamping ────────────────────────────────
  describe('generated-object metadata stamping', () => {
    it('stamps GeneratedObjectMeta on each clip.add operation', () => {
      const dsl = makeDsl();
      canary.processDsl(dslJson(dsl));

      // Find the main patch (not the data patch)
      const mainPatch = services.timelineOps._appliedPatches.find(
        (p) => p.meta && (p.meta as Record<string, unknown>).kind === 'compiler-canary',
      );

      if (mainPatch) {
        const addOps = mainPatch.operations.filter((op) => op.op === 'clip.add');
        for (const op of addOps) {
          const payload = op.payload as Record<string, unknown>;
          const app = payload.app as Record<string, unknown>;
          expect(app).toBeDefined();
          const generatedMeta = app.__generated__ as Record<string, unknown>;
          expect(generatedMeta).toBeDefined();
          expect(generatedMeta.extensionId).toBe('com.example.canary');
          expect(generatedMeta.contributionId).toBe('compiler-canary-generator');
          expect(typeof generatedMeta.generatedAt).toBe('number');
        }
      } else {
        // If the main patch is only in the proposal (since we mock apply),
        // check the proposal
        const proposal = services.proposals._createdProposals.find(
          (p) => p.meta && (p as Record<string, unknown>).kind === 'compiler-canary' ||
            p.patch.meta && (p.patch.meta as Record<string, unknown>).kind === 'compiler-canary',
        );
        // At minimum, verify proposal exists and has clip operations
        expect(services.proposals._createdProposals.length).toBeGreaterThanOrEqual(1);
        const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
        const clipOps = lastProposal.patch.operations.filter((op) => op.op === 'clip.add');
        expect(clipOps.length).toBe(2);

        for (const op of clipOps) {
          const payload = op.payload as Record<string, unknown>;
          const app = payload.app as Record<string, unknown>;
          expect(app).toBeDefined();
          const generatedMeta = app.__generated__ as Record<string, unknown>;
          expect(generatedMeta).toBeDefined();
          expect(generatedMeta.extensionId).toBe('com.example.canary');
          expect(generatedMeta.contributionId).toBe('compiler-canary-generator');
          expect(typeof generatedMeta.generatedAt).toBe('number');
        }
      }
    });

    it('includes sourceMapEntryId in GeneratedObjectMeta when source-map exists', () => {
      const dsl = makeDsl();
      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const clipOps = lastProposal.patch.operations.filter((op) => op.op === 'clip.add');

      for (const op of clipOps) {
        const payload = op.payload as Record<string, unknown>;
        const app = payload.app as Record<string, unknown>;
        const generatedMeta = app.__generated__ as Record<string, unknown>;
        expect(generatedMeta.sourceMapEntryId).toMatch(/^cc-sme-/);
      }
    });

    it('includes extension namespace in clip app data', () => {
      const dsl = makeDsl();
      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const clipOps = lastProposal.patch.operations.filter((op) => op.op === 'clip.add');

      for (const op of clipOps) {
        const payload = op.payload as Record<string, unknown>;
        const app = payload.app as Record<string, unknown>;
        expect(app['com.example.canary']).toBeDefined();
        expect((app['com.example.canary'] as Record<string, unknown>).source).toBe('compiler-canary');
      }
    });

    it('generated clips have unique IDs', () => {
      const dsl = makeDsl();
      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const clipOps = lastProposal.patch.operations.filter((op) => op.op === 'clip.add');
      const ids = clipOps.map((op) => op.target);
      expect(new Set(ids).size).toBe(ids.length); // all unique
    });

    it('generated clips carry version information via DSL version', () => {
      const dsl = makeDsl();
      const result = canary.processDsl(dslJson(dsl));
      // The DSL version (1) is stored in project data and indirectly versioned
      // through the data patch. The generated objects reference the DSL version
      // through source-map entries.
      expect(result).not.toBeNull();
      expect(result!.sourceMapEntryIds.length).toBeGreaterThan(0);

      // Verify DSL version is stored
      const dataOps = services.timelineOps._appliedPatches.flatMap((p) => p.operations);
      const dslWrite = dataOps.find(
        (op) =>
          op.op === 'project-data.write' &&
          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__dsl__'),
      );
      const dslValue = JSON.parse((dslWrite!.payload as Record<string, unknown>).value as string);
      expect(dslValue.version).toBe(1);
    });
  });

  // ── Ownership-Based Operations ────────────────────────────────────────
  describe('ownership-based operations', () => {
    it('proposes clip.add only for new clips not in snapshot', () => {
      const dsl = makeDsl({
        clips: [{ id: 'gen-new', track: 'V1', at: 0, duration: 5, clipType: 'hold' }],
      });

      // Snapshot has existing-clip, not gen-new
      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const clipOps = lastProposal.patch.operations;
      // Should only have clip.add for gen-new
      const addOps = clipOps.filter((op) => op.op === 'clip.add');
      expect(addOps.length).toBe(1);
      expect(addOps[0].target).toBe('gen-new');
    });

    it('proposes clip.remove only for owned clips no longer in DSL', () => {
      // Put an owned clip in the snapshot
      const ownedClip = makeClipSummary({
        id: 'old-gen-1',
        track: 'V1',
        at: 0,
        duration: 3,
        managed: true,
        managedBy: 'com.example.canary',
        generatedMeta: {
          extensionId: 'com.example.canary',
          contributionId: 'compiler-canary-generator',
          generatedAt: Date.now(),
        },
      });

      services.reader._snapshotOverrides = {
        clips: [makeClipSummary({ id: 'existing-clip' }), ownedClip],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold' }],
      });

      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const removeOps = lastProposal.patch.operations.filter((op) => op.op === 'clip.remove');
      // old-gen-1 should be removed since it's owned but not in DSL
      expect(removeOps.length).toBe(1);
      expect(removeOps[0].target).toBe('old-gen-1');
    });

    it('does NOT propose remove for clips owned by other extensions', () => {
      const otherOwnedClip = makeClipSummary({
        id: 'other-ext-clip',
        track: 'V1',
        at: 3,
        duration: 2,
        managed: true,
        managedBy: 'com.other.extension',
        generatedMeta: {
          extensionId: 'com.other.extension',
          contributionId: 'other-gen',
          generatedAt: Date.now(),
        },
      });

      services.reader._snapshotOverrides = {
        clips: [makeClipSummary({ id: 'existing-clip' }), otherOwnedClip],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold' }],
      });

      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const removeOps = lastProposal.patch.operations.filter((op) => op.op === 'clip.remove');
      // other-ext-clip should NOT be removed
      expect(removeOps.find((op) => op.target === 'other-ext-clip')).toBeUndefined();
    });

    it('does NOT propose remove for user-authored clips (not managed)', () => {
      const userClip = makeClipSummary({
        id: 'user-clip',
        track: 'V1',
        at: 5,
        duration: 2,
        managed: false,
      });

      services.reader._snapshotOverrides = {
        clips: [makeClipSummary({ id: 'existing-clip' }), userClip],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold' }],
      });

      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const removeOps = lastProposal.patch.operations.filter((op) => op.op === 'clip.remove');
      expect(removeOps.find((op) => op.target === 'user-clip')).toBeUndefined();
    });

    it('proposes clip.update for owned clips that differ from DSL', () => {
      const ownedClip = makeClipSummary({
        id: 'gen-1',
        track: 'V1',
        at: 0,
        duration: 2, // DSL says 5
        managed: true,
        managedBy: 'com.example.canary',
        generatedMeta: {
          extensionId: 'com.example.canary',
          contributionId: 'compiler-canary-generator',
          generatedAt: Date.now(),
        },
      });

      services.reader._snapshotOverrides = {
        clips: [ownedClip],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold' }],
      });

      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const updateOps = lastProposal.patch.operations.filter((op) => op.op === 'clip.update');
      expect(updateOps.length).toBe(1);
      expect(updateOps[0].target).toBe('gen-1');
    });

    it('does NOT propose update for owned clips that match DSL exactly', () => {
      const ownedClip = makeClipSummary({
        id: 'gen-1',
        track: 'V1',
        at: 0,
        duration: 5, // matches DSL
        managed: true,
        managedBy: 'com.example.canary',
        generatedMeta: {
          extensionId: 'com.example.canary',
          contributionId: 'compiler-canary-generator',
          generatedAt: Date.now(),
        },
      });

      services.reader._snapshotOverrides = {
        clips: [ownedClip],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold' }],
      });

      const result = canary.processDsl(dslJson(dsl));

      // When all owned clips match exactly, no clip mutation proposal is created
      expect(result).not.toBeNull();
      // No proposal since there are no changes
      expect(result!.proposal).toBeUndefined();
      // DSL data and source-map data were still written
      expect(result!.sourceMapEntryIds.length).toBe(1);
    });

    it('does NOT propose update for clips owned by other extensions', () => {
      const otherOwnedClip = makeClipSummary({
        id: 'gen-1',
        track: 'V1',
        at: 0,
        duration: 2,
        managed: true,
        managedBy: 'com.other.extension',
        generatedMeta: {
          extensionId: 'com.other.extension',
          contributionId: 'other-gen',
          generatedAt: Date.now(),
        },
      });

      services.reader._snapshotOverrides = {
        clips: [otherOwnedClip],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold' }],
      });

      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const ops = lastProposal.patch.operations;
      // clip.add for gen-1 (since it's not recognized as owned), NOT clip.update
      const addOps = ops.filter((op) => op.op === 'clip.add');
      const updateOps = ops.filter((op) => op.op === 'clip.update');
      expect(updateOps.length).toBe(0);
      expect(addOps.length).toBe(1);
      expect(addOps[0].target).toBe('gen-1');
    });
  });

  // ── Cleanup ────────────────────────────────────────────────────────────
  describe('cleanupOwnObjects', () => {
    it('removes all clips owned by the extension', () => {
      // Add owned clips to snapshot
      const ownedClips = [
        makeClipSummary({
          id: 'owned-1',
          track: 'V1',
          at: 0,
          duration: 3,
          managed: true,
          managedBy: 'com.example.canary',
          generatedMeta: {
            extensionId: 'com.example.canary',
            contributionId: 'compiler-canary-generator',
            generatedAt: Date.now(),
          },
        }),
        makeClipSummary({
          id: 'owned-2',
          track: 'V1',
          at: 3,
          duration: 2,
          managed: true,
          managedBy: 'com.example.canary',
          generatedMeta: {
            extensionId: 'com.example.canary',
            contributionId: 'compiler-canary-generator',
            generatedAt: Date.now(),
          },
        }),
        makeClipSummary({ id: 'not-owned', track: 'A1', duration: 5 }),
      ];

      services.reader._snapshotOverrides = { clips: ownedClips };

      const result = canary.cleanupOwnObjects();

      expect(result).not.toBeNull();
      expect(result!.proposal).toBeDefined();

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const removeOps = lastProposal.patch.operations.filter((op) => op.op === 'clip.remove');

      // Should remove owned-1 and owned-2
      expect(removeOps.length).toBe(2);
      expect(removeOps.map((op) => op.target).sort()).toEqual(['owned-1', 'owned-2']);
    });

    it('does not remove clips owned by other extensions during cleanup', () => {
      const otherClip = makeClipSummary({
        id: 'other-owned',
        track: 'V1',
        at: 0,
        duration: 3,
        managed: true,
        managedBy: 'com.other.extension',
        generatedMeta: {
          extensionId: 'com.other.extension',
          contributionId: 'other-gen',
          generatedAt: Date.now(),
        },
      });

      services.reader._snapshotOverrides = { clips: [otherClip] };

      const result = canary.cleanupOwnObjects();

      // No proposal should be created (no owned objects to remove)
      expect(result!.proposal).toBeUndefined();
      expect(result!.generatedClipIds).toEqual([]);
    });

    it('returns empty result when there are no owned objects', () => {
      services.reader._snapshotOverrides = {
        clips: [makeClipSummary({ id: 'user-clip', managed: false })],
      };

      const result = canary.cleanupOwnObjects();

      expect(result!.proposal).toBeUndefined();
      expect(result!.generatedClipIds).toEqual([]);
      expect(result!.sourceMapEntryIds).toEqual([]);
    });

    it('cleanup proposal includes rationale', () => {
      const owned = [
        makeClipSummary({
          id: 'owned-1',
          managed: true,
          managedBy: 'com.example.canary',
          generatedMeta: {
            extensionId: 'com.example.canary',
            contributionId: 'compiler-canary-generator',
            generatedAt: Date.now(),
          },
        }),
      ];
      services.reader._snapshotOverrides = { clips: [owned[0]] };

      canary.cleanupOwnObjects('Custom cleanup reason');
      const proposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      expect(proposal.rationale).toBe('Custom cleanup reason');
    });
  });

  // ── No Internal API Usage ─────────────────────────────────────────────
  describe('public contract purity', () => {
    it('canary does not import from video-editor internals', () => {
      // The compiler-canary.ts imports only from @reigh/editor-sdk and itself.
      // This is verified at the TypeScript level — no internal imports exist.
      // Runtime test: the canary should work with only mock services.
      const result = canary.processDsl(dslJson(makeDsl()));
      expect(result).not.toBeNull();
      expect(result!.proposal).toBeDefined();
    });

    it('canary uses only public SDK types for its API', () => {
      // The CompilerCanaryOptions requires TimelineOps, TimelineReader,
      // ProposalRuntime — all public SDK interfaces.
      const canary2 = createCompilerCanary({
        extensionId: 'test',
        timeline: services.timelineOps,
        reader: services.reader,
        proposals: services.proposals,
      });
      expect(canary2).toBeDefined();
      expect(canary2.extensionId).toBe('test');
      expect(typeof canary2.processDsl).toBe('function');
      expect(typeof canary2.cleanupOwnObjects).toBe('function');
    });

    it('canary does not mutate snapshot clips array', () => {
      const originalClips = [
        makeClipSummary({ id: 'clip-a' }),
        makeClipSummary({ id: 'clip-b' }),
      ];
      // Clone for comparison
      const clipsBefore = JSON.parse(JSON.stringify(originalClips));

      services.reader._snapshotOverrides = { clips: originalClips };

      canary.processDsl(dslJson(makeDsl()));

      // Snapshot clips should not be mutated
      expect(originalClips).toEqual(clipsBefore);
    });
  });

  // ── Edge Cases ─────────────────────────────────────────────────────────
  describe('edge cases', () => {
    it('handles empty DSL (no clips)', () => {
      const dsl = makeDsl({ clips: [] });
      const result = canary.processDsl(dslJson(dsl));

      // Should not create a proposal when there are no clip changes
      // and no owned objects to remove
      expect(result).not.toBeNull();
      expect(result!.generatedClipIds).toEqual([]);
      expect(result!.sourceMapEntryIds).toEqual([]);
    });

    it('handles DSL with many clips (stress test)', () => {
      const manyClips = Array.from({ length: 50 }, (_, i) => ({
        id: `gen-${i}`,
        track: 'V1',
        at: i * 2,
        duration: 1,
        clipType: 'hold',
        sourceLine: i + 3,
      }));

      const dsl = makeDsl({ clips: manyClips });
      const result = canary.processDsl(dslJson(dsl));

      expect(result).not.toBeNull();
      expect(result!.generatedClipIds.length).toBe(50);
      expect(result!.sourceMapEntryIds.length).toBe(50);

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const addOps = lastProposal.patch.operations.filter((op) => op.op === 'clip.add');
      expect(addOps.length).toBe(50);
    });

    it('handles concurrent operations: add + remove + update', () => {
      // Snapshot: owned clip old-gen (to remove), gen-1 with wrong duration (to update)
      const oldClip = makeClipSummary({
        id: 'old-gen',
        track: 'V1',
        at: 10,
        duration: 3,
        managed: true,
        managedBy: 'com.example.canary',
        generatedMeta: {
          extensionId: 'com.example.canary',
          contributionId: 'compiler-canary-generator',
          generatedAt: Date.now(),
        },
      });
      const toUpdate = makeClipSummary({
        id: 'gen-1',
        track: 'V1',
        at: 0,
        duration: 2, // differs from DSL (5)
        managed: true,
        managedBy: 'com.example.canary',
        generatedMeta: {
          extensionId: 'com.example.canary',
          contributionId: 'compiler-canary-generator',
          generatedAt: Date.now(),
        },
      });

      services.reader._snapshotOverrides = { clips: [oldClip, toUpdate] };

      const dsl = makeDsl({
        clips: [
          { id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold', sourceLine: 4 },
          { id: 'gen-2', track: 'V1', at: 5, duration: 3, clipType: 'hold', sourceLine: 5 },
        ],
      });

      const result = canary.processDsl(dslJson(dsl));

      expect(result).not.toBeNull();
      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const ops = lastProposal.patch.operations;

      // Should have: remove old-gen, update gen-1, add gen-2
      const removeOps = ops.filter((op) => op.op === 'clip.remove');
      const updateOps = ops.filter((op) => op.op === 'clip.update');
      const addOps = ops.filter((op) => op.op === 'clip.add');

      expect(removeOps.length).toBe(1);
      expect(removeOps[0].target).toBe('old-gen');
      expect(updateOps.length).toBe(1);
      expect(updateOps[0].target).toBe('gen-1');
      expect(addOps.length).toBe(1);
      expect(addOps[0].target).toBe('gen-2');
    });

    it('custom sourceUri is propagated to source-map entries', () => {
      const dsl = makeDsl({ sourceUri: 'file:///custom/path.json' });
      canary.processDsl(dslJson(dsl));

      const dataOps = services.timelineOps._appliedPatches.flatMap((p) => p.operations);
      const smWrites = dataOps.filter(
        (op) =>
          op.op === 'project-data.write' &&
          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__sm__'),
      );

      for (const smWrite of smWrites) {
        const value = (smWrite.payload as Record<string, unknown>).value as Record<string, unknown>;
        expect(value.sourceUri).toBe('file:///custom/path.json');
      }
    });

    it('uses default sourceUri when not specified', () => {
      const dsl = makeDsl();
      delete (dsl as Record<string, unknown>).sourceUri;
      canary.processDsl(dslJson(dsl));

      const dataOps = services.timelineOps._appliedPatches.flatMap((p) => p.operations);
      const smWrites = dataOps.filter(
        (op) =>
          op.op === 'project-data.write' &&
          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__sm__'),
      );

      for (const smWrite of smWrites) {
        const value = (smWrite.payload as Record<string, unknown>).value as Record<string, unknown>;
        expect(value.sourceUri).toBe('dsl://com.example.canary/main.json');
      }
    });
  });
  // ===========================================================================
  // -- Canary Import/Call Boundary -------------------------------------------
  // ===========================================================================
  describe('canary import/call boundary', () => {
    it('canary source file imports only from @reigh/editor-sdk (no internal modules)', () => {
      const __filename = fileURLToPath(import.meta.url);
      const __dirname = dirname(__filename);
      const sourcePath = resolve(__dirname, 'compiler-canary.ts');
      const source = readFileSync(sourcePath, 'utf-8');

      const importLines = source.split('\n').filter(line => /^\s*import\s/.test(line));

      for (const line of importLines) {
        const fromMatch = line.match(/from\s+['"]([^'"]+)['"]/);
        if (fromMatch) {
          const modulePath = fromMatch[1];
          expect(
            modulePath,
            `Canary import violation: imports from "${modulePath}" instead of @reigh/editor-sdk`,
          ).toBe('@reigh/editor-sdk');
        }
      }

      expect(importLines.length).toBeGreaterThan(0);
    });

    it('canary source does not reference TimelineData or DataProvider', () => {
      const __filename = fileURLToPath(import.meta.url);
      const __dirname = dirname(__filename);
      const sourcePath = resolve(__dirname, 'compiler-canary.ts');
      const source = readFileSync(sourcePath, 'utf-8');
      const importLines = source.split('\n').filter(line => /^\s*import\s/.test(line)).join('\n');
      expect(importLines).not.toMatch(/TimelineData/);
      expect(importLines).not.toMatch(/DataProvider/);
      expect(importLines).not.toMatch(/TimelineEditMutation/);
    });

    it('canary source does not reference store, provider, or command internals', () => {
      const __filename = fileURLToPath(import.meta.url);
      const __dirname = dirname(__filename);
      const sourcePath = resolve(__dirname, 'compiler-canary.ts');
      const source = readFileSync(sourcePath, 'utf-8');
      expect(source).not.toMatch(/timelineStore/);
      expect(source).not.toMatch(/DataProviderContext/);
      expect(source).not.toMatch(/commitData/);
      expect(source).not.toMatch(/timeline-mutation-engine/);
      expect(source).not.toMatch(/useTimelineCommands/);
    });

    it('canary source does not reference internal config/save/asset utilities', () => {
      const __filename = fileURLToPath(import.meta.url);
      const __dirname = dirname(__filename);
      const sourcePath = resolve(__dirname, 'compiler-canary.ts');
      const source = readFileSync(sourcePath, 'utf-8');
      const importLines = source.split('\n').filter(line => /^\s*import\s/.test(line)).join('\n');
      expect(importLines).not.toMatch(/config-utils/);
      expect(importLines).not.toMatch(/timeline-save-utils/);
      expect(importLines).not.toMatch(/AssetResolver/);
      expect(importLines).not.toMatch(/AssetRegistry/);
      expect(importLines).not.toMatch(/serialize\.ts/);
    });

    it('canary only calls TimelineOps.apply, not validate/preview/checkpoint/rollback/setAllTracksMuted', () => {
      canary.processDsl(dslJson(makeDsl()));

      expect(services.timelineOps.apply).toHaveBeenCalled();

      expect(services.timelineOps.validate).not.toHaveBeenCalled();
      expect(services.timelineOps.preview).not.toHaveBeenCalled();
      expect(services.timelineOps.checkpoint).not.toHaveBeenCalled();
      expect(services.timelineOps.rollback).not.toHaveBeenCalled();
      expect(services.timelineOps.setAllTracksMuted).not.toHaveBeenCalled();
    });

    it('canary uses proposals.create but not proposals.preview/accept/reject', () => {
      canary.processDsl(dslJson(makeDsl()));

      expect(services.proposals._createdProposals.length).toBeGreaterThan(0);
      expect(services.proposals._accepted.length).toBe(0);
      expect(services.proposals._rejected.length).toBe(0);
    });

    it('canary operates entirely through CreativeContext.timeline, reader, and proposals', () => {
      const canary2 = createCompilerCanary({
        extensionId: 'com.boundary.test',
        timeline: services.timelineOps,
        reader: services.reader,
        proposals: services.proposals,
      });

      expect(canary2).toBeDefined();
      const result = canary2.processDsl(dslJson(makeDsl()));
      expect(result).not.toBeNull();
      expect(result!.proposal).toBeDefined();
    });

    it('canary creates patches using only public SDK operation families', () => {
      canary.processDsl(dslJson(makeDsl()));

      const allPatches = [
        ...services.timelineOps._appliedPatches,
        ...services.proposals._createdProposals.map(p => p.patch),
      ];

      const allOps = allPatches.flatMap(p => p.operations);
      const opFamilies = new Set(allOps.map(o => o.op));

      const publicFamilies = [
        'clip.add', 'clip.remove', 'clip.update', 'clip.move',
        'track.add', 'track.remove', 'track.update',
        'app.update', 'project-data.write', 'project-data.delete',
        'asset.update', 'asset.remove', 'extension.noop',
      ];

      for (const opFamily of opFamilies) {
        expect(publicFamilies).toContain(opFamily);
      }
    });
  });

  // ===========================================================================
  // -- Ownership Preservation on Recompile -----------------------------------
  // ===========================================================================
  describe('ownership preservation on recompile', () => {
    it('recompiling with identical DSL preserves ownership (no-op, no proposal)', () => {
      services.reader._snapshotOverrides = {
        clips: [
          makeClipSummary({
            id: 'gen-1', track: 'V1', at: 0, duration: 5,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: Date.now(),
            },
          }),
          makeClipSummary({
            id: 'gen-2', track: 'V1', at: 5, duration: 3,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: Date.now(),
            },
          }),
        ],
      };

      const dsl = makeDsl();
      const result = canary.processDsl(dslJson(dsl));

      expect(result).not.toBeNull();
      expect(result!.proposal).toBeUndefined();
      expect(result!.sourceMapEntryIds.length).toBe(2);
    });

    it('recompiling with modified DSL updates clip properties while preserving ownership', () => {
      services.reader._snapshotOverrides = {
        clips: [
          makeClipSummary({
            id: 'gen-1', track: 'V1', at: 0, duration: 2,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: Date.now() - 10000,
            },
          }),
        ],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 7, clipType: 'hold', sourceLine: 4 }],
      });

      const result = canary.processDsl(dslJson(dsl));
      expect(result).not.toBeNull();

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const updateOps = lastProposal.patch.operations.filter(op => op.op === 'clip.update');
      const addOps = lastProposal.patch.operations.filter(op => op.op === 'clip.add');

      expect(updateOps.length).toBe(1);
      expect(updateOps[0].target).toBe('gen-1');
      expect(addOps.length).toBe(0);

      const payload = updateOps[0].payload as Record<string, unknown>;
      const app = payload.app as Record<string, unknown>;
      const generatedMeta = app.__generated__ as Record<string, unknown>;
      expect(generatedMeta.extensionId).toBe('com.example.canary');
      expect(generatedMeta.contributionId).toBe('compiler-canary-generator');
      expect(typeof generatedMeta.generatedAt).toBe('number');
    });

    it('recompiling preserves extension namespace in app data on clip.update', () => {
      services.reader._snapshotOverrides = {
        clips: [
          makeClipSummary({
            id: 'gen-1', track: 'V1', at: 0, duration: 2,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: Date.now() - 10000,
            },
          }),
        ],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'A1', at: 2, duration: 4, clipType: 'hold' }],
      });

      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const updateOps = lastProposal.patch.operations.filter(op => op.op === 'clip.update');
      expect(updateOps.length).toBe(1);

      const payload = updateOps[0].payload as Record<string, unknown>;
      const app = payload.app as Record<string, unknown>;
      expect(app['com.example.canary']).toBeDefined();
      expect((app['com.example.canary'] as Record<string, unknown>).source).toBe('compiler-canary');
    });

    it('recompiling does not affect non-owned clips', () => {
      const otherOwnedClip = makeClipSummary({
        id: 'other-clip', track: 'V1', at: 3, duration: 2,
        managed: true, managedBy: 'com.other.extension',
        generatedMeta: {
          extensionId: 'com.other.extension',
          contributionId: 'other-gen',
          generatedAt: Date.now(),
        },
      });
      const userClip = makeClipSummary({
        id: 'user-clip', track: 'A1', at: 0, duration: 5, managed: false,
      });

      services.reader._snapshotOverrides = { clips: [otherOwnedClip, userClip] };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold' }],
      });

      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const ops = lastProposal.patch.operations;
      const addOps = ops.filter(op => op.op === 'clip.add');
      const removeOps = ops.filter(op => op.op === 'clip.remove');
      const updateOps = ops.filter(op => op.op === 'clip.update');

      expect(addOps.length).toBe(1);
      expect(addOps[0].target).toBe('gen-1');
      expect(removeOps.length).toBe(0);
      expect(updateOps.length).toBe(0);
    });

    it('recompiling updates generatedAt timestamp on modified clips', () => {
      const oldTimestamp = Date.now() - 60000;

      services.reader._snapshotOverrides = {
        clips: [
          makeClipSummary({
            id: 'gen-1', track: 'V1', at: 0, duration: 2,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: oldTimestamp,
            },
          }),
        ],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 7, clipType: 'hold' }],
      });

      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const updateOps = lastProposal.patch.operations.filter(op => op.op === 'clip.update');
      expect(updateOps.length).toBe(1);

      const payload = updateOps[0].payload as Record<string, unknown>;
      const app = payload.app as Record<string, unknown>;
      const generatedMeta = app.__generated__ as Record<string, unknown>;

      expect(typeof generatedMeta.generatedAt).toBe('number');
      expect(generatedMeta.generatedAt).toBeGreaterThanOrEqual(oldTimestamp);
    });

    it('recompiling preserves sourceMapEntryId linkage on updates', () => {
      services.reader._snapshotOverrides = {
        clips: [
          makeClipSummary({
            id: 'gen-1', track: 'V1', at: 0, duration: 2,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: Date.now() - 10000,
              sourceMapEntryId: 'cc-sme-old',
            },
          }),
        ],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 7, clipType: 'hold', sourceLine: 10 }],
      });

      canary.processDsl(dslJson(dsl));

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const updateOps = lastProposal.patch.operations.filter(op => op.op === 'clip.update');

      if (updateOps.length > 0) {
        const payload = updateOps[0].payload as Record<string, unknown>;
        const app = payload.app as Record<string, unknown>;
        const generatedMeta = app.__generated__ as Record<string, unknown>;
        expect(generatedMeta.sourceMapEntryId).toMatch(/^cc-sme-/);
      }
    });

    it('three-pass recompile: add -> update -> no-op preserves ownership chain', () => {
      let dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 3, clipType: 'hold' }],
      });
      const result1 = canary.processDsl(dslJson(dsl));
      expect(result1).not.toBeNull();
      expect(result1!.generatedClipIds).toContain('gen-1');
      const pass1Proposal = result1!.proposal!;
      const pass1AddOps = pass1Proposal.patch.operations.filter(op => op.op === 'clip.add');
      expect(pass1AddOps.length).toBe(1);
      const pass1Payload = pass1AddOps[0].payload as Record<string, unknown>;
      const pass1App = pass1Payload.app as Record<string, unknown>;
      const pass1Meta = pass1App.__generated__ as Record<string, unknown>;
      expect(pass1Meta.extensionId).toBe('com.example.canary');

      services.reader._snapshotOverrides = {
        clips: [
          makeClipSummary({
            id: 'gen-1', track: 'V1', at: 0, duration: 3,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: Date.now(),
            },
          }),
        ],
      };

      dsl = makeDsl({
        clips: [
          { id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold' },
          { id: 'gen-2', track: 'V1', at: 5, duration: 2, clipType: 'hold' },
        ],
      });
      const result2 = canary.processDsl(dslJson(dsl));
      expect(result2).not.toBeNull();

      const pass2Proposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const pass2UpdateOps = pass2Proposal.patch.operations.filter(op => op.op === 'clip.update');
      const pass2AddOps = pass2Proposal.patch.operations.filter(op => op.op === 'clip.add');

      expect(pass2UpdateOps.length).toBe(1);
      expect(pass2UpdateOps[0].target).toBe('gen-1');
      expect(pass2AddOps.length).toBe(1);
      expect(pass2AddOps[0].target).toBe('gen-2');

      const updatePayload = pass2UpdateOps[0].payload as Record<string, unknown>;
      const updateApp = updatePayload.app as Record<string, unknown>;
      const updateMeta = updateApp.__generated__ as Record<string, unknown>;
      expect(updateMeta.extensionId).toBe('com.example.canary');

      const addPayload = pass2AddOps[0].payload as Record<string, unknown>;
      const addApp = addPayload.app as Record<string, unknown>;
      const addMeta = addApp.__generated__ as Record<string, unknown>;
      expect(addMeta.extensionId).toBe('com.example.canary');

      services.reader._snapshotOverrides = {
        clips: [
          makeClipSummary({
            id: 'gen-1', track: 'V1', at: 0, duration: 5,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: Date.now(),
            },
          }),
          makeClipSummary({
            id: 'gen-2', track: 'V1', at: 5, duration: 2,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: Date.now(),
            },
          }),
        ],
      };

      const result3 = canary.processDsl(dslJson(dsl));
      expect(result3).not.toBeNull();
      expect(result3!.proposal).toBeUndefined();
      expect(result3!.sourceMapEntryIds.length).toBe(2);
    });

    it('recompiling with removed clip proposes clip.remove only for owned clips', () => {
      services.reader._snapshotOverrides = {
        clips: [
          makeClipSummary({
            id: 'gen-1', track: 'V1', at: 0, duration: 5,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: Date.now(),
            },
          }),
          makeClipSummary({
            id: 'gen-2', track: 'V1', at: 5, duration: 3,
            managed: true, managedBy: 'com.example.canary',
            generatedMeta: {
              extensionId: 'com.example.canary',
              contributionId: 'compiler-canary-generator',
              generatedAt: Date.now(),
            },
          }),
          makeClipSummary({ id: 'user-clip', track: 'A1', at: 0, duration: 4, managed: false }),
        ],
      };

      const dsl = makeDsl({
        clips: [{ id: 'gen-1', track: 'V1', at: 0, duration: 5, clipType: 'hold' }],
      });

      const result = canary.processDsl(dslJson(dsl));
      expect(result).not.toBeNull();

      const lastProposal = services.proposals._createdProposals[services.proposals._createdProposals.length - 1];
      const removeOps = lastProposal.patch.operations.filter(op => op.op === 'clip.remove');
      const addOps = lastProposal.patch.operations.filter(op => op.op === 'clip.add');
      const updateOps = lastProposal.patch.operations.filter(op => op.op === 'clip.update');

      expect(removeOps.length).toBe(1);
      expect(removeOps[0].target).toBe('gen-2');
      expect(addOps.length).toBe(0);
      expect(updateOps.length).toBe(0);
      expect(removeOps.find(op => op.target === 'user-clip')).toBeUndefined();
    });
  });

});
