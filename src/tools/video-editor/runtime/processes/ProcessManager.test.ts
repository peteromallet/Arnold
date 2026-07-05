import { EventEmitter } from 'node:events';
import { describe, expect, it } from 'vitest';
import type { ProcessRoundtripResult } from '@/sdk/capabilities';
import type { ProcessSpec } from '@/sdk/video/families/processes';
import {
  createProcessManager,
  type ProcessManagerRestartPolicyEvent,
} from './ProcessManager';
import { JsonRpcTransportError } from './jsonRpcStdioTransport';
import type {
  JsonRpcProcessLike,
  JsonRpcStdioTransport,
  JsonRpcTransportNotification,
  JsonRpcTransportNotificationOptions,
  JsonRpcTransportRequestOptions,
} from './jsonRpcStdioTransport';

interface Deferred<T> {
  readonly promise: Promise<T>;
  resolve(value: T): void;
}

interface FakeProcessBehavior {
  readonly healthResponses?: unknown[];
  readonly onExecute?: (
    options: JsonRpcTransportRequestOptions,
    transport: FakeTransport,
    process: FakeProcess,
  ) => Promise<unknown>;
  readonly onShutdown?: (
    options: JsonRpcTransportRequestOptions,
    transport: FakeTransport,
    process: FakeProcess,
  ) => Promise<unknown>;
  readonly onNotify?: (
    options: JsonRpcTransportNotificationOptions,
    transport: FakeTransport,
    process: FakeProcess,
  ) => Promise<void>;
}

interface FakeTransportHooks {
  readonly onNotification: (notification: JsonRpcTransportNotification) => void;
  readonly onProtocolError: (error: JsonRpcTransportError) => void;
}

class FakeStdout extends EventEmitter {}

class FakeStdin {
  write(
    _chunk: string,
    _encoding?: BufferEncoding,
    callback?: (error?: Error | null) => void,
  ): boolean {
    callback?.(null);
    return true;
  }

  end(): void {}
}

class FakeProcess extends EventEmitter implements JsonRpcProcessLike {
  readonly stdin = new FakeStdin();
  readonly stdout = new FakeStdout();
  readonly pid: number;

  constructor(
    readonly behavior: FakeProcessBehavior,
    pid: number,
  ) {
    super();
    this.pid = pid;
  }

  exit(code: number | null, signal: NodeJS.Signals | null = null): void {
    this.emit('exit', code, signal);
  }
}

class FakeTransport implements JsonRpcStdioTransport {
  readonly requests: JsonRpcTransportRequestOptions[] = [];
  readonly notifications: JsonRpcTransportNotificationOptions[] = [];

  constructor(
    private readonly process: FakeProcess,
    private readonly hooks: FakeTransportHooks,
  ) {}

  emitNotification(notification: JsonRpcTransportNotification): void {
    this.hooks.onNotification(notification);
  }

  emitProtocolError(error: JsonRpcTransportError): void {
    this.hooks.onProtocolError(error);
  }

  async request<TResult = unknown>(options: JsonRpcTransportRequestOptions): Promise<TResult> {
    this.requests.push(options);
    if (options.method === 'health') {
      const next = this.process.behavior.healthResponses?.shift();
      return next as TResult;
    }
    if (options.method === 'execute') {
      const payload = await this.process.behavior.onExecute?.(options, this, this.process);
      return payload as TResult;
    }
    if (options.method === 'shutdown') {
      const payload = await this.process.behavior.onShutdown?.(options, this, this.process);
      return payload as TResult;
    }
    throw new Error(`Unexpected fake transport method "${options.method}".`);
  }

  async notify(options: JsonRpcTransportNotificationOptions): Promise<void> {
    this.notifications.push(options);
    await this.process.behavior.onNotify?.(options, this, this.process);
  }

  dispose(): void {}
}

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

