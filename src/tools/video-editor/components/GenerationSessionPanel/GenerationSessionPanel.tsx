/**
 * GenerationSessionPanel — focused UI for long-running generation sessions.
 *
 * Renders progress, cancellation, live-delivery activation, steering lineage,
 * diagnostics, and optional steerable parameter controls for sessions created
 * by AgentToolRegistry.
 */

import { AlertCircle, AlertTriangle, GitFork, Info, Link2, Loader2, Square } from 'lucide-react';
import type { ReactElement } from 'react';
import { SchemaForm } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import type { StandardSchema } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import type { AgentToolSessionEntry } from '@/tools/video-editor/runtime/agentToolRegistry';
import type { DiagnosticSeverity } from '@reigh/editor-sdk';

export interface GenerationSessionPanelProps {
  sessions: readonly AgentToolSessionEntry[];
  steeringSchema?: StandardSchema | null;
  steeringValues?: Record<string, unknown>;
  onSteeringChange?: (name: string, value: unknown) => void;
  steeringDisabled?: boolean;
  onCancelAll?: () => void;
}

interface SessionDiagnostic {
  severity: DiagnosticSeverity;
  code?: string;
  message: string;
  detail?: Record<string, unknown>;
}

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

const DECISION_LABEL: Record<string, string> = {
  supersede: 'Supersede',
  fork: 'Fork',
  reject: 'Reject',
};

const DECISION_CLASS: Record<string, string> = {
  supersede: 'bg-green-500/15 text-green-400',
  fork: 'bg-purple-500/15 text-purple-400',
  reject: 'bg-red-500/15 text-red-400',
};

function originLabel(origin: string | undefined): string {
  if (!origin) return 'agent';
  if (origin === 'agent-tool') return 'agent';
  if (origin === 'live') return 'live';
  if (origin === 'process') return 'process';
  return origin;
}

function diagnosticDetailText(diagnostic: SessionDiagnostic): string | null {
  const detail = diagnostic.detail;
  if (!detail || typeof detail !== 'object') return null;
  const fields = Object.entries(detail)
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`);
  return fields.length > 0 ? fields.join(' · ') : null;
}

function refList(label: string, refs: readonly string[] | undefined): ReactElement | null {
  if (!refs || refs.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1 text-[9px] text-zinc-500">
      <Link2 className="h-2.5 w-2.5 text-zinc-600" aria-hidden="true" />
      <span>{label}:</span>
      {refs.map((ref) => (
        <a
          key={`${label}:${ref}`}
          href={`#${encodeURIComponent(ref)}`}
          className="rounded bg-zinc-800 px-1 py-0 text-zinc-300 hover:bg-zinc-700"
          data-video-editor-generation-session-ref={label}
        >
          {ref}
        </a>
      ))}
    </div>
  );
}

