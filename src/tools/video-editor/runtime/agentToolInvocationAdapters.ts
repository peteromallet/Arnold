/**
 * M10: Agent tool invocation adapters.
 *
 * Defines execution boundaries for browser (local), worker-safe, edge-action,
 * and pre-M12 process invocation. Every adapter uses the shared
 * `AgentToolInvocationRequest` / `ToolResult` contract with explicit
 * serializable context slices — never raw provider internals.
 *
 * @module agentToolInvocationAdapters
 * @milestone M10
 */

import type {
  AgentToolInvocationRequest,
  AgentToolRequestContext,
  AgentToolRegistrationService,
  AgentToolHandler,
  DisposeHandle,
  ToolResult,
  ToolProcessResult,
  ToolResultDiagnostic,
  ProcessSpawnConfig,
} from '@reigh/editor-sdk';
import type { AgentToolRegistry } from '@/tools/video-editor/runtime/agentToolRegistry';
import type { AgentToolInvocationService } from '@/tools/video-editor/runtime/agentToolInvocationService';

// ---------------------------------------------------------------------------
// Structured process invocation pending diagnostic (pre-M12 stub)
// ---------------------------------------------------------------------------

/** Stable diagnostic code for pre-M12 process invocation. */
export const PROCESS_INVOCATION_PENDING_CODE = 'agent-tool/process-not-available' as const;

/** Stable diagnostic message for pre-M12 process invocation. */
export const PROCESS_INVOCATION_PENDING_MESSAGE = 'Process invocation is not available until M12.';

/**
 * Create a structured `ToolResultDiagnostic` for a pending process invocation.
 *
 * This diagnostic is always returned by {@link invokeProcess} before M12.
 * It carries sufficient metadata for UI surface and diagnostic collection
 * without exposing any raw provider internals.
 */
export function createProcessInvocationPendingDiagnostic(
  toolId: string,
): ToolResultDiagnostic {
  return {
    severity: 'info',
    code: 'agent-tool/process-not-available',
    message: `Process invocation for tool "${toolId}" is not available until M12.`,
  };
}

/**
 * Create a `ToolProcessResult` with a structured pending diagnostic.
 *
 * This is the canonical return value for {@link AgentToolRegistrationService.invokeProcess}
 * before M12 process execution plumbing is available.
 */
export function createProcessInvocationResult(toolId: string): ToolProcessResult {
  return {
    family: 'process',
    diagnostics: [createProcessInvocationPendingDiagnostic(toolId)],
  };
}

// ---------------------------------------------------------------------------
// Serializable worker context (explicit slices, no provider internals)
// ---------------------------------------------------------------------------

/**
 * Serializable context slice for worker-based tool invocation.
 *
 * Contains only the explicit creative context fields defined by
 * {@link AgentToolInvocationRequest} — no raw provider references,
 * mutable store handles, or non-serializable internals.
 */
export interface SerializableWorkerContext {
  toolId: string;
  extensionId: string;
  contributionId: string;
  input?: Record<string, unknown>;
  context?: AgentToolRequestContext;
}

/**
 * Serialize an {@link AgentToolInvocationRequest} for transfer to a Web Worker.
 *
 * Only explicit serializable slices are included. This function is the
 * single chokepoint that prevents raw provider internals from leaking
 * across the worker boundary.
 */
export function serializeRequestForWorker(
  request: AgentToolInvocationRequest,
): SerializableWorkerContext {
  return {
    toolId: request.toolId,
    extensionId: request.extensionId,
    contributionId: request.contributionId,
    input: request.input,
    context: request.context,
  };
}

// ---------------------------------------------------------------------------
// Serializable edge context (explicit slices, no provider internals)
// ---------------------------------------------------------------------------

/**
 * Serializable context slice for edge-function-based tool invocation.
 *
 * Same explicit-contract guarantee as {@link SerializableWorkerContext}:
 * only serializable fields from the request, no provider internals.
 */
export interface SerializableEdgeContext {
  toolId: string;
  extensionId: string;
  contributionId: string;
  input?: Record<string, unknown>;
  context?: AgentToolRequestContext;
}

