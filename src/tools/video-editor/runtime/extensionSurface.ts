import type { ReactNode } from 'react';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import type {
  TimelineChromeContextValue,
  TimelineEditorDataContextValue,
  TimelineEditorOpsContextValue,
  TimelinePlaybackContextValue,
} from '@/tools/video-editor/hooks/useTimelineState.types.ts';

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

export function resolveVideoEditorExtensionRuntime(
  config?: VideoEditorExtensionConfig,
): VideoEditorExtensionRuntimeConfig {
  if (!config) {
    return DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME;
  }

  const slots = config.slots ? { ...config.slots } : EMPTY_SLOTS;
  const dialogs = config.dialogHost?.dialogs ? [...config.dialogHost.dialogs] : EMPTY_DIALOGS;
  const panels = config.registry?.panels ? [...config.registry.panels] : EMPTY_PANELS;
  const inspectorSections = config.registry?.inspectorSections
    ? [...config.registry.inspectorSections]
    : EMPTY_INSPECTOR_SECTIONS;

  return {
    slots,
    dialogHost: {
      dialogs,
    },
    registry: {
      panels,
      inspectorSections,
    },
  };
}

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
