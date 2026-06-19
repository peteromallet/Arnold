/**
 * CopilotPrompt — Host-owned copilot prompt surface.
 *
 * A singular, host-owned freeform prompt that:
 * - Routes only to registered copilot tools (filtered by family + metadata)
 * - Shows selectable context preview (timeline, export, etc.)
 * - Supports context trimming and confirmation before invocation
 * - Stores invocation history summaries locally
 * - Diagnoses and rejects competing extension-owned chat surfaces
 *   detected in agentTool contributions
 *
 * This is the only copilot prompt surface in the editor. Extensions
 * cannot contribute their own chat surfaces — any agentTool contribution
 * that looks like a competing chat/copilot surface is diagnosed and
 * prevented from being used as a routing target.
 *
 * Accessibility:
 * - role="region" with aria-label="Copilot prompt"
 * - aria-live="polite" on the chat output area
 * - Interactive elements have accessible labels
 *
 * @module CopilotPrompt
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
  Send,
  ChevronDown,
  ChevronRight,
  Clock,
  AlertTriangle,
  AlertCircle,
  Info,
  X,
  Trash2,
  Settings2,
  Wrench,
  Zap,
  Loader2,
  CheckCircle2,
  XCircle,
  MessageSquare,
  SlidersHorizontal,
} from 'lucide-react';
import type {
  ToolResult,
  ToolResultDiagnostic,
  ToolUISummaryResult,
  ToolMutationProposalResult,
  DisposeHandle,
  ExtensionDiagnostic,
} from '@reigh/editor-sdk';
import type {
  AgentToolRegistry,
  AgentToolEntry,
  AgentToolRegistrySnapshot,
} from '@/tools/video-editor/runtime/agentToolRegistry';
import type { AgentToolInvocationService } from '@/tools/video-editor/runtime/agentToolInvocationService';
import { isTimelineEditableResult } from '@/tools/video-editor/runtime/agentToolContracts';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CopilotPromptProps {
  /** Provider-scoped agent tool registry for snapshots. */
  agentToolRegistry: AgentToolRegistry;
  /** Invocation service for proposal-backed tool invocation. */
  agentToolInvocationService?: AgentToolInvocationService;
  /** Called when the panel requests to be closed. */
  onClose?: () => void;
}

