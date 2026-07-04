import { TextDecoder } from 'node:util';

export type JsonRpcId = number | string;

export type JsonRpcTransportErrorClass =
  | 'protocol-error'
  | 'timeout'
  | 'process-exited'
  | 'invalid-request';

export interface JsonRpcTransportCorrelation {
  readonly processId: string;
  readonly operationId?: string;
  readonly taskId?: string;
}

export interface JsonRpcTransportRequestOptions {
  readonly method: string;
  readonly params?: Record<string, unknown>;
  readonly correlation?: JsonRpcTransportCorrelation;
  readonly timeoutMs?: number;
}

export interface JsonRpcTransportNotificationOptions {
  readonly method: string;
  readonly params?: Record<string, unknown>;
}

export interface JsonRpcTransportProgressNotification {
  readonly kind: 'progress';
  readonly method: 'progress';
  readonly params: JsonRpcTransportCorrelation & {
    readonly progress: Record<string, unknown>;
  };
}

export interface JsonRpcTransportLogNotification {
  readonly kind: 'log';
  readonly method: 'log';
  readonly params: JsonRpcTransportCorrelation & {
    readonly level: 'debug' | 'info' | 'warn' | 'error';
    readonly message: string;
    readonly timestamp?: string;
  };
}

export interface JsonRpcTransportCancelNotification {
  readonly kind: 'cancel';
  readonly method: 'cancel';
  readonly params: JsonRpcTransportCorrelation;
}

export type JsonRpcTransportNotification =
  | JsonRpcTransportProgressNotification
  | JsonRpcTransportLogNotification
  | JsonRpcTransportCancelNotification;

export interface JsonRpcReadableStreamLike {
  on(event: 'data', listener: (chunk: string | Uint8Array) => void): unknown;
  on(event: 'close' | 'end', listener: () => void): unknown;
  off?(event: 'data' | 'close' | 'end', listener: (...args: unknown[]) => void): unknown;
  removeListener?(event: 'data' | 'close' | 'end', listener: (...args: unknown[]) => void): unknown;
  setEncoding?(encoding: BufferEncoding): unknown;
}

export interface JsonRpcWritableStreamLike {
  write(
    chunk: string,
    encoding?: BufferEncoding,
    callback?: (error?: Error | null) => void,
  ): boolean;
  end?(): void;
}

export interface JsonRpcProcessLike {
  readonly stdin: JsonRpcWritableStreamLike | null;
  readonly stdout: JsonRpcReadableStreamLike | null;
  readonly pid?: number;
  on(event: 'exit', listener: (code: number | null, signal: NodeJS.Signals | null) => void): unknown;
  on(event: 'error', listener: (error: Error) => void): unknown;
  off?(
    event: 'exit' | 'error',
    listener: ((code: number | null, signal: NodeJS.Signals | null) => void) | ((error: Error) => void),
  ): unknown;
  removeListener?(
    event: 'exit' | 'error',
    listener: ((code: number | null, signal: NodeJS.Signals | null) => void) | ((error: Error) => void),
  ): unknown;
}

export interface JsonRpcStdioTransportOptions {
  readonly process: JsonRpcProcessLike;
  readonly defaultTimeoutMs?: number;
  readonly onNotification?: (notification: JsonRpcTransportNotification) => void;
  readonly onProtocolError?: (error: JsonRpcTransportError) => void;
  readonly setTimeoutFn?: typeof globalThis.setTimeout;
  readonly clearTimeoutFn?: typeof globalThis.clearTimeout;
}

export interface JsonRpcStdioTransport {
  request<TResult = unknown>(options: JsonRpcTransportRequestOptions): Promise<TResult>;
  notify(options: JsonRpcTransportNotificationOptions): Promise<void>;
  dispose(): void;
}

interface JsonRpcErrorObject {
  readonly code: number;
  readonly message: string;
  readonly data?: unknown;
}

interface PendingRequest {
  readonly id: JsonRpcId;
  readonly method: string;
  readonly correlation?: JsonRpcTransportCorrelation;
  readonly reject: (reason: unknown) => void;
  readonly resolve: (value: unknown) => void;
  readonly timeoutHandle?: ReturnType<typeof globalThis.setTimeout>;
}

