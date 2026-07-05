// @vitest-environment jsdom

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ProcessRoundtripResult } from '@/sdk/capabilities';
import type { ProcessStatus } from '@/sdk/video/families/processes';
import { DataProviderWrapper, type VideoEditorRuntimeContextValue } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import {
  createProcessResultAttachRecord,
  type ProcessResultAttachRecord,
} from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import type { ProcessManager } from '@/tools/video-editor/runtime/processes/ProcessManager.ts';
import type { VideoEditorProcessDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  deriveProcessDashboardEntries,
  ProcessDashboard,
} from './ProcessDashboard';

function processDescriptor(
  id: string,
  processId: string,
  label: string,
  overrides: Partial<VideoEditorProcessDescriptor> = {},
): VideoEditorProcessDescriptor {
  return {
    id,
    extensionId: `ext.${processId}`,
    processId,
    label,
    description: `${label} description`,
    spec: {
      id: processId,
      label,
      spawn: { command: `${processId}-bin` },
      protocol: 'stdio-jsonrpc',
      operations: [{
        id: 'run',
        label: 'Run',
        routes: ['browser-export'],
        outputKinds: ['material', 'artifact', 'sidecar'],
        requiredCapabilities: ['browser-export'],
      }],
      env: [{ key: 'TOKEN', required: true }],
    },
    protocol: 'stdio-jsonrpc',
    operations: [{
      id: 'run',
      label: 'Run',
      routes: ['browser-export'],
      outputKinds: ['material', 'artifact', 'sidecar'],
      requiredCapabilities: ['browser-export'],
    }],
    availableRoutes: ['browser-export'],
    requiredBy: [],
    blockers: [],
    nextActions: [],
    ...overrides,
  };
}

function processStatus(
  processId: string,
  state: ProcessStatus['state'],
  overrides: Record<string, unknown> = {},
): ProcessStatus {
  return {
    processId,
    state,
    ...overrides,
  } as ProcessStatus;
}

function attachRecord(
  descriptor: VideoEditorProcessDescriptor,
  overrides: Partial<ProcessRoundtripResult> = {},
): ProcessResultAttachRecord {
  return createProcessResultAttachRecord({
    processDescriptor: descriptor,
    attachedAt: '2026-07-04T23:30:00.000Z',
    result: {
      requestId: `${descriptor.processId}:run`,
      processId: descriptor.processId,
      operationId: 'run',
      status: 'completed',
      returnedMaterials: [{
        id: `${descriptor.processId}-material`,
        mediaKind: 'image',
        locator: { kind: 'url', uri: `https://example.test/${descriptor.processId}.png` },
        determinism: 'process-dependent',
        replacementPolicy: 'replace-live-ref',
      }],
      artifacts: [{
        id: `${descriptor.processId}-artifact`,
        route: 'browser-export',
        locator: { kind: 'url', uri: `https://example.test/${descriptor.processId}.json` },
        mediaKind: 'json',
        determinism: 'process-dependent',
        boundary: {
          source: 'process',
          target: 'artifact-store',
          route: 'browser-export',
          failureBehavior: 'emit-diagnostic',
        },
        consumedMaterialRefs: [],
      }],
      sidecars: [{
        id: `${descriptor.processId}-log`,
        filename: `${descriptor.processId}.log`,
        kind: 'log',
        mimeType: 'text/plain',
        data: new TextEncoder().encode('done'),
      }],
      diagnostics: [{
        id: `${descriptor.processId}-diag`,
        severity: 'warning',
        message: `${descriptor.label} warning`,
      }],
      logs: [{
        level: 'info',
        message: `${descriptor.label} finished`,
      }],
      availableActions: ['create-proposal'],
      ...overrides,
    },
  });
}

class FakeProcessManager implements ProcessManager {
  private statusesById = new Map<string, ProcessStatus>();

  readonly listStatuses = vi.fn(() => [...this.statusesById.values()]);
  readonly start = vi.fn(async (processId: string) => {
    const next = processStatus(processId, 'ready', { message: `${processId} ready` });
    this.statusesById.set(processId, next);
    return next;
  });
  readonly checkHealth = vi.fn(async (processId: string) => (
    this.statusesById.get(processId) ?? processStatus(processId, 'stopped')
  ));
  readonly execute = vi.fn(async () => {
    throw new Error('execute not used in dashboard tests');
  });
  readonly cancel = vi.fn(async (processId: string) => {
    const next = processStatus(processId, 'ready', { message: `${processId} cancelled` });
    this.statusesById.set(processId, next);
    return next;
  });
  readonly shutdown = vi.fn(async (processId: string) => {
    const next = processStatus(processId, 'stopped', { message: `${processId} stopped` });
    this.statusesById.set(processId, next);
    return next;
  });
  readonly dispose = vi.fn(async () => {});