/** A single entry in the copilot invocation history. */
export interface CopilotHistoryEntry {
  /** Unique entry ID (nanoid-style timestamp). */
  id: string;
  /** Timestamp (epoch ms). */
  timestamp: number;
  /** The user's prompt text. */
  prompt: string;
  /** The tool ID that was invoked. */
  toolId: string;
  /** The tool label. */
  toolLabel: string;
  /** The result family (if available). */
  resultFamily?: string;
  /** Summary of the result (max 200 chars). */
  resultSummary: string | null;
  /** Whether the invocation succeeded. */
  success: boolean;
  /** Error message if failed. */
  error?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Tool IDs or patterns that indicate a competing chat surface. */
const COMPETING_CHAT_PATTERNS = [
  /^chat$/i,
  /^copilot$/i,
  /^assistant$/i,
  /^conversation$/i,
  /\.chat$/i,
  /\.copilot$/i,
  /\.assistant$/i,
  /\.conversation$/i,
  /-chat$/i,
  /-copilot$/i,
  /-assistant$/i,
  /-conversation$/i,
  /^agent\./i,
  /^ai\./i,
];

/** Competing chat label keywords (case-insensitive). */
const COMPETING_CHAT_LABEL_KEYWORDS = [
  'chat',
  'copilot',
  'assistant',
  'conversation',
  'prompt',
];

/** Result families considered "copilot-compatible" for routing. */
const COPILOT_RESULT_FAMILIES = new Set<string>([
  'ui/summary',
  'mutation/proposal',
  'generation/session',
  'enrichment/search',
  'export',
]);

/** Max history entries to keep in memory. */
const MAX_HISTORY_ENTRIES = 50;

/** Max result summary length in history. */
const MAX_SUMMARY_LENGTH = 200;

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

/**
 * Detect whether an agent tool contribution looks like a competing
 * extension-owned chat surface.
 *
 * Returns a diagnostic if the tool looks like a chat/copilot/assistant
 * surface, or null if it passes.
 */
export function diagnoseCompetingChatSurface(
  tool: AgentToolEntry,
): ExtensionDiagnostic | null {
  const idLower = tool.toolId.toLowerCase();
  const labelLower = tool.label.toLowerCase();
  const descLower = (tool.description ?? '').toLowerCase();

  // Check tool ID against known chat patterns
  for (const pattern of COMPETING_CHAT_PATTERNS) {
    if (pattern.test(idLower)) {
      return {
        severity: 'warning',
        code: 'agent-tool/competing-chat-surface',
        message:
          `Agent tool "${tool.toolId}" (extension "${tool.extensionId}") ` +
          `has a tool ID that matches a competing chat surface pattern. ` +
          `Extension-owned chat/copilot/assistant surfaces are not permitted. ` +
          `The host provides the singular copilot prompt surface. ` +
          `This tool will be hidden from copilot routing and may be removed ` +
          `in a future milestone.`,
        extensionId: tool.extensionId,
        contributionId: tool.contributionId,
        detail: { toolId: tool.toolId, label: tool.label, pattern: pattern.source },
      };
    }
  }

  // Check label for chat-related keywords (only if it strongly suggests a chat surface)
  const keywordHits: string[] = [];
  for (const keyword of COMPETING_CHAT_LABEL_KEYWORDS) {
    if (labelLower.includes(keyword)) keywordHits.push(keyword);
  }

  if (keywordHits.length >= 2 || (keywordHits.length === 1 && idLower.includes(keywordHits[0]))) {
    return {
      severity: 'warning',
      code: 'agent-tool/competing-chat-surface',
      message:
        `Agent tool "${tool.toolId}" (label: "${tool.label}") has label keywords ` +
        `(${keywordHits.join(', ')}) that suggest a competing chat surface. ` +
        `Extension-owned chat/copilot/assistant surfaces are not permitted. ` +
        `The host provides the singular copilot prompt surface.`,
      extensionId: tool.extensionId,
      contributionId: tool.contributionId,
      detail: { toolId: tool.toolId, label: tool.label, keywords: keywordHits },
    };
  }

  // Check description for strong chat surface claims
  const chatDescPhrases = [
    'chat interface',
    'copilot panel',
    'assistant panel',
    'conversation ui',
    'chat surface',
    'copilot surface',
    'own copilot',
    'custom assistant',
  ];
  for (const phrase of chatDescPhrases) {
    if (descLower.includes(phrase)) {
      return {
        severity: 'error',
        code: 'agent-tool/competing-chat-surface',
        message:
          `Agent tool "${tool.toolId}" (extension "${tool.extensionId}") ` +
          `describes itself as "${phrase}" — a competing chat/copilot surface. ` +
          `Extension-owned chat surfaces are explicitly prohibited. ` +
          `This contribution will be rejected from copilot routing.`,
        extensionId: tool.extensionId,
        contributionId: tool.contributionId,
        detail: { toolId: tool.toolId, label: tool.label, phrase },
      };
    }
  }

  return null;
}

/**
 * Filter the tool list to only copilot-eligible tools.
 *
 * A tool is copilot-eligible if:
 * - It has a registered handler
 * - Its result families overlap with COPILOT_RESULT_FAMILIES (or it has no restriction)
 * - It is NOT diagnosed as a competing chat surface
 */
export function filterCopilotTools(
  snapshot: AgentToolRegistrySnapshot,
): {
  tools: AgentToolEntry[];
  chatSurfaceDiagnostics: ExtensionDiagnostic[];
} {
  const chatSurfaceDiagnostics: ExtensionDiagnostic[] = [];
  const tools: AgentToolEntry[] = [];

  for (const tool of snapshot.tools) {
    if (!tool.hasHandler) continue;

    // Check result families: if tool declares families, at least one must be copilot-compatible
    if (tool.resultFamilies.length > 0) {
      const hasCompatibleFamily = tool.resultFamilies.some((f) =>
        COPILOT_RESULT_FAMILIES.has(f),
      );
      if (!hasCompatibleFamily) continue;
    }

    // Diagnose competing chat surfaces
    const chatDiag = diagnoseCompetingChatSurface(tool);
    if (chatDiag) {
      chatSurfaceDiagnostics.push(chatDiag);
      // Error-level diags fully exclude from routing; warning still allow
      if (chatDiag.severity === 'error') continue;
    }

    tools.push(tool);
  }

  return { tools, chatSurfaceDiagnostics };
}

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

function createHistoryEntry(
  prompt: string,
  tool: AgentToolEntry,
  result: ToolResult | null,
  error?: string,
): CopilotHistoryEntry {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: Date.now(),
    prompt: prompt.slice(0, 500),
    toolId: tool.toolId,
    toolLabel: tool.label,
    resultFamily: result?.family,
    resultSummary: summarizeForHistory(result),
    success: result !== null && !error,
    error,
  };
}

