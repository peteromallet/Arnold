import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import type {
  CapabilityFinding,
  ExtensionDiagnostic,
  ProcessLogSummary,
  ProcessProgressEvent,
  ProcessRoundtripRequest,
  ProcessRoundtripResult,
  ProcessSpec,
  ProcessStatus,
} from '@reigh/editor-sdk';
import {
  createJsonRpcStdioTransport,
  JsonRpcTransportError,
  type JsonRpcProcessLike,
  type JsonRpcStdioTransport,
  type JsonRpcTransportCorrelation,
  type JsonRpcTransportLogNotification,
  type JsonRpcTransportNotification,
  type JsonRpcTransportNotificationOptions,
  type JsonRpcTransportProgressNotification,
} from './jsonRpcStdioTransport';

type ProcessState = ProcessStatus['state'];

const PROCESS_STATES = new Set<ProcessState>([
  'not-installed',
  'stopped',
  'starting',
  'ready',
  'busy',
  'degraded',
  'failed',
  'stopping',
]);

interface ProcessHealthPayload extends Record<string, unknown> {
  readonly processId: string;
  readonly state: ProcessState;
}

interface ProcessManagerTransportHooks {
  readonly onNotification: (notification: JsonRpcTransportNotification) => void;
  readonly onProtocolError: (error: JsonRpcTransportError) => void;
}

interface ActiveOperationRecord {
  readonly correlation: JsonRpcTransportCorrelation;
  readonly key: string;
  readonly request: ProcessRoundtripRequest;
  logs: ProcessLogSummary[];
  progress?: ProcessProgressEvent;
  cancelRequested: boolean;
  cancelPromise?: Promise<ProcessStatus>;
}

interface CompletedOperationRecord {
  readonly key: string;
  readonly correlation: JsonRpcTransportCorrelation;
  readonly finishedAt: string;
  readonly status: ProcessRoundtripResult['status'];
}

interface ProcessRecord {
  readonly spec: ProcessSpec;
  status: ProcessStatus;
  diagnostics: ExtensionDiagnostic[];
  process?: JsonRpcProcessLike;
  transport?: JsonRpcStdioTransport;
  startedAt?: string;
  startupPromise?: Promise<JsonRpcProcessLike>;
  shutdownPromise?: Promise<ProcessStatus>;
  expectedExit: boolean;
  exitPromise?: Promise<void>;
  resolveExit?: () => void;
  activeOperation?: ActiveOperationRecord;
  completedOperations: CompletedOperationRecord[];
}

export interface ProcessManagerStartOptions {
  readonly timeoutMs?: number;
}

export interface ProcessManagerHealthOptions {
  readonly timeoutMs?: number;
}

export interface ProcessManagerExecuteOptions {
  readonly timeoutMs?: number;
}

export interface ProcessManagerCancelOptions {
  readonly taskId: string;
  readonly operationId: string;
  readonly reason?: string;
}

export interface ProcessManagerShutdownOptions {
  readonly reason?: string;
  readonly timeoutMs?: number;
}

export interface ProcessManagerRestartPolicyEvent {
  readonly processId: string;
  readonly restartPolicy: NonNullable<ProcessSpec['restartPolicy']>;
  readonly reason: 'process-exited' | 'process-error' | 'execute-timeout' | 'shutdown-timeout';
  readonly recoverable: boolean;
  readonly operationId?: string;
  readonly taskId?: string;
}

export interface ProcessManager {
  getDeclaredProcesses(): readonly ProcessSpec[];
  getProcessSpec(processId: string): ProcessSpec | undefined;
  getStatus(processId: string): ProcessStatus | undefined;
  listStatuses(): readonly ProcessStatus[];
  start(processId: string, options?: ProcessManagerStartOptions): Promise<ProcessStatus>;
  checkHealth(processId: string, options?: ProcessManagerHealthOptions): Promise<ProcessStatus>;
  execute(
    request: ProcessRoundtripRequest,
    options?: ProcessManagerExecuteOptions,
  ): Promise<ProcessRoundtripResult>;
  cancel(processId: string, options: ProcessManagerCancelOptions): Promise<ProcessStatus>;
  shutdown(processId: string, options?: ProcessManagerShutdownOptions): Promise<ProcessStatus>;
  dispose(): Promise<void>;
}

export interface CreateProcessManagerOptions {
  readonly processes: readonly ProcessSpec[];
  readonly spawnProcess?: (spec: ProcessSpec) => JsonRpcProcessLike;
  readonly createTransport?: (
    process: JsonRpcProcessLike,
    hooks: ProcessManagerTransportHooks,
  ) => JsonRpcStdioTransport;
  readonly now?: () => string;
  readonly defaultHealthTimeoutMs?: number;
  readonly defaultExecuteTimeoutMs?: number;
  readonly defaultShutdownTimeoutMs?: number;
  readonly onRestartPolicyEvent?: (event: ProcessManagerRestartPolicyEvent) => void;
}

export class ProcessManagerError extends Error {
  readonly code:
    | 'process-undeclared'
    | 'unsupported-protocol'
    | 'operation-undeclared'
    | 'operation-active';
  readonly processId?: string;
  readonly operationId?: string;
  readonly taskId?: string;

