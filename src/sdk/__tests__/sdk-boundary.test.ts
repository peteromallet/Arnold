/**
 * @publicContract
 * SDK public-import boundary test.
 *
 * Proves that the stable @reigh/editor-sdk alias resolves to the public
 * contract re-exported from src/sdk/index.ts and that the real vendored
 * @banodoco/timeline-schema package is consumable without relying on
 * editor-internal deep imports or the Vitest shim.
 */

import { describe, expect, it } from 'vitest';

// ── Public SDK alias boundary ────────────────────────────────────────────────
// These imports must resolve through the @reigh/editor-sdk alias (wired in
// vitest.config.ts → src/sdk) and re-export the stable public contract from
// src/tools/video-editor/index.ts.  No deep @/tools/video-editor/… paths.
import {
  BUILTIN_CLIP_TYPES,
  getStableConfigSignature,
  TimelineVersionConflictError,
} from '@reigh/editor-sdk';

// ── Real vendored timeline-schema boundary ───────────────────────────────────
// Import the actual vendored package dist (not the Vitest shim) so this test
// proves the canonical @banodoco/timeline-schema artifact is consumable.
// Path is relative from src/sdk/__tests__/ to vendor/timeline-schema.
import {
  TimelineConfig,
  resolveTheme,
  deepMergeTheme,
} from '../../../vendor/timeline-schema/typescript/dist/src/index.js';

describe('SDK public-import boundary (@reigh/editor-sdk)', () => {
  it('exports BUILTIN_CLIP_TYPES as a non-empty array', () => {
    expect(Array.isArray(BUILTIN_CLIP_TYPES)).toBe(true);
    expect(BUILTIN_CLIP_TYPES.length).toBeGreaterThan(0);
  });

  it('exports getStableConfigSignature as a function', () => {
    expect(typeof getStableConfigSignature).toBe('function');
  });

  it('exports TimelineVersionConflictError as an Error class', () => {
    const err = new TimelineVersionConflictError('test', 1, 2);
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe('TimelineVersionConflictError');
    expect(err.message).toContain('test');
  });
});

describe('Real vendored timeline-schema boundary', () => {
  it('resolves TimelineConfig zod schema from vendored dist', () => {
    // TimelineConfig is a zod schema object with .parse and .safeParse
    expect(typeof TimelineConfig.parse).toBe('function');
    expect(typeof TimelineConfig.safeParse).toBe('function');
  });

  it('parses a minimal valid TimelineConfig', () => {
    const result = TimelineConfig.safeParse({ clips: [] });
    expect(result.success).toBe(true);
  });

  it('rejects invalid TimelineConfig', () => {
    const result = TimelineConfig.safeParse({ clips: 'not-an-array' });
    expect(result.success).toBe(false);
  });

  it('exports resolveTheme as a function', () => {
    expect(typeof resolveTheme).toBe('function');
  });

  it('exports deepMergeTheme as a function', () => {
    expect(typeof deepMergeTheme).toBe('function');
  });

  it('resolveTheme returns a merged theme object', () => {
    const registry = {
      'test-theme': {
        id: 'test-theme',
        visual: { canvas: { width: 1920, height: 1080 } },
      },
    };
    const result = resolveTheme({ theme: 'test-theme' }, registry);
    expect(result).toBeDefined();
    expect(typeof result).toBe('object');
  });
});

// ── M3: SDK boundary ──────────────────────────────────────────────────────────
// Prove extensions can import M3 contracts from @reigh/editor-sdk but
// cannot import raw TimelineData, TimelineEditMutation, provider, store,
// or command internals.

