import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useClientRender } from '@/tools/video-editor/hooks/useClientRender.ts';
import type { CompositionMetadata } from '@/tools/video-editor/hooks/useDerivedTimeline.ts';
import type { VideoEditorExporter } from '@/tools/video-editor/lib/browser-runtime.ts';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';
import type { ExtensionRuntime, VideoEditorOutputFormatDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  createCompileOnlyOutputFormatRegistry,
  executeCompileOnlyOutput,
  type CompileOnlyOutputFormatEntry,
  type CompileOnlyOutputFormatRegistry,
} from '@/tools/video-editor/runtime/outputFormatRegistry.ts';
import { useEffectRegistrySnapshot } from '@/tools/video-editor/effects/registry/EffectRegistryContext.tsx';
import { useTransitionRegistrySnapshot } from '@/tools/video-editor/transitions/registry/TransitionRegistryContext.tsx';
import { useClipTypeRegistrySnapshot } from '@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx';
import {
  collectBuiltInKnownIds,
  collectExtensionDeclaredIds,
  hasTimelineShaderMetadata,
  scanExportConfig,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import {
  planRender,
  type RenderPlannerResult,
} from '@/tools/video-editor/runtime/renderPlanner.ts';
import {
  DataProviderContext,
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { syncPlannerDiagnosticsToCollection } from '@/tools/video-editor/runtime/diagnosticCollectionSync.ts';
import type {
  CapabilityFinding,
  Diagnostic,
  ExportDiagnostic,
  RenderBlocker,
  RenderBlockerReason,
  RenderRoute,
} from '@reigh/editor-sdk';

export type RenderStatus = 'idle' | 'rendering' | 'done' | 'error';

/** M6: Export status for compile-only and render-dependent export operations. */
export type ExportStatus = 'idle' | 'exporting' | 'done' | 'error';

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

type RenderRouteDecisionForPlanning = {
  readonly route: 'browser-remotion' | 'worker-banodoco' | 'preview-only' | 'external';
  readonly reason: string;
};

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

  // Show blocking errors first, naming the effect/transition and route when available
  for (const diag of guardResult.diagnostics) {
    if (diag.severity === 'error') {
      const name = diag.detail?.effectType
        ? ` effect "${diag.detail.effectType}"`
        : diag.detail?.transitionType
          ? ` transition "${diag.detail.transitionType}"`
          : diag.detail?.clipType
            ? ` clip type "${diag.detail.clipType}"`
            : diag.detail?.shaderId
              ? ` shader "${diag.detail.shaderId}"`
            : '';
      const route = diag.detail?.renderRoute ? ` (${diag.detail.renderRoute})` : '';
      lines.push(`  [${diag.code}]${name}${route}: ${diag.message}`);
    }
  }

  // Then warnings — also name effects/transitions/clip types
  for (const diag of guardResult.diagnostics) {
    if (diag.severity === 'warning') {
      const name = diag.detail?.effectType
        ? ` effect "${diag.detail.effectType}"`
        : diag.detail?.transitionType
          ? ` transition "${diag.detail.transitionType}"`
          : diag.detail?.clipType
            ? ` clip type "${diag.detail.clipType}"`
            : diag.detail?.shaderId
              ? ` shader "${diag.detail.shaderId}"`
            : '';
      const route = diag.detail?.renderRoute ? ` (${diag.detail.renderRoute})` : '';
      lines.push(`  [${diag.code}]${name}${route}: ${diag.message}`);
    }
  }

  // Append per-route blocker summaries from findings (when available)
  const blockerFindings = (guardResult.findings ?? []).filter((f) => f.severity === 'error');
  if (blockerFindings.length > 0) {
    lines.push('');
    lines.push('Route blockers:');
    for (const finding of blockerFindings) {
      const name = finding.detail?.effectType
        ? `"${finding.detail.effectType}"`
        : finding.detail?.transitionType
          ? `"${finding.detail.transitionType}"`
          : finding.detail?.shaderId
            ? `"${finding.detail.shaderId}"`
          : 'unknown';
      const route = finding.route ?? 'unknown-route';
      lines.push(`  ${name} blocked on ${route}: ${finding.message}`);
    }
  }

  return lines.join('\n');
}

function exportDiagnosticId(diagnostic: ReturnType<typeof scanExportConfig>['diagnostics'][number], index: number): string {
  const detail = diagnostic.detail ?? {};
  return [
    'export-guard',
    diagnostic.code,
    diagnostic.extensionId ?? 'host',
    diagnostic.contributionId ?? 'timeline',
    detail.clipId ?? 'no-clip',
    detail.effectType ?? detail.transitionType ?? detail.clipType ?? detail.shaderId ?? index,
  ].join(':');
}

function blockerReasonForExportDiagnostic(diagnostic: ExportDiagnostic): RenderBlockerReason {
  if (diagnostic.code.includes('unknown') || diagnostic.code.includes('missing')) {
    return 'missing-contribution';
  }
  if (diagnostic.code.includes('inactive')) {
    return 'inactive-extension';
  }
  if (diagnostic.code.includes('live-binding')) {
    return 'live-unbaked';
  }
  if (diagnostic.code.includes('shader')) {
    return 'missing-material';
  }
  return 'route-unsupported';
}

function exportDiagnosticToPlannerFinding(diagnostic: ExportDiagnostic, index: number): CapabilityFinding {
  const route = diagnostic.detail?.renderRoute === 'worker-export' || diagnostic.detail?.renderRoute === 'preview'
    ? diagnostic.detail.renderRoute
    : 'browser-export';
  const reason = diagnostic.severity === 'error'
    ? blockerReasonForExportDiagnostic(diagnostic)
    : undefined;

  return {
    id: exportDiagnosticId(diagnostic, index),
    severity: diagnostic.severity,
    route,
    ...(reason ? { reason } : {}),
    message: diagnostic.message,
    ...(diagnostic.extensionId ? { extensionId: diagnostic.extensionId } : {}),
    ...(diagnostic.contributionId ? { contributionId: diagnostic.contributionId } : {}),
    detail: {
      ...(diagnostic.detail ?? {}),
      source: 'export-guard-compat',
      code: diagnostic.code,
    },
  };
}

function planFromExportGuardResult(
  guardResult: ReturnType<typeof scanExportConfig>,
  options?: {
    readonly extensionRuntime?: ExtensionRuntime;
    readonly processStatuses?: VideoEditorRuntimeContextValue['processStatuses'];
    readonly processResultAttachRecords?: VideoEditorRuntimeContextValue['processResultAttachRecords'];
  },
): RenderPlannerResult {
  const diagnostics: CapabilityFinding[] = [
    ...(guardResult.findings ?? []),
    ...(guardResult.blockers ?? []),
    ...guardResult.diagnostics.map(exportDiagnosticToPlannerFinding),
  ];
  return planRender({
    diagnostics,
    extensionRuntime: options?.extensionRuntime,
    outputFormats: outputFormatsForPlanning(options?.extensionRuntime),
    processStatuses: options?.processStatuses,
    processResultAttachRecords: options?.processResultAttachRecords,
  });
}

function plannerRouteForDecision(
  decision: RenderRouteDecisionForPlanning,
): RenderRoute {
  return decision.route === 'worker-banodoco' || decision.route === 'external'
    ? 'worker-export'
    : 'browser-export';
}

function blockerReasonForRouteDecision(
  decision: RenderRouteDecisionForPlanning,
): RenderBlockerReason {
  if (decision.route === 'preview-only') {
    return decision.reason === 'remotion_module_missing_artifact'
      ? 'missing-material'
      : 'materialization-failed';
  }
  return 'route-unsupported';
}

function blockerMessageForRouteDecision(
  decision: RenderRouteDecisionForPlanning,
): string {
  if (decision.route === 'preview-only') {
    return `Render blocked: ${decision.reason}. Generated Remotion module clips require valid worker artifact metadata.`;
  }
  return `Worker render unavailable for route "${decision.reason}". This timeline was not sent to the browser renderer.`;
}

function planRouteDecisionBlocker(
  decision: RenderRouteDecisionForPlanning,
  options?: {
    readonly extensionRuntime?: ExtensionRuntime;
    readonly processStatuses?: VideoEditorRuntimeContextValue['processStatuses'];
    readonly processResultAttachRecords?: VideoEditorRuntimeContextValue['processResultAttachRecords'];
  },
): RenderPlannerResult {
  const finding: CapabilityFinding = {
    id: `planner.renderRoute.${decision.route}.${decision.reason}`,
    severity: 'error',
    route: plannerRouteForDecision(decision),
    reason: blockerReasonForRouteDecision(decision),
    message: blockerMessageForRouteDecision(decision),
    detail: {
      source: 'render-route-decision',
      providerRoute: decision.route,
      legacyReason: decision.reason,
    },
  };

  return planRender({
    diagnostics: [finding],
    extensionRuntime: options?.extensionRuntime,
    outputFormats: outputFormatsForPlanning(options?.extensionRuntime),
    processStatuses: options?.processStatuses,
    processResultAttachRecords: options?.processResultAttachRecords,
  });
}

function firstPlannerBlockerForDecision(
  plannerResult: RenderPlannerResult,
  decision: RenderRouteDecisionForPlanning,
): RenderBlocker | undefined {
  const expectedId = `planner.renderRoute.${decision.route}.${decision.reason}`;
  return plannerResult.blockers.find((blocker) => blocker.id === expectedId)
    ?? plannerResult.blockers[0];
}

function outputFormatsForPlanning(extensionRuntime: ExtensionRuntime | undefined): readonly VideoEditorOutputFormatDescriptor[] {
  const outputFormats = extensionRuntime?.outputFormats
    ?? extensionRuntime?.config?.outputFormats
    ?? [];
  return outputFormats.map((format) => ({
    ...format,
    availableRoutes: format.availableRoutes ?? [],
    routeRequirements: format.routeRequirements ?? [],
    processRequirements: format.processRequirements ?? [],
    blockers: format.blockers ?? [],
    nextActions: format.nextActions ?? [],
    sidecars: format.sidecars ?? [],
  }));
}

function toCollectionDiagnostic(
  diagnostic: ReturnType<typeof scanExportConfig>['diagnostics'][number],
  index: number,
): Diagnostic {
  return {
    id: exportDiagnosticId(diagnostic, index),
    severity: diagnostic.severity,
    code: diagnostic.code,
    message: diagnostic.message,
    ...(diagnostic.extensionId ? { extensionId: diagnostic.extensionId } : {}),
    ...(diagnostic.contributionId ? { contributionId: diagnostic.contributionId } : {}),
    ...(diagnostic.detail ? { detail: { ...diagnostic.detail, source: 'export-guard' } } : { detail: { source: 'export-guard' } }),
  };
}

// ---------------------------------------------------------------------------
// M6: Export format categorization
// ---------------------------------------------------------------------------

/** Categorize output format descriptors into compile-only and render-dependent groups. */
function categorizeExportFormats(
  outputFormats: readonly VideoEditorOutputFormatDescriptor[],
): {
  compileOnly: VideoEditorOutputFormatDescriptor[];
  renderDependent: VideoEditorOutputFormatDescriptor[];
} {
  const compileOnly: VideoEditorOutputFormatDescriptor[] = [];
  const renderDependent: VideoEditorOutputFormatDescriptor[] = [];
  for (const fmt of outputFormats) {
    if (fmt.requiresRender || fmt.disabled) {
      renderDependent.push(fmt);
    } else {
      compileOnly.push(fmt);
    }
  }
  return { compileOnly, renderDependent };
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
  // M6: Export state
  const [exportStatus, setExportStatus] = useState<ExportStatus>('idle');
  const [exportLog, setExportLogState] = useState('');
  const [exportResultUrl, setExportResultUrl] = useState<string | null>(null);
  const [exportResultFilename, setExportResultFilename] = useState<string | null>(null);
  const effectRegistrySnapshot = useEffectRegistrySnapshot();
  const transitionRegistrySnapshot = useTransitionRegistrySnapshot();
  const clipTypeRegistrySnapshot = useClipTypeRegistrySnapshot();
  // M6: Derive export format categories from extension runtime
  const exportFormats = useMemo(() => {
    const outputFormats = outputFormatsForPlanning(extensionRuntime);
    return categorizeExportFormats(outputFormats);
  }, [extensionRuntime]);
  const runtimeContext = useContext(DataProviderContext);
  const diagnosticCollection = runtimeContext?.diagnosticCollection;
  const processStatuses = runtimeContext?.processStatuses;
  const processResultAttachRecords = runtimeContext?.processResultAttachRecords;

  useEffect(() => {
    return () => {
      if (renderResultUrl) {
        URL.revokeObjectURL(renderResultUrl);
      }
    };
  }, [renderResultUrl]);
  // M6: Cleanup export result URL on unmount
  useEffect(() => {
    return () => {
      if (exportResultUrl) {
        URL.revokeObjectURL(exportResultUrl);
      }
    };
  }, [exportResultUrl]);

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
    diagnosticCollection?.remove((diagnostic) => diagnostic.detail?.source === 'export-guard');
    diagnosticCollection?.remove((diagnostic) => diagnostic.detail?.source === 'render-planner');

    const compositionGraph = extensionRuntime?.compositionGraph;

    // Skip guard work only when there is no active extension/provider registry input.
    if (
      isExtensionRuntimeEmpty(extensionRuntime)
      && effectRegistrySnapshot.records.length === 0
      && transitionRegistrySnapshot.records.length === 0
      && clipTypeRegistrySnapshot.records.length === 0
      && !hasTimelineShaderMetadata(resolvedConfig, compositionGraph)
    ) {
      return true; // no blocker
    }

    if (!resolvedConfig || resolvedConfig.clips.length === 0) {
      return true; // nothing to scan
    }

    const builtIn = collectBuiltInKnownIds();
    const allContributions = extensionRuntime ? buildExtensionContributions(extensionRuntime) : [];
    const extIds = collectExtensionDeclaredIds(allContributions);
    const guardResult = scanExportConfig(
      resolvedConfig,
      builtIn,
      extIds,
      effectRegistrySnapshot,
      transitionRegistrySnapshot,
      clipTypeRegistrySnapshot,
      compositionGraph,
      processResultAttachRecords,
    );
    const plannerResult = planFromExportGuardResult(guardResult, {
      extensionRuntime,
      processStatuses,
      processResultAttachRecords,
    });

    guardResult.diagnostics.forEach((diagnostic, index) => {
      diagnosticCollection?.publish(toCollectionDiagnostic(diagnostic, index));
    });
    syncPlannerDiagnosticsToCollection(diagnosticCollection, plannerResult.blockers);

    // Emit structured diagnostics as concise render log output
    const log = formatExportGuardLog(guardResult);
    setRenderLog(log);

    if (plannerResult.blockers.length > 0) {
      // Planner-owned blockers are the canonical readiness decision.
      setRenderStatus('error');
      setRenderProgress(null);
      setRenderDirty(false);
      return false; // blocker
    }

    // Extension-declared warnings only — preserve native routing
    return true; // no blocker
  }, [
    diagnosticCollection,
    effectRegistrySnapshot,
    transitionRegistrySnapshot,
    clipTypeRegistrySnapshot,
    extensionRuntime,
    processResultAttachRecords,
    processStatuses,
    resolvedConfig,
  ]);

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
        importedDecision = renderRouter.decideRenderRoute(
          resolvedConfig,
          undefined,
          {
            compositionGraph: extensionRuntime?.compositionGraph,
            processes: extensionRuntime?.processes,
            processStatuses,
            processResultAttachRecords,
          },
        );
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
      const plannerResult = planRouteDecisionBlocker(decision, {
        extensionRuntime,
        processStatuses,
        processResultAttachRecords,
      });
      const blocker = firstPlannerBlockerForDecision(plannerResult, decision);
      syncPlannerDiagnosticsToCollection(diagnosticCollection, blocker ? [blocker] : plannerResult.blockers);
      setRenderStatus('error');
      setRenderProgress(null);
      setRenderDirty(false);
      setRenderLog(blocker?.message ?? blockerMessageForRouteDecision(decision));
      return;
    }

    if (decision.route === 'worker-banodoco' || decision.route === 'external') {
      const plannerResult = planRouteDecisionBlocker(decision, {
        extensionRuntime,
        processStatuses,
        processResultAttachRecords,
      });
      const blocker = firstPlannerBlockerForDecision(plannerResult, decision);
      syncPlannerDiagnosticsToCollection(diagnosticCollection, blocker ? [blocker] : plannerResult.blockers);
      setRenderStatus('error');
      setRenderProgress(null);
      setRenderDirty(false);
      setRenderLog(blocker?.message ?? blockerMessageForRouteDecision(decision));
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
  }, [
    exporter,
    extensionRuntime?.compositionGraph,
    extensionRuntime?.processes,
    processResultAttachRecords,
    processStatuses,
    renderMetadata?.durationInFrames,
    resolvedConfig,
    startClientRender,
    runExportGuard,
    diagnosticCollection,
  ]);

  // ---- M6: compile-only export ------------------------------------------------
  const startExport = useCallback(async (
    formatId: string,
    compileOnlyRegistry?: CompileOnlyOutputFormatRegistry,
  ) => {
    if (!resolvedConfig) {
      setExportStatus('error');
      setExportLogState('Export unavailable: no timeline configuration.');
      return;
    }

    const plannerOutputFormats = outputFormatsForPlanning(extensionRuntime);
    const outputPlan = planRender({
      extensionRuntime,
      outputFormats: plannerOutputFormats,
      processes: extensionRuntime?.processes ?? [],
      processStatuses,
      processResultAttachRecords,
      shaders: extensionRuntime?.shaders ?? [],
      compositionGraph: extensionRuntime?.compositionGraph,
      request: {
        outputFormatId: formatId,
        routes: ['browser-export'],
      },
      diagnostics: plannerOutputFormats.find((candidate) => candidate.id === formatId)?.disabled
        ? [{
            id: `planner.outputFormat.${formatId}.disabled`,
            severity: 'error',
            route: 'browser-export',
            reason: 'inactive-extension',
            message: plannerOutputFormats.find((candidate) => candidate.id === formatId)?.disabledReason
              ?? `Export format "${formatId}" is disabled.`,
            contributionId: formatId,
            detail: { source: 'output-format', outputFormatId: formatId },
          }]
        : [],
    });
    const browserOutputPlan = outputPlan.routePlans.find((routePlan) => routePlan.route === 'browser-export');
    const fmt = plannerOutputFormats.find((f) => f.id === formatId && !f.requiresRender && !f.disabled);
    if (!fmt || browserOutputPlan?.blocked) {
      const requestedFormat = plannerOutputFormats.find((f) => f.id === formatId);
      const blocker = outputPlan.blockers.find((candidate) => candidate.id === `planner.outputFormat.${formatId}.disabled`)
        ?? browserOutputPlan?.blockers[0]
        ?? outputPlan.blockers[0];
      setExportStatus('error');
      if (blocker) {
        setExportLogState(`Export blocked: ${blocker.message}`);
      } else if (requestedFormat) {
        setExportLogState(`Export blocked: "${requestedFormat.label}" is not available for browser export.`);
      } else {
        setExportLogState(`Export format "${formatId}" not found.`);
      }
      return;
    }

    // ---- M7: Run export guard before compile-only export --------------------
    // Compile-only exports don't need rendered pixels, but they still process
    // timeline data.  Unknown / missing-contribution effects should block
    // because the exported data would be invalid.  Route-specific capability
    // blockers (browser-export blocked, worker-export blocked) are surfaced
    // as warnings but do not prevent compile-only export.
    const guardPassed = runExportGuard();
    if (!guardPassed) {
      // Export guard found blocking errors (e.g. truly unknown effects).
      // Surface the guard log as the export error.
      setExportStatus('error');
      setExportLogState(
        `Export blocked by readiness scan. See render log for details.`,
      );
      return;
    }

    if (!compileOnlyRegistry || compileOnlyRegistry.size === 0) {
      setExportStatus('error');
      setExportLogState(`Export unavailable: no compile-only output handlers registered. Format "${fmt.label}" (${fmt.id}) requires a handler registered via ctx.export.registerOutputFormat().`);
      return;
    }

    setExportStatus('exporting');
    setExportLogState(`Exporting "${fmt.label}"...`);
    setExportResultUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return null;
    });
    setExportResultFilename(null);

    try {
      // Build timeline snapshot from resolved config
      const timeline = Object.freeze({
        id: resolvedConfig.output?.file ?? 'timeline',
        assetKeys: Object.freeze(Object.keys(resolvedConfig.registry ?? {})),
        clipCount: resolvedConfig.clips?.length ?? 0,
        trackCount: resolvedConfig.tracks?.length ?? 0,
        fps: resolvedConfig.output?.fps ?? 30,
        resolution: resolvedConfig.output?.resolution ?? '1920x1080',
      });

      // Build assets map from registry
      const assetsMap = new Map<string, any>();
      if (resolvedConfig.registry) {
        for (const [key, entry] of Object.entries(resolvedConfig.registry)) {
          assetsMap.set(key, Object.freeze(entry));
        }
      }
      const assets: ReadonlyMap<string, Readonly<any>> = Object.freeze(assetsMap);

      const result = await executeCompileOnlyOutput(compileOnlyRegistry, {
        formatId,
        timeline: timeline as any,
        assets: assets as any,
        extensionId: fmt.extensionId,
      });

      if (!result) {
        setExportStatus('error');
        setExportLogState(`Export failed: format "${fmt.label}" is not available in the compile-only registry.`);
        return;
      }

      // Create a downloadable blob from the artifact data
      const mimeType = fmt.outputMimeType ?? 'application/octet-stream';
      const blob = new Blob([result.data], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const filename = `export.${fmt.outputExtension}`;

      setExportResultUrl(url);
      setExportResultFilename(filename);
      setExportStatus('done');
      const diagCount = result.artifact.diagnostics?.length ?? 0;
      setExportLogState(
        `Export complete: "${fmt.label}" → ${filename}` +
        (result.hasBlockingErrors ? ' (with blocking errors)' : '') +
        (diagCount > 0 ? ` [${diagCount} diagnostic(s)]` : ''),
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setExportStatus('error');
      setExportLogState(`Export failed: ${message}`);
    }
  }, [
    resolvedConfig,
    extensionRuntime,
    processResultAttachRecords,
    processStatuses,
    runExportGuard,
  ]);

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
    // M6: Export state
    exportStatus,
    exportLog,
    exportResultUrl,
    exportResultFilename,
    exportFormats,
    startExport,
  };
}
