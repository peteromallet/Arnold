# JSON-RPC Protocol V0 — Stdio Wire Contract For Trusted Local Processes

Date: 2026-07-02
Status: frozen (planning-only; no runtime implementation)
Milestone: M0 — Decisions, Fixtures, and Protocol V0

## Posture

This document defines the **newline-delimited JSON-RPC 2.0 over stdio** wire
contract for `ProcessSpec.protocol: 'stdio-jsonrpc'`. It is a **durable planning
artifact only**. No runtime source, SDK export, test, script, process manager,
or sidecar runtime is created or edited by this milestone. M0 implements **no**
protocol runtime behavior — it only formalizes the contract that downstream
milestones (M12 and beyond) will implement.

Source of record: `src/sdk/video/families/processes.ts` lines 67–129
(`ProcessSpec`, `ProcessLifecycleState`); `src/examples/process-example.ts`
lines 94–113 (canonical `stdio-jsonrpc` spec shape); M0 brief
(`.megaplan/initiatives/reigh-extension-composition-spine-epic/m0-decisions-fixtures.md`);
fixture matrix rows `PL-01` through `PL-08`
(`docs/extensions/composition-spine/m0-fixture-matrices.md` lines 147–154).

## 1. Transport

| Property | Value |
|---|---|
| Transport | `stdio` (stdin/stdout; stderr reserved for process diagnostics) |
| Framing | Newline-delimited (`\n`); one JSON-RPC message per line |
| Encoding | UTF-8 |
| Protocol | JSON-RPC 2.0 (conformant) |
| `ProcessSpec` discriminator | `protocol: 'stdio-jsonrpc'` |

Source: `processes.ts:73` (`protocol: 'stdio-jsonrpc'`); `process-example.ts:107`
(`protocol: 'stdio-jsonrpc'`).

Messages are framed as single lines terminated by `\n`. The host runtime writes
requests to the process's stdin and reads responses/notifications from the
process's stdout. The process MUST NOT emit unstructured output on stdout; all
stdout output MUST be valid newline-delimited JSON-RPC 2.0 messages. The
process MAY emit diagnostic information on stderr; stderr output is not parsed
by the host.

## 2. Methods

The host runtime sends JSON-RPC 2.0 **requests** (method calls) to the process.
The four required methods are:

### 2.1 `health`

**Purpose**: Query process health and current lifecycle state.

**Direction**: Host → Process (request)

**Request**:
```json
{"jsonrpc":"2.0","id":1,"method":"health","params":{}}
```

**Response** (`result`):
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "state": "ready",
    "processId": "example-analyzer",
    "version": {"semver": "1.0.0"},
    "uptimeMs": 12000
  }
}
```

The `state` field MUST be one of the eight `ProcessLifecycleState` values
(see §5). The `processId` MUST match the `ProcessSpec.id` declared in the
extension manifest.

**Error response** (`error`):
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": {"class": "protocol-error", "detail": "Process is in failed state"}
  }
}
```

Source: `processes.ts:74` (`healthCheck?: string`); `process-example.ts:108`
(`healthCheck: 'health'`). The `healthCheck` field in `ProcessSpec` names the
method the host calls for health checks; it defaults to `health` when omitted.

### 2.2 `execute`

**Purpose**: Execute a named operation declared in `ProcessOperationSpec`.

**Direction**: Host → Process (request)

**Request**:
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "execute",
  "params": {
    "operationId": "analyze",
    "taskId": "task-42",
    "processId": "example-analyzer",
    "input": {"frameIndex": 0, "region": {"x": 0, "y": 0, "width": 1920, "height": 1080}}
  }
}
```

The `operationId` MUST match an `id` from the `ProcessSpec.operations` array.
The `taskId` is a host-assigned correlation identifier scoped to this execution.
The `input` object MUST conform to the `ProcessOperationSpec.inputSchema` for
the named operation.

During execution, the process MAY emit `progress` and `log` notifications
(see §3).

**Successful response** (`result`):
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "operationId": "analyze",
    "taskId": "task-42",
    "processId": "example-analyzer",
    "output": {"detections": [], "metadata": {}}
  }
}
```

Source: `processes.ts:55–65` (`ProcessOperationSpec`); `process-example.ts:60–92`
(canonical operation specs with `inputSchema`, `outputKinds`, `routes`, and
`requiredCapabilities`).

