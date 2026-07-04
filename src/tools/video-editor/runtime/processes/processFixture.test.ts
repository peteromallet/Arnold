import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { afterEach, describe, expect, it } from 'vitest';
import {
  createJsonRpcStdioTransport,
  type JsonRpcStdioTransport,
  type JsonRpcTransportNotification,
} from './jsonRpcStdioTransport';
import {
  PROCESS_FIXTURE_MISSING_BINARY,
  createNotInstalledProcessFixtureDescriptor,
  createProcessFixtureDescriptor,
} from '../../../../../tests/fixtures/video-editor/process-fixture-descriptor.ts';

interface SpawnedFixture {
  readonly child: ChildProcessWithoutNullStreams;
  readonly transport: JsonRpcStdioTransport;
  readonly notifications: JsonRpcTransportNotification[];
  readonly processId: string;
}

const spawnedFixtures: SpawnedFixture[] = [];

afterEach(async () => {
  while (spawnedFixtures.length > 0) {
    const fixture = spawnedFixtures.pop();
    if (!fixture) continue;
    try {
      await shutdownFixture(fixture, fixture.processId);
    } catch {
      // Best effort only. The child may have already exited.
    } finally {
      fixture.transport.dispose();
      if (!fixture.child.killed && fixture.child.exitCode === null) {
        fixture.child.kill('SIGKILL');
      }
    }
  }
});

function spawnFixture(
  options: Parameters<typeof createProcessFixtureDescriptor>[0] = {},
): SpawnedFixture {
  const descriptor = createProcessFixtureDescriptor(options);
  const child = spawn(descriptor.spawn.command, [...(descriptor.spawn.args ?? [])], {
    cwd: descriptor.spawn.cwd,
    env: {
      ...process.env,
      ...descriptor.spawn.env,
    },
    stdio: 'pipe',
  });
  const notifications: JsonRpcTransportNotification[] = [];
  const transport = createJsonRpcStdioTransport({
    process: child,
    onNotification: (notification) => notifications.push(notification),
  });
  const fixture = { child, transport, notifications, processId: descriptor.id };
  spawnedFixtures.push(fixture);
  return fixture;
}

async function shutdownFixture(
  fixture: SpawnedFixture,
  processId: string,
): Promise<void> {
  if (fixture.child.exitCode !== null || fixture.child.killed) return;
  await fixture.transport.request({
    method: 'shutdown',
    params: {
      processId,
      reason: 'test-cleanup',
    },
    correlation: { processId },
  });
  await new Promise<void>((resolve) => {
    fixture.child.once('exit', () => resolve());
  });
}

