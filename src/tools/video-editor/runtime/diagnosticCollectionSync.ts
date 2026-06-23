import type {
  Diagnostic,
  DiagnosticCollection,
  ExtensionDiagnostic,
  LiveSourceDiagnostic,
} from '@reigh/editor-sdk';
import { DIAGNOSTIC_SOURCE_EXTENSION, getSettingsPrefix } from '@reigh/editor-sdk';
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
  // Extension-authored diagnostics carry provenance in two layers:
  // 1. The top-level Diagnostic.source is always set to
  //    DIAGNOSTIC_SOURCE_EXTENSION so that clean-up by extension ID
  //    scopes correctly without touching host-owned diagnostic sources.
  // 2. The caller may stash finer-grained info (e.g. 'fragment' for
  //    a shader stage) inside detail.source; we move that into
  //    diagnosticSource before the provider source overwrites
  //    detail.source.
  const callerDetailSource = detail.source;

  return {
    id: diagnosticId(source, diagnostic, index),
    severity: diagnostic.severity,
    code: diagnostic.code,
    message: diagnostic.message,
    source: DIAGNOSTIC_SOURCE_EXTENSION,
    ...(diagnostic.extensionId ? { extensionId: diagnostic.extensionId } : {}),
    ...(diagnostic.contributionId ? { contributionId: diagnostic.contributionId } : {}),
    ...(diagnostic.milestone ? { milestone: diagnostic.milestone } : {}),
    ...(diagnostic.sourceRange ? { sourceRange: diagnostic.sourceRange } : {}),
    ...(diagnostic.relatedRanges ? { relatedRanges: diagnostic.relatedRanges } : {}),
    detail: {
      ...detail,
      ...(callerDetailSource !== undefined ? { diagnosticSource: callerDetailSource } : {}),
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
  // Use removeByExtensionId to scope removal to extension-authored
  // diagnostics without touching host-owned diagnostic sources.
  collection?.removeByExtensionId(extensionId);
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


/**
 * Clear all localStorage settings keys for a given extension.
 *
 * This is the settings-derived UI state reset counterpart to
 * removeExtensionDiagnosticsFromCollection. Callers should invoke both from
 * the shared ExtensionLifecycleHost.onLifecycleDisposed callback to
 * guarantee that disable/unload clears the targeted extension's diagnostics
 * and settings UI state without touching unrelated extension state.
 */
export function clearExtensionSettingsFromLocalStorage(extensionId: string): void {
  const prefix = getSettingsPrefix(extensionId);
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const key = localStorage.key(i);
      if (key && key.startsWith(prefix)) {
        localStorage.removeItem(key);
      }
    }
  } catch {
    // localStorage unavailable — silently no-op
  }
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
