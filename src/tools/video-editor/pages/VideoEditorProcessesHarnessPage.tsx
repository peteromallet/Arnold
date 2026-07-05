import { useCallback, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type {
  DataProvider,
  ProcessRoundtripRequest,
  ProcessRoundtripResult,
  ProcessStatus,
  RenderArtifact,
  RenderArtifactSidecarDescriptor,
  RenderMaterial,
  RenderRoute,
} from '@reigh/editor-sdk';
import {
  BlockerActionCard,
  normalizeBlockerActionCardNextAction,
} from '@/tools/video-editor/components/BlockerActionCard.tsx';
import { ProcessDashboard } from '@/tools/video-editor/components/ProcessDashboard/ProcessDashboard.tsx';
import { RoundtripResultsPanel } from '@/tools/video-editor/components/RoundtripResultsPanel.tsx';
import {
  DataProviderWrapper,
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { projectHostMaterialRuntime } from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import {
  createProcessResultAttachRecord,
  projectProcessResultContracts,
  type ProcessResultAttachRecord,
} from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import type {
  VideoEditorOutputFormatDescriptor,
  VideoEditorPlannerNextActionDescriptor,
  VideoEditorProcessDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { ProcessManager } from '@/tools/video-editor/runtime/processes/ProcessManager.ts';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';

type ProcessHarnessScenario = 'happy-path' | 'stopped-repair';

const VALID_SCENARIOS: ReadonlySet<ProcessHarnessScenario> = new Set([
  'happy-path',
  'stopped-repair',
]);

const ATTACHED_AT = '2026-07-05T00:00:00.000Z';
const PROCESS_ROUTE: RenderRoute = 'browser-export';
const PROCESS_ID = 'browser-fixture.process';
const PROCESS_DESCRIPTOR_ID = `${PROCESS_ID}.contribution`;
const OPERATION_ID = 'browser-fixture.execute';

const EMPTY_PROVIDER = null as unknown as DataProvider;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function createStatus(
  state: ProcessStatus['state'],
  details: Partial<ProcessStatus> = {},
): ProcessStatus {
  const message = details.message ?? (
    state === 'stopped'
      ? 'Fixture process is stopped.'
      : state === 'ready'
        ? 'Fixture process is ready.'
        : state === 'busy'
          ? 'Fixture process is executing.'
          : 'Fixture process status updated.'
  );

  return Object.freeze({
    processId: PROCESS_ID,
    label: 'Browser Fixture Process',
    state,
    updatedAt: new Date().toISOString(),
    ...details,
    message,
  });
}

function createHarnessDescriptor(): VideoEditorProcessDescriptor {
  return {
    id: PROCESS_DESCRIPTOR_ID,
    extensionId: 'ext.browser.fixture.process',
    processId: PROCESS_ID,
    label: 'Browser Fixture Process',
    description: 'Deterministic browser harness for M6b process UX acceptance.',
    spec: {
      id: PROCESS_ID,
      label: 'Browser Fixture Process',
      description: 'Browser-only trusted local fixture descriptor for Playwright acceptance.',
      protocol: 'stdio-jsonrpc',
      spawn: {
        command: 'browser-fixture',
        args: ['--playwright'],
      },
      healthCheck: 'health',
      shutdown: 'shutdown',
      restartPolicy: 'never',
      version: {
        semver: '1.0.0',
      },
      operations: [
        {
          id: OPERATION_ID,
          label: 'Fixture Execute',
          outputKinds: ['material', 'artifact', 'sidecar', 'diagnostic', 'tool-result'],
        },
      ],
    },
    protocol: 'stdio-jsonrpc',
    operations: [
      {
        id: OPERATION_ID,
        label: 'Fixture Execute',
        routes: [PROCESS_ROUTE],
        outputKinds: ['material', 'artifact', 'sidecar', 'diagnostic', 'tool-result'],
        requiredCapabilities: [PROCESS_ROUTE],
      },
    ],
    availableRoutes: [PROCESS_ROUTE],
    requiredBy: [
      {
        source: 'extension',
        extensionId: 'ext.browser.fixture.process',
        contributionId: 'dataset-output',
      },
    ],
    blockers: [],
    nextActions: [],
  };
}

function returnedMaterial(): RenderMaterial {
  return {
    id: 'fixture-material',
    mediaKind: 'image',
    locator: {
      kind: 'artifact-store',
      uri: 'artifact://fixture/material.png',
    },
    determinism: 'process-dependent',
    replacementPolicy: 'materialize-on-export',
    provenance: {
      origin: 'process',
    },
  };
}

function returnedArtifact(material: RenderMaterial): RenderArtifact {
  return {
    id: 'fixture-artifact',
    route: PROCESS_ROUTE,
    locator: {
      kind: 'artifact-store',
      uri: 'artifact://fixture/dataset.json',
      mimeType: 'application/json',
    },
    mediaKind: 'json',
    determinism: 'process-dependent',
    boundary: {
      source: 'browser-fixture',
      target: 'artifact-store',
      route: PROCESS_ROUTE,
      failureBehavior: 'emit-diagnostic',
    },
    consumedMaterialRefs: [material],
  };
}

function returnedSidecar(): RenderArtifactSidecarDescriptor {
  return {
    id: 'fixture-sidecar',
    filename: 'fixture.log',
    mimeType: 'text/plain',
    kind: 'log',
    locator: {
      kind: 'artifact-store',
      uri: 'artifact://fixture/fixture.log',
      mimeType: 'text/plain',
    },
    provenance: {
      source: 'browser-fixture',
    },
  };
}

function createResult(request: ProcessRoundtripRequest): ProcessRoundtripResult {
  const material = returnedMaterial();
  return {
    requestId: request.id,
    processId: request.processId,
    operationId: request.operationId,
    status: 'completed',
    returnedMaterials: [material],
    artifacts: [returnedArtifact(material)],
    sidecars: [returnedSidecar()],
    diagnostics: [
      {
        id: 'browser-fixture-warning',
        severity: 'warning',
        message: 'Fixture returned a warning.',
      },
    ],
    logs: [
      {
        level: 'info',
        message: 'Fixture finished.',
      },
    ],
    progress: {
      percent: 100,
      message: 'Fixture render complete.',
      operationId: request.operationId,
    },
    availableActions: ['create-proposal'],
    metadata: {
      scenario: 'browser-harness',
    },
  };
}

function createBrowserProcessManager(
  descriptor: VideoEditorProcessDescriptor,
  initialState: ProcessStatus['state'],
): ProcessManager {
  let status = createStatus(initialState);

  return {
    getDeclaredProcesses: () => [descriptor.spec],
    getProcessSpec: (processId) => (processId === descriptor.processId ? descriptor.spec : undefined),
    getStatus: (processId) => (processId === descriptor.processId ? status : undefined),
    listStatuses: () => [status],
    start: async (processId) => {
      if (processId !== descriptor.processId) {
        throw new Error(`Unknown process "${processId}".`);
      }
      status = createStatus('ready');
      return status;
    },
    checkHealth: async (processId) => {
      if (processId !== descriptor.processId) {
        throw new Error(`Unknown process "${processId}".`);
      }
      return status;
    },
    execute: async (request) => {
      if (request.processId !== descriptor.processId) {
        throw new Error(`Unknown process "${request.processId}".`);
      }
      if (status.state !== 'ready' && status.state !== 'degraded') {
        throw new Error('Start the fixture process before executing it.');
      }

      status = createStatus('busy', {
        operationId: request.operationId,
        progress: {
          percent: 20,
          message: 'Preparing fixture outputs.',
          operationId: request.operationId,
        },
        taskId: request.id,
      } as Partial<ProcessStatus>);
      await delay(50);
      const result = createResult(request);
      status = createStatus('ready');
      return result;
    },
    cancel: async (processId) => {
      if (processId !== descriptor.processId) {
        throw new Error(`Unknown process "${processId}".`);
      }
      status = createStatus('ready');
      return status;
    },
    shutdown: async (processId) => {
      if (processId !== descriptor.processId) {
        throw new Error(`Unknown process "${processId}".`);
      }
      status = createStatus('stopped');
      return status;
    },
    dispose: async () => {},
  };
}

function processOutputFormat(
  descriptor: VideoEditorProcessDescriptor,
): VideoEditorOutputFormatDescriptor {
  return {
    id: 'dataset-output',
    extensionId: descriptor.extensionId,
    order: 1,
    label: 'Dataset export',
    requiresRender: true,
    outputExtension: '.json',
    outputMimeType: 'application/json',
    disabled: false,
    availableRoutes: [PROCESS_ROUTE],
    routeRequirements: [
      {
        routes: [PROCESS_ROUTE],
        requiredCapabilities: [PROCESS_ROUTE],
        processId: descriptor.processId,
        operationId: OPERATION_ID,
        determinism: 'process-dependent',
        unavailableMessage: 'Start the fixture process before exporting the dataset.',
      },
    ],
    processRequirements: [
      {
        processId: descriptor.processId,
        operationId: OPERATION_ID,
        requiredCapabilities: [PROCESS_ROUTE],
      },
    ],
    blockers: [],
    nextActions: [
      {
        kind: 'select-route',
        label: 'Select browser export',
        route: PROCESS_ROUTE,
        processId: descriptor.processId,
        operationId: OPERATION_ID,
      },
    ],
    capabilities: {
      extensionId: descriptor.extensionId,
      contributionId: 'dataset-output',
      routes: [PROCESS_ROUTE],
      determinism: 'process-dependent',
      sourceRefs: [
        {
          source: 'extension',
          extensionId: descriptor.extensionId,
          contributionId: 'dataset-output',
        },
      ],
      capabilityRequirements: [
        {
          id: `ext.browser.fixture.process.dataset-output.${PROCESS_ROUTE}`,
          sourceRef: {
            source: 'extension',
            extensionId: descriptor.extensionId,
            contributionId: 'dataset-output',
          },
          route: PROCESS_ROUTE,
          requiredCapabilities: [PROCESS_ROUTE],
          determinism: 'process-dependent',
          routeFit: { route: PROCESS_ROUTE, fit: 'supported' },
          blocking: false,
        },
      ],
      fullySupported: true,
      anyBlocked: false,
    },
    sidecars: [],
  };
}

function createRuntimeValue(args: {
  descriptor: VideoEditorProcessDescriptor;
  manager: ProcessManager;
  statuses: readonly ProcessStatus[];
  attachRecords: readonly ProcessResultAttachRecord[];
}): VideoEditorRuntimeContextValue {
  const extensionRuntime = {
    config: {
      processes: [args.descriptor],
    },
    processes: [args.descriptor],
    settingsDefaults: {
      [args.descriptor.extensionId]: {
        endpoint: 'browser-fixture',
      },
    },
  } as VideoEditorRuntimeContextValue['extensionRuntime'];

  return {
    provider: EMPTY_PROVIDER,
    assetResolver: { resolveAssetUrl: async (path: string) => path },
    auth: { userId: 'process-harness-user' },
    project: { projectId: 'project-process-harness' },
    shots: {
      shots: undefined,
      isLoading: false,
      error: null,
      refetchShots: () => {},
      finalVideoMap: new Map(),
      dismissFinalVideo: () => {},
    },
    mediaLightbox: {
      Lightbox: (() => null) as unknown as VideoEditorRuntimeContextValue['mediaLightbox']['Lightbox'],
      loadGenerationForLightbox: async () => null,
    },
    agentChat: {
      registerTimeline: () => {},
      unregisterTimeline: () => {},
    },
    toast: {
      error: () => '',
      success: () => '',
      warning: () => '',
      info: () => '',
    },
    telemetry: {
      log: () => {},
      warn: () => {},
      error: () => {},
    },
    timelineId: 'timeline-process-harness',
    userId: 'process-harness-user',
    extensions: extensionRuntime.config as VideoEditorRuntimeContextValue['extensions'],
    extensionRuntime,
    processManager: args.manager,
    processStatuses: args.statuses,
    processResultAttachRecords: args.attachRecords,
  };
}

const SCENARIO_META: Record<ProcessHarnessScenario, { title: string; description: string; initialState: ProcessStatus['state'] }> = {
  'happy-path': {
    title: 'Happy Path',
    description: 'Ready process executes a local fixture and exposes process.result.attach provenance.',
    initialState: 'ready',
  },
  'stopped-repair': {
    title: 'Stopped Repair',
    description: 'Stopped process surfaces a route-scoped blocker and clears it through Start Process.',
    initialState: 'stopped',
  },
};

function ProcessHarnessScenarioView({
  scenario,
}: {
  scenario: ProcessHarnessScenario;
}) {
  const descriptor = useMemo(() => createHarnessDescriptor(), []);
  const manager = useMemo(
    () => createBrowserProcessManager(descriptor, SCENARIO_META[scenario].initialState),
    [descriptor, scenario],
  );
  const outputFormat = useMemo(() => processOutputFormat(descriptor), [descriptor]);
  const [statuses, setStatuses] = useState<readonly ProcessStatus[]>(() => manager.listStatuses());
  const [attachRecords, setAttachRecords] = useState<readonly ProcessResultAttachRecord[]>([]);
  const [latestResult, setLatestResult] = useState<ProcessRoundtripResult | null>(null);

  const refreshStatuses = useCallback(() => {
    setStatuses(manager.listStatuses());
  }, [manager]);

  const latestAttachRecord = attachRecords[attachRecords.length - 1];

  const handleStartProcess = useCallback(async () => {
    await manager.start(descriptor.processId);
    refreshStatuses();
  }, [descriptor.processId, manager, refreshStatuses]);

  const handleExecute = useCallback(async () => {
    const result = await manager.execute({
      id: 'fixture-task-1',
      processId: descriptor.processId,
      operationId: OPERATION_ID,
      params: {
        source: 'playwright-harness',
      },
    });
    const attachRecord = createProcessResultAttachRecord({
      processDescriptor: descriptor,
      result,
      attachedAt: ATTACHED_AT,
    });
    setLatestResult(result);
    setAttachRecords((current) => [...current, attachRecord]);
    refreshStatuses();
  }, [descriptor, manager, refreshStatuses]);

  const planner = useMemo(() => planRender({
    outputFormats: [outputFormat],
    processes: [descriptor],
    processStatuses: statuses,
    processResultAttachRecords: attachRecords,
  }), [attachRecords, descriptor, outputFormat, statuses]);

  const startProcessAction = planner.nextActions.find((action) => (
    action.kind === 'start-process' && action.processId === descriptor.processId
  )) as VideoEditorPlannerNextActionDescriptor | undefined;

  const projection = useMemo(
    () => (latestAttachRecord ? projectProcessResultContracts(latestAttachRecord) : {
      materialRefs: [],
      materialStatuses: [],
      artifacts: [],
      sidecars: [],
    }),
    [latestAttachRecord],
  );

  const materialRuntime = useMemo(() => projectHostMaterialRuntime({
    materialRefs: projection.materialRefs,
    materialStatuses: projection.materialStatuses,
    processes: [descriptor],
    processStatuses: statuses,
    processResultAttachRecords: attachRecords,
    requestedRoutes: [PROCESS_ROUTE],
    canonicalRoutes: [PROCESS_ROUTE],
  }), [attachRecords, descriptor, projection.materialRefs, projection.materialStatuses, statuses]);

  const contextValue = useMemo(() => createRuntimeValue({
    descriptor,
    manager,
    statuses,
    attachRecords,
  }), [attachRecords, descriptor, manager, statuses]);

  return (
    <div
      className="min-h-screen bg-background p-6"
      data-video-editor-process-harness-scenario={scenario}
    >
      <div className="mx-auto flex max-w-5xl flex-col gap-4">
        <header className="space-y-1">
          <h1 className="text-xl font-semibold text-foreground">
            Video Editor Process Harness — {SCENARIO_META[scenario].title}
          </h1>
          <p className="text-sm text-muted-foreground">
            {SCENARIO_META[scenario].description}
          </p>
        </header>

        <section className="rounded-xl border border-border bg-card/60 p-4 shadow-sm">
          <div className="space-y-3">
            <div data-testid="planner-summary" className="text-xs text-muted-foreground">
              {JSON.stringify({
                canBrowserExport: planner.canBrowserExport,
                blockerReasons: planner.blockers.map((blocker) => blocker.reason),
                nextActionKinds: planner.nextActions.map((action) => action.kind),
              })}
            </div>

            {startProcessAction ? (
              <BlockerActionCard
                severity="warning"
                code="planner/process-not-ready"
                message={startProcessAction.message ?? 'Start the fixture process to clear the blocker.'}
                nextAction={normalizeBlockerActionCardNextAction(startProcessAction, startProcessAction)}
                onAction={() => {
                  void handleStartProcess();
                }}
              />
            ) : (
              <p data-testid="planner-clear" className="text-sm text-muted-foreground">
                Planner clear.
              </p>
            )}

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                data-testid="fixture-execute"
                className="rounded border border-border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                disabled={statuses[0]?.state !== 'ready' && statuses[0]?.state !== 'degraded'}
                onClick={() => {
                  void handleExecute();
                }}
              >
                Execute fixture
              </button>
            </div>

            <div data-testid="projected-materials" className="text-xs text-muted-foreground">
              {materialRuntime.materials.length === 0
                ? 'none'
                : materialRuntime.materials.map((entry) => [
                  entry.materialRef.id,
                  entry.status.state,
                  entry.descriptorFacts.process?.attachProvenance?.descriptorId ?? 'no-provenance',
                ].join(':')).join('|')}
            </div>
          </div>
        </section>

        <DataProviderWrapper value={contextValue}>
          <section className="rounded-xl border border-border bg-card/60 shadow-sm">
            <ProcessDashboard />
          </section>
        </DataProviderWrapper>

        {latestResult && latestAttachRecord ? (
          <section className="rounded-xl border border-border bg-card/60 p-4 shadow-sm">
            <RoundtripResultsPanel
              result={latestResult}
              processResultAttachRecord={latestAttachRecord}
              proposalContext={{ baseVersion: 1 }}
              onCreateProposal={() => {}}
            />
          </section>
        ) : null}
      </div>
    </div>
  );
}

export default function VideoEditorProcessesHarnessPage() {
  const [searchParams] = useSearchParams();
  const scenarioParam = searchParams.get('scenario');
  const scenario = scenarioParam && VALID_SCENARIOS.has(scenarioParam as ProcessHarnessScenario)
    ? scenarioParam as ProcessHarnessScenario
    : 'happy-path';

  return <ProcessHarnessScenarioView scenario={scenario} />;
}