/**
 * Serialize an {@link AgentToolInvocationRequest} for transfer to an edge function.
 *
 * Chokepoint that prevents raw provider internals from crossing the
 * edge boundary.
 */
export function serializeRequestForEdge(
  request: AgentToolInvocationRequest,
): SerializableEdgeContext {
  return {
    toolId: request.toolId,
    extensionId: request.extensionId,
    contributionId: request.contributionId,
    input: request.input,
    context: request.context,
  };
}

// ---------------------------------------------------------------------------
// Local (browser) invocation adapter
// ---------------------------------------------------------------------------

/**
 * Adapter for local (browser) tool invocation.
 *
 * Delegates directly to the provider-scoped {@link AgentToolRegistry}.
 * The result is validated by the registry against the shared
 * {@link ToolResult} contract before being returned.
 */
export interface LocalInvocationAdapter {
  /**
   * Invoke a tool through the local registry.
   *
   * @returns The validated ToolResult, or null if the tool/handler is unavailable.
   */
  invokeTool(request: AgentToolInvocationRequest): Promise<ToolResult | null>;
}

/**
 * Create a local (browser) invocation adapter.
 *
 * When an `invocationService` is provided, timeline-editing (mutation/proposal)
 * results are automatically routed through {@link ProposalRuntime.create()} so
 * the host owns the proposal lifecycle. When omitted, results are returned
 * directly from the registry without proposal creation.
 *
 * @param registry - The provider-scoped agent tool registry.
 * @param invocationService - Optional composed invocation service that routes
 *   timeline-editing results through ProposalRuntime.
 */
export function createLocalInvocationAdapter(
  registry: AgentToolRegistry,
  invocationService?: AgentToolInvocationService,
): LocalInvocationAdapter {
  return {
    async invokeTool(request: AgentToolInvocationRequest): Promise<ToolResult | null> {
      if (invocationService) {
        return invocationService.invokeTool(request);
      }
      return registry.invokeTool(request);
    },
  };
}

// ---------------------------------------------------------------------------
// Worker-feasible invocation adapter
// ---------------------------------------------------------------------------

/**
 * Adapter for worker-safe tool invocation.
 *
 * Provides both the invocation boundary and serialization helper.
 * For M10, dispatch is delegated to the local registry; true worker
 * plumbing (postMessage + structured clone) is deferred to M12.
 */
export interface WorkerInvocationAdapter {
  /**
   * Invoke a tool through the worker boundary.
   *
   * In M10 this delegates to the local registry. In M12 this will
   * post the serialized request to a worker and await the result.
   */
  invokeTool(request: AgentToolInvocationRequest): Promise<ToolResult | null>;

  /**
   * Serialize a request for worker transfer.
   *
   * Strips non-serializable fields and ensures only explicit context
   * slices cross the boundary.
   */
  serializeRequest(request: AgentToolInvocationRequest): SerializableWorkerContext;
}

/**
 * Create a worker-feasible invocation adapter.
 *
 * When an `invocationService` is provided, timeline-editing results are
 * routed through ProposalRuntime. When omitted, results are returned
 * directly from the registry.
 *
 * @param registry - The provider-scoped agent tool registry.
 * @param invocationService - Optional composed invocation service.
 */
export function createWorkerInvocationAdapter(
  registry: AgentToolRegistry,
  invocationService?: AgentToolInvocationService,
): WorkerInvocationAdapter {
  return {
    async invokeTool(request: AgentToolInvocationRequest): Promise<ToolResult | null> {
      // M10: delegate to local registry. M12: postMessage + await.
      if (invocationService) {
        return invocationService.invokeTool(request);
      }
      return registry.invokeTool(request);
    },
    serializeRequest(request: AgentToolInvocationRequest): SerializableWorkerContext {
      return serializeRequestForWorker(request);
    },
  };
}

// ---------------------------------------------------------------------------
// Edge-action invocation adapter
// ---------------------------------------------------------------------------

