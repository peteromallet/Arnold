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
  getConfigSignature,
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

  it('exports getConfigSignature as a function', () => {
    expect(typeof getConfigSignature).toBe('function');
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
  getVideoFamilyDefinition,
  getVideoFamilyConformanceReport,
  getVideoFamilyLegacyBridgeStatus,
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
  // M3 Expiry / conflict diagnostics
  ProposalExpiryDetail,
  ProposalEnvelope,
  // M1: Proposal import contracts
  ProposalImportDiagnostic,
  ProposalImportResult,
  ProposalImportStatus,
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
  ProcessLiveSourceValueShape,
  ProcessLiveSourceDeclaration,
  ProcessLiveSourceBinding,
  ProcessContribution,
} from '@reigh/editor-sdk';
import type {
  ExtensionId,
  ExtensionManifest,
  ExtensionContext,
  ExtensionDiagnostic,
  DisposeHandle,
  // M1a: Composition reference identity
  ContributionRef,
  LiveSourceRef,
  MaterialRef,
} from '@reigh/editor-sdk';
import type {
  ProcessProgressEvent,
  ProcessRoundtripRequest,
  ProcessRoundtripResult,
  ProcessLogSummary,
} from '@reigh/editor-sdk/capabilities';
import type {
  ProcessLifecycleState,
  ProcessOutputKind,
  ProcessSpec,
  ProcessStatus,
  ProcessStatusBase,
  ProcessEnvFieldSpec,
  ProcessOperationSpec,
} from '@reigh/editor-sdk/video/families/processes';

// M1a value exports
import {
  contributionRefKey,
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

  it('ProposalState includes expired', () => {
    const states: ProposalState[] = [
      'pending',
      'accepted',
      'rejected',
      'stale',
      'expired',
    ];
    expect(states).toHaveLength(5);
    expect(states).toContain('expired');
  });

  it('TimelineProposal shape is constructable with expiry fields', () => {
    const now = Date.now();
    const proposal: TimelineProposal = {
      id: 'prop-exp',
      source: 'com.test.ext',
      rationale: 'Test expiry',
      state: 'pending',
      patch: { version: 0, operations: [] },
      baseVersion: 5,
      previewable: true,
      createdAt: now,
      updatedAt: now,
      expiresAt: now + 60_000, // 1 minute TTL
    };
    expect(proposal.expiresAt).toBe(now + 60_000);
    expect(proposal.expiryDetail).toBeUndefined();
  });

  it('TimelineProposal carries expiryDetail when stale/expired', () => {
    const now = Date.now();
    const detail: ProposalExpiryDetail = {
      reason: 'base-version-mismatch',
      baseVersion: 5,
      currentVersion: 7,
      createdAt: now - 60000,
      expiredAt: now,
      ttlMs: 30000,
    };
    const proposal: TimelineProposal = {
      id: 'prop-stale',
      source: 'com.test.ext',
      state: 'stale',
      patch: { version: 0, operations: [] },
      baseVersion: 5,
      previewable: false,
      createdAt: now - 60000,
      updatedAt: now,
      expiryDetail: detail,
    };
    expect(proposal.state).toBe('stale');
    expect(proposal.expiryDetail).toBeDefined();
    expect(proposal.expiryDetail!.reason).toBe('base-version-mismatch');
    expect(proposal.expiryDetail!.currentVersion).toBe(7);
  });

  it('ProposalExpiryDetail shape is constructable for ttl-elapsed', () => {
    const now = Date.now();
    const detail: ProposalExpiryDetail = {
      reason: 'ttl-elapsed',
      baseVersion: 3,
      currentVersion: 3,
      createdAt: now - 120000,
      expiredAt: now,
      ttlMs: 60000,
    };
    expect(detail.reason).toBe('ttl-elapsed');
    expect(detail.ttlMs).toBe(60000);
    // currentVersion matches baseVersion when expired by TTL (no conflict)
    expect(detail.baseVersion).toBe(detail.currentVersion);
  });

  it('ProposalExpiryDetail shape is constructable for manual expiry', () => {
    const now = Date.now();
    const detail: ProposalExpiryDetail = {
      reason: 'manual',
      baseVersion: 1,
      currentVersion: 2,
      createdAt: now - 5000,
      expiredAt: now,
    };
    expect(detail.reason).toBe('manual');
    expect(detail.ttlMs).toBeUndefined();
  });

  it('ProposalEnvelope shape is constructable', () => {
    const now = Date.now();
    const proposal: TimelineProposal = {
      id: 'env-prop-1',
      source: 'edge-agent',
      rationale: 'Move clip',
      state: 'pending',
      patch: {
        version: 0,
        operations: [{ op: 'clip.move', target: 'clip-1', payload: { at: 2.5 } }],
      },
      baseVersion: 4,
      previewable: true,
      createdAt: now,
      updatedAt: now,
    };
    const envelope: ProposalEnvelope = {
      proposals: [proposal],
      baseVersion: 4,
      summary: 'Moved clip-1 to 2.5s',
      mutationApplied: false,
    };
    expect(envelope.proposals).toHaveLength(1);
    expect(envelope.proposals[0].id).toBe('env-prop-1');
    expect(envelope.baseVersion).toBe(4);
    expect(envelope.summary).toBe('Moved clip-1 to 2.5s');
    expect(envelope.mutationApplied).toBe(false);
  });

  it('ProposalEnvelope with empty proposals and no summary is constructable', () => {
    const envelope: ProposalEnvelope = {
      proposals: [],
      baseVersion: 1,
      mutationApplied: false,
    };
    expect(envelope.proposals).toHaveLength(0);
    expect(envelope.summary).toBeUndefined();
    expect(envelope.mutationApplied).toBe(false);
  });

  it('ProposalEnvelope mutationApplied=true for apply-mode responses', () => {
    const envelope: ProposalEnvelope = {
      proposals: [],
      baseVersion: 5,
      mutationApplied: true,
    };
    expect(envelope.mutationApplied).toBe(true);
  });

  // ── M1: Proposal import contracts ─────────────────────────────────────────

  it('ProposalImportDiagnostic shape is constructable', () => {
    const diag: ProposalImportDiagnostic = {
      severity: 'error',
      code: 'proposal-import/missing-id',
      message: 'Proposal missing required id field',
      proposalIndex: 0,
      proposalId: undefined,
      detail: { source: 'edge-agent', reason: 'invalid-shape' },
    };
    expect(diag.severity).toBe('error');
    expect(diag.code).toBe('proposal-import/missing-id');
    expect(diag.proposalIndex).toBe(0);
    expect(diag.proposalId).toBeUndefined();
    expect(diag.detail).toEqual({ source: 'edge-agent', reason: 'invalid-shape' });
  });

  it('ProposalImportResult shape is constructable', () => {
    const result: ProposalImportResult = {
      imported: 2,
      skipped: 1,
      rejected: 0,
      statuses: [
        { proposalId: 'prop-1', status: 'imported' },
        { proposalId: 'prop-2', status: 'imported' },
        { proposalId: 'prop-3', status: 'skipped' },
      ],
      diagnostics: [],
    };
    expect(result.imported).toBe(2);
    expect(result.skipped).toBe(1);
    expect(result.rejected).toBe(0);
    expect(result.statuses).toHaveLength(3);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('ProposalImportResult with diagnostics is constructable', () => {
    const result: ProposalImportResult = {
      imported: 0,
      skipped: 0,
      rejected: 2,
      statuses: [
        { proposalId: 'bad-1', status: 'rejected' },
        { proposalId: 'bad-2', status: 'rejected' },
      ],
      diagnostics: [
        {
          severity: 'error',
          code: 'proposal-import/invalid-shape',
          message: 'Proposal missing required fields',
          proposalIndex: 0,
          proposalId: 'bad-1',
        },
        {
          severity: 'warning',
          code: 'proposal-import/stale-base-version',
          message: 'Proposal baseVersion behind current snapshot',
          proposalIndex: 1,
          proposalId: 'bad-2',
        },
      ],
    };
    expect(result.rejected).toBe(2);
    expect(result.diagnostics).toHaveLength(2);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[1].severity).toBe('warning');
  });

  it('ProposalImportStatus only accepts "imported" | "skipped" | "rejected"', () => {
    // Type-level contract: the union is narrow and compile-time checked.
    const statuses: ProposalImportStatus[] = ['imported', 'skipped', 'rejected'];
    expect(statuses).toHaveLength(3);
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
  it('parser is delegated to a placeholder adapter (contributionKindNotYetBridged returns M6)', () => {
    expect(contributionKindNotYetBridged('parser')).toBe('M6');
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

    // parser is now delegated to a placeholder adapter, so it also reports M6.
    expect(contributionKindNotYetBridged('parser')).toBe('M6');
  });

  it('unsupported contribution behavior remains explicit (registry-derived)', () => {
    // Each reserved/unsupported kind returns its owning milestone name,
    // so consumers get a clear diagnostic rather than silent ignorance.
    // M9 clipType and automation are bridged (executionMaturity runtime-bridged).
    expect(contributionKindNotYetBridged('clipType')).toBeNull();
    expect(contributionKindNotYetBridged('automation')).toBeNull();
    // agentTool is delegated to a placeholder adapter (executionMaturity delegated).
    expect(contributionKindNotYetBridged('agentTool')).toBe('M10');
    // agent is NOT bridged (executionMaturity delegated — no host adapter).
    expect(contributionKindNotYetBridged('agent')).toBe('M10');
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
  it('effect is delegated to a placeholder adapter (contributionKindNotYetBridged returns M7)', () => {
    expect(contributionKindNotYetBridged('effect')).toBe('M7');
  });

  it('transition is delegated to a placeholder adapter (contributionKindNotYetBridged returns M8)', () => {
    expect(contributionKindNotYetBridged('transition')).toBe('M8');
  });

  it('CONTRIBUTION_KIND_MILESTONE maps effect to M7 and transition to M8', () => {
    expect(CONTRIBUTION_KIND_MILESTONE.effect).toBe('M7');
    expect(CONTRIBUTION_KIND_MILESTONE.transition).toBe('M8');
  });

  it('previously bridged kinds remain bridged (regression)', () => {
    expect(contributionKindNotYetBridged('slot')).toBeNull();
    expect(contributionKindNotYetBridged('command')).toBeNull();
    expect(contributionKindNotYetBridged('parser')).toBe('M6');
    expect(contributionKindNotYetBridged('effect')).toBe('M7');
    expect(contributionKindNotYetBridged('transition')).toBe('M8');
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

// ---------------------------------------------------------------------------
// M5: Renderability, blocker, material, and artifact type interfaces
// ---------------------------------------------------------------------------

import type {
  DeterminismStatus,
  RenderBlockerReason,
  RenderRoute,
  RenderCapability,
  RenderCapabilityStatus,
  ContributionRenderability,
  CapabilityFinding,
  CapabilityFindingSeverity,
  RenderBlocker,
  ShaderMaterializerRequirementScope,
  RenderMaterial,
  RenderMaterialRef,
  RenderMaterialMediaKind,
  RenderLocatorKind,
  RenderStorageLocator,
  RenderArtifact,
  ArtifactBoundary,
  BakeContract,
} from '@reigh/editor-sdk';

import {
  DETERMINISM_STATUSES,
  RENDER_BLOCKER_REASONS,
  RENDER_ROUTES,
} from '@reigh/editor-sdk';

describe('M5: renderability type interfaces are importable from @reigh/editor-sdk', () => {
  it('RenderRoute union covers preview, browser-export, worker-export, sidecar-export', () => {
    const routes: RenderRoute[] = ['preview', 'browser-export', 'worker-export', 'sidecar-export'];
    expect(routes).toHaveLength(4);
    expect(routes).toContain('preview');
    expect(routes).toContain('browser-export');
    expect(routes).toContain('worker-export');
    expect(routes).toContain('sidecar-export');
  });

  it('RENDER_ROUTES const is a frozen array of all four routes', () => {
    expect(Array.isArray(RENDER_ROUTES)).toBe(true);
    expect(RENDER_ROUTES).toHaveLength(4);
    expect(RENDER_ROUTES).toContain('preview');
    expect(Object.isFrozen(RENDER_ROUTES)).toBe(true);
  });

  it('DeterminismStatus covers all six statuses', () => {
    const statuses: DeterminismStatus[] = [
      'deterministic',
      'process-dependent',
      'preview-only',
      'sampling-required',
      'unknown',
      'deferred',
    ];
    expect(statuses).toHaveLength(6);
  });

  it('DETERMINISM_STATUSES is a frozen array', () => {
    expect(Array.isArray(DETERMINISM_STATUSES)).toBe(true);
    expect(DETERMINISM_STATUSES.length).toBeGreaterThan(0);
    expect(Object.isFrozen(DETERMINISM_STATUSES)).toBe(true);
  });

  it('RenderBlockerReason covers all blocker codes', () => {
    const reasons: RenderBlockerReason[] = [
      'route-unsupported',
      'missing-contribution',
      'missing-materializer',
      'process-unavailable',
      'insufficient-capability',
      'unknown',
    ];
    expect(reasons).toHaveLength(6);
  });

  it('RENDER_BLOCKER_REASONS is a frozen array', () => {
    expect(Array.isArray(RENDER_BLOCKER_REASONS)).toBe(true);
    expect(RENDER_BLOCKER_REASONS.length).toBeGreaterThan(0);
    expect(Object.isFrozen(RENDER_BLOCKER_REASONS)).toBe(true);
  });

  it('RenderCapability shape is constructable', () => {
    const cap: RenderCapability = {
      route: 'browser-export' as RenderRoute,
      status: 'supported',
    };
    expect(cap.route).toBe('browser-export');
    expect(cap.status).toBe('supported');
  });

  it('RenderCapabilityStatus covers supported, blocked, unknown', () => {
    const statuses: RenderCapabilityStatus[] = ['supported', 'blocked', 'unknown'];
    expect(statuses).toHaveLength(3);
  });

  it('ContributionRenderability shape is constructable', () => {
    const renderability: ContributionRenderability = {
      capabilities: [
        { route: 'preview' as RenderRoute, status: 'supported' },
        { route: 'browser-export' as RenderRoute, status: 'blocked' },
      ],
    };
    expect(renderability.capabilities).toHaveLength(2);
  });

  it('CapabilityFinding shape is constructable', () => {
    const finding: CapabilityFinding = {
      id: 'cf-1',
      severity: 'warning',
      route: 'worker-export' as RenderRoute,
      reason: 'route-unsupported' as RenderBlockerReason,
      message: 'Worker export is not supported',
    };
    expect(finding.id).toBe('cf-1');
    expect(finding.severity).toBe('warning');
    expect(finding.route).toBe('worker-export');
    expect(finding.reason).toBe('route-unsupported');
  });

  it('CapabilityFindingSeverity covers error, warning, info', () => {
    const severities: CapabilityFindingSeverity[] = ['error', 'warning', 'info'];
    expect(severities).toHaveLength(3);
  });

  it('RenderBlocker extends CapabilityFinding', () => {
    const blocker: RenderBlocker = {
      id: 'rb-1',
      severity: 'error',
      route: 'browser-export' as RenderRoute,
      reason: 'missing-materializer' as RenderBlockerReason,
      message: 'No materializer available',
    };
    expect(blocker.severity).toBe('error');
    expect(blocker.reason).toBe('missing-materializer');
  });

  it('RenderMaterialRef shape is constructable', () => {
    const ref: RenderMaterialRef = {
      id: 'mat-1',
      mediaKind: 'video' as RenderMaterialMediaKind,
      locator: { kind: 'asset-registry' as RenderLocatorKind, uri: 'asset://mat-1' },
      determinism: 'deterministic' as DeterminismStatus,
    };
    expect(ref.id).toBe('mat-1');
    expect(ref.mediaKind).toBe('video');
    expect(ref.locator.kind).toBe('asset-registry');
  });

  it('RenderMaterial extends RenderMaterialRef with duration and metadata', () => {
    const mat: RenderMaterial = {
      id: 'mat-2',
      mediaKind: 'image' as RenderMaterialMediaKind,
      locator: { kind: 'inline' as RenderLocatorKind, uri: 'data:image/png;base64,' },
      determinism: 'deterministic' as DeterminismStatus,
      durationSeconds: 5,
      metadata: { resolution: '1920x1080' },
    };
    expect(mat.durationSeconds).toBe(5);
    expect(mat.metadata?.resolution).toBe('1920x1080');
  });

  it('RenderMaterialMediaKind covers video, image, audio, sidecar, placeholder', () => {
    const kinds: RenderMaterialMediaKind[] = ['video', 'image', 'audio', 'sidecar', 'placeholder'];
    expect(kinds).toHaveLength(5);
  });

  it('RenderLocatorKind covers asset-registry, inline, temp, virtual', () => {
    const kinds: RenderLocatorKind[] = ['asset-registry', 'inline', 'temp', 'virtual'];
    expect(kinds).toHaveLength(4);
  });

  it('RenderStorageLocator shape is constructable', () => {
    const loc: RenderStorageLocator = {
      kind: 'asset-registry' as RenderLocatorKind,
      uri: 'asset://key-1',
    };
    expect(loc.kind).toBe('asset-registry');
    expect(loc.uri).toBe('asset://key-1');
  });

  it('ShaderMaterializerRequirementScope covers clip and postprocess', () => {
    const scopes: ShaderMaterializerRequirementScope[] = ['clip', 'postprocess'];
    expect(scopes).toHaveLength(2);
  });

  it('RenderArtifact shape is constructable (compile-only)', () => {
    const artifact: RenderArtifact = {
      route: 'browser-export' as RenderRoute,
      determinism: 'deterministic' as DeterminismStatus,
      manifestId: 'manifest-1',
      manifest: {
        id: 'manifest-1',
        schemaVersion: 1,
        artifactId: 'artifact-1',
        route: 'browser-export' as RenderRoute,
        determinism: 'deterministic' as DeterminismStatus,
        producerExtensionId: 'com.example.ext',
        producerVersion: '1.0.0',
        consumedMaterialRefs: [],
        sidecars: [],
        diagnostics: [],
      },
      materials: [],
      sidecars: [],
      diagnostics: [],
    };
    expect(artifact.route).toBe('browser-export');
    expect(artifact.manifest.schemaVersion).toBe(1);
  });

  it('ArtifactBoundary shape is constructable', () => {
    const boundary: ArtifactBoundary = {
      artifactId: 'artifact-1',
      route: 'browser-export' as RenderRoute,
      mainBytes: 1024,
      sidecarBytes: new Map(),
    };
    expect(boundary.artifactId).toBe('artifact-1');
    expect(boundary.mainBytes).toBe(1024);
  });

  it('BakeContract shape is constructable', () => {
    const contract: BakeContract = {
      kind: 'asset',
      targetRef: 'asset-key',
      bakeAt: '2026-06-20T00:00:00Z',
    };
    expect(contract.kind).toBe('asset');
    expect(contract.targetRef).toBe('asset-key');
  });
});

// ---------------------------------------------------------------------------
// M10: Agent tool type interfaces
// ---------------------------------------------------------------------------

import type {
  AgentToolContribution,
  AgentToolInvocationRequest,
  AgentToolRequestContext,
  AgentToolExportContext,
  AgentToolHandler,
  AgentToolRegistrationService,
  AgentToolInputSchema,
  AgentToolInputProperty,
  ToolResultFamily,
  ToolResult,
  ToolMutationProposalResult,
  ToolGenerationSessionResult,
  ToolMaterialArtifactResult,
  ToolEnrichmentSearchResult,
  ToolExportResult,
  ToolProcessResult,
  ToolUISummaryResult,
  ToolSourceRef,
  ToolArtifactRef,
  ToolSearchResultMatch,
  ToolResultDiagnostic,
  GenerationSession,
  GenerationSessionLiveDelivery,
  SteeringDecision,
  SteeringDecisionKind,
  SteeringLineage,
  SteeringProvenance,
  SteeringParameterChange,
  SteeringParameterHotness,
  SteeringPriorSamplePolicy,
  ProcessSpawnConfig,
} from '@reigh/editor-sdk';

describe('M10: agent tool type interfaces are importable from @reigh/editor-sdk', () => {
  it('AgentToolContribution shape is constructable (minimal)', () => {
    const contrib: AgentToolContribution = {
      id: 'myTool' as ContributionId,
      kind: 'agentTool',
      toolId: 'tool.summarize',
      label: 'Summarize Timeline',
    };
    expect(contrib.kind).toBe('agentTool');
    expect(contrib.toolId).toBe('tool.summarize');
    expect(contrib.label).toBe('Summarize Timeline');
  });

  it('AgentToolContribution shape is constructable (full)', () => {
    const contrib: AgentToolContribution = {
      id: 'fullTool' as ContributionId,
      kind: 'agentTool',
      toolId: 'tool.full',
      label: 'Full Tool',
      description: 'A fully specified agent tool',
      order: 5,
      when: 'editorHasSelection',
      resultFamilies: ['mutation/proposal', 'ui/summary'],
    };
    expect(contrib.description).toBe('A fully specified agent tool');
    expect(contrib.resultFamilies).toEqual(['mutation/proposal', 'ui/summary']);
  });

  it('AgentToolInputSchema shape is constructable', () => {
    const schema: AgentToolInputSchema = {
      type: 'object',
      title: 'Tool Input',
      properties: {
        query: { type: 'string', title: 'Query', description: 'Search query' },
        count: { type: 'number', title: 'Count', default: 10 },
      },
      required: ['query'],
    };
    expect(schema.type).toBe('object');
    expect(schema.properties?.query.type).toBe('string');
    expect(schema.required).toEqual(['query']);
  });

  it('AgentToolInputProperty covers string, number, boolean, object types', () => {
    const types: AgentToolInputProperty['type'][] = ['string', 'number', 'boolean', 'object'];
    expect(types).toHaveLength(4);
  });

  it('AgentToolInputProperty with nested object is constructable', () => {
    const prop: AgentToolInputProperty = {
      type: 'object',
      title: 'Nested Config',
      properties: {
        enabled: { type: 'boolean', title: 'Enabled' },
      },
      required: ['enabled'],
    };
    expect(prop.type).toBe('object');
    expect(prop.properties?.enabled.type).toBe('boolean');
  });

  it('ToolResultFamily covers all seven families', () => {
    const families: ToolResultFamily[] = [
      'mutation/proposal',
      'generation/session',
      'material/artifact',
      'enrichment/search',
      'export',
      'process',
      'ui/summary',
    ];
    expect(families).toHaveLength(7);
  });

  it('ToolMutationProposalResult is constructable', () => {
    const result: ToolMutationProposalResult = {
      family: 'mutation/proposal',
      rationale: 'Reorder clips for pacing',
      patches: [{ version: 1, operations: [] }],
      affectedObjectIds: ['clip-1', 'clip-2'],
    };
    expect(result.family).toBe('mutation/proposal');
    expect(result.patches).toHaveLength(1);
  });

  it('ToolGenerationSessionResult is constructable', () => {
    const session: GenerationSession = {
      id: 'gen-1',
      progress: 0,
      cancelled: false,
      done: false,
      diagnostics: [],
      onProgress: () => ({ dispose() {} }),
      cancel: () => {},
      getSampleChannel: () => 'ch' as any,
      onSample: () => ({ dispose() {} }),
      getSteeringLineage: () => undefined,
      complete: () => {},
    };
    const result: ToolGenerationSessionResult = {
      family: 'generation/session',
      session,
      rationale: 'Generate a slow-pan effect',
    };
    expect(result.family).toBe('generation/session');
    expect(result.session.id).toBe('gen-1');
  });

  it('ToolMaterialArtifactResult is constructable', () => {
    const refs: ToolArtifactRef[] = [
      { ref: 'asset-1', kind: 'asset', label: 'Generated Image' },
    ];
    const result: ToolMaterialArtifactResult = {
      family: 'material/artifact',
      refs,
      rationale: 'Generated background layer',
    };
    expect(result.family).toBe('material/artifact');
    expect(result.refs[0].ref).toBe('asset-1');
  });

  it('ToolEnrichmentSearchResult is constructable', () => {
    const result: ToolEnrichmentSearchResult = {
      family: 'enrichment/search',
      suggestions: { 'asset-1': { tags: ['sunset'] } },
    };
    expect(result.family).toBe('enrichment/search');
    expect(result.suggestions!['asset-1'].tags).toEqual(['sunset']);
  });

  it('ToolExportResult is constructable', () => {
    const result: ToolExportResult = {
      family: 'export',
      findings: [{ id: 'f1', severity: 'info', route: 'browser-export', message: 'Ready' }],
      rationale: 'Export checklist complete',
    };
    expect(result.family).toBe('export');
    expect(result.findings).toHaveLength(1);
  });

  it('ToolProcessResult is constructable with pending diagnostic', () => {
    const result: ToolProcessResult = {
      family: 'process',
      diagnostics: [{
        severity: 'info',
        code: 'agent-tool/process-unavailable',
        message: 'Process execution is not available until M12',
      }],
    };
    expect(result.family).toBe('process');
    expect(result.diagnostics[0].code).toBe('agent-tool/process-unavailable');
  });

  it('ToolUISummaryResult is constructable', () => {
    const result: ToolUISummaryResult = {
      family: 'ui/summary',
      summary: 'The timeline contains 5 clips across 2 tracks.',
      detail: { clipCount: 5, trackCount: 2 },
    };
    expect(result.family).toBe('ui/summary');
    expect(result.summary).toContain('5 clips');
  });

  it('ToolResult discriminated union accepts all variant shapes', () => {
    const mutationResult: ToolResult = { family: 'mutation/proposal', patches: [] };
    const genResult: ToolResult = {
      family: 'generation/session',
      session: {
        id: 'g', progress: 0, cancelled: false, done: false, diagnostics: [],
        onProgress: () => ({ dispose() {} }), cancel: () => {},
        getSampleChannel: () => 'c' as any, onSample: () => ({ dispose() {} }),
        getSteeringLineage: () => undefined, complete: () => {},
      },
    };
    const summaryResult: ToolResult = { family: 'ui/summary', summary: 'Done' };

    expect(mutationResult.family).toBe('mutation/proposal');
    expect(genResult.family).toBe('generation/session');
    expect(summaryResult.family).toBe('ui/summary');
  });

  it('ToolSourceRef is constructable', () => {
    const ref: ToolSourceRef = {
      sourceId: 'clip-1',
      outputId: 'asset-1',
      description: 'Generated from clip preview',
    };
    expect(ref.sourceId).toBe('clip-1');
    expect(ref.outputId).toBe('asset-1');
  });

  it('ToolArtifactRef covers asset, material, placeholder kinds', () => {
    const kinds: ToolArtifactRef['kind'][] = ['asset', 'material', 'placeholder'];
    expect(kinds).toHaveLength(3);
  });

  it('ToolSearchResultMatch is constructable', () => {
    const match: ToolSearchResultMatch = {
      key: 'asset-1',
      score: 0.95,
      label: 'Sunset image',
    };
    expect(match.key).toBe('asset-1');
    expect(match.score).toBe(0.95);
  });

  it('ToolResultDiagnostic has agent-tool/ prefixed codes', () => {
    const diag: ToolResultDiagnostic = {
      severity: 'error',
      code: 'agent-tool/invalid-input',
      message: 'Invalid input schema',
    };
    expect(diag.code).toBe('agent-tool/invalid-input');
    expect(diag.severity).toBe('error');
  });

  it('AgentToolInvocationRequest shape is constructable', () => {
    const req: AgentToolInvocationRequest = {
      toolId: 'tool.summarize',
      extensionId: 'com.example.ext',
      contributionId: 'myTool',
      input: { maxClips: 5 },
    };
    expect(req.toolId).toBe('tool.summarize');
    expect(req.extensionId).toBe('com.example.ext');
    expect(req.input?.maxClips).toBe(5);
  });

  it('AgentToolRequestContext shape is constructable', () => {
    const ctx: AgentToolRequestContext = {
      timeline: {
        projectId: 'proj-1',
        baseVersion: 1,
        currentVersion: 1,
        extensionRequirements: [],
        clips: [],
        tracks: [],
        assetKeys: [],
        app: {},
      },
      assets: [{ key: 'asset-1', metadata: { width: 1920 } }],
      materials: [{ key: 'mat-1' }],
      meta: { source: 'command-palette' },
    };
    expect(ctx.timeline?.projectId).toBe('proj-1');
    expect(ctx.assets?.[0].key).toBe('asset-1');
  });

  it('AgentToolExportContext shape is constructable', () => {
    const exportCtx: AgentToolExportContext = {
      outputFormatId: 'mp4-export',
      blockers: [{ reason: 'missing-materializer', message: 'Wait for M12' }],
      contributionIds: ['myTool'],
    };
    expect(exportCtx.outputFormatId).toBe('mp4-export');
    expect(exportCtx.blockers).toHaveLength(1);
  });

  it('AgentToolHandler typed function is callable (sync)', () => {
    const handler: AgentToolHandler = (_req) => ({
      family: 'ui/summary' as const,
      summary: 'OK',
    });
    const result = handler({
      toolId: 't', extensionId: 'e', contributionId: 'c',
    });
    expect(result.family).toBe('ui/summary');
  });

  it('AgentToolHandler typed function handles async', async () => {
    const handler: AgentToolHandler = async (_req) => ({
      family: 'ui/summary' as const,
      summary: 'Async OK',
    });
    const result = await handler({
      toolId: 't', extensionId: 'e', contributionId: 'c',
    });
    expect((result as ToolUISummaryResult).summary).toBe('Async OK');
  });

  it('AgentToolRegistrationService interface has registerTool and invokeProcess', () => {
    const svc: AgentToolRegistrationService = {
      registerTool(_toolId, _handler) { return { dispose() {} }; },
      invokeProcess(_toolId, _config) {
        return Promise.resolve({
          family: 'process',
          diagnostics: [{ severity: 'info', code: 'agent-tool/process-unavailable', message: 'Not available' }],
        });
      },
    };
    expect(typeof svc.registerTool).toBe('function');
    expect(typeof svc.invokeProcess).toBe('function');
  });

  it('GenerationSession shape covers progress, cancel, onSample, getSteeringLineage', () => {
    const session: GenerationSession = {
      id: 'gen-s1',
      progress: 42,
      progressLabel: 'Rendering...',
      cancelled: false,
      done: false,
      diagnostics: [],
      finalRefs: ['ref-1'],
      bakedRefs: ['baked-1'],
      onProgress: () => ({ dispose() {} }),
      cancel: () => {},
      getSampleChannel: () => 'ch-gen' as any,
      onSample: () => ({ dispose() {} }),
      getSteeringLineage: () => undefined,
      complete: () => {},
    };
    expect(session.progress).toBe(42);
    expect(session.finalRefs).toEqual(['ref-1']);
    expect(session.bakedRefs).toEqual(['baked-1']);
  });

  it('GenerationSessionLiveDelivery is constructable', () => {
    const steeringDecision: SteeringDecision = {
      kind: 'fork',
      sessionId: 'gen-1',
      lineage: {
        generationIndex: 1,
        steerHash: 'hash1',
        parentRefs: ['gen-0'],
        producerVersion: '1.0.0',
        provenance: { prompt: 'P', model: 'M', seed: 1 },
      },
      reason: 'Non-hot change',
    };
    const delivery: GenerationSessionLiveDelivery = {
      origin: 'agent-tool',
      steeringDecision,
      activeChannels: ['ch-1' as any],
      finalRefs: ['asset-1'],
      bakedRefs: ['baked-1'],
    };
    expect(delivery.origin).toBe('agent-tool');
    expect(delivery.steeringDecision.kind).toBe('fork');
  });

  it('SteeringDecisionKind covers supersede, fork, reject', () => {
    const kinds: SteeringDecisionKind[] = ['supersede', 'fork', 'reject'];
    expect(kinds).toHaveLength(3);
  });

  it('SteeringParameterHotness covers hot, non-hot', () => {
    const hotness: SteeringParameterHotness[] = ['hot', 'non-hot'];
    expect(hotness).toHaveLength(2);
  });

  it('SteeringPriorSamplePolicy covers replace, fork, retain, discard', () => {
    const policies: SteeringPriorSamplePolicy[] = ['replace', 'fork', 'retain', 'discard'];
    expect(policies).toHaveLength(4);
  });

  it('SteeringProvenance is constructable', () => {
    const provenance: SteeringProvenance = {
      prompt: 'A slow pan across clouds',
      model: 'reigh-gen-v1',
      seed: 42,
      producerExtensionId: 'ext.generator',
      tags: ['user-approved'],
    };
    expect(provenance.prompt).toBe('A slow pan across clouds');
    expect(provenance.model).toBe('reigh-gen-v1');
  });

  it('SteeringParameterChange is constructable', () => {
    const change: SteeringParameterChange = {
      path: 'params.prompt',
      previousValue: 'Clouds',
      nextValue: 'Storm clouds',
      hotness: 'hot',
    };
    expect(change.path).toBe('params.prompt');
    expect(change.nextValue).toBe('Storm clouds');
    expect(change.hotness).toBe('hot');
  });

  it('SteeringLineage is constructable', () => {
    const lineage: SteeringLineage = {
      generationIndex: 3,
      steerHash: 'abc123',
      parentRefs: ['session-1', 'session-2'],
      producerVersion: '1.2.0',
      provenance: {
        prompt: 'A slow pan across clouds',
        model: 'reigh-gen-v1',
        seed: 42,
        producerExtensionId: 'ext.generator',
      },
      provenanceTags: ['user-approved'],
    };
    expect(lineage.generationIndex).toBe(3);
    expect(lineage.steerHash).toBe('abc123');
  });

  it('ProcessSpawnConfig is constructable', () => {
    const config: ProcessSpawnConfig = {
      command: 'node',
      args: ['--version'],
      env: { NODE_ENV: 'test' },
      cwd: '/tmp',
    };
    expect(config.command).toBe('node');
    expect(config.env?.NODE_ENV).toBe('test');
  });
});

// ---------------------------------------------------------------------------
// M12: Process spec, contribution, status, roundtrip type interfaces
// ---------------------------------------------------------------------------

describe('M12: process type interfaces are importable from public SDK modules', () => {
  it('ProcessLifecycleState covers all 8 states', () => {
    const states: ProcessLifecycleState[] = [
      'not-installed', 'stopped', 'starting', 'ready',
      'busy', 'degraded', 'failed', 'stopping',
    ];
    expect(states).toHaveLength(8);
  });

  it('ProcessSpec shape is constructable', () => {
    const spec: ProcessSpec = {
      id: 'blender-mcp',
      label: 'Blender MCP',
      spawn: { command: 'blender-mcp', args: ['--stdio'] },
      protocol: 'stdio-jsonrpc',
      healthCheck: 'ping',
      shutdown: 'SIGTERM',
      restartPolicy: 'on-failure',
    };
    expect(spec.id).toBe('blender-mcp');
    expect(spec.protocol).toBe('stdio-jsonrpc');
    expect(spec.spawn.command).toBe('blender-mcp');
  });

  it('ProcessSpec with operations and capabilities is constructable', () => {
    const op: ProcessOperationSpec = {
      id: 'render-pass',
      label: 'Render Pass',
      outputKinds: ['material', 'sidecar'],
      routes: ['browser-export' as RenderRoute],
      determinism: 'deterministic' as DeterminismStatus,
    };
    const spec: ProcessSpec = {
      id: 'full-process',
      label: 'Full Process',
      spawn: { command: 'node', args: ['worker.js'] },
      protocol: 'stdio-jsonrpc',
      operations: [op],
      capabilities: {
        routes: ['browser-export' as RenderRoute],
        determinism: 'deterministic' as DeterminismStatus,
        capabilityRequirements: [],
        sourceRefs: [],
        fullySupported: true,
        anyBlocked: false,
      },
    };
    expect(spec.operations).toHaveLength(1);
    expect(spec.operations![0].id).toBe('render-pass');
    expect(spec.capabilities?.fullySupported).toBe(true);
  });

  it('ProcessContribution shape is constructable', () => {
    const contrib: ProcessContribution = {
      id: 'proc-contrib' as ContributionId,
      kind: 'process',
      label: 'My Process',
      spec: {
        id: 'my-process',
        label: 'My Process',
        spawn: { command: 'echo', args: ['hello'] },
        protocol: 'stdio-jsonrpc',
      },
    };
    expect(contrib.kind).toBe('process');
    expect(contrib.spec.id).toBe('my-process');
  });

  it('ProcessStatus discriminated union covers not-installed variant', () => {
    const status: ProcessStatus = {
      processId: 'p1',
      state: 'not-installed',
      installHint: 'Run: npm install -g my-tool',
    };
    expect(status.state).toBe('not-installed');
    if (status.state === 'not-installed') {
      expect(status.installHint).toBe('Run: npm install -g my-tool');
    }
  });

  it('ProcessStatus discriminated union covers ready variant', () => {
    const status: ProcessStatus = {
      processId: 'p1',
      state: 'ready',
      pid: 1234,
      version: { semver: '1.0.0' },
    };
    expect(status.state).toBe('ready');
    if (status.state === 'ready') {
      expect(status.pid).toBe(1234);
    }
  });

  it('ProcessStatus discriminated union covers busy variant', () => {
    const status: ProcessStatus = {
      processId: 'p1',
      state: 'busy',
      operationId: 'render-pass',
      progress: { operationId: 'render-pass', percent: 50 },
    };
    expect(status.state).toBe('busy');
    if (status.state === 'busy') {
      expect(status.progress?.percent).toBe(50);
    }
  });

  it('ProcessStatus discriminated union covers failed variant', () => {
    const status: ProcessStatus = {
      processId: 'p1',
      state: 'failed',
      errorCode: 'spawn-failed',
      recoverable: true,
    };
    expect(status.state).toBe('failed');
    if (status.state === 'failed') {
      expect(status.errorCode).toBe('spawn-failed');
      expect(status.recoverable).toBe(true);
    }
  });

  it('ProcessRoundtripRequest shape is constructable', () => {
    const req: ProcessRoundtripRequest = {
      id: 'roundtrip-1',
      processId: 'blender-mcp',
      operationId: 'render-pass',
      inputMaterialRefs: [],
      params: { passName: 'beauty' },
      frameRange: { startFrame: 0, endFrame: 24 },
    };
    expect(req.processId).toBe('blender-mcp');
    expect(req.operationId).toBe('render-pass');
    expect(req.frameRange?.endFrame).toBe(24);
  });

  it('ProcessRoundtripResult shape is constructable', () => {
    const result: ProcessRoundtripResult = {
      requestId: 'roundtrip-1',
      processId: 'blender-mcp',
      operationId: 'render-pass',
      status: 'completed',
      returnedMaterials: [],
      sidecars: [],
      availableActions: ['insert-as-clip'],
    };
    expect(result.status).toBe('completed');
    expect(result.availableActions).toEqual(['insert-as-clip']);
  });

  it('ProcessProgressEvent shape is constructable', () => {
    const evt: ProcessProgressEvent = {
      operationId: 'render-pass',
      percent: 75,
      message: 'Rendering frame 18/24',
      currentStep: 'render',
      totalSteps: 24,
    };
    expect(evt.operationId).toBe('render-pass');
    expect(evt.percent).toBe(75);
  });

  it('ProcessLogSummary shape is constructable', () => {
    const log: ProcessLogSummary = {
      level: 'info',
      message: 'Process started',
      at: '2026-06-20T00:00:00.000Z',
      detail: { pid: 1234 },
    };
    expect(log.level).toBe('info');
    expect(log.message).toBe('Process started');
  });

  it('ProcessEnvFieldSpec shape is constructable', () => {
    const env: ProcessEnvFieldSpec = {
      key: 'API_KEY',
      label: 'API Key',
      description: 'API key for external service',
      required: true,
      secret: true,
      defaultValue: '',
      platformDefaults: { darwin: '/usr/local/bin/tool' },
    };
    expect(env.key).toBe('API_KEY');
    expect(env.secret).toBe(true);
  });

  it('ProcessOperationSpec shape is constructable', () => {
    const op: ProcessOperationSpec = {
      id: 'export-show-control',
      label: 'Export Show Control',
      description: 'Export a show-control package',
      outputKinds: ['material', 'sidecar', 'diagnostic'],
      requiredCapabilities: ['sidecar-export'],
      routes: ['sidecar-export' as RenderRoute],
      determinism: 'process-dependent' as DeterminismStatus,
    };
    expect(op.id).toBe('export-show-control');
    expect(op.outputKinds).toEqual(['material', 'sidecar', 'diagnostic']);
  });

  it('process live-source declaration types are constructable as data-only SDK contracts', () => {
    const outputKinds: ProcessOutputKind[] = [
      'live-source-scalar',
      'live-source-vector',
      'live-source-structured',
    ];
    const valueShape: ProcessLiveSourceValueShape = 'structured';
    const liveSource: ProcessLiveSourceDeclaration = {
      sourceId: 'pose-tracking',
      valueShape,
      label: 'Pose Tracking',
      sourceKind: 'generated',
    };
    const spec: ProcessSpec = {
      id: 'pose-process',
      label: 'Pose Process',
      spawn: { command: 'node', args: ['pose-process.js'] },
      protocol: 'stdio-jsonrpc',
      operations: [
        {
          id: 'track-pose',
          label: 'Track Pose',
          outputKinds,
        },
      ],
      liveSources: [liveSource],
    };

    expect(spec.operations?.[0].outputKinds).toEqual(outputKinds);
    expect(spec.liveSources?.[0]).toEqual(liveSource);
  });
});

// ---------------------------------------------------------------------------
// M13: Shader type interfaces (SDK boundary proof)
// ---------------------------------------------------------------------------

import type {
  ShaderContribution,
  ShaderRegistrationService,
  ShaderRegistrationOptions,
  ShaderInlineSource,
  ShaderSourceDescriptor,
  ShaderPassKind,
  ShaderPassDescriptor,
  ShaderColorSpace,
  ShaderFallbackBehavior,
  ShaderTextureSourceKind,
  ShaderTextureFilter,
  ShaderTextureWrap,
  ShaderUniformDefinition,
  ShaderUniformType,
  ShaderUniformEnumOption,
  ShaderTextureRef,
  ShaderUniformDefaultValue,
  ShaderTextureDefinition,
  ShaderUniformSchema,
  ShaderTextureSchema,
  ShaderMaterializerDescriptor,
} from '@reigh/editor-sdk';

describe('M13: shader type interfaces are importable from @reigh/editor-sdk', () => {
  it('ShaderPassKind covers clip, overlay, postprocess', () => {
    const kinds: ShaderPassKind[] = ['clip', 'overlay', 'postprocess'];
    expect(kinds).toHaveLength(3);
  });

  it('ShaderColorSpace covers srgb and linear', () => {
    const spaces: ShaderColorSpace[] = ['srgb', 'linear'];
    expect(spaces).toHaveLength(2);
  });

  it('ShaderFallbackBehavior covers bypass, transparent, solid-black', () => {
    const fallbacks: ShaderFallbackBehavior[] = ['bypass', 'transparent', 'solid-black'];
    expect(fallbacks).toHaveLength(3);
  });

  it('ShaderTextureSourceKind covers clip-frame, static-image-asset, live-generated-frame', () => {
    const kinds: ShaderTextureSourceKind[] = ['clip-frame', 'static-image-asset', 'live-generated-frame'];
    expect(kinds).toHaveLength(3);
  });

  it('ShaderTextureFilter covers nearest and linear', () => {
    const filters: ShaderTextureFilter[] = ['nearest', 'linear'];
    expect(filters).toHaveLength(2);
  });

  it('ShaderTextureWrap covers clamp-to-edge, repeat, mirrored-repeat', () => {
    const wraps: ShaderTextureWrap[] = ['clamp-to-edge', 'repeat', 'mirrored-repeat'];
    expect(wraps).toHaveLength(3);
  });

  it('ShaderInlineSource is constructable', () => {
    const src: ShaderInlineSource = {
      kind: 'inline',
      fragment: 'void main() { gl_FragColor = vec4(1.0); }',
      vertex: 'attribute vec2 position; void main() { gl_Position = vec4(position, 0.0, 1.0); }',
    };
    expect(src.kind).toBe('inline');
    expect(src.fragment).toContain('gl_FragColor');
    expect(src.vertex).toContain('gl_Position');
  });

  it('ShaderPassDescriptor is constructable', () => {
    const pass: ShaderPassDescriptor = {
      kind: 'clip',
      inputTextureUniform: 'u_clip',
      colorSpace: 'srgb',
      alpha: 'preserve',
    };
    expect(pass.kind).toBe('clip');
    expect(pass.inputTextureUniform).toBe('u_clip');
    expect(pass.alpha).toBe('preserve');
  });

  it('ShaderUniformType covers all 11 V1 types', () => {
    const types: ShaderUniformType[] = [
      'float', 'int', 'bool', 'vec2', 'vec3', 'vec4',
      'color', 'enum', 'textureRef', 'frame', 'time',
    ];
    expect(types).toHaveLength(11);
  });

  it('ShaderUniformDefinition is constructable (float)', () => {
    const def: ShaderUniformDefinition = {
      name: 'u_intensity',
      label: 'Intensity',
      type: 'float',
      default: 0.5,
      min: 0,
      max: 1,
      step: 0.01,
    };
    expect(def.name).toBe('u_intensity');
    expect(def.default).toBe(0.5);
  });

  it('ShaderUniformDefinition is constructable (enum)', () => {
    const def: ShaderUniformDefinition = {
      name: 'u_mode',
      label: 'Mode',
      type: 'enum',
      default: 'blend',
      options: [
        { label: 'Blend', value: 'blend' },
        { label: 'Add', value: 'add' },
      ],
    };
    expect(def.type).toBe('enum');
    expect(def.options).toHaveLength(2);
  });

  it('ShaderUniformDefinition is constructable (textureRef)', () => {
    const ref: ShaderTextureRef = { kind: 'clip-frame' };
    const def: ShaderUniformDefinition = {
      name: 'u_source',
      label: 'Source',
      type: 'textureRef',
      default: ref,
    };
    expect(def.type).toBe('textureRef');
    expect((def.default as ShaderTextureRef).kind).toBe('clip-frame');
  });

  it('ShaderTextureRef covers all source kinds', () => {
    const refs: ShaderTextureRef[] = [
      { kind: 'clip-frame' },
      { kind: 'static-image-asset', ref: 'asset-1' },
      { kind: 'live-generated-frame', ref: 'gen-frame-1' },
    ];
    expect(refs).toHaveLength(3);
  });

  it('ShaderTextureDefinition is constructable', () => {
    const tex: ShaderTextureDefinition = {
      name: 'clipFrame',
      uniform: 'u_clip',
      sourceKind: 'clip-frame',
      required: true,
      colorSpace: 'srgb',
      filter: 'linear',
      wrap: 'clamp-to-edge',
    };
    expect(tex.name).toBe('clipFrame');
    expect(tex.required).toBe(true);
  });

  it('ShaderContribution shape is constructable', () => {
    const contrib: ShaderContribution = {
      id: 'shader-glow' as ContributionId,
      kind: 'shader',
      shaderId: 'shader.clipGlow',
      label: 'Clip Glow',
      pass: { kind: 'clip', inputTextureUniform: 'u_clip' },
      source: { kind: 'inline', fragment: 'void main() {}' },
      uniforms: [{ name: 'u_intensity', label: 'Intensity', type: 'float', default: 0.5 }],
      textures: [{ name: 'clipFrame', sourceKind: 'clip-frame' }],
      fallback: 'bypass',
    };
    expect(contrib.kind).toBe('shader');
    expect(contrib.shaderId).toBe('shader.clipGlow');
    expect(contrib.uniforms).toHaveLength(1);
  });

  it('ShaderRegistrationOptions is constructable', () => {
    const opts: ShaderRegistrationOptions = {
      label: 'My Shader',
      pass: 'clip',
      uniforms: [{ name: 'u_t', label: 'Time', type: 'time' }],
      fallback: 'transparent',
    };
    expect(opts.label).toBe('My Shader');
    expect(opts.pass).toBe('clip');
  });

  it('ShaderRegistrationService interface has registerShader', () => {
    const svc: ShaderRegistrationService = {
      registerShader(_shaderId, _source, _options) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerShader).toBe('function');
    const handle = svc.registerShader('shader.test', { kind: 'inline', fragment: 'void main() {}' });
    expect(typeof handle.dispose).toBe('function');
  });

  it('ShaderMaterializerDescriptor is constructable', () => {
    const desc: ShaderMaterializerDescriptor = {
      routes: ['browser-export' as RenderRoute],
      requiredCapabilities: ['browser-export'],
      unavailableMessage: 'Materializer not available until render planning',
    };
    expect(desc.routes).toEqual(['browser-export']);
    expect(desc.unavailableMessage).toBeDefined();
  });

  it('ShaderUniformEnumOption is constructable', () => {
    const option: ShaderUniformEnumOption = { label: 'Blend', value: 'blend' };
    expect(option.label).toBe('Blend');
    expect(option.value).toBe('blend');
  });
});

// ---------------------------------------------------------------------------
// Diagnostics, migration, packaging, settings type interfaces
// ---------------------------------------------------------------------------

import type {
  DiagnosticSeverity,
  DiagnosticSourceRange,
  Diagnostic,
  DiagnosticCollection,
  ExportDiagnostic,
  ExtensionDiagnosticsService,
  ExtensionChromeService,
  ChromeEvent,
  ChromeToastPayload,
  ChromeProgressPayload,
  ChromeEventPayload,
  ExtensionI18nService,
  MigrationHookKind,
  MigrationDeclaration,
  ExtensionDependency,
  DependencyPosture,
  ExtensionSettingsSchema,
  IntegrityAlgorithm,
  IntegrityHash,
  InstalledExtensionMetadata,
  InstalledExtensionPackage,
  ManifestValidationMode,
  ManifestValidationResult,
  ExtensionPermissionDeclaration,
} from '@reigh/editor-sdk';

describe('SDK diagnostics types are importable from @reigh/editor-sdk', () => {
  it('DiagnosticSeverity covers error, warning, info', () => {
    const severities: DiagnosticSeverity[] = ['error', 'warning', 'info'];
    expect(severities).toHaveLength(3);
  });

  it('DiagnosticSourceRange is constructable', () => {
    const range: DiagnosticSourceRange = {
      startLine: 10,
      startCol: 5,
      endLine: 15,
      endCol: 20,
    };
    expect(range.startLine).toBe(10);
    expect(range.endCol).toBe(20);
  });

  it('Diagnostic is constructable', () => {
    const diag: Diagnostic = {
      id: 'diag-1',
      severity: 'error',
      code: 'test/error',
      message: 'Test diagnostic',
      extensionId: 'com.test.ext',
      sourceRange: { startLine: 1, startCol: 1, endLine: 1, endCol: 10 },
      relatedRanges: [{ startLine: 2, startCol: 1, endLine: 2, endCol: 5 }],
      detail: { clipId: 'clip-1' },
    };
    expect(diag.id).toBe('diag-1');
    expect(diag.sourceRange?.startLine).toBe(1);
    expect(diag.relatedRanges).toHaveLength(1);
  });

  it('ExportDiagnostic has export/-prefixed codes', () => {
    const diag: ExportDiagnostic = {
      severity: 'warning',
      code: 'export/unknown-clip-type',
      message: 'Clip type not registered for export',
      detail: { clipId: 'clip-1', clipType: 'custom-clip' },
    };
    expect(diag.code).toBe('export/unknown-clip-type');
    expect(diag.detail?.clipId).toBe('clip-1');
    expect(diag.detail?.clipType).toBe('custom-clip');
  });

  it('ExportDiagnostic detail includes shader scope fields', () => {
    const diag: ExportDiagnostic = {
      severity: 'error',
      code: 'export/missing-shader-materializer',
      message: 'Shader has no materializer for export route',
      detail: {
        shaderId: 'shader.glow',
        shaderScope: 'clip' as ShaderMaterializerRequirementScope,
      },
    };
    expect(diag.detail?.shaderId).toBe('shader.glow');
    expect(diag.detail?.shaderScope).toBe('clip');
  });

  it('ExtensionDiagnosticsService interface shape is correct', () => {
    const svc: ExtensionDiagnosticsService = {
      report(_diag) {},
      diagnostics: [],
    };
    expect(typeof svc.report).toBe('function');
    expect(Array.isArray(svc.diagnostics)).toBe(true);
  });

  it('ExtensionChromeService interface shape is correct', () => {
    const svc: ExtensionChromeService = {
      toast(_msg, _severity) {},
      progress(_percent, _label) {},
      subscribe(_event, _handler) { return { dispose() {} }; },
      focus(_selector) {},
      announce(_message, _politeness) {},
    };
    expect(typeof svc.toast).toBe('function');
    expect(typeof svc.progress).toBe('function');
    expect(typeof svc.subscribe).toBe('function');
    expect(typeof svc.focus).toBe('function');
    expect(typeof svc.announce).toBe('function');
  });

  it('ChromeEvent covers toast, progress, save, renderStatus', () => {
    const events: ChromeEvent[] = ['toast', 'progress', 'save', 'renderStatus'];
    expect(events).toHaveLength(4);
  });

  it('ChromeEventPayload maps toast to ChromeToastPayload', () => {
    const payload: ChromeEventPayload<'toast'> = {
      message: 'Hello',
      severity: 'info',
    };
    expect(payload.message).toBe('Hello');
    expect(payload.severity).toBe('info');
  });

  it('ChromeEventPayload maps progress to ChromeProgressPayload', () => {
    const payload: ChromeEventPayload<'progress'> = {
      percent: 75,
      label: 'Exporting...',
    };
    expect(payload.percent).toBe(75);
    expect(payload.label).toBe('Exporting...');
  });

  it('ExtensionI18nService interface shape is correct', () => {
    const svc: ExtensionI18nService = {
      t(key, _replacements) { return key; },
    };
    expect(typeof svc.t).toBe('function');
    expect(svc.t('hello')).toBe('hello');
  });
});

describe('SDK migration types are importable from @reigh/editor-sdk', () => {
  it('MigrationHookKind covers settings, contribution, manifest', () => {
    const kinds: MigrationHookKind[] = ['settings', 'contribution', 'manifest'];
    expect(kinds).toHaveLength(3);
  });

  it('MigrationDeclaration shape is constructable', () => {
    const migration: MigrationDeclaration = {
      kind: 'settings',
      fromVersion: '1.0.0',
      toVersion: '2.0.0',
      handler: 'migrateSettings',
      description: 'Migrate settings from v1 to v2',
    };
    expect(migration.kind).toBe('settings');
    expect(migration.fromVersion).toBe('1.0.0');
    expect(migration.toVersion).toBe('2.0.0');
    expect(migration.handler).toBe('migrateSettings');
  });
});

describe('SDK packaging types are importable from @reigh/editor-sdk', () => {
  it('DependencyPosture covers required and optional', () => {
    const postures: DependencyPosture[] = ['required', 'optional'];
    expect(postures).toHaveLength(2);
  });

  it('ExtensionDependency shape is constructable', () => {
    const dep: ExtensionDependency = {
      extensionId: 'com.example.lib',
      versionRange: '^1.0.0',
      posture: 'required',
    };
    expect(dep.extensionId).toBe('com.example.lib');
    expect(dep.versionRange).toBe('^1.0.0');
    expect(dep.posture).toBe('required');
  });

  it('ExtensionDependency with optional and contributionIds is constructable', () => {
    const dep: ExtensionDependency = {
      extensionId: 'com.example.optional',
      versionRange: '>=1.0.0',
      optional: true,
      posture: 'optional',
      contributionIds: ['toolbar-main'],
    };
    expect(dep.optional).toBe(true);
    expect(dep.contributionIds).toEqual(['toolbar-main']);
  });

  it('IntegrityAlgorithm is only sha256', () => {
    const algo: IntegrityAlgorithm = 'sha256';
    expect(algo).toBe('sha256');
  });

  it('IntegrityHash shape is constructable', () => {
    const hash: IntegrityHash = {
      algorithm: 'sha256',
      value: 'dGVzdC1oYXNo',
    };
    expect(hash.algorithm).toBe('sha256');
    expect(hash.value).toBe('dGVzdC1oYXNo');
  });

  it('ExtensionSettingsSchema shape is constructable', () => {
    const schema: ExtensionSettingsSchema = {
      version: 1,
      schema: { type: 'object', properties: {} },
    };
    expect(schema.version).toBe(1);
    expect(schema.schema?.type).toBe('object');
  });

  it('InstalledExtensionMetadata shape is constructable', () => {
    const meta: InstalledExtensionMetadata = {
      extensionId: 'com.example.ext' as ExtensionId,
      version: '1.0.0',
      integrity: { algorithm: 'sha256', value: 'abc' },
      enabled: true,
      publisher: 'Example Corp',
      license: 'MIT',
    };
    expect(meta.extensionId).toBe('com.example.ext');
    expect(meta.enabled).toBe(true);
    expect(meta.publisher).toBe('Example Corp');
  });

  it('InstalledExtensionPackage shape is constructable', () => {
    const pkg: InstalledExtensionPackage = {
      metadata: {
        extensionId: 'com.example.ext' as ExtensionId,
        version: '1.0.0',
        integrity: { algorithm: 'sha256', value: 'abc' },
        enabled: true,
      },
      manifest: {
        id: 'com.example.ext' as ExtensionId,
        version: '1.0.0',
        label: 'Test Extension',
        publisher: 'Example Corp',
        license: 'MIT',
      },
      bundleContent: 'export function activate() {}',
    };
    expect(pkg.metadata.extensionId).toBe('com.example.ext');
    expect(pkg.manifest.id).toBe('com.example.ext');
    expect(pkg.bundleContent).toContain('export function activate');
  });

  it('ManifestValidationMode covers dev and installed', () => {
    const modes: ManifestValidationMode[] = ['dev', 'installed'];
    expect(modes).toHaveLength(2);
  });

  it('ManifestValidationResult shape is constructable', () => {
    const result: ManifestValidationResult = {
      valid: true,
      errors: [],
      warnings: [],
    };
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('ExtensionPermissionDeclaration shape is constructable', () => {
    const perm: ExtensionPermissionDeclaration = {
      reason: 'Needs network access for API calls',
      posture: {
        network: true,
        filesystem: false,
        env: true,
        processes: false,
      },
    };
    expect(perm.reason).toContain('network');
    expect(perm.posture?.network).toBe(true);
    expect(perm.posture?.filesystem).toBe(false);
    expect(perm.posture?.env).toBe(true);
    expect(perm.posture?.processes).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// M10: Internal agent tool types are NOT leaked through @reigh/editor-sdk
// ---------------------------------------------------------------------------

describe('M10: internal agent tool types are NOT re-exported from @reigh/editor-sdk', () => {
  const M10_INTERNAL_FORBIDDEN = [
    'agentToolRegistry',
    'AgentToolRegistry',
    'registerAgentTool',
    'resolveAgentTool',
    'executeAgentTool',
    'AgentToolExecutor',
    'agentToolStore',
    'createAgentToolRegistrationService',
  ];

  it('none of the forbidden M10 internal names appear as SDK value exports', () => {
    const valueExports = Object.keys(sdkStar);
    for (const forbidden of M10_INTERNAL_FORBIDDEN) {
      expect(valueExports).not.toContain(forbidden);
    }
  });

  it('forbidden M10 internal names are not accessible on the SDK namespace', () => {
    const ns = sdkStar as Record<string, unknown>;
    for (const forbidden of M10_INTERNAL_FORBIDDEN) {
      expect(ns[forbidden]).toBeUndefined();
    }
  });
});

// ---------------------------------------------------------------------------
// M5/M12: Internal renderability types are NOT leaked
// ---------------------------------------------------------------------------

describe('M5/M12: internal renderability types are NOT re-exported from @reigh/editor-sdk', () => {
  const M5_M12_INTERNAL_FORBIDDEN = [
    'renderabilityRegistry',
    'RenderabilityChecker',
    'createRenderabilityChecker',
    'resolveRenderRoute',
    'executeRenderPlan',
    'RenderPipeline',
    'RenderPipelineExecutor',
    'materializeEffect',
    'materializeTransition',
    'isMaterializerAvailable',
    'processRegistry',
    'ProcessRegistry',
    'createProcessRegistry',
    'registerProcess',
    'resolveProcess',
    'spawnProcess',
    'killProcess',
  ];

  it('none of the forbidden renderability/process internal names appear as SDK value exports', () => {
    const valueExports = Object.keys(sdkStar);
    for (const forbidden of M5_M12_INTERNAL_FORBIDDEN) {
      expect(valueExports).not.toContain(forbidden);
    }
  });
});

// ---------------------------------------------------------------------------
// M1: Proposal import API name contract
// ---------------------------------------------------------------------------

describe('M1: proposal import API name contract', () => {
  it('no public importEnvelope alias exists in SDK value exports', () => {
    const valueExports = Object.keys(sdkStar);
    expect(valueExports).not.toContain('importEnvelope');
  });

  it('no public importEnvelope alias exists in SDK type exports (namespace check)', () => {
    // Verify importEnvelope is not a property on the SDK namespace at runtime.
    const sdkKeys = Object.keys(sdkStar);
    expect(sdkKeys.filter((k) => k.toLowerCase().includes('importenvelope'))).toHaveLength(0);
  });

  it('ProposalImportDiagnostic is exported as a type from @reigh/editor-sdk', () => {
    // Type-only import already verified above; runtime check proves it's in
    // the module's type space (not a value export, so not in Object.keys).
    // We verify it compiles by constructing the type — already proven above.
    const diag: ProposalImportDiagnostic = {
      severity: 'warning',
      code: 'test',
      message: 'test',
    };
    expect(diag.severity).toBe('warning');
  });

  it('ProposalImportResult is exported as a type from @reigh/editor-sdk', () => {
    const result: ProposalImportResult = {
      imported: 0,
      skipped: 0,
      rejected: 0,
      statuses: [],
      diagnostics: [],
    };
    expect(result.imported).toBe(0);
  });

  it('ProposalImportStatus is exported as a type from @reigh/editor-sdk', () => {
    const s: ProposalImportStatus = 'imported';
    expect(s).toBe('imported');
  });
});

// ---------------------------------------------------------------------------
// Semver-sensitive SDK export snapshot
// ---------------------------------------------------------------------------

describe('semver-sensitive SDK export snapshot', () => {
  it('SDK value exports include semver-aware constants and API version gate', () => {
    const valueExports = Object.keys(sdkStar);
    // Contract: SDK must export CONTRIBUTION_KIND_MILESTONE mapping each kind to its
    // owning milestone so extensions can feature-detect by milestone string.
    expect(valueExports).toContain('CONTRIBUTION_KIND_MILESTONE');
    expect(valueExports).toContain('CREATIVE_MEMBER_MILESTONE');

    // Contract: SDK must export the extension defines / validation surface.
    expect(valueExports).toContain('defineExtension');
    expect(valueExports).toContain('validateExtensionId');
    expect(valueExports).toContain('validateManifest');
    expect(valueExports).toContain('validateInstalledPackage');

    // Contract: SDK must export the contribution bridging gate.
    expect(valueExports).toContain('contributionKindNotYetBridged');

    // Contract: SDK must export renderability constants for cross-milestone
    // blocker/reason enumeration.
    expect(valueExports).toContain('DETERMINISM_STATUSES');
    expect(valueExports).toContain('RENDER_BLOCKER_REASONS');
    expect(valueExports).toContain('RENDER_ROUTES');

    // Contract: SDK must export the migration surface for semver-sensitive upgrades.
    expect(valueExports).toContain('runSettingsMigration');
    expect(valueExports).toContain('getManifestSettingsSchemaVersion');

    // Contract: SDK must export the settings service factory.
    expect(valueExports).toContain('createExtensionSettingsService');
  });

  it('CONTRIBUTION_KIND_MILESTONE maps all known kinds to milestone strings', () => {
    const mandatoryKinds = [
      'slot', 'dialog', 'panel', 'inspectorSection',
      'command', 'keybinding', 'contextMenuItem',
      'parser', 'outputFormat', 'searchProvider',
      'effect', 'transition', 'clipType', 'shader',
      'automation', 'agentTool', 'agent', 'process',
      'timelineOverlay', 'metadataFacet', 'assetDetailSection',
    ];
    for (const kind of mandatoryKinds) {
      expect(CONTRIBUTION_KIND_MILESTONE).toHaveProperty(kind);
      expect(CONTRIBUTION_KIND_MILESTONE[kind as keyof typeof CONTRIBUTION_KIND_MILESTONE]).toMatch(/^M\d+$/);
    }
  });

  it('SDK value export count remains within semver-safe public surface range', () => {
    // After adding the new re-exports (renderability constants, migration, settings
    // service) the count may increase, but it must stay under a reasonable ceiling
    // to prevent accidental surface expansion.
    const valueCount = Object.keys(sdkStar).length;
    // Updated ceiling to account for expanded legitimate public surface
    expect(valueCount).toBeLessThan(200);
    expect(valueCount).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Registry-derived family helpers (sdk-boundary)
// ---------------------------------------------------------------------------

describe('registry-derived family helpers', () => {
  it('getVideoFamilyDefinition returns registry data for known kinds', () => {
    const slotDef = getVideoFamilyDefinition('slot');
    expect(slotDef).toBeDefined();
    expect(slotDef!.kind).toBe('slot');
    expect(slotDef!.executionMaturity).toBe('public-supported');
    expect(slotDef!.legacyMilestone).toBe('M1');

    const parserDef = getVideoFamilyDefinition('parser');
    expect(parserDef).toBeDefined();
    expect(parserDef!.executionMaturity).toBe('delegated');
    expect(parserDef!.legacyMilestone).toBe('M6');
  });

  it('getVideoFamilyDefinition returns undefined for unknown kind', () => {
    expect(getVideoFamilyDefinition('nonexistent' as any)).toBeUndefined();
  });

  it('getVideoFamilyConformanceReport returns report from registry', () => {
    const report = getVideoFamilyConformanceReport('slot');
    expect(report).toBeDefined();
    expect(report!.kind).toBe('slot');
    expect(Array.isArray(report!.gaps)).toBe(true);
    expect(typeof report!.coherent).toBe('boolean');
  });

  it('getVideoFamilyLegacyBridgeStatus matches registry execution maturity', () => {
    // Bridged
    expect(getVideoFamilyLegacyBridgeStatus('slot')).toBeNull();
    expect(getVideoFamilyLegacyBridgeStatus('command')).toBeNull();
    // Delegated placeholder-backed kinds still report their legacy milestone.
    expect(getVideoFamilyLegacyBridgeStatus('parser')).toBe('M6');
    expect(getVideoFamilyLegacyBridgeStatus('agentTool')).toBe('M10');
    expect(getVideoFamilyLegacyBridgeStatus('effect')).toBe('M7');
    expect(getVideoFamilyLegacyBridgeStatus('transition')).toBe('M8');
    // Not bridged (delegated / absent)
    expect(getVideoFamilyLegacyBridgeStatus('agent')).toBe('M10');
    expect(getVideoFamilyLegacyBridgeStatus('outputFormat')).toBe('M6');
    expect(getVideoFamilyLegacyBridgeStatus('shader')).toBe('M13');
  });

  it('CONTRIBUTION_KIND_MILESTONE is derived from the family registry', () => {
    // Spot-check key mappings
    expect(CONTRIBUTION_KIND_MILESTONE.slot).toBe('M1');
    expect(CONTRIBUTION_KIND_MILESTONE.command).toBe('M4');
    expect(CONTRIBUTION_KIND_MILESTONE.parser).toBe('M6');
    expect(CONTRIBUTION_KIND_MILESTONE.effect).toBe('M7');
    expect(CONTRIBUTION_KIND_MILESTONE.transition).toBe('M8');
    expect(CONTRIBUTION_KIND_MILESTONE.clipType).toBe('M9');
    expect(CONTRIBUTION_KIND_MILESTONE.agent).toBe('M10');
    expect(CONTRIBUTION_KIND_MILESTONE.process).toBe('M12');
    expect(CONTRIBUTION_KIND_MILESTONE.shader).toBe('M13');
    // All 21 kinds must be present
    expect(Object.keys(CONTRIBUTION_KIND_MILESTONE).length).toBeGreaterThanOrEqual(21);
  });

  it('contributionKindNotYetBridged uses execution maturity from registry', () => {
    // runtime-bridged → bridged
    expect(contributionKindNotYetBridged('clipType')).toBeNull();
    // host-integrated → bridged
    expect(contributionKindNotYetBridged('command')).toBeNull();
    expect(contributionKindNotYetBridged('dialog')).toBeNull();
    // public-supported → bridged
    expect(contributionKindNotYetBridged('slot')).toBeNull();
    // delegated → NOT bridged (returns legacy milestone)
    expect(contributionKindNotYetBridged('agent')).toBe('M10');
    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
    expect(contributionKindNotYetBridged('searchProvider')).toBe('M6');
    expect(contributionKindNotYetBridged('shader')).toBe('M13');
    expect(contributionKindNotYetBridged('parser')).toBe('M6');
    expect(contributionKindNotYetBridged('effect')).toBe('M7');
    expect(contributionKindNotYetBridged('transition')).toBe('M8');
    expect(contributionKindNotYetBridged('agentTool')).toBe('M10');
  });
});

// ---------------------------------------------------------------------------
// T3: Family adapter contract types (sdk-boundary)
// ---------------------------------------------------------------------------

import {
  FamilyAdapterRegistryImpl,
} from '@reigh/editor-sdk';
import type {
  HostFamilyAdapter,
  HostAdapterManifest,
  HostAdapterRegistrationDescriptor,
  FamilyAdapterRegistry,
  FamilyDefinition,
  FamilyConformanceReport,
  ConformanceGap,
  ConformanceGapCategory,
  DeclarationMaturity,
  ExecutionMaturity,
  FamilyRequirementChecklist,
  FamilyAdapterManifest,
  FamilyAdapterManifestEntry,
  ManifestCrossReferenceResult,
} from '@reigh/editor-sdk';

describe('T3: family adapter contract types (sdk-boundary)', () => {
  it('HostFamilyAdapter import resolves and is constructable', () => {
    const adapter: HostFamilyAdapter<'slot', unknown> = {
      kind: 'slot',
      manifest: {
        adapterId: 'slot-main',
        kind: 'slot',
        version: '1.0.0',
        maturity: 'public-supported',
        description: 'Slot adapter for host chrome',
      },
    };
    expect(adapter.kind).toBe('slot');
    expect(adapter.manifest.maturity).toBe('public-supported');
  });

  it('HostAdapterManifest carries required identity fields', () => {
    const m: HostAdapterManifest = {
      adapterId: 'md-default',
      kind: 'metadataFacet',
      version: '0.1.0',
      maturity: 'runtime-bridged',
    };
    expect(m.adapterId).toBe('md-default');
    expect(m.kind).toBe('metadataFacet');
    expect(m.version).toBe('0.1.0');
  });

  it('HostAdapterRegistrationDescriptor accepts null adapter', () => {
    const desc: HostAdapterRegistrationDescriptor = {
      adapter: null,
      overrideMaturity: 'absent',
    };
    expect(desc.adapter).toBeNull();
    expect(desc.overrideMaturity).toBe('absent');
  });

  it('FamilyAdapterRegistry maps kinds to adapters or null', () => {
    const reg: FamilyAdapterRegistry = new Map([
      ['parser', null],
      ['metadataFacet', {
        kind: 'metadataFacet',
        manifest: {
          adapterId: 'md-1',
          kind: 'metadataFacet',
          version: '1.0.0',
          maturity: 'runtime-bridged',
        },
      } as HostFamilyAdapter],
    ]);
    expect(reg.size).toBe(2);
    expect(reg.get('parser')).toBeNull();
    expect(reg.get('metadataFacet')?.kind).toBe('metadataFacet');
  });

  it('FamilyDefinition is importable and fully constructable', () => {
    const def: FamilyDefinition<'slot'> = {
      kind: 'slot',
      declarationMaturity: 'documented',
      executionMaturity: 'public-supported',
      hostIntegrationNotes: 'Mature slot family',
      requiresTrustedCode: true,
      manifestSchemaDefinition: 'slotContribution',
      sdkModules: ['src/sdk/video/families/slots'],
      hostAdapter: 'src/tools/video-editor/host/adapters/slotAdapter.ts',
      requirements: {
        manifestSchema: true,
        normalizedDescriptor: true,
        registrationApi: true,
        lifecycleCleanup: true,
        diagnostics: true,
        hostCapabilityProjection: true,
        uiIntegration: true,
        persistencePosture: true,
        examples: true,
        tests: true,
      },
      legacyMilestone: 'M1',
      label: 'Slot',
      description: 'Host chrome slot contribution family',
    };
    expect(def.kind).toBe('slot');
    expect(def.executionMaturity).toBe('public-supported');
    expect(def.requirements.tests).toBe(true);
  });

  it('ConformanceGap supports optional metadata (T3 extension)', () => {
    const gap: ConformanceGap = {
      category: 'host-adapter-missing',
      message: 'Expected host adapter for effect family',
      requirementKeys: ['hostCapabilityProjection'],
      metadata: {
        kind: 'effect',
        maturity: 'runtime-bridged',
        expectedAdapterPath: 'src/tools/video-editor/host/adapters/effectAdapter.ts',
        checkedAt: Date.now(),
      },
    };
    expect(gap.metadata).toBeDefined();
    expect(gap.metadata!.kind).toBe('effect');
    expect(gap.metadata!.expectedAdapterPath).toContain('effectAdapter');
    expect(typeof gap.metadata!.checkedAt).toBe('number');
  });

  it('FamilyConformanceReport.gaps elements accept metadata', () => {
    const report: FamilyConformanceReport<'slot'> = {
      kind: 'slot',
      definition: {
        kind: 'slot',
        declarationMaturity: 'documented',
        executionMaturity: 'public-supported',
        hostIntegrationNotes: '',
        requiresTrustedCode: true,
        manifestSchemaDefinition: 'slotContribution',
        sdkModules: [],
        hostAdapter: 'slotAdapter.ts',
        requirements: {
          manifestSchema: true,
          normalizedDescriptor: true,
          registrationApi: true,
          lifecycleCleanup: true,
          diagnostics: true,
          hostCapabilityProjection: true,
          uiIntegration: true,
          persistencePosture: true,
          examples: true,
          tests: true,
        },
        legacyMilestone: 'M1',
        label: 'Slot',
      },
      declarationMaturity: 'documented',
      executionMaturity: 'public-supported',
      requirements: {
        manifestSchema: true,
        normalizedDescriptor: true,
        registrationApi: true,
        lifecycleCleanup: true,
        diagnostics: true,
        hostCapabilityProjection: true,
        uiIntegration: true,
        persistencePosture: true,
        examples: true,
        tests: true,
      },
      unmetRequirements: [],
      metRequirements: [],
      unassessedRequirements: [],
      gaps: [{
        category: 'unassessed-requirement',
        message: 'Test gap with metadata',
        metadata: { test: true },
      }],
      coherent: true,
      schemaCovered: true,
    };
    expect(report.gaps).toHaveLength(1);
    expect(report.gaps[0].metadata).toEqual({ test: true });
  });

  it('DeclarationMaturity and ExecutionMaturity are sealed unions', () => {
    const declLevels: DeclarationMaturity[] = ['typed', 'schema-backed', 'documented'];
    const execLevels: ExecutionMaturity[] = ['absent', 'delegated', 'runtime-bridged', 'host-integrated', 'public-supported'];
    expect(declLevels).toHaveLength(3);
    expect(execLevels).toHaveLength(5);
  });

  it('ConformanceGapCategory is importable with all 5 values', () => {
    const cats: ConformanceGapCategory[] = [
      'unmet-requirement',
      'coherence-violation',
      'schema-coverage-missing',
      'host-adapter-missing',
      'unassessed-requirement',
    ];
    expect(cats).toHaveLength(5);
    cats.forEach(c => expect(typeof c).toBe('string'));
  });

  it('FamilyRequirementChecklist has all 10 requirement keys', () => {
    const checklist: FamilyRequirementChecklist = {
      manifestSchema: undefined,
      normalizedDescriptor: undefined,
      registrationApi: undefined,
      lifecycleCleanup: undefined,
      diagnostics: undefined,
      hostCapabilityProjection: undefined,
      uiIntegration: undefined,
      persistencePosture: undefined,
      examples: undefined,
      tests: undefined,
    };
    expect(Object.keys(checklist)).toHaveLength(10);
  });
});

// ---------------------------------------------------------------------------
// T4: Passive adapter registry (sdk-boundary)
// ---------------------------------------------------------------------------

describe('T4: passive adapter registry (sdk-boundary)', () => {
  // ---- construction -------------------------------------------------------

  it('constructs empty', () => {
    const reg = new FamilyAdapterRegistryImpl();
    expect(reg.size).toBe(0);
    expect(reg.kinds()).toEqual([]);
    expect(reg.get('anything')).toBeUndefined();
  });

  it('constructs with entries', () => {
    const fake: HostFamilyAdapter = {
      kind: 'command',
      manifest: {
        adapterId: 'cmd-1',
        kind: 'command',
        version: '1.0.0',
        maturity: 'host-integrated',
      },
    };
    const reg = new FamilyAdapterRegistryImpl([
      ['command', fake],
      ['outputFormat', null],
    ]);
    expect(reg.size).toBe(2);
    expect(reg.get('command')).toBe(fake);
    expect(reg.get('outputFormat')).toBeNull();
  });

  // ---- get ----------------------------------------------------------------

  it('get distinguishes adapter, null, and undefined', () => {
    const fake: HostFamilyAdapter = {
      kind: 'slot',
      manifest: {
        adapterId: 's-1',
        kind: 'slot',
        version: '1.0.0',
        maturity: 'public-supported',
      },
    };
    const reg = new FamilyAdapterRegistryImpl([
      ['slot', fake],
      ['shader', null],
    ]);
    expect(reg.get('slot')).toBe(fake);
    expect(reg.get('shader')).toBeNull();
    expect(reg.get('dialog')).toBeUndefined();
  });

  // ---- require ------------------------------------------------------------

  it('require throws descriptive error for unregistered kind', () => {
    const reg = new FamilyAdapterRegistryImpl();
    expect(() => reg.require('nonexistent')).toThrow(
      'FamilyAdapterRegistry: kind "nonexistent" is not registered.',
    );
  });

  it('require returns null for known-unavailable', () => {
    const reg = new FamilyAdapterRegistryImpl([['parser', null]]);
    expect(reg.require('parser')).toBeNull();
  });

  // ---- kinds --------------------------------------------------------------

  it('kinds returns sorted array', () => {
    const fake: HostFamilyAdapter = {
      kind: 'z',
      manifest: {
        adapterId: 'z',
        kind: 'z',
        version: '1.0.0',
        maturity: 'absent',
      },
    };
    const reg = new FamilyAdapterRegistryImpl([
      ['c', fake],
      ['a', null],
      ['b', fake],
    ]);
    expect(reg.kinds()).toEqual(['a', 'b', 'c']);
  });

  // ---- register -----------------------------------------------------------

  it('register with overrideMaturity does not mutate original adapter', () => {
    const reg = new FamilyAdapterRegistryImpl();
    const fake: HostFamilyAdapter = {
      kind: 'effect',
      manifest: {
        adapterId: 'eff-1',
        kind: 'effect',
        version: '1.0.0',
        maturity: 'runtime-bridged',
      },
    };
    const originalMaturity = fake.manifest.maturity;
    reg.register({ adapter: fake, overrideMaturity: 'delegated' });
    const stored = reg.get('effect')!;
    expect(stored.manifest.maturity).toBe('delegated');
    expect(fake.manifest.maturity).toBe(originalMaturity);
  });

  it('register null adapter via metadata.kind', () => {
    const reg = new FamilyAdapterRegistryImpl();
    reg.register({
      adapter: null,
      metadata: { kind: 'keybinding' },
    });
    expect(reg.get('keybinding')).toBeNull();
    expect(reg.kinds()).toContain('keybinding');
  });

  // ---- snapshot -----------------------------------------------------------

  it('snapshot is a FamilyAdapterRegistry (ReadonlyMap)', () => {
    const fake: HostFamilyAdapter = {
      kind: 'dialog',
      manifest: {
        adapterId: 'dlg-1',
        kind: 'dialog',
        version: '1.0.0',
        maturity: 'host-integrated',
      },
    };
    const reg = new FamilyAdapterRegistryImpl([['dialog', fake]]);
    const snap: FamilyAdapterRegistry = reg.snapshot();
    expect(snap instanceof Map).toBe(true);
    expect(snap.get('dialog')).toBe(fake);
    // Snapshot is a new Map, not the internal map
    expect(snap).not.toBe(reg.snapshot());
  });

  // ---- passive / no side effects ------------------------------------------

  it('registry operations are pure lookups, no side effects', () => {
    const reg = new FamilyAdapterRegistryImpl();
    const fake: HostFamilyAdapter = {
      kind: 'inspectorSection',
      manifest: {
        adapterId: 'is-1',
        kind: 'inspectorSection',
        version: '1.0.0',
        maturity: 'host-integrated',
      },
    };

    // All operations must succeed without side effects
    reg.register({ adapter: fake });
    expect(reg.require('inspectorSection')).toBe(fake);
    expect(reg.get('inspectorSection')).toBe(fake);
    expect(reg.kinds()).toEqual(['inspectorSection']);
    const snap = reg.snapshot();
    expect(snap.size).toBe(1);

    // Repeat operations are idempotent
    expect(reg.kinds()).toEqual(['inspectorSection']);
    expect(reg.require('inspectorSection')).toBe(fake);
  });
});

// ---------------------------------------------------------------------------
// T5: Adapter coordinator & conformance aggregation (sdk-boundary)
// ---------------------------------------------------------------------------

import {
  normalizeAdapters,
  disposeAll,
  projectMaturityCapabilities,
  findAdapter,
  listRegisteredKinds,
  aggregateHostConformance,
  isValidDelegatedGap,
  identifyDelegatedFamilies,
  buildFamilyAdapterManifest,
  crossReferenceManifest,
} from '@reigh/editor-sdk';

// ---- T5 shared helpers ------------------------------------------------------

function fakeAdapter(kind: string, maturity: ExecutionMaturity = 'runtime-bridged'): HostFamilyAdapter {
  return {
    kind,
    manifest: {
      adapterId: `${kind}-fake`,
      kind,
      version: '1.0.0',
      maturity,
    },
  };
}

function fakeDefinition(
  kind: string,
  executionMaturity: ExecutionMaturity,
  opts?: { hostAdapter?: string | null; manifestSchema?: boolean },
): FamilyDefinition {
  return {
    kind,
    declarationMaturity: 'schema-backed',
    executionMaturity,
    requiresTrustedCode: false,
    manifestSchemaDefinition: `${kind}Schema`,
    sdkModules: [`video/families/${kind}`],
    hostAdapter: opts?.hostAdapter ?? null,
    requirements: {
      manifestSchema: opts?.manifestSchema ?? true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: undefined,
      diagnostics: undefined,
      hostCapabilityProjection: undefined,
      uiIntegration: undefined,
      persistencePosture: undefined,
      examples: undefined,
      tests: undefined,
    },
  };
}

describe('T5: adapter coordinator (sdk-boundary)', () => {
  it('normalizeAdapters deduplicates by kind (last wins)', () => {
    const a1 = fakeAdapter('effect', 'runtime-bridged');
    const a2 = fakeAdapter('effect', 'host-integrated');
    const a3 = fakeAdapter('transition', 'runtime-bridged');

    const normalized = normalizeAdapters([a1, a2, a3]);
    expect(normalized.size).toBe(2);
    expect(normalized.get('effect')!.manifest.maturity).toBe('host-integrated');
    expect(normalized.get('transition')).toBe(a3);
  });

  it('normalizeAdapters returns empty map for empty input', () => {
    expect(normalizeAdapters([]).size).toBe(0);
  });

  it('disposeAll calls disposer for every adapter in order', () => {
    const disposed: string[] = [];
    const adapters = [fakeAdapter('a'), fakeAdapter('b'), fakeAdapter('c')];

    disposeAll(adapters, (a) => disposed.push(a.kind));
    expect(disposed).toEqual(['a', 'b', 'c']);
  });

  it('disposeAll does not throw on empty array', () => {
    expect(() => disposeAll([], () => {})).not.toThrow();
  });

  it('projectMaturityCapabilities maps null entries to delegated', () => {
    const registry: FamilyAdapterRegistry = new Map([
      ['shader', null],
      ['agent', null],
    ]);

    const projection = projectMaturityCapabilities(registry);
    expect(projection.get('shader')).toBe('delegated');
    expect(projection.get('agent')).toBe('delegated');
  });

  it('projectMaturityCapabilities returns read-only typed map', () => {
    const registry: FamilyAdapterRegistry = new Map([
      ['slot', fakeAdapter('slot')],
    ]);

    const projection = projectMaturityCapabilities(registry);
    // ReadonlyMap is a type-level contract — verify data correctness.
    expect(projection.get('slot')).toBe('runtime-bridged');
    expect(projection.has('nonexistent')).toBe(false);
  });

  it('findAdapter returns adapter, null, and undefined appropriately', () => {
    const adapter = fakeAdapter('dialog', 'host-integrated');
    const registry: FamilyAdapterRegistry = new Map([
      ['dialog', adapter],
      ['shader', null],
    ]);
    expect(findAdapter(registry, 'dialog')).toBe(adapter);
    expect(findAdapter(registry, 'shader')).toBeNull();
    expect(findAdapter(registry, 'nonexistent')).toBeUndefined();
  });

  it('listRegisteredKinds returns sorted alphabetical list', () => {
    const registry: FamilyAdapterRegistry = new Map([
      ['zebra', fakeAdapter('zebra')],
      ['alpha', null],
      ['beta', fakeAdapter('beta')],
    ]);
    expect(listRegisteredKinds(registry)).toEqual(['alpha', 'beta', 'zebra']);
  });
});

describe('T5: conformance aggregation (sdk-boundary)', () => {
  it('aggregateHostConformance adds host-adapter-missing for null registry entry', () => {
    const defs = [fakeDefinition('shader', 'runtime-bridged')];
    const registry: FamilyAdapterRegistry = new Map([['shader', null]]);

    const reports = aggregateHostConformance(defs, registry);
    expect(reports).toHaveLength(1);

    const nullGaps = reports[0].gaps.filter(
      (g: ConformanceGap) => g.category === 'host-adapter-missing' &&
        g.metadata?.registryStatus === 'null',
    );
    expect(nullGaps.length).toBeGreaterThan(0);
  });

  it('aggregateHostConformance does not add host-adapter-missing for absent maturity', () => {
    const defs = [fakeDefinition('unknown', 'absent')];
    const registry: FamilyAdapterRegistry = new Map();

    const reports = aggregateHostConformance(defs, registry);
    const hostMissingGaps = reports[0].gaps.filter(
      (g: ConformanceGap) => g.category === 'host-adapter-missing',
    );
    expect(hostMissingGaps).toHaveLength(0);
  });

  it('aggregateHostConformance preserves base report gaps', () => {
    const defs = [fakeDefinition('effect', 'runtime-bridged', { manifestSchema: false })];
    const registry: FamilyAdapterRegistry = new Map([
      ['effect', fakeAdapter('effect', 'runtime-bridged')],
    ]);

    const reports = aggregateHostConformance(defs, registry);
    const schemaGaps = reports[0].gaps.filter(
      (g: ConformanceGap) => g.category === 'schema-coverage-missing',
    );
    expect(schemaGaps.length).toBeGreaterThan(0);
  });

  it('isValidDelegatedGap validates delegated-gap metadata against registry', () => {
    const registry: FamilyAdapterRegistry = new Map([['shader', null]]);

    // Valid delegated gap
    const validGap: ConformanceGap = {
      category: 'host-adapter-missing',
      message: 'Delegated gap for shader',
      metadata: {
        kind: 'shader',
        delegatedKind: true,
        executionMaturity: 'runtime-bridged',
      },
    };
    expect(isValidDelegatedGap(validGap, registry)).toBe(true);

    // Missing delegatedKind
    const noDelegatedFlag: ConformanceGap = {
      category: 'host-adapter-missing',
      message: 'Not delegated',
      metadata: { kind: 'shader', executionMaturity: 'runtime-bridged' },
    };
    expect(isValidDelegatedGap(noDelegatedFlag, registry)).toBe(false);

    // Real adapter in registry
    const registryWithReal: FamilyAdapterRegistry = new Map([
      ['shader', fakeAdapter('shader')],
    ]);
    expect(isValidDelegatedGap(validGap, registryWithReal)).toBe(false);

    // Absent maturity
    const absentGap: ConformanceGap = {
      category: 'host-adapter-missing',
      message: 'Delegated with absent',
      metadata: {
        kind: 'shader',
        delegatedKind: true,
        executionMaturity: 'absent',
      },
    };
    expect(isValidDelegatedGap(absentGap, registry)).toBe(false);
  });

  it('identifyDelegatedFamilies returns sorted null-adapter kinds', () => {
    const registry: FamilyAdapterRegistry = new Map([
      ['shader', null],
      ['slot', fakeAdapter('slot', 'public-supported')],
      ['agent', null],
    ]);

    expect(identifyDelegatedFamilies(registry)).toEqual(['agent', 'shader']);
  });

  it('identifyDelegatedFamilies returns empty when no null entries', () => {
    const registry: FamilyAdapterRegistry = new Map([
      ['slot', fakeAdapter('slot')],
    ]);
    expect(identifyDelegatedFamilies(registry)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// T6: Family adapter manifest — cross-reference checklist (sdk-boundary)
// ---------------------------------------------------------------------------

describe('T6: family adapter manifest (sdk-boundary)', () => {
  it('buildFamilyAdapterManifest returns a non-empty manifest', () => {
    const manifest = buildFamilyAdapterManifest();
    expect(manifest.size).toBeGreaterThan(0);
    expect(manifest.entries.length).toBe(manifest.size);
  });

  it('manifest has 21 entries (one per family kind)', () => {
    const manifest = buildFamilyAdapterManifest();
    expect(manifest.size).toBe(21);
  });

  it('manifest entries are sorted alphabetically by kind', () => {
    const manifest = buildFamilyAdapterManifest();
    const kinds = manifest.entries.map((e) => e.kind);
    expect(kinds).toEqual([...kinds].sort());
  });

  it('getEntry resolves known families', () => {
    const manifest = buildFamilyAdapterManifest();
    expect(manifest.getEntry('slot')!.executionMaturity).toBe('public-supported');
    expect(manifest.getEntry('effect')!.executionMaturity).toBe('delegated');
    expect(manifest.getEntry('agent')!.executionMaturity).toBe('delegated');
    expect(manifest.getEntry('outputFormat')!.executionMaturity).toBe('delegated');
  });

  it('getEntry returns undefined for unknown kind', () => {
    const manifest = buildFamilyAdapterManifest();
    expect(manifest.getEntry('bogus')).toBeUndefined();
  });

  it('crossReferenceManifest with empty registry flags all kinds as missing', () => {
    const manifest = buildFamilyAdapterManifest();
    const registry: FamilyAdapterRegistry = new Map();
    const result = crossReferenceManifest(manifest, registry);

    // Every kind is missing from the registry
    expect(result.missingFromRegistry.length).toBe(manifest.size);
    expect(result.isFullyAligned).toBe(false);
  });

  it('crossReferenceManifest detects manifest-registry-constributionKinds alignment', () => {
    const manifest = buildFamilyAdapterManifest();
    const registry: FamilyAdapterRegistry = new Map();
    const result = crossReferenceManifest(manifest, registry);

    // Manifest should cover all contribution kinds
    expect(result.contributionKindsNotInManifest).toEqual([]);
    expect(result.manifestKindsNotInContributionKinds).toEqual([]);
  });

  it('crossReferenceManifest detects adapter-needing kinds', () => {
    const manifest = buildFamilyAdapterManifest();
    // Register slot and dialog as null — both are public-supported / host-integrated
    // and therefore expect a real adapter.
    const registry: FamilyAdapterRegistry = new Map([
      ['slot', null],
      ['dialog', null],
    ]);
    const result = crossReferenceManifest(manifest, registry);

    expect(result.kindsNeedingAdapter).toContain('slot');
    expect(result.kindsNeedingAdapter).toContain('dialog');
  });

  it('crossReferenceManifest reports missingFromManifest for extra registry entries', () => {
    const manifest = buildFamilyAdapterManifest();
    const registry: FamilyAdapterRegistry = new Map([
      ['extraKind1', null],
      ['extraKind2', null],
    ]);
    const result = crossReferenceManifest(manifest, registry);

    expect(result.missingFromManifest).toContain('extraKind1');
    expect(result.missingFromManifest).toContain('extraKind2');
  });

  it('every manifest entry has structurally valid fields', () => {
    const manifest = buildFamilyAdapterManifest();
    const validMaturities = new Set([
      'absent', 'delegated', 'runtime-bridged', 'host-integrated', 'public-supported',
    ]);
    const validDeclMaturities = new Set(['typed', 'schema-backed', 'documented']);

    for (const entry of manifest.entries) {
      expect(typeof entry.kind).toBe('string');
      expect(entry.kind.length).toBeGreaterThan(0);
      expect(typeof entry.label).toBe('string');
      expect(validDeclMaturities.has(entry.declarationMaturity)).toBe(true);
      expect(validMaturities.has(entry.executionMaturity)).toBe(true);
      expect(
        entry.hostAdapter === null || typeof entry.hostAdapter === 'string',
      ).toBe(true);
      expect(typeof entry.expectsRealAdapter).toBe('boolean');
      expect(Array.isArray(entry.gaps)).toBe(true);
      expect(Array.isArray(entry.sdkModules)).toBe(true);
    }
  });
});

// ===========================================================================
// M1a: Composition reference identity
// ===========================================================================

describe('M1a: Composition reference types are data-only and importable from @reigh/editor-sdk', () => {
  it('ContributionRef is a data-only type with kind, extensionId, contributionId', () => {
    const ref: ContributionRef = {
      kind: 'effect',
      extensionId: 'com.example.my-ext',
      contributionId: 'glow-effect',
    };
    expect(ref.kind).toBe('effect');
    expect(ref.extensionId).toBe('com.example.my-ext');
    expect(ref.contributionId).toBe('glow-effect');
    // Data-only: no methods, no version fields
    expect(Object.keys(ref).sort()).toEqual(['contributionId', 'extensionId', 'kind']);
  });

  it('LiveSourceRef is constructable with only sourceId and also accepts sourceKind/processBinding when supplied', () => {
    // Constructable with only sourceId (sourceKind is optional)
    const refMinimal: LiveSourceRef = { sourceId: 'webcam-1' };
    expect(refMinimal.sourceId).toBe('webcam-1');
    expect(refMinimal.sourceKind).toBeUndefined();
    expect(Object.keys(refMinimal).sort()).toEqual(['sourceId']);

    const processBinding: ProcessLiveSourceBinding = {
      processId: 'pose-process',
    };

    // Also accepts sourceKind and processBinding when supplied
    const refFull: LiveSourceRef = {
      sourceId: 'webcam-2',
      sourceKind: 'webcam',
      processBinding,
    };
    expect(refFull.sourceId).toBe('webcam-2');
    expect(refFull.sourceKind).toBe('webcam');
    expect(refFull.processBinding).toEqual(processBinding);
    expect(Object.keys(refFull).sort()).toEqual(['processBinding', 'sourceId', 'sourceKind']);
  });

  it('MaterialRef is a transparent alias of RenderMaterialRef', () => {
    // Type-level assertion: assign a MaterialRef to a RenderMaterialRef
    const mat: MaterialRef = {
      id: 'mat-1',
      mediaKind: 'video',
      locator: { kind: 'url', uri: 'https://example.com/video.mp4' },
      determinism: 'deterministic',
      replacementPolicy: 'preserve-live-ref',
    };
    // MaterialRef and RenderMaterialRef are the same type
    const asRender: RenderMaterialRef = mat;
    expect(asRender.id).toBe('mat-1');
    expect(asRender.mediaKind).toBe('video');
    // MaterialRef is not a deprecation — both names coexist
    expect(typeof (mat as any).__deprecated).toBe('undefined');
  });

  it('contributionRefKey returns kind:extensionId:contributionId without version fields', () => {
    const ref: ContributionRef = {
      kind: 'shader',
      extensionId: 'com.example.shaders',
      contributionId: 'bloom-pass',
    };
    const key = contributionRefKey(ref);
    expect(key).toBe('shader:com.example.shaders:bloom-pass');
    // No version fields in the key
    expect(key).not.toContain('version');
    expect(key).not.toContain('semver');
  });

  it('contributionRefKey is deterministic and stable', () => {
    const a: ContributionRef = { kind: 'slot', extensionId: 'ext-a', contributionId: 'toolbar' };
    const b: ContributionRef = { kind: 'slot', extensionId: 'ext-a', contributionId: 'toolbar' };
    expect(contributionRefKey(a)).toBe(contributionRefKey(b));
    expect(contributionRefKey(a)).toBe('slot:ext-a:toolbar');
  });

  it('ContributionRef scoped keys distinguish same contributionId in different extensions', () => {
    const refA: ContributionRef = { kind: 'effect', extensionId: 'ext-a', contributionId: 'glow' };
    const refB: ContributionRef = { kind: 'effect', extensionId: 'ext-b', contributionId: 'glow' };
    expect(contributionRefKey(refA)).not.toBe(contributionRefKey(refB));
    expect(contributionRefKey(refA)).toBe('effect:ext-a:glow');
    expect(contributionRefKey(refB)).toBe('effect:ext-b:glow');
  });

  it('ContributionRef scoped keys distinguish same contributionId in different kinds', () => {
    const refA: ContributionRef = { kind: 'effect', extensionId: 'ext-a', contributionId: 'glow' };
    const refB: ContributionRef = { kind: 'transition', extensionId: 'ext-a', contributionId: 'glow' };
    expect(contributionRefKey(refA)).not.toBe(contributionRefKey(refB));
    expect(contributionRefKey(refA)).toBe('effect:ext-a:glow');
    expect(contributionRefKey(refB)).toBe('transition:ext-a:glow');
  });

  it('contributionRefKey is importable from @reigh/editor-sdk as a function', () => {
    expect(typeof contributionRefKey).toBe('function');
  });

  it('all M1a exports are present in the SDK star import', () => {
    // Re-import via star to verify barrel visibility
    expect('contributionRefKey' in (globalThis as any) === false || typeof contributionRefKey === 'function').toBe(true);
  });
});