type JsonRpcIncomingMessage =
  | {
      readonly jsonrpc: '2.0';
      readonly id: JsonRpcId;
      readonly result: unknown;
    }
  | {
      readonly jsonrpc: '2.0';
      readonly id: JsonRpcId | null;
      readonly error: JsonRpcErrorObject;
    }
  | {
      readonly jsonrpc: '2.0';
      readonly method: string;
      readonly params?: unknown;
    };

export class JsonRpcTransportError extends Error {
  readonly code: number;
  readonly errorClass: JsonRpcTransportErrorClass;
  readonly method?: string;
  readonly requestId?: JsonRpcId | null;
  readonly processId?: string;
  readonly operationId?: string;
  readonly taskId?: string;
  readonly timeoutMs?: number;
  readonly exitCode?: number | null;
  readonly signal?: NodeJS.Signals | null;
  readonly detail?: string;
  readonly rawMessage?: unknown;

  constructor(
    message: string,
    options: {
      code: number;
      errorClass: JsonRpcTransportErrorClass;
      method?: string;
      requestId?: JsonRpcId | null;
      processId?: string;
      operationId?: string;
      taskId?: string;
      timeoutMs?: number;
      exitCode?: number | null;
      signal?: NodeJS.Signals | null;
      detail?: string;
      rawMessage?: unknown;
      cause?: unknown;
    },
  ) {
    super(message, { cause: options.cause });
    this.name = 'JsonRpcTransportError';
    this.code = options.code;
    this.errorClass = options.errorClass;
    this.method = options.method;
    this.requestId = options.requestId;
    this.processId = options.processId;
    this.operationId = options.operationId;
    this.taskId = options.taskId;
    this.timeoutMs = options.timeoutMs;
    this.exitCode = options.exitCode;
    this.signal = options.signal;
    this.detail = options.detail;
    this.rawMessage = options.rawMessage;
  }
}