### 2.3 `cancel`

**Purpose**: Cancel an in-flight operation.

**Direction**: Host → Process (notification or request)

**Request/Notification**:
```json
{"jsonrpc":"2.0","method":"cancel","params":{"operationId":"analyze","taskId":"task-42","processId":"example-analyzer"}}
```

`cancel` MAY be sent as a JSON-RPC notification (no `id` field). The host does
not require a response, but the process SHOULD stop executing the named
operation and transition the process state accordingly. If sent as a request
(with `id`), the process MUST respond with a `result` or `error`.

Source: M0 brief Locked Decisions; `processes.ts:55–65` (operation lifecycle
needs a cancellation path for long-running, route-blocking operations).

### 2.4 `shutdown`

**Purpose**: Request graceful process shutdown.

**Direction**: Host → Process (request)

**Request**:
```json
{"jsonrpc":"2.0","id":3,"method":"shutdown","params":{"processId":"example-analyzer","reason":"host-closing"}}
```

The process SHOULD complete or cancel in-flight operations, flush any pending
output, and exit with code 0. The host waits for the process to exit, then
transitions the lifecycle state to `stopped`.

**Response** (`result`):
```json
{"jsonrpc":"2.0","id":3,"result":{"acknowledged":true,"processId":"example-analyzer"}}
```

Source: `processes.ts:75` (`shutdown?: string`); `processLifecycleState`
includes `stopping` as the transition state during shutdown.

## 3. Message Types

In addition to standard JSON-RPC 2.0 request/response semantics, the protocol
defines four message categories used for notification-style communication from
the process to the host.

### 3.1 `progress`

**Type**: JSON-RPC notification (process → host)

Sent by the process during a long-running `execute` operation to report
incremental progress.

```json
{
  "jsonrpc": "2.0",
  "method": "progress",
  "params": {
    "operationId": "analyze",
    "taskId": "task-42",
    "processId": "example-analyzer",
    "progress": {"percent": 45, "current": 450, "total": 1000, "message": "Processing frame 450/1000"}
  }
}
```

The `progress` object carries a `ProcessProgressEvent` shape as defined in
`src/sdk/capabilities` (imported by `processes.ts:23`).

The host MAY surface progress in the UI (progress bar, status indicator) for
the owning route or operation.

### 3.2 `log`

**Type**: JSON-RPC notification (process → host)

Sent by the process to emit structured log entries to the host diagnostic
channel.

```json
{
  "jsonrpc": "2.0",
  "method": "log",
  "params": {
    "processId": "example-analyzer",
    "level": "warn",
    "message": "GPU memory pressure detected; falling back to CPU path",
    "operationId": "analyze",
    "taskId": "task-42",
    "timestamp": "2026-07-02T14:00:00.000Z"
  }
}
```

`level` is one of `debug`, `info`, `warn`, or `error`. The host MAY surface log
entries as `ExtensionDiagnostic` items in the extension status drawer.

### 3.3 `result`

**Type**: JSON-RPC 2.0 success response (process → host)

Sent by the process in response to a request (`health`, `execute`, `shutdown`,
or `cancel` with `id`). The `result` object MUST include the correlation fields
applicable to the method.

See §2.1 and §2.2 for representative `result` payloads.

### 3.4 `error`

**Type**: JSON-RPC 2.0 error response (process → host, or host → process)

Sent when a request cannot be fulfilled. The `error.data` object SHOULD include
a `class` field identifying the error category (see §6).

See §2.1 for a representative `error` payload.

## 4. Correlation Fields

Every protocol message that relates to a specific process, operation, or task
carries a subset of the following correlation fields:

| Field | Type | Scope | Description |
|---|---|---|---|
| `processId` | `string` | All messages | Matches `ProcessSpec.id` from the extension manifest. Identifies which trusted local process the message targets. |
| `operationId` | `string` | Execute/cancel/progress/log/result/error | Matches an `id` from `ProcessSpec.operations[]`. Identifies which declared operation is being invoked. |
| `taskId` | `string` | Execute/cancel/progress/log/result/error | Host-assigned, unique per execution invocation. Allows the host to correlate progress/log/result/error notifications with the originating `execute` request when multiple operations are in flight. |

`processId` is present in every message. `operationId` and `taskId` are present
only in message contexts that relate to a specific operation execution (execute,
cancel, progress, log, result, error for an operation). `health` and `shutdown`
messages carry `processId` but not `operationId` or `taskId`.

