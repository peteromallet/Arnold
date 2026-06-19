/**
 * CodePanelCanary — Host-contained canary for the codePanel surface.
 *
 * Demonstrates the code panel slot by:
 * - Publishing a syntax diagnostic with a 1-based range
 * - Rendering a visible marker for the diagnostic range
 * - Showing host state (timeline, save posture) without production behavior
 *
 * This is NOT a production code editor — it is a small host-contained
 * proof-of-life for the codePanel surface slot infrastructure.
 */

import { useMemo } from 'react';
import { AlertCircle, Code2 } from 'lucide-react';
import type { VideoEditorRenderContext } from '@/tools/video-editor/runtime/extensionSurface';

// ---------------------------------------------------------------------------
// Demo source
// ---------------------------------------------------------------------------

const DEMO_SOURCE = [
  'function createClip(config) {',
  '  const { duration, source } = config;',
  '  if (!name) {',
  "    throw new Error('clip name required');",
  '  }',
  '  return {',
  '    name,',
  '    duration: duration ?? 5,',
  '    source: source ?? null,',
  '  };',
  '}',
].join('\n');

/** Demo diagnostic: ``name`` used before declaration on line 7, col 5–9. */
const DEMO_DIAGNOSTIC = {
  severity: 'warning' as const,
  code: 'canary/syntax-warn',
  message: "Identifier 'name' used before its declaration.",
  sourceRange: {
    startLine: 7,
    startCol: 5,
    endLine: 7,
    endCol: 9,
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatSourceRange(
  r: { startLine: number; startCol: number; endLine: number; endCol: number },
): string {
  if (r.startLine === r.endLine) {
    return `L${r.startLine}:${r.startCol}–${r.endCol}`;
  }
  return `L${r.startLine}:${r.startCol}–L${r.endLine}:${r.endCol}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface CodePanelCanaryProps {
  context: VideoEditorRenderContext;
}

export function CodePanelCanary({ context }: CodePanelCanaryProps) {
  const { timelineName, chrome, data } = context;

  const sourceLines = useMemo(() => DEMO_SOURCE.split('\n'), []);

  const markerLineIdx = DEMO_DIAGNOSTIC.sourceRange.startLine - 1; // 1-based → 0-based
  const markerStartCol = DEMO_DIAGNOSTIC.sourceRange.startCol - 1;
  const markerEndCol = DEMO_DIAGNOSTIC.sourceRange.endCol - 1;

  return (
    <div
      data-video-editor-slot="codePanel"
      data-video-editor-canary="true"
      className="flex flex-col gap-2 rounded-md border border-border/60 bg-card/80 p-3 text-[11px]"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Code2 className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Code panel canary
          </span>
        </div>
        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
          {timelineName ?? '(unnamed)'}
        </span>
      </div>

      {/* Status line */}
      <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
        <span>Save: {chrome.saveStatus}</span>
        <span>·</span>
        <span>Device: {data.deviceClass}</span>
      </div>

      {/* Diagnostic banner */}
      <div
        data-video-editor-canary-diagnostic="true"
        className="flex items-start gap-2 rounded border border-yellow-500/30 bg-yellow-500/10 px-2 py-1.5 text-[10px]"
      >
        <AlertCircle className="mt-0.5 h-3 w-3 shrink-0 text-yellow-400" />
        <div>
          <span className="font-mono font-semibold text-yellow-300">
            {DEMO_DIAGNOSTIC.code}
          </span>
          <span className="mx-1 text-yellow-400/80">—</span>
          <span className="text-yellow-200/90">{DEMO_DIAGNOSTIC.message}</span>
          <div className="mt-0.5 text-yellow-400/60">
            Range: {formatSourceRange(DEMO_DIAGNOSTIC.sourceRange)}
          </div>
        </div>
      </div>

      {/* Source display with marker */}
      <div className="overflow-x-auto rounded border border-border/40 bg-muted/30 font-mono text-[10px] leading-relaxed">
        {sourceLines.map((line, idx) => {
          const lineNum = idx + 1; // 1-based
          const isMarkedLine = idx === markerLineIdx;

          return (
            <div
              key={lineNum}
              className={`flex ${isMarkedLine ? 'bg-yellow-500/10' : ''}`}
            >
              <span className="select-none pr-3 text-right text-muted-foreground/50 w-8 shrink-0">
                {lineNum}
              </span>
              <span className="whitespace-pre">
                {isMarkedLine ? (
                  <>
                    <span>{line.slice(0, markerStartCol)}</span>
                    {/* Marker span — the highlighted identifier */}
                    <span
                      data-video-editor-canary-marker="true"
                      className="rounded-sm bg-yellow-500/30 text-yellow-200 underline decoration-yellow-500/50 decoration-wavy underline-offset-2"
                    >
                      {line.slice(markerStartCol, markerEndCol)}
                    </span>
                    <span>{line.slice(markerEndCol)}</span>
                  </>
                ) : (
                  line
                )}
              </span>
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