/**
 * Adapter for edge-action tool invocation.
 *
 * Provides both the invocation boundary and serialization helper.
 * For M10, dispatch is delegated to the local registry; true edge
 * invocation (fetch to Supabase Edge Function) is deferred to M12.
 */
export interface EdgeInvocationAdapter {
  /**
   * Invoke a tool through the edge boundary.
   *
   * In M10 this delegates to the local registry. In M12 this will
   * POST the serialized request to an edge function and await the result.
   */
  invokeTool(request: AgentToolInvocationRequest): Promise<ToolResult | null>;

  /**
   * Serialize a request for edge-function transfer.
   *
   * Strips non-serializable fields and ensures only explicit context
   * slices cross the boundary.
   */
  serializeRequest(request: AgentToolInvocationRequest): SerializableEdgeContext;
}

/**
 * Create an edge-action invocation adapter.
 *
 * When an `invocationService` is provided, timeline-editing results are
 * routed through ProposalRuntime. When omitted, results are returned
 * directly from the registry.
 *
 * @param registry - The provider-scoped agent tool registry.
 * @param invocationService - Optional composed invocation service.
 */
export function createEdgeInvocationAdapter(
  registry: AgentToolRegistry,
  invocationService?: AgentToolInvocationService,
): EdgeInvocationAdapter {
  return {
    async invokeTool(request: AgentToolInvocationRequest): Promise<ToolResult | null> {
      // M10: delegate to local registry. M12: fetch to edge function.
      if (invocationService) {
        return invocationService.invokeTool(request);
      }
      return registry.invokeTool(request);
    },
    serializeRequest(request: AgentToolInvocationRequest): SerializableEdgeContext {
      return serializeRequestForEdge(request);
    },
  };
}

// ---------------------------------------------------------------------------
// Pre-M12 process invocation adapter
// ---------------------------------------------------------------------------

/**
 * Adapter for process-backed tool invocation (pre-M12 stub).
 *
 * Always returns a `ToolProcessResult` with a structured pending diagnostic.
 * Real process spawning (child_process, stdio-jsonrpc) is deferred to M12.
 */
export interface ProcessInvocationAdapter {
  /**
   * Invoke a process-backed tool.
   *
   * Before M12, always returns a pending diagnostic. The `config` parameter
   * is accepted for forward-compatibility but not executed.
   */
  invokeProcess(toolId: string, config: ProcessSpawnConfig): Promise<ToolProcessResult>;
}

/**
 * Create a pre-M12 process invocation adapter.
 *
 * The returned adapter always responds with a structured
 * `processInvocationPending` diagnostic — it never spawns a real process.
 */
export function createProcessInvocationAdapter(): ProcessInvocationAdapter {
  return {
    async invokeProcess(toolId: string, _config: ProcessSpawnConfig): Promise<ToolProcessResult> {
      return createProcessInvocationResult(toolId);
    },
  };
}

// ---------------------------------------------------------------------------
// AgentToolRegistrationService factory
// ---------------------------------------------------------------------------

/**
 * Create a per-extension `AgentToolRegistrationService` that composes
 * registry-backed handler registration and the pre-M12 process stub.
 *
 * This factory is the intended way for provider contexts to construct
 * the `agentTools` object passed to {@link createExtensionContext}.
 * It ensures:
 * - `registerTool` delegates to the provider-scoped {@link AgentToolRegistry}
 * - `invokeProcess` returns a structured pending diagnostic via the
 *   {@link ProcessInvocationAdapter}
 * - No raw provider internals are exposed through either path
 */
export function createAgentToolRegistrationService(
  registry: AgentToolRegistry,
  extensionId: string,
): AgentToolRegistrationService {
  const processAdapter = createProcessInvocationAdapter();

  return {
    registerTool(toolId: string, handler: AgentToolHandler): DisposeHandle {
      return registry.registerTool(extensionId, toolId, handler);
    },
    async invokeProcess(toolId: string, config: ProcessSpawnConfig): Promise<ToolProcessResult> {
      return processAdapter.invokeProcess(toolId, config);
    },
  };
}