Source: `processes.ts:68–82` (`ProcessSpec.id`); `processes.ts:55–65`
(`ProcessOperationSpec.id`); `processes.ts:111–129` (`ProcessStatus`
discriminated union uses `processId` and `operationId` for correlation).

## 5. Process Lifecycle States

The eight canonical `ProcessLifecycleState` values, as defined in
`src/sdk/video/families/processes.ts` lines 101–109 and fixture matrix rows
`PL-01` through `PL-08`:

| Row | State | Description | Protocol visibility |
|---|---|---|---|
| `PL-01` | `not-installed` | Process is declared but not installed on the host system. | Process cannot be spawned. No protocol traffic. |
| `PL-02` | `stopped` | Process is installed but not running. | Process is not spawned. No protocol traffic until host issues spawn. |
| `PL-03` | `starting` | Host has spawned the process; awaiting `health` → `ready`. | Host sends `health` requests; process MAY respond with `starting`. |
| `PL-04` | `ready` | Process can serve operations. | Host may send `execute` requests. Process responds to `health` with `ready`. |
| `PL-05` | `busy` | Process is executing an operation (`execute` in flight). | Host sent `execute`; process emits `progress`/`log`; awaits `result`/`error`. |
| `PL-06` | `degraded` | Process is usable but in a warning state (e.g., health check latency high). | Host may still send `execute`; `health` response carries `degraded` with diagnostic detail. |
| `PL-07` | `failed` | Process crashed, exited unexpectedly, or is otherwise unavailable. | No protocol traffic until host restarts or replaces the process. |
| `PL-08` | `stopping` | Host has sent `shutdown`; process is draining and preparing to exit. | Host awaits process exit; process SHOULD respond to `shutdown` with `result` before exiting. |

State transitions are managed by the host runtime, not by the protocol itself.
The protocol transports state information; it does not define the state machine
transitions.

Source: `processes.ts:101–109` (`ProcessLifecycleState` type);
`m0-fixture-matrices.md:147–154` (fixture rows `PL-01` through `PL-08`);
`renderPlanner.ts:358–360,593–633` (planner consumes lifecycle states to
determine route readiness).

## 6. Error Classes

Every JSON-RPC error response SHOULD carry a `data.class` field identifying
one of the following four error classes:

### 6.1 `protocol-error`

A protocol-level violation: malformed JSON, missing required fields, invalid
method name, or non-conformant message framing.

```json
{
  "jsonrpc": "2.0",
  "id": null,
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": {"class": "protocol-error", "detail": "Missing jsonrpc version field"}
  }
}
```

### 6.2 `timeout`

An operation exceeded its configured timeout. The host MAY cancel the operation
and the process SHOULD stop processing.

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32000,
    "message": "Operation timed out",
    "data": {"class": "timeout", "operationId": "analyze", "taskId": "task-42", "timeoutMs": 30000}
  }
}
```

### 6.3 `process-exited`

The process exited unexpectedly while an operation was in flight. This error is
generated by the host runtime (not the process) when the process stdout pipe
closes or the process exits with a non-zero code during an active `execute`.

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32001,
    "message": "Process exited unexpectedly",
    "data": {"class": "process-exited", "processId": "example-analyzer", "exitCode": 1, "signal": null}
  }
}
```

### 6.4 `invalid-request`

