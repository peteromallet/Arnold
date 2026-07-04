import readline from 'node:readline';

type JsonRpcId = number | string;

type ProcessLifecycleState =
  | 'not-installed'
  | 'stopped'
  | 'starting'
  | 'ready'
  | 'busy'
  | 'degraded'
  | 'failed'
  | 'stopping';

type FixtureErrorClass =
  | 'protocol-error'
  | 'timeout'
  | 'process-exited'
  | 'invalid-request';

type ExecuteResultStatus = 'completed' | 'failed' | 'cancelled';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface JsonRpcErrorObject {
  readonly code: number;
  readonly message: string;
  readonly data?: Record<string, unknown>;
}

interface JsonRpcRequest {
  readonly jsonrpc: '2.0';
  readonly id?: JsonRpcId;
  readonly method: string;
  readonly params?: unknown;
}

interface HealthResponseConfig {
  readonly state: ProcessLifecycleState;
  readonly message?: string;
  readonly versionSemver?: string;
  readonly uptimeMs?: number;
  readonly errorCode?: string;
  readonly recoverable?: boolean;
  readonly progress?: Record<string, unknown>;
  readonly operationId?: string;
  readonly reason?: string;
}

interface FixtureProgressEvent {
  readonly percent?: number;
  readonly message?: string;
  readonly currentStep?: string;
  readonly totalSteps?: number;
}

interface FixtureLogEvent {
  readonly level: LogLevel;
  readonly message: string;
  readonly timestamp?: string;
}

interface LateResultConfig {
  readonly delayMs?: number;
  readonly status?: ExecuteResultStatus;
}

interface ExecuteScenario {
  readonly progressEvents?: readonly FixtureProgressEvent[];
  readonly logEvents?: readonly FixtureLogEvent[];
  readonly resultStatus?: ExecuteResultStatus;
  readonly resultDelayMs?: number;
  readonly waitForCancel?: boolean;
  readonly hang?: boolean;
  readonly errorClass?: Exclude<FixtureErrorClass, 'process-exited'>;
  readonly errorCode?: number;
  readonly errorMessage?: string;
  readonly errorDetail?: string;
  readonly timeoutMs?: number;
  readonly exitDuring?: 'execute' | 'shutdown';
  readonly exitCode?: number;
  readonly lateNotifications?: readonly Array<'progress' | 'log' | 'cancel'>;
  readonly lateResult?: LateResultConfig | boolean;
  readonly emitCancelNotificationOnCancel?: boolean;
  readonly cancelOutcome?: 'result' | 'error';
  readonly returnedMaterials?: readonly unknown[];
  readonly artifacts?: readonly unknown[];
  readonly sidecars?: readonly unknown[];
  readonly diagnostics?: readonly unknown[];
  readonly availableActions?: readonly unknown[];
  readonly metadata?: Record<string, unknown>;
}

interface ActiveExecution {
  readonly requestId: JsonRpcId;
  readonly taskId: string;
  readonly operationId: string;
  readonly scenario: ExecuteScenario;
  readonly lateResult: LateResultConfig | null;
  readonly resolvedNotifications: {
    readonly progressEvents: readonly FixtureProgressEvent[];
    readonly logEvents: readonly FixtureLogEvent[];
  };
  completed: boolean;
}

const DEFAULT_MAX_DELAY_MS = 1_000;
const DEFAULT_VERSION = '1.0.0';
const DEFAULT_PROCESS_ID = 'video-editor.process-fixture';
const DEFAULT_OPERATION_ID = 'fixture.execute';
const MISSING_BINARY_COMMAND = '__reigh_process_fixture_missing_binary__';

const processId = readEnvString('REIGH_PROCESS_FIXTURE_PROCESS_ID') ?? DEFAULT_PROCESS_ID;
const operationIds = readEnvStringArray('REIGH_PROCESS_FIXTURE_OPERATION_IDS') ?? [DEFAULT_OPERATION_ID];
const versionSemver = readEnvString('REIGH_PROCESS_FIXTURE_VERSION_SEMVER') ?? DEFAULT_VERSION;
const healthSequence = readHealthSequence(
  readEnvString('REIGH_PROCESS_FIXTURE_HEALTH_SEQUENCE'),
  versionSemver,
);

let healthIndex = 0;
let lastState: ProcessLifecycleState = healthSequence[0]?.state ?? 'starting';
let activeExecution: ActiveExecution | undefined;
let shutdownRequested = false;

