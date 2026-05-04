import { memo } from 'react';
import AssetPanel from '@/tools/video-editor/components/PropertiesPanel/AssetPanel';
import {
  useTimelineEditorData,
  useTimelineEditorOps,
} from '@/tools/video-editor/hooks/timelineStore';
import {
  useVideoEditorAssetPanels,
  useVideoEditorRenderContext,
} from '@/tools/video-editor/runtime/useVideoEditorRenderContext';

export interface VideoEditorAssetPanelSurfaceProps {
  includeBuiltIn?: boolean;
}

function VideoEditorAssetPanelSurfaceComponent({
  includeBuiltIn = true,
}: VideoEditorAssetPanelSurfaceProps) {
  const renderContext = useVideoEditorRenderContext();
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

  return (
    <div className="flex flex-col gap-3">
      {builtInPanel}
      {assetPanels.map((panel) => (
        <div key={panel.id} data-video-editor-panel-id={panel.id}>
          {panel.render(renderContext)}
        </div>
      ))}
    </div>
  );
}

export const VideoEditorAssetPanelSurface = memo(VideoEditorAssetPanelSurfaceComponent);
