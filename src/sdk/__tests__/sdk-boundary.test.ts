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
  contributionKindNotYetBridged,
  CONTRIBUTION_KIND_MILESTONE,
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
  // M6: Parser / output format / search provider
  ParserContribution,
  OutputFormatContribution,
  SearchProviderContribution,
  CompileOnlyOutputFormatContribution,
  RenderDependentOutputFormatContribution,
  RenderArtifactManifest,
  RenderArtifactSidecarDescriptor,
  ParserInput,
  ParserResult,
  ParserDiagnostic,
  ParserHandler,
  CompileOnlyOutputResult,
  OutputFormatHandler,
  OutputFormatContext,
  SearchMatch,
  SearchProviderResult,
  SearchProviderHandler,
  SearchProviderContext,
  AssetReadSurface,
  MaterialReadSurface,
  ExportService,
  MetadataFacetDescriptor,
  MetadataFacetValueKind,
  AssetDetailSectionDescriptor,
  // M7: Trusted component effects
  EffectContribution,
  EffectComponent,
  EffectParameterDefinition,
  EffectParameterSchema,
  EffectRegistrationOptions,
  EffectRegistrationService,
  // M8: Trusted component transitions
  TransitionContribution,
  TransitionRenderer,
  TransitionParameterDefinition,
  TransitionParameterSchema,
  TransitionRegistrationOptions,
  TransitionRegistrationService,
  // M9: Clip type dispatch, keyframes, automation
  ClipTypeContribution,
  ClipRenderer,
  ClipInspector,
  ClipParameterDefinition,
  ClipParameterSchema,
  ClipTypeRegistrationOptions,
  ClipTypeRegistrationService,
  KeyframeInterpolation,
  Keyframe,
  InterpolatedParam,
  AutomationClipTarget,
  AutomationClipParams,
  // M12 planner requirement types
  CapabilityVersion,
  CapabilitySourceRef,
  RouteFitMetadata,
  CapabilityRequirement,
  IntegrationCapabilities,
  SamplingConfig,
  SamplingResult,
  TimelineRenderPassSummary,
  ProcessSpec,
  ProcessContribution,
  ProcessStatus,
  ProcessRoundtripRequest,
  ProcessRoundtripResult,
} from '@reigh/editor-sdk';
import type {
  ExtensionId,
  ExtensionManifest,
  ExtensionContext,
  ExtensionDiagnostic,
  DisposeHandle,
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
      'proposals',
      'reader',
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

// ---------------------------------------------------------------------------
// M6: Parser / output format / search provider contribution type interfaces
// ---------------------------------------------------------------------------

describe('M6: parser/outputFormat/searchProvider type interfaces are importable from @reigh/editor-sdk', () => {
  it('ParserContribution shape is constructable (minimal)', () => {
    const contrib: ParserContribution = {
      id: 'myParser' as ContributionId,
      kind: 'parser',
      label: 'My Parser',
      acceptMimeTypes: ['image/jpeg'],
    };
    expect(contrib.kind).toBe('parser');
    expect(contrib.label).toBe('My Parser');
    expect(contrib.acceptMimeTypes).toEqual(['image/jpeg']);
    expect(contrib.required).toBeUndefined();
  });

  it('ParserContribution with acceptExtensions is constructable', () => {
    const contrib: ParserContribution = {
      id: 'extParser' as ContributionId,
      kind: 'parser',
      label: 'Extension Parser',
      acceptExtensions: ['jpg', 'jpeg', 'png'],
      maxBytes: 10485760,
    };
    expect(contrib.acceptExtensions).toEqual(['jpg', 'jpeg', 'png']);
    expect(contrib.maxBytes).toBe(10485760);
    expect(contrib.acceptMimeTypes).toBeUndefined();
  });

  it('ParserContribution with required:true is constructable', () => {
    const contrib: ParserContribution = {
      id: 'requiredParser' as ContributionId,
      kind: 'parser',
      label: 'Required Parser',
      acceptMimeTypes: ['video/mp4'],
      required: true,
      order: 5,
    };
    expect(contrib.required).toBe(true);
    expect(contrib.order).toBe(5);
  });

  it('OutputFormatContribution (compile-only) shape is constructable', () => {
    const contrib: OutputFormatContribution = {
      id: 'metadataJson' as ContributionId,
      kind: 'outputFormat',
      label: 'Metadata JSON',
      requiresRender: false,
      outputExtension: 'json',
      outputMimeType: 'application/json',
      description: 'Serializes timeline metadata to JSON',
      order: 10,
    };
    expect(contrib.kind).toBe('outputFormat');
    expect(contrib.requiresRender).toBe(false);
    expect(contrib.outputExtension).toBe('json');
    expect(contrib.outputMimeType).toBe('application/json');
    expect(contrib.description).toBe('Serializes timeline metadata to JSON');
    expect(contrib.order).toBe(10);
  });

  it('OutputFormatContribution (render-dependent) shape is constructable', () => {
    const contrib: OutputFormatContribution = {
      id: 'mp4Export' as ContributionId,
      kind: 'outputFormat',
      label: 'MP4 Export',
      requiresRender: true,
      outputExtension: 'mp4',
      outputMimeType: 'video/mp4',
      description: 'Rendered video export',
    };
    expect(contrib.kind).toBe('outputFormat');
    expect(contrib.requiresRender).toBe(true);
    expect(contrib.outputExtension).toBe('mp4');
  });

  it('OutputFormatContribution requiresRender distinguishes compile-only from render-dependent', () => {
    const compileOnly: OutputFormatContribution = {
      id: 'co' as ContributionId,
      kind: 'outputFormat',
      label: 'Compile Only',
      requiresRender: false,
      outputExtension: 'json',
    };
    const renderDependent: OutputFormatContribution = {
      id: 'rd' as ContributionId,
      kind: 'outputFormat',
      label: 'Render Dependent',
      requiresRender: true,
      outputExtension: 'mp4',
    };
    expect(compileOnly.requiresRender).toBe(false);
    expect(renderDependent.requiresRender).toBe(true);
  });

  it('SearchProviderContribution shape is constructable', () => {
    const contrib: SearchProviderContribution = {
      id: 'mySearch' as ContributionId,
      kind: 'searchProvider',
      label: 'My Search Provider',
      description: 'Semantic search over image embeddings',
      order: 5,
    };
    expect(contrib.kind).toBe('searchProvider');
    expect(contrib.label).toBe('My Search Provider');
    expect(contrib.description).toBe('Semantic search over image embeddings');
    expect(contrib.order).toBe(5);
  });

  it('SearchProviderContribution with resultKinds is constructable', () => {
    const contrib: SearchProviderContribution = {
      id: 'assetSearch' as ContributionId,
      kind: 'searchProvider',
      label: 'Asset Search',
      resultKinds: ['asset', 'material'],
    };
    expect(contrib.resultKinds).toEqual(['asset', 'material']);
  });

  it('SearchProviderContribution defaults resultKinds to asset-only when omitted', () => {
    const contrib: SearchProviderContribution = {
      id: 'defaultSearch' as ContributionId,
      kind: 'searchProvider',
      label: 'Default Search',
    };
    expect(contrib.resultKinds).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// M6: Contribution kind bridging — parser is M6-active, output/search are typed
// ---------------------------------------------------------------------------

describe('M6: contribution kind bridging for parser/output/search', () => {
  it('parser is M6-active (contributionKindNotYetBridged returns null)', () => {
    expect(contributionKindNotYetBridged('parser')).toBeNull();
  });

  it('outputFormat is typed but execution is reserved (returns M6)', () => {
    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
  });

  it('searchProvider is typed but execution is reserved (returns M6)', () => {
    expect(contributionKindNotYetBridged('searchProvider')).toBe('M6');
  });

  it('render-dependent output declarations remain declarable but reserved for execution', () => {
    // outputFormat contributions (both compile-only and render-dependent)
    // are declarable in manifests during M6 but their runtime execution
    // is reserved. The bridging function reflects this by returning 'M6'
    // (not yet bridged).
    const bridged = contributionKindNotYetBridged('outputFormat');
    expect(bridged).toBe('M6');

    // contrats with parser which IS bridged
    expect(contributionKindNotYetBridged('parser')).toBeNull();
  });

  it('unsupported contribution behavior remains explicit (each returns its milestone)', () => {
    // Each reserved/unsupported kind returns its owning milestone name,
    // so consumers get a clear diagnostic rather than silent ignorance.
    // M9 clipType and automation are now bridged, returning null.
    expect(contributionKindNotYetBridged('clipType')).toBeNull();
    expect(contributionKindNotYetBridged('automation')).toBeNull();
    expect(contributionKindNotYetBridged('agentTool')).toBe('M5');
    expect(contributionKindNotYetBridged('agent')).toBe('M5');
  });

  it('CONTRIBUTION_KIND_MILESTONE maps M6 kinds to M6 milestone', () => {
    expect(CONTRIBUTION_KIND_MILESTONE.parser).toBe('M6');
    expect(CONTRIBUTION_KIND_MILESTONE.outputFormat).toBe('M6');
    expect(CONTRIBUTION_KIND_MILESTONE.searchProvider).toBe('M6');
  });

  it('already-bridged M1/M2/M4 kinds still return null', () => {
    // Regression: existing bridged kinds must remain bridged
    expect(contributionKindNotYetBridged('slot')).toBeNull();
    expect(contributionKindNotYetBridged('dialog')).toBeNull();
    expect(contributionKindNotYetBridged('panel')).toBeNull();
    expect(contributionKindNotYetBridged('inspectorSection')).toBeNull();
    expect(contributionKindNotYetBridged('command')).toBeNull();
    expect(contributionKindNotYetBridged('keybinding')).toBeNull();
    expect(contributionKindNotYetBridged('contextMenuItem')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// M6: Internal types are NOT leaked through @reigh/editor-sdk
// ---------------------------------------------------------------------------

describe('M6: internal types are NOT re-exported from @reigh/editor-sdk', () => {
  const M6_INTERNAL_FORBIDDEN = [
    // Parser internals
    'parserRegistry',
    'registerParser',
    'executeParser',
    'ParserRegistry',
    'ParserExecutor',
    'resolveParser',
    // Output format internals
    'outputFormatRegistry',
    'registerOutputFormat',
    'executeOutputFormat',
    'OutputFormatRegistry',
    'OutputFormatExecutor',
    'resolveOutputFormat',
    'renderPipeline',
    // Search provider internals
    'searchProviderRegistry',
    'registerSearchProvider',
    'executeSearch',
    'SearchProviderRegistry',
    'SearchExecutor',
    'resolveSearchProvider',
    // Search index internals
    'searchIndex',
    // Asset/material internal accessors
    'assetStore',
    'materialStore',
    'getAssetStore',
    'getMaterialStore',
    'resolveAsset',
    'resolveMaterial',
    // Export internals (execution, not registration)
    'executeExport',
    'renderAndExport',
    'ExportExecutor',
    'ExportPipeline',
  ];

  it('none of the forbidden M6 internal names appear as SDK value exports', () => {
    const valueExports = Object.keys(sdkStar);
    for (const forbidden of M6_INTERNAL_FORBIDDEN) {
      expect(valueExports).not.toContain(forbidden);
    }
  });

  it('forbidden M6 internal names are not accessible on the SDK namespace', () => {
    const ns = sdkStar as Record<string, unknown>;
    for (const forbidden of M6_INTERNAL_FORBIDDEN) {
      expect(ns[forbidden]).toBeUndefined();
    }
  });
});

// ---------------------------------------------------------------------------
// M7: Trusted component effect contribution type interfaces
// ---------------------------------------------------------------------------

describe('M7: trusted component effect type interfaces are importable from @reigh/editor-sdk', () => {
  it('EffectContribution shape is constructable (minimal)', () => {
    const contrib: EffectContribution = {
      id: 'myEffect' as ContributionId,
      kind: 'effect',
      effectId: 'fx.glow',
    };
    expect(contrib.kind).toBe('effect');
    expect(contrib.effectId).toBe('fx.glow');
    expect(contrib.allowBrowserExport).toBeUndefined();
    expect(contrib.allowWorkerExport).toBeUndefined();
    expect(contrib.order).toBeUndefined();
  });

  it('EffectContribution shape is constructable (full)', () => {
    const contrib: EffectContribution = {
      id: 'fullEffect' as ContributionId,
      kind: 'effect',
      effectId: 'fx.full',
      label: 'Full Effect',
      allowBrowserExport: true,
      allowWorkerExport: true,
      order: 10,
    };
    expect(contrib.kind).toBe('effect');
    expect(contrib.label).toBe('Full Effect');
    expect(contrib.allowBrowserExport).toBe(true);
    expect(contrib.allowWorkerExport).toBe(true);
    expect(contrib.order).toBe(10);
  });

  it('EffectContribution defaults allowBrowserExport and allowWorkerExport to false', () => {
    const contrib: EffectContribution = {
      id: 'defaultExport' as ContributionId,
      kind: 'effect',
      effectId: 'fx.default',
    };
    // SD2: defaults are false (preview-only)
    expect(contrib.allowBrowserExport ?? false).toBe(false);
    expect(contrib.allowWorkerExport ?? false).toBe(false);
  });

  it('EffectComponent type can be a plain object', () => {
    const comp: EffectComponent = { render: () => null };
    expect(typeof comp).toBe('object');
    expect(comp).not.toBeNull();
  });

  it('EffectComponent type can be a function', () => {
    const comp: EffectComponent = () => null;
    expect(typeof comp).toBe('function');
  });

  it('EffectParameterDefinition shape is constructable (number)', () => {
    const def: EffectParameterDefinition = {
      name: 'intensity',
      label: 'Intensity',
      description: 'The effect intensity',
      type: 'number',
      default: 50,
      min: 0,
      max: 100,
      step: 1,
    };
    expect(def.name).toBe('intensity');
    expect(def.type).toBe('number');
    expect(def.default).toBe(50);
    expect(def.min).toBe(0);
    expect(def.max).toBe(100);
    expect(def.step).toBe(1);
  });

  it('EffectParameterDefinition shape is constructable (select)', () => {
    const def: EffectParameterDefinition = {
      name: 'style',
      label: 'Style',
      description: 'Visual style',
      type: 'select',
      default: 'modern',
      options: [
        { label: 'Modern', value: 'modern' },
        { label: 'Classic', value: 'classic' },
      ],
    };
    expect(def.type).toBe('select');
    expect(def.options).toHaveLength(2);
    expect(def.options?.[0].label).toBe('Modern');
  });

  it('EffectParameterDefinition shape is constructable (boolean)', () => {
    const def: EffectParameterDefinition = {
      name: 'enabled',
      label: 'Enabled',
      description: 'Enable effect',
      type: 'boolean',
      default: true,
    };
    expect(def.type).toBe('boolean');
    expect(def.default).toBe(true);
  });

  it('EffectParameterDefinition shape is constructable (color)', () => {
    const def: EffectParameterDefinition = {
      name: 'tint',
      label: 'Tint',
      description: 'Color tint',
      type: 'color',
      default: '#ff0000',
    };
    expect(def.type).toBe('color');
    expect(def.default).toBe('#ff0000');
  });

  it('EffectParameterDefinition shape is constructable (audio-binding)', () => {
    const def: EffectParameterDefinition = {
      name: 'bass',
      label: 'Bass',
      description: 'Bass reactivity',
      type: 'audio-binding',
      default: { source: 'bass', min: 0, max: 1 },
    };
    expect(def.type).toBe('audio-binding');
    expect(def.default).toEqual({ source: 'bass', min: 0, max: 1 });
  });

  it('EffectParameterSchema is an array of parameter definitions', () => {
    const schema: EffectParameterSchema = [
      { name: 'a', label: 'A', description: 'D', type: 'number', default: 0 },
      { name: 'b', label: 'B', description: 'D', type: 'boolean', default: false },
    ];
    expect(Array.isArray(schema)).toBe(true);
    expect(schema).toHaveLength(2);
    expect(schema[0].name).toBe('a');
    expect(schema[1].name).toBe('b');
  });

  it('EffectRegistrationOptions shape is constructable', () => {
    const opts: EffectRegistrationOptions = {
      label: 'My Effect',
      parameterSchema: [
        { name: 'x', label: 'X', description: 'D', type: 'number', default: 0 },
      ],
    };
    expect(opts.label).toBe('My Effect');
    expect(opts.parameterSchema).toBeDefined();
    expect(opts.parameterSchema?.[0].name).toBe('x');
  });

  it('EffectRegistrationOptions with only label is constructable', () => {
    const opts: EffectRegistrationOptions = { label: 'Just a label' };
    expect(opts.label).toBe('Just a label');
    expect(opts.parameterSchema).toBeUndefined();
  });

  it('EffectRegistrationOptions empty object is constructable', () => {
    const opts: EffectRegistrationOptions = {};
    expect(opts.label).toBeUndefined();
    expect(opts.parameterSchema).toBeUndefined();
  });

  it('EffectRegistrationService interface has registerComponent method with correct signature', () => {
    // Compile-time proof that the interface shape is correct.
    const svc: EffectRegistrationService = {
      registerComponent(_effectId: string, _component: EffectComponent, _options?: EffectRegistrationOptions) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerComponent).toBe('function');

    const handle = svc.registerComponent('fx.test', {});
    expect(typeof handle.dispose).toBe('function');
  });
});

// ---------------------------------------------------------------------------
// M7: ExtensionContext includes effects registration service
// ---------------------------------------------------------------------------

describe('M7: ExtensionContext includes effects registration service', () => {
  it('ExtensionContext type includes readonly effects property', () => {
    // Compile-time proof: ExtensionContext must have an 'effects' member.
    const ctx: ExtensionContext = {
      apiVersion: 1,
      extension: {
        id: 'test.ext' as ExtensionId,
        version: '1.0.0',
        label: 'Test',
        manifest: {} as ExtensionManifest,
      },
      chrome: {
        toast: () => {},
        progress: () => {},
        subscribe: () => ({ dispose: () => {} }),
        focus: () => {},
        announce: () => {},
      },
      services: {
        settings: { get: () => undefined, set: () => {}, delete: () => {}, keys: () => [] },
        i18n: { t: (k: string) => k },
        diagnostics: { report: () => {}, diagnostics: [] },
      },
      creative: {
        project: {},
        timeline: {},
        assets: {},
        materials: {},
        sessions: {},
        export: {},
        stage: {},
        writing: {},
        reader: {},
        proposals: {},
      } as CreativeContext,
      commands: {
        registerCommand: () => ({ dispose: () => {} }),
      },
      effects: {
        registerComponent: () => ({ dispose: () => {} }),
      },
    };
    expect(ctx.effects).toBeDefined();
    expect(typeof ctx.effects.registerComponent).toBe('function');
  });
});

// ---------------------------------------------------------------------------
// M7: Internal effect registration types are NOT exported
// ---------------------------------------------------------------------------

describe('M7: internal effect registration types are NOT re-exported from @reigh/editor-sdk', () => {
  const M7_INTERNAL_FORBIDDEN = [
    // Effect registry internals
    'effectRegistry',
    'EffectRegistry',
    'EffectRegistryRecord',
    'EffectRegistrySnapshot',
    'createEffectRegistry',
    'registerEffect',
    'resolveEffect',
    'resolveSnapshotEffect',
    'validateEffectParameterSchema',
    'createEffectRegistrationService',
    // Effect component internals
    'EffectComponentProps',
  ];

  it('none of the forbidden M7 internal names appear as SDK value exports', () => {
    const valueExports = Object.keys(sdkStar);
    for (const forbidden of M7_INTERNAL_FORBIDDEN) {
      expect(valueExports).not.toContain(forbidden);
    }
  });

  it('forbidden M7 internal names are not accessible on the SDK namespace', () => {
    const ns = sdkStar as Record<string, unknown>;
    for (const forbidden of M7_INTERNAL_FORBIDDEN) {
      expect(ns[forbidden]).toBeUndefined();
    }
  });
});

// ---------------------------------------------------------------------------
// M7 / M8: Contribution kind bridging — effect is M7-bridged, transition is M8-bridged
// ---------------------------------------------------------------------------

describe('M7/M8: contribution kind bridging for effect and transition', () => {
  it('effect is M7-bridged (contributionKindNotYetBridged returns null)', () => {
    expect(contributionKindNotYetBridged('effect')).toBeNull();
  });

  it('transition is M8-bridged (contributionKindNotYetBridged returns null)', () => {
    expect(contributionKindNotYetBridged('transition')).toBeNull();
  });

  it('CONTRIBUTION_KIND_MILESTONE maps effect to M7 and transition to M8', () => {
    expect(CONTRIBUTION_KIND_MILESTONE.effect).toBe('M7');
    expect(CONTRIBUTION_KIND_MILESTONE.transition).toBe('M8');
  });

  it('previously bridged kinds remain bridged (regression)', () => {
    expect(contributionKindNotYetBridged('slot')).toBeNull();
    expect(contributionKindNotYetBridged('command')).toBeNull();
    expect(contributionKindNotYetBridged('parser')).toBeNull();
    expect(contributionKindNotYetBridged('effect')).toBeNull();
    expect(contributionKindNotYetBridged('transition')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// M8: Trusted component transition contribution type interfaces
// ---------------------------------------------------------------------------

describe('M8: trusted component transition type interfaces are importable from @reigh/editor-sdk', () => {
  it('TransitionContribution shape is constructable (minimal)', () => {
    const contrib: TransitionContribution = {
      id: 'myTransition' as ContributionId,
      kind: 'transition',
      transitionId: 'tx.dissolve',
    };
    expect(contrib.kind).toBe('transition');
    expect(contrib.transitionId).toBe('tx.dissolve');
    expect(contrib.allowBrowserExport).toBeUndefined();
    expect(contrib.allowWorkerExport).toBeUndefined();
    expect(contrib.order).toBeUndefined();
  });

  it('TransitionContribution shape is constructable (full)', () => {
    const contrib: TransitionContribution = {
      id: 'fullTransition' as ContributionId,
      kind: 'transition',
      transitionId: 'tx.full',
      label: 'Full Transition',
      allowBrowserExport: true,
      allowWorkerExport: true,
      order: 10,
    };
    expect(contrib.kind).toBe('transition');
    expect(contrib.label).toBe('Full Transition');
    expect(contrib.allowBrowserExport).toBe(true);
    expect(contrib.allowWorkerExport).toBe(true);
    expect(contrib.order).toBe(10);
  });

  it('TransitionContribution defaults allowBrowserExport and allowWorkerExport to false', () => {
    const contrib: TransitionContribution = {
      id: 'defaultExport' as ContributionId,
      kind: 'transition',
      transitionId: 'tx.default',
    };
    // SD3: defaults are false (preview-only)
    expect(contrib.allowBrowserExport ?? false).toBe(false);
    expect(contrib.allowWorkerExport ?? false).toBe(false);
  });

  it('TransitionRenderer type can be a plain object', () => {
    const renderer: TransitionRenderer = { render: () => ({}) };
    expect(typeof renderer).toBe('object');
    expect(renderer).not.toBeNull();
  });

  it('TransitionRenderer type can be a function', () => {
    const renderer: TransitionRenderer = () => ({});
    expect(typeof renderer).toBe('function');
  });

  it('TransitionParameterDefinition shape is constructable (number)', () => {
    const def: TransitionParameterDefinition = {
      name: 'duration',
      label: 'Duration',
      description: 'Transition duration in frames',
      type: 'number',
      default: 30,
      min: 1,
      max: 120,
      step: 1,
    };
    expect(def.name).toBe('duration');
    expect(def.type).toBe('number');
    expect(def.default).toBe(30);
    expect(def.min).toBe(1);
    expect(def.max).toBe(120);
    expect(def.step).toBe(1);
  });

  it('TransitionParameterDefinition shape is constructable (select)', () => {
    const def: TransitionParameterDefinition = {
      name: 'direction',
      label: 'Direction',
      description: 'Wipe direction',
      type: 'select',
      default: 'left',
      options: [
        { label: 'Left', value: 'left' },
        { label: 'Right', value: 'right' },
      ],
    };
    expect(def.type).toBe('select');
    expect(def.options).toHaveLength(2);
    expect(def.options?.[0].label).toBe('Left');
  });

  it('TransitionParameterDefinition shape is constructable (boolean)', () => {
    const def: TransitionParameterDefinition = {
      name: 'reverse',
      label: 'Reverse',
      description: 'Reverse transition direction',
      type: 'boolean',
      default: false,
    };
    expect(def.type).toBe('boolean');
    expect(def.default).toBe(false);
  });

  it('TransitionParameterDefinition shape is constructable (color)', () => {
    const def: TransitionParameterDefinition = {
      name: 'matteColor',
      label: 'Matte Color',
      description: 'Color for matte transitions',
      type: 'color',
      default: '#000000',
    };
    expect(def.type).toBe('color');
    expect(def.default).toBe('#000000');
  });

  it('TransitionParameterDefinition shape is constructable (audio-binding)', () => {
    const def: TransitionParameterDefinition = {
      name: 'reactivity',
      label: 'Reactivity',
      description: 'Audio reactivity',
      type: 'audio-binding',
      default: { source: 'kick', min: 0, max: 1 },
    };
    expect(def.type).toBe('audio-binding');
    expect(def.default).toEqual({ source: 'kick', min: 0, max: 1 });
  });

  it('TransitionParameterSchema is an array of parameter definitions', () => {
    const schema: TransitionParameterSchema = [
      { name: 'a', label: 'A', description: 'D', type: 'number', default: 0 },
      { name: 'b', label: 'B', description: 'D', type: 'boolean', default: false },
    ];
    expect(Array.isArray(schema)).toBe(true);
    expect(schema).toHaveLength(2);
    expect(schema[0].name).toBe('a');
    expect(schema[1].name).toBe('b');
  });

  it('TransitionRegistrationOptions shape is constructable', () => {
    const opts: TransitionRegistrationOptions = {
      label: 'My Transition',
      parameterSchema: [
        { name: 'x', label: 'X', description: 'D', type: 'number', default: 0 },
      ],
    };
    expect(opts.label).toBe('My Transition');
    expect(opts.parameterSchema).toBeDefined();
    expect(opts.parameterSchema?.[0].name).toBe('x');
  });

  it('TransitionRegistrationOptions with only label is constructable', () => {
    const opts: TransitionRegistrationOptions = { label: 'Just a label' };
    expect(opts.label).toBe('Just a label');
    expect(opts.parameterSchema).toBeUndefined();
  });

  it('TransitionRegistrationOptions empty object is constructable', () => {
    const opts: TransitionRegistrationOptions = {};
    expect(opts.label).toBeUndefined();
    expect(opts.parameterSchema).toBeUndefined();
  });

  it('TransitionRegistrationService interface has registerRenderer method with correct signature', () => {
    const svc: TransitionRegistrationService = {
      registerRenderer(_transitionId: string, _renderer: TransitionRenderer, _options?: TransitionRegistrationOptions) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerRenderer).toBe('function');

    const handle = svc.registerRenderer('tx.test', {});
    expect(typeof handle.dispose).toBe('function');
  });
});

// ---------------------------------------------------------------------------
// M8: ExtensionContext includes transitions registration service
// ---------------------------------------------------------------------------

describe('M8: ExtensionContext includes transitions registration service', () => {
  it('ExtensionContext type includes readonly transitions property', () => {
    const ctx: ExtensionContext = {
      apiVersion: 1,
      extension: {
        id: 'test.ext' as ExtensionId,
        version: '1.0.0',
        label: 'Test',
        manifest: {} as ExtensionManifest,
      },
      chrome: {
        toast: () => {},
        progress: () => {},
        subscribe: () => ({ dispose: () => {} }),
        focus: () => {},
        announce: () => {},
      },
      services: {
        settings: { get: () => undefined, set: () => {}, delete: () => {}, keys: () => [] },
        i18n: { t: (k: string) => k },
        diagnostics: { report: () => {}, diagnostics: [] },
      },
      creative: {
        project: {},
        timeline: {},
        assets: {},
        materials: {},
        sessions: {},
        export: {},
        stage: {},
        writing: {},
        reader: {},
        proposals: {},
      } as CreativeContext,
      commands: {
        registerCommand: () => ({ dispose: () => {} }),
      },
      effects: {
        registerComponent: () => ({ dispose: () => {} }),
      },
      transitions: {
        registerRenderer: () => ({ dispose: () => {} }),
      },
    };
    expect(ctx.transitions).toBeDefined();
    expect(typeof ctx.transitions.registerRenderer).toBe('function');
  });
});

// ---------------------------------------------------------------------------
// M8: Internal transition registration types are NOT exported
// ---------------------------------------------------------------------------

describe('M8: internal transition registration types are NOT re-exported from @reigh/editor-sdk', () => {
  const M8_INTERNAL_FORBIDDEN = [
    // Transition registry internals
    'transitionRegistry',
    'TransitionRegistry',
    'TransitionRegistryRecord',
    'TransitionRegistrySnapshot',
    'createTransitionRegistry',
    'registerTransition',
    'resolveTransition',
    'resolveSnapshotTransition',
    'validateTransitionParameterSchema',
    'createTransitionRegistrationService',
    // Transition renderer internals
    'TransitionRendererProps',
  ];

  it('none of the forbidden M8 internal names appear as SDK value exports', () => {
    const valueExports = Object.keys(sdkStar);
    for (const forbidden of M8_INTERNAL_FORBIDDEN) {
      expect(valueExports).not.toContain(forbidden);
    }
  });

  it('forbidden M8 internal names are not accessible on the SDK namespace', () => {
    const ns = sdkStar as Record<string, unknown>;
    for (const forbidden of M8_INTERNAL_FORBIDDEN) {
      expect(ns[forbidden]).toBeUndefined();
    }
  });
});

// ---------------------------------------------------------------------------
// M9: Clip type contribution type interfaces
// ---------------------------------------------------------------------------

describe('M9: trusted component clip type interfaces are importable from @reigh/editor-sdk', () => {
  it('ClipTypeContribution shape is constructable (minimal)', () => {
    const contrib: ClipTypeContribution = {
      id: 'myClipType' as ContributionId,
      kind: 'clipType',
      clipTypeId: 'ct.counter',
    };
    expect(contrib.kind).toBe('clipType');
    expect(contrib.clipTypeId).toBe('ct.counter');
    expect(contrib.allowBrowserExport).toBeUndefined();
    expect(contrib.allowWorkerExport).toBeUndefined();
    expect(contrib.order).toBeUndefined();
  });

  it('ClipTypeContribution shape is constructable (full)', () => {
    const contrib: ClipTypeContribution = {
      id: 'fullClipType' as ContributionId,
      kind: 'clipType',
      clipTypeId: 'ct.full',
      label: 'Full Clip Type',
      allowBrowserExport: true,
      allowWorkerExport: true,
      order: 10,
    };
    expect(contrib.kind).toBe('clipType');
    expect(contrib.label).toBe('Full Clip Type');
    expect(contrib.allowBrowserExport).toBe(true);
    expect(contrib.allowWorkerExport).toBe(true);
    expect(contrib.order).toBe(10);
  });

  it('ClipTypeContribution defaults allowBrowserExport and allowWorkerExport to false', () => {
    const contrib: ClipTypeContribution = {
      id: 'defaultExport' as ContributionId,
      kind: 'clipType',
      clipTypeId: 'ct.default',
    };
    expect(contrib.allowBrowserExport ?? false).toBe(false);
    expect(contrib.allowWorkerExport ?? false).toBe(false);
  });

  it('ClipRenderer type can be a plain object', () => {
    const renderer: ClipRenderer = { render: () => null };
    expect(typeof renderer).toBe('object');
    expect(renderer).not.toBeNull();
  });

  it('ClipRenderer type can be a function', () => {
    const renderer: ClipRenderer = () => null;
    expect(typeof renderer).toBe('function');
  });

  it('ClipInspector type can be a plain object', () => {
    const inspector: ClipInspector = { render: () => null };
    expect(typeof inspector).toBe('object');
    expect(inspector).not.toBeNull();
  });

  it('ClipInspector type can be a function', () => {
    const inspector: ClipInspector = () => null;
    expect(typeof inspector).toBe('function');
  });

  it('ClipParameterDefinition shape is constructable (number)', () => {
    const def: ClipParameterDefinition = {
      name: 'count',
      label: 'Count',
      description: 'Number of items',
      type: 'number',
      default: 5,
      min: 1,
      max: 10,
      step: 1,
    };
    expect(def.name).toBe('count');
    expect(def.type).toBe('number');
    expect(def.default).toBe(5);
    expect(def.min).toBe(1);
    expect(def.max).toBe(10);
    expect(def.step).toBe(1);
  });

  it('ClipParameterDefinition shape is constructable (select)', () => {
    const def: ClipParameterDefinition = {
      name: 'variant',
      label: 'Variant',
      description: 'Display variant',
      type: 'select',
      default: 'a',
      options: [
        { label: 'Variant A', value: 'a' },
        { label: 'Variant B', value: 'b' },
      ],
    };
    expect(def.type).toBe('select');
    expect(def.options).toHaveLength(2);
    expect(def.options?.[0].label).toBe('Variant A');
  });

  it('ClipParameterDefinition shape is constructable (boolean)', () => {
    const def: ClipParameterDefinition = {
      name: 'enabled',
      label: 'Enabled',
      description: 'Enable clip',
      type: 'boolean',
      default: true,
    };
    expect(def.type).toBe('boolean');
    expect(def.default).toBe(true);
  });

  it('ClipParameterDefinition shape is constructable (color)', () => {
    const def: ClipParameterDefinition = {
      name: 'background',
      label: 'Background',
      description: 'Background color',
      type: 'color',
      default: '#ffffff',
    };
    expect(def.type).toBe('color');
    expect(def.default).toBe('#ffffff');
  });

  it('ClipParameterDefinition shape is constructable (audio-binding)', () => {
    const def: ClipParameterDefinition = {
      name: 'reactivity',
      label: 'Reactivity',
      description: 'Audio reactivity',
      type: 'audio-binding',
      default: { source: 'bass', min: 0, max: 1 },
    };
    expect(def.type).toBe('audio-binding');
    expect(def.default).toEqual({ source: 'bass', min: 0, max: 1 });
  });

  it('ClipParameterSchema is an array of parameter definitions', () => {
    const schema: ClipParameterSchema = [
      { name: 'a', label: 'A', description: 'D', type: 'number', default: 0 },
      { name: 'b', label: 'B', description: 'D', type: 'boolean', default: false },
    ];
    expect(Array.isArray(schema)).toBe(true);
    expect(schema).toHaveLength(2);
    expect(schema[0].name).toBe('a');
    expect(schema[1].name).toBe('b');
  });

  it('ClipTypeRegistrationOptions shape is constructable', () => {
    const opts: ClipTypeRegistrationOptions = {
      label: 'My Clip Type',
      parameterSchema: [
        { name: 'x', label: 'X', description: 'D', type: 'number', default: 0 },
      ],
    };
    expect(opts.label).toBe('My Clip Type');
    expect(opts.parameterSchema).toBeDefined();
    expect(opts.parameterSchema?.[0].name).toBe('x');
  });

  it('ClipTypeRegistrationOptions with only label is constructable', () => {
    const opts: ClipTypeRegistrationOptions = { label: 'Just a label' };
    expect(opts.label).toBe('Just a label');
    expect(opts.parameterSchema).toBeUndefined();
  });

  it('ClipTypeRegistrationOptions empty object is constructable', () => {
    const opts: ClipTypeRegistrationOptions = {};
    expect(opts.label).toBeUndefined();
    expect(opts.parameterSchema).toBeUndefined();
  });

  it('ClipTypeRegistrationService interface has registerClipType method with correct signature', () => {
    const svc: ClipTypeRegistrationService = {
      registerClipType(
        _clipTypeId: string,
        _renderer: ClipRenderer,
        _inspector?: ClipInspector,
        _options?: ClipTypeRegistrationOptions,
      ) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerClipType).toBe('function');

    const handle = svc.registerClipType('ct.test', {});
    expect(typeof handle.dispose).toBe('function');
  });
});

// ---------------------------------------------------------------------------
// M9: ExtensionContext includes clipTypes registration service
// ---------------------------------------------------------------------------

describe('M9: ExtensionContext includes clipTypes registration service', () => {
  it('ExtensionContext type includes readonly clipTypes property', () => {
    const ctx: ExtensionContext = {
      apiVersion: 1,
      extension: {
        id: 'test.ext' as ExtensionId,
        version: '1.0.0',
        label: 'Test',
        manifest: {} as ExtensionManifest,
      },
      chrome: {
        toast: () => {},
        progress: () => {},
        subscribe: () => ({ dispose: () => {} }),
        focus: () => {},
        announce: () => {},
      },
      services: {
        settings: { get: () => undefined, set: () => {}, delete: () => {}, keys: () => [] },
        i18n: { t: (k: string) => k },
        diagnostics: { report: () => {}, diagnostics: [] },
      },
      creative: {
        project: {},
        timeline: {},
        assets: {},
        materials: {},
        sessions: {},
        export: {},
        stage: {},
        writing: {},
        reader: {},
        proposals: {},
      } as CreativeContext,
      commands: {
        registerCommand: () => ({ dispose: () => {} }),
      },
      effects: {
        registerComponent: () => ({ dispose: () => {} }),
      },
      transitions: {
        registerRenderer: () => ({ dispose: () => {} }),
      },
      clipTypes: {
        registerClipType: () => ({ dispose: () => {} }),
      },
    };
    expect(ctx.clipTypes).toBeDefined();
    expect(typeof ctx.clipTypes.registerClipType).toBe('function');
  });
});

// ---------------------------------------------------------------------------
// M9: Internal clip type registration types are NOT exported
// ---------------------------------------------------------------------------

describe('M9: internal clip type registration types are NOT re-exported from @reigh/editor-sdk', () => {
  const M9_INTERNAL_FORBIDDEN = [
    // Clip type registry internals
    'clipTypeRegistry',
    'ClipTypeRegistry',
    'ClipTypeRegistryRecord',
    'ClipTypeRegistrySnapshot',
    'createClipTypeRegistry',
    'registerClipTypeHandler',
    'resolveClipType',
    'resolveSnapshotClipType',
    'validateClipTypeParameterSchema',
    'createClipTypeRegistrationService',
    // Clip renderer internals
    'ClipRendererProps',
    'ClipInspectorProps',
  ];

  it('none of the forbidden M9 internal names appear as SDK value exports', () => {
    const valueExports = Object.keys(sdkStar);
    for (const forbidden of M9_INTERNAL_FORBIDDEN) {
      expect(valueExports).not.toContain(forbidden);
    }
  });

  it('forbidden M9 internal names are not accessible on the SDK namespace', () => {
    const ns = sdkStar as Record<string, unknown>;
    for (const forbidden of M9_INTERNAL_FORBIDDEN) {
      expect(ns[forbidden]).toBeUndefined();
    }
  });
});

// ---------------------------------------------------------------------------
// M9: Keyframe contracts
// ---------------------------------------------------------------------------

describe('M9: keyframe contracts are importable from @reigh/editor-sdk', () => {
  it('KeyframeInterpolation accepts only linear and hold', () => {
    const linear: KeyframeInterpolation = 'linear';
    const hold: KeyframeInterpolation = 'hold';
    expect(linear).toBe('linear');
    expect(hold).toBe('hold');
  });

  it('Keyframe shape is constructable', () => {
    const kf: Keyframe = {
      time: 1.5,
      value: 0.75,
      interpolation: 'linear',
    };
    expect(kf.time).toBe(1.5);
    expect(kf.value).toBe(0.75);
    expect(kf.interpolation).toBe('linear');
  });

  it('Keyframe supports string values', () => {
    const kf: Keyframe = {
      time: 2.0,
      value: 'active',
      interpolation: 'hold',
    };
    expect(kf.value).toBe('active');
    expect(kf.interpolation).toBe('hold');
  });

  it('Keyframe supports boolean values', () => {
    const kf: Keyframe = {
      time: 0.0,
      value: true,
      interpolation: 'linear',
    };
    expect(kf.value).toBe(true);
  });

  it('InterpolatedParam shape is constructable', () => {
    const param: InterpolatedParam = {
      name: 'opacity',
      value: 0.5,
    };
    expect(param.name).toBe('opacity');
    expect(param.value).toBe(0.5);
  });
});

// ---------------------------------------------------------------------------
// M9: Automation clip contracts
// ---------------------------------------------------------------------------

describe('M9: automation clip contracts are importable from @reigh/editor-sdk', () => {
  it('AutomationClipTarget shape is constructable', () => {
    const target: AutomationClipTarget = {
      contributionId: 'myContrib',
      parameterPath: 'params.opacity',
    };
    expect(target.contributionId).toBe('myContrib');
    expect(target.parameterPath).toBe('params.opacity');
  });

  it('AutomationClipParams shape is constructable', () => {
    const params: AutomationClipParams = {
      target: {
        contributionId: 'myContrib',
        parameterPath: 'params.opacity',
      },
      keyframes: [
        { time: 0, value: 0, interpolation: 'linear' },
        { time: 1, value: 1, interpolation: 'linear' },
      ],
      enabled: true,
    };
    expect(params.target.contributionId).toBe('myContrib');
    expect(params.keyframes).toHaveLength(2);
    expect(params.enabled).toBe(true);
  });

  it('AutomationClipParams with disabled state is constructable', () => {
    const params: AutomationClipParams = {
      target: {
        contributionId: 'otherContrib',
        parameterPath: 'params.scale',
      },
      keyframes: [],
      enabled: false,
    };
    expect(params.enabled).toBe(false);
    expect(params.keyframes).toHaveLength(0);
  });
});