  constructor(
    message: string,
    options: {
      code:
        | 'process-undeclared'
        | 'unsupported-protocol'
        | 'operation-undeclared'
        | 'operation-active';
      processId?: string;
      operationId?: string;
      taskId?: string;
      cause?: unknown;
    },
  ) {
    super(message, { cause: options.cause });
    this.name = 'ProcessManagerError';
    this.code = options.code;
    this.processId = options.processId;
    this.operationId = options.operationId;
    this.taskId = options.taskId;
  }
}

function defaultNow(): string {
  return new Date().toISOString();
}

function createDefaultSpawnProcess(spec: ProcessSpec): ChildProcessWithoutNullStreams {
  return spawn(spec.spawn.command, [...(spec.spawn.args ?? [])], {
    cwd: spec.spawn.cwd,
    env: {
      ...process.env,
      ...spec.spawn.env,
    },
    shell: false,
    stdio: 'pipe',
  });
}

function createStoppedStatus(spec: ProcessSpec, now: () => string): ProcessStatus {
  return Object.freeze({
    processId: spec.id,
    label: spec.label,
    state: 'stopped',
    message: `${spec.label} is stopped.`,
    updatedAt: now(),
  });
}

function createStatus(
  spec: ProcessSpec,
  state: ProcessState,
  now: () => string,
  details: Record<string, unknown> = {},
): ProcessStatus {
  const message = typeof details.message === 'string' ? details.message : undefined;
  const base = {
    processId: spec.id,
    label: spec.label,
    state,
    updatedAt: now(),
    ...details,
  };

  switch (state) {
    case 'not-installed':
      return Object.freeze({
        ...base,
        state,
        message: message ?? `${spec.label} is not installed.`,
      });
    case 'stopped':
      return Object.freeze({
        ...base,
        state,
        message: message ?? `${spec.label} is stopped.`,
      });
    case 'starting':
      return Object.freeze({
        ...base,
        state,
        message: message ?? `${spec.label} is starting.`,
      });
    case 'ready':
      return Object.freeze({
        ...base,
        state,
        message: message ?? `${spec.label} is ready.`,
      });
    case 'busy':
      return Object.freeze({
        ...base,
        state,
        message: message ?? `${spec.label} is busy.`,
      });
    case 'degraded':
      return Object.freeze({
        ...base,
        state,
        message: message ?? `${spec.label} is degraded.`,
      });
    case 'failed':
      return Object.freeze({
        ...base,
        state,
        message: message ?? `${spec.label} failed.`,
      });
    case 'stopping':
      return Object.freeze({
        ...base,
        state,
        message: message ?? `${spec.label} is stopping.`,
      });
  }
}

