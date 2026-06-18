import type { ReactNode } from 'react';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import type {
  TimelineChromeContextValue,
  TimelineEditorDataContextValue,
  TimelineEditorOpsContextValue,
  TimelinePlaybackContextValue,
} from '@/tools/video-editor/hooks/useTimelineState.types.ts';
import type {
  ReighExtension,
  ExtensionContribution,
  ExtensionDiagnostic,
  ContributionKind,
} from '@reigh/editor-sdk';
import { contributionKindNotYetBridged } from '@reigh/editor-sdk';

export type VideoEditorSlotName =
  | 'header'
  | 'toolbar'
  | 'leftPanel'
  | 'rightPanel'
  | 'timelineFooter'
  | 'statusBar'
  | 'dialogs'
  | 'assetPanel'
  | 'inspectorPanel';

export interface VideoEditorRuntimeSlices {
  data: TimelineEditorDataContextValue;
  ops: TimelineEditorOpsContextValue;
  chrome: TimelineChromeContextValue;
  playback: TimelinePlaybackContextValue;
}

export interface VideoEditorRenderContext extends VideoEditorRuntimeSlices {
  provider: DataProvider;
  timelineId: string;
  timelineName: string | null;
  userId: string;
  extensions: VideoEditorExtensionRuntimeConfig;
}

export type VideoEditorVisibilityPredicate = (context: VideoEditorRenderContext) => boolean;
export type VideoEditorSlotRenderer = (context: VideoEditorRenderContext) => ReactNode;

