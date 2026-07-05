// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useCallback, useMemo, useState } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import type {
  RenderArtifact,
  RenderArtifactSidecarDescriptor,
  RenderMaterial,
  RenderRoute,
} from '@reigh/editor-sdk';
import type { ProcessRoundtripResult } from '@/sdk/capabilities';
import type { ProcessStatus } from '@/sdk/video/families/processes';
import {
  BlockerActionCard,
  normalizeBlockerActionCardNextAction,
} from '@/tools/video-editor/components/BlockerActionCard.tsx';
import { ProcessDashboard } from '@/tools/video-editor/components/ProcessDashboard/ProcessDashboard.tsx';
import { RoundtripResultsPanel } from '@/tools/video-editor/components/RoundtripResultsPanel.tsx';
import { DataProviderWrapper, type VideoEditorRuntimeContextValue } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { projectHostMaterialRuntime } from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import {
  createProcessResultAttachRecord,
  projectProcessResultContracts,
  type ProcessResultAttachRecord,
  type ProcessResultContractProjection,
} from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import {
  createProcessManager,
  type ProcessManager,
} from '@/tools/video-editor/runtime/processes/ProcessManager.ts';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import type {
  VideoEditorOutputFormatDescriptor,
  VideoEditorProcessDescriptor,
  VideoEditorPlannerNextActionDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  createProcessFixtureDescriptor,
  type ProcessFixtureDescriptorOptions,
} from '../../../../../../tests/fixtures/video-editor/process-fixture-descriptor.ts';

const managedManagers: ProcessManager[] = [];
const ATTACHED_AT = '2026-07-05T00:00:00.000Z';
const PROCESS_ROUTE: RenderRoute = 'browser-export';

afterEach(async () => {
  cleanup();
  while (managedManagers.length > 0) {
    const manager = managedManagers.pop();
    if (!manager) continue;
    await manager.dispose();
  }
});

function returnedMaterial(
  id: string,
  overrides: Partial<RenderMaterial> = {},
): RenderMaterial {
  return {
    id,
    mediaKind: 'image',
    locator: {
      kind: 'artifact-store',
      uri: `artifact://${id}`,
    },
    determinism: 'process-dependent',
    replacementPolicy: 'materialize-on-export',
    provenance: {
      origin: 'process',
    },
    ...overrides,
  };
}

function artifact(
  material: RenderMaterial,
  overrides: Partial<RenderArtifact> = {},
): RenderArtifact {
  return {
    id: 'artifact.dataset',
    route: PROCESS_ROUTE,
    locator: {
      kind: 'artifact-store',
      uri: 'artifact://exports/dataset.json',
      mimeType: 'application/json',
    },
    mediaKind: 'json',
    determinism: 'process-dependent',
    boundary: {
      source: 'sidecar-process',
      target: 'artifact-store',
      route: PROCESS_ROUTE,
      failureBehavior: 'emit-diagnostic',
    },
    consumedMaterialRefs: [material],
    ...overrides,
  };
}

function sidecar(overrides: Partial<RenderArtifactSidecarDescriptor> = {}): RenderArtifactSidecarDescriptor {
  return {
    id: 'sidecar.log',
    filename: 'dataset.log',
    mimeType: 'text/plain',
    kind: 'log',
    locator: {
      kind: 'artifact-store',
      uri: 'artifact://sidecars/dataset.log',
      mimeType: 'text/plain',
    },
    provenance: { source: 'dataset-process' },
    ...overrides,
  };
}