export function createJsonRpcStdioTransport({
  process,
  defaultTimeoutMs = 30_000,
  onNotification,
  onProtocolError,
  setTimeoutFn = globalThis.setTimeout.bind(globalThis),
  clearTimeoutFn = globalThis.clearTimeout.bind(globalThis),
}: JsonRpcStdioTransportOptions): JsonRpcStdioTransport {
  const stdin = process.stdin;
  const stdout = process.stdout;
  if (!stdin || !stdout) {
    throw new JsonRpcTransportError('Process stdio streams are unavailable.', {
      code: -32001,
      errorClass: 'process-exited',
      exitCode: null,
      signal: null,
    });
  }

  stdout.setEncoding?.('utf8');

  const decoder = new TextDecoder('utf-8');
  const pendingRequests = new Map<JsonRpcId, PendingRequest>();
  let buffer = '';
  let nextRequestId = 0;
  let disposed = false;
  let exitInfo: { code: number | null; signal: NodeJS.Signals | null } | null = null;

  const rejectPending = (
    makeError: (request: PendingRequest) => JsonRpcTransportError,
  ) => {
    for (const request of pendingRequests.values()) {
      if (request.timeoutHandle !== undefined) clearTimeoutFn(request.timeoutHandle);
      request.reject(makeError(request));
    }
    pendingRequests.clear();
  };

  const detach = (
    target: {
      off?: (event: string, listener: (...args: unknown[]) => void) => unknown;
      removeListener?: (event: string, listener: (...args: unknown[]) => void) => unknown;
    },
    event: string,
    listener: (...args: unknown[]) => void,
  ) => {
    if (target.off) {
      target.off(event, listener);
      return;
    }
    target.removeListener?.(event, listener);
  };

  const emitProtocolError = (error: JsonRpcTransportError) => {
    onProtocolError?.(error);
  };

  const normalizeCorrelation = (
    message: unknown,
    request: PendingRequest,
    location: 'result' | 'error.data' | 'notification',
  ): JsonRpcTransportCorrelation => {
    if (!isRecord(message)) {
      throw new JsonRpcTransportError(`Expected ${location} to be an object.`, {
        code: -32600,
        errorClass: 'protocol-error',
        method: request.method,
        requestId: request.id,
        rawMessage: message,
      });
    }

    const processId = expectString(message.processId, `${location}.processId`, request);
    const operationId = readOptionalString(message.operationId, `${location}.operationId`, request);
    const taskId = readOptionalString(message.taskId, `${location}.taskId`, request);

    const expected = request.correlation;
    if (expected) {
      if (expected.processId !== processId) {
        throw new JsonRpcTransportError(`Correlation mismatch for processId on ${request.method}.`, {
          code: -32600,
          errorClass: 'protocol-error',
          method: request.method,
          requestId: request.id,
          processId,
          operationId,
          taskId,
          rawMessage: message,
        });
      }
      if (expected.operationId !== undefined && expected.operationId !== operationId) {
        throw new JsonRpcTransportError(`Correlation mismatch for operationId on ${request.method}.`, {
          code: -32600,
          errorClass: 'protocol-error',
          method: request.method,
          requestId: request.id,
          processId,
          operationId,
          taskId,
          rawMessage: message,
        });
      }
      if (expected.taskId !== undefined && expected.taskId !== taskId) {
        throw new JsonRpcTransportError(`Correlation mismatch for taskId on ${request.method}.`, {
          code: -32600,
          errorClass: 'protocol-error',
          method: request.method,
          requestId: request.id,
          processId,
          operationId,
          taskId,
          rawMessage: message,
        });
      }
    }

    return { processId, operationId, taskId };
  };

  const handleResponse = (message: JsonRpcIncomingMessage & { readonly id: JsonRpcId | null }) => {
    if (message.id === null) {
      emitProtocolError(new JsonRpcTransportError('Response id must not be null for host-initiated requests.', {
        code: -32600,
        errorClass: 'protocol-error',
        requestId: null,
        rawMessage: message,
      }));
      return;
    }
    const pending = pendingRequests.get(message.id);
    if (!pending) {
      emitProtocolError(new JsonRpcTransportError(`Received response for unknown request id "${String(message.id)}".`, {
        code: -32600,
        errorClass: 'protocol-error',
        requestId: message.id,
        rawMessage: message,
      }));
      return;
    }

    pendingRequests.delete(message.id);
    if (pending.timeoutHandle !== undefined) clearTimeoutFn(pending.timeoutHandle);

    try {
      if ('result' in message) {
        normalizeCorrelation(message.result, pending, 'result');
        pending.resolve(message.result);
        return;
      }

      const data = isRecord(message.error.data) ? message.error.data : undefined;
      const correlation = pending.correlation
        ? normalizeCorrelation(data, pending, 'error.data')
        : undefined;
      const errorClass = parseIncomingErrorClass(data?.class);
      pending.reject(new JsonRpcTransportError(message.error.message, {
        code: message.error.code,
        errorClass,
        method: pending.method,
        requestId: pending.id,
        processId: correlation?.processId,
        operationId: correlation?.operationId,
        taskId: correlation?.taskId,
        detail: typeof data?.detail === 'string' ? data.detail : undefined,
        rawMessage: message,
      }));
    } catch (error) {
      pending.reject(error);
    }
  };

  const handleNotification = (message: Extract<JsonRpcIncomingMessage, { readonly method: string }>) => {
    switch (message.method) {
      case 'progress': {
        const params = validateNotificationCorrelation(message.params, message.method, true);
        if (!isRecord(message.params) || !isRecord(message.params.progress)) {
          throw new JsonRpcTransportError('Progress notifications must include params.progress.', {
            code: -32600,
            errorClass: 'protocol-error',
            rawMessage: message,
          });
        }
        onNotification?.({
          kind: 'progress',
          method: 'progress',
          params: {
            ...params,
            progress: message.params.progress,
          },
        });
        return;
      }
      case 'log': {
        const params = validateNotificationCorrelation(message.params, message.method, false);
        if (!isRecord(message.params)) {
          throw new JsonRpcTransportError('Log notifications must include params.', {
            code: -32600,
            errorClass: 'protocol-error',
            rawMessage: message,
          });
        }
        const level = expectString(message.params.level, 'params.level');
        if (!isLogLevel(level)) {
          throw new JsonRpcTransportError('Log notifications must include a valid params.level.', {
            code: -32600,
            errorClass: 'protocol-error',
            rawMessage: message,
          });
        }
        const logMessage = expectString(message.params.message, 'params.message');
        const timestamp = readOptionalString(message.params.timestamp, 'params.timestamp');
        onNotification?.({
          kind: 'log',
          method: 'log',
          params: {
            ...params,
            level,
            message: logMessage,
            timestamp,
          },
        });
        return;
      }
      case 'cancel': {
        const params = validateNotificationCorrelation(message.params, message.method, true);
        onNotification?.({
          kind: 'cancel',
          method: 'cancel',
          params,
        });
        return;
      }
      default:
        throw new JsonRpcTransportError(`Unknown JSON-RPC notification method "${message.method}".`, {
          code: -32601,
          errorClass: 'protocol-error',
          rawMessage: message,
        });
    }
  };

  const onData = (chunk: string | Uint8Array) => {
    if (disposed) return;
    buffer += typeof chunk === 'string'
      ? chunk
      : decoder.decode(chunk, { stream: true });

    let newlineIndex = buffer.indexOf('\n');
    while (newlineIndex >= 0) {
      const rawLine = buffer.slice(0, newlineIndex).replace(/\r$/, '');
      buffer = buffer.slice(newlineIndex + 1);
      if (rawLine.trim().length === 0) {
        emitProtocolError(new JsonRpcTransportError('Received empty JSON-RPC line.', {
          code: -32600,
          errorClass: 'protocol-error',
          rawMessage: rawLine,
        }));
      } else {
        try {
          const parsed = parseIncomingMessage(rawLine);
          if ('method' in parsed) {
            handleNotification(parsed);
          } else {
            handleResponse(parsed);
          }
        } catch (error) {
          emitProtocolError(asTransportError(error, rawLine));
        }
      }
      newlineIndex = buffer.indexOf('\n');
    }
  };

  const onExit = (code: number | null, signal: NodeJS.Signals | null) => {
    exitInfo = { code, signal };
    rejectPending((request) => new JsonRpcTransportError('Process exited unexpectedly.', {
      code: -32001,
      errorClass: 'process-exited',
      method: request.method,
      requestId: request.id,
      processId: request.correlation?.processId,
      operationId: request.correlation?.operationId,
      taskId: request.correlation?.taskId,
      exitCode: code,
      signal,
    }));
  };

  const onProcessError = (error: Error) => {
    rejectPending((request) => new JsonRpcTransportError(error.message, {
      code: -32001,
      errorClass: 'process-exited',
      method: request.method,
      requestId: request.id,
      processId: request.correlation?.processId,
      operationId: request.correlation?.operationId,
      taskId: request.correlation?.taskId,
      exitCode: exitInfo?.code ?? null,
      signal: exitInfo?.signal ?? null,
      cause: error,
    }));
  };

  const onStreamClosed = () => {
    if (exitInfo) return;
    onExit(null, null);
  };

  stdout.on('data', onData);
  stdout.on('end', onStreamClosed);
  stdout.on('close', onStreamClosed);
  process.on('exit', onExit);
  process.on('error', onProcessError);

  const writeMessage = async (message: Record<string, unknown>): Promise<void> => {
    if (disposed) {
      throw new JsonRpcTransportError('Transport has been disposed.', {
        code: -32603,
        errorClass: 'protocol-error',
      });
    }
    if (exitInfo) {
      throw new JsonRpcTransportError('Process exited before message could be written.', {
        code: -32001,
        errorClass: 'process-exited',
        exitCode: exitInfo.code,
        signal: exitInfo.signal,
      });
    }

    const payload = `${JSON.stringify(message)}\n`;
    await new Promise<void>((resolve, reject) => {
      stdin.write(payload, 'utf8', (error) => {
        if (error) {
          reject(new JsonRpcTransportError(error.message, {
            code: -32001,
            errorClass: 'process-exited',
            exitCode: exitInfo?.code ?? null,
            signal: exitInfo?.signal ?? null,
            cause: error,
          }));
          return;
        }
        resolve();
      });
    });
  };

  return {
    async request<TResult = unknown>({
      method,
      params,
      correlation,
      timeoutMs = defaultTimeoutMs,
    }: JsonRpcTransportRequestOptions): Promise<TResult> {
      if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
        throw new JsonRpcTransportError('Request timeout must be a positive finite number.', {
          code: -32602,
          errorClass: 'invalid-request',
          method,
          processId: correlation?.processId,
          operationId: correlation?.operationId,
          taskId: correlation?.taskId,
          timeoutMs,
        });
      }

      nextRequestId += 1;
      const id = nextRequestId;

      return new Promise<TResult>(async (resolve, reject) => {
        const timeoutHandle = setTimeoutFn(() => {
          pendingRequests.delete(id);
          reject(new JsonRpcTransportError(`Request "${method}" timed out after ${timeoutMs}ms.`, {
            code: -32000,
            errorClass: 'timeout',
            method,
            requestId: id,
            processId: correlation?.processId,
            operationId: correlation?.operationId,
            taskId: correlation?.taskId,
            timeoutMs,
          }));
        }, timeoutMs);

        pendingRequests.set(id, {
          id,
          method,
          correlation,
          resolve,
          reject,
          timeoutHandle,
        });

        try {
          await writeMessage({
            jsonrpc: '2.0',
            id,
            method,
            params: params ?? {},
          });
        } catch (error) {
          clearTimeoutFn(timeoutHandle);
          pendingRequests.delete(id);
          reject(error);
        }
      });
    },

    async notify({ method, params }: JsonRpcTransportNotificationOptions): Promise<void> {
      await writeMessage({
        jsonrpc: '2.0',
        method,
        params: params ?? {},
      });
    },

    dispose() {
      if (disposed) return;
      disposed = true;
      if (buffer.trim().length > 0) {
        emitProtocolError(new JsonRpcTransportError('Transport disposed with an unterminated JSON-RPC line.', {
          code: -32600,
          errorClass: 'protocol-error',
          rawMessage: buffer,
        }));
      }
      rejectPending((request) => new JsonRpcTransportError('Transport disposed.', {
        code: -32603,
        errorClass: 'protocol-error',
        method: request.method,
        requestId: request.id,
        processId: request.correlation?.processId,
        operationId: request.correlation?.operationId,
        taskId: request.correlation?.taskId,
      }));
      detach(stdout, 'data', onData as (...args: unknown[]) => void);
      detach(stdout, 'end', onStreamClosed as (...args: unknown[]) => void);
      detach(stdout, 'close', onStreamClosed as (...args: unknown[]) => void);
      detach(process, 'exit', onExit as (...args: unknown[]) => void);
      detach(process, 'error', onProcessError as (...args: unknown[]) => void);
    },
  };
}

