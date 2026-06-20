/**
 * M10: Agent tool registry — provider-scoped, in-memory, unit-testable.
 *
 * Responsibilities:
 * - Declarative AgentToolContribution ingestion from extension manifests
 * - Imperative agent tool handler registration during activate()
 * - Deterministic contribution/local-handler registration with duplicate detection
 * - Lifecycle snapshots and subscriptions for external consumers
 * - Progress events, cancellation, and session handles
 * - Diagnostics attribution (tool-scoped, extension-scoped)
 * - Result validation via agentToolContracts helpers
 * - `unregisterAll(extensionId)` for HMR and extension disposal
 *
 * One registry per editor provider mount.  Wired into the lifecycle so that
 * `unregisterAll(extensionId)` tears down every contribution and handler
 * for a disposed extension.
 *
 * @module agentToolRegistry
 * @milestone M10
 */

import type {
  DisposeHandle,
  ExtensionDiagnostic,
  DiagnosticSeverity,
  AgentToolContribution,
  AgentToolInputSchema,
  AgentToolHandler,
  AgentToolInvocationRequest,
  AgentToolRegistrationService,
  ToolResult,
  ToolResultFamily,
  ToolResultDiagnostic,
  GenerationSession,
  GenerationSessionLiveDelivery,
  LiveChannelDescriptor,
  LiveSourceDiagnostic,
} from '@reigh/editor-sdk';
import {
  validateAgentToolInputSchema,
  validateToolResult,
  isToolResultFamily,
} from '@/tools/video-editor/runtime/agentToolContracts';
import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry';
import { evaluateGenerationSessionLiveDeliveryGate } from '@/tools/video-editor/runtime/liveSteering';

// ---------------------------------------------------------------------------
// Public registry shapes
// ---------------------------------------------------------------------------

/** A single resolved agent tool entry (frozen for snapshot consumers). */
export interface AgentToolEntry {
  /** The tool identifier used in registration calls. */
  readonly toolId: string;
  /** The extension that declared this tool. */
  readonly extensionId: string;
  /** The contribution ID in the manifest. */
  readonly contributionId: string;
  /** Human-readable label. */
  readonly label: string;
  /** Human-readable description. */
  readonly description?: string;
  /** Raw input schema as declared in the manifest (undefined if absent or invalid). */
  readonly inputSchema?: AgentToolInputSchema;
  /** Input schema validation diagnostics (empty = valid). */
  readonly inputSchemaDiagnostics: readonly ToolResultDiagnostic[];
  /** Result families this tool can produce (empty = all accepted). */
  readonly resultFamilies: readonly ToolResultFamily[];
  /** Sort order. */
  readonly order: number;
  /** Optional visibility predicate. */
  readonly when?: string;
  /** Whether a handler has been registered for this tool. */
  readonly hasHandler: boolean;
}

/** Execution status for the most recent invocation of a tool. */
export interface AgentToolRunStatus {
  /** The total number of invocations (successful + failed). */
  readonly invocationCount: number;
  /** Timestamp of the most recent invocation (epoch ms), or 0 if never invoked. */
  readonly lastRunAt: number;
  /** Whether the most recent invocation completed without errors. */
  readonly lastRunOk: boolean;
  /** Error message from the most recent failed invocation, or null. */
  readonly lastError: string | null;
}

/** A tracked generation session. */
export interface AgentToolSessionEntry {
  /** The session handle. */
  readonly session: GenerationSession;
  /** The tool ID that created this session. */
  readonly toolId: string;
  /** The extension that owns the tool. */
  readonly extensionId: string;
  /** Creation timestamp (epoch ms). */
  readonly createdAt: number;
  /** Live delivery activation metadata, when this generation session streams samples. */
  readonly liveDelivery?: AgentToolSessionLiveDeliveryState;
}

export interface AgentToolSessionLiveDeliveryState {
  readonly origin: string;
  readonly sourceId?: string;
  readonly activeChannels: readonly LiveChannelDescriptor[];
  readonly progress: number;
  readonly cancelled: boolean;
  readonly steeringDecision?: GenerationSessionLiveDelivery['steeringDecision'];
  readonly generationIndex?: number;
  readonly steerHash?: string;
  readonly parentRefs?: readonly string[];
  readonly finalRefs?: readonly string[];
  readonly bakedRefs?: readonly string[];
  readonly sampleCount: number;
  readonly canActivate: boolean;
  readonly diagnostics: readonly LiveSourceDiagnostic[];
}