const rl = readline.createInterface({
  input: process.stdin,
  crlfDelay: Infinity,
});

rl.on('line', (line) => {
  void handleLine(line);
});

rl.on('close', () => {
  process.exit(0);
});

async function handleLine(line: string): Promise<void> {
  if (line.trim().length === 0) {
    await writeError(null, -32600, 'Invalid Request', 'protocol-error', 'Received empty JSON-RPC line.');
    return;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(line);
  } catch {
    await writeError(null, -32700, 'Parse error', 'protocol-error', 'Malformed JSON line.');
    return;
  }

  if (!isRecord(parsed)) {
    await writeError(null, -32600, 'Invalid Request', 'protocol-error', 'JSON-RPC payload must be an object.');
    return;
  }

  if (parsed.jsonrpc !== '2.0') {
    await writeError(asJsonRpcIdOrNull(parsed.id), -32600, 'Invalid Request', 'protocol-error', 'Missing jsonrpc="2.0".');
    return;
  }

  if (typeof parsed.method !== 'string') {
    await writeError(asJsonRpcIdOrNull(parsed.id), -32600, 'Invalid Request', 'protocol-error', 'JSON-RPC method must be a string.');
    return;
  }

  const request: JsonRpcRequest = {
    jsonrpc: '2.0',
    ...(isJsonRpcId(parsed.id) ? { id: parsed.id } : {}),
    method: parsed.method,
    ...(parsed.params !== undefined ? { params: parsed.params } : {}),
  };

  switch (request.method) {
    case 'health':
      await handleHealth(request);
      return;
    case 'execute':
      await handleExecute(request);
      return;
    case 'cancel':
      await handleCancel(request);
      return;
    case 'shutdown':
      await handleShutdown(request);
      return;
    default:
      await writeError(
        request.id ?? null,
        -32601,
        'Method not found',
        'protocol-error',
        `Unknown method "${request.method}".`,
      );
  }
}

async function handleHealth(request: JsonRpcRequest): Promise<void> {
  const params = expectObject(request.params, request.id ?? null, 'health params');
  if (!params) return;
  if (!expectProcessId(params.processId, request.id ?? null)) return;

  const response = nextHealthResponse();
  lastState = response.state;

  await writeResult(request.id ?? null, {
    processId,
    state: response.state,
    ...(response.message ? { message: response.message } : {}),
    ...(response.versionSemver ? { version: { semver: response.versionSemver } } : {}),
    ...(typeof response.uptimeMs === 'number' ? { uptimeMs: response.uptimeMs } : {}),
    ...(response.errorCode ? { errorCode: response.errorCode } : {}),
    ...(typeof response.recoverable === 'boolean' ? { recoverable: response.recoverable } : {}),
    ...(response.progress ? { progress: response.progress } : {}),
    ...(response.operationId ? { operationId: response.operationId } : {}),
    ...(response.reason ? { reason: response.reason } : {}),
  });
}

async function handleExecute(request: JsonRpcRequest): Promise<void> {
  const params = expectObject(request.params, request.id ?? null, 'execute params');
  if (!params) return;

  if (!expectProcessId(params.processId, request.id ?? null)) return;

  const operationId = readRequiredString(
    params.operationId,
    request.id ?? null,
    'execute params.operationId',
  );
  if (!operationId) return;
  const declaredTaskId = typeof params.taskId === 'string'
    ? params.taskId
    : typeof params.requestId === 'string'
      ? params.requestId
      : undefined;
  if (!operationIds.includes(operationId)) {
    await writeError(
      request.id ?? null,
      -32602,
      'Invalid params',
      'invalid-request',
      `Unknown operationId: "${operationId}".`,
      {
        operationId,
        ...(declaredTaskId ? { taskId: declaredTaskId } : {}),
      },
    );
    return;
  }

  const taskId = readExecuteTaskId(params, request.id ?? null);
  if (!taskId) return;

  if (!isExecutableState(lastState)) {
    await writeError(
      request.id ?? null,
      -32602,
      'Invalid params',
      'invalid-request',
      `Process is in "${lastState}" state and cannot execute.`,
      { operationId, taskId },
    );
    return;
  }

  const scenario = readExecuteScenario(params);

  if (scenario.errorClass) {
    await writeScenarioError(request.id ?? null, operationId, taskId, scenario);
    return;
  }

  if (scenario.exitDuring === 'execute') {
    process.exitCode = clampExitCode(scenario.exitCode);
    process.exit(process.exitCode);
  }

  const resolvedProgressEvents = resolveProgressEvents(scenario.progressEvents);
  const resolvedLogEvents = resolveLogEvents(scenario.logEvents);
  const lateResult = normalizeLateResult(scenario.lateResult, scenario.resultStatus);

  activeExecution = {
    requestId: request.id ?? taskId,
    taskId,
    operationId,
    scenario,
    lateResult,
    resolvedNotifications: {
      progressEvents: resolvedProgressEvents,
      logEvents: resolvedLogEvents,
    },
    completed: false,
  };
  lastState = 'busy';

  await emitNotificationSet(operationId, taskId, resolvedProgressEvents, resolvedLogEvents);

  if (scenario.hang || scenario.waitForCancel) {
    return;
  }

  await finalizeExecution(activeExecution, false);
}

