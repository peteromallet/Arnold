import { useCallback, useEffect, useState } from 'react';
import { useClientRender } from '@/tools/video-editor/hooks/useClientRender.ts';
import type { CompositionMetadata } from '@/tools/video-editor/hooks/useDerivedTimeline.ts';
import type { VideoEditorExporter } from '@/tools/video-editor/lib/browser-runtime.ts';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';
import type { ExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  collectBuiltInKnownIds,
  collectExtensionDeclaredIds,
  scanExportConfig,
} from '@/tools/video-editor/runtime/exportGuard.ts';

export type RenderStatus = 'idle' | 'rendering' | 'done' | 'error';

type RenderProgress = { current: number; total: number; percent: number; phase: string } | null;

const CLIENT_CLIP_TYPES = new Set(['media', 'text', 'effect-layer', 'hold']);

function getFastRenderRouteDecision(resolvedConfig: ResolvedTimelineConfig | null) {
  const clips = resolvedConfig?.clips ?? [];

  if (clips.length === 0) {
    return { route: 'browser-remotion' as const, reason: 'no_clips' };
  }

  let hasGeneratedModuleClip = false;
  let hasOtherClip = false;
  for (const clip of clips) {
    if (clip.generation?.sequence_lane === 'remotion_module') {
      if (!clip.generation?.artifact_id) {
        return { route: 'preview-only' as const, reason: 'remotion_module_missing_artifact' };
      }
      hasGeneratedModuleClip = true;
      continue;
    }

    if (!clip.clipType || CLIENT_CLIP_TYPES.has(clip.clipType)) {
      hasOtherClip = true;
      continue;
    }

    return null;
  }

  if (hasGeneratedModuleClip) {
    return {
      route: 'worker-banodoco' as const,
      reason: hasOtherClip ? 'mixed_generated_module_and_other' : 'generated_remotion_module',
    };
  }

  return { route: 'browser-remotion' as const, reason: 'pure_native_clips' };
}

function isExtensionRuntimeEmpty(extRuntime: ExtensionRuntime | undefined): boolean {
  if (!extRuntime) return true;
  return extRuntime.extensions.length === 0 && extRuntime.inactiveReserved.length === 0;
}

function buildExtensionContributions(extRuntime: ExtensionRuntime) {
  const allContributions: import('@reigh/editor-sdk').ExtensionContribution[] = [];
  for (const ext of extRuntime.extensions) {
    const contribs = ext.manifest.contributions ?? [];
    for (const c of contribs) {
      allContributions.push(c);
    }
  }
  return allContributions;
}

/**
 * Create a concise render log line from export guard diagnostics.
 * Emits a single summary line plus per-diagnostic error lines for blocking issues.
 */
function formatExportGuardLog(
  guardResult: ReturnType<typeof scanExportConfig>,
): string {
  const lines: string[] = [];

  const totalDiags = guardResult.diagnostics.length;
  const errorCount = guardResult.diagnostics.filter((d) => d.severity === 'error').length;
  const warningCount = guardResult.diagnostics.filter((d) => d.severity === 'warning').length;
  const infoCount = totalDiags - errorCount - warningCount;

  if (totalDiags === 0) {
    lines.push('Export guard: no issues found.');
    return lines.join('\n');
  }

  lines.push(
    `Export guard: ${totalDiags} issue(s) — ${errorCount} error(s), ${warningCount} warning(s), ${infoCount} info(s).`,
  );

  // Show blocking errors first
  for (const diag of guardResult.diagnostics) {
    if (diag.severity === 'error') {
      lines.push(`  [${diag.code}] ${diag.message}`);
    }
  }

  // Then warnings
  for (const diag of guardResult.diagnostics) {
    if (diag.severity === 'warning') {
      lines.push(`  [${diag.code}] ${diag.message}`);
    }
  }

  return lines.join('\n');
}

