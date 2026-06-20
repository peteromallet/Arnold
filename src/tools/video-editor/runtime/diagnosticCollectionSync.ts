import type {
  Diagnostic,
  DiagnosticCollection,
  ExtensionDiagnostic,
  LiveSourceDiagnostic,
} from '@reigh/editor-sdk';
import type {
  CapabilityFinding,
  RenderBlocker,
} from '@/tools/video-editor/runtime/renderability.ts';

export type DiagnosticCollectionSource =
  | 'effect-registry'
  | 'extension-lifecycle'
  | 'command-registry'
  | 'transition-registry'
  | 'shader-effect-registry'
  | 'clip-type-registry'
  | 'live-registry'
  | 'export-guard'
  | 'render-planner';

type ExtensionDiagnosticWithRanges = ExtensionDiagnostic & Pick<Partial<Diagnostic>, 'sourceRange' | 'relatedRanges'>;

function diagnosticId(
  source: DiagnosticCollectionSource,
  diagnostic: ExtensionDiagnosticWithRanges,
  index: number,
): string {
  const detail = diagnostic.detail ?? {};
  return [
    source,
    diagnostic.code,
    diagnostic.extensionId ?? 'host',
    diagnostic.contributionId ?? 'runtime',
    detail.clipId ?? detail.effectType ?? detail.shaderId ?? detail.clipType ?? detail.transitionType ?? index,
  ].join(':');
}

export function extensionDiagnosticToCollectionDiagnostic(
  source: DiagnosticCollectionSource,
  diagnostic: ExtensionDiagnosticWithRanges,
  index: number,
): Diagnostic {
  const detail = diagnostic.detail ?? {};
  const originalSource = detail.source;

  return {
    id: diagnosticId(source, diagnostic, index),
    severity: diagnostic.severity,
    code: diagnostic.code,
    message: diagnostic.message,
    ...(diagnostic.extensionId ? { extensionId: diagnostic.extensionId } : {}),
    ...(diagnostic.contributionId ? { contributionId: diagnostic.contributionId } : {}),
    ...(diagnostic.milestone ? { milestone: diagnostic.milestone } : {}),
    ...(diagnostic.sourceRange ? { sourceRange: diagnostic.sourceRange } : {}),
    ...(diagnostic.relatedRanges ? { relatedRanges: diagnostic.relatedRanges } : {}),
    detail: {
      ...detail,
      ...(originalSource !== undefined ? { diagnosticSource: originalSource } : {}),
      source,
    },
  };
}

export function syncExtensionDiagnosticsToCollection(
  collection: DiagnosticCollection | undefined,
  source: DiagnosticCollectionSource,
  diagnostics: readonly ExtensionDiagnosticWithRanges[],
  options: { activeExtensionIds?: ReadonlySet<string> } = {},
): void {
  if (!collection) return;
  collection.remove((diagnostic) => diagnostic.detail?.source === source);
  const activeExtensionIds = options.activeExtensionIds;
  diagnostics.filter((diagnostic) => {
    if (!activeExtensionIds || !diagnostic.extensionId) return true;
    return activeExtensionIds.has(diagnostic.extensionId);
  }).forEach((diagnostic, index) => {
    collection.publish(extensionDiagnosticToCollectionDiagnostic(source, diagnostic, index));
  });
}

export function removeExtensionDiagnosticsFromCollection(
  collection: DiagnosticCollection | undefined,
  extensionId: string,
): void {
  collection?.remove((diagnostic) => diagnostic.extensionId === extensionId);
}

export function plannerFindingToDiagnostic(
  item: CapabilityFinding | RenderBlocker,
  index: number,
): Diagnostic {
  return {
    id: ['render-planner', item.id, index].join(':'),
    severity: item.severity,
    code: item.route ? `planner/${item.route}/${item.reason}` : `planner/${item.reason}`,
    message: item.message,
    ...(item.extensionId ? { extensionId: item.extensionId } : {}),
    ...(item.contributionId ? { contributionId: item.contributionId } : {}),
    detail: {
      ...(item.detail ?? {}),
      source: 'render-planner',
      route: item.route,
      reason: item.reason,
      clipId: item.clipId,
    },
  };
}

export function syncPlannerDiagnosticsToCollection(
  collection: DiagnosticCollection | undefined,
  items: readonly (CapabilityFinding | RenderBlocker)[],
): void {
  if (!collection) return;
  collection.remove((diagnostic) => diagnostic.detail?.source === 'render-planner');
  items.forEach((item, index) => {
    collection.publish(plannerFindingToDiagnostic(item, index));
  });
}


export function syncLiveDiagnosticsToCollection(
  collection: DiagnosticCollection | undefined,
  diagnostics: readonly LiveSourceDiagnostic[],
): void {
  if (!collection) return;
  collection.remove((diagnostic) => diagnostic.detail?.source === 'live-registry');
  diagnostics.forEach((diagnostic, index) => {
    const id = [
      'live-registry',
      diagnostic.code,
      diagnostic.sourceId ?? 'registry',
      diagnostic.channelId ?? 'runtime',
      index,
    ].join(':');
    collection.publish({
      id,
      severity: diagnostic.severity,
      code: diagnostic.code,
      message: diagnostic.message,
      detail: {
        ...(diagnostic.detail ?? {}),
        source: 'live-registry',
        ...(diagnostic.sourceId ? { sourceId: diagnostic.sourceId } : {}),
        ...(diagnostic.channelId ? { channelId: diagnostic.channelId } : {}),
      },
    });
  });
}