async function handleCancel(request: JsonRpcRequest): Promise<void> {
  const params = expectObject(request.params, request.id ?? null, 'cancel params');
  if (!params) return;

  if (!expectProcessId(params.processId, request.id ?? null)) return;
  const operationId = readRequiredString(
    params.operationId,
    request.id ?? null,
    'cancel params.operationId',
  );
  if (!operationId) return;
  const taskId = readRequiredString(params.taskId, request.id ?? null, 'cancel params.taskId');
  if (!taskId) return;

  if (!activeExecution || activeExecution.taskId !== taskId || activeExecution.operationId !== operationId) {
    if (request.id !== undefined) {
      await writeError(
        request.id,
        -32602,
        'Invalid params',
        'invalid-request',
        `Cancel target not found for operation "${operationId}" and task "${taskId}".`,
        { operationId, taskId },
      );
    }
    return;
  }

  if (activeExecution.scenario.emitCancelNotificationOnCancel) {
    await writeNotification('cancel', {
      processId,
      operationId,
      taskId,
    });
  }

  if (request.id !== undefined) {
    await writeResult(request.id, {
      acknowledged: true,
      processId,
      operationId,
      taskId,
      cancelled: true,
    });
  }

  if (activeExecution.completed) return;

  if (activeExecution.scenario.cancelOutcome === 'error') {
    const execution = activeExecution;
    execution.completed = true;
    await delay(execution.lateResult?.delayMs ?? 0);
    await writeError(
      execution.requestId,
      -32800,
      'Operation cancelled',
      'protocol-error',
      'Cancelled by host.',
      {
        operationId: execution.operationId,
        taskId: execution.taskId,
      },
    );
    await emitLateNotifications(execution);
    lastState = 'ready';
    activeExecution = undefined;
    return;
  }

  await finalizeExecution(activeExecution, true);
}

async function handleShutdown(request: JsonRpcRequest): Promise<void> {
  const params = expectObject(request.params, request.id ?? null, 'shutdown params');
  if (!params) return;

  if (!expectProcessId(params.processId, request.id ?? null)) return;

  shutdownRequested = true;
  lastState = 'stopping';

  if (request.id !== undefined) {
    await writeResult(request.id, {
      acknowledged: true,
      processId,
      ...(typeof params.reason === 'string' ? { reason: params.reason } : {}),
      ...(typeof params.operationId === 'string' ? { operationId: params.operationId } : {}),
      ...(typeof params.taskId === 'string' ? { taskId: params.taskId } : {}),
    });
  }

  const exitCode = activeExecution?.scenario.exitDuring === 'shutdown'
    ? clampExitCode(activeExecution.scenario.exitCode)
    : 0;
  process.exitCode = exitCode;
  setImmediate(() => process.exit(exitCode));
}

