import { once } from 'node:events';
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { afterEach, describe, expect, it } from 'vitest';
import type { ProcessSpec, ProcessStatus } from '@reigh/editor-sdk';
import {
  createProcessManager,
  type CreateProcessManagerOptions,
  type ProcessManager,
} from './ProcessManager';
import {
  JsonRpcTransportError,
  createJsonRpcStdioTransport,
  type JsonRpcProcessLike,
  type JsonRpcStdioTransport,
  type JsonRpcTransportNotificationOptions,
  type JsonRpcTransportRequestOptions,
} from './jsonRpcStdioTransport';
import {
  PROCESS_FIXTURE_MISSING_BINARY,
  PROCESS_FIXTURE_OPERATION_ID,
  createNotInstalledProcessFixtureDescriptor,
  createProcessFixtureDescriptor,
  type ProcessFixtureDescriptorOptions,
} from '../../../../../tests/fixtures/video-editor/process-fixture-descriptor.ts';

interface ManagedFixture {
  readonly children: ChildProcessWithoutNullStreams[];
  readonly manager: ProcessManager;
}

interface TransportSpy {
  readonly notifications: JsonRpcTransportNotificationOptions[];
  readonly protocolErrors: JsonRpcTransportError[];
  readonly requests: JsonRpcTransportRequestOptions[];
}

type ProcessManagerTransportHooks = Parameters<NonNullable<CreateProcessManagerOptions['createTransport']>>[1];

const managedFixtures: ManagedFixture[] = [];
const FIXTURE_DEFAULT_TIMEOUT_MS = 1_000;

afterEach(async () => {
  while (managedFixtures.length > 0) {
    const fixture = managedFixtures.pop();
    if (!fixture) continue;

    try {
      await fixture.manager.dispose();
    } catch {
      // Best effort only during cleanup.
    }

    for (const child of fixture.children) {
      if (child.exitCode === null && !child.killed) {
        child.kill('SIGKILL');
        await waitForChildExit(child);
      }
    }
  }
});

function createSpawnError(command: string): NodeJS.ErrnoException {
  const error = new Error(`spawn ${command} ENOENT`) as NodeJS.ErrnoException;
  error.code = 'ENOENT';
  return error;
}

function spawnFixtureProcess(
  spec: ProcessSpec,
  children: ChildProcessWithoutNullStreams[],
): ChildProcessWithoutNullStreams {
  if (spec.spawn.command === PROCESS_FIXTURE_MISSING_BINARY) {
    throw createSpawnError(spec.spawn.command);
  }

  const child = spawn(spec.spawn.command, [...(spec.spawn.args ?? [])], {
    cwd: spec.spawn.cwd,
    env: {
      ...process.env,
      ...spec.spawn.env,
    },
    shell: false,
    stdio: 'pipe',
  });
  children.push(child);
  return child;
}

function createSpyTransport(
  processHandle: JsonRpcProcessLike,
  spy: TransportSpy,
  hooks: ProcessManagerTransportHooks,
): JsonRpcStdioTransport {
  const transport = createJsonRpcStdioTransport({
    process: processHandle,
    onNotification: hooks.onNotification,
    onProtocolError: (error) => {
      spy.protocolErrors.push(error);
      hooks.onProtocolError(error);
    },
  });

  return {
    request<TResult = unknown>(options: JsonRpcTransportRequestOptions): Promise<TResult> {
      spy.requests.push(options);
      return transport.request<TResult>(options);
    },
    notify(options: JsonRpcTransportNotificationOptions): Promise<void> {
      spy.notifications.push(options);
      return transport.notify(options);
    },
    dispose(): void {
      transport.dispose();
    },
  };
}

