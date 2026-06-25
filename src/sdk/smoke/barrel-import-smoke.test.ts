/**
 * M2a Barrel-import smoke coverage.
 *
 * Verifies that moved core names are importable BOTH from the public barrel
 * (`@/sdk/index`) and from canonical direct module paths.  Each module
 * family is represented by a small set of its most characteristic exports.
 *
 * The test is intentionally representative rather than exhaustive — it does
 * not attempt to duplicate the full API manifest (the API manifest gate
 * handles that).  It exists to catch import-resolution breakage across the
 * full breadth of moved M2a module families.
 *
 * @publicContract
 */

import { describe, expect, it } from 'vitest';

// ===========================================================================
// Public barrel imports (simulate downstream extension code)
// ===========================================================================
import {
  // ids
  validateExtensionId,
  validateContributionId,
  // lifecycle
  defineExtension,
  // context
  createCreativeContextStubs,
  ExtensionNotImplementedError,
  CREATIVE_MEMBER_MILESTONE,
  disposeExtensionContextServices,
  CONTEXT_DISPOSE_SYMBOL,
  // diagnostics
  createDiagnosticCollection,
  DIAGNOSTIC_SOURCE_EXTENSION,
  DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY,
  // manifest / validation
  KNOWN_CONTRIBUTION_KINDS_SET,
  ALL_VALID_PLACEMENTS,
  // settings
  createExtensionSettingsService,
} from '@/sdk/index';
import type {
  // ids
  ExtensionId,
  ContributionId,
  // dispose
  DisposeHandle,
  // diagnostics
  DiagnosticSeverity,
  DiagnosticSource,
  ExtensionDiagnostic,
  DiagnosticSourceRange,
  Diagnostic,
  DiagnosticCollection,
  CreateDiagnosticCollectionOptions,
  ExportDiagnostic,
  // manifest
  ContributionKind,
  VideoEditorSlotName,
  ExtensionContribution,
  ManifestValidationMode,
  ManifestValidationResult,
  // packaging
  DependencyPosture,
  ExtensionDependency,
  IntegrityAlgorithm,
  IntegrityHash,
  MigrationHookKind,
  MigrationDeclaration,
  InstalledExtensionMetadata,
  // settings
  ExtensionSettingsSchema,
  ExtensionSettingsService,
  // commands
  TargetContext,
  TargetContextPayload,
  CommandRunContext,
  CommandHandler,
  CommandRegistrationOptions,
  // chrome
  ExtensionChromeService,
  ChromeEvent,
  ChromeToastPayload,
  ChromeProgressPayload,
  ChromeSavePayload,
  ChromeRenderStatusPayload,
  ChromeEventPayload,
  // context
  ExtensionI18nService,
  ExtensionDiagnosticsService,
  CreativeContext,
  ExtensionCommandService,
  ExtensionContext,
  // lifecycle
  ExtensionActivateFn,
  ReighExtension,
  DefineExtensionOptions,
  // capabilities
  CapabilityVersion,
  CapabilitySourceRef,
  RouteFitMetadata,
  CapabilityRequirement,
  IntegrationCapabilities,
  SamplingStrategy,
  SamplingSourceRef,
  SamplingRange,
  SamplingAttachmentKind,
  SamplingAttachmentRule,
  SamplingConfig,
  SamplingResultItem,
  SamplingResult,
  ProcessRoundtripRequest,
  ProcessRoundtripAction,
  ProcessRoundtripResult,
  ProcessProgressEvent,
  ProcessLogSummary,
} from '@/sdk/index';

// ===========================================================================
// Canonical direct module imports (simulate SDK-internal code access)
// ===========================================================================
import {
  type ExtensionId as ExtId_Direct,
  type ContributionId as ContribId_Direct,
  validateExtensionId as validateExtId_Direct,
  validateContributionId as validateContribId_Direct,
} from '../ids';

import type { DisposeHandle as DisposeHandle_Direct } from '../dispose';