async function finalizeExecution(execution: ActiveExecution, cancelled: boolean): Promise<void> {
  execution.completed = true;
  const scenario = execution.scenario;
  const resultDelayMs = cancelled && execution.lateResult
    ? execution.lateResult.delayMs ?? 0
    : scenario.resultDelayMs ?? 0;
  await delay(resultDelayMs);

  const status = cancelled
    ? execution.lateResult?.status ?? 'cancelled'
    : scenario.resultStatus ?? 'completed';

  await writeResult(execution.requestId, {
    requestId: execution.taskId,
    taskId: execution.taskId,
    processId,
    operationId: execution.operationId,
    status,
    returnedMaterials: Array.isArray(scenario.returnedMaterials)
      ? [...scenario.returnedMaterials]
      : [],
    ...(Array.isArray(scenario.artifacts) ? { artifacts: [...scenario.artifacts] } : {}),
    ...(Array.isArray(scenario.sidecars) ? { sidecars: [...scenario.sidecars] } : {}),
    ...(Array.isArray(scenario.diagnostics) ? { diagnostics: [...scenario.diagnostics] } : {}),
    ...(execution.resolvedNotifications.logEvents.length > 0
      ? {
          logs: execution.resolvedNotifications.logEvents.map((event) => ({
            level: event.level === 'warn' ? 'warn' : event.level,
            message: event.message,
            ...(event.timestamp ? { at: event.timestamp } : {}),
          })),
        }
      : {}),
    ...(execution.resolvedNotifications.progressEvents.length > 0
      ? {
          progress: {
            operationId: execution.operationId,
            ...execution.resolvedNotifications.progressEvents.at(-1),
          },
        }
      : {}),
    ...(Array.isArray(scenario.availableActions) ? { availableActions: [...scenario.availableActions] } : {}),
    ...(scenario.metadata ? { metadata: scenario.metadata } : {}),
  });

  lastState = shutdownRequested ? 'stopping' : 'ready';
  await emitLateNotifications(execution);
  activeExecution = undefined;
}

async function emitLateNotifications(execution: ActiveExecution): Promise<void> {
  const lateNotifications = execution.scenario.lateNotifications ?? [];
  if (lateNotifications.length === 0) return;

  for (const kind of lateNotifications) {
    switch (kind) {
      case 'progress':
        await writeNotification('progress', {
          processId,
          operationId: execution.operationId,
          taskId: execution.taskId,
          progress: {
            percent: 99,
            message: 'late progress from fixture',
          },
        });
        break;
      case 'log':
        await writeNotification('log', {
          processId,
          operationId: execution.operationId,
          taskId: execution.taskId,
          level: 'warn',
          message: 'late log from fixture',
          timestamp: new Date().toISOString(),
        });
        break;
      case 'cancel':
        await writeNotification('cancel', {
          processId,
          operationId: execution.operationId,
          taskId: execution.taskId,
        });
        break;
    }
  }
}

async function emitNotificationSet(
  operationId: string,
  taskId: string,
  progressEvents: readonly FixtureProgressEvent[],
  logEvents: readonly FixtureLogEvent[],
): Promise<void> {
  for (const progress of progressEvents) {
    await writeNotification('progress', {
      processId,
      operationId,
      taskId,
      progress,
    });
  }

  for (const event of logEvents) {
    await writeNotification('log', {
      processId,
      operationId,
      taskId,
      level: event.level,
      message: event.message,
      ...(event.timestamp ? { timestamp: event.timestamp } : {}),
    });
  }
}

function nextHealthResponse(): HealthResponseConfig {
  const fallbackState = activeExecution
    ? 'busy'
    : shutdownRequested
      ? 'stopping'
      : lastState;

  const config = healthSequence[healthIndex] ?? { state: fallbackState };
  if (healthIndex < healthSequence.length) healthIndex += 1;

  if (activeExecution && config.state === 'busy') {
    return {
      ...config,
      operationId: activeExecution.operationId,
      progress: activeExecution.resolvedNotifications.progressEvents.at(-1),
    };
  }

  return config;
}

function readExecuteScenario(params: Record<string, unknown>): ExecuteScenario {
  const candidates = [
    params.fixtureScenario,
    params.fixture,
    isRecord(params.params) ? params.params.fixtureScenario : undefined,
    isRecord(params.params) ? params.params.fixture : undefined,
    isRecord(params.input) ? params.input.fixtureScenario : undefined,
  ];

  for (const candidate of candidates) {
    if (isRecord(candidate)) {
      return candidate as ExecuteScenario;
    }
  }

  return {};
}

function normalizeLateResult(
  lateResult: ExecuteScenario['lateResult'],
  resultStatus: ExecuteResultStatus | undefined,
): LateResultConfig | null {
  if (!lateResult) return null;
  if (lateResult === true) {
    return {
      delayMs: 0,
      status: resultStatus ?? 'cancelled',
    };
  }

  return {
    delayMs: lateResult.delayMs ?? 0,
    status: lateResult.status ?? resultStatus ?? 'cancelled',
  };
}