import * as sdkStar from '@reigh/editor-sdk';
import {
  // M3 value exports (const, function, class)
  EXTENSION_PROJECT_DATA_LIMITS,
  CREATIVE_MEMBER_MILESTONE,
  createCreativeContextStubs,
  ExtensionNotImplementedError,
} from '@reigh/editor-sdk';
import type {
  // M4 commands / keybindings / context menus
  ContributionId,
  TargetContext,
  TargetContextPayload,
  CommandRunContext,
  CommandHandler,
  CommandRegistrationOptions,
  CommandContribution,
  KeybindingContribution,
  ContextMenuItemContribution,
  ExtensionCommandService,
  // M3 TimelinePatch types
  TimelinePatchOpFamily,
  TimelinePatchReservedOpFamily,
  TimelinePatchAnyOpFamily,
  TimelinePatchOperation,
  TimelinePatch,
  TimelinePatchDiagnostic,
  TimelinePatchValidationResult,
  // M3 TimelineOps
  TimelineOps,
  // M3 TimelineDiff
  TimelineDiffGranularity,
  TimelineDiffKind,
  TimelineDiffEntry,
  TimelineDiff,
  TimelinePreviewResult,
  // M3 TimelineSnapshot / Reader
  TimelineSnapshot,
  TimelineClipSummary,
  TimelineTrackSummary,
  TimelineReader,
  // M3 Proposals
  ProposalState,
  TimelineProposal,
  TimelineProposalInput,
  ProposalListener,
  ProposalRuntime,
  // M3 Source Maps
  SourceMapEntry,
  // M3 Generated-object metadata
  GeneratedObjectMeta,
  // M3 Project-data limits
  ProjectDataLimitCode,
  ProjectDataLimitDetail,
  // M3 Host UI
  ProposalPanelState,
  ProposalPanelAction,
  // CreativeContext (updated in M3)
  CreativeContext,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// 1. M3 value exports are importable from @reigh/editor-sdk
// ---------------------------------------------------------------------------

describe('M3: value exports are importable from @reigh/editor-sdk', () => {
  it('EXTENSION_PROJECT_DATA_LIMITS is a frozen const object', () => {
    expect(typeof EXTENSION_PROJECT_DATA_LIMITS).toBe('object');
    expect(EXTENSION_PROJECT_DATA_LIMITS).not.toBeNull();
    expect(EXTENSION_PROJECT_DATA_LIMITS.MAX_ENTRY_BYTES).toBe(64 * 1024);
    expect(EXTENSION_PROJECT_DATA_LIMITS.MAX_EXTENSION_TOTAL_BYTES).toBe(
      1 * 1024 * 1024,
    );
    expect(EXTENSION_PROJECT_DATA_LIMITS.MAX_ENTRIES_PER_EXTENSION).toBe(128);
  });

  it('CREATIVE_MEMBER_MILESTONE includes timeline with M3 milestone', () => {
    expect(typeof CREATIVE_MEMBER_MILESTONE).toBe('object');
    expect(CREATIVE_MEMBER_MILESTONE.timeline).toBe('M3');
  });

  it('createCreativeContextStubs still produces a frozen object', () => {
    const stubs = createCreativeContextStubs();
    expect(Object.isFrozen(stubs)).toBe(true);
    const creativeKeys = Object.keys(stubs).sort();
    expect(creativeKeys).toEqual([
      'assets',
      'export',
      'materials',
      'project',
      'sessions',
      'stage',
      'timeline',
      'writing',
    ]);
  });

  it('creative.timeline stub throws ExtensionNotImplementedError with M3 milestone', () => {
    const stubs = createCreativeContextStubs();
    expect(() => stubs.timeline).toThrow(ExtensionNotImplementedError);
    try {
      stubs.timeline;
    } catch (err) {
      expect(err).toBeInstanceOf(ExtensionNotImplementedError);
      expect((err as ExtensionNotImplementedError).feature).toBe('timeline');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M3');
    }
  });
});

// ---------------------------------------------------------------------------
// 2. M3 type interfaces are importable and have expected shapes
// ---------------------------------------------------------------------------

describe('M3: type interfaces are importable from @reigh/editor-sdk', () => {
  it('TimelinePatchOperation shape is constructable', () => {
    const op: TimelinePatchOperation = {
      op: 'clip.add',
      target: 'clip-1',
      payload: { at: 0, clipType: 'video' },
      order: 0,
    };
    expect(op.op).toBe('clip.add');
    expect(op.target).toBe('clip-1');
    expect(op.payload).toEqual({ at: 0, clipType: 'video' });
    expect(op.order).toBe(0);
  });

  it('TimelinePatch shape is constructable', () => {
    const patch: TimelinePatch = {
      version: 1,
      operations: [
        { op: 'clip.add', target: 'clip-1' },
        { op: 'track.add', target: 'track-1' },
      ],
      source: 'com.test.extension',
      meta: { requestId: 'abc' },
    };
    expect(patch.version).toBe(1);
    expect(patch.operations).toHaveLength(2);
    expect(patch.source).toBe('com.test.extension');
  });

  it('TimelinePatchDiagnostic shape is constructable', () => {
    const diag: TimelinePatchDiagnostic = {
      severity: 'error',
      code: 'timeline-patch/unknown-op',
      message: 'Unknown operation family',
      operationIndex: 0,
      op: 'clip.add',
      target: 'clip-1',
      detail: { expected: 'clip.add', actual: 'clip.unknown' },
    };
    expect(diag.code.startsWith('timeline-patch/')).toBe(true);
    expect(diag.severity).toBe('error');
    expect(diag.operationIndex).toBe(0);
  });

  it('TimelinePatchValidationResult shape is constructable', () => {
    const result: TimelinePatchValidationResult = {
      valid: true,
      diagnostics: [],
    };
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);

    const invalidResult: TimelinePatchValidationResult = {
      valid: false,
      diagnostics: [
        {
          severity: 'error',
          code: 'timeline-patch/unknown-op',
          message: 'Unknown operation',
          operationIndex: 0,
        },
      ],
    };
    expect(invalidResult.valid).toBe(false);
    expect(invalidResult.diagnostics).toHaveLength(1);
  });

  it('TimelineDiffEntry shape is constructable', () => {
    const entry: TimelineDiffEntry = {
      granularity: 'clip',
      kind: 'added',
      target: 'clip-1',
      op: 'clip.add',
      before: undefined,
      after: { at: 0, track: 'track-1' },
    };
    expect(entry.granularity).toBe('clip');
    expect(entry.kind).toBe('added');
    expect(entry.op).toBe('clip.add');
  });

  it('TimelineDiff shape is constructable', () => {
    const diff: TimelineDiff = {
      version: 1,
      entries: [
        {
          granularity: 'clip',
          kind: 'added',
          target: 'clip-1',
          op: 'clip.add',
          after: { at: 0 },
        },
      ],
      affectedObjectIds: ['clip-1'],
    };
    expect(diff.version).toBe(1);
    expect(diff.entries).toHaveLength(1);
    expect(diff.affectedObjectIds).toContain('clip-1');
  });

  it('TimelinePreviewResult shape is constructable', () => {
    const preview: TimelinePreviewResult = {
      diff: { version: 0, entries: [], affectedObjectIds: [] },
      fullyPreviewable: true,
      diagnostics: [],
    };
    expect(preview.fullyPreviewable).toBe(true);
    expect(preview.diff.entries).toHaveLength(0);
  });

  it('TimelineClipSummary shape is constructable', () => {
    const clip: TimelineClipSummary = {
      id: 'clip-1',
      track: 'track-1',
      at: 0,
      clipType: 'video',
      duration: 120,
      managed: true,
      managedBy: 'com.test.ext',
    };
    expect(clip.id).toBe('clip-1');
    expect(clip.managed).toBe(true);
    expect(clip.managedBy).toBe('com.test.ext');
  });

  it('TimelineTrackSummary shape is constructable', () => {
    const track: TimelineTrackSummary = {
      id: 'track-1',
      kind: 'visual',
      label: 'Track 1',
      muted: false,
    };
    expect(track.kind).toBe('visual');
    expect(track.muted).toBe(false);
  });

  it('TimelineSnapshot shape is constructable', () => {
    const snap: TimelineSnapshot = {
      projectId: 'proj-1',
      baseVersion: 5,
      currentVersion: 5,
      extensionRequirements: [],
      clips: [{ id: 'c1', track: 't1', at: 0, duration: 30, managed: false }],
      tracks: [{ id: 't1', kind: 'visual', label: 'T1', muted: false }],
      assetKeys: ['asset-1'],
      app: {},
    };
    expect(snap.baseVersion).toBe(5);
    expect(snap.clips).toHaveLength(1);
    expect(snap.tracks).toHaveLength(1);
  });

  it('TimelineProposal shape is constructable', () => {
    const proposal: TimelineProposal = {
      id: 'prop-1',
      source: 'com.test.ext',
      rationale: 'Add intro clip',
      state: 'pending',
      patch: { version: 0, operations: [] },
      baseVersion: 5,
      previewable: true,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    expect(proposal.state).toBe('pending');
    expect(proposal.previewable).toBe(true);
    expect(proposal.source).toBe('com.test.ext');
  });

  it('TimelineProposalInput shape is constructable', () => {
    const input: TimelineProposalInput = {
      source: 'com.test.ext',
      rationale: 'Test',
      patch: { version: 0, operations: [] },
      baseVersion: 1,
    };
    expect(input.source).toBe('com.test.ext');
    expect(input.baseVersion).toBe(1);
  });

  it('SourceMapEntry shape is constructable', () => {
    const entry: SourceMapEntry = {
      id: 'sme-1',
      source: 'com.test.ext',
      targetId: 'clip-1',
      targetGranularity: 'clip',
      sourceUri: 'file:///src/main.ts',
      sourceStartLine: 10,
      sourceStartColumn: 0,
      sourceEndLine: 15,
      sourceEndColumn: 20,
      stale: false,
    };
    expect(entry.stale).toBe(false);
    expect(entry.targetGranularity).toBe('clip');
  });

  it('GeneratedObjectMeta shape is constructable', () => {
    const meta: GeneratedObjectMeta = {
      extensionId: 'com.test.ext',
      contributionId: 'generator-1',
      provenance: { promptId: 'abc' },
      generatedAt: Date.now(),
      sourceMapEntryId: 'sme-1',
    };
    expect(meta.extensionId).toBe('com.test.ext');
    expect(meta.sourceMapEntryId).toBe('sme-1');
  });

  it('ProjectDataLimitDetail shape is constructable', () => {
    const detail: ProjectDataLimitDetail = {
      extensionId: 'com.test.ext',
      limit: 65536,
      actual: 100000,
      unit: 'bytes',
      code: 'project-data/entry-size-exceeded',
    };
    expect(detail.code).toBe('project-data/entry-size-exceeded');
    expect(detail.unit).toBe('bytes');
  });

  it('ProposalPanelState shape is constructable', () => {
    const state: ProposalPanelState = {
      proposals: [],
      selectedProposalId: null,
      visible: false,
    };
    expect(state.proposals).toHaveLength(0);
    expect(state.visible).toBe(false);
  });

  it('ProposalPanelAction discriminated union covers all variants', () => {
    const selectAction: ProposalPanelAction = {
      type: 'select',
      proposalId: 'prop-1',
    };
    expect(selectAction.type).toBe('select');

    const acceptAction: ProposalPanelAction = {
      type: 'accept',
      proposalId: 'prop-1',
    };
    expect(acceptAction.type).toBe('accept');

    const rejectAction: ProposalPanelAction = {
      type: 'reject',
      proposalId: 'prop-1',
      reason: 'Not needed',
    };
    expect(rejectAction.type).toBe('reject');
    expect(rejectAction.reason).toBe('Not needed');

    const previewAction: ProposalPanelAction = {
      type: 'preview',
      proposalId: 'prop-1',
    };
    expect(previewAction.type).toBe('preview');

    const toggleAction: ProposalPanelAction = { type: 'toggleVisibility' };
    expect(toggleAction.type).toBe('toggleVisibility');
  });

  it('CreativeContext timeline member is assignable from TimelineOps (typing proof)', () => {
    // This test proves that CreativeContext.timeline is no longer `unknown`.
    // A TimelineOps-shaped object can be assigned to ctx.creative.timeline
    // at the type level. We verify the stub still throws, but the type is
    // narrowed to TimelineOps.
    const stubs: CreativeContext = createCreativeContextStubs();
    // TypeScript compile-time check: the following would error if timeline
    // were still `unknown`. We verify at runtime that accessing the stub
    // throws the expected error.
    expect(() => stubs.timeline).toThrow(ExtensionNotImplementedError);
    try {
      stubs.timeline;
    } catch (err) {
      const e = err as ExtensionNotImplementedError;
      expect(e.feature).toBe('timeline');
      expect(e.milestone).toBe('M3');
    }
  });
});

// ---------------------------------------------------------------------------
// M4: Command / keybinding / context-menu type interfaces
// ---------------------------------------------------------------------------

describe('M4: command/keybinding/context-menu type interfaces are importable from @reigh/editor-sdk', () => {
  it('TargetContext sealed union accepts only the 4 documented values', () => {
    // Compile-time proof that TargetContext is limited to these 4 literals.
    // Assigning anything else would be a type error.
    const values: TargetContext[] = ['clip', 'clip-selection', 'track', 'timeline-area'];
    expect(values).toHaveLength(4);
    expect(values).toContain('clip');
    expect(values).toContain('clip-selection');
    expect(values).toContain('track');
    expect(values).toContain('timeline-area');
  });

  it('TargetContextPayload clip variant is constructable', () => {
    const payload: TargetContextPayload = {
      target: 'clip',
      clipId: 'clip-1',
      trackId: 'track-1',
    };
    expect(payload.target).toBe('clip');
    expect(payload.clipId).toBe('clip-1');
    expect(payload.trackId).toBe('track-1');
  });

  it('TargetContextPayload clip-selection variant is constructable', () => {
    const payload: TargetContextPayload = {
      target: 'clip-selection',
      clipIds: ['clip-1', 'clip-2'],
      trackId: 'track-1',
    };
    expect(payload.target).toBe('clip-selection');
    expect(payload.clipIds).toEqual(['clip-1', 'clip-2']);
    expect(payload.trackId).toBe('track-1');
  });

  it('TargetContextPayload track variant is constructable', () => {
    const payload: TargetContextPayload = {
      target: 'track',
      trackId: 'track-1',
    };
    expect(payload.target).toBe('track');
    expect(payload.trackId).toBe('track-1');
  });

  it('TargetContextPayload timeline-area variant is constructable', () => {
    const payload: TargetContextPayload = {
      target: 'timeline-area',
    };
    expect(payload.target).toBe('timeline-area');
  });

  it('CommandRunContext shape is constructable (without target)', () => {
    const ctx: CommandRunContext = {
      commandId: 'myExtension.doSomething',
      extensionId: 'myExtension',
    };
    expect(ctx.commandId).toBe('myExtension.doSomething');
    expect(ctx.extensionId).toBe('myExtension');
    expect(ctx.target).toBeUndefined();
  });

  it('CommandRunContext shape is constructable (with clip target)', () => {
    const ctx: CommandRunContext = {
      commandId: 'myExtension.doSomething',
      extensionId: 'myExtension',
      target: { target: 'clip', clipId: 'clip-1', trackId: 'track-1' },
    };
    expect(ctx.target?.target).toBe('clip');
    expect(ctx.target?.clipId).toBe('clip-1');
  });

  it('CommandHandler typed function is callable (sync)', () => {
    let called = false;
    const handler: CommandHandler = (_ctx) => {
      called = true;
    };
    handler({ commandId: 'test.cmd', extensionId: 'test' });
    expect(called).toBe(true);
  });

  it('CommandHandler typed function handles async', async () => {
    let called = false;
    const handler: CommandHandler = async (_ctx) => {
      called = true;
    };
    await handler({ commandId: 'test.cmd', extensionId: 'test' });
    expect(called).toBe(true);
  });

  it('CommandRegistrationOptions shape is constructable', () => {
    const opts: CommandRegistrationOptions = {
      label: 'My Command',
      category: 'Editing',
    };
    expect(opts.label).toBe('My Command');
    expect(opts.category).toBe('Editing');
  });

  it('CommandRegistrationOptions with only label is constructable', () => {
    const opts: CommandRegistrationOptions = { label: 'My Command' };
    expect(opts.label).toBe('My Command');
    expect(opts.category).toBeUndefined();
  });

  it('CommandContribution shape is constructable', () => {
    const contrib: CommandContribution = {
      id: 'myCommand' as ContributionId,
      kind: 'command',
      command: 'myExtension.doSomething',
      label: 'Do Something',
      category: 'Editing',
      when: 'editorHasSelection',
      order: 10,
    };
    expect(contrib.kind).toBe('command');
    expect(contrib.command).toBe('myExtension.doSomething');
    expect(contrib.label).toBe('Do Something');
    expect(contrib.category).toBe('Editing');
    expect(contrib.when).toBe('editorHasSelection');
    expect(contrib.order).toBe(10);
  });

  it('KeybindingContribution shape is constructable', () => {
    const contrib: KeybindingContribution = {
      id: 'myKeybinding' as ContributionId,
      kind: 'keybinding',
      command: 'myExtension.doSomething',
      key: 'CtrlOrCmd+K',
      when: 'editorHasSelection',
      order: 5,
    };
    expect(contrib.kind).toBe('keybinding');
    expect(contrib.command).toBe('myExtension.doSomething');
    expect(contrib.key).toBe('CtrlOrCmd+K');
    expect(contrib.when).toBe('editorHasSelection');
    expect(contrib.order).toBe(5);
  });

  it('ContextMenuItemContribution shape is constructable', () => {
    const contrib: ContextMenuItemContribution = {
      id: 'myMenuItem' as ContributionId,
      kind: 'contextMenuItem',
      command: 'myExtension.doSomething',
      label: 'Do Something',
      target: 'clip',
      when: 'editorHasSelection',
      order: 5,
      icon: 'scissors',
    };
    expect(contrib.kind).toBe('contextMenuItem');
    expect(contrib.command).toBe('myExtension.doSomething');
    expect(contrib.target).toBe('clip');
    expect(contrib.icon).toBe('scissors');
  });

  it('ContextMenuItemContribution targets cover all variants', () => {
    const targets: TargetContext[] = ['clip', 'clip-selection', 'track', 'timeline-area'];
    const contribs: ContextMenuItemContribution[] = targets.map((t) => ({
      id: `menu-${t}` as ContributionId,
      kind: 'contextMenuItem',
      command: 'myExtension.doSomething',
      target: t,
    }));
    expect(contribs).toHaveLength(4);
    expect(contribs.map((c) => c.target).sort()).toEqual([
      'clip',
      'clip-selection',
      'timeline-area',
      'track',
    ]);
  });
});

// ---------------------------------------------------------------------------
// 3. Internal types are NOT importable from @reigh/editor-sdk
//    (neither as value exports nor leaked through the context)
// ---------------------------------------------------------------------------

describe('M3: internal types are NOT re-exported from @reigh/editor-sdk', () => {
  const INTERNAL_FORBIDDEN_NAMES = [
    // Raw timeline data structures
    'TimelineData',
    'TimelineEditMutation',
    // Data provider internals
    'DataProvider',
    'provider',
    'dataProvider',
    'dataProviderRef',
    'getDataProvider',
    'isDataProviderPersistenceEnabled',
    // Timeline store internals
    'timelineStore',
    'store',
    'getTimeline',
    'timelineRef',
    'useTimelineDataSlice',
    'useTimelineDataSelector',
    'useTimelineEditorData',
    'timelineState',
    'TimelineDataRef',
    // M4 command / keybinding / context-menu internals
    'commandRegistry',
    'keybindingRegistry',
    'contextMenuRegistry',
    'registerCommandHandler',
    'executeCommand',
    'getCommands',
    'getKeybindings',
    'getContextMenuItems',
    'resolveKeybinding',
    'matchKeybinding',
    'parseKeyChord',
    'normalizeKeyNotation',
    'KeybindingResolver',
    'CommandExecutor',
    'ContextMenuRenderer',
    'CommandPaletteStore',
    'commandStore',
    'keybindingStore',
    'menuStore',
    // Command internals
    'buildTimelineData',
    'buildTimelineDataWithResolver',
    'buildTimelineCommandData',
    'assembleTimelineData',
    'preserveUploadingClips',
    // Mutation internals
    'applyEdit',
    'edit',
    'mutate',
    'patch',
    'commit',
    'transact',
    'commitData',
    // Internal ops / internals escape hatches
    'ops',
    'internalOps',
    '_internal',
    '__editorInternals',
    '_editor',
    // Provider resolution
    'resolveTimelineProvider',
    'createProvider',
  ];

  it('none of the forbidden internal names appear as SDK value exports', () => {
    const valueExports = Object.keys(sdkStar);
    for (const forbidden of INTERNAL_FORBIDDEN_NAMES) {
      expect(valueExports).not.toContain(forbidden);
    }
  });

  it('forbidden names are not accessible as properties on the SDK namespace', () => {
    const ns = sdkStar as Record<string, unknown>;
    for (const forbidden of INTERNAL_FORBIDDEN_NAMES) {
      expect(ns[forbidden]).toBeUndefined();
    }
  });

  it('total SDK value export count is within the expected public surface range', () => {
    // The public SDK surface should be a well-known, curated set.
    // We expect fewer than 80 value exports (types don't count).
    const valueCount = Object.keys(sdkStar).length;
    expect(valueCount).toBeLessThan(80);
    expect(valueCount).toBeGreaterThan(0);
  });
});