import {
  type DiagnosticSeverity as DiagSev_Direct,
  type DiagnosticSource as DiagSrc_Direct,
  DIAGNOSTIC_SOURCE_EXTENSION as DIAG_SRC_EXT_Direct,
  type ExtensionDiagnostic as ExtDiag_Direct,
  type DiagnosticSourceRange as DiagSrcRange_Direct,
  type Diagnostic as Diagnostic_Direct,
  type DiagnosticCollection as DiagColl_Direct,
  DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY as DEFAULT_DIAG_CAP_Direct,
  type CreateDiagnosticCollectionOptions as CreateDiagCollOpts_Direct,
  createDiagnosticCollection as createDiagColl_Direct,
  type ExportDiagnostic as ExportDiag_Direct,
} from '../diagnostics';

import {
  type ContributionKind as ContribKind_Direct,
  type VideoEditorSlotName as Slot_Direct,
  type ExtensionContribution as ExtContrib_Direct,
  KNOWN_CONTRIBUTION_KINDS_SET as KNOWN_CONTRIB_KINDS_SET_Direct,
  ALL_VALID_PLACEMENTS as ALL_VALID_PLACEMENTS_Direct,
  type ManifestValidationMode as ManifValMode_Direct,
  type ManifestValidationResult as ManifValResult_Direct,
} from '../manifest';

import type {
  DependencyPosture as DepPosture_Direct,
  ExtensionDependency as ExtDep_Direct,
  IntegrityAlgorithm as IntAlg_Direct,
  IntegrityHash as IntHash_Direct,
  MigrationHookKind as MigHookKind_Direct,
  MigrationDeclaration as MigDecl_Direct,
  InstalledExtensionMetadata as InstExtMeta_Direct,
} from '../packaging';

import type {
  ExtensionSettingsSchema as ExtSetSchema_Direct,
  ExtensionSettingsService as ExtSetSvc_Direct,
} from '../settings';

import type {
  TargetContext as TargetCtx_Direct,
  TargetContextPayload as TargetCtxPayload_Direct,
  CommandRunContext as CmdRunCtx_Direct,
  CommandHandler as CmdHandler_Direct,
  CommandRegistrationOptions as CmdRegOpts_Direct,
} from '../commands';

import type {
  ExtensionChromeService as ChromeSvc_Direct,
  ChromeEvent as ChromeEvt_Direct,
  ChromeToastPayload as ChromeToast_Direct,
  ChromeProgressPayload as ChromeProg_Direct,
  ChromeSavePayload as ChromeSave_Direct,
  ChromeRenderStatusPayload as ChromeRender_Direct,
  ChromeEventPayload as ChromeEvtPayload_Direct,
} from '../chrome';

import {
  type ExtensionI18nService as I18nSvc_Direct,
  type ExtensionDiagnosticsService as ExtDiagSvc_Direct,
  type CreativeContext as CreativeCtx_Direct,
  type ExtensionCommandService as ExtCmdSvc_Direct,
  type ExtensionContext as ExtCtx_Direct,
  createCreativeContextStubs as createCreativeStubs_Direct,
  ExtensionNotImplementedError as NotImplErr_Direct,
  CREATIVE_MEMBER_MILESTONE as CREATIVE_MEMBER_MILESTONE_Direct,
  disposeExtensionContextServices as disposeExtCtxSvc_Direct,
  CONTEXT_DISPOSE_SYMBOL as CTX_DISPOSE_SYM_Direct,
} from '../context';

import {
  type ExtensionActivateFn as ActivateFn_Direct,
  type ReighExtension as ReighExt_Direct,
  type DefineExtensionOptions as DefExtOpts_Direct,
  defineExtension as defExt_Direct,
} from '../lifecycle';

import type {
  CapabilityVersion as CapVer_Direct,
  CapabilitySourceRef as CapSrcRef_Direct,
  RouteFitMetadata as RouteFit_Direct,
  CapabilityRequirement as CapReq_Direct,
  IntegrationCapabilities as IntCap_Direct,
  SamplingStrategy as SampStrat_Direct,
  SamplingSourceRef as SampSrcRef_Direct,
  SamplingRange as SampRange_Direct,
  SamplingAttachmentKind as SampAttachKind_Direct,
  SamplingAttachmentRule as SampAttachRule_Direct,
  SamplingConfig as SampCfg_Direct,
  SamplingResultItem as SampResultItem_Direct,
  SamplingResult as SampResult_Direct,
  ProcessRoundtripRequest as ProcRRReq_Direct,
  ProcessRoundtripAction as ProcRRAction_Direct,
  ProcessRoundtripResult as ProcRRResult_Direct,
  ProcessProgressEvent as ProcProgEvt_Direct,
  ProcessLogSummary as ProcLogSum_Direct,
} from '../capabilities';