function createCanaryProcessDescriptor(
  options: ProcessFixtureDescriptorOptions = {},
): VideoEditorProcessDescriptor {
  const spec = createProcessFixtureDescriptor({
    processId: options.processId ?? 'fixture-process',
    label: options.label ?? 'Fixture Process',
    operationId: options.operationId ?? 'fixture.execute',
    healthSequence: options.healthSequence,
    restartPolicy: options.restartPolicy,
    versionSemver: options.versionSemver,
  });
  const operation = spec.operations?.[0];
  if (!operation) {
    throw new Error('Fixture descriptor must declare at least one operation.');
  }

  return {
    id: `${spec.id}.contribution`,
    extensionId: 'ext.fixture.process',
    processId: spec.id,
    label: spec.label,
    description: 'Repo-controlled process fixture for the M6b jsdom canary.',
    spec,
    protocol: spec.protocol,
    operations: [{
      ...operation,
      routes: [PROCESS_ROUTE],
      outputKinds: ['material', 'artifact', 'sidecar', 'diagnostic', 'tool-result'],
      requiredCapabilities: [PROCESS_ROUTE],
    }],
    availableRoutes: [PROCESS_ROUTE],
    requiredBy: [
      {
        source: 'extension',
        extensionId: 'ext.fixture.process',
        contributionId: 'dataset-output',
      },
    ],
    blockers: [],
    nextActions: [],
  };
}

function createManagedProcessManager(
  descriptor: VideoEditorProcessDescriptor,
): ProcessManager {
  const manager = createProcessManager({
    processes: [descriptor.spec],
    defaultExecuteTimeoutMs: 1_000,
    defaultHealthTimeoutMs: 1_000,
    defaultShutdownTimeoutMs: 1_000,
  });
  managedManagers.push(manager);
  return manager;
}