function createManagedFixture(options: {
  readonly descriptorOptions?: ProcessFixtureDescriptorOptions;
  readonly includeNotInstalled?: boolean;
} = {}): {
  readonly descriptor: ProcessSpec;
  readonly manager: ProcessManager;
  readonly notInstalledDescriptor?: ProcessSpec;
  readonly operationId: string;
  readonly spy: TransportSpy;
} {
  const descriptor = createProcessFixtureDescriptor(options.descriptorOptions);
  const operationId = descriptor.operations?.[0]?.id ?? PROCESS_FIXTURE_OPERATION_ID;
  const notInstalledDescriptor = options.includeNotInstalled
    ? createNotInstalledProcessFixtureDescriptor({
      processId: `${descriptor.id}.missing`,
      operationId,
    })
    : undefined;
  const children: ChildProcessWithoutNullStreams[] = [];
  const spy: TransportSpy = {
    notifications: [],
    protocolErrors: [],
    requests: [],
  };

  const manager = createProcessManager({
    processes: [
      descriptor,
      ...(notInstalledDescriptor ? [notInstalledDescriptor] : []),
    ],
    spawnProcess: (spec) => spawnFixtureProcess(spec, children),
    createTransport: (processHandle, hooks) => createSpyTransport(processHandle, spy, hooks),
    // Real stdio + tsx startup can exceed very small test-only defaults when
    // broader suites are contending for CPU; keep the integration helper stable.
    defaultExecuteTimeoutMs: FIXTURE_DEFAULT_TIMEOUT_MS,
    defaultHealthTimeoutMs: FIXTURE_DEFAULT_TIMEOUT_MS,
    defaultShutdownTimeoutMs: FIXTURE_DEFAULT_TIMEOUT_MS,
  });

  managedFixtures.push({ children, manager });

  return {
    descriptor,
    manager,
    ...(notInstalledDescriptor ? { notInstalledDescriptor } : {}),
    operationId,
    spy,
  };
}

async function waitForChildExit(
  child: ChildProcessWithoutNullStreams,
  timeoutMs = 500,
): Promise<void> {
  if (child.exitCode !== null) return;
  await Promise.race([
    once(child, 'exit').then(() => undefined),
    delay(timeoutMs),
  ]);
}

async function delay(ms: number): Promise<void> {
  await new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });
}

// Integration assertions need a bounded wait because late diagnostics arrive
// asynchronously after real stdio roundtrips complete.
async function waitForStatus(
  manager: ProcessManager,
  processId: string,
  predicate: (status: ProcessStatus) => boolean,
  timeoutMs = 1_000,
): Promise<ProcessStatus> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() <= deadline) {
    const status = manager.getStatus(processId);
    if (status && predicate(status)) {
      return status;
    }
    await delay(10);
  }

  throw new Error(`Timed out waiting for process status for "${processId}".`);
}