// ===========================================================================
// Smoke coverage: each module family is exercised through a focused test
// that confirms its representative names are reachable and well-formed.
// ===========================================================================

// ── ids ────────────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — ids', () => {
  it('validateExtensionId is callable from the barrel and returns an array', () => {
    const result = validateExtensionId('my.extension');
    expect(Array.isArray(result)).toBe(true);
    expect(result).toEqual([]);
  });

  it('validateExtensionId rejects empty strings', () => {
    const result = validateExtensionId('');
    expect(result.length).toBeGreaterThan(0);
  });

  it('validateContributionId delegates to the same validation logic', () => {
    expect(validateContributionId('my.extension')).toEqual([]);
    expect(validateContributionId('')).toEqual(validateExtensionId(''));
  });

  it('canonical direct import yields the same function', () => {
    const barrelResult = validateExtensionId('test.id');
    const directResult = validateExtId_Direct('test.id');
    expect(directResult).toEqual(barrelResult);
  });
});

// ── dispose ────────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — dispose', () => {
  it('DisposeHandle type is importable from the barrel (structural check)', () => {
    const handle: DisposeHandle = { dispose: () => {} };
    expect(typeof handle.dispose).toBe('function');
    handle.dispose(); // should not throw
  });

  it('DisposeHandle type is importable from canonical direct path', () => {
    const handle: DisposeHandle_Direct = { dispose: () => {} };
    expect(typeof handle.dispose).toBe('function');
    handle.dispose();
  });
});

// ── diagnostics ────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — diagnostics', () => {
  it('createDiagnosticCollection is callable from the barrel', () => {
    const coll = createDiagnosticCollection();
    expect(coll).toBeDefined();
    expect(Array.isArray(coll.snapshot)).toBe(true);
    expect(coll.snapshot.length).toBe(0);
  });

  it('DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY is a positive number', () => {
    expect(DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY).toBeGreaterThan(0);
  });

  it('DIAGNOSTIC_SOURCE_EXTENSION is the literal "extension"', () => {
    expect(DIAGNOSTIC_SOURCE_EXTENSION).toBe('extension');
  });

  it('canonical direct import yields the same constants', () => {
    const coll = createDiagColl_Direct();
    expect(coll).toBeDefined();
    expect(DIAG_SRC_EXT_Direct).toBe('extension');
    expect(DEFAULT_DIAG_CAP_Direct).toBe(DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY);
  });

  it('publish + snapshot works through barrel import', () => {
    const coll = createDiagnosticCollection();
    coll.publish({
      id: 'test.1',
      severity: 'info',
      code: 'test/info',
      message: 'hello',
    });
    expect(coll.snapshot.length).toBe(1);
    expect(coll.snapshot[0].id).toBe('test.1');
  });
});

// ── manifest / validation ──────────────────────────────────────────────────

describe('M2a barrel-import smoke — manifest / validation', () => {
  it('KNOWN_CONTRIBUTION_KINDS_SET is a Set with expected members', () => {
    expect(KNOWN_CONTRIBUTION_KINDS_SET instanceof Set).toBe(true);
    expect(KNOWN_CONTRIBUTION_KINDS_SET.has('slot')).toBe(true);
    expect(KNOWN_CONTRIBUTION_KINDS_SET.has('command')).toBe(true);
  });

  it('ALL_VALID_PLACEMENTS is a readonly array', () => {
    expect(Array.isArray(ALL_VALID_PLACEMENTS)).toBe(true);
    expect(ALL_VALID_PLACEMENTS.length).toBeGreaterThan(0);
    expect(ALL_VALID_PLACEMENTS).toContain('before-default');
  });

  it('canonical direct import yields the same values', () => {
    expect(KNOWN_CONTRIB_KINDS_SET_Direct).toBe(KNOWN_CONTRIBUTION_KINDS_SET);
    expect(ALL_VALID_PLACEMENTS_Direct).toEqual(ALL_VALID_PLACEMENTS);
    // Both paths reference the exact same objects (module singleton)
    expect(KNOWN_CONTRIB_KINDS_SET_Direct).toBe(KNOWN_CONTRIBUTION_KINDS_SET);
    expect(ALL_VALID_PLACEMENTS_Direct).toBe(ALL_VALID_PLACEMENTS);
  });
});