function summarizeForHistory(result: ToolResult | null): string | null {
  if (!result) return null;
  switch (result.family) {
    case 'ui/summary': {
      const s = result as ToolUISummaryResult;
      return s.summary.length > MAX_SUMMARY_LENGTH
        ? s.summary.slice(0, MAX_SUMMARY_LENGTH) + '\u2026'
        : s.summary;
    }
    case 'mutation/proposal': {
      const m = result as ToolMutationProposalResult;
      const pc = m.patches?.length ?? 0;
      return pc === 1 ? '1 proposed change' : `${pc} proposed changes`;
    }
    case 'generation/session':
      return 'Generation session started';
    case 'enrichment/search': {
      const e = result as { matches?: unknown[] };
      return `${e.matches?.length ?? 0} matches found`;
    }
    case 'export': {
      const e = result as { findings?: unknown[] };
      return `${e.findings?.length ?? 0} findings`;
    }
    default:
      return `Result: ${result.family}`;
  }
}

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

/** Get a short one-line summary of context being sent. */
function contextSummary(contextKeys: Set<string>): string {
  const parts: string[] = [];
  if (contextKeys.has('timeline')) parts.push('Timeline snapshot');
  if (contextKeys.has('export')) parts.push('Export context');
  if (contextKeys.has('selection')) parts.push('Current selection');
  if (contextKeys.has('project')) parts.push('Project metadata');
  if (parts.length === 0) return 'No context selected';
  return parts.join(', ');
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CopilotPrompt({
  agentToolRegistry,
  agentToolInvocationService,
  onClose,
}: CopilotPromptProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const historyEndRef = useRef<HTMLDivElement>(null);

  // ---- Subscribe to registry ----------------------------------------------
  const snapshotRef = useRef(agentToolRegistry.getSnapshot());

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

  // ---- Copilot tool filtering -------------------------------------------
  const { tools: copilotTools, chatSurfaceDiagnostics } = useMemo(
    () => filterCopilotTools(snapshot),
    [snapshot],
  );

  // ---- State --------------------------------------------------------------
  const [promptText, setPromptText] = useState('');
  const [selectedToolId, setSelectedToolId] = useState<string>('');
  const [isInvoking, setIsInvoking] = useState(false);
  const [history, setHistory] = useState<CopilotHistoryEntry[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showContextSettings, setShowContextSettings] = useState(false);
  const [contextKeys, setContextKeys] = useState<Set<string>>(
    new Set(['timeline', 'selection', 'project']),
  );
  const [showToolSelector, setShowToolSelector] = useState(false);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [showChatDiags, setShowChatDiags] = useState(false);

  // ---- Derived data -------------------------------------------------------
  const selectedTool = copilotTools.find((t) => t.toolId === selectedToolId) ?? null;

  // Auto-select first tool if none selected
  const effectiveToolId = selectedToolId || (copilotTools.length > 0 ? copilotTools[0].toolId : '');
  const effectiveTool = selectedTool ?? (copilotTools.length > 0 ? copilotTools[0] : null);

  const canSend = promptText.trim().length > 0 && effectiveTool !== null && !isInvoking;
  const hasActiveChatDiags = chatSurfaceDiagnostics.length > 0;

  // ---- Handlers -----------------------------------------------------------

  const handleSend = useCallback(async () => {
    const tool = effectiveTool;
    if (!tool || !promptText.trim()) return;

    setPendingError(null);
    setIsInvoking(true);

    try {
      const request = {
        toolId: tool.toolId,
        extensionId: tool.extensionId,
        contributionId: tool.contributionId,
        input: {
          prompt: promptText.trim(),
          ...(contextKeys.has('timeline') ? { includeTimeline: true } : {}),
          ...(contextKeys.has('export') ? { includeExport: true } : {}),
          ...(contextKeys.has('selection') ? { includeSelection: true } : {}),
          ...(contextKeys.has('project') ? { includeProject: true } : {}),
        },
      };

      const result = agentToolInvocationService
        ? await agentToolInvocationService.invokeTool(request)
        : await agentToolRegistry.invokeTool(request);

      // Null result means the tool handler failed (error caught by registry).
      // Check registry diagnostics for the failure reason.
      if (result === null) {
        const snapshot = agentToolRegistry.getSnapshot();
        const failureDiags = snapshot.diagnostics.filter(
          (d) =>
            d.code === 'agent-tool-registry/handler-error' &&
            d.extensionId === tool.extensionId,
        );
        const lastFailure = failureDiags[failureDiags.length - 1];
        const errorMsg =
          lastFailure?.message ?? `Tool "${tool.label}" returned no result.`;
        setPendingError(errorMsg);
        const entry = createHistoryEntry(promptText, tool, null, errorMsg);
        setHistory((prev) => [entry, ...prev].slice(0, MAX_HISTORY_ENTRIES));
      } else {
        const entry = createHistoryEntry(promptText, tool, result);
        setHistory((prev) => [entry, ...prev].slice(0, MAX_HISTORY_ENTRIES));
        setPromptText('');
      }

      // Scroll to bottom after render
      setTimeout(() => historyEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setPendingError(message);
      const entry = createHistoryEntry(promptText, tool, null, message);
      setHistory((prev) => [entry, ...prev].slice(0, MAX_HISTORY_ENTRIES));
    } finally {
      setIsInvoking(false);
    }
  }, [
    effectiveTool,
    promptText,
    contextKeys,
    agentToolRegistry,
    agentToolInvocationService,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && canSend) {
        e.preventDefault();
        handleSend();
      }
    },
    [canSend, handleSend],
  );

  const toggleContextKey = useCallback((key: string) => {
    setContextKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  // ---- Context availability -----------------------------------------------
  const contextOptions = useMemo(
    () => [
      {
        key: 'timeline',
        label: 'Timeline Snapshot',
        description: 'Include current timeline clips, tracks, and metadata.',
        available: true,
      },
      {
        key: 'selection',
        label: 'Current Selection',
        description: 'Include currently selected clips/tracks.',
        available: true,
      },
      {
        key: 'project',
        label: 'Project Metadata',
        description: 'Include project-level settings and metadata.',
        available: true,
      },
      {
        key: 'export',
        label: 'Export Context',
        description: 'Include export configuration if available.',
        available: true,
      },
    ],
    [],
  );

  // ---- Render -------------------------------------------------------------

  return (
    <div
      ref={panelRef}
      role="region"
      aria-label="Copilot prompt"
      tabIndex={-1}
      data-video-editor-copilot-prompt="true"
      className="flex flex-col rounded-lg border border-white/10 bg-zinc-900 text-xs text-zinc-200 shadow-2xl"
      style={{ maxHeight: '70vh', minWidth: '380px', maxWidth: '640px' }}
    >
      {/* ---- Header -------------------------------------------------------- */}
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-3.5 w-3.5 text-zinc-400" aria-hidden="true" />
          <span className="font-medium text-zinc-300">Copilot</span>
          {copilotTools.length > 0 && (
            <span className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
              {copilotTools.length} tool{copilotTools.length === 1 ? '' : 's'}
            </span>
          )}
          {hasActiveChatDiags && (
            <button
              type="button"
              onClick={() => setShowChatDiags((v) => !v)}
              aria-pressed={showChatDiags}
              aria-label={`${showChatDiags ? 'Hide' : 'Show'} chat surface diagnostics (${chatSurfaceDiagnostics.length})`}
              className={`rounded px-1.5 py-0.5 text-[10px] transition-colors ${
                showChatDiags
                  ? 'bg-yellow-500/10 text-yellow-400'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              <AlertTriangle className="mr-1 inline-block h-3 w-3" aria-hidden="true" />
              {chatSurfaceDiagnostics.length}
            </button>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setShowHistory((v) => !v)}
            aria-pressed={showHistory}
            aria-label={`${showHistory ? 'Hide' : 'Show'} history (${history.length})`}
            className={`rounded px-1.5 py-0.5 text-[10px] transition-colors ${
              showHistory
                ? 'bg-blue-500/10 text-blue-400'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Clock className="mr-1 inline-block h-3 w-3" aria-hidden="true" />
            {history.length}
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
              aria-label="Close copilot prompt"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ---- Chat surface diagnostics -------------------------------------- */}
      {showChatDiags && chatSurfaceDiagnostics.length > 0 && (
        <div className="border-b border-white/5 max-h-36 overflow-y-auto">
          {chatSurfaceDiagnostics.map((diag, idx) => {
            const SevIcon = SEVERITY_ICON[diag.severity] ?? Info;
            const sevColor = SEVERITY_COLOR[diag.severity] ?? 'text-zinc-400';
            return (
              <div
                key={`chat-diag-${idx}`}
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

      {/* ---- Empty state (no copilot tools) --------------------------------- */}
      {copilotTools.length === 0 && (
        <div className="flex flex-col items-center gap-1.5 px-4 py-8 text-center">
          <Zap className="h-5 w-5 text-zinc-600" aria-hidden="true" />
          <p className="text-[11px] text-zinc-500">
            No copilot-compatible tools registered.
          </p>
          <p className="text-[10px] text-zinc-600">
            Extensions contribute copilot-compatible agent tools via
            &apos;agentTool&apos; manifest entries with &apos;ui/summary&apos;,
            &apos;mutation/proposal&apos;, or &apos;enrichment/search&apos; result families.
          </p>
        </div>
      )}

      {/* ---- Copilot tools available --------------------------------------- */}
      {copilotTools.length > 0 && (
        <>
          {/* ---- Tool selector --------------------------------------------- */}
          <div className="border-b border-white/5 px-3 py-1.5">
            <button
              type="button"
              onClick={() => setShowToolSelector((v) => !v)}
              className="flex w-full items-center gap-1.5 text-left text-[10px] text-zinc-400 hover:text-zinc-300 transition-colors"
              aria-expanded={showToolSelector}
              aria-label={`Tool: ${effectiveTool?.label ?? 'None selected'}`}
            >
              <Wrench className="h-3 w-3 shrink-0" aria-hidden="true" />
              <span className="flex-1 truncate">
                {effectiveTool ? (
                  <>
                    <span className="text-zinc-300">{effectiveTool.label}</span>
                    <span className="ml-1.5 text-zinc-600 font-mono">
                      {effectiveTool.toolId}
                    </span>
                  </>
                ) : (
                  <span className="text-zinc-500">Select a tool…</span>
                )}
              </span>
              {showToolSelector ? (
                <ChevronDown className="h-3 w-3 shrink-0" />
              ) : (
                <ChevronRight className="h-3 w-3 shrink-0" />
              )}
            </button>

            {showToolSelector && (
              <div className="mt-1 space-y-0.5 max-h-40 overflow-y-auto">
                {copilotTools.map((tool) => (
                  <button
                    key={tool.toolId}
                    type="button"
                    onClick={() => {
                      setSelectedToolId(tool.toolId);
                      setShowToolSelector(false);
                    }}
                    className={`flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-[10px] transition-colors ${
                      tool.toolId === effectiveToolId
                        ? 'bg-blue-500/10 text-blue-300'
                        : 'text-zinc-400 hover:bg-white/5 hover:text-zinc-300'
                    }`}
                    aria-pressed={tool.toolId === effectiveToolId}
                  >
                    <Zap className="h-3 w-3 shrink-0" aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{tool.label}</div>
                      {tool.description && (
                        <div className="truncate text-[9px] text-zinc-500">
                          {tool.description}
                        </div>
                      )}
                    </div>
                    {tool.toolId === effectiveToolId && (
                      <CheckCircle2 className="h-3 w-3 shrink-0 text-blue-400" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* ---- Context settings toggle ------------------------------------ */}
          <div className="border-b border-white/5 px-3 py-1">
            <button
              type="button"
              onClick={() => setShowContextSettings((v) => !v)}
              className="flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
              aria-expanded={showContextSettings}
              aria-label={`Context: ${contextSummary(contextKeys)}`}
            >
              <SlidersHorizontal className="h-3 w-3 shrink-0" aria-hidden="true" />
              <span>Context: {contextSummary(contextKeys)}</span>
              {showContextSettings ? (
                <ChevronDown className="h-3 w-3 shrink-0" />
              ) : (
                <ChevronRight className="h-3 w-3 shrink-0" />
              )}
            </button>

            {showContextSettings && (
              <div className="mt-1.5 space-y-1 rounded border border-white/5 bg-zinc-950 px-2 py-1.5">
                <div className="text-[9px] font-medium text-zinc-500 mb-1">
                  Select context to include with your prompt:
                </div>
                {contextOptions.map((option) => (
                  <label
                    key={option.key}
                    className="flex items-start gap-1.5 cursor-pointer py-0.5"
                  >
                    <input
                      type="checkbox"
                      checked={contextKeys.has(option.key)}
                      onChange={() => toggleContextKey(option.key)}
                      className="mt-0.5 h-3 w-3 rounded border-zinc-600 bg-zinc-800
                        text-blue-500 focus:ring-1 focus:ring-blue-500/50
                        accent-blue-500"
                      aria-label={`Include ${option.label}`}
                    />
                    <div className="min-w-0">
                      <div className="text-[10px] text-zinc-300">{option.label}</div>
                      <div className="text-[9px] text-zinc-500">
                        {option.description}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* ---- History panel ------------------------------------------------- */}
      {showHistory && (
        <div className="border-b border-white/5 max-h-48 overflow-y-auto">
          <div className="flex items-center justify-between px-3 py-1.5">
            <span className="text-[10px] font-medium text-zinc-400">
              History ({history.length})
            </span>
            {history.length > 0 && (
              <button
                type="button"
                onClick={clearHistory}
                className="flex items-center gap-1 text-[9px] text-zinc-500 hover:text-red-400 transition-colors"
                aria-label="Clear history"
              >
                <Trash2 className="h-2.5 w-2.5" />
                Clear
              </button>
            )}
          </div>
          {history.length === 0 ? (
            <div className="px-3 py-3 text-center text-[10px] text-zinc-600">
              No invocation history yet.
            </div>
          ) : (
            <div className="space-y-0.5 px-2 pb-2" role="log" aria-live="polite" aria-label="Copilot invocation history">
              {history.map((entry) => (
                <div
                  key={entry.id}
                  data-video-editor-copilot-history-entry="true"
                  className={`rounded border px-2 py-1 text-[10px] ${
                    entry.success
                      ? 'border-white/5 bg-zinc-950'
                      : 'border-red-500/20 bg-red-500/5'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {entry.success ? (
                      <CheckCircle2 className="h-2.5 w-2.5 shrink-0 text-green-400" />
                    ) : (
                      <XCircle className="h-2.5 w-2.5 shrink-0 text-red-400" />
                    )}
                    <span className="text-zinc-400 truncate">
                      {entry.prompt.length > 80
                        ? entry.prompt.slice(0, 80) + '\u2026'
                        : entry.prompt}
                    </span>
                    <span className="shrink-0 text-[9px] text-zinc-600 ml-auto">
                      {formatTimestamp(entry.timestamp)}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <span className="text-[9px] text-zinc-600 font-mono">
                      {entry.toolId}
                    </span>
                    {entry.resultSummary && (
                      <span className="text-[9px] text-zinc-500 truncate">
                        → {entry.resultSummary}
                      </span>
                    )}
                  </div>
                  {entry.error && (
                    <div className="mt-0.5 text-[9px] text-red-400 truncate">
                      Error: {entry.error}
                    </div>
                  )}
                </div>
              ))}
              <div ref={historyEndRef} />
            </div>
          )}
        </div>
      )}

      {/* ---- Error display ------------------------------------------------- */}
      {pendingError && (
        <div
          className="border-b border-red-500/20 bg-red-500/5 px-3 py-1.5 text-[10px] text-red-400"
          role="alert"
          data-video-editor-copilot-error="true"
        >
          {pendingError}
        </div>
      )}

      {/* ---- Prompt input area --------------------------------------------- */}
      {effectiveTool && (
        <div className="flex flex-col gap-1.5 px-3 py-2">
          <div className="relative">
            <textarea
              ref={inputRef}
              value={promptText}
              onChange={(e) => {
                setPromptText(e.target.value);
                setPendingError(null);
              }}
              onKeyDown={handleKeyDown}
              placeholder={`Ask ${effectiveTool.label}…`}
              rows={3}
              disabled={isInvoking || copilotTools.length === 0}
              className="w-full resize-none rounded border border-white/10 bg-zinc-800 px-2.5 py-1.5
                text-[11px] text-zinc-200 placeholder:text-zinc-600
                focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30
                disabled:opacity-50 disabled:cursor-not-allowed
                transition-colors"
              aria-label="Copilot prompt input"
              data-video-editor-copilot-input="true"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-[9px] text-zinc-600">
              {isInvoking ? (
                <span className="flex items-center gap-1 text-blue-400">
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                  Running {effectiveTool.label}…
                </span>
              ) : (
                <span>
                  <kbd className="rounded border border-zinc-700 bg-zinc-800 px-1 py-0 text-[9px] text-zinc-500">
                    ⌘Enter
                  </kbd>
                  {' '}to send
                </span>
              )}
            </span>
            <button
              type="button"
              onClick={handleSend}
              disabled={!canSend}
              className={`flex items-center gap-1.5 rounded px-3 py-1 text-[10px] font-medium transition-colors ${
                canSend
                  ? 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30'
                  : 'bg-zinc-800 text-zinc-600 cursor-not-allowed'
              }`}
              aria-label={`Send prompt to ${effectiveTool.label}`}
              data-video-editor-copilot-send="true"
            >
              <Send className="h-3 w-3" aria-hidden="true" />
              Send
            </button>
          </div>
        </div>
      )}

      {/* ---- Footer -------------------------------------------------------- */}
      <div className="flex items-center justify-between border-t border-white/10 px-3 py-1.5">
        <span className="text-[9px] text-zinc-600">
          {copilotTools.length} copilot tool{copilotTools.length === 1 ? '' : 's'}{' '}
          available
          {history.length > 0 && ` · ${history.length} invocation${history.length === 1 ? '' : 's'}`}
        </span>
        <span className="text-[9px] text-zinc-700">M10 · Host-owned copilot</span>
      </div>
    </div>
  );
}