function makeSpec(overrides: Partial<ProcessSpec> = {}): ProcessSpec {
  return {
    id: 'proc.alpha',
    label: 'Process Alpha',
    protocol: 'stdio-jsonrpc',
    spawn: {
      command: 'alpha-binary',
    },
    healthCheck: 'health',
    shutdown: 'shutdown',
    operations: [
      {
        id: 'render',
        label: 'Render',
      },
    ],
    ...overrides,
  };
}

function makeExecuteResult(
  overrides: Partial<ProcessRoundtripResult> = {},
): Record<string, unknown> {
  return {
    requestId: 'task-1',
    taskId: 'task-1',
    processId: 'proc.alpha',
    operationId: 'render',
    status: 'completed',
    returnedMaterials: [],
    ...overrides,
  };
}

describe('createProcessManager', () => {
  it('keeps declared processes stopped until startup is explicitly required', () => {
    let spawnCount = 0;
    const manager = createProcessManager({
      processes: [makeSpec()],
      spawnProcess: () => {
        spawnCount += 1;
        return new FakeProcess({}, 101);
      },
      createTransport: (process, hooks) => new FakeTransport(process as FakeProcess, hooks),
      now: () => '2026-07-04T20:00:00.000Z',
    });

    expect(manager.listStatuses()).toEqual([
      expect.objectContaining({
        processId: 'proc.alpha',
        state: 'stopped',
      }),
    ]);
    expect(manager.getStatus('proc.alpha')).toMatchObject({
      state: 'stopped',
    });
    expect(spawnCount).toBe(0);
  });

  it('spawns only declared trusted stdio-jsonrpc descriptors and rejects undeclared or unsupported entries', async () => {
    const manager = createProcessManager({
      processes: [makeSpec()],
      spawnProcess: () => new FakeProcess({
        healthResponses: [{ processId: 'proc.alpha', state: 'ready' }],
      }, 201),
      createTransport: (process, hooks) => new FakeTransport(process as FakeProcess, hooks),
    });

    await expect(manager.start('proc.missing')).rejects.toMatchObject({
      code: 'process-undeclared',
      processId: 'proc.missing',
    });

    expect(() => createProcessManager({
      processes: [
        {
          ...makeSpec({ id: 'proc.unsupported' }),
          protocol: 'tcp-jsonrpc' as never,
        },
      ],
    })).toThrow(/unsupported protocol/i);
  });

  it('projects health responses across starting, ready, busy, degraded, and failed states without respawning', async () => {
    let spawnCount = 0;
    const fakeProcess = new FakeProcess({
      healthResponses: [
        { processId: 'proc.alpha', state: 'starting' },
        { processId: 'proc.alpha', state: 'ready', version: { semver: '1.2.3' } },
        {
          processId: 'proc.alpha',
          state: 'busy',
          operationId: 'render',
          progress: { percent: 50, message: 'Half done' },
        },
        {
          processId: 'proc.alpha',
          state: 'degraded',
          message: 'Health latency is elevated.',
        },
        {
          processId: 'proc.alpha',
          state: 'failed',
          errorCode: 'worker-unavailable',
          recoverable: false,
          message: 'Worker pool is unavailable.',
        },
      ],
    }, 777);

    const manager = createProcessManager({
      processes: [makeSpec({ version: { semver: '1.0.0' } })],
      spawnProcess: () => {
        spawnCount += 1;
        return fakeProcess;
      },
      createTransport: (process, hooks) => new FakeTransport(process as FakeProcess, hooks),
      now: () => '2026-07-04T20:10:00.000Z',
    });

    await expect(manager.checkHealth('proc.alpha')).resolves.toMatchObject({
      state: 'starting',
      startedAt: '2026-07-04T20:10:00.000Z',
    });
    await expect(manager.checkHealth('proc.alpha')).resolves.toMatchObject({
      state: 'ready',
      pid: 777,
      version: { semver: '1.2.3' },
    });
    await expect(manager.checkHealth('proc.alpha')).resolves.toMatchObject({
      state: 'busy',
      operationId: 'render',
      progress: { percent: 50, message: 'Half done' },
    });
    await expect(manager.checkHealth('proc.alpha')).resolves.toMatchObject({
      state: 'degraded',
      healthCheck: 'health',
      message: 'Health latency is elevated.',
    });
    await expect(manager.checkHealth('proc.alpha')).resolves.toMatchObject({
      state: 'failed',
      errorCode: 'worker-unavailable',
      recoverable: false,
      message: 'Worker pool is unavailable.',
    });

    expect(spawnCount).toBe(1);
  });

  it('projects not-installed when the declared binary cannot be spawned', async () => {
    const manager = createProcessManager({
      processes: [makeSpec()],
      spawnProcess: () => {
        const error = new Error('spawn alpha-binary ENOENT') as NodeJS.ErrnoException;
        error.code = 'ENOENT';
        throw error;
      },
      createTransport: (process, hooks) => new FakeTransport(process as FakeProcess, hooks),
    });

    await expect(manager.checkHealth('proc.alpha')).resolves.toMatchObject({
      state: 'not-installed',
      installHint: 'Install or configure "alpha-binary" for process "proc.alpha".',
    });
  });

  it('executes correlated operations, captures progress/logs, and returns ready after success', async () => {
    let transportRef: FakeTransport | undefined;

    const manager = createProcessManager({
      processes: [makeSpec({ version: { semver: '1.0.0' } })],
      spawnProcess: () => new FakeProcess({
        healthResponses: [{ processId: 'proc.alpha', state: 'ready' }],
        onExecute: async (_options, transport) => {
          transport.emitNotification({
            kind: 'progress',
            method: 'progress',
            params: {
              processId: 'proc.alpha',
              operationId: 'render',
              taskId: 'task-1',
              progress: { percent: 75, message: 'Rendering' },
            },
          });
          transport.emitNotification({
            kind: 'log',
            method: 'log',
            params: {
              processId: 'proc.alpha',
              operationId: 'render',
              taskId: 'task-1',
              level: 'info',
              message: 'halfway there',
              timestamp: '2026-07-04T20:20:00.000Z',
            },
          });
          return makeExecuteResult({
            progress: {
              operationId: 'render',
              percent: 100,
              message: 'Done',
            },
          });
        },
      }, 404),
      createTransport: (process, hooks) => {
        transportRef = new FakeTransport(process as FakeProcess, hooks);
        return transportRef;
      },
    });

    await manager.start('proc.alpha');

    const result = await manager.execute({
      id: 'task-1',
      processId: 'proc.alpha',
      operationId: 'render',
      params: { preset: 'draft' },
    });

    expect(result).toMatchObject({
      requestId: 'task-1',
      processId: 'proc.alpha',
      operationId: 'render',
      status: 'completed',
      progress: {
        operationId: 'render',
        percent: 100,
        message: 'Done',
      },
      logs: [
        {
          level: 'info',
          message: 'halfway there',
          at: '2026-07-04T20:20:00.000Z',
        },
      ],
    });
    expect(transportRef?.requests.at(-1)).toMatchObject({
      method: 'execute',
      correlation: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-1',
      },
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        requestId: 'task-1',
        taskId: 'task-1',
        params: { preset: 'draft' },
      },
    });
    expect(manager.getStatus('proc.alpha')).toMatchObject({
      state: 'ready',
      pid: 404,
      version: { semver: '1.0.0' },
    });
  });

  it('returns failed operation results without leaving the process stuck busy', async () => {
    const manager = createProcessManager({
      processes: [makeSpec()],
      spawnProcess: () => new FakeProcess({
        healthResponses: [{ processId: 'proc.alpha', state: 'ready' }],
        onExecute: async () => makeExecuteResult({
          requestId: 'task-fail',
          taskId: 'task-fail',
          status: 'failed',
          diagnostics: [
            {
              id: 'diag.failure',
              severity: 'warning',
              message: 'Render failed cleanly.',
            },
          ],
        }),
      }, 505),
      createTransport: (process, hooks) => new FakeTransport(process as FakeProcess, hooks),
    });

    await manager.start('proc.alpha');

    await expect(manager.execute({
      id: 'task-fail',
      processId: 'proc.alpha',
      operationId: 'render',
    })).resolves.toMatchObject({
      status: 'failed',
      diagnostics: [
        {
          id: 'diag.failure',
          severity: 'warning',
          message: 'Render failed cleanly.',
        },
      ],
    });
    expect(manager.getStatus('proc.alpha')).toMatchObject({
      state: 'ready',
    });
  });

  it('cancels active operations with task/process/operation correlation and preserves the eventual cancelled result', async () => {
    const releaseExecute = createDeferred<Record<string, unknown>>();
    let transportRef: FakeTransport | undefined;

    const manager = createProcessManager({
      processes: [makeSpec()],
      spawnProcess: () => new FakeProcess({
        healthResponses: [{ processId: 'proc.alpha', state: 'ready' }],
        onExecute: async () => releaseExecute.promise,
      }, 606),
      createTransport: (process, hooks) => {
        transportRef = new FakeTransport(process as FakeProcess, hooks);
        return transportRef;
      },
    });

    await manager.start('proc.alpha');

    const execution = manager.execute({
      id: 'task-cancel',
      processId: 'proc.alpha',
      operationId: 'render',
    });
    await Promise.resolve();
    await manager.cancel('proc.alpha', {
      taskId: 'task-cancel',
      operationId: 'render',
      reason: 'user-aborted',
    });

    releaseExecute.resolve(makeExecuteResult({
      requestId: 'task-cancel',
      taskId: 'task-cancel',
      status: 'cancelled',
    }));

    await expect(execution).resolves.toMatchObject({
      status: 'cancelled',
    });
    expect(transportRef?.notifications).toContainEqual({
      method: 'cancel',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-cancel',
        reason: 'user-aborted',
      },
    });
    expect(manager.getStatus('proc.alpha')).toMatchObject({
      state: 'ready',
    });
  });

  it('rejects mismatched execute correlations and records a recoverable diagnostic without reviving the operation', async () => {
    const manager = createProcessManager({
      processes: [makeSpec()],
      spawnProcess: () => new FakeProcess({
        healthResponses: [{ processId: 'proc.alpha', state: 'ready' }],
        onExecute: async () => makeExecuteResult({
          taskId: 'task-other',
          requestId: 'task-other',
        }),
      }, 707),
      createTransport: (process, hooks) => new FakeTransport(process as FakeProcess, hooks),
    });

    await manager.start('proc.alpha');

    await expect(manager.execute({
      id: 'task-1',
      processId: 'proc.alpha',
      operationId: 'render',
    })).rejects.toMatchObject({
      errorClass: 'protocol-error',
      message: expect.stringContaining('requestId mismatch'),
    });
    expect(manager.getStatus('proc.alpha')).toMatchObject({
      state: 'failed',
      errorCode: 'protocol-error',
      diagnostics: expect.arrayContaining([
        expect.objectContaining({
          code: 'process/protocol-error',
        }),
      ]),
    });
  });

  it('records late progress and log notifications as recoverable diagnostics without mutating the terminal ready state', async () => {
    let transportRef: FakeTransport | undefined;

    const manager = createProcessManager({
      processes: [makeSpec()],
      spawnProcess: () => new FakeProcess({
        healthResponses: [{ processId: 'proc.alpha', state: 'ready' }],
        onExecute: async () => makeExecuteResult(),
      }, 808),
      createTransport: (process, hooks) => {
        transportRef = new FakeTransport(process as FakeProcess, hooks);
        return transportRef;
      },
    });

    await manager.start('proc.alpha');
    await manager.execute({
      id: 'task-1',
      processId: 'proc.alpha',
      operationId: 'render',
    });

    transportRef?.emitNotification({
      kind: 'progress',
      method: 'progress',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-1',
        progress: { percent: 99, message: 'too late' },
      },
    });
    transportRef?.emitNotification({
      kind: 'log',
      method: 'log',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-1',
        level: 'warn',
        message: 'late log',
      },
    });

    expect(manager.getStatus('proc.alpha')).toMatchObject({
      state: 'ready',
      diagnostics: expect.arrayContaining([
        expect.objectContaining({ code: 'process/late-progress' }),
        expect.objectContaining({ code: 'process/late-log' }),
      ]),
    });
  });

  it('tracks graceful shutdown through stopping back to stopped and tears down an in-flight operation correlation', async () => {
    const releaseShutdown = createDeferred<void>();
    let processRef: FakeProcess | undefined;

    const manager = createProcessManager({
      processes: [makeSpec({ restartPolicy: 'on-failure' })],
      spawnProcess: () => {
        const fakeProcess = new FakeProcess({
          healthResponses: [{ processId: 'proc.alpha', state: 'ready' }],
          onExecute: async (_options, _transport, process) => new Promise<unknown>((_resolve, reject) => {
            process.once('exit', (code, signal) => {
              reject(new JsonRpcTransportError('Process exited unexpectedly.', {
                code: -32001,
                errorClass: 'process-exited',
                method: 'execute',
                processId: 'proc.alpha',
                operationId: 'render',
                taskId: 'task-shutdown',
                exitCode: code,
                signal,
              }));
            });
          }),
          onShutdown: async (_options, _transport, process) => {
            await releaseShutdown.promise;
            process.exit(0);
            return { acknowledged: true, processId: 'proc.alpha' };
          },
        }, 909);
        processRef = fakeProcess;
        return fakeProcess;
      },
      createTransport: (process, hooks) => new FakeTransport(process as FakeProcess, hooks),
    });

    await manager.start('proc.alpha');
    const execution = manager.execute({
      id: 'task-shutdown',
      processId: 'proc.alpha',
      operationId: 'render',
    });
    const executionExpectation = expect(execution).rejects.toMatchObject({
      errorClass: 'process-exited',
    });

    const shutdownPromise = manager.shutdown('proc.alpha', { reason: 'host-closing' });
    expect(manager.getStatus('proc.alpha')).toMatchObject({
      state: 'stopping',
      reason: 'host-closing',
    });

    releaseShutdown.resolve(undefined);

    await expect(shutdownPromise).resolves.toMatchObject({
      state: 'stopped',
      message: 'Process Alpha stopped gracefully.',
    });
    await executionExpectation;
    expect(processRef).toBeDefined();
  });

  it('emits restart-policy hooks when a running process exits unexpectedly', async () => {
    let fakeProcess: FakeProcess | undefined;
    const restartEvents: ProcessManagerRestartPolicyEvent[] = [];

    const manager = createProcessManager({
      processes: [makeSpec({ restartPolicy: 'on-failure' })],
      spawnProcess: () => {
        fakeProcess = new FakeProcess({
          healthResponses: [{ processId: 'proc.alpha', state: 'ready' }],
        }, 333);
        return fakeProcess;
      },
      createTransport: (process, hooks) => new FakeTransport(process as FakeProcess, hooks),
      onRestartPolicyEvent: (event) => restartEvents.push(event),
    });

    await manager.start('proc.alpha');
    fakeProcess?.exit(1);

    expect(manager.getStatus('proc.alpha')).toMatchObject({
      state: 'failed',
      errorCode: 'process-exited',
    });
    expect(restartEvents).toContainEqual(expect.objectContaining({
      processId: 'proc.alpha',
      restartPolicy: 'on-failure',
      reason: 'process-exited',
      recoverable: true,
    }));
  });
});
