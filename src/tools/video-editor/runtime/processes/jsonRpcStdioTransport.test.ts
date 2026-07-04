import { EventEmitter } from 'node:events';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createJsonRpcStdioTransport,
  JsonRpcTransportError,
  type JsonRpcStdioTransport,
} from './jsonRpcStdioTransport';

class FakeStdout extends EventEmitter {
  setEncoding(_encoding: BufferEncoding) {}

  pushLine(line: string): void {
    this.emit('data', `${line}\n`);
  }

  pushChunk(chunk: string | Uint8Array): void {
    this.emit('data', chunk);
  }

  close(): void {
    this.emit('close');
  }
}

class FakeStdin {
  readonly writes: string[] = [];

  write(
    chunk: string,
    _encoding?: BufferEncoding,
    callback?: (error?: Error | null) => void,
  ): boolean {
    this.writes.push(chunk);
    callback?.(null);
    return true;
  }
}

class FakeProcess extends EventEmitter {
  readonly stdin = new FakeStdin();
  readonly stdout = new FakeStdout();
  readonly pid = 4242;

  exit(code: number | null, signal: NodeJS.Signals | null = null): void {
    this.emit('exit', code, signal);
  }
}

describe('createJsonRpcStdioTransport', () => {
  const transports: JsonRpcStdioTransport[] = [];

  afterEach(() => {
    while (transports.length > 0) transports.pop()?.dispose();
    vi.useRealTimers();
  });

  it('writes newline-delimited UTF-8 JSON-RPC requests and resolves correlated responses', async () => {
    const fakeProcess = new FakeProcess();
    const transport = createJsonRpcStdioTransport({ process: fakeProcess });
    transports.push(transport);

    const request = transport.request({
      method: 'execute',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-1',
        input: { label: 'caf\u00e9 noir' },
      },
      correlation: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-1',
      },
    });

    expect(fakeProcess.stdin.writes).toHaveLength(1);
    expect(fakeProcess.stdin.writes[0].endsWith('\n')).toBe(true);

    const outbound = JSON.parse(fakeProcess.stdin.writes[0].trim());
    expect(outbound).toMatchObject({
      jsonrpc: '2.0',
      method: 'execute',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-1',
        input: { label: 'caf\u00e9 noir' },
      },
    });

    fakeProcess.stdout.pushChunk(`{"jsonrpc":"2.0","id":${outbound.id},"result":{"processId":"proc.alpha",`);
    fakeProcess.stdout.pushLine(`"operationId":"render","taskId":"task-1","output":{"ok":true}}}`);

    await expect(request).resolves.toEqual({
      processId: 'proc.alpha',
      operationId: 'render',
      taskId: 'task-1',
      output: { ok: true },
    });
  });

  it('surfaces malformed messages, missing jsonrpc, and unknown notification methods as protocol errors', () => {
    const fakeProcess = new FakeProcess();
    const protocolErrors: JsonRpcTransportError[] = [];
    const transport = createJsonRpcStdioTransport({
      process: fakeProcess,
      onProtocolError: (error) => protocolErrors.push(error),
    });
    transports.push(transport);

    fakeProcess.stdout.pushLine('{"jsonrpc":"2.0"');
    fakeProcess.stdout.pushLine('{"id":1,"result":{"processId":"proc.alpha"}}');
    fakeProcess.stdout.pushLine('{"jsonrpc":"2.0","method":"mystery","params":{"processId":"proc.alpha"}}');

    expect(protocolErrors).toHaveLength(3);
    expect(protocolErrors.map((error) => error.errorClass)).toEqual([
      'protocol-error',
      'protocol-error',
      'protocol-error',
    ]);
    expect(protocolErrors[0].code).toBe(-32700);
    expect(protocolErrors[1].message).toContain('jsonrpc="2.0"');
    expect(protocolErrors[2].message).toContain('Unknown JSON-RPC notification method');
  });

  it('rejects timed out requests with timeout metadata', async () => {
    vi.useFakeTimers();

    const fakeProcess = new FakeProcess();
    const transport = createJsonRpcStdioTransport({ process: fakeProcess });
    transports.push(transport);

    const request = transport.request({
      method: 'health',
      params: { processId: 'proc.alpha' },
      correlation: { processId: 'proc.alpha' },
      timeoutMs: 500,
    });
    const expectation = expect(request).rejects.toMatchObject({
      errorClass: 'timeout',
      code: -32000,
      method: 'health',
      processId: 'proc.alpha',
      timeoutMs: 500,
    });

    await vi.advanceTimersByTimeAsync(500);

    await expectation;
  });

  it('rejects pending and future requests when the process exits', async () => {
    const fakeProcess = new FakeProcess();
    const transport = createJsonRpcStdioTransport({ process: fakeProcess });
    transports.push(transport);

    const request = transport.request({
      method: 'execute',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-exit',
      },
      correlation: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-exit',
      },
      timeoutMs: 5_000,
    });
    const pendingExpectation = expect(request).rejects.toMatchObject({
      errorClass: 'process-exited',
      code: -32001,
      method: 'execute',
      processId: 'proc.alpha',
      operationId: 'render',
      taskId: 'task-exit',
      exitCode: 1,
    });

    fakeProcess.exit(1);

    await pendingExpectation;

    await expect(transport.request({
      method: 'health',
      params: { processId: 'proc.alpha' },
      correlation: { processId: 'proc.alpha' },
    })).rejects.toMatchObject({
      errorClass: 'process-exited',
      code: -32001,
      exitCode: 1,
    });
  });

  it('rejects messages with missing correlation fields on responses and notifications', async () => {
    const fakeProcess = new FakeProcess();
    const protocolErrors: JsonRpcTransportError[] = [];
    const transport = createJsonRpcStdioTransport({
      process: fakeProcess,
      onProtocolError: (error) => protocolErrors.push(error),
    });
    transports.push(transport);

    const request = transport.request({
      method: 'execute',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-corr',
      },
      correlation: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-corr',
      },
    });
    const rejection = expect(request).rejects.toMatchObject({
      errorClass: 'protocol-error',
      code: -32600,
      method: 'execute',
    });

    const outbound = JSON.parse(fakeProcess.stdin.writes[0].trim());
    fakeProcess.stdout.pushLine(JSON.stringify({
      jsonrpc: '2.0',
      id: outbound.id,
      result: {
        processId: 'proc.alpha',
        operationId: 'render',
      },
    }));

    await rejection;

    fakeProcess.stdout.pushLine(JSON.stringify({
      jsonrpc: '2.0',
      method: 'progress',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        progress: { percent: 10 },
      },
    }));

    expect(protocolErrors).toHaveLength(1);
    expect(protocolErrors[0].message).toContain('taskId');
  });

  it('emits progress, log, and cancel notifications with validated correlation', () => {
    const fakeProcess = new FakeProcess();
    const notifications: Array<string> = [];
    const transport = createJsonRpcStdioTransport({
      process: fakeProcess,
      onNotification: (notification) => notifications.push(notification.kind),
    });
    transports.push(transport);

    fakeProcess.stdout.pushLine(JSON.stringify({
      jsonrpc: '2.0',
      method: 'progress',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-note',
        progress: { percent: 25, message: 'working' },
      },
    }));
    fakeProcess.stdout.pushLine(JSON.stringify({
      jsonrpc: '2.0',
      method: 'log',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-note',
        level: 'info',
        message: 'halfway',
        timestamp: '2026-07-04T19:30:00.000Z',
      },
    }));
    fakeProcess.stdout.pushLine(JSON.stringify({
      jsonrpc: '2.0',
      method: 'cancel',
      params: {
        processId: 'proc.alpha',
        operationId: 'render',
        taskId: 'task-note',
      },
    }));

    expect(notifications).toEqual(['progress', 'log', 'cancel']);
  });
});