function asTransportError(error: unknown, rawMessage: unknown): JsonRpcTransportError {
  if (error instanceof JsonRpcTransportError) return error;
  if (error instanceof SyntaxError) {
    return new JsonRpcTransportError('Malformed JSON-RPC payload.', {
      code: -32700,
      errorClass: 'protocol-error',
      cause: error,
      rawMessage,
    });
  }
  if (error instanceof Error) {
    return new JsonRpcTransportError(error.message, {
      code: -32603,
      errorClass: 'protocol-error',
      cause: error,
      rawMessage,
    });
  }
  return new JsonRpcTransportError('Unknown transport failure.', {
    code: -32603,
    errorClass: 'protocol-error',
    rawMessage,
    cause: error,
  });
}

function parseIncomingMessage(rawLine: string): JsonRpcIncomingMessage {
  const parsed = JSON.parse(rawLine) as unknown;
  if (!isRecord(parsed)) {
    throw new JsonRpcTransportError('JSON-RPC payload must be an object.', {
      code: -32600,
      errorClass: 'protocol-error',
      rawMessage: parsed,
    });
  }
  if (parsed.jsonrpc !== '2.0') {
    throw new JsonRpcTransportError('JSON-RPC payload must include jsonrpc="2.0".', {
      code: -32600,
      errorClass: 'protocol-error',
      rawMessage: parsed,
    });
  }
  if ('method' in parsed) {
    if (typeof parsed.method !== 'string' || parsed.method.length === 0) {
      throw new JsonRpcTransportError('JSON-RPC notifications must include a method string.', {
        code: -32600,
        errorClass: 'protocol-error',
        rawMessage: parsed,
      });
    }
    if ('id' in parsed) {
      throw new JsonRpcTransportError('Process-to-host requests are not supported by the stdio transport.', {
        code: -32600,
        errorClass: 'protocol-error',
        rawMessage: parsed,
      });
    }
    return parsed as Extract<JsonRpcIncomingMessage, { readonly method: string }>;
  }
  if ('result' in parsed) {
    if (!isJsonRpcId(parsed.id)) {
      throw new JsonRpcTransportError('JSON-RPC responses must include a numeric or string id.', {
        code: -32600,
        errorClass: 'protocol-error',
        rawMessage: parsed,
      });
    }
    return parsed as Extract<JsonRpcIncomingMessage, { readonly result: unknown }>;
  }
  if ('error' in parsed) {
    if (!('id' in parsed) || (!isJsonRpcId(parsed.id) && parsed.id !== null)) {
      throw new JsonRpcTransportError('JSON-RPC error responses must include an id or null id.', {
        code: -32600,
        errorClass: 'protocol-error',
        rawMessage: parsed,
      });
    }
    if (!isRecord(parsed.error) || typeof parsed.error.code !== 'number' || typeof parsed.error.message !== 'string') {
      throw new JsonRpcTransportError('JSON-RPC error responses must include code and message fields.', {
        code: -32600,
        errorClass: 'protocol-error',
        rawMessage: parsed,
      });
    }
    return parsed as Extract<JsonRpcIncomingMessage, { readonly error: JsonRpcErrorObject }>;
  }
  throw new JsonRpcTransportError('JSON-RPC payload must include a result, error, or method field.', {
    code: -32600,
    errorClass: 'protocol-error',
    rawMessage: parsed,
  });
}

