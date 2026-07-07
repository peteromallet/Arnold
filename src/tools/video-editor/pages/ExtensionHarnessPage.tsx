/**
 * ExtensionHarnessPage — Deterministic test harness route for Playwright e2e.
 *
 * Renders ExtensionManager and ExtensionActivityRegion in populated, empty,
 * package-error, and repaired-settings states using mock VideoEditorRuntimeContextValue
 * injected through DataProviderWrapper. Also exposes a dedicated manager-cycle
 * scenario backed by the real BrowserVideoEditorProvider, persistence
 * repository, loader re-resolution, and smoke contribution rendering.
 *
 * Usage: /tools/video-editor/harness?scenario=populated|empty|package-error|repaired-settings|manager-cycle|all
 *
 * Only mounted when import.meta.env.DEV is true.
 */

import { useEffect, useMemo, useState, type FC } from 'react';
import { useSearchParams } from 'react-router-dom';
import { BrowserVideoEditorProvider } from '@/tools/video-editor/browser/BrowserVideoEditorProvider';
import {
  DataProviderWrapper,
  useVideoEditorRuntime,
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext';
import { ExtensionManager } from '@/tools/video-editor/components/ExtensionManager/ExtensionManager';
import { ExtensionActivityRegion, type ExtensionStatusEvent } from '@/tools/video-editor/components/ExtensionActivityRegion';
import {
  EXTENSION_SMOKE_ACTIVE_VALUE,
  EXTENSION_SMOKE_QUERY_PARAM,
  getExtensionSmokeExtension,
} from '@/sdk/smoke/extensionSmoke';
import { useVideoEditorRenderContext, useVideoEditorSlotRenderers } from '@/tools/video-editor/runtime/useVideoEditorRenderContext';
import { InMemoryDataProvider } from '@/tools/video-editor/testing/InMemoryDataProvider';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
import type {
  Diagnostic,
  DiagnosticCollection,
  DisposeHandle,
  ExtensionDiagnostic,
} from '@reigh/editor-sdk';
import type { PackageStateInventoryEntry, ExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface';
import type { ExtensionStateRepository } from '@/tools/video-editor/runtime/extensionStateRepository';

// ---------------------------------------------------------------------------
// Scenario type
// ---------------------------------------------------------------------------

export type HarnessScenario =
  | 'populated'
  | 'empty'
  | 'package-error'
  | 'repaired-settings'
  | 'manager-cycle'
  | 'all';

type MockHarnessScenario = Exclude<HarnessScenario, 'manager-cycle' | 'all'>;

const VALID_SCENARIOS: ReadonlySet<string> = new Set([
  'populated',
  'empty',
  'package-error',
  'repaired-settings',
  'manager-cycle',
  'all',
]);

const MANAGER_CYCLE_TIMELINE_ID = 'extension-harness-manager-cycle';
const MANAGER_CYCLE_USER_ID = 'extension-harness-user';
const MANAGER_CYCLE_PROJECT_ID = 'extension-harness-project';
const MANAGER_CYCLE_EXTENSION_ID = 'com.reigh.smoke.extension-smoke';

// ---------------------------------------------------------------------------
// Mock DiagnosticCollection
// ---------------------------------------------------------------------------

class MockDiagnosticCollection implements DiagnosticCollection {
  private _diagnostics: Diagnostic[] = [];
  private _listeners = new Set<() => void>();

  setDiagnostics(diags: Diagnostic[]) {
    this._diagnostics = diags;
    for (const l of this._listeners) l();
  }

  getSnapshot(): readonly Diagnostic[] {
    return this._diagnostics;
  }

  subscribe(listener: () => void): DisposeHandle {
    this._listeners.add(listener);
    let disposed = false;
    return {
      dispose: () => {
        if (disposed) return;
        disposed = true;
        this._listeners.delete(listener);
      },
    };
  }
}

// ---------------------------------------------------------------------------
// Mock ExtensionStateRepository (no-op)
// ---------------------------------------------------------------------------

function makeMockRepository(): ExtensionStateRepository {
  return {
    initialize: async () => {},
    dispose: async () => {},
    isDisposed: false,
    putPackRecord: async () => {},
    updatePackRecord: async () => {},
    getPackRecord: async () => null,
    getAllPackRecords: async () => [],
    deletePackRecord: async () => {},
    putEnablementState: async () => {},
    getEnablementState: async () => null,
    getAllEnablementStates: async () => [],
    deleteEnablementState: async () => {},
    putDevOverride: async () => {},
    getDevOverride: async () => null,
    getAllDevOverrides: async () => [],
    deleteDevOverride: async () => {},
    putSettingsSnapshot: async () => {},
    getSettingsSnapshot: async () => null,
    getAllSettingsSnapshots: async () => [],
    deleteSettingsSnapshot: async () => {},
    appendLifecycleEvent: async () => {},
    queryLifecycleEvents: async () => [],
    getLifecycleEvents: async () => [],
    getLock: async () => ({ entries: {}, lastUpdatedAt: '' }),
    putLockEntry: async () => {},
    deleteLockEntry: async () => {},
    getFullExtensionState: async () => ({ enablement: {}, devOverrides: {}, settings: {}, packs: {} }),
  };
}

// ---------------------------------------------------------------------------
// Mock ExtensionRuntime (minimal for ExtensionManager)
// ---------------------------------------------------------------------------

function makeEmptyExtensionRuntime(): ExtensionRuntime {
  return {
    config: {
      slots: {},
      dialogHost: { dialogs: [] },
      registry: { panels: [], inspectorSections: [] },
      overlays: [],
      assetParsers: [],
      outputFormats: [],
      processes: [],
      searchProviders: [],
      metadataFacets: [],
      assetDetailSections: [],
      effects: [],
      transitions: [],
      shaders: [],
      agentTools: [],
    },
    extensions: [],
    diagnostics: [],
    inactiveReserved: [],
    knownRenderIds: new Set(),
    contributionIndex: {},
    compositionGraph: {
      nodes: [{ id: 'timeline-postprocess', kind: 'timeline-postprocess', detail: { scope: 'postprocess' } }],
      edges: [],
      referenceStates: [],
      diagnostics: [],
    },
    settingsDefaults: {},
    assetParsers: [],
    outputFormats: [],
    processes: [],
    searchProviders: [],
    metadataFacets: [],
    assetDetailSections: [],
    effects: [],
    transitions: [],
    shaders: [],
    agentTools: [],
    requirements: [],
    packageStateInventory: [],
  };
}

// ---------------------------------------------------------------------------
// Scenario builders
// ---------------------------------------------------------------------------

function makeEntry(overrides: Partial<PackageStateInventoryEntry> & { extensionId: string; packageState: PackageStateInventoryEntry['packageState'] }): PackageStateInventoryEntry {
  return {
    stateReason: '',
    packageMetadata: null,
    ...overrides,
  };
}

interface ScenarioData {
  packageStateInventory: PackageStateInventoryEntry[];
  diagnostics: Diagnostic[];
  activityEvents: ExtensionStatusEvent[];
}

function buildPopulatedScenario(): ScenarioData {
  const now = Date.now();
  return {
    packageStateInventory: [
      makeEntry({
        extensionId: 'ext.inspector-tools',
        packageState: 'loaded',
        stateReason: '',
        packageMetadata: { label: 'Inspector Tools', version: '1.2.0', publisher: 'Reigh', description: 'Adds inspector sections for clip metadata.' },
        contributionSummary: { declared: 3, active: 3, inactive: 0, kinds: ['Inspector section'] },
      }),
      makeEntry({
        extensionId: 'ext.shader-pack',
        packageState: 'loaded',
        stateReason: '',
        packageMetadata: { label: 'Shader Pack', version: '2.0.1', publisher: 'Studio FX', description: 'Custom GLSL shaders for timeline rendering.' },
        contributionSummary: { declared: 5, active: 4, inactive: 1, kinds: ['Shader'] },
      }),
      makeEntry({
        extensionId: 'ext.effect-bundle',
        packageState: 'loaded',
        stateReason: '',
        packageMetadata: { label: 'Effect Bundle', version: '0.9.0', publisher: 'Motion Lab', description: 'Collection of video effects and transitions.' },
        contributionSummary: { declared: 8, active: 8, inactive: 0, kinds: ['Effect', 'Transition'] },
      }),
    ],
    diagnostics: [
      { id: 'd1', severity: 'info', message: 'All systems operational.', extensionId: 'ext.inspector-tools', timestamp: now },
      { id: 'd2', severity: 'warning', message: 'Shader "glow" uses deprecated uniform syntax.', extensionId: 'ext.shader-pack', timestamp: now - 60000, code: 'shader/deprecated-uniform' },
    ],
    activityEvents: [
      { id: 'ev1', extensionId: 'ext.inspector-tools', kind: 'success', message: 'Inspector sections registered.', timestamp: now },
      { id: 'ev2', extensionId: 'ext.shader-pack', kind: 'info', message: 'Shaders compiled successfully.', timestamp: now - 30000 },
      { id: 'ev3', extensionId: 'ext.effect-bundle', kind: 'warning', message: 'Transition "wipe" missing preview thumbnail.', timestamp: now - 60000 },
    ],
  };
}

function buildEmptyScenario(): ScenarioData {
  return {
    packageStateInventory: [],
    diagnostics: [],
    activityEvents: [],
  };
}

function buildPackageErrorScenario(): ScenarioData {
  return {
    packageStateInventory: [
      makeEntry({
        extensionId: 'ext.broken-config',
        packageState: 'settings-error',
        stateReason: 'Settings schema validation failed: unknown field "renderMode"',
        packageMetadata: { label: 'Broken Config', version: '0.1.0', publisher: 'Unknown', description: 'Extension with invalid settings schema.' },
        contributionSummary: { declared: 2, active: 0, inactive: 0, kinds: ['Effect'] },
      }),
      makeEntry({
        extensionId: 'ext.runtime-crash',
        packageState: 'runtime-error',
        stateReason: 'Uncaught TypeError: Cannot read properties of undefined',
        packageMetadata: { label: 'Runtime Crash', version: '1.0.0', publisher: 'Buggy Inc.', description: 'Extension that crashes on activation.' },
        contributionSummary: { declared: 4, active: 0, inactive: 0, kinds: ['Panel', 'Inspector section'] },
      }),
      makeEntry({
        extensionId: 'ext.invalid-manifest',
        packageState: 'invalid',
        stateReason: 'Manifest missing required field "id"',
        packageMetadata: { label: 'Invalid Manifest', version: '?.?.?', publisher: null, description: 'Corrupted extension manifest.' },
      }),
      makeEntry({
        extensionId: 'ext.old-api',
        packageState: 'incompatible',
        stateReason: 'Requires editor API v2 but host provides v3',
        packageMetadata: { label: 'Old API Extension', version: '3.0.0', publisher: 'Legacy Co.', description: 'Built for an older editor API version.' },
        contributionSummary: { declared: 6, active: 0, inactive: 0, kinds: ['Slot', 'Overlay'] },
      }),
      makeEntry({
        extensionId: 'ext.duplicate-pack',
        packageState: 'duplicate',
        stateReason: 'Duplicate of ext.effect-bundle (same publisher and version)',
        packageMetadata: { label: 'Effect Bundle (copy)', version: '0.9.0', publisher: 'Motion Lab', description: 'Duplicate package.' },
        contributionSummary: { declared: 8, active: 0, inactive: 0, kinds: ['Effect', 'Transition'] },
      }),
    ],
    diagnostics: [
      { id: 'de1', severity: 'error', message: 'Settings schema validation failed.', extensionId: 'ext.broken-config', code: 'settings/invalid-schema', timestamp: Date.now() },
      { id: 'de2', severity: 'error', message: 'Uncaught TypeError: Cannot read properties of undefined (reading "render")', extensionId: 'ext.runtime-crash', code: 'runtime/uncaught-error', timestamp: Date.now() },
      { id: 'de3', severity: 'error', message: 'Manifest validation: missing required field "id".', extensionId: 'ext.invalid-manifest', code: 'manifest/missing-id', timestamp: Date.now() },
      { id: 'de4', severity: 'warning', message: 'Extension ext.old-api requires API v2 but host provides v3.', extensionId: 'ext.old-api', code: 'compat/api-mismatch', timestamp: Date.now() },
      { id: 'de5', severity: 'info', message: 'Duplicate package detected.', extensionId: 'ext.duplicate-pack', code: 'pack/duplicate', timestamp: Date.now() },
    ],
    activityEvents: [
      { id: 'ev-err1', extensionId: 'ext.broken-config', kind: 'error', message: 'Failed to reconcile settings schema.', timestamp: Date.now() },
      { id: 'ev-err2', extensionId: 'ext.runtime-crash', kind: 'error', message: 'Extension activation failed with uncaught error.', timestamp: Date.now() - 1000 },
      { id: 'ev-err3', extensionId: 'ext.invalid-manifest', kind: 'error', message: 'Manifest validation failed.', timestamp: Date.now() - 2000 },
      { id: 'ev-err4', extensionId: 'ext.old-api', kind: 'warning', message: 'API version mismatch detected.', timestamp: Date.now() - 3000 },
    ],
  };
}

function buildRepairedSettingsScenario(): ScenarioData {
  return {
    packageStateInventory: [
      makeEntry({
        extensionId: 'ext.repaired-config',
        packageState: 'loaded',
        stateReason: '',
        packageMetadata: { label: 'Repaired Config', version: '1.0.0', publisher: 'Auto-Fix Labs', description: 'Settings were auto-repaired on load.' },
        contributionSummary: { declared: 2, active: 2, inactive: 0, kinds: ['Inspector section'] },
      }),
      makeEntry({
        extensionId: 'ext.needs-review',
        packageState: 'loaded',
        stateReason: '',
        packageMetadata: { label: 'Review Needed', version: '2.1.0', publisher: 'Pending Co.', description: 'Settings need manual review after migration.' },
        contributionSummary: { declared: 3, active: 2, inactive: 1, kinds: ['Effect'] },
      }),
      makeEntry({
        extensionId: 'ext.settings-blocked',
        packageState: 'loaded',
        stateReason: '',
        packageMetadata: { label: 'Blocked Settings', version: '0.5.0', publisher: 'Complex Schema Inc.', description: 'Settings schema contains unsupported $ref constructs.' },
        contributionSummary: { declared: 1, active: 0, inactive: 0, kinds: ['Panel'] },
      }),
    ],
    diagnostics: [
      { id: 'ds1', severity: 'info', message: 'Settings auto-repaired: default values filled for missing keys.', extensionId: 'ext.repaired-config', code: 'settings/repaired', timestamp: Date.now() },
      { id: 'ds2', severity: 'warning', message: 'Settings need review: 2 fields were type-coerced during migration.', extensionId: 'ext.needs-review', code: 'settings/needs-review', timestamp: Date.now() },
      { id: 'ds3', severity: 'warning', message: 'Settings schema blocked: $ref constructs are not supported.', extensionId: 'ext.settings-blocked', code: 'settings/unsupported-schema', timestamp: Date.now() },
    ],
    activityEvents: [
      { id: 'ev-rep1', extensionId: 'ext.repaired-config', kind: 'success', message: 'Settings auto-repaired on activation.', timestamp: Date.now() },
      { id: 'ev-rep2', extensionId: 'ext.needs-review', kind: 'warning', message: 'Settings migration requires manual review.', timestamp: Date.now() - 1000 },
      { id: 'ev-rep3', extensionId: 'ext.settings-blocked', kind: 'warning', message: 'Settings schema contains unsupported constructs.', timestamp: Date.now() - 2000 },
    ],
  };
}

// ---------------------------------------------------------------------------
// Scenario card wrapper
// ---------------------------------------------------------------------------

const ScenarioCard: FC<{
  title: string;
  description: string;
  scenario: HarnessScenario;
  data: ScenarioData;
}> = ({ title, description, data }) => {
  const mockDiagnostics = useMemo(() => {
    const coll = new MockDiagnosticCollection();
    coll.setDiagnostics(data.diagnostics);
    return coll;
  }, [data.diagnostics]);

  const mockExtensionRuntime = useMemo<ExtensionRuntime>(() => {
    const base = makeEmptyExtensionRuntime();
    return {
      ...base,
      packageStateInventory: data.packageStateInventory,
    };
  }, [data.packageStateInventory]);

  const mockContextValue = useMemo<VideoEditorRuntimeContextValue>(() => ({
    provider: {} as unknown as DataProvider,
    assetResolver: { resolveAssetUrl: async (f: string) => f },
    auth: { userId: 'harness' },
    project: { projectId: null },
    shots: { shots: undefined, isLoading: false, error: null, refetchShots: () => {}, finalVideoMap: new Map(), dismissFinalVideo: () => {} },
    mediaLightbox: { Lightbox: (() => null) as unknown as VideoEditorRuntimeContextValue['mediaLightbox']['Lightbox'], loadGenerationForLightbox: async () => null },
    agentChat: { registerTimeline: () => {}, unregisterTimeline: () => {} },
    toast: { error: () => '', success: () => '', warning: () => '', info: () => '' },
    telemetry: { log: () => {}, warn: () => {}, error: () => {} },
    timelineId: 'harness-timeline',
    userId: 'harness-user',
    extensions: mockExtensionRuntime.config,
    extensionRuntime: mockExtensionRuntime,
    diagnosticCollection: mockDiagnostics,
    extensionStateRepository: makeMockRepository(),
    triggerExtensionRefresh: () => {},
  }), [mockExtensionRuntime, mockDiagnostics]);

  return (
    <div
      className="rounded-xl border-2 border-border bg-card/40 p-4"
      data-video-editor-harness-scenario={title.toLowerCase().replace(/\s+/g, '-')}
    >
      <div className="mb-3 border-b border-border pb-2">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>

      {/* Activity Region */}
      <div className="mb-4">
        <h3 className="mb-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Activity Region
        </h3>
        <ExtensionActivityRegion
          statusEvents={data.activityEvents}
          onDismiss={() => {}}
          isExpanded={false}
        />
      </div>

      {/* Extension Manager */}
      <div>
        <h3 className="mb-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Extension Manager
        </h3>
        <div className="rounded-lg border border-border bg-card/30 p-3">
          <DataProviderWrapper value={mockContextValue}>
            <ExtensionManager />
          </DataProviderWrapper>
        </div>
      </div>
    </div>
  );
};

function ManagerCycleContributionProbe() {
  const { extensionRuntime, extensionStateRepository } = useVideoEditorRuntime();
  const renderContext = useVideoEditorRenderContext();
  const slotRenderers = useVideoEditorSlotRenderers();
  const [persistedEnablement, setPersistedEnablement] = useState('loading');

  const packageState =
    extensionRuntime?.packageStateInventory.find(
      (entry) => entry.extensionId === MANAGER_CYCLE_EXTENSION_ID,
    )?.packageState ?? 'missing';

  useEffect(() => {
    let cancelled = false;

    async function syncPersistedEnablement() {
      if (!extensionStateRepository) {
        if (!cancelled) {
          setPersistedEnablement('unavailable');
        }
        return;
      }

      const enablement = await extensionStateRepository.getEnablementState(
        MANAGER_CYCLE_EXTENSION_ID,
      );

      if (!cancelled) {
        setPersistedEnablement(enablement?.enabled === false ? 'disabled' : 'enabled');
      }
    }

    syncPersistedEnablement().catch(() => {
      if (!cancelled) {
        setPersistedEnablement('error');
      }
    });

    return () => {
      cancelled = true;
    };
  }, [extensionStateRepository, packageState]);

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-border bg-card/30 p-3">
        <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Persistence Probe
        </div>
        <div className="mt-2 grid gap-2 text-sm text-foreground sm:grid-cols-2">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Package State
            </div>
            <div data-testid="extension-manager-cycle-package-state">{packageState}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Persisted Enablement
            </div>
            <div data-testid="extension-manager-cycle-persisted-enablement">{persistedEnablement}</div>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card/30 p-3">
        <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Status Bar Surface
        </div>
        <div className="mt-2" data-testid="extension-manager-cycle-status-surface">
          {slotRenderers.statusBar
            ? slotRenderers.statusBar(renderContext)
            : (
              <span data-testid="extension-manager-cycle-no-contribution">
                No active status-bar contribution
              </span>
            )}
        </div>
      </div>
    </div>
  );
}

function ManagerCycleScenarioCard() {
  const [dataProvider] = useState(
    () => new InMemoryDataProvider({ [MANAGER_CYCLE_TIMELINE_ID]: {} }),
  );
  const [repository, setRepository] = useState<ExtensionStateRepository | null | undefined>(
    undefined,
  );
  const [initializationError, setInitializationError] = useState<string | null>(null);
  const smokeExtension = useMemo(
    () =>
      getExtensionSmokeExtension(
        `?${EXTENSION_SMOKE_QUERY_PARAM}=${EXTENSION_SMOKE_ACTIVE_VALUE}`,
      ),
    [],
  );

  useEffect(() => {
    const diagnostics: ExtensionDiagnostic[] = [];
    const service = dataProvider.createExtensionPersistenceService(
      {
        userId: MANAGER_CYCLE_USER_ID,
        timelineId: MANAGER_CYCLE_TIMELINE_ID,
      },
      diagnostics,
    );

    let disposed = false;

    service.initialize().then(() => {
      if (disposed) {
        service.dispose().catch(() => {});
        return;
      }

      setRepository(service.stateRepository);
    }).catch((error) => {
      if (!disposed) {
        setInitializationError(
          error instanceof Error ? error.message : 'Failed to initialize extension persistence.',
        );
      }
    });

    return () => {
      disposed = true;
      service.dispose().catch(() => {});
    };
  }, [dataProvider]);

  if (!smokeExtension) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
        Smoke extension is unavailable.
      </div>
    );
  }

  if (initializationError) {
    return (
      <div
        className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400"
        role="alert"
      >
        {initializationError}
      </div>
    );
  }

  if (repository === undefined) {
    return (
      <div className="rounded-lg border border-border bg-card/30 p-3 text-sm text-muted-foreground">
        Initializing real extension manager harness…
      </div>
    );
  }

  return (
    <BrowserVideoEditorProvider
      dataProvider={dataProvider}
      timelineId={MANAGER_CYCLE_TIMELINE_ID}
      timelineName="Extension Harness Manager Cycle"
      userId={MANAGER_CYCLE_USER_ID}
      hostContext={{ projectId: MANAGER_CYCLE_PROJECT_ID }}
      repository={repository}
      extensions={[smokeExtension]}
    >
      <div className="space-y-4 rounded-xl border-2 border-border bg-card/40 p-4">
        <div className="border-b border-border pb-2">
          <h2 className="text-base font-semibold text-foreground">Manager Cycle</h2>
          <p className="text-xs text-muted-foreground">
            Real repository-backed enable/disable cycle with loader re-resolution and live slot rendering.
          </p>
        </div>
        <div className="space-y-1">
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Extension Manager
          </h3>
          <div className="rounded-lg border border-border bg-card/30 p-3">
            <ExtensionManager />
          </div>
        </div>
        <ManagerCycleContributionProbe />
      </div>
    </BrowserVideoEditorProvider>
  );
}