function resolveProgressEvents(
  configured: readonly FixtureProgressEvent[] | undefined,
): readonly FixtureProgressEvent[] {
  if (!Array.isArray(configured) || configured.length === 0) {
    return [
      {
        percent: 50,
        message: 'fixture executing',
      },
    ];
  }
  return configured.map((event) => ({
    ...(typeof event.percent === 'number' ? { percent: event.percent } : {}),
    ...(typeof event.message === 'string' ? { message: event.message } : {}),
    ...(typeof event.currentStep === 'string' ? { currentStep: event.currentStep } : {}),
    ...(typeof event.totalSteps === 'number' ? { totalSteps: event.totalSteps } : {}),
  }));
}

function resolveLogEvents(configured: readonly FixtureLogEvent[] | undefined): readonly FixtureLogEvent[] {
  if (!Array.isArray(configured) || configured.length === 0) {
    return [
      {
        level: 'info',
        message: 'fixture executing',
      },
    ];
  }

  return configured
    .filter((event): event is FixtureLogEvent => isLogLevel(event.level) && typeof event.message === 'string')
    .map((event) => ({
      level: event.level,
      message: event.message,
      ...(typeof event.timestamp === 'string' ? { timestamp: event.timestamp } : {}),
    }));
}

async function writeScenarioError(
  id: JsonRpcId | null,
  operationId: string,
  taskId: string,
  scenario: ExecuteScenario,
): Promise<void> {
  const errorClass = scenario.errorClass ?? 'protocol-error';
  const defaultCode = errorClass === 'timeout'
    ? -32000
    : errorClass === 'invalid-request'
      ? -32602
      : -32600;
  const defaultMessage = errorClass === 'timeout'
    ? 'Operation timed out'
    : errorClass === 'invalid-request'
      ? 'Invalid params'
      : 'Invalid Request';

  await writeError(
    id,
    typeof scenario.errorCode === 'number' ? scenario.errorCode : defaultCode,
    scenario.errorMessage ?? defaultMessage,
    errorClass,
    scenario.errorDetail ?? `Fixture scenario produced ${errorClass}.`,
    {
      operationId,
      taskId,
      ...(errorClass === 'timeout' && typeof scenario.timeoutMs === 'number'
        ? { timeoutMs: scenario.timeoutMs }
        : {}),
    },
  );
}

async function writeResult(id: JsonRpcId | null, result: Record<string, unknown>): Promise<void> {
  if (id === null) return;
  await writeMessage({
    jsonrpc: '2.0',
    id,
    result,
  });
}

async function writeError(
  id: JsonRpcId | null,
  code: number,
  message: string,
  errorClass: FixtureErrorClass,
  detail: string,
  extraData: Record<string, unknown> = {},
): Promise<void> {
  await writeMessage({
    jsonrpc: '2.0',
    id,
    error: {
      code,
      message,
      data: {
        class: errorClass,
        processId,
        detail,
        ...extraData,
      },
    } satisfies JsonRpcErrorObject,
  });
}

async function writeNotification(method: string, params: Record<string, unknown>): Promise<void> {
  await writeMessage({
    jsonrpc: '2.0',
    method,
    params,
  });
}