/** Frozen snapshot of the entire agent tool registry for external consumers. */
export interface AgentToolRegistrySnapshot {
  /** All registered tools, ordered by extensionId → toolId. */
  readonly tools: readonly AgentToolEntry[];
  /** Active generation sessions. */
  readonly sessions: readonly AgentToolSessionEntry[];
  /** Diagnostics emitted by the registry. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /** Lookup a tool entry by tool ID. */
  readonly getTool: (toolId: string) => AgentToolEntry | undefined;
  /** Lookup execution status for a tool. */
  readonly getStatus: (toolId: string) => AgentToolRunStatus;
  /** Get all active sessions for a tool. */
  readonly getSessions: (toolId: string) => readonly AgentToolSessionEntry[];
}

// ---------------------------------------------------------------------------
// Internal state
// ---------------------------------------------------------------------------

interface InternalTool {
  toolId: string;
  extensionId: string;
  contributionId: string;
  label: string;
  description?: string;
  inputSchema?: AgentToolInputSchema;
  inputSchemaDiagnostics: readonly ToolResultDiagnostic[];
  resultFamilies: readonly ToolResultFamily[];
  order: number;
  when?: string;
  handler: AgentToolHandler | null; // null until registerTool() is called
}

interface InternalRunStatus {
  invocationCount: number;
  lastRunAt: number;
  lastRunOk: boolean;
  lastError: string | null;
}

interface InternalSessionLiveDeliveryState {
  origin: string;
  sourceId?: string;
  activeChannels: LiveChannelDescriptor[];
  progress: number;
  cancelled: boolean;
  steeringDecision?: GenerationSessionLiveDelivery['steeringDecision'];
  generationIndex?: number;
  steerHash?: string;
  parentRefs?: readonly string[];
  finalRefs?: readonly string[];
  bakedRefs?: readonly string[];
  sampleCount: number;
  canActivate: boolean;
  diagnostics: LiveSourceDiagnostic[];
}

interface InternalSessionEntry {
  session: GenerationSession;
  toolId: string;
  extensionId: string;
  createdAt: number;
  liveDelivery?: InternalSessionLiveDeliveryState;
}

export interface AgentToolRegistryConfig {
  readonly liveDataRegistry?: LiveDataRegistry;
}

// ---------------------------------------------------------------------------
// Emit helper
// ---------------------------------------------------------------------------

function emitDiagnostic(
  diagnostics: ExtensionDiagnostic[],
  severity: DiagnosticSeverity,
  code: string,
  message: string,
  extensionId?: string,
  contributionId?: string,
  detail?: Record<string, unknown>,
): void {
  diagnostics.push(Object.freeze({
    severity,
    code,
    message,
    ...(extensionId ? { extensionId } : {}),
    ...(contributionId ? { contributionId } : {}),
    ...(detail ? { detail } : {}),
  }));
}

// ---------------------------------------------------------------------------
// Callbacks
// ---------------------------------------------------------------------------

/**
 * Callbacks for toast and progress reporting from the agent tool runtime.
 * The host wires these at provider mount time so the pure registry can
 * signal failures to the UI without importing React or host components.
 */
export interface AgentToolRegistryCallbacks {
  /** Called when a tool handler throws or rejects. */
  onToolFailure?: (toolId: string, error: Error, extensionId: string) => void;
  /** Called when a duplicate tool registration is diagnosed. */
  onDuplicateTool?: (toolId: string, originalExtension: string, conflictingExtension: string) => void;
  /** Called when progress is reported by a tool. */
  onToolProgress?: (toolId: string, extensionId: string, progress: number, label?: string) => void;
  /** Called when a tool session is cancelled. */
  onToolCancelled?: (toolId: string, extensionId: string, sessionId: string) => void;
  /** Called when a tool session completes. */
  onToolCompleted?: (toolId: string, extensionId: string, sessionId: string) => void;
}

// ---------------------------------------------------------------------------
// Public interface
// ---------------------------------------------------------------------------

export interface AgentToolRegistry {
  // ---- Imperative handler registration -----------------------------------

  /**
   * Register an agent tool handler imperatively during activate().
   *
   * The tool must have been declared via an AgentToolContribution in the
   * extension manifest. Returns a DisposeHandle that unregisters the handler
   * (but not the tool declaration itself).
   */
  registerTool(
    extensionId: string,
    toolId: string,
    handler: AgentToolHandler,
  ): DisposeHandle;

  // ---- Declarative contribution ingestion --------------------------------