// ---------------------------------------------------------------------------
// Main harness page
// ---------------------------------------------------------------------------

function buildScenarioData(scenario: MockHarnessScenario): ScenarioData {
  switch (scenario) {
    case 'populated':
      return buildPopulatedScenario();
    case 'empty':
      return buildEmptyScenario();
    case 'package-error':
      return buildPackageErrorScenario();
    case 'repaired-settings':
      return buildRepairedSettingsScenario();
  }
}

const SCENARIO_META: Record<MockHarnessScenario, { title: string; description: string }> = {
  populated: {
    title: 'Populated',
    description: 'Multiple loaded extensions with active contributions, diagnostics, and status events.',
  },
  empty: {
    title: 'Empty',
    description: 'No extensions loaded. Trust warning banner and empty state message.',
  },
  'package-error': {
    title: 'Package Error',
    description: 'Extensions in error states: settings-error, runtime-error, invalid, incompatible, duplicate.',
  },
  'repaired-settings': {
    title: 'Repaired Settings',
    description: 'Extensions with settings reconciliation states: repaired, needs-review, and blocked.',
  },
};

export default function ExtensionHarnessPage() {
  const [searchParams] = useSearchParams();
  const scenarioParam = searchParams.get('scenario') ?? 'populated';

  const scenario: HarnessScenario = VALID_SCENARIOS.has(scenarioParam)
    ? (scenarioParam as HarnessScenario)
    : 'populated';

  if (scenario === 'all') {
    // Render all scenarios in a grid
    const scenarios = ['populated', 'empty', 'package-error', 'repaired-settings'] as const;
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-foreground">Extension Harness — All Scenarios</h1>
          <p className="text-sm text-muted-foreground">
            Deterministic test harness for Extension Activity Region and Manager states.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          {scenarios.map((s) => (
            <ScenarioCard
              key={s}
              title={SCENARIO_META[s].title}
              description={SCENARIO_META[s].description}
              scenario={s}
              data={buildScenarioData(s)}
            />
          ))}
        </div>
      </div>
    );
  }

  if (scenario === 'manager-cycle') {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-foreground">
            Extension Harness — Manager Cycle
          </h1>
          <p className="text-sm text-muted-foreground">
            Real extension-manager enablement flow with repository persistence and contribution re-resolution.
          </p>
        </div>
        <ManagerCycleScenarioCard />
      </div>
    );
  }

  // Single scenario
  const data = buildScenarioData(scenario);
  return (
    <div className="min-h-screen bg-background p-6">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-foreground">
          Extension Harness — {SCENARIO_META[scenario]?.title ?? scenario}
        </h1>
        <p className="text-sm text-muted-foreground">
          {SCENARIO_META[scenario]?.description ?? 'Deterministic test harness for extension states.'}
        </p>
      </div>
      <ScenarioCard
        title={SCENARIO_META[scenario]?.title ?? scenario}
        description={SCENARIO_META[scenario]?.description ?? ''}
        scenario={scenario}
        data={data}
      />
    </div>
  );
}
