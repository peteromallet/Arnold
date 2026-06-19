/**
 * WritingPanelCanary — Host-contained canary for the writingPanel surface.
 *
 * Demonstrates the writing panel slot by:
 * - Showing source identity (timeline name, ID, user)
 * - Displaying dirty/save posture from host chrome state
 * - Listing canary diagnostics with source ranges
 * - Rendering source range annotations inline
 *
 * This is NOT a production writing tool — it is a small host-contained
 * proof-of-life for the writingPanel surface slot infrastructure.
 */

import { useMemo } from 'react';
import { FileText, AlertTriangle, Info, CheckCircle2, Pencil } from 'lucide-react';
import type { VideoEditorRenderContext } from '@/tools/video-editor/runtime/extensionSurface';

// ---------------------------------------------------------------------------
// Demo data
// ---------------------------------------------------------------------------

interface CanarySourceRange {
  startLine: number;
  startCol: number;
  endLine: number;
  endCol: number;
}

interface CanaryDiagnostic {
  severity: 'error' | 'warning' | 'info';
  code: string;
  message: string;
  sourceRange?: CanarySourceRange;
}

const DEMO_SOURCE_IDENTITY = {
  title: 'Document Draft v3',
  language: 'en',
  wordCount: 1250,
};

const DEMO_DIAGNOSTICS: CanaryDiagnostic[] = [
  {
    severity: 'error',
    code: 'writing/grammar-error',
    message: 'Subject-verb agreement: "they was" should be "they were".',
    sourceRange: { startLine: 12, startCol: 10, endLine: 12, endCol: 18 },
  },
  {
    severity: 'warning',
    code: 'writing/style-passive',
    message: 'Passive voice detected. Consider rephrasing.',
    sourceRange: { startLine: 23, startCol: 5, endLine: 23, endCol: 28 },
  },
  {
    severity: 'info',
    code: 'writing/word-count-target',
    message: 'Section is 150 words under the recommended length.',
  },
  {
    severity: 'warning',
    code: 'writing/repetition',
    message: 'Word "therefore" used 3 times in this paragraph.',
    sourceRange: { startLine: 8, startCol: 1, endLine: 8, endCol: 80 },
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SEVERITY_ICON = {
  error: AlertTriangle,
  warning: AlertTriangle,
  info: Info,
} as const;

const SEVERITY_COLOR = {
  error: 'text-red-400',
  warning: 'text-yellow-400',
  info: 'text-blue-400',
} as const;

const SEVERITY_BG = {
  error: 'bg-red-500/10 border-red-500/30',
  warning: 'bg-yellow-500/10 border-yellow-500/30',
  info: 'bg-blue-500/10 border-blue-500/30',
} as const;

function formatSourceRange(r: CanarySourceRange): string {
  if (r.startLine === r.endLine) {
    return `L${r.startLine}:${r.startCol}–${r.endCol}`;
  }
  return `L${r.startLine}:${r.startCol}–L${r.endLine}:${r.endCol}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface WritingPanelCanaryProps {
  context: VideoEditorRenderContext;
}

export function WritingPanelCanary({ context }: WritingPanelCanaryProps) {
  const { timelineId, timelineName, userId, chrome } = context;

  const savePosture = useMemo(() => {
    switch (chrome.saveStatus) {
      case 'saved':
        return { label: 'Clean — all changes saved', icon: CheckCircle2, color: 'text-green-400' };
      case 'saving':
        return { label: 'Saving…', icon: Pencil, color: 'text-yellow-400' };
      case 'dirty':
        return { label: 'Dirty — unsaved changes', icon: Pencil, color: 'text-yellow-400' };
      case 'error':
        return { label: 'Save error', icon: AlertTriangle, color: 'text-red-400' };
      default:
        return { label: String(chrome.saveStatus), icon: Info, color: 'text-muted-foreground' };
    }
  }, [chrome.saveStatus]);

  return (
    <div
      data-video-editor-slot="writingPanel"
      data-video-editor-canary="true"
      className="flex flex-col gap-3 rounded-md border border-border/60 bg-card/80 p-3"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Writing panel canary
          </span>
        </div>
      </div>

      {/* Source identity */}
      <div
        data-video-editor-canary-section="source-identity"
        className="space-y-1 rounded border border-border/40 bg-muted/30 p-2 text-[10px]"
      >
        <div className="flex items-center justify-between">
          <span className="font-semibold text-foreground/80">
            {DEMO_SOURCE_IDENTITY.title}
          </span>
          <span className="text-muted-foreground/70">
            {DEMO_SOURCE_IDENTITY.wordCount} words
          </span>
        </div>
        <div className="flex gap-3 text-muted-foreground/60">
          <span>Lang: {DEMO_SOURCE_IDENTITY.language}</span>
          <span>Timeline: {timelineName ?? timelineId.slice(0, 12)}</span>
          <span>User: {userId.slice(0, 8)}…</span>
        </div>
      </div>

      {/* Dirty / save posture */}
      <div
        data-video-editor-canary-section="save-posture"
        className="flex items-center gap-2 rounded border border-border/40 bg-muted/30 p-2 text-[10px]"
      >
        <savePosture.icon className={`h-3 w-3 ${savePosture.color}`} />
        <span className={savePosture.color}>{savePosture.label}</span>
        <span className="text-muted-foreground/50">
          ({chrome.saveStatus})
        </span>
      </div>

      {/* Diagnostics with source ranges */}
      <div
        data-video-editor-canary-section="diagnostics"
        className="space-y-1.5"
      >
        <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          Diagnostics ({DEMO_DIAGNOSTICS.length})
        </div>

        {DEMO_DIAGNOSTICS.map((diag, idx) => {
          const Icon = SEVERITY_ICON[diag.severity];
          return (
            <div
              key={idx}
              data-video-editor-canary-diagnostic={diag.code}
              className={`flex items-start gap-2 rounded border px-2 py-1.5 text-[10px] ${SEVERITY_BG[diag.severity]}`}
            >
              <Icon className={`mt-0.5 h-3 w-3 shrink-0 ${SEVERITY_COLOR[diag.severity]}`} />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-1">
                  <span className={`font-mono font-semibold ${SEVERITY_COLOR[diag.severity]}`}>
                    {diag.code}
                  </span>
                </div>
                <div className="text-foreground/80">{diag.message}</div>
                {diag.sourceRange && (
                  <div
                    data-video-editor-canary-source-range="true"
                    className="mt-0.5 font-mono text-[9px] text-muted-foreground/60"
                  >
                    Range: {formatSourceRange(diag.sourceRange)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="text-[10px] text-muted-foreground/60">
        Canary — not available for production authoring (M4)
      </div>
    </div>
  );
}