export function useRenderState(
  resolvedConfig: ResolvedTimelineConfig | null,
  renderMetadata: CompositionMetadata | null,
  exporter?: VideoEditorExporter | null,
  extensionRuntime?: ExtensionRuntime,
) {
  const [renderStatus, setRenderStatus] = useState<RenderStatus>('idle');
  const [renderLog, setRenderLog] = useState('');
  const [renderDirty, setRenderDirty] = useState(false);
  const [renderProgress, setRenderProgress] = useState<RenderProgress>(null);
  const [renderResultUrl, setRenderResultUrl] = useState<string | null>(null);
  const [renderResultFilename, setRenderResultFilename] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (renderResultUrl) {
        URL.revokeObjectURL(renderResultUrl);
      }
    };
  }, [renderResultUrl]);

  const startClientRender = useClientRender({
    resolvedConfig,
    metadata: renderMetadata,
    setRenderStatus,
    setRenderProgress,
    setRenderLog,
    setRenderDirty,
    setRenderResult: (updater) => {
      const nextValue = typeof updater === 'function'
        ? updater({ url: renderResultUrl, filename: renderResultFilename })
        : updater;

      if (renderResultUrl && renderResultUrl !== nextValue.url) {
        URL.revokeObjectURL(renderResultUrl);
      }

      setRenderResultUrl(nextValue.url);
      setRenderResultFilename(nextValue.filename);
    },
  });

  const runExportGuard = useCallback((): boolean => {
    // Skip guard work for the empty extension runtime
    if (isExtensionRuntimeEmpty(extensionRuntime)) {
      return true; // no blocker
    }

    if (!resolvedConfig || resolvedConfig.clips.length === 0) {
      return true; // nothing to scan
    }

    const builtIn = collectBuiltInKnownIds();
    const allContributions = buildExtensionContributions(extensionRuntime!);
    const extIds = collectExtensionDeclaredIds(allContributions);
    const guardResult = scanExportConfig(resolvedConfig, builtIn, extIds);

    // Emit structured diagnostics as concise render log output
    const log = formatExportGuardLog(guardResult);
    setRenderLog(log);

    if (guardResult.hasBlockingErrors) {
      // M1 blocker: truly unknown IDs that cannot be rendered
      setRenderStatus('error');
      setRenderProgress(null);
      setRenderDirty(false);
      return false; // blocker
    }

    // Extension-declared warnings only — preserve native routing
    return true; // no blocker
  }, [extensionRuntime, resolvedConfig]);

  const startRender = useCallback(async () => {
    // ---- export guard: scan for unknown IDs before routing ------------------
    if (!runExportGuard()) {
      return; // blocked by export guard
    }

    let decision = getFastRenderRouteDecision(resolvedConfig);
    if (!decision) {
      let importedDecision: {
      route: 'browser-remotion' | 'worker-banodoco' | 'preview-only' | 'external';
      reason: string;
      };
      try {
        const renderRouter = await import('@/tools/video-editor/lib/renderRouter');
        importedDecision = renderRouter.decideRenderRoute(resolvedConfig);
      } catch (error) {
        setRenderStatus('error');
        setRenderProgress(null);
        setRenderDirty(false);
        setRenderLog(error instanceof Error
          ? `Render routing unavailable: ${error.message}`
          : 'Render routing unavailable.');
        return;
      }
      decision = importedDecision;
    }
    if (decision.route === 'preview-only') {
      setRenderStatus('error');
      setRenderProgress(null);
      setRenderDirty(false);
      setRenderLog(`Render blocked: ${decision.reason}. Generated Remotion module clips require valid worker artifact metadata.`);
      return;
    }

    if (decision.route === 'worker-banodoco' || decision.route === 'external') {
      setRenderStatus('error');
      setRenderProgress(null);
      setRenderDirty(false);
      setRenderLog(`Worker render unavailable for route "${decision.reason}". This timeline was not sent to the browser renderer.`);
      return;
    }

    if (exporter && resolvedConfig) {
      setRenderStatus('rendering');
      setRenderProgress({
        current: 0,
        total: renderMetadata?.durationInFrames ?? 1,
        percent: 0,
        phase: 'validating',
      });
      setRenderResultUrl((current) => {
        if (current) {
          URL.revokeObjectURL(current);
        }
        return null;
      });
      setRenderResultFilename(null);
      setRenderLog('');

      const job = await exporter.render({
        timeline: resolvedConfig,
        registry: resolvedConfig.registry,
        output: {
          file: resolvedConfig.output.file,
          fps: resolvedConfig.output.fps,
        },
      });

      job.subscribe((progress) => {
        setRenderLog(progress.log ?? '');
        setRenderProgress(progress.progress == null
          ? null
          : {
            current: Math.round((renderMetadata?.durationInFrames ?? 1) * progress.progress),
            total: renderMetadata?.durationInFrames ?? 1,
            percent: Math.round(progress.progress * 100),
            phase: progress.phase,
          });

        if (progress.phase === 'complete') {
          setRenderStatus('done');
          setRenderDirty(false);
          if (progress.resultUrl) {
            setRenderResultUrl(progress.resultUrl);
            setRenderResultFilename(resolvedConfig.output.file);
          }
          return;
        }

        if (progress.phase === 'failed') {
          setRenderStatus('error');
          setRenderDirty(false);
          return;
        }

        setRenderStatus('rendering');
      });
      return;
    }

    await startClientRender();
  }, [exporter, renderMetadata?.durationInFrames, resolvedConfig, startClientRender, runExportGuard]);

  return {
    renderStatus,
    renderLog,
    renderDirty,
    renderProgress,
    renderResultUrl,
    renderResultFilename,
    setRenderStatus,
    setRenderLog,
    setRenderDirty,
    setRenderProgress,
    startRender,
  };
}