  /**
   * Ingest an AgentToolContribution from an extension manifest.
   * Called during synchronization when contributions are discovered.
   *
   * - Duplicate tool IDs (already registered by a different extension)
   *   are rejected (first-registered-wins).
   * - Duplicate contributions from the same extension are treated as
   *   overwrites (last wins within the same extension).
   * - Input schemas are validated at ingestion time.
   */
  ingestAgentToolContribution(extensionId: string, contribution: AgentToolContribution): void;

  // ---- Tool invocation ---------------------------------------------------

  /**
   * Invoke a registered agent tool.
   *
   * Validates the input schema before invocation and validates the result
   * after. Handles missing tools, tools without handlers (disabled),
   * and handler errors gracefully — all are captured as diagnostics.
   *
   * @param request  The invocation request with tool ID, context, and input.
   * @returns The ToolResult, or null if the tool/handler is unavailable.
   */
  invokeTool(request: AgentToolInvocationRequest): Promise<ToolResult | null>;

  // ---- Progress & cancellation -------------------------------------------

  /**
   * Report progress for an in-flight tool invocation.
   */
  reportProgress(toolId: string, extensionId: string, progress: number, label?: string): void;

  /**
   * Cancel all active sessions for a tool.
   * Returns the number of sessions cancelled.
   */
  cancelSessions(toolId: string): number;

  /**
   * Cancel all active sessions for an extension.
   * Returns the number of sessions cancelled.
   */
  cancelExtensionSessions(extensionId: string): number;

  // ---- Session tracking --------------------------------------------------

  /**
   * Track a generation session produced by a tool invocation.
   */
  trackSession(toolId: string, extensionId: string, session: GenerationSession): void;

  /**
   * Remove a completed or cancelled session from tracking.
   */
  untrackSession(sessionId: string): void;

  // ---- Diagnostics -------------------------------------------------------

  /** All diagnostics emitted by the registry. */
  readonly diagnostics: readonly ExtensionDiagnostic[];

  /** Subscribe to registry diagnostic changes. */
  subscribe(listener: () => void): DisposeHandle;

  // ---- Snapshot ----------------------------------------------------------

  /** Return a frozen snapshot suitable for external consumers. */
  getSnapshot(): AgentToolRegistrySnapshot;

  // ---- Lifecycle ---------------------------------------------------------

  /**
   * Remove every tool contribution, handler, and active session
   * for a given extension. Called during extension disposal.
   */
  unregisterAll(extensionId: string): void;

  /** Set callbacks for toast/diagnostic integration with the host UI. */
  setCallbacks(callbacks: AgentToolRegistryCallbacks): void;