function validateNotificationCorrelation(
  params: unknown,
  method: string,
  requireOperationFields: boolean,
): JsonRpcTransportCorrelation {
  if (!isRecord(params)) {
    throw new JsonRpcTransportError(`${method} notifications must include params.`, {
      code: -32600,
      errorClass: 'protocol-error',
      rawMessage: params,
    });
  }

  const processId = expectString(params.processId, 'params.processId');
  const operationId = readOptionalString(params.operationId, 'params.operationId');
  const taskId = readOptionalString(params.taskId, 'params.taskId');

  if (requireOperationFields && (operationId === undefined || taskId === undefined)) {
    throw new JsonRpcTransportError(`${method} notifications must include params.operationId and params.taskId.`, {
      code: -32600,
      errorClass: 'protocol-error',
      processId,
      operationId,
      taskId,
      rawMessage: params,
    });
  }
  if ((operationId === undefined) !== (taskId === undefined)) {
    throw new JsonRpcTransportError(`${method} notifications must include both params.operationId and params.taskId together.`, {
      code: -32600,
      errorClass: 'protocol-error',
      processId,
      operationId,
      taskId,
      rawMessage: params,
    });
  }

  return { processId, operationId, taskId };
}

function parseIncomingErrorClass(value: unknown): JsonRpcTransportErrorClass {
  switch (value) {
    case 'timeout':
    case 'process-exited':
    case 'invalid-request':
    case 'protocol-error':
      return value;
    default:
      return 'protocol-error';
  }
}

function isLogLevel(value: string): value is JsonRpcTransportLogNotification['params']['level'] {
  return value === 'debug' || value === 'info' || value === 'warn' || value === 'error';
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isJsonRpcId(value: unknown): value is JsonRpcId {
  return typeof value === 'number' || typeof value === 'string';
}

function expectString(
  value: unknown,
  path: string,
  request?: Pick<PendingRequest, 'id' | 'method'>,
): string {
  if (typeof value !== 'string' || value.length === 0) {
    throw new JsonRpcTransportError(`Expected ${path} to be a non-empty string.`, {
      code: -32600,
      errorClass: 'protocol-error',
      method: request?.method,
      requestId: request?.id,
      rawMessage: value,
    });
  }
  return value;
}

function readOptionalString(
  value: unknown,
  path: string,
  request?: Pick<PendingRequest, 'id' | 'method'>,
): string | undefined {
  if (value === undefined) return undefined;
  return expectString(value, path, request);
}