describe('process fixture descriptor', () => {
  it('is repo-controlled, shell-free, and supports declared health-state sequences', async () => {
    const descriptor = createProcessFixtureDescriptor({
      healthSequence: [
        'starting',
        'ready',
        { state: 'degraded', message: 'fixture degraded' },
        { state: 'failed', errorCode: 'fixture-failed', recoverable: true },
      ],
    });
    const notInstalledDescriptor = createNotInstalledProcessFixtureDescriptor();

    expect(descriptor.spawn.command).toBe(process.execPath);
    expect(descriptor.spawn.args).toEqual([
      '--import',
      expect.stringContaining('/node_modules/tsx/dist/loader.mjs'),
      expect.stringContaining('/tests/fixtures/video-editor/process-fixture.ts'),
    ]);
    expect(descriptor.spawn.cwd).toContain('/reigh-app');
    expect(notInstalledDescriptor.spawn.command).toBe(PROCESS_FIXTURE_MISSING_BINARY);
    expect(notInstalledDescriptor.spawn.args).toEqual([]);

    const fixture = spawnFixture({
      healthSequence: [
        'starting',
        'ready',
        { state: 'degraded', message: 'fixture degraded' },
        { state: 'failed', errorCode: 'fixture-failed', recoverable: true },
      ],
    });

    await expect(fixture.transport.request({
      method: 'health',
      params: { processId: descriptor.id },
      correlation: { processId: descriptor.id },
    })).resolves.toMatchObject({
      processId: descriptor.id,
      state: 'starting',
    });
    await expect(fixture.transport.request({
      method: 'health',
      params: { processId: descriptor.id },
      correlation: { processId: descriptor.id },
    })).resolves.toMatchObject({
      processId: descriptor.id,
      state: 'ready',
      version: { semver: '1.0.0' },
    });
    await expect(fixture.transport.request({
      method: 'health',
      params: { processId: descriptor.id },
      correlation: { processId: descriptor.id },
    })).resolves.toMatchObject({
      processId: descriptor.id,
      state: 'degraded',
      message: 'fixture degraded',
    });
    await expect(fixture.transport.request({
      method: 'health',
      params: { processId: descriptor.id },
      correlation: { processId: descriptor.id },
    })).resolves.toMatchObject({
      processId: descriptor.id,
      state: 'failed',
      errorCode: 'fixture-failed',
      recoverable: true,
    });

    await shutdownFixture(fixture, descriptor.id);
  });

  it('supports execute, cancel as notification and request, progress/log notifications, and graceful shutdown', async () => {
    const descriptor = createProcessFixtureDescriptor({
      healthSequence: ['ready'],
    });
    const operationId = descriptor.operations?.[0]?.id ?? 'fixture.execute';
    const fixture = spawnFixture({
      healthSequence: ['ready'],
    });

    await fixture.transport.request({
      method: 'health',
      params: { processId: descriptor.id },
      correlation: { processId: descriptor.id },
    });

    const executeViaNotificationCancel = fixture.transport.request({
      method: 'execute',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-notify-cancel',
        fixtureScenario: {
          waitForCancel: true,
          lateResult: { status: 'cancelled' },
          progressEvents: [{ percent: 10, message: 'working' }],
          logEvents: [{ level: 'info', message: 'working log' }],
        },
      },
      correlation: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-notify-cancel',
      },
    });
    await fixture.transport.notify({
      method: 'cancel',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-notify-cancel',
      },
    });
    await expect(executeViaNotificationCancel).resolves.toMatchObject({
      processId: descriptor.id,
      operationId,
      status: 'cancelled',
    });

    const executeViaRequestCancel = fixture.transport.request({
      method: 'execute',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-request-cancel',
        fixtureScenario: {
          waitForCancel: true,
          lateResult: { status: 'cancelled', delayMs: 1 },
          emitCancelNotificationOnCancel: true,
        },
      },
      correlation: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-request-cancel',
      },
    });
    await expect(fixture.transport.request({
      method: 'cancel',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-request-cancel',
      },
      correlation: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-request-cancel',
      },
    })).resolves.toMatchObject({
      acknowledged: true,
      processId: descriptor.id,
      operationId,
      taskId: 'task-request-cancel',
      cancelled: true,
    });
    await expect(executeViaRequestCancel).resolves.toMatchObject({
      status: 'cancelled',
    });

    expect(fixture.notifications).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ kind: 'progress' }),
        expect.objectContaining({ kind: 'log' }),
        expect.objectContaining({ kind: 'cancel' }),
      ]),
    );

    await shutdownFixture(fixture, descriptor.id);
    expect(fixture.child.exitCode).toBe(0);
  });

  it('supports protocol-error, timeout, invalid-request, process-exited, and late-notification scenarios', async () => {
    const descriptor = createProcessFixtureDescriptor({
      healthSequence: ['ready'],
    });
    const operationId = descriptor.operations?.[0]?.id ?? 'fixture.execute';
    const fixture = spawnFixture({
      healthSequence: ['ready'],
    });

    await fixture.transport.request({
      method: 'health',
      params: { processId: descriptor.id },
      correlation: { processId: descriptor.id },
    });

    await expect(fixture.transport.request({
      method: 'execute',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-protocol-error',
        fixtureScenario: {
          errorClass: 'protocol-error',
          errorDetail: 'fixture protocol failure',
        },
      },
      correlation: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-protocol-error',
      },
    })).rejects.toMatchObject({
      errorClass: 'protocol-error',
      detail: 'fixture protocol failure',
    });

    await expect(fixture.transport.request({
      method: 'execute',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-timeout-error',
        fixtureScenario: {
          errorClass: 'timeout',
          timeoutMs: 25,
        },
      },
      correlation: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-timeout-error',
      },
    })).rejects.toMatchObject({
      errorClass: 'timeout',
    });

    await expect(fixture.transport.request({
      method: 'execute',
      params: {
        processId: descriptor.id,
        operationId: 'unknown.operation',
        taskId: 'task-invalid-request',
      },
      correlation: {
        processId: descriptor.id,
        operationId: 'unknown.operation',
        taskId: 'task-invalid-request',
      },
    })).rejects.toMatchObject({
      errorClass: 'invalid-request',
      detail: expect.stringContaining('Unknown operationId'),
    });

    const lateExecution = fixture.transport.request({
      method: 'execute',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-late-notes',
        fixtureScenario: {
          waitForCancel: true,
          lateResult: { status: 'completed', delayMs: 1 },
          lateNotifications: ['progress', 'log', 'cancel'],
        },
      },
      correlation: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-late-notes',
      },
    });
    await fixture.transport.request({
      method: 'cancel',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-late-notes',
      },
      correlation: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-late-notes',
      },
    });
    await expect(lateExecution).resolves.toMatchObject({
      status: 'completed',
    });
    await new Promise<void>((resolve) => {
      setTimeout(resolve, 25);
    });
    expect(fixture.notifications).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ kind: 'progress' }),
        expect.objectContaining({ kind: 'log' }),
        expect.objectContaining({ kind: 'cancel' }),
      ]),
    );

    await shutdownFixture(fixture, descriptor.id);

    const exitFixture = spawnFixture({
      healthSequence: ['ready'],
    });
    await exitFixture.transport.request({
      method: 'health',
      params: { processId: descriptor.id },
      correlation: { processId: descriptor.id },
    });
    await expect(exitFixture.transport.request({
      method: 'execute',
      params: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-process-exit',
        fixtureScenario: {
          exitDuring: 'execute',
          exitCode: 9,
        },
      },
      correlation: {
        processId: descriptor.id,
        operationId,
        taskId: 'task-process-exit',
      },
    })).rejects.toMatchObject({
      errorClass: 'process-exited',
    });
    exitFixture.transport.dispose();
  });
});