  /** Dispose the entire registry. Terminal. */
  dispose(): void;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export function createAgentToolRegistry(config: AgentToolRegistryConfig = {}): AgentToolRegistry {
  // toolId → InternalTool
  const tools = new Map<string, InternalTool>();

  // toolId → InternalRunStatus
  const runStatuses = new Map<string, InternalRunStatus>();

  // sessionId → InternalSessionEntry
  const sessions = new Map<string, InternalSessionEntry>();
  const sessionDisposers = new Map<string, DisposeHandle[]>();

  const diagnostics: ExtensionDiagnostic[] = [];
  const listeners = new Set<() => void>();
  let callbacks: AgentToolRegistryCallbacks = {};
  let disposed = false;
  let frozenSnapshot: AgentToolRegistrySnapshot | null = null;

  // ---- helpers -----------------------------------------------------------

  function guardDisposed(operation: string): boolean {
    if (disposed) {
      addDiagnostic('warning',
        'agent-tool-registry/disposed',
        `AgentToolRegistry operation "${operation}" called after dispose.`,
      );
      return true;
    }
    return false;
  }

  function invalidateSnapshot(): void {
    frozenSnapshot = null;
  }

  function notifyListeners(): void {
    for (const listener of listeners) {
      listener();
    }
  }

  function addDiagnostic(
    severity: DiagnosticSeverity,
    code: string,
    message: string,
    extensionId?: string,
    contributionId?: string,
    detail?: Record<string, unknown>,
  ): void {
    emitDiagnostic(diagnostics, severity, code, message, extensionId, contributionId, detail);
    invalidateSnapshot();
    notifyListeners();
  }

  function getOrCreateStatus(toolId: string): InternalRunStatus {
    let s = runStatuses.get(toolId);
    if (!s) {
      s = { invocationCount: 0, lastRunAt: 0, lastRunOk: true, lastError: null };
      runStatuses.set(toolId, s);
    }
    return s;
  }

  function recordSuccess(toolId: string): void {
    const s = getOrCreateStatus(toolId);
    s.invocationCount += 1;
    s.lastRunAt = Date.now();
    s.lastRunOk = true;
    s.lastError = null;
  }

  function recordFailure(toolId: string, error: Error): void {
    const s = getOrCreateStatus(toolId);
    s.invocationCount += 1;
    s.lastRunAt = Date.now();
    s.lastRunOk = false;
    s.lastError = error.message;
  }

  // ---- ingestAgentToolContribution ---------------------------------------

  function ingestAgentToolContribution(
    extensionId: string,
    contribution: AgentToolContribution,
  ): void {
    if (guardDisposed('ingestAgentToolContribution')) return;

    const toolId = contribution.toolId;

    // Validate input schema at ingestion time
    const inputSchemaDiagnostics = validateAgentToolInputSchema(contribution.inputSchema);

    // Validate result families
    const resultFamilies: ToolResultFamily[] = [];
    if (contribution.resultFamilies && contribution.resultFamilies.length > 0) {
      for (const family of contribution.resultFamilies) {
        if (isToolResultFamily(family)) {
          resultFamilies.push(family);
        } else {
          addDiagnostic('warning',
            'agent-tool-registry/invalid-result-family',
            `Tool "${toolId}" (extension "${extensionId}") declares unsupported result family "${String(family)}".`,
            extensionId,
            contribution.id,
            { family },
          );
        }
      }
    }

    // Conflict check: first-registered-wins (across extensions)
    const existing = tools.get(toolId);
    if (existing && existing.extensionId !== extensionId) {
      addDiagnostic('warning',
        'agent-tool-registry/duplicate-tool',
        `Tool "${toolId}" already registered by extension "${existing.extensionId}". Extension "${extensionId}" cannot override it.`,
        extensionId,
        contribution.id,
        { originalExtension: existing.extensionId },
      );
      callbacks.onDuplicateTool?.(toolId, existing.extensionId, extensionId);
      return;
    }

    // Same-extension re-registration: overwrite metadata (handler preserved if already set)
    const existingHandler = existing?.handler ?? null;

    tools.set(toolId, {
      toolId,
      extensionId,
      contributionId: contribution.id,
      label: contribution.label,
      description: contribution.description,
      inputSchema: contribution.inputSchema,
      inputSchemaDiagnostics,
      resultFamilies,
      order: contribution.order ?? 0,
      when: contribution.when,
      handler: existingHandler,
    });

    // Emit diagnostics for schema validation failures
    for (const diag of inputSchemaDiagnostics) {
      addDiagnostic(
        diag.severity,
        diag.code,
        `Tool "${toolId}" input schema: ${diag.message}`,
        extensionId,
        contribution.id,
        diag.detail,
      );
    }

    invalidateSnapshot();
  }

  // ---- registerTool ------------------------------------------------------

  function registerTool(
    extensionId: string,
    toolId: string,
    handler: AgentToolHandler,
  ): DisposeHandle {
    if (guardDisposed('registerTool')) {
      return { dispose() {} };
    }

    // Must have a tool contribution already ingested
    const tool = tools.get(toolId);
    if (!tool) {
      addDiagnostic('warning',
        'agent-tool-registry/handler-no-tool',
        `Cannot register handler for tool "${toolId}" — no matching AgentToolContribution found for extension "${extensionId}".`,
        extensionId,
      );
      return { dispose() {} }; // No-op dispose
    }

    // Handler must belong to the declaring extension
    if (tool.extensionId !== extensionId) {
      addDiagnostic('warning',
        'agent-tool-registry/handler-wrong-extension',
        `Cannot register handler for tool "${toolId}" — tool is owned by extension "${tool.extensionId}", not "${extensionId}".`,
        extensionId,
      );
      return { dispose() {} };
    }

    // Duplicate handler detection within same extension
    if (tool.handler !== null) {
      addDiagnostic('warning',
        'agent-tool-registry/duplicate-handler',
        `Tool "${toolId}" already has a handler registered by extension "${extensionId}". Overwriting.`,
        extensionId,
        tool.contributionId,
      );
    }

    tool.handler = handler;
    invalidateSnapshot();

    let unregistered = false;

    return {
      dispose(): void {
        if (unregistered) return;
        unregistered = true;

        const current = tools.get(toolId);
        if (current && current.extensionId === extensionId) {
          current.handler = null;
          invalidateSnapshot();
        }
      },
    };
  }

  // ---- invokeTool --------------------------------------------------------

  async function invokeTool(
    request: AgentToolInvocationRequest,
  ): Promise<ToolResult | null> {
    if (guardDisposed('invokeTool')) return null;

    const { toolId, extensionId } = request;

    const tool = tools.get(toolId);
    if (!tool) {
      addDiagnostic('error',
        'agent-tool-registry/tool-not-found',
        `Tool "${toolId}" is not registered.`,
        extensionId,
      );
      return null;
    }

    if (tool.extensionId !== extensionId) {
      addDiagnostic('error',
        'agent-tool-registry/tool-extension-mismatch',
        `Tool "${toolId}" is owned by extension "${tool.extensionId}", not "${extensionId}".`,
        extensionId,
      );
      return null;
    }

    if (!tool.handler) {
      addDiagnostic('warning',
        'agent-tool-registry/tool-no-handler',
        `Tool "${toolId}" has no handler registered.`,
        extensionId,
        tool.contributionId,
      );
      return null;
    }

    try {
      const result = await tool.handler(request);

      // Validate the result
      const resultDiagnostics = validateToolResult(result);
      for (const diag of resultDiagnostics) {
        addDiagnostic(
          diag.severity,
          diag.code,
          `Tool "${toolId}" result: ${diag.message}`,
          extensionId,
          tool.contributionId,
          diag.detail,
        );
      }

      // If the result has its own diagnostics, surface them
      if (result && typeof result === 'object' && 'diagnostics' in result) {
        const resultDiags = (result as unknown as Record<string, unknown>).diagnostics;
        if (Array.isArray(resultDiags)) {
          for (const diag of resultDiags) {
            if (diag && typeof diag === 'object') {
              const d = diag as Record<string, unknown>;
              addDiagnostic(
                (d.severity as DiagnosticSeverity) ?? 'info',
                typeof d.code === 'string' ? d.code : 'agent-tool/result-diagnostic',
                typeof d.message === 'string' ? d.message : 'Tool produced a diagnostic.',
                extensionId,
                tool.contributionId,
                d.detail as Record<string, unknown> | undefined,
              );
            }
          }
        }
      }

      recordSuccess(toolId);

      // Track sessions if the result is a generation/session result
      if (
        result &&
        typeof result === 'object' &&
        (result as unknown as Record<string, unknown>).family === 'generation/session'
      ) {
        const sessionResult = result as {
          session: GenerationSession;
          liveDelivery?: GenerationSessionLiveDelivery;
        };
        if (sessionResult.session && typeof sessionResult.session === 'object') {
          trackSession(
            toolId,
            extensionId,
            sessionResult.session,
            sessionResult.liveDelivery ?? sessionResult.session.liveDelivery,
          );
        }
      }

      return result;
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      recordFailure(toolId, err);

      addDiagnostic('error',
        'agent-tool-registry/handler-error',
        `Tool "${toolId}" handler threw: ${err.message}`,
        extensionId,
        tool.contributionId,
        { stack: err.stack },
      );

      callbacks.onToolFailure?.(toolId, err, extensionId);
      return null;
    }
  }

  // ---- progress & cancellation -------------------------------------------

  function reportProgress(
    toolId: string,
    extensionId: string,
    progress: number,
    label?: string,
  ): void {
    callbacks.onToolProgress?.(toolId, extensionId, progress, label);
  }

  function cancelSessions(toolId: string): number {
    let count = 0;
    for (const [sessionId, entry] of sessions) {
      if (entry.toolId === toolId) {
        try {
          entry.session.cancel();
        } catch {
          // Cancel should never throw, but guard anyway
        }
        cleanupSession(sessionId);
        sessions.delete(sessionId);
        callbacks.onToolCancelled?.(toolId, entry.extensionId, sessionId);
        count += 1;
      }
    }
    if (count > 0) {
      invalidateSnapshot();
    }
    return count;
  }

  function cancelExtensionSessions(extensionId: string): number {
    let count = 0;
    for (const [sessionId, entry] of sessions) {
      if (entry.extensionId === extensionId) {
        try {
          entry.session.cancel();
        } catch {
          // Cancel should never throw, but guard anyway
        }
        cleanupSession(sessionId);
        sessions.delete(sessionId);
        callbacks.onToolCancelled?.(entry.toolId, extensionId, sessionId);
        count += 1;
      }
    }
    if (count > 0) {
      invalidateSnapshot();
    }
    return count;
  }

  // ---- session tracking --------------------------------------------------

  function trackSession(
    toolId: string,
    extensionId: string,
    session: GenerationSession,
    liveDelivery?: GenerationSessionLiveDelivery,
  ): void {
    const entry: InternalSessionEntry = {
      session,
      toolId,
      extensionId,
      createdAt: Date.now(),
    };
    sessions.set(session.id, entry);
    activateGenerationSessionLiveDelivery(entry, liveDelivery ?? session.liveDelivery);

    // Auto-untrack on completion
    const originalComplete = session.complete.bind(session);
    session.complete = (result?: Record<string, unknown>) => {
      if (entry.liveDelivery) {
        entry.liveDelivery.progress = 100;
        entry.liveDelivery.finalRefs = readStringArray(result?.finalRefs) ?? entry.liveDelivery.finalRefs;
        entry.liveDelivery.bakedRefs = readStringArray(result?.bakedRefs) ?? entry.liveDelivery.bakedRefs;
      }
      originalComplete(result);
      untrackSession(session.id);
      callbacks.onToolCompleted?.(toolId, extensionId, session.id);
    };

    if (entry.liveDelivery) {
      const originalCancel = session.cancel.bind(session);
      session.cancel = () => {
        entry.liveDelivery.cancelled = true;
        originalCancel();
      };
    }

    invalidateSnapshot();
  }

  function untrackSession(sessionId: string): void {
    cleanupSession(sessionId);
    const existed = sessions.delete(sessionId);
    if (existed) {
      invalidateSnapshot();
    }
  }

  function cleanupSession(sessionId: string): void {
    const disposers = sessionDisposers.get(sessionId);
    if (!disposers) return;
    for (const disposer of disposers) {
      try {
        disposer.dispose();
      } catch {
        // Ignore cleanup failures from extension-owned handles.
      }
    }
    sessionDisposers.delete(sessionId);
  }

  function addSessionDisposer(sessionId: string, disposer: DisposeHandle): void {
    const existing = sessionDisposers.get(sessionId) ?? [];
    existing.push(disposer);
    sessionDisposers.set(sessionId, existing);
  }

  function activateGenerationSessionLiveDelivery(
    entry: InternalSessionEntry,
    delivery: GenerationSessionLiveDelivery | undefined,
  ): void {
    if (!delivery) return;

    const sessionId = entry.session.id;
    const initialChannels = collectInitialChannels(entry.session, delivery);
    const state: InternalSessionLiveDeliveryState = {
      origin: isNonEmptyString(delivery.origin) ? delivery.origin : 'agent-tool',
      sourceId: delivery.sourceId,
      activeChannels: [...initialChannels],
      progress: entry.session.progress,
      cancelled: entry.session.cancelled,
      steeringDecision: delivery.steeringDecision,
      generationIndex: delivery.steeringDecision?.lineage?.generationIndex,
      steerHash: delivery.steeringDecision?.lineage?.steerHash,
      parentRefs: delivery.steeringDecision?.lineage?.parentRefs,
      finalRefs: delivery.finalRefs ?? entry.session.finalRefs,
      bakedRefs: delivery.bakedRefs ?? entry.session.bakedRefs,
      sampleCount: 0,
      canActivate: false,
      diagnostics: [],
    };
    entry.liveDelivery = state;

    const gate = evaluateGenerationSessionLiveDeliveryGate(delivery.steeringDecision);
    state.diagnostics.push(...gate.diagnostics);
    state.canActivate = gate.canActivate;
    for (const diagnostic of gate.diagnostics) {
      addDiagnostic(
        diagnostic.severity,
        diagnostic.code,
        diagnostic.message,
        entry.extensionId,
        undefined,
        diagnostic.detail,
      );
    }

    if (!gate.canActivate) {
      invalidateSnapshot();
      return;
    }

    const liveRegistry = config.liveDataRegistry;
    if (!liveRegistry) {
      const diagnostic: LiveSourceDiagnostic = {
        severity: 'error',
        code: 'live/generation-session-registry-missing',
        message: 'GenerationSession live delivery requires a live data registry.',
        detail: { sessionId, toolId: entry.toolId },
      };
      state.diagnostics.push(diagnostic);
      addDiagnostic(diagnostic.severity, diagnostic.code, diagnostic.message, entry.extensionId, undefined, diagnostic.detail);
      state.canActivate = false;
      invalidateSnapshot();
      return;
    }

    liveRegistry.applySteeringDecision(delivery.steeringDecision);
    const sourceId = delivery.sourceId ?? `generation-session:${sessionId}`;
    state.sourceId = sourceId;

    if (!liveRegistry.getSource(sourceId)) {
      liveRegistry.registerSourceWithOwner({
        id: sourceId,
        kind: 'generated',
        label: delivery.sourceLabel ?? `Generation session ${sessionId}`,
        metadata: {
          origin: state.origin,
          sessionId,
          toolId: entry.toolId,
          extensionId: entry.extensionId,
          generationIndex: state.generationIndex,
          steerHash: state.steerHash,
          parentRefs: state.parentRefs,
          finalRefs: state.finalRefs,
          bakedRefs: state.bakedRefs,
          delivery: delivery.metadata,
        },
      }, entry.extensionId);
    }

    const hostChannelId = liveRegistry.openChannel(sourceId, delivery.channelKind ?? 'video', {
      origin: state.origin,
      sessionId,
      toolId: entry.toolId,
      extensionId: entry.extensionId,
      sourceChannelId: initialChannels[0],
      steeringDecision: delivery.steeringDecision.kind,
      generationIndex: state.generationIndex,
      steerHash: state.steerHash,
      parentRefs: state.parentRefs,
    });
    state.activeChannels = [...new Set([...state.activeChannels, hostChannelId])];

    try {
      const progressHandle = entry.session.onProgress((progress) => {
        state.progress = progress;
        invalidateSnapshot();
        reportProgress(entry.toolId, entry.extensionId, progress, entry.session.progressLabel);
      });
      addSessionDisposer(sessionId, progressHandle);
    } catch (error) {
      recordLiveDeliveryDiagnostic(entry, state, 'live/generation-session-progress-subscribe-failed', error);
    }

    try {
      const sampleHandle = entry.session.onSample((sample) => {
        if (state.cancelled || entry.session.cancelled || entry.session.done) return;
        liveRegistry.pushSample(hostChannelId, {
          ...sample.frame,
          metadata: {
            ...sample.frame.metadata,
            origin: state.origin,
            sessionId,
            toolId: entry.toolId,
            extensionId: entry.extensionId,
            sourceChannelId: sample.channelId,
            sourceSequenceNumber: sample.sequenceNumber,
            generationIndex: state.generationIndex,
            steerHash: state.steerHash,
            parentRefs: state.parentRefs,
            finalRefs: state.finalRefs,
            bakedRefs: state.bakedRefs,
            steeringDecision: delivery.steeringDecision.kind,
          },
        });
        state.sampleCount += 1;
        if (!state.activeChannels.includes(sample.channelId)) {
          state.activeChannels = [...state.activeChannels, sample.channelId];
        }
        invalidateSnapshot();
      });
      addSessionDisposer(sessionId, sampleHandle);
    } catch (error) {
      recordLiveDeliveryDiagnostic(entry, state, 'live/generation-session-sample-subscribe-failed', error);
    }
  }

  function recordLiveDeliveryDiagnostic(
    entry: InternalSessionEntry,
    state: InternalSessionLiveDeliveryState,
    code: string,
    error: unknown,
  ): void {
    const message = error instanceof Error ? error.message : String(error);
    const diagnostic: LiveSourceDiagnostic = {
      severity: 'error',
      code,
      message,
      sourceId: state.sourceId,
      detail: { sessionId: entry.session.id, toolId: entry.toolId },
    };
    state.diagnostics.push(diagnostic);
    addDiagnostic(diagnostic.severity, diagnostic.code, diagnostic.message, entry.extensionId, undefined, diagnostic.detail);
  }

  function collectInitialChannels(
    session: GenerationSession,
    delivery: GenerationSessionLiveDelivery,
  ): LiveChannelDescriptor[] {
    const channels: LiveChannelDescriptor[] = [];
    for (const channel of delivery.activeChannels ?? []) {
      if (isNonEmptyString(channel)) channels.push(channel);
    }
    try {
      const channel = session.getSampleChannel();
      if (isNonEmptyString(channel)) channels.push(channel);
    } catch {
      // getSampleChannel is part of the typed contract, but legacy sessions may throw.
    }
    return [...new Set(channels)];
  }

  function readStringArray(value: unknown): readonly string[] | undefined {
    if (!Array.isArray(value)) return undefined;
    const strings = value.filter((item): item is string => typeof item === 'string' && item.length > 0);
    return strings.length > 0 ? strings : undefined;
  }

  function isNonEmptyString(value: unknown): value is string {
    return typeof value === 'string' && value.length > 0;
  }

  // ---- diagnostics & snapshot --------------------------------------------

  function subscribe(listener: () => void): DisposeHandle {
    listeners.add(listener);
    return {
      dispose(): void {
        listeners.delete(listener);
      },
    };
  }

  function getSnapshot(): AgentToolRegistrySnapshot {
    if (frozenSnapshot) return frozenSnapshot;

    const frozenTools: readonly AgentToolEntry[] = Object.freeze(
      [...tools.values()]
        .sort((a, b) => {
          const extCmp = a.extensionId.localeCompare(b.extensionId);
          if (extCmp !== 0) return extCmp;
          return a.toolId.localeCompare(b.toolId);
        })
        .map((t) =>
          Object.freeze({
            toolId: t.toolId,
            extensionId: t.extensionId,
            contributionId: t.contributionId,
            label: t.label,
            description: t.description,
            inputSchema: t.inputSchema,
            inputSchemaDiagnostics: t.inputSchemaDiagnostics,
            resultFamilies: t.resultFamilies,
            order: t.order,
            when: t.when,
            hasHandler: t.handler !== null,
          }),
        ),
    );

    const frozenSessions: readonly AgentToolSessionEntry[] = Object.freeze(
      [...sessions.values()].map((s) => Object.freeze({
        session: s.session,
        toolId: s.toolId,
        extensionId: s.extensionId,
        createdAt: s.createdAt,
        liveDelivery: s.liveDelivery
          ? Object.freeze({
              ...s.liveDelivery,
              activeChannels: Object.freeze([...s.liveDelivery.activeChannels]),
              parentRefs: s.liveDelivery.parentRefs ? Object.freeze([...s.liveDelivery.parentRefs]) : undefined,
              finalRefs: s.liveDelivery.finalRefs ? Object.freeze([...s.liveDelivery.finalRefs]) : undefined,
              bakedRefs: s.liveDelivery.bakedRefs ? Object.freeze([...s.liveDelivery.bakedRefs]) : undefined,
              diagnostics: Object.freeze([...s.liveDelivery.diagnostics]),
            })
          : undefined,
      })),
    );

    const frozenDiagnostics: readonly ExtensionDiagnostic[] = Object.freeze([...diagnostics]);

    const snapshot: AgentToolRegistrySnapshot = {
      tools: frozenTools,
      sessions: frozenSessions,
      diagnostics: frozenDiagnostics,
      getTool(toolId: string): AgentToolEntry | undefined {
        return frozenTools.find((t) => t.toolId === toolId);
      },
      getStatus(toolId: string): AgentToolRunStatus {
        const s = runStatuses.get(toolId);
        if (!s) {
          return { invocationCount: 0, lastRunAt: 0, lastRunOk: true, lastError: null };
        }
        return { ...s };
      },
      getSessions(toolId: string): readonly AgentToolSessionEntry[] {
        return frozenSessions.filter((s) => s.toolId === toolId);
      },
    };

    frozenSnapshot = snapshot;
    return snapshot;
  }

  // ---- lifecycle ---------------------------------------------------------

  function unregisterAll(extensionId: string): void {
    if (guardDisposed('unregisterAll')) return;

    // Remove all tools owned by this extension
    for (const [toolId, tool] of tools) {
      if (tool.extensionId === extensionId) {
        tools.delete(toolId);
        runStatuses.delete(toolId);
      }
    }

    // Cancel and remove all sessions owned by this extension
    cancelExtensionSessions(extensionId);

    invalidateSnapshot();
    notifyListeners();
  }

  function setCallbacks(cbs: AgentToolRegistryCallbacks): void {
    callbacks = cbs;
  }

  function dispose(): void {
    if (disposed) return;
    disposed = true;

    // Cancel all sessions
    for (const [, entry] of sessions) {
      try {
        entry.session.cancel();
      } catch {
        // Ignore
      }
    }
    for (const sessionId of sessions.keys()) {
      cleanupSession(sessionId);
    }
    sessions.clear();

    tools.clear();
    runStatuses.clear();
    diagnostics.length = 0;
    listeners.clear();
    callbacks = {};
    frozenSnapshot = null;
  }

  // ---- return public API ------------------------------------------------

  return {
    registerTool,
    ingestAgentToolContribution,
    invokeTool,
    reportProgress,
    cancelSessions,
    cancelExtensionSessions,
    trackSession,
    untrackSession,
    get diagnostics(): readonly ExtensionDiagnostic[] {
      return diagnostics;
    },
    subscribe,
    getSnapshot,
    unregisterAll,
    setCallbacks,
    dispose,
  };
}