function isProcessState(value: unknown): value is ProcessState {
  return typeof value === 'string' && PROCESS_STATES.has(value as ProcessState);
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function installHint(spec: ProcessSpec): string {
  return `Install or configure "${spec.spawn.command}" for process "${spec.id}".`;
}

function looksLikeErrno(error: unknown): error is NodeJS.ErrnoException {
  return typeof error === 'object' && error !== null && ('code' in error || 'message' in error);
}

function protocolGuard(spec: ProcessSpec): void {
  if (spec.protocol !== 'stdio-jsonrpc') {
    throw new ProcessManagerError(
      `Process "${spec.id}" uses unsupported protocol "${String(spec.protocol)}".`,
      {
        code: 'unsupported-protocol',
        processId: spec.id,
      },
    );
  }
}

function freezeDiagnostics(
  diagnostics: readonly ExtensionDiagnostic[],
): readonly ExtensionDiagnostic[] {
  return Object.freeze(diagnostics.map((diagnostic) => Object.freeze({
    ...diagnostic,
    ...(diagnostic.detail ? { detail: Object.freeze({ ...diagnostic.detail }) } : {}),
  })));
}

function freezeProgress(progress: ProcessProgressEvent): ProcessProgressEvent {
  return Object.freeze({ ...progress });
}

function freezeLogs(logs: readonly ProcessLogSummary[]): readonly ProcessLogSummary[] {
  return Object.freeze(logs.map((log) => Object.freeze({
    ...log,
    ...(log.detail ? { detail: Object.freeze({ ...log.detail }) } : {}),
  })));
}

function operationKey(correlation: JsonRpcTransportCorrelation): string {
  return `${correlation.processId}:${correlation.operationId ?? ''}:${correlation.taskId ?? ''}`;
}

function readOptionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function isLogLevel(value: unknown): value is ProcessLogSummary['level'] | 'warn' {
  return value === 'debug' || value === 'info' || value === 'warning' || value === 'warn' || value === 'error';
}

function normalizeProgressEvent(
  notification: JsonRpcTransportProgressNotification,
): ProcessProgressEvent {
  const progress = asObject(notification.params.progress) ?? {};
  const percent = typeof progress.percent === 'number' && Number.isFinite(progress.percent)
    ? progress.percent
    : undefined;
  const totalSteps = typeof progress.totalSteps === 'number' && Number.isFinite(progress.totalSteps)
    ? progress.totalSteps
    : undefined;
  const event: ProcessProgressEvent = {
    operationId: notification.params.operationId ?? '',
    ...(percent !== undefined ? { percent } : {}),
    ...(typeof progress.message === 'string' ? { message: progress.message } : {}),
    ...(typeof progress.currentStep === 'string' ? { currentStep: progress.currentStep } : {}),
    ...(totalSteps !== undefined ? { totalSteps } : {}),
  };
  return freezeProgress(event);
}

function normalizeLogSummary(
  notification: JsonRpcTransportLogNotification,
): ProcessLogSummary {
  const level = notification.params.level === 'warn'
    ? 'warning'
    : notification.params.level;
  return Object.freeze({
    level,
    message: notification.params.message,
    ...(notification.params.timestamp ? { at: notification.params.timestamp } : {}),
  });
}

function normalizeCapabilityFinding(
  value: unknown,
  request: ProcessRoundtripRequest,
): CapabilityFinding {
  const record = asObject(value);
  if (!record) {
    throw new JsonRpcTransportError('Process result diagnostics must be objects.', {
      code: -32600,
      errorClass: 'protocol-error',
      processId: request.processId,
      operationId: request.operationId,
      taskId: request.id,
      rawMessage: value,
    });
  }

  if (
    typeof record.id !== 'string'
    || (record.severity !== 'error' && record.severity !== 'warning' && record.severity !== 'info')
    || typeof record.message !== 'string'
  ) {
    throw new JsonRpcTransportError('Process result diagnostics are invalid.', {
      code: -32600,
      errorClass: 'protocol-error',
      processId: request.processId,
      operationId: request.operationId,
      taskId: request.id,
      rawMessage: value,
    });
  }

  return Object.freeze({
    id: record.id,
    severity: record.severity,
    message: record.message,
    ...(typeof record.route === 'string' ? { route: record.route as CapabilityFinding['route'] } : {}),
    ...(typeof record.reason === 'string' ? { reason: record.reason as CapabilityFinding['reason'] } : {}),
    ...(typeof record.extensionId === 'string' ? { extensionId: record.extensionId } : {}),
    ...(typeof record.contributionId === 'string' ? { contributionId: record.contributionId } : {}),
    ...(typeof record.clipId === 'string' ? { clipId: record.clipId } : {}),
    ...(typeof record.materialRefId === 'string' ? { materialRefId: record.materialRefId } : {}),
    ...(asObject(record.detail) ? { detail: Object.freeze({ ...record.detail }) } : {}),
  });
}

function extractCorrelation(
  rawMessage: unknown,
): JsonRpcTransportCorrelation | undefined {
  const record = asObject(rawMessage);
  if (!record) return undefined;

  const nested = (
    ('result' in record && asObject(record.result))
    || ('params' in record && asObject(record.params))
    || ('error' in record && asObject(record.error) && asObject(record.error.data))
    || record
  );
  if (!nested) return undefined;

  const processId = readOptionalString(nested.processId);
  const operationId = readOptionalString(nested.operationId);
  const taskId = readOptionalString(nested.taskId);
  if (!processId) return undefined;
  return {
    processId,
    ...(operationId ? { operationId } : {}),
    ...(taskId ? { taskId } : {}),
  };
}

function classifyLateMessage(rawMessage: unknown): 'late-result' | 'late-progress' | 'late-log' | 'late-cancel' | undefined {
  const record = asObject(rawMessage);
  if (!record) return undefined;
  if ('result' in record || 'error' in record) return 'late-result';
  if (record.method === 'progress') return 'late-progress';
  if (record.method === 'log') return 'late-log';
  if (record.method === 'cancel') return 'late-cancel';
  return undefined;
}

function normalizeExecuteResult(
  payload: unknown,
  request: ProcessRoundtripRequest,
  progress: ProcessProgressEvent | undefined,
  logs: readonly ProcessLogSummary[],
): ProcessRoundtripResult {
  const record = asObject(payload);
  if (!record) {
    throw new JsonRpcTransportError('Process execute response must be an object.', {
      code: -32600,
      errorClass: 'protocol-error',
      processId: request.processId,
      operationId: request.operationId,
      taskId: request.id,
      rawMessage: payload,
    });
  }

  if (record.processId !== request.processId) {
    throw new JsonRpcTransportError('Process execute response processId mismatch.', {
      code: -32600,
      errorClass: 'protocol-error',
      processId: request.processId,
      operationId: request.operationId,
      taskId: request.id,
      rawMessage: payload,
    });
  }

  if (record.operationId !== request.operationId) {
    throw new JsonRpcTransportError('Process execute response operationId mismatch.', {
      code: -32600,
      errorClass: 'protocol-error',
      processId: request.processId,
      operationId: request.operationId,
      taskId: request.id,
      rawMessage: payload,
    });
  }

  const requestId = readOptionalString(record.requestId) ?? readOptionalString(record.taskId);
  if (requestId !== request.id) {
    throw new JsonRpcTransportError('Process execute response requestId mismatch.', {
      code: -32600,
      errorClass: 'protocol-error',
      processId: request.processId,
      operationId: request.operationId,
      taskId: request.id,
      rawMessage: payload,
    });
  }

  if (
    record.status !== 'completed'
    && record.status !== 'failed'
    && record.status !== 'cancelled'
  ) {
    throw new JsonRpcTransportError('Process execute response status is invalid.', {
      code: -32600,
      errorClass: 'protocol-error',
      processId: request.processId,
      operationId: request.operationId,
      taskId: request.id,
      rawMessage: payload,
    });
  }

  if (!Array.isArray(record.returnedMaterials)) {
    throw new JsonRpcTransportError('Process execute response returnedMaterials must be an array.', {
      code: -32600,
      errorClass: 'protocol-error',
      processId: request.processId,
      operationId: request.operationId,
      taskId: request.id,
      rawMessage: payload,
    });
  }

  const diagnostics = Array.isArray(record.diagnostics)
    ? Object.freeze(record.diagnostics.map((item) => normalizeCapabilityFinding(item, request)))
    : undefined;

  const normalizedLogs = Array.isArray(record.logs)
    ? freezeLogs(record.logs.filter((item): item is ProcessLogSummary => {
      const candidate = asObject(item);
      return Boolean(candidate && isLogLevel(candidate.level) && typeof candidate.message === 'string');
    }).map((item) => ({
      level: item.level === 'warn' ? 'warning' : item.level,
      message: item.message,
      ...(typeof item.at === 'string' ? { at: item.at } : {}),
      ...(asObject(item.detail) ? { detail: item.detail } : {}),
    })))
    : (logs.length > 0 ? freezeLogs(logs) : undefined);

  const progressRecord = asObject(record.progress);
  const normalizedProgress = progressRecord
    ? freezeProgress({
      operationId: request.operationId,
      ...(typeof progressRecord.percent === 'number' && Number.isFinite(progressRecord.percent)
        ? { percent: progressRecord.percent }
        : {}),
      ...(typeof progressRecord.message === 'string' ? { message: progressRecord.message } : {}),
      ...(typeof progressRecord.currentStep === 'string' ? { currentStep: progressRecord.currentStep } : {}),
      ...(typeof progressRecord.totalSteps === 'number' && Number.isFinite(progressRecord.totalSteps)
        ? { totalSteps: progressRecord.totalSteps }
        : {}),
    })
    : progress;

  return Object.freeze({
    requestId: request.id,
    processId: request.processId,
    operationId: request.operationId,
    status: record.status,
    returnedMaterials: Object.freeze([...record.returnedMaterials]) as ProcessRoundtripResult['returnedMaterials'],
    ...(Array.isArray(record.artifacts) ? { artifacts: Object.freeze([...record.artifacts]) as ProcessRoundtripResult['artifacts'] } : {}),
    ...(Array.isArray(record.sidecars) ? { sidecars: Object.freeze([...record.sidecars]) as ProcessRoundtripResult['sidecars'] } : {}),
    ...(diagnostics ? { diagnostics } : {}),
    ...(normalizedLogs ? { logs: normalizedLogs } : {}),
    ...(normalizedProgress ? { progress: normalizedProgress } : {}),
    ...(Array.isArray(record.availableActions)
      ? { availableActions: Object.freeze([...record.availableActions]) as ProcessRoundtripResult['availableActions'] }
      : {}),
    ...(asObject(record.metadata) ? { metadata: Object.freeze({ ...record.metadata }) } : {}),
  });
}

export function createProcessManager({
  processes,
  spawnProcess = createDefaultSpawnProcess,
  createTransport = (process, hooks) => createJsonRpcStdioTransport({
    process,
    onNotification: hooks.onNotification,
    onProtocolError: hooks.onProtocolError,
  }),
  now = defaultNow,
  defaultHealthTimeoutMs = 30_000,
  defaultExecuteTimeoutMs = 120_000,
  defaultShutdownTimeoutMs = 30_000,
  onRestartPolicyEvent,
}: CreateProcessManagerOptions): ProcessManager {
  const orderedProcesses = Object.freeze([...processes]);
  const records = new Map<string, ProcessRecord>();

  for (const spec of orderedProcesses) {
    protocolGuard(spec);
    if (records.has(spec.id)) {
      throw new Error(`Duplicate process declaration "${spec.id}".`);
    }

    records.set(spec.id, {
      spec,
      status: createStoppedStatus(spec, now),
      diagnostics: [],
      expectedExit: false,
      completedOperations: [],
    });
  }

  const getRecord = (processId: string): ProcessRecord => {
    const record = records.get(processId);
    if (!record) {
      throw new ProcessManagerError(`Process "${processId}" is not declared in the trusted registry.`, {
        code: 'process-undeclared',
        processId,
      });
    }
    return record;
  };

  const setStatus = (
    record: ProcessRecord,
    state: ProcessState,
    details: Record<string, unknown> = {},
  ): ProcessStatus => {
    record.status = createStatus(record.spec, state, now, {
      ...details,
      ...(record.diagnostics.length > 0 ? { diagnostics: freezeDiagnostics(record.diagnostics) } : {}),
    });
    return record.status;
  };

  const refreshStatus = (
    record: ProcessRecord,
    patch: Record<string, unknown> = {},
  ): ProcessStatus => {
    const { processId: _processId, label: _label, state, updatedAt: _updatedAt, ...details } = record.status;
    return setStatus(record, state, {
      ...details,
      ...patch,
    });
  };

  const addDiagnostic = (
    record: ProcessRecord,
    diagnostic: ExtensionDiagnostic,
  ): ExtensionDiagnostic => {
    const frozen = Object.freeze({
      ...diagnostic,
      ...(diagnostic.detail ? { detail: Object.freeze({ ...diagnostic.detail }) } : {}),
    });
    record.diagnostics.push(frozen);
    refreshStatus(record);
    return frozen;
  };

  const rememberCompletedOperation = (
    record: ProcessRecord,
    correlation: JsonRpcTransportCorrelation,
    status: ProcessRoundtripResult['status'],
  ) => {
    record.completedOperations.push(Object.freeze({
      key: operationKey(correlation),
      correlation: Object.freeze({ ...correlation }),
      finishedAt: now(),
      status,
    }));
    if (record.completedOperations.length > 8) {
      record.completedOperations.splice(0, record.completedOperations.length - 8);
    }
  };

  const findCompletedOperation = (
    record: ProcessRecord,
    correlation: JsonRpcTransportCorrelation | undefined,
  ): CompletedOperationRecord | undefined => {
    if (!correlation) return undefined;
    const key = operationKey(correlation);
    return record.completedOperations.find((entry) => entry.key === key);
  };

  const emitRestartHook = (
    record: ProcessRecord,
    reason: ProcessManagerRestartPolicyEvent['reason'],
    recoverable: boolean,
    correlation?: JsonRpcTransportCorrelation,
  ) => {
    const restartPolicy = record.spec.restartPolicy;
    if (!restartPolicy) return;
    onRestartPolicyEvent?.({
      processId: record.spec.id,
      restartPolicy,
      reason,
      recoverable,
      ...(correlation?.operationId ? { operationId: correlation.operationId } : {}),
      ...(correlation?.taskId ? { taskId: correlation.taskId } : {}),
    });
  };

  const resolveExitWaiter = (record: ProcessRecord) => {
    record.resolveExit?.();
    record.resolveExit = undefined;
    record.exitPromise = undefined;
  };

  const clearRuntime = (record: ProcessRecord) => {
    record.transport?.dispose();
    record.transport = undefined;
    record.process = undefined;
    record.startedAt = undefined;
    record.startupPromise = undefined;
  };

  const ensureExitPromise = (record: ProcessRecord): Promise<void> => {
    if (!record.exitPromise) {
      record.exitPromise = new Promise<void>((resolve) => {
        record.resolveExit = resolve;
      });
    }
    return record.exitPromise;
  };

  const handleProtocolError = (record: ProcessRecord, error: JsonRpcTransportError) => {
    const correlation = extractCorrelation(error.rawMessage);
    const lateKind = classifyLateMessage(error.rawMessage);
    if (lateKind && findCompletedOperation(record, correlation)) {
      addDiagnostic(record, {
        severity: 'warning',
        code: `process/${lateKind}`,
        message: `${record.spec.label} produced a ${lateKind.replace('-', ' ')} after the operation was terminal.`,
        detail: {
          processId: record.spec.id,
          operationId: correlation?.operationId,
          taskId: correlation?.taskId,
          recoverable: true,
        },
      });
      return;
    }

    addDiagnostic(record, {
      severity: 'warning',
      code: 'process/protocol-error',
      message: error.message,
      detail: {
        processId: record.spec.id,
        operationId: correlation?.operationId,
        taskId: correlation?.taskId,
        errorClass: error.errorClass,
        recoverable: true,
      },
    });
  };

  const handleProcessFailure = (
    record: ProcessRecord,
    error: unknown,
    context: 'start' | 'health' | 'execute' | 'shutdown' | 'process',
    correlation?: JsonRpcTransportCorrelation,
  ) => {
    if (looksLikeErrno(error) && error.code === 'ENOENT') {
      addDiagnostic(record, {
        severity: 'warning',
        code: 'process/not-installed',
        message: `${record.spec.label} is not installed.`,
        detail: {
          processId: record.spec.id,
          recoverable: true,
        },
      });
      setStatus(record, 'not-installed', {
        installHint: installHint(record.spec),
        message: `${record.spec.label} is not installed.`,
      });
      clearRuntime(record);
      resolveExitWaiter(record);
      return;
    }

    if (error instanceof JsonRpcTransportError && error.errorClass === 'timeout') {
      const message = context === 'health'
        ? `Health check for ${record.spec.label} timed out.`
        : context === 'shutdown'
          ? `Shutdown for ${record.spec.label} timed out.`
          : `${record.spec.label} ${context} timed out.`;
      addDiagnostic(record, {
        severity: 'warning',
        code: context === 'shutdown' ? 'process/shutdown-timeout' : 'process/timeout',
        message,
        detail: {
          processId: record.spec.id,
          operationId: correlation?.operationId,
          taskId: correlation?.taskId,
          timeoutMs: error.timeoutMs,
          recoverable: true,
        },
      });
      setStatus(record, 'degraded', {
        healthCheck: record.spec.healthCheck ?? 'health',
        message,
      });
      emitRestartHook(
        record,
        context === 'shutdown' ? 'shutdown-timeout' : 'execute-timeout',
        true,
        correlation,
      );
      return;
    }

    if (error instanceof JsonRpcTransportError && error.errorClass === 'protocol-error') {
      handleProtocolError(record, error);
    } else if (error instanceof Error) {
      addDiagnostic(record, {
        severity: 'warning',
        code: 'process/runtime-error',
        message: error.message,
        detail: {
          processId: record.spec.id,
          operationId: correlation?.operationId,
          taskId: correlation?.taskId,
          recoverable: true,
        },
      });
    }

    setStatus(record, 'failed', {
      errorCode:
        error instanceof JsonRpcTransportError ? error.errorClass : 'process-error',
      recoverable: true,
      message:
        error instanceof Error && error.message.length > 0
          ? error.message
          : `${record.spec.label} failed.`,
    });
  };

  const handleNotification = (record: ProcessRecord, notification: JsonRpcTransportNotification) => {
    const correlation = notification.params;
    const activeOperation = record.activeOperation;
    const completedOperation = findCompletedOperation(record, correlation);

    if (completedOperation) {
      addDiagnostic(record, {
        severity: 'warning',
        code: `process/late-${notification.kind}`,
        message: `${record.spec.label} emitted ${notification.kind} after operation completion.`,
        detail: {
          processId: record.spec.id,
          operationId: correlation.operationId,
          taskId: correlation.taskId,
          recoverable: true,
        },
      });
      return;
    }

    if (!activeOperation || activeOperation.key !== operationKey(correlation)) {
      addDiagnostic(record, {
        severity: 'warning',
        code: 'process/correlation-mismatch',
        message: `${record.spec.label} emitted a notification for an unknown task/process/operation correlation.`,
        detail: {
          processId: record.spec.id,
          operationId: correlation.operationId,
          taskId: correlation.taskId,
          kind: notification.kind,
          recoverable: true,
        },
      });
      return;
    }

    switch (notification.kind) {
      case 'progress': {
        activeOperation.progress = normalizeProgressEvent(notification);
        setStatus(record, 'busy', {
          operationId: activeOperation.request.operationId,
          progress: activeOperation.progress,
        });
        return;
      }
      case 'log': {
        activeOperation.logs = [...activeOperation.logs, normalizeLogSummary(notification)];
        return;
      }
      case 'cancel': {
        activeOperation.cancelRequested = true;
      }
    }
  };

  const attachProcessLifecycle = (record: ProcessRecord, processHandle: JsonRpcProcessLike) => {
    processHandle.on('exit', (code, signal) => {
      const expectedExit = record.expectedExit;
      clearRuntime(record);
      resolveExitWaiter(record);
      if (expectedExit) {
        record.expectedExit = false;
        setStatus(record, 'stopped', {
          message: `${record.spec.label} stopped gracefully.`,
        });
        return;
      }

      emitRestartHook(
        record,
        'process-exited',
        code !== 0,
        record.activeOperation?.correlation,
      );
      setStatus(record, 'failed', {
        errorCode: 'process-exited',
        recoverable: code !== 0,
        message: signal
          ? `${record.spec.label} exited unexpectedly (${signal}).`
          : `${record.spec.label} exited unexpectedly.`,
      });
    });

    processHandle.on('error', (error) => {
      emitRestartHook(record, 'process-error', true, record.activeOperation?.correlation);
      handleProcessFailure(record, error, 'process', record.activeOperation?.correlation);
    });
  };

  const ensureStarted = async (record: ProcessRecord): Promise<JsonRpcProcessLike> => {
    if (record.process && record.transport) return record.process;
    if (record.startupPromise) return record.startupPromise;

    record.startupPromise = Promise.resolve().then(() => {
      setStatus(record, 'starting', {
        startedAt: now(),
      });

      const processHandle = spawnProcess(record.spec);
      record.process = processHandle;
      record.transport = createTransport(processHandle, {
        onNotification: (notification) => handleNotification(record, notification),
        onProtocolError: (error) => handleProtocolError(record, error),
      });
      record.startedAt = record.status.state === 'starting' ? record.status.startedAt : now();
      attachProcessLifecycle(record, processHandle);
      return processHandle;
    }).catch((error) => {
      handleProcessFailure(record, error, 'start');
      throw error;
    }).finally(() => {
      record.startupPromise = undefined;
    });

    return record.startupPromise;
  };

  const validateHealthPayload = (
    record: ProcessRecord,
    payload: unknown,
  ): ProcessHealthPayload => {
    const objectPayload = asObject(payload);
    if (!objectPayload) {
      throw new JsonRpcTransportError('Process health response must be an object.', {
        code: -32600,
        errorClass: 'protocol-error',
        processId: record.spec.id,
      });
    }

    if (objectPayload.processId !== record.spec.id) {
      throw new JsonRpcTransportError('Process health response processId mismatch.', {
        code: -32600,
        errorClass: 'protocol-error',
        processId: record.spec.id,
        rawMessage: payload,
      });
    }

    if (!isProcessState(objectPayload.state)) {
      throw new JsonRpcTransportError('Process health response state is invalid.', {
        code: -32600,
        errorClass: 'protocol-error',
        processId: record.spec.id,
        rawMessage: payload,
      });
    }

    return objectPayload as ProcessHealthPayload;
  };

  const projectHealthStatus = (
    record: ProcessRecord,
    payload: ProcessHealthPayload,
  ): ProcessStatus => {
    const pid = record.process?.pid;
    const details = {
      ...payload,
      ...(payload.state === 'starting' ? { startedAt: record.startedAt } : {}),
      ...(payload.state === 'ready' ? { pid, version: payload.version ?? record.spec.version } : {}),
      ...(payload.state === 'busy' ? { operationId: payload.operationId, progress: payload.progress } : {}),
      ...(payload.state === 'degraded' ? { healthCheck: record.spec.healthCheck ?? 'health' } : {}),
      ...(payload.state === 'failed'
        ? {
          errorCode:
              typeof payload.errorCode === 'string' ? payload.errorCode : 'health-check-failed',
          recoverable:
              typeof payload.recoverable === 'boolean' ? payload.recoverable : true,
        }
        : {}),
    };
    return setStatus(record, payload.state, details);
  };

  const checkHealth = async (
    processId: string,
    options: ProcessManagerHealthOptions = {},
  ): Promise<ProcessStatus> => {
    const record = getRecord(processId);
    try {
      await ensureStarted(record);
      const transport = record.transport;
      if (!transport) {
        return record.status;
      }

      const payload = await transport.request<unknown>({
        method: record.spec.healthCheck ?? 'health',
        params: { processId: record.spec.id },
        correlation: { processId: record.spec.id },
        timeoutMs: options.timeoutMs ?? defaultHealthTimeoutMs,
      });
      return projectHealthStatus(record, validateHealthPayload(record, payload));
    } catch (error) {
      handleProcessFailure(record, error, 'health');
      return record.status;
    }
  };

  const readyStatus = (record: ProcessRecord): ProcessStatus => setStatus(record, 'ready', {
    pid: record.process?.pid,
    version: record.spec.version,
  });

  const validateOperation = (record: ProcessRecord, request: ProcessRoundtripRequest) => {
    const declaredOperation = record.spec.operations?.find((operation) => operation.id === request.operationId);
    if (!declaredOperation) {
      throw new ProcessManagerError(
        `Process "${request.processId}" does not declare operation "${request.operationId}".`,
        {
          code: 'operation-undeclared',
          processId: request.processId,
          operationId: request.operationId,
          taskId: request.id,
        },
      );
    }

    if (record.activeOperation) {
      throw new ProcessManagerError(
        `Process "${request.processId}" is already executing "${record.activeOperation.request.operationId}".`,
        {
          code: 'operation-active',
          processId: request.processId,
          operationId: record.activeOperation.request.operationId,
          taskId: record.activeOperation.request.id,
        },
      );
    }
  };

  return {
    getDeclaredProcesses(): readonly ProcessSpec[] {
      return orderedProcesses;
    },

    getProcessSpec(processId: string): ProcessSpec | undefined {
      return records.get(processId)?.spec;
    },

    getStatus(processId: string): ProcessStatus | undefined {
      return records.get(processId)?.status;
    },

    listStatuses(): readonly ProcessStatus[] {
      return orderedProcesses
        .map((spec) => records.get(spec.id)?.status)
        .filter((status): status is ProcessStatus => Boolean(status));
    },

    async start(processId: string, options: ProcessManagerStartOptions = {}): Promise<ProcessStatus> {
      return checkHealth(processId, { timeoutMs: options.timeoutMs });
    },

    checkHealth,

    async execute(
      request: ProcessRoundtripRequest,
      options: ProcessManagerExecuteOptions = {},
    ): Promise<ProcessRoundtripResult> {
      const record = getRecord(request.processId);
      validateOperation(record, request);

      await ensureStarted(record);
      const transport = record.transport;
      if (!transport) {
        throw new JsonRpcTransportError('Process transport is unavailable.', {
          code: -32001,
          errorClass: 'process-exited',
          processId: request.processId,
          operationId: request.operationId,
          taskId: request.id,
        });
      }

      const correlation: JsonRpcTransportCorrelation = {
        processId: request.processId,
        operationId: request.operationId,
        taskId: request.id,
      };
      const activeOperation: ActiveOperationRecord = {
        correlation,
        key: operationKey(correlation),
        request,
        logs: [],
        cancelRequested: false,
      };
      record.activeOperation = activeOperation;
      setStatus(record, 'busy', {
        operationId: request.operationId,
      });

      try {
        const payload = await transport.request<unknown>({
          method: 'execute',
          params: {
            ...request,
            requestId: request.id,
            taskId: request.id,
          },
          correlation,
          timeoutMs: options.timeoutMs ?? defaultExecuteTimeoutMs,
        });
        const result = normalizeExecuteResult(
          payload,
          request,
          activeOperation.progress,
          activeOperation.logs,
        );
        record.activeOperation = undefined;
        rememberCompletedOperation(record, correlation, result.status);
        readyStatus(record);
        return result;
      } catch (error) {
        record.activeOperation = undefined;
        const interruptedByShutdown = error instanceof JsonRpcTransportError
          && error.errorClass === 'process-exited'
          && (record.status.state === 'stopping' || record.status.state === 'stopped');
        rememberCompletedOperation(record, correlation, interruptedByShutdown ? 'cancelled' : 'failed');
        if (interruptedByShutdown) {
          throw error;
        }
        if (error instanceof JsonRpcTransportError && error.errorClass === 'timeout') {
          activeOperation.cancelRequested = true;
          emitRestartHook(record, 'execute-timeout', true, correlation);
          try {
            await transport.notify({
              method: 'cancel',
              params: {
                processId: request.processId,
                operationId: request.operationId,
                taskId: request.id,
                reason: 'execute-timeout',
              },
            });
          } catch {
            // Best-effort cancellation only; timeout is already terminal locally.
          }
        }
        handleProcessFailure(record, error, 'execute', correlation);
        throw error;
      }
    },

    async cancel(processId: string, options: ProcessManagerCancelOptions): Promise<ProcessStatus> {
      const record = getRecord(processId);
      const activeOperation = record.activeOperation;
      if (!activeOperation) {
        addDiagnostic(record, {
          severity: 'warning',
          code: 'process/cancel-missing-operation',
          message: `${record.spec.label} has no active operation to cancel.`,
          detail: {
            processId: record.spec.id,
            operationId: options.operationId,
            taskId: options.taskId,
            recoverable: true,
          },
        });
        return record.status;
      }

      if (
        activeOperation.request.operationId !== options.operationId
        || activeOperation.request.id !== options.taskId
      ) {
        addDiagnostic(record, {
          severity: 'warning',
          code: 'process/correlation-mismatch',
          message: `${record.spec.label} rejected a cancel request with mismatched task/process/operation correlation.`,
          detail: {
            processId: record.spec.id,
            operationId: options.operationId,
            taskId: options.taskId,
            recoverable: true,
          },
        });
        return record.status;
      }

      if (!record.transport) return record.status;
      if (activeOperation.cancelPromise) return activeOperation.cancelPromise;

      activeOperation.cancelRequested = true;
      activeOperation.cancelPromise = Promise.resolve().then(async () => {
        await record.transport?.notify({
          method: 'cancel',
          params: {
            processId: record.spec.id,
            operationId: options.operationId,
            taskId: options.taskId,
            ...(options.reason ? { reason: options.reason } : {}),
          },
        } satisfies JsonRpcTransportNotificationOptions);
        return record.status;
      }).catch((error) => {
        handleProcessFailure(record, error, 'execute', activeOperation.correlation);
        return record.status;
      }).finally(() => {
        activeOperation.cancelPromise = undefined;
      });

      return activeOperation.cancelPromise;
    },

    async shutdown(
      processId: string,
      options: ProcessManagerShutdownOptions = {},
    ): Promise<ProcessStatus> {
      const record = getRecord(processId);
      if (!record.process || !record.transport) {
        return record.status;
      }
      if (record.shutdownPromise) return record.shutdownPromise;

      record.expectedExit = true;
      const exitPromise = ensureExitPromise(record);
      const activeCorrelation = record.activeOperation?.correlation;
      setStatus(record, 'stopping', {
        reason: options.reason,
      });

      record.shutdownPromise = Promise.resolve().then(async () => {
        try {
          await record.transport?.request({
            method: record.spec.shutdown ?? 'shutdown',
            params: {
              processId: record.spec.id,
              reason: options.reason,
              ...(activeCorrelation?.operationId ? { operationId: activeCorrelation.operationId } : {}),
              ...(activeCorrelation?.taskId ? { taskId: activeCorrelation.taskId } : {}),
            },
            correlation: activeCorrelation ?? { processId: record.spec.id },
            timeoutMs: options.timeoutMs ?? defaultShutdownTimeoutMs,
          });
        } catch (error) {
          record.expectedExit = false;
          handleProcessFailure(record, error, 'shutdown', activeCorrelation);
          return record.status;
        }

        await exitPromise;
        if (record.activeOperation && activeCorrelation) {
          rememberCompletedOperation(record, activeCorrelation, 'cancelled');
          record.activeOperation = undefined;
        }
        return record.status;
      }).finally(() => {
        record.shutdownPromise = undefined;
      });

      return record.shutdownPromise;
    },

    async dispose(): Promise<void> {
      await Promise.all(
        [...orderedProcesses].map(async (spec) => {
          const record = records.get(spec.id);
          if (!record) return;
          try {
            if (record.process || record.transport) {
              await this.shutdown(spec.id, { reason: 'manager-dispose' });
            }
          } catch {
            // Best effort only during disposal.
          } finally {
            clearRuntime(record);
          }
        }),
      );
    },
  };
}