function processOutputFormat(
  process: VideoEditorProcessDescriptor,
): VideoEditorOutputFormatDescriptor {
  const operation = process.operations[0];
  if (!operation) {
    throw new Error('Fixture process must declare an operation.');
  }

  return {
    id: 'dataset-output',
    extensionId: process.extensionId,
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
        processId: process.processId,
        operationId: operation.id,
        determinism: 'process-dependent',
        unavailableMessage: 'Start the fixture process before exporting the dataset.',
      },
    ],
    processRequirements: [
      {
        processId: process.processId,
        operationId: operation.id,
        requiredCapabilities: [PROCESS_ROUTE],
      },
    ],
    blockers: [],
    nextActions: [
      {
        kind: 'select-route',
        label: 'Select browser export',
        route: PROCESS_ROUTE,
        processId: process.processId,
        operationId: operation.id,
      },
    ],
    capabilities: {
      extensionId: process.extensionId,
      contributionId: 'dataset-output',
      routes: [PROCESS_ROUTE],
      determinism: 'process-dependent',
      sourceRefs: [
        {
          source: 'extension',
          extensionId: process.extensionId,
          contributionId: 'dataset-output',
        },
      ],
      capabilityRequirements: [
        {
          id: `ext.fixture.process.dataset-output.${PROCESS_ROUTE}`,
          sourceRef: {
            source: 'extension',
            extensionId: process.extensionId,
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

function runtimeValue(
  descriptor: VideoEditorProcessDescriptor,
  manager: ProcessManager,
  attachRecords: readonly ProcessResultAttachRecord[],
): VideoEditorRuntimeContextValue {
  const extensionRuntime = {
    config: {
      processes: [descriptor],
    },
    processes: [descriptor],
    settingsDefaults: {
      [descriptor.extensionId]: { endpoint: 'local-fixture' },
    },
  } as VideoEditorRuntimeContextValue['extensionRuntime'];

  return {
    provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
    assetResolver: { resolveAssetUrl: async (path: string) => path },
    auth: { userId: 'canary-user' },
    project: { projectId: 'project-canary' },
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
    timelineId: 'timeline-canary',
    userId: 'canary-user',
    extensions: extensionRuntime.config as VideoEditorRuntimeContextValue['extensions'],
    extensionRuntime,
    processManager: manager,
    processResultAttachRecords: attachRecords,
  };
}

const EMPTY_PROJECTION: ProcessResultContractProjection = Object.freeze({
  materialRefs: Object.freeze([]),
  materialStatuses: Object.freeze([]),
  artifacts: Object.freeze([]),
  sidecars: Object.freeze([]),
});

function ProcessRuntimeCanaryShell({
  descriptor,
  manager,
}: {
  descriptor: VideoEditorProcessDescriptor;
  manager: ProcessManager;
}) {
  const [statuses, setStatuses] = useState<readonly ProcessStatus[]>(() => manager.listStatuses());
  const [attachRecords, setAttachRecords] = useState<readonly ProcessResultAttachRecord[]>([]);
  const [latestResult, setLatestResult] = useState<ProcessRoundtripResult | null>(null);
  const [dashboardKey, setDashboardKey] = useState(0);
  const outputFormat = useMemo(() => processOutputFormat(descriptor), [descriptor]);
  const latestAttachRecord = attachRecords[attachRecords.length - 1];

  const refreshStatuses = useCallback(async () => {
    setStatuses(manager.listStatuses());
    setDashboardKey((current) => current + 1);
  }, [manager]);

  const handleStartProcess = useCallback(async () => {
    await manager.start(descriptor.processId);
    await refreshStatuses();
  }, [descriptor.processId, manager, refreshStatuses]);

  const handleAdvanceHealth = useCallback(async () => {
    let status = await manager.checkHealth(descriptor.processId);
    let safety = 0;
    while ((status.state === 'starting' || status.state === 'ready') && safety < 2) {
      status = await manager.checkHealth(descriptor.processId);
      safety += 1;
    }
    await refreshStatuses();
  }, [descriptor.processId, manager, refreshStatuses]);

  const handleExecute = useCallback(async () => {
    let status = manager.getStatus(descriptor.processId);
    if (status?.state === 'starting') {
      let safety = 0;
      while (status.state === 'starting' && safety < 3) {
        status = await manager.checkHealth(descriptor.processId);
        safety += 1;
      }
    }
    if (
      !status
      || (status.state !== 'ready' && status.state !== 'degraded' && status.state !== 'busy')
    ) {
      await manager.start(descriptor.processId);
      status = await manager.checkHealth(descriptor.processId);
    }

    const material = returnedMaterial('fixture-material');
    const result = await manager.execute({
      id: 'fixture-task-1',
      processId: descriptor.processId,
      operationId: descriptor.operations[0]!.id,
      params: {
        fixtureScenario: {
          resultStatus: 'completed',
          returnedMaterials: [material],
          artifacts: [artifact(material)],
          sidecars: [sidecar()],
          diagnostics: [{
            id: 'fixture-diagnostic',
            severity: 'warning',
            message: 'Fixture returned a warning.',
          }],
          progressEvents: [{
            percent: 100,
            message: 'Fixture render complete.',
          }],
          logEvents: [{
            level: 'info',
            message: 'Fixture finished.',
          }],
          availableActions: ['create-proposal'],
          metadata: {
            mode: 'canary',
          },
        },
      },
    });
    const record = createProcessResultAttachRecord({
      processDescriptor: descriptor,
      result,
      attachedAt: ATTACHED_AT,
    });
    setAttachRecords((current) => [...current, record]);
    setLatestResult(result);
    await refreshStatuses();
  }, [descriptor, manager, refreshStatuses]);

  const planner = useMemo(() => planRender({
    outputFormats: [outputFormat],
    processes: [descriptor],
    processStatuses: statuses,
    processResultAttachRecords: attachRecords,
  }), [attachRecords, descriptor, outputFormat, statuses]);

  const startProcessAction = planner.nextActions.find((action) =>
    action.kind === 'start-process'
    && action.processId === descriptor.processId) as VideoEditorPlannerNextActionDescriptor | undefined;

  const projection = useMemo(
    () => (latestAttachRecord ? projectProcessResultContracts(latestAttachRecord) : EMPTY_PROJECTION),
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

  const contextValue = useMemo(
    () => runtimeValue(descriptor, manager, attachRecords),
    [attachRecords, descriptor, manager],
  );

  return (
    <DataProviderWrapper value={contextValue}>
      <section aria-label="Process runtime canary" className="space-y-3">
        <div data-testid="planner-summary">
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
          <p data-testid="planner-clear">Planner clear.</p>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            data-testid="fixture-execute"
            onClick={() => {
              void handleExecute();
            }}
          >
            Execute fixture
          </button>
          <button
            type="button"
            data-testid="fixture-health"
            onClick={() => {
              void handleAdvanceHealth();
            }}
          >
            Advance health
          </button>
        </div>

        <div data-testid="projected-materials">
          {materialRuntime.materials.length === 0
            ? 'none'
            : materialRuntime.materials.map((entry) => [
              entry.materialRef.id,
              entry.status.state,
              entry.descriptorFacts.process?.attachProvenance?.descriptorId ?? 'no-provenance',
            ].join(':')).join('|')}
        </div>

        <ProcessDashboard key={dashboardKey} />

        {latestResult && latestAttachRecord ? (
          <RoundtripResultsPanel
            result={latestResult}
            processResultAttachRecord={latestAttachRecord}
            proposalContext={{ baseVersion: 1 }}
            onCreateProposal={() => {}}
          />
        ) : null}
      </section>
    </DataProviderWrapper>
  );
}

describe('process runtime M6b jsdom canary', () => {
  it('covers stopped-process repair plus execute, attach, projection, and provenance inspection', async () => {
    const descriptor = createCanaryProcessDescriptor();
    const manager = createManagedProcessManager(descriptor);

    render(
      <ProcessRuntimeCanaryShell descriptor={descriptor} manager={manager} />,
    );

    expect(screen.getByRole('button', { name: /Start .*Process/i })).toBeInTheDocument();
    expect(screen.getByTestId('planner-summary')).toHaveTextContent('"canBrowserExport":false');
    expect(screen.getByTestId('planner-summary')).toHaveTextContent('"start-process"');

    fireEvent.click(screen.getByRole('button', { name: /Start .*Process/i }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Start .*Process/i })).toBeNull();
      expect(screen.getByTestId('planner-summary')).not.toHaveTextContent('"start-process"');
      expect(screen.getByTestId(`process-status-${descriptor.id}`)).not.toHaveTextContent('stopped');
    });

    fireEvent.click(screen.getByTestId('fixture-execute'));

    await waitFor(() => {
      expect(screen.getByTestId('projected-materials')).toHaveTextContent(
        `${'fixture-material'}:${'resolved'}:${descriptor.id}`,
      );
    });

    fireEvent.click(screen.getByTestId(`process-action-inspect-${descriptor.id}`));

    expect(screen.getByTestId(`process-details-${descriptor.id}`)).toHaveTextContent(
      `process.result.attach · ${descriptor.id} · ${descriptor.operations[0]!.label}`,
    );
    expect(screen.getByText(`process.result.attach via ${descriptor.id}`)).toBeInTheDocument();
    expect(screen.getAllByText('Fixture returned a warning.')).toHaveLength(2);
    expect(screen.getAllByText('info: Fixture finished.')).toHaveLength(2);
    expect(screen.getByText('Attached materials: fixture-material')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create proposal' })).toBeInTheDocument();
  });

  it('surfaces degraded and recoverable failed diagnostics with retry visibility', async () => {
    const descriptor = createCanaryProcessDescriptor({
      processId: 'fixture-process-health',
      healthSequence: [
        'starting',
        'ready',
        { state: 'degraded', message: 'Fixture degraded.' },
        { state: 'failed', message: 'Fixture failed.', errorCode: 'fixture-failed', recoverable: true },
      ],
    });
    const manager = createManagedProcessManager(descriptor);
    await manager.start(descriptor.processId);

    render(
      <ProcessRuntimeCanaryShell descriptor={descriptor} manager={manager} />,
    );

    fireEvent.click(screen.getByTestId('fixture-health'));

    await waitFor(() => {
      expect(screen.getByTestId(`process-status-${descriptor.id}`)).toHaveTextContent('degraded');
      expect(screen.getByText('Fixture degraded.')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('fixture-health'));

    await waitFor(() => {
      expect(screen.getByTestId(`process-status-${descriptor.id}`)).toHaveTextContent('failed');
      expect(screen.getByText('Fixture failed.')).toBeInTheDocument();
      expect(screen.getByTestId(`process-action-retry-${descriptor.id}`)).toBeEnabled();
    });

    expect(screen.getByTestId(`process-action-retry-${descriptor.id}`)).toBeEnabled();
  });
});