async function writeMessage(message: Record<string, unknown>): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    process.stdout.write(`${JSON.stringify(message)}\n`, 'utf8', (error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
}

async function delay(ms: number): Promise<void> {
  const bounded = Math.max(0, Math.min(normalizeFiniteNumber(ms) ?? 0, DEFAULT_MAX_DELAY_MS));
  if (bounded === 0) {
    await Promise.resolve();
    return;
  }

  await new Promise<void>((resolve) => {
    setTimeout(resolve, bounded);
  });
}

function readHealthSequence(raw: string | undefined, fallbackVersion: string): HealthResponseConfig[] {
  const parsed = parseJson(raw);
  if (!Array.isArray(parsed) || parsed.length === 0) {
    return [
      { state: 'starting', message: 'Fixture is starting.' },
      { state: 'ready', message: 'Fixture is ready.', versionSemver: fallbackVersion, uptimeMs: 1 },
    ];
  }

  const sequence = parsed
    .map((entry) => normalizeHealthResponse(entry, fallbackVersion))
    .filter((entry): entry is HealthResponseConfig => entry !== null);

  return sequence.length > 0
    ? sequence
    : [
        { state: 'starting', message: 'Fixture is starting.' },
        { state: 'ready', message: 'Fixture is ready.', versionSemver: fallbackVersion, uptimeMs: 1 },
      ];
}

function normalizeHealthResponse(entry: unknown, fallbackVersion: string): HealthResponseConfig | null {
  if (typeof entry === 'string' && isLifecycleState(entry)) {
    return {
      state: entry,
      ...(entry === 'ready' ? { versionSemver: fallbackVersion, uptimeMs: 1 } : {}),
      ...(entry === 'failed' ? { errorCode: 'fixture-health-failed', recoverable: true } : {}),
    };
  }

  if (!isRecord(entry) || !isLifecycleState(entry.state)) return null;

  return {
    state: entry.state,
    ...(typeof entry.message === 'string' ? { message: entry.message } : {}),
    ...(typeof entry.versionSemver === 'string' ? { versionSemver: entry.versionSemver } : {}),
    ...(typeof entry.uptimeMs === 'number' ? { uptimeMs: entry.uptimeMs } : {}),
    ...(typeof entry.errorCode === 'string' ? { errorCode: entry.errorCode } : {}),
    ...(typeof entry.recoverable === 'boolean' ? { recoverable: entry.recoverable } : {}),
    ...(isRecord(entry.progress) ? { progress: entry.progress } : {}),
    ...(typeof entry.operationId === 'string' ? { operationId: entry.operationId } : {}),
    ...(typeof entry.reason === 'string' ? { reason: entry.reason } : {}),
  };
}

function readExecuteTaskId(params: Record<string, unknown>, id: JsonRpcId | null): string | null {
  const taskId = typeof params.taskId === 'string'
    ? params.taskId
    : typeof params.requestId === 'string'
      ? params.requestId
      : null;
  if (taskId) return taskId;
  void writeError(id, -32602, 'Invalid params', 'invalid-request', 'Execute params must include taskId or requestId.');
  return null;
}

function expectProcessId(value: unknown, id: JsonRpcId | null): value is string {
  if (value === processId) return true;
  void writeError(id, -32602, 'Invalid params', 'invalid-request', `Expected processId "${processId}".`);
  return false;
}

function expectObject(
  value: unknown,
  id: JsonRpcId | null,
  label: string,
): Record<string, unknown> | null {
  if (isRecord(value)) return value;
  void writeError(id, -32602, 'Invalid params', 'invalid-request', `${label} must be an object.`);
  return null;
}

function readRequiredString(value: unknown, id: JsonRpcId | null, label: string): string | null {
  if (typeof value === 'string' && value.length > 0) return value;
  void writeError(id, -32602, 'Invalid params', 'invalid-request', `${label} must be a non-empty string.`);
  return null;
}

function readEnvString(name: string): string | undefined {
  const value = process.env[name];
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function readEnvStringArray(name: string): string[] | undefined {
  const parsed = parseJson(readEnvString(name));
  if (!Array.isArray(parsed)) return undefined;
  const values = parsed.filter((value): value is string => typeof value === 'string' && value.length > 0);
  return values.length > 0 ? values : undefined;
}

function parseJson(raw: string | undefined): unknown {
  if (!raw) return undefined;
  try {
    return JSON.parse(raw);
  } catch {
    return undefined;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isJsonRpcId(value: unknown): value is JsonRpcId {
  return typeof value === 'number' || typeof value === 'string';
}

function asJsonRpcIdOrNull(value: unknown): JsonRpcId | null {
  return isJsonRpcId(value) ? value : null;
}

function isLifecycleState(value: unknown): value is ProcessLifecycleState {
  return value === 'not-installed'
    || value === 'stopped'
    || value === 'starting'
    || value === 'ready'
    || value === 'busy'
    || value === 'degraded'
    || value === 'failed'
    || value === 'stopping';
}

function isExecutableState(state: ProcessLifecycleState): boolean {
  return state === 'ready' || state === 'busy' || state === 'degraded';
}

function isLogLevel(value: unknown): value is LogLevel {
  return value === 'debug' || value === 'info' || value === 'warn' || value === 'error';
}

function normalizeFiniteNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function clampExitCode(value: unknown): number {
  const normalized = normalizeFiniteNumber(value);
  if (normalized === undefined) return 1;
  return Math.max(0, Math.min(Math.trunc(normalized), 255));
}

void MISSING_BINARY_COMMAND;
