import { createContext, useContext } from 'react';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
import type {
  VideoEditorAssetResolver,
  VideoEditorExporter,
  VideoEditorHostContext,
} from '@/tools/video-editor/lib/browser-runtime';
import type {
  VideoEditorAgentChatHost,
  VideoEditorAuthHost,
  VideoEditorMediaLightboxHost,
  VideoEditorProjectHost,
  VideoEditorShotsHost,
  VideoEditorTelemetryHost,
  VideoEditorToastHost,
} from '@/tools/video-editor/runtime/ports';
import type { VideoEditorExtensionRuntimeConfig } from '@/tools/video-editor/runtime/extensionSurface';

export interface VideoEditorRuntimeContextValue {
  provider: DataProvider;
  assetResolver: VideoEditorAssetResolver;
  auth: VideoEditorAuthHost;
  project: VideoEditorProjectHost;
  shots: VideoEditorShotsHost;
  mediaLightbox: VideoEditorMediaLightboxHost;
  agentChat: VideoEditorAgentChatHost;
  toast: VideoEditorToastHost;
  telemetry: VideoEditorTelemetryHost;
  timelineId: string;
  userId: string | null;
  timelineName?: string | null;
  exporter?: VideoEditorExporter | null;
  hostContext?: VideoEditorHostContext | null;
  extensions: VideoEditorExtensionRuntimeConfig;
}

const DataProviderContext = createContext<VideoEditorRuntimeContextValue | null>(null);

export function DataProviderWrapper({
  value,
  children,
}: {
  value: VideoEditorRuntimeContextValue;
  children: React.ReactNode;
}) {
  return (
    <DataProviderContext.Provider value={value}>
      {children}
    </DataProviderContext.Provider>
  );
}

export function useVideoEditorRuntime(): VideoEditorRuntimeContextValue {
  const context = useContext(DataProviderContext);
  if (!context) {
    throw new Error('useVideoEditorRuntime must be used within DataProviderWrapper');
  }

  return context;
}