A request that is syntactically valid JSON-RPC but semantically invalid:
unknown `operationId`, `input` that fails `inputSchema` validation, `cancel`
targeting a non-existent task, or `execute` sent to a process not in `ready` or
`busy` state.

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {"class": "invalid-request", "detail": "Unknown operationId: 'nonexistent'"}
  }
}
```

Source: M0 brief error classification requirements;
`processes.ts:101–129` (lifecycle states and status discriminated union include
error/timing/failure fields for host-side error synthesis).

## 7. Protocol Sequence Examples

### 7.1 Healthy Startup

```
Host spawns process
Host → Process: {"jsonrpc":"2.0","id":1,"method":"health","params":{}}
Process → Host: {"jsonrpc":"2.0","id":1,"result":{"state":"starting","processId":"example-analyzer"}}
Host → Process: {"jsonrpc":"2.0","id":2,"method":"health","params":{}}
Process → Host: {"jsonrpc":"2.0","id":2,"result":{"state":"ready","processId":"example-analyzer","version":{"semver":"1.0.0"},"uptimeMs":500}}
```

### 7.2 Execute With Progress

```
Host → Process: {"jsonrpc":"2.0","id":3,"method":"execute","params":{"operationId":"analyze","taskId":"task-42","processId":"example-analyzer","input":{"frameIndex":0}}}
Process → Host: {"jsonrpc":"2.0","method":"progress","params":{"operationId":"analyze","taskId":"task-42","processId":"example-analyzer","progress":{"percent":50,"message":"Half done"}}}
Process → Host: {"jsonrpc":"2.0","method":"log","params":{"processId":"example-analyzer","level":"info","message":"Intermediate result cached","operationId":"analyze","taskId":"task-42"}}
Process → Host: {"jsonrpc":"2.0","id":3,"result":{"operationId":"analyze","taskId":"task-42","processId":"example-analyzer","output":{"detections":[]}}}
```

### 7.3 Cancel During Execution

```
Host → Process: {"jsonrpc":"2.0","id":4,"method":"execute","params":{"operationId":"analyze","taskId":"task-43","processId":"example-analyzer","input":{"frameIndex":1}}}
Host → Process: {"jsonrpc":"2.0","method":"cancel","params":{"operationId":"analyze","taskId":"task-43","processId":"example-analyzer"}}
Process → Host: {"jsonrpc":"2.0","id":4,"error":{"code":-32800,"message":"Operation cancelled","data":{"class":"protocol-error","operationId":"analyze","taskId":"task-43","detail":"Cancelled by host"}}}
```

### 7.4 Graceful Shutdown

```
Host → Process: {"jsonrpc":"2.0","id":5,"method":"shutdown","params":{"processId":"example-analyzer","reason":"host-closing"}}
Process → Host: {"jsonrpc":"2.0","id":5,"result":{"acknowledged":true,"processId":"example-analyzer"}}
Process exits with code 0
Host transitions state → stopped
```

## 8. M0 Scope Boundary

This document defines the **wire contract only**. It does not:

- Define a process manager, spawner, or lifecycle state machine
- Specify timeout values, retry policies, or restart semantics
- Implement JSON-RPC framing, parsing, or validation
- Create SDK exports, runtime modules, or test suites
- Wire `progress`/`log` notifications to UI surfaces
- Define input schema validation or output kind routing

All of the above are deferred to downstream milestones (M12 for process
lifecycle execution, M9 for sidecar sandboxing, and later integration
milestones). This artifact exists so those milestones can reference stable
method names, message types, state values, and error classes without
re-deriving them from source.

## 9. Derived Schemas (Non-Normative)

This section provides TypeScript type sketches derived from the protocol
definition above. These are not runtime exports; they are included here
for planning reference only.

```typescript
// Non-normative: for planning reference only. Not an SDK export.

type JsonRpcProtocolMethod =
  | 'health'
  | 'execute'
  | 'cancel'
  | 'shutdown';

type JsonRpcMessageType =
  | 'progress'
  | 'log'
  | 'result'
  | 'error';

type JsonRpcErrorClass =
  | 'protocol-error'
  | 'timeout'
  | 'process-exited'
  | 'invalid-request';

type ProcessLifecycleState =
  | 'not-installed'
  | 'stopped'
  | 'starting'
  | 'ready'
  | 'busy'
  | 'degraded'
  | 'failed'
  | 'stopping';

interface JsonRpcCorrelation {
  processId: string;
  operationId?: string;
  taskId?: string;
}

interface JsonRpcHealthResult {
  state: ProcessLifecycleState;
  processId: string;
  version?: { semver: string };
  uptimeMs?: number;
}

interface JsonRpcExecuteParams extends JsonRpcCorrelation {
  operationId: string;
  taskId: string;
  input: Record<string, unknown>;
}

interface JsonRpcProgressNotificationParams extends JsonRpcCorrelation {
  operationId: string;
  taskId: string;
  progress: {
    percent?: number;
    current?: number;
    total?: number;
    message?: string;
  };
}

interface JsonRpcErrorDetail {
  class: JsonRpcErrorClass;
  detail?: string;
  operationId?: string;
  taskId?: string;
  processId?: string;
  timeoutMs?: number;
  exitCode?: number;
  signal?: string | null;
}
```
