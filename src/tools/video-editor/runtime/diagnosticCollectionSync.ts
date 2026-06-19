import type {
  Diagnostic,
  DiagnosticCollection,
  ExtensionDiagnostic,
} from '@reigh/editor-sdk';
import type {
  CapabilityFinding,
  RenderBlocker,
} from '@/tools/video-editor/runtime/renderability.ts';

export type DiagnosticCollectionSource =
  | 'effect-registry'
  | 'extension-lifecycle'
  | 'command-registry'
  | 'clip-type-registry'
  | 'export-guard'
  | 'render-planner';

function diagnosticId(
  source: DiagnosticCollectionSource,
  diagnostic: ExtensionDiagnostic,
  index: number,
): string {
  const detail = diagnostic.detail ?? {};
  return [
    source,
    diagnostic.code,
    diagnostic.extensionId ?? 'host',
    diagnostic.contributionId ?? 'runtime',
    detail.clipId ?? detail.effectType ?? detail.clipType ?? detail.transitionType ?? index,
  ].join(':');
}

export function extensionDiagnosticToCollectionDiagnostic(
  source: DiagnosticCollectionSource,
  diagnostic: ExtensionDiagnostic,
  index: number,
): Diagnostic {
  return {
    id: diagnosticId(source, diagnostic, index),
    severity: diagnostic.severity,
    code: diagnostic.code,
    message: diagnostic.message,
    ...(diagnostic.extensionId ? { extensionId: diagnostic.extensionId } : {}),
    ...(diagnostic.contributionId ? { contributionId: diagnostic.contributionId } : {}),
    ...(diagnostic.milestone ? { milestone: diagnostic.milestone } : {}),
    detail: { ...(diagnostic.detail ?? {}), source },
  };
}

export function syncExtensionDiagnosticsToCollection(
  collection: DiagnosticCollection | undefined,
  source: DiagnosticCollectionSource,
  diagnostics: readonly ExtensionDiagnostic[],
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