describe('createProcessManager fixture integration', () => {
  it('covers lifecycle states plus health, execute, cancel, and shutdown roundtrips', async () => {
    const { descriptor, manager, notInstalledDescriptor, operationId, spy } = createManagedFixture({
      descriptorOptions: {
        healthSequence: [
          'starting',
          'ready',
          { state: 'degraded', message: 'fixture degraded' },
          { state: 'failed', errorCode: 'fixture-failed', recoverable: true },
        ],
      },
      includeNotInstalled: true,
    });
    const missingDescriptor = notInstalledDescriptor!;

    expect(manager.listStatuses()).toEqual([
      expect.objectContaining({
        processId: descriptor.id,
        state: 'stopped',
      }),
      expect.objectContaining({
        processId: missingDescriptor.id,
        state: 'stopped',
      }),
    ]);

    await expect(manager.checkHealth(missingDescriptor.id)).resolves.toMatchObject({
      state: 'not-installed',
      processId: missingDescriptor.id,
    });
    await expect(manager.checkHealth(descriptor.id)).resolves.toMatchObject({
      state: 'starting',
      startedAt: expect.any(String),
    });
    await expect(manager.checkHealth(descriptor.id)).resolves.toMatchObject({
      state: 'ready',
      processId: descriptor.id,
      version: { semver: '1.0.0' },
      pid: expect.any(Number),
    });

    const execution = manager.execute({
      id: 'task-lifecycle',
      processId: descriptor.id,
      operationId,
      params: {
        fixtureScenario: {
          waitForCancel: true,
          lateResult: { status: 'cancelled' },
          progressEvents: [{ percent: 35, message: 'fixture busy' }],
          logEvents: [{ level: 'info', message: 'fixture log' }],
        },
      },
    });

    await expect(waitForStatus(
      manager,
      descriptor.id,
      (status) => status.state === 'busy'
        && status.operationId === operationId
        && status.progress?.percent === 35,
    )).resolves.toMatchObject({
      state: 'busy',
      operationId,
      progress: {
        percent: 35,
        message: 'fixture busy',
      },
    });

    await expect(manager.cancel(descriptor.id, {
      taskId: 'task-lifecycle',
      operationId,
      reason: 'user-aborted',
    })).resolves.toMatchObject({
      state: 'busy',
      operationId,
    });

    await expect(execution).resolves.toMatchObject({
      requestId: 'task-lifecycle',
      processId: descriptor.id,
      operationId,
      status: 'cancelled',
      progress: {
        operationId,
        percent: 35,
        message: 'fixture busy',
      },
      logs: [
        {
          level: 'info',
          message: 'fixture log',
        },
      ],
    });
    expect(manager.getStatus(descriptor.id)).toMatchObject({
      state: 'ready',
      processId: descriptor.id,
    });

    await expect(manager.checkHealth(descriptor.id)).resolves.toMatchObject({
      state: 'degraded',
      healthCheck: 'health',
      message: 'fixture degraded',
    });
    await expect(manager.checkHealth(descriptor.id)).resolves.toMatchObject({
      state: 'failed',
      errorCode: 'fixture-failed',
      recoverable: true,
    });

    const shutdown = manager.shutdown(descriptor.id, {
      reason: 'test-shutdown',
    });
    expect(manager.getStatus(descriptor.id)).toMatchObject({
      state: 'stopping',
      reason: 'test-shutdown',
    });
    await expect(shutdown).resolves.toMatchObject({
      state: 'stopped',
      processId: descriptor.id,
      message: expect.stringContaining('stopped gracefully'),
    });

    expect(spy.requests).toEqual(expect.arrayContaining([
      expect.objectContaining({
        method: 'health',
        correlation: {
          processId: descriptor.id,
        },
        params: {
          processId: descriptor.id,
        },
      }),
      expect.objectContaining({
        method: 'execute',
        correlation: {
          processId: descriptor.id,
          operationId,
          taskId: 'task-lifecycle',
        },
        params: expect.objectContaining({
          processId: descriptor.id,
          operationId,
          requestId: 'task-lifecycle',
          taskId: 'task-lifecycle',
        }),
      }),
      expect.objectContaining({
        method: 'shutdown',
        correlation: {
          processId: descriptor.id,
        },
        params: {
          processId: descriptor.id,
          reason: 'test-shutdown',
        },
      }),
    ]));
    expect(spy.notifications).toContainEqual({
      method: 'cancel',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-lifecycle',
        reason: 'user-aborted',
      },
    });
  });

  it('preserves correlated JSON-RPC error shapes for protocol, timeout, invalid-request, and process-exited failures', async () => {
    const cases = [
      {
        taskId: 'task-protocol-error',
        scenario: {
          errorClass: 'protocol-error',
          errorDetail: 'fixture protocol failure',
        },
        expectedError: {
          code: -32600,
          detail: 'fixture protocol failure',
          errorClass: 'protocol-error',
        },
        expectedState: 'failed',
        expectedErrorCode: 'protocol-error',
      },
      {
        taskId: 'task-timeout-error',
        scenario: {
          errorClass: 'timeout',
          timeoutMs: 25,
        },
        expectedError: {
          code: -32000,
          errorClass: 'timeout',
        },
        expectedState: 'degraded',
        expectedErrorCode: undefined,
      },
      {
        taskId: 'task-invalid-request',
        scenario: {
          errorClass: 'invalid-request',
          errorDetail: 'fixture invalid request',
        },
        expectedError: {
          code: -32602,
          detail: 'fixture invalid request',
          errorClass: 'invalid-request',
        },
        expectedState: 'failed',
        expectedErrorCode: 'invalid-request',
      },
      {
        taskId: 'task-process-exited',
        scenario: {
          exitDuring: 'execute',
          exitCode: 9,
        },
        expectedError: {
          code: -32001,
          errorClass: 'process-exited',
        },
        expectedState: 'failed',
        expectedErrorCode: 'process-exited',
      },
    ] as const;

    for (const testCase of cases) {
      const { descriptor, manager, operationId, spy } = createManagedFixture({
        descriptorOptions: {
          healthSequence: ['ready'],
        },
      });

      await expect(manager.start(descriptor.id)).resolves.toMatchObject({
        state: 'ready',
      });

      await expect(manager.execute({
        id: testCase.taskId,
        processId: descriptor.id,
        operationId,
        params: {
          fixtureScenario: testCase.scenario,
        },
      })).rejects.toMatchObject({
        ...testCase.expectedError,
        processId: descriptor.id,
        operationId,
        taskId: testCase.taskId,
      });

      expect(spy.requests.at(-1)).toMatchObject({
        method: 'execute',
        correlation: {
          processId: descriptor.id,
          operationId,
          taskId: testCase.taskId,
        },
      });
      expect(manager.getStatus(descriptor.id)).toMatchObject({
        state: testCase.expectedState,
        ...(testCase.expectedErrorCode ? { errorCode: testCase.expectedErrorCode } : {}),
      });
    }
  });

  it('ignores late result, progress, and log messages for state mutation while recording recoverable diagnostics', async () => {
    const { descriptor, manager, operationId, spy } = createManagedFixture({
      descriptorOptions: {
        healthSequence: ['ready'],
      },
    });

    await expect(manager.start(descriptor.id)).resolves.toMatchObject({
      state: 'ready',
    });

    await expect(manager.execute({
      id: 'task-late-timeout',
      processId: descriptor.id,
      operationId,
      params: {
        fixtureScenario: {
          hang: true,
          lateNotifications: ['progress', 'log'],
          lateResult: { status: 'cancelled' },
        },
      },
    }, {
      timeoutMs: 25,
    })).rejects.toMatchObject({
      code: -32000,
      errorClass: 'timeout',
      processId: descriptor.id,
      operationId,
      taskId: 'task-late-timeout',
      timeoutMs: 25,
    });

    const lateStatus = await waitForStatus(
      manager,
      descriptor.id,
      (status) => {
        if (status.state !== 'degraded') return false;
        const codes = (status.diagnostics ?? []).map((diagnostic) => diagnostic.code);
        return codes.includes('process/timeout')
          && codes.includes('process/late-result')
          && codes.includes('process/late-progress')
          && codes.includes('process/late-log');
      },
    );

    expect(lateStatus).toMatchObject({
      state: 'degraded',
      diagnostics: expect.arrayContaining([
        expect.objectContaining({
          code: 'process/timeout',
          detail: expect.objectContaining({
            processId: descriptor.id,
            operationId,
            taskId: 'task-late-timeout',
            timeoutMs: 25,
            recoverable: true,
          }),
        }),
        expect.objectContaining({
          code: 'process/late-result',
          detail: expect.objectContaining({
            processId: descriptor.id,
            operationId,
            taskId: 'task-late-timeout',
            recoverable: true,
          }),
        }),
        expect.objectContaining({
          code: 'process/late-progress',
          detail: expect.objectContaining({
            processId: descriptor.id,
            operationId,
            taskId: 'task-late-timeout',
            recoverable: true,
          }),
        }),
        expect.objectContaining({
          code: 'process/late-log',
          detail: expect.objectContaining({
            processId: descriptor.id,
            operationId,
            taskId: 'task-late-timeout',
            recoverable: true,
          }),
        }),
      ]),
    });
    expect(spy.notifications).toContainEqual({
      method: 'cancel',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-late-timeout',
        reason: 'execute-timeout',
      },
    });
    expect(spy.protocolErrors).toEqual(expect.arrayContaining([
      expect.objectContaining({
        errorClass: 'protocol-error',
        message: expect.stringContaining('unknown request id'),
      }),
    ]));
  });
});