export function GenerationSessionPanel({
  sessions,
  steeringSchema,
  steeringValues = {},
  onSteeringChange,
  steeringDisabled = false,
  onCancelAll,
}: GenerationSessionPanelProps) {
  if (sessions.length === 0) {
    return (
      <div
        className="rounded border border-white/5 bg-zinc-900/60 px-2 py-2 text-[10px] text-zinc-500"
        data-video-editor-generation-session-empty="true"
      >
        No generation sessions.
      </div>
    );
  }

  return (
    <div className="space-y-2" data-video-editor-generation-session-panel="true">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[10px] font-medium text-zinc-400">
          Active Sessions ({sessions.length})
        </div>
        {onCancelAll && sessions.length > 0 && (
          <button
            type="button"
            onClick={onCancelAll}
            className="text-[10px] text-red-400 hover:text-red-300 transition-colors"
          >
            Cancel all sessions for this tool
          </button>
        )}
      </div>

      {steeringSchema && onSteeringChange && (
        <div
          className="rounded border border-white/5 p-2"
          data-video-editor-generation-session-steering="true"
        >
          <div className="mb-1 text-[10px] font-medium text-zinc-400">Steering</div>
          <SchemaForm
            schema={steeringSchema}
            values={steeringValues}
            onChange={onSteeringChange}
            disabled={steeringDisabled}
          />
        </div>
      )}

      {sessions.map((sessionEntry) => {
        const s = sessionEntry.session;
        const live = sessionEntry.liveDelivery;
        const progress = live?.progress ?? s.progress;
        const cancelled = live?.cancelled ?? s.cancelled;
        const decisionKind = live?.steeringDecision?.kind;
        const lineage = live?.steeringDecision?.lineage;
        const diagnostics: readonly SessionDiagnostic[] = [
          ...(s.diagnostics ?? []),
          ...(live?.diagnostics ?? []),
        ];

        return (
          <div
            key={s.id}
            className="space-y-2 rounded border border-blue-500/20 bg-blue-500/5 px-2 py-1.5"
            data-video-editor-agent-tool-session="true"
            data-video-editor-generation-session-origin={originLabel(live?.origin)}
            data-video-editor-generation-session-decision={decisionKind ?? 'none'}
          >
            <div className="flex items-start gap-2">
              <Loader2
                className={`mt-0.5 h-3 w-3 shrink-0 text-blue-400 ${s.done || cancelled ? '' : 'animate-spin'}`}
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1">
                  <span className="truncate text-[10px] text-zinc-300">{s.id}</span>
                  <span className="rounded bg-zinc-800 px-1 py-0 text-[9px] text-zinc-400">
                    {originLabel(live?.origin)}
                  </span>
                  {decisionKind && (
                    <span className={`rounded px-1 py-0 text-[9px] ${DECISION_CLASS[decisionKind] ?? 'bg-zinc-800 text-zinc-400'}`}>
                      {DECISION_LABEL[decisionKind] ?? decisionKind}
                    </span>
                  )}
                  {live && (
                    <span className={`rounded px-1 py-0 text-[9px] ${live.canActivate ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                      {live.canActivate ? 'live active' : 'live blocked'}
                    </span>
                  )}
                </div>

                <div className="mt-1 h-1 w-full rounded-full bg-zinc-800">
                  <div
                    className="h-1 rounded-full bg-blue-500 transition-all"
                    style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                    role="progressbar"
                    aria-valuenow={progress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`Progress: ${progress}%`}
                  />
                </div>
                <div className="mt-0.5 text-[9px] text-zinc-500">
                  {progress}%
                  {s.progressLabel ? ` — ${s.progressLabel}` : ''}
                  {s.done && ' (complete)'}
                  {cancelled && ' (cancelled)'}
                </div>
              </div>
              {!s.done && !cancelled && (
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

            {live && (
              <div className="space-y-1 rounded border border-white/5 bg-zinc-950/40 px-2 py-1">
                <div className="flex flex-wrap items-center gap-2 text-[9px] text-zinc-500">
                  {lineage?.generationIndex !== undefined && (
                    <span data-video-editor-generation-session-attempt="true">
                      Attempt {lineage.generationIndex}
                    </span>
                  )}
                  {live.steerHash && <span>Steer {live.steerHash}</span>}
                  {live.sampleCount > 0 && <span>{live.sampleCount} sample{live.sampleCount === 1 ? '' : 's'}</span>}
                  {live.activeChannels.length > 0 && (
                    <span>Channels {live.activeChannels.join(', ')}</span>
                  )}
                </div>
                {lineage?.provenance && (
                  <div className="text-[9px] text-zinc-500">
                    {lineage.provenance.model} · seed {lineage.provenance.seed}
                  </div>
                )}
                {refList('fork', live.parentRefs)}
                {refList('final', live.finalRefs)}
                {refList('baked', live.bakedRefs)}
              </div>
            )}

            {diagnostics.length > 0 && (
              <div className="space-y-0.5" data-video-editor-generation-session-diagnostics="true">
                {diagnostics.map((diag, idx) => {
                  const SevIcon = SEVERITY_ICON[diag.severity] ?? Info;
                  const sevColor = SEVERITY_COLOR[diag.severity] ?? 'text-zinc-400';
                  const detail = diagnosticDetailText(diag);
                  return (
                    <div
                      key={`${s.id}:diag:${idx}`}
                      className={`flex items-start gap-1 rounded border px-1.5 py-0.5 text-[9px] ${SEVERITY_BG[diag.severity] ?? ''}`}
                    >
                      <SevIcon className={`mt-0.5 h-2.5 w-2.5 shrink-0 ${sevColor}`} aria-hidden="true" />
                      <span className={sevColor}>
                        {diag.message}
                        {diag.code && <span className="ml-1 text-zinc-600">[{diag.code}]</span>}
                        {detail && <span className="ml-1 text-zinc-500">({detail})</span>}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            {decisionKind === 'fork' && (
              <div className="flex items-center gap-1 text-[9px] text-purple-400">
                <GitFork className="h-2.5 w-2.5" aria-hidden="true" />
                Forked generation branch
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
