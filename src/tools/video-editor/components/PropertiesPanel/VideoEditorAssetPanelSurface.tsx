import { memo } from 'react';
import AssetPanel from '@/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx';
import {
  useTimelineEditorData,
  useTimelineEditorOps,
} from '@/tools/video-editor/hooks/timelineStore.ts';
import {
  useVideoEditorAssetPanels,
  useVideoEditorRenderContext,
} from '@/tools/video-editor/runtime/useVideoEditorRenderContext.ts';
import { useOptionalVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import {
  HostContributionErrorBoundary,
  type ContributionErrorInfo,
} from '@/tools/video-editor/runtime/ContributionErrorBoundary.tsx';

export interface VideoEditorAssetPanelSurfaceProps {
  includeBuiltIn?: boolean;
}

function VideoEditorAssetPanelSurfaceComponent({
  includeBuiltIn = true,
}: VideoEditorAssetPanelSurfaceProps) {
  const renderContext = useVideoEditorRenderContext();
  const runtime = useOptionalVideoEditorRuntime();
  const ownerMap = runtime?.extensionRuntime?.contributionOwnerMap;
  const assetPanels = useVideoEditorAssetPanels();
  const { data, preferences } = useTimelineEditorData();
  const { setAssetPanelState, uploadFiles } = useTimelineEditorOps();

  const builtInPanel = includeBuiltIn && data ? (
    <div className="rounded-xl border border-border bg-card/80 p-3">
      <AssetPanel
        assetMap={data.assetMap}
        rows={data.rows}
        meta={data.meta}
        backgroundAsset={data.output.background ?? undefined}
        showAll={preferences.assetPanel.showAll}
        showHidden={preferences.assetPanel.showHidden}
        hidden={preferences.assetPanel.hidden}
        setPanelState={setAssetPanelState}
        onUploadFiles={uploadFiles}
        registry={data.registry.assets}
      />
    </div>
  ) : null;

  if (!builtInPanel && assetPanels.length === 0) {
    return null;
  }

  const handleContributionError = (info: ContributionErrorInfo) => {
    if (typeof console !== 'undefined') {
      console.warn(
        '[VideoEditorAssetPanelSurface] Panel error captured by boundary:',
        info,
      );
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {builtInPanel}
      {assetPanels.map((panel) => (
        <HostContributionErrorBoundary
          key={panel.id}
          contributionId={panel.id}
          extensionId={ownerMap?.get(panel.id)}
          kind="panel"
          onError={handleContributionError}
        >
          <div data-video-editor-panel-id={panel.id}>
            {panel.render(renderContext)}
          </div>
        </HostContributionErrorBoundary>
      ))}
    </div>
  );
}

export const VideoEditorAssetPanelSurface = memo(VideoEditorAssetPanelSurfaceComponent);