  constructor(
    private readonly descriptors: readonly VideoEditorProcessDescriptor[],
    initialStatuses: readonly ProcessStatus[],
  ) {
    for (const status of initialStatuses) {
      this.statusesById.set(status.processId, status);
    }
  }

  getDeclaredProcesses() {
    return this.descriptors.map((descriptor) => descriptor.spec);
  }

  getProcessSpec(processId: string) {
    return this.descriptors.find((descriptor) => descriptor.processId === processId)?.spec;
  }

  getStatus(processId: string) {
    return this.statusesById.get(processId);
  }

  setStatus(status: ProcessStatus) {
    this.statusesById.set(status.processId, status);
  }
}

function runtimeValue(params: {
  configProcesses?: readonly VideoEditorProcessDescriptor[];
  runtimeProcesses?: readonly VideoEditorProcessDescriptor[];
  statuses?: readonly ProcessStatus[];
  attachRecords?: readonly ProcessResultAttachRecord[];
  processManager?: ProcessManager;
}): VideoEditorRuntimeContextValue {
  const extensionRuntime = {
    config: {
      processes: params.configProcesses ?? [],
    },
    processes: params.runtimeProcesses ?? [],
    settingsDefaults: {
      'ext.beta': { token: 'abc' },
    },
  } as VideoEditorRuntimeContextValue['extensionRuntime'];

  return {
    provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
    assetResolver: { resolveAssetUrl: async (path: string) => path },
    auth: { userId: 'test-user' },
    project: { projectId: null },
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
    timelineId: 'timeline-1',
    userId: 'test-user',
    extensions: extensionRuntime.config as VideoEditorRuntimeContextValue['extensions'],
    extensionRuntime,
    processManager: params.processManager,
    processStatuses: params.statuses,
    processResultAttachRecords: params.attachRecords,
  };
}

function renderDashboard(context: VideoEditorRuntimeContextValue) {
  return render(
    <DataProviderWrapper value={context}>
      <ProcessDashboard />
    </DataProviderWrapper>,
  );
}

describe('deriveProcessDashboardEntries', () => {
  it('merges declared processes from config and runtime without duplicates', () => {
    const alpha = processDescriptor('proc.alpha', 'alpha', 'Alpha');
    const beta = processDescriptor('proc.beta', 'beta', 'Beta');
    const entries = deriveProcessDashboardEntries({
      extensionRuntime: {
        config: { processes: [alpha, beta] },
        processes: [beta],
        settingsDefaults: {},
      } as VideoEditorRuntimeContextValue['extensionRuntime'],
      statuses: [processStatus('beta', 'busy')],
      attachRecords: [],
    });

    expect(entries.map((entry) => entry.descriptor.id)).toEqual([
      'proc.alpha',
      'proc.beta',
    ]);
  });
});

