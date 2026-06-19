/**
 * AgentToolsPanel — Host-owned agent tool discovery and management UI.
 *
 * Subscribes to the provider-scoped AgentToolRegistry via useSyncExternalStore
 * and renders tool discovery, schema inputs via SchemaForm, lifecycle state
 * (invocation status, progress bars, sessions), cancel controls, diagnostics,
 * result summaries, and proposal creation from valid tool outputs.
 *
 * All mutations are proposal-backed: timeline-editing results are routed
 * through the host-owned AgentToolInvocationService which composes
 * ProposalRuntime.create(). Preview/accept/reject remain in ProposalPanel.
 *
 * Designed to sit alongside ProposalPanel and DiagnosticPanel in the
 * editor shell's toolbar/status-bar region.
 *
 * Accessibility:
 * - role="region" with aria-label="Agent tools panel"
 * - aria-live="polite" on the tool list for screen-reader updates
 * - Interactive elements have accessible labels
 *
 * @module AgentToolsPanel
 * @milestone M10
 */

import {
  useCallback,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  X,
  ChevronDown,
  ChevronRight,
  Play,
  Square,
  Loader2,
  Zap,
  Wrench,
  CheckCircle2,
  XCircle,
  Clock,
  Bug,
} from 'lucide-react';
import { SchemaForm } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import type { StandardSchema, StandardSchemaProperty } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import type {
  ToolResult,
  ToolResultDiagnostic,
  ToolMutationProposalResult,
  ToolGenerationSessionResult,
  ToolMaterialArtifactResult,
  ToolEnrichmentSearchResult,
  ToolExportResult,
  ToolProcessResult,
  ToolUISummaryResult,
  ExtensionDiagnostic,
  DisposeHandle,
  AgentToolInputSchema,
  AgentToolInputProperty,
} from '@reigh/editor-sdk';
import type {
  AgentToolRegistry,
  AgentToolEntry,
  AgentToolRunStatus,
} from '@/tools/video-editor/runtime/agentToolRegistry';
import type { AgentToolInvocationService } from '@/tools/video-editor/runtime/agentToolInvocationService';
import { isTimelineEditableResult } from '@/tools/video-editor/runtime/agentToolContracts';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentToolsPanelProps {
  /** Provider-scoped agent tool registry for snapshots and lifecycle state. */
  agentToolRegistry: AgentToolRegistry;
  /**
   * Optional invocation service for proposal-backed tool invocation.
   * When absent, the panel invokes tools through the registry directly
   * and displays results without routing through ProposalRuntime.
   */
  agentToolInvocationService?: AgentToolInvocationService;
  /** Called when the panel requests to be closed. */
  onClose?: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FAMILY_LABEL: Record<string, string> = {
  'mutation/proposal': 'Proposal',
  'generation/session': 'Generation',
  'material/artifact': 'Artifact',
  'enrichment/search': 'Search',
  'export': 'Export',
  'process': 'Process',
  'ui/summary': 'Summary',
};

const SEVERITY_ICON: Record<string, typeof AlertTriangle> = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const SEVERITY_COLOR: Record<string, string> = {
  error: 'text-red-400',
  warning: 'text-yellow-400',
  info: 'text-blue-400',
};

const SEVERITY_BG: Record<string, string> = {
  error: 'bg-red-500/10 border-red-500/20',
  warning: 'bg-yellow-500/10 border-yellow-500/20',
  info: 'bg-blue-500/10 border-blue-500/20',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(epochMs: number): string {
  if (epochMs === 0) return 'never';
  try {
    return new Date(epochMs).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return 'unknown';
  }
}

/** Extract displayable diagnostics from a tool result. */
function extractResultDiagnostics(
  result: ToolResult | null,
): readonly ToolResultDiagnostic[] {
  if (!result) return [];
  const r = result as unknown as Record<string, unknown>;
  if (Array.isArray(r.diagnostics)) {
    return r.diagnostics as readonly ToolResultDiagnostic[];
  }
  return [];
}

/** Get a short summary string for a tool result. */
function resultSummary(result: ToolResult | null): string | null {
  if (!result) return null;
  switch (result.family) {
    case 'mutation/proposal': {
      const mr = result as ToolMutationProposalResult;
      const patchCount = mr.patches?.length ?? 0;
      return patchCount === 1
        ? '1 proposed change'
        : `${patchCount} proposed changes`;
    }
    case 'generation/session': {
      const gs = result as ToolGenerationSessionResult;
      if (gs.session?.done) return 'Generation complete';
      if (gs.session?.cancelled) return 'Generation cancelled';
      return `Progress: ${gs.session?.progress ?? 0}%`;
    }
    case 'material/artifact': {
      const ma = result as ToolMaterialArtifactResult;
      const refCount = ma.refs?.length ?? 0;
      return `${refCount} artifact${refCount === 1 ? '' : 's'}`;
    }
    case 'enrichment/search': {
      const es = result as ToolEnrichmentSearchResult;
      const matchCount = es.matches?.length ?? 0;
      const sugCount = es.suggestions ? Object.keys(es.suggestions).length : 0;
      if (matchCount > 0 && sugCount > 0) return `${matchCount} matches, ${sugCount} suggestions`;
      if (matchCount > 0) return `${matchCount} matches`;
      if (sugCount > 0) return `${sugCount} suggestions`;
      return 'No results';
    }
    case 'export': {
      const ex = result as ToolExportResult;
      const findingCount = ex.findings?.length ?? 0;
      return `${findingCount} finding${findingCount === 1 ? '' : 's'}`;
    }
    case 'process': {
      return 'Process pending (M12)';
    }
    case 'ui/summary': {
      const us = result as ToolUISummaryResult;
      return us.summary.length > 120
        ? us.summary.slice(0, 120) + '\u2026'
        : us.summary;
    }
    default:
      return null;
  }
}

/**
 * Convert an AgentToolInputSchema to the StandardSchema shape
 * accepted by SchemaForm.
 *
 * AgentToolInputSchema is a StandardSchema-compatible subset.
 * We map each AgentToolInputProperty to a StandardSchemaProperty,
 * preserving type, title, description, default, enum, and nested properties.
 */
function agentToolInputSchemaToStandardSchema(
  schema: AgentToolInputSchema | undefined,
): StandardSchema | null {
  if (!schema || !schema.properties || Object.keys(schema.properties).length === 0) {
    return null;
  }

  function convertProperty(prop: AgentToolInputProperty): StandardSchemaProperty {
    const result: StandardSchemaProperty = {
      type: prop.type,
    };
    if (prop.title !== undefined) result.title = prop.title;
    if (prop.description !== undefined) result.description = prop.description;
    if (prop.default !== undefined) result.default = prop.default;
    if (prop.enum !== undefined) result.enum = [...prop.enum];
    return result;
  }

  const properties: Record<string, StandardSchemaProperty> = {};
  for (const [key, prop] of Object.entries(schema.properties)) {
    properties[key] = convertProperty(prop);
  }

  return {
    type: 'object',
    properties,
    required: schema.required ? [...schema.required] : undefined,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AgentToolsPanel({
  agentToolRegistry,
  agentToolInvocationService,
  onClose,
}: AgentToolsPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // ---- Subscribe to the registry via useSyncExternalStore --------------
  const snapshotRef = useRef(
    agentToolRegistry.getSnapshot(),
  );

  const subscribe = useCallback(
    (handler: () => void): (() => void) => {
      const handle: DisposeHandle = agentToolRegistry.subscribe(() => {
        snapshotRef.current = agentToolRegistry.getSnapshot();
        handler();
      });
      return () => handle.dispose();
    },
    [agentToolRegistry],
  );

  const snapshot = useSyncExternalStore(
    subscribe,
    () => snapshotRef.current,
  );

  const { tools, sessions, diagnostics } = snapshot;

  // ---- State ----------------------------------------------------------
  const [expandedToolIds, setExpandedToolIds] = useState<Set<string>>(new Set());
  const [invokeInputs, setInvokeInputs] = useState<Record<string, Record<string, unknown>>>({});
  const [invokingTools, setInvokingTools] = useState<Set<string>>(new Set());
  const [toolResults, setToolResults] = useState<Record<string, ToolResult | null>>({});
  const [toolErrors, setToolErrors] = useState<Record<string, string>>({});
  const [showRegistryDiags, setShowRegistryDiags] = useState(false);

  // ---- Derived data ----------------------------------------------------
  const toolsByExtension = useMemo(() => {
    const map = new Map<string, AgentToolEntry[]>();
    for (const tool of tools) {
      const list = map.get(tool.extensionId) ?? [];
      list.push(tool);
      map.set(tool.extensionId, list);
    }
    return map;
  }, [tools]);

  // ---- Handlers --------------------------------------------------------
  const toggleExpand = useCallback((toolId: string) => {
    setExpandedToolIds((prev) => {
      const next = new Set(prev);
      if (next.has(toolId)) {
        next.delete(toolId);
      } else {
        next.add(toolId);
      }
      return next;
    });
  }, []);

  const handleInputChange = useCallback(
    (toolId: string) => (name: string, value: unknown) => {
      setInvokeInputs((prev) => ({
        ...prev,
        [toolId]: { ...(prev[toolId] ?? {}), [name]: value },
      }));
    },
    [],
  );

  const handleInvoke = useCallback(
    async (tool: AgentToolEntry) => {
      const toolId = tool.toolId;
      setInvokingTools((prev) => new Set(prev).add(toolId));
      setToolErrors((prev) => {
        const next = { ...prev };
        delete next[toolId];
        return next;
      });

      try {
        const request = {
          toolId: tool.toolId,
          extensionId: tool.extensionId,
          contributionId: tool.contributionId,
          input: invokeInputs[toolId],
        };

        // Use the invocation service when available (proposal routing)
        // otherwise fall back to direct registry invocation.
        const result = agentToolInvocationService
          ? await agentToolInvocationService.invokeTool(request)
          : await agentToolRegistry.invokeTool(request);

        setToolResults((prev) => ({ ...prev, [toolId]: result }));
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setToolErrors((prev) => ({ ...prev, [toolId]: message }));
        setToolResults((prev) => ({ ...prev, [toolId]: null }));
      } finally {
        setInvokingTools((prev) => {
          const next = new Set(prev);
          next.delete(toolId);
          return next;
        });
      }
    },
    [agentToolRegistry, agentToolInvocationService, invokeInputs],
  );

  const handleCancel = useCallback(
    (toolId: string) => {
      agentToolRegistry.cancelSessions(toolId);
    },
    [agentToolRegistry],
  );

  // ---- Filter diagnostics for the panel ----------------------------------
  const registryDiagnostics = useMemo(
    () =>
      diagnostics.filter((d) =>
        d.code?.startsWith('agent-tool-registry/') ||
        d.code?.startsWith('agent-tool/'),
      ),
    [diagnostics],
  );

  // Count tools with handlers
  const handlerCount = tools.filter((t) => t.hasHandler).length;
  const totalTools = tools.length;

  // ---- Render ---------------------------------------------------------

  return (
    <div
      ref={panelRef}
      role="region"
      aria-label="Agent tools panel"
      tabIndex={-1}
      data-video-editor-agent-tools-panel="true"
      className="flex flex-col rounded-lg border border-white/10 bg-zinc-900 text-xs text-zinc-200 shadow-2xl"
      style={{ maxHeight: '65vh', minWidth: '360px', maxWidth: '600px' }}
    >
      {/* ---- Header ---------------------------------------------------- */}
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <div className="flex items-center gap-2">
          <Wrench className="h-3.5 w-3.5 text-zinc-400" aria-hidden="true" />
          <span className="font-medium text-zinc-300">Agent Tools</span>
          {totalTools > 0 && (
            <span className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
              {totalTools}
            </span>
          )}
          {handlerCount > 0 && (
            <span className="rounded-full bg-green-500/15 px-1.5 py-0.5 text-[10px] text-green-400">
              {handlerCount} ready
            </span>
          )}
          {totalTools - handlerCount > 0 && (
            <span className="rounded-full bg-yellow-500/15 px-1.5 py-0.5 text-[10px] text-yellow-400">
              {totalTools - handlerCount} no handler
            </span>
          )}
          {sessions.length > 0 && (
            <span className="rounded-full bg-blue-500/15 px-1.5 py-0.5 text-[10px] text-blue-400">
              {sessions.length} active
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {registryDiagnostics.length > 0 && (
            <button
              type="button"
              onClick={() => setShowRegistryDiags((v) => !v)}
              aria-pressed={showRegistryDiags}
              aria-label={`${showRegistryDiags ? 'Hide' : 'Show'} registry diagnostics (${registryDiagnostics.length})`}
              className={`rounded px-1.5 py-0.5 text-[10px] transition-colors ${
                showRegistryDiags
                  ? 'bg-yellow-500/10 text-yellow-400'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              <Bug className="mr-1 inline-block h-3 w-3" aria-hidden="true" />
              {registryDiagnostics.length}
            </button>
          )}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
              aria-label="Close agent tools panel"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ---- Registry diagnostics --------------------------------------- */}
      {showRegistryDiags && registryDiagnostics.length > 0 && (
        <div className="border-b border-white/5 max-h-40 overflow-y-auto">
          {registryDiagnostics.map((diag, idx) => {
            const SevIcon = SEVERITY_ICON[diag.severity] ?? Info;
            const sevColor = SEVERITY_COLOR[diag.severity] ?? 'text-zinc-400';
            return (
              <div
                key={`reg-diag-${idx}`}
                className={`flex items-start gap-2 border-b border-white/5 px-3 py-1.5 last:border-b-0 ${SEVERITY_BG[diag.severity] ?? ''}`}
              >
                <SevIcon className={`h-3 w-3 mt-0.5 shrink-0 ${sevColor}`} aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <div className="text-[10px] text-zinc-400">
                    {diag.extensionId && (
                      <span className="font-medium text-zinc-500">{diag.extensionId}</span>
                    )}
                    {diag.code && (
                      <span className="ml-1 text-zinc-600">[{diag.code}]</span>
                    )}
                  </div>
                  <div className={`text-[10px] ${sevColor}`}>{diag.message}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ---- Tool list -------------------------------------------------- */}
      <div
        className="overflow-y-auto"
        role="log"
        aria-live="polite"
        aria-label={`${totalTools} agent tool${totalTools === 1 ? '' : 's'}`}
        aria-relevant="additions removals"
      >
        {tools.length === 0 ? (
          <div className="flex flex-col items-center gap-1.5 px-4 py-8 text-center">
            <Wrench className="h-5 w-5 text-zinc-600" aria-hidden="true" />
            <p className="text-[11px] text-zinc-500">
              No agent tools registered.
            </p>
            <p className="text-[10px] text-zinc-600">
              Extensions contribute agent tools via &apos;agentTool&apos; manifest entries.
            </p>
          </div>
        ) : (
          <div className="flex flex-col">
            {[...toolsByExtension.entries()].map(([extensionId, extTools]) => (
              <div key={extensionId}>
                {/* Extension group header */}
                <div className="flex items-center gap-1.5 border-b border-white/5 bg-zinc-950 px-3 py-1.5">
                  <span className="text-[10px] font-medium uppercase tracking-[0.1em] text-zinc-500">
                    {extensionId}
                  </span>
                  <span className="rounded-full bg-zinc-800 px-1 py-0 text-[9px] text-zinc-600">
                    {extTools.length}
                  </span>
                </div>
                {extTools.map((tool) => {
                  const isExpanded = expandedToolIds.has(tool.toolId);
                  const isInvoking = invokingTools.has(tool.toolId);
                  const result = toolResults[tool.toolId];
                  const error = toolErrors[tool.toolId];
                  const status: AgentToolRunStatus = snapshot.getStatus(tool.toolId);
                  const toolSessions = snapshot.getSessions(tool.toolId);
                  const hasActiveSessions = toolSessions.length > 0;
                  const hasSchemaDiags = tool.inputSchemaDiagnostics.length > 0;
                  const canInvoke = tool.hasHandler;

                  // Convert input schema for SchemaForm rendering
                  const standardSchema = agentToolInputSchemaToStandardSchema(tool.inputSchema);

                  return (
                    <div
                      key={tool.toolId}
                      data-video-editor-agent-tool-item="true"
                      data-video-editor-agent-tool-id={tool.toolId}
                      data-video-editor-agent-tool-extension={tool.extensionId}
                      className="border-b border-white/5 last:border-b-0"
                    >
                      {/* Tool header */}
                      <button
                        type="button"
                        onClick={() => toggleExpand(tool.toolId)}
                        className="flex w-full items-center gap-1.5 px-3 py-2 text-left hover:bg-white/5 transition-colors"
                        aria-expanded={isExpanded}
                        aria-label={`Tool ${tool.label}: ${tool.description ?? 'no description'} — ${tool.hasHandler ? 'ready' : 'no handler'}${hasActiveSessions ? ' — active' : ''}`}
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-3 w-3 shrink-0 text-zinc-500" aria-hidden="true" />
                        ) : (
                          <ChevronRight className="h-3 w-3 shrink-0 text-zinc-500" aria-hidden="true" />
                        )}
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-zinc-300 truncate">
                              {tool.label}
                            </span>
                            <span className="shrink-0 text-[9px] text-zinc-600 font-mono">
                              {tool.toolId}
                            </span>
                            {/* Handler status */}
                            {tool.hasHandler ? (
                              <CheckCircle2
                                className="h-2.5 w-2.5 shrink-0 text-green-400"
                                aria-label="Handler registered"
                                data-video-editor-agent-tool-ready="true"
                              />
                            ) : (
                              <XCircle
                                className="h-2.5 w-2.5 shrink-0 text-yellow-500"
                                aria-label="No handler registered"
                                data-video-editor-agent-tool-no-handler="true"
                              />
                            )}
                            {/* Result families */}
                            {tool.resultFamilies.length > 0 && (
                              <span className="shrink-0 text-[9px] text-zinc-600">
                                {tool.resultFamilies.map((f) => FAMILY_LABEL[f] ?? f).join(', ')}
                              </span>
                            )}
                            {/* Active session indicator */}
                            {hasActiveSessions && (
                              <Loader2
                                className="h-2.5 w-2.5 shrink-0 animate-spin text-blue-400"
                                aria-label="Active session"
                              />
                            )}
                          </div>
                          {/* Description + status */}
                          <div className="flex items-center gap-2 mt-0.5">
                            {tool.description && (
                              <span className="text-[10px] text-zinc-500 truncate">
                                {tool.description}
                              </span>
                            )}
                            {status.invocationCount > 0 && (
                              <span className="shrink-0 text-[9px] text-zinc-600">
                                {status.invocationCount} run{status.invocationCount === 1 ? '' : 's'}
                                {status.lastRunOk ? '' : ' (last failed)'}
                              </span>
                            )}
                          </div>
                        </div>
                      </button>

                      {/* Expanded details */}
                      {isExpanded && (
                        <div className="border-t border-white/5 bg-zinc-950/50 px-3 py-2 space-y-2">
                          {/* Tool metadata */}
                          <div className="flex flex-wrap items-center gap-2 text-[10px] text-zinc-500">
                            <span>
                              Extension:{' '}
                              <span className="text-zinc-400">{tool.extensionId}</span>
                            </span>
                            <span>
                              Contribution:{' '}
                              <span className="text-zinc-400 font-mono">{tool.contributionId}</span>
                            </span>
                            <span>
                              Order: <span className="text-zinc-400">{tool.order}</span>
                            </span>
                            {tool.when && (
                              <span>
                                When:{' '}
                                <span className="text-zinc-400 font-mono">{tool.when}</span>
                              </span>
                            )}
                          </div>

                          {/* Last run status */}
                          {status.invocationCount > 0 && (
                            <div
                              className={`rounded border px-2 py-1 text-[10px] ${
                                status.lastRunOk
                                  ? 'border-green-500/20 bg-green-500/5 text-green-400'
                                  : 'border-red-500/20 bg-red-500/5 text-red-400'
                              }`}
                              data-video-editor-agent-tool-status="true"
                            >
                              <div className="flex items-center gap-1.5">
                                {status.lastRunOk ? (
                                  <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                                ) : (
                                  <AlertCircle className="h-3 w-3" aria-hidden="true" />
                                )}
                                <span>
                                  Last run: {formatTimestamp(status.lastRunAt)}
                                  {!status.lastRunOk && status.lastError && (
                                    <span className="ml-1">— {status.lastError}</span>
                                  )}
                                </span>
                              </div>
                            </div>
                          )}

                          {/* Error display */}
                          {error && (
                            <div
                              className="rounded border border-red-500/20 bg-red-500/5 px-2 py-1 text-[10px] text-red-400"
                              role="alert"
                              data-video-editor-agent-tool-error="true"
                            >
                              {error}
                            </div>
                          )}

                          {/* Schema diagnostics */}
                          {hasSchemaDiags && (
                            <div className="space-y-1">
                              <div className="flex items-center gap-1 text-[10px] text-yellow-400">
                                <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                                {tool.inputSchemaDiagnostics.length} schema diagnostic
                                {tool.inputSchemaDiagnostics.length === 1 ? '' : 's'}
                              </div>
                              {tool.inputSchemaDiagnostics.map((diag, idx) => {
                                const SevIcon = SEVERITY_ICON[diag.severity] ?? Info;
                                const sevColor =
                                  SEVERITY_COLOR[diag.severity] ?? 'text-zinc-400';
                                return (
                                  <div
                                    key={`schema-diag-${idx}`}
                                    className={`flex items-start gap-1.5 rounded border px-2 py-1 text-[10px] ${SEVERITY_BG[diag.severity] ?? ''}`}
                                  >
                                    <SevIcon
                                      className={`h-3 w-3 mt-0.5 shrink-0 ${sevColor}`}
                                      aria-hidden="true"
                                    />
                                    <div>
                                      <span className={sevColor}>{diag.message}</span>
                                      {diag.code && (
                                        <span className="ml-1 text-zinc-600">
                                          [{diag.code}]
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}

                          {/* Active sessions */}
                          {hasActiveSessions && (
                            <div className="space-y-1">
                              <div className="text-[10px] font-medium text-zinc-400">
                                Active Sessions ({toolSessions.length})
                              </div>
                              {toolSessions.map((sessionEntry) => {
                                const s = sessionEntry.session;
                                return (
                                  <div
                                    key={s.id}
                                    className="flex items-center gap-2 rounded border border-blue-500/20 bg-blue-500/5 px-2 py-1"
                                    data-video-editor-agent-tool-session="true"
                                  >
                                    <Loader2
                                      className="h-3 w-3 shrink-0 animate-spin text-blue-400"
                                      aria-hidden="true"
                                    />
                                    <div className="min-w-0 flex-1">
                                      <div className="text-[10px] text-zinc-300 truncate">
                                        {s.id}
                                      </div>
                                      {/* Progress bar */}
                                      <div className="mt-1 h-1 w-full rounded-full bg-zinc-800">
                                        <div
                                          className="h-1 rounded-full bg-blue-500 transition-all"
                                          style={{
                                            width: `${Math.min(100, Math.max(0, s.progress))}%`,
                                          }}
                                          role="progressbar"
                                          aria-valuenow={s.progress}
                                          aria-valuemin={0}
                                          aria-valuemax={100}
                                          aria-label={`Progress: ${s.progress}%`}
                                        />
                                      </div>
                                      <div className="mt-0.5 text-[9px] text-zinc-500">
                                        {s.progress}%
                                        {s.progressLabel
                                          ? ` — ${s.progressLabel}`
                                          : ''}
                                        {s.done && ' (complete)'}
                                        {s.cancelled && ' (cancelled)'}
                                      </div>
                                    </div>
                                    {!s.done && !s.cancelled && (
                                      <button
                                        type="button"
                                        onClick={() => s.cancel()}
                                        className="shrink-0 rounded p-0.5 text-zinc-500 hover:bg-red-500/10 hover:text-red-400 transition-colors"
                                        aria-label={`Cancel session ${s.id}`}
                                      >
                                        <Square className="h-3 w-3" />
                                      </button>
                                    )}
                                  </div>
                                );
                              })}
                              {toolSessions.length > 0 && (
                                <button
                                  type="button"
                                  onClick={() => handleCancel(tool.toolId)}
                                  className="text-[10px] text-red-400 hover:text-red-300 transition-colors"
                                >
                                  Cancel all sessions for this tool
                                </button>
                              )}
                            </div>
                          )}

                          {/* Result display */}
                          {result && (
                            <div
                              className="space-y-1 rounded border border-white/10 bg-zinc-900 px-2 py-1.5"
                              data-video-editor-agent-tool-result="true"
                              data-video-editor-agent-tool-result-family={
                                result.family
                              }
                            >
                              <div className="flex items-center gap-1.5">
                                <Zap
                                  className="h-3 w-3 text-zinc-400"
                                  aria-hidden="true"
                                />
                                <span className="text-[10px] font-medium text-zinc-400">
                                  {FAMILY_LABEL[result.family] ?? result.family}
                                </span>
                                {isTimelineEditableResult(result) && (
                                  <span className="rounded bg-purple-500/15 px-1 py-0 text-[9px] text-purple-400">
                                    Proposal-backed
                                  </span>
                                )}
                              </div>
                              <div className="text-[10px] text-zinc-300">
                                {resultSummary(result)}
                              </div>
                              {/* Rationale */}
                              {'rationale' in result &&
                                result.rationale &&
                                typeof (result as unknown as Record<string, unknown>).rationale === 'string' && (
                                  <div className="text-[10px] text-zinc-500 italic">
                                    {(String(
                                      (result as unknown as Record<string, unknown>).rationale,
                                    ).length > 200
                                      ? String(
                                          (result as unknown as Record<string, unknown>).rationale,
                                        ).slice(0, 200) + '\u2026'
                                      : String(
                                          (result as unknown as Record<string, unknown>).rationale,
                                        ))}
                                  </div>
                                )}
                              {/* Affected objects */}
                              {'affectedObjectIds' in result &&
                                Array.isArray(
                                  (result as unknown as Record<string, unknown>).affectedObjectIds,
                                ) && (
                                  <div className="text-[9px] text-zinc-600">
                                    Affected:{' '}
                                    {(
                                      (result as unknown as Record<string, unknown>)
                                        .affectedObjectIds as string[]
                                    ).join(', ')}
                                  </div>
                                )}
                              {/* Source refs */}
                              {'sourceRefs' in result &&
                                Array.isArray(
                                  (result as unknown as Record<string, unknown>).sourceRefs,
                                ) && (
                                  <div className="text-[9px] text-zinc-600">
                                    Ref map:{' '}
                                    {(
                                      (result as unknown as Record<string, unknown>)
                                        .sourceRefs as Array<Record<string, unknown>>
                                    )
                                      .map((r) => `${r.sourceId}→${r.outputId}`)
                                      .join(', ')}
                                  </div>
                                )}
                              {/* Result diagnostics */}
                              {extractResultDiagnostics(result).length > 0 && (
                                <div className="space-y-0.5 mt-1">
                                  {extractResultDiagnostics(result).map((diag, idx) => {
                                    const SevIcon =
                                      SEVERITY_ICON[diag.severity] ?? Info;
                                    const sevColor =
                                      SEVERITY_COLOR[diag.severity] ??
                                      'text-zinc-400';
                                    return (
                                      <div
                                        key={`result-diag-${idx}`}
                                        className={`flex items-start gap-1 rounded px-1.5 py-0.5 text-[9px] ${SEVERITY_BG[diag.severity] ?? ''}`}
                                      >
                                        <SevIcon
                                          className={`h-2.5 w-2.5 mt-0.5 shrink-0 ${sevColor}`}
                                          aria-hidden="true"
                                        />
                                        <span className={sevColor}>
                                          {diag.message}
                                        </span>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Input form + invoke */}
                          {canInvoke && (
                            <div className="space-y-2">
                              {/* SchemaForm when tool has a valid input schema with properties */}
                              {standardSchema && (
                                <div className="rounded border border-white/5 p-2">
                                  <SchemaForm
                                    schema={standardSchema}
                                    values={invokeInputs[tool.toolId] ?? {}}
                                    onChange={handleInputChange(tool.toolId)}
                                    disabled={isInvoking}
                                  />
                                </div>
                              )}
                              {/* Invoke button */}
                              <button
                                type="button"
                                onClick={() => handleInvoke(tool)}
                                disabled={isInvoking}
                                className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-[10px] font-medium transition-colors ${
                                  isInvoking
                                    ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                                    : 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30'
                                }`}
                                aria-label={`Invoke tool ${tool.label}`}
                                data-video-editor-agent-tool-invoke="true"
                              >
                                {isInvoking ? (
                                  <>
                                    <Loader2
                                      className="h-3 w-3 animate-spin"
                                      aria-hidden="true"
                                    />
                                    Running…
                                  </>
                                ) : (
                                  <>
                                    <Play className="h-3 w-3" aria-hidden="true" />
                                    Invoke
                                  </>
                                )}
                              </button>
                            </div>
                          )}

                          {/* Disabled state: no handler */}
                          {!canInvoke && (
                            <div className="text-[10px] text-yellow-500 italic">
                              <Clock
                                className="mr-1 inline-block h-3 w-3"
                                aria-hidden="true"
                              />
                              No handler registered — tool cannot be invoked.
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---- Footer ------------------------------------------------------ */}
      <div className="flex items-center justify-between border-t border-white/10 px-3 py-1.5">
        <span className="text-[9px] text-zinc-600">
          {totalTools} tool{totalTools === 1 ? '' : 's'} across{' '}
          {toolsByExtension.size} extension
          {toolsByExtension.size === 1 ? '' : 's'}
          {sessions.length > 0 &&
            ` · ${sessions.length} active session${sessions.length === 1 ? '' : 's'}`}
        </span>
        <span className="text-[9px] text-zinc-700">M10 · Proposal-backed</span>
      </div>
    </div>
  );
}