// ── packaging ──────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — packaging', () => {
  it('DependencyPosture accepts valid literal', () => {
    const posture: DependencyPosture = 'required';
    expect(posture).toBe('required');
  });

  it('MigrationHookKind accepts valid literal', () => {
    const kind: MigrationHookKind = 'settings';
    expect(kind).toBe('settings');
  });

  it('InstalledExtensionMetadata has expected shape', () => {
    const meta: InstalledExtensionMetadata = {
      extensionId: 'com.example' as ExtensionId,
      version: '1.0.0',
      integrity: { algorithm: 'sha256', value: 'abc123' },
      enabled: true,
    };
    expect(meta.extensionId).toBe('com.example');
    expect(meta.integrity.algorithm).toBe('sha256');
  });
});

// ── settings ───────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — settings', () => {
  it('ExtensionSettingsSchema has expected shape', () => {
    const schema: ExtensionSettingsSchema = { version: 1 };
    expect(schema.version).toBe(1);
  });

  it('createExtensionSettingsService is callable from the barrel', () => {
    const svc = createExtensionSettingsService('com.example' as ExtensionId, {
      id: 'com.example' as ExtensionId,
      label: 'test',
      apiVersion: 1,
    });
    expect(svc).toBeDefined();
    expect(svc.service).toBeDefined();
    expect(typeof svc.service.get).toBe('function');
    expect(typeof svc.service.set).toBe('function');
  });
});

// ── commands ───────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — commands', () => {
  it('TargetContext accepts valid literal', () => {
    const ctx: TargetContext = 'clip';
    expect(ctx).toBe('clip');
  });

  it('CommandHandler is a callable type', () => {
    const handler: CommandHandler = (_ctx) => {};
    expect(typeof handler).toBe('function');
  });
});

// ── chrome ─────────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — chrome', () => {
  it('ChromeEvent accepts valid union member', () => {
    const evt: ChromeEvent = 'toast';
    expect(evt).toBe('toast');
  });

  it('ChromeToastPayload has expected fields', () => {
    const payload: ChromeToastPayload = {
      message: 'hello',
      severity: 'info' as DiagnosticSeverity,
    };
    expect(payload.message).toBe('hello');
    expect(payload.severity).toBe('info');
  });
});

// ── context ────────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — context', () => {
  it('createCreativeContextStubs returns a frozen CreativeContext', () => {
    const ctx = createCreativeContextStubs();
    expect(ctx).toBeDefined();
    expect(Object.isFrozen(ctx)).toBe(true);
  });

  it('stub members throw ExtensionNotImplementedError', () => {
    const ctx = createCreativeContextStubs();
    expect(() => (ctx as any).timeline).toThrow(ExtensionNotImplementedError);
    try {
      (ctx as any).timeline;
    } catch (e) {
      expect(e).toBeInstanceOf(ExtensionNotImplementedError);
      expect((e as ExtensionNotImplementedError).feature).toBe('timeline');
    }
  });

  it('CREATIVE_MEMBER_MILESTONE is a record with expected keys', () => {
    expect(CREATIVE_MEMBER_MILESTONE).toBeDefined();
    expect(typeof CREATIVE_MEMBER_MILESTONE.project).toBe('string');
    expect(typeof CREATIVE_MEMBER_MILESTONE.timeline).toBe('string');
  });

  it('CONTEXT_DISPOSE_SYMBOL is a unique symbol', () => {
    expect(typeof CONTEXT_DISPOSE_SYMBOL).toBe('symbol');
  });

  it('canonical direct imports match barrel values', () => {
    const stubsViaBarrel = createCreativeContextStubs();
    const stubsViaDirect = createCreativeStubs_Direct();
    expect(stubsViaDirect).toBeDefined();
    expect(Object.isFrozen(stubsViaDirect)).toBe(true);

    expect(CREATIVE_MEMBER_MILESTONE_Direct).toBe(CREATIVE_MEMBER_MILESTONE);
    expect(CTX_DISPOSE_SYM_Direct).toBe(CONTEXT_DISPOSE_SYMBOL);
  });
});