describe('ProcessDashboard', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders declared processes with lifecycle, route/output details, and returned-ref provenance', () => {
    const alpha = processDescriptor('proc.alpha', 'alpha', 'Alpha', {
      operations: [{
        id: 'probe',
        label: 'Probe',
        routes: ['sidecar-export'],
        outputKinds: ['artifact'],
      }],
      spec: {
        id: 'alpha',
        label: 'Alpha',
        spawn: { command: 'alpha-bin' },
        protocol: 'stdio-jsonrpc',
        operations: [{
          id: 'probe',
          label: 'Probe',
          routes: ['sidecar-export'],
          outputKinds: ['artifact'],
        }],
      },
      availableRoutes: ['sidecar-export'],
    });
    const beta = processDescriptor('proc.beta', 'beta', 'Beta');
    const manager = new FakeProcessManager([alpha, beta], [
      processStatus('alpha', 'stopped', { message: 'Alpha stopped.' }),
      processStatus('beta', 'busy', {
        message: 'Beta processing.',
        operationId: 'run',
        taskId: 'beta-task-1',
        progress: { operationId: 'run', percent: 50, message: 'Halfway' },
      }),
    ]);

    renderDashboard(runtimeValue({
      configProcesses: [alpha],
      runtimeProcesses: [beta],
      processManager: manager,
      attachRecords: [attachRecord(beta)],
    }));

    expect(screen.getByTestId('process-card-proc.alpha')).toBeInTheDocument();
    expect(screen.getByTestId('process-card-proc.beta')).toBeInTheDocument();
    expect(screen.getByText('alpha-bin · cwd default · no env fields')).toBeInTheDocument();
    expect(screen.getByText('No material outputs declared.')).toBeInTheDocument();
    expect(screen.getAllByText('Run')).toHaveLength(2);
    expect(screen.getByText('run · beta-task-1')).toBeInTheDocument();
    expect(screen.getByText('1 extension setting default declared.')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('process-action-inspect-proc.beta'));

    expect(screen.getByTestId('process-details-proc.beta')).toHaveTextContent('process.result.attach · proc.beta · Run');
    expect(screen.getByTestId('process-details-proc.beta')).toHaveTextContent('materials: beta-material');
    expect(screen.getByTestId('process-details-proc.beta')).toHaveTextContent('artifacts: beta-artifact');
    expect(screen.getByTestId('process-details-proc.beta')).toHaveTextContent('sidecars: beta.log');
    expect(screen.getByTestId('process-details-proc.beta')).toHaveTextContent('Beta warning');
    expect(screen.getByTestId('process-details-proc.beta')).toHaveTextContent('info: Beta finished');
  });

  it('guards lifecycle controls and refreshes status after actions', async () => {
    const startable = processDescriptor('proc.start', 'startable', 'Startable');
    const starting = processDescriptor('proc.starting', 'starting', 'Starting');
    const busy = processDescriptor('proc.busy', 'busy', 'Busy');
    const ready = processDescriptor('proc.ready', 'ready', 'Ready');
    const failed = processDescriptor('proc.failed', 'failed', 'Failed');
    const manager = new FakeProcessManager(
      [startable, starting, busy, ready, failed],
      [
        processStatus('startable', 'stopped', { message: 'Stopped.' }),
        processStatus('starting', 'starting', { message: 'Starting.' }),
        processStatus('busy', 'busy', { message: 'Busy.', operationId: 'run', taskId: 'busy-task' }),
        processStatus('ready', 'ready', { message: 'Ready.' }),
        processStatus('failed', 'failed', { message: 'Failed.', recoverable: true }),
      ],
    );

    renderDashboard(runtimeValue({
      runtimeProcesses: [startable, starting, busy, ready, failed],
      processManager: manager,
    }));

    expect(screen.getByTestId('process-action-start-proc.start')).toBeEnabled();
    expect(screen.getByTestId('process-action-cancel-proc.starting')).toBeEnabled();
    expect(screen.getByTestId('process-action-cancel-proc.busy')).toBeEnabled();
    expect(screen.getByTestId('process-action-shutdown-proc.ready')).toBeEnabled();
    expect(screen.getByTestId('process-action-retry-proc.failed')).toBeEnabled();
    expect(screen.queryByTestId('process-action-start-proc.ready')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('process-action-start-proc.start'));
    fireEvent.click(screen.getByTestId('process-action-cancel-proc.starting'));
    fireEvent.click(screen.getByTestId('process-action-cancel-proc.busy'));
    fireEvent.click(screen.getByTestId('process-action-shutdown-proc.ready'));
    fireEvent.click(screen.getByTestId('process-action-retry-proc.failed'));

    await waitFor(() => {
      expect(manager.start).toHaveBeenCalledWith('startable');
      expect(manager.start).toHaveBeenCalledWith('failed');
      expect(manager.cancel).toHaveBeenCalledWith('busy', {
        operationId: 'run',
        reason: 'dashboard-cancel',
        taskId: 'busy-task',
      });
      expect(manager.shutdown).toHaveBeenCalledWith('starting', { reason: 'dashboard-cancel-startup' });
      expect(manager.shutdown).toHaveBeenCalledWith('ready', { reason: 'dashboard-shutdown' });
    });

    await waitFor(() => {
      expect(screen.getByTestId('process-status-proc.start')).toHaveTextContent('ready');
      expect(screen.getByTestId('process-status-proc.ready')).toHaveTextContent('stopped');
      expect(screen.getByTestId('process-status-proc.failed')).toHaveTextContent('ready');
    });
  });

  it('polls only while at least one process is transient', async () => {
    vi.useFakeTimers();

    const alpha = processDescriptor('proc.alpha', 'alpha', 'Alpha');
    const manager = new FakeProcessManager([alpha], [
      processStatus('alpha', 'starting', { message: 'Starting.' }),
    ]);

    renderDashboard(runtimeValue({
      runtimeProcesses: [alpha],
      processManager: manager,
    }));

    const initialCalls = manager.listStatuses.mock.calls.length;

    await act(async () => {
      vi.advanceTimersByTime(1_000);
      await Promise.resolve();
    });

    expect(manager.listStatuses.mock.calls.length).toBeGreaterThan(initialCalls);

    manager.setStatus(processStatus('alpha', 'ready', { message: 'Ready.' }));

    await act(async () => {
      vi.advanceTimersByTime(1_000);
      await Promise.resolve();
    });

    const settledCalls = manager.listStatuses.mock.calls.length;

    await act(async () => {
      vi.advanceTimersByTime(2_000);
      await Promise.resolve();
    });

    expect(manager.listStatuses.mock.calls.length).toBe(settledCalls);
  });
});