export interface VideoEditorDialogDescriptor {
  id: string;
  order?: number;
  layer?: 'modal' | 'overlay';
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorPanelDescriptor {
  id: string;
  placement: 'asset-panel';
  order?: number;
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorInspectorSectionDescriptor {
  id: string;
  placement: 'before-default' | 'after-default';
  order?: number;
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorPanelRegistryConfig {
  panels?: readonly VideoEditorPanelDescriptor[];
  inspectorSections?: readonly VideoEditorInspectorSectionDescriptor[];
}

export interface VideoEditorDialogHostConfig {
  dialogs?: readonly VideoEditorDialogDescriptor[];
}

export interface VideoEditorExtensionConfig {
  slots?: Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>>;
  dialogHost?: VideoEditorDialogHostConfig;
  registry?: VideoEditorPanelRegistryConfig;
}

export interface VideoEditorExtensionRuntimeConfig {
  slots: Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>>;
  dialogHost: {
    dialogs: readonly VideoEditorDialogDescriptor[];
  };
  registry: {
    panels: readonly VideoEditorPanelDescriptor[];
    inspectorSections: readonly VideoEditorInspectorSectionDescriptor[];
  };
}

export interface ResolvedVideoEditorPanelRegistry {
  assetPanels: readonly VideoEditorPanelDescriptor[];
  inspectorSections: {
    all: readonly VideoEditorInspectorSectionDescriptor[];
    beforeDefault: readonly VideoEditorInspectorSectionDescriptor[];
    afterDefault: readonly VideoEditorInspectorSectionDescriptor[];
  };
}

// ---------------------------------------------------------------------------
// Host-owned runtime normalization types
// ---------------------------------------------------------------------------

/** A contribution that was declared but is not yet bridged in this runtime. */
export interface InactiveReservedContribution {
  extensionId: string;
  contributionId: string;
  kind: ContributionKind;
  /** The earliest milestone that activates this kind. */
  milestone: string;
}

/**
 * The normalized, frozen result of host-owned extension runtime normalization.
 * Produced by {@link normalizeExtensionRuntime} and scoped to a provider render.
 */
export interface ExtensionRuntime {
  /** The rendered runtime config consumed by shell chrome and slots. */
  readonly config: VideoEditorExtensionRuntimeConfig;
  /** All enabled extensions in deterministic order. */
  readonly extensions: readonly ReighExtension[];
  /** Structured diagnostics from registration (duplicates, validation, etc.). */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /** Contributions whose kind is not yet bridged in this runtime. */
  readonly inactiveReserved: readonly InactiveReservedContribution[];
  /** Set of contribution IDs that are known to have render declarations. */
  readonly knownRenderIds: ReadonlySet<string>;
  /** Extension-scoped settings defaults keyed by extension ID. */
  readonly settingsDefaults: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
}

/** Signature for host-owned runtime normalization. */
export type ExtensionHost = (extensions: readonly ReighExtension[]) => ExtensionRuntime;

const EMPTY_SLOTS: Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>> = Object.freeze({});
const EMPTY_DIALOGS: readonly VideoEditorDialogDescriptor[] = Object.freeze([]);
const EMPTY_PANELS: readonly VideoEditorPanelDescriptor[] = Object.freeze([]);
const EMPTY_INSPECTOR_SECTIONS: readonly VideoEditorInspectorSectionDescriptor[] = Object.freeze([]);
const EMPTY_RESOLVED_PANEL_REGISTRY: ResolvedVideoEditorPanelRegistry = Object.freeze({
  assetPanels: EMPTY_PANELS,
  inspectorSections: Object.freeze({
    all: EMPTY_INSPECTOR_SECTIONS,
    beforeDefault: EMPTY_INSPECTOR_SECTIONS,
    afterDefault: EMPTY_INSPECTOR_SECTIONS,
  }),
});

export const DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME: VideoEditorExtensionRuntimeConfig = Object.freeze({
  slots: EMPTY_SLOTS,
  dialogHost: Object.freeze({
    dialogs: EMPTY_DIALOGS,
  }),
  registry: Object.freeze({
    panels: EMPTY_PANELS,
    inspectorSections: EMPTY_INSPECTOR_SECTIONS,
  }),
});

/**
 * Host-owned runtime normalization: converts a list of ReighExtension objects
 * into a frozen, deterministic, provider-scoped {@link ExtensionRuntime}.
 *
 * - Preserves {@link DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME} identity when
 *   the extension list is empty or all contributions are inactive/reserved.
 * - Detects duplicate extension IDs and duplicate contribution IDs (both
 *   intra-extension and cross-extension) and emits structured diagnostics.
 * - Separates bridged M1 contributions (slot, dialog, panel, inspectorSection)
 *   from reserved future kinds (effect, transition, clipType, parser, agentTool,
 *   agent) and collects the latter as inactive reserved metadata.
 * - Orders contributions deterministically: by `order` ascending, then by
 *   contribution ID alphabetically. (Built-in priority is reserved for a
 *   future flag.)
 * - Collects known render IDs and extension-scoped settings defaults.
 * - Freezes the returned runtime and all nested objects.
 */
export function normalizeExtensionRuntime(
  extensions: readonly ReighExtension[],
): ExtensionRuntime {
  // ---- Empty fast path: preserve the default empty identity ----------------
  if (extensions.length === 0) {
    return EMPTY_EXTENSION_RUNTIME;
  }

  // ---- Phase 1: validate extension IDs, detect duplicates ------------------
  const diagnostics: ExtensionDiagnostic[] = [];
  const seenExtensionIds = new Set<string>();
  const uniqueExtensions: ReighExtension[] = [];

  for (const ext of extensions) {
    const id = ext.manifest.id as string;
    if (seenExtensionIds.has(id)) {
      diagnostics.push({
        severity: 'error',
        code: 'runtime/duplicate-extension',
        message: `Duplicate extension ID "${id}". Only the first occurrence will be used.`,
        extensionId: id,
      });
    } else {
      seenExtensionIds.add(id);
      uniqueExtensions.push(ext);
    }
  }

  // ---- Phase 2: collect contributions, detect duplicate contribution IDs ----
  interface CollectedContribution {
    contribution: ExtensionContribution;
    extensionId: string;
  }

  const bridged: CollectedContribution[] = [];
  const inactiveReserved: InactiveReservedContribution[] = [];
  const knownRenderIds = new Set<string>();
  const settingsDefaults: Record<string, Record<string, unknown>> = {};

  const seenContributionIds = new Map<string, string>(); // contribId -> extensionId

  for (const ext of uniqueExtensions) {
    const extId = ext.manifest.id as string;

    // Settings defaults — each extension gets its declared defaults, frozen
    settingsDefaults[extId] = ext.manifest.settingsDefaults
      ? { ...ext.manifest.settingsDefaults }
      : {};

    const contribs = ext.manifest.contributions ?? [];
    for (const contrib of contribs) {
      const contribId = contrib.id as string;

      // Cross-extension duplicate detection
      const existingOwner = seenContributionIds.get(contribId);
      if (existingOwner !== undefined) {
        diagnostics.push({
          severity: 'error',
          code: 'runtime/duplicate-contribution',
          message:
            `Duplicate contribution ID "${contribId}" in extension "${extId}" ` +
            `(already declared by "${existingOwner}"). Skipping.`,
          extensionId: extId,
          contributionId: contribId,
        });
        continue;
      }
      seenContributionIds.set(contribId, extId);

      // Check if the contribution kind is bridged in M1
      const notYetBridged = contributionKindNotYetBridged(contrib.kind);
      if (notYetBridged !== null) {
        inactiveReserved.push({
          extensionId: extId,
          contributionId: contribId,
          kind: contrib.kind,
          milestone: notYetBridged,
        });
        diagnostics.push({
          severity: 'info',
          code: 'runtime/contribution-kind-not-yet-bridged',
          message:
            `Contribution "${contribId}" (kind: ${contrib.kind}) in extension "${extId}" ` +
            `is reserved for ${notYetBridged}.`,
          extensionId: extId,
          contributionId: contribId,
          milestone: notYetBridged,
        });
        // Still collect known render IDs even for inactive contributions
        if (contrib.render) {
          knownRenderIds.add(contrib.render);
        }
        continue;
      }

      bridged.push({ contribution: contrib, extensionId: extId });

      // Track known render IDs
      if (contrib.render) {
        knownRenderIds.add(contrib.render);
      }
    }
  }

  // ---- Phase 3: deterministic ordering -------------------------------------
  // Sort by order ascending, then by contribution ID alphabetically.
  // Built-in extensions are reserved for a future flag.
  const sorted = [...bridged].sort((a, b) => {
    const orderA = a.contribution.order ?? 0;
    const orderB = b.contribution.order ?? 0;
    if (orderA !== orderB) return orderA - orderB;
    return (a.contribution.id as string).localeCompare(b.contribution.id as string);
  });

  // ---- Phase 4: project onto VideoEditorExtensionRuntimeConfig --------------
  const slots: Record<string, VideoEditorSlotRenderer> = {};
  const dialogDescriptors: VideoEditorDialogDescriptor[] = [];
  const panelDescriptors: VideoEditorPanelDescriptor[] = [];
  const inspectorSectionDescriptors: VideoEditorInspectorSectionDescriptor[] = [];

  for (const { contribution, extensionId } of sorted) {
    switch (contribution.kind) {
      case 'slot': {
        if (contribution.slot) {
          // Slots are rendered by the host; we register a placeholder that
          // extension activation can replace with a real render function.
          // For now, slots collect metadata without render functions.
          // (Render functions are wired during activation in a later task.)
          slots[contribution.slot] = slots[contribution.slot] ?? (null as unknown as VideoEditorSlotRenderer);
        }
        break;
      }
      case 'dialog': {
        dialogDescriptors.push({
          id: contribution.id as VideoEditorDialogDescriptor['id'],
          order: contribution.order,
          layer: contribution.layer,
          render: null as unknown as VideoEditorSlotRenderer, // placeholder
        });
        break;
      }
      case 'panel': {
        panelDescriptors.push({
          id: contribution.id as VideoEditorPanelDescriptor['id'],
          placement: 'asset-panel',
          order: contribution.order,
          render: null as unknown as VideoEditorSlotRenderer, // placeholder
        });
        break;
      }
      case 'inspectorSection': {
        inspectorSectionDescriptors.push({
          id: contribution.id as VideoEditorInspectorSectionDescriptor['id'],
          placement: contribution.placement ?? 'after-default',
          order: contribution.order,
          render: null as unknown as VideoEditorSlotRenderer, // placeholder
        });
        break;
      }
    }
  }

  // ---- Phase 5: assemble and freeze ----------------------------------------
  const hasAnyBridged =
    Object.keys(slots).length > 0 ||
    dialogDescriptors.length > 0 ||
    panelDescriptors.length > 0 ||
    inspectorSectionDescriptors.length > 0;

  const config: VideoEditorExtensionRuntimeConfig = hasAnyBridged
    ? Object.freeze({
        slots: Object.freeze(slots) as Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>>,
        dialogHost: Object.freeze({
          dialogs: Object.freeze(dialogDescriptors),
        }),
        registry: Object.freeze({
          panels: Object.freeze(panelDescriptors),
          inspectorSections: Object.freeze(inspectorSectionDescriptors),
        }),
      })
    : DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME;

  const runtime: ExtensionRuntime = Object.freeze({
    config,
    extensions: Object.freeze([...uniqueExtensions]),
    diagnostics: Object.freeze(diagnostics),
    inactiveReserved: Object.freeze(inactiveReserved),
    knownRenderIds: Object.freeze(new Set(knownRenderIds)),
    settingsDefaults: Object.freeze(
      Object.fromEntries(
        Object.entries(settingsDefaults).map(([k, v]) => [k, Object.freeze(v)]),
      ),
    ),
  });

  return runtime;
}

/** Frozen empty runtime, preserving {@link DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME} identity. */
const EMPTY_EXTENSION_RUNTIME: ExtensionRuntime = Object.freeze({
  config: DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME,
  extensions: Object.freeze([]),
  diagnostics: Object.freeze([]),
  inactiveReserved: Object.freeze([]),
  knownRenderIds: Object.freeze(new Set<string>()),
  settingsDefaults: Object.freeze({}),
});

type RegistryDescriptor = {
  id: string;
  order?: number;
  when?: VideoEditorVisibilityPredicate;
};

function sortRegistryDescriptors<T extends RegistryDescriptor>(descriptors: readonly T[]) {
  return [...descriptors].sort((left, right) => {
    const leftOrder = left.order ?? 0;
    const rightOrder = right.order ?? 0;
    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder;
    }

    return left.id.localeCompare(right.id);
  });
}

function resolveVisibleRegistryDescriptors<T extends RegistryDescriptor>(
  descriptors: readonly T[],
  context: VideoEditorRenderContext,
) {
  if (descriptors.length === 0) {
    return EMPTY_PANELS as unknown as readonly T[];
  }

  return sortRegistryDescriptors(
    descriptors.filter((descriptor) => !descriptor.when || descriptor.when(context)),
  );
}

export function resolveVideoEditorPanelRegistry(
  registry: VideoEditorExtensionRuntimeConfig['registry'],
  context: VideoEditorRenderContext,
): ResolvedVideoEditorPanelRegistry {
  const assetPanels = resolveVisibleRegistryDescriptors(registry.panels, context);
  const inspectorSections = resolveVisibleRegistryDescriptors(registry.inspectorSections, context);

  if (assetPanels.length === 0 && inspectorSections.length === 0) {
    return EMPTY_RESOLVED_PANEL_REGISTRY;
  }

  const beforeDefault = inspectorSections.filter((descriptor) => descriptor.placement === 'before-default');
  const afterDefault = inspectorSections.filter((descriptor) => descriptor.placement === 'after-default');

  return {
    assetPanels,
    inspectorSections: {
      all: inspectorSections,
      beforeDefault,
      afterDefault,
    },
  };
}