// ── lifecycle ──────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — lifecycle', () => {
  it('defineExtension returns a frozen ReighExtension for a valid manifest', () => {
    const ext = defineExtension({
      manifest: {
        id: 'smoke.lifecycle',
        label: 'Smoke',
        apiVersion: 1,
      },
    });
    expect(ext).toBeDefined();
    expect(Object.isFrozen(ext)).toBe(true);
    expect(ext.manifest.id).toBe('smoke.lifecycle');
  });

  it('defineExtension throws on invalid extension ID', () => {
    expect(() =>
      defineExtension({
        manifest: { id: '', label: 'Bad', apiVersion: 1 },
      }),
    ).toThrow();
  });

  it('canonical direct import defineExtension matches barrel', () => {
    const barrelExt = defineExtension({
      manifest: { id: 'smoke.canon', label: 'Canon', apiVersion: 1 },
    });
    const directExt = defExt_Direct({
      manifest: { id: 'smoke.canon', label: 'Canon', apiVersion: 1 },
    });
    expect(directExt.manifest.id).toBe(barrelExt.manifest.id);
    expect(directExt.manifest.label).toBe(barrelExt.manifest.label);
  });
});

// ── capabilities ───────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — capabilities', () => {
  it('CapabilityRequirement type is importable from the barrel', () => {
    const req: CapabilityRequirement = {
      id: 'test.req',
      sourceRef: { source: 'built-in' },
      route: 'browser-export',
      requiredCapabilities: ['browser-export'],
      determinism: 'deterministic',
    };
    expect(req.id).toBe('test.req');
    expect(req.sourceRef.source).toBe('built-in');
  });

  it('SamplingConfig type is importable from the barrel', () => {
    const cfg: SamplingConfig = {
      strategy: 'whole-timeline',
      sources: [{ kind: 'timeline', id: 't1' }],
    };
    expect(cfg.strategy).toBe('whole-timeline');
    expect(cfg.sources[0].kind).toBe('timeline');
  });

  it('ProcessRoundtripResult type is importable from the barrel', () => {
    const result: ProcessRoundtripResult = {
      requestId: 'r1',
      processId: 'p1',
      operationId: 'op1',
      status: 'completed',
      returnedMaterials: [],
    };
    expect(result.status).toBe('completed');
  });
});

// ===========================================================================
// Cross-cutting: barrel and direct imports refer to identical runtime values
// ===========================================================================

describe('M2a barrel-import smoke — cross-cutting identity', () => {
  it('value exports (not type-exports) are identical regardless of import path', () => {
    // Value exports from ids
    expect(validateExtId_Direct).toBe(validateExtensionId);

    // Value exports from diagnostics
    expect(DIAG_SRC_EXT_Direct).toBe(DIAGNOSTIC_SOURCE_EXTENSION);
    expect(DEFAULT_DIAG_CAP_Direct).toBe(DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY);
    expect(createDiagColl_Direct).toBe(createDiagnosticCollection);

    // Value exports from manifest
    expect(KNOWN_CONTRIB_KINDS_SET_Direct).toBe(KNOWN_CONTRIBUTION_KINDS_SET);
    expect(ALL_VALID_PLACEMENTS_Direct).toBe(ALL_VALID_PLACEMENTS);

    // Value exports from context
    expect(createCreativeStubs_Direct).toBe(createCreativeContextStubs);
    expect(NotImplErr_Direct).toBe(ExtensionNotImplementedError);
    expect(CREATIVE_MEMBER_MILESTONE_Direct).toBe(CREATIVE_MEMBER_MILESTONE);
    expect(disposeExtCtxSvc_Direct).toBe(disposeExtensionContextServices);
    expect(CTX_DISPOSE_SYM_Direct).toBe(CONTEXT_DISPOSE_SYMBOL);

    // Value exports from lifecycle
    expect(defExt_Direct).toBe(defineExtension);
  });
});
