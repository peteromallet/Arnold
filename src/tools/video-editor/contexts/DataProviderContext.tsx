import { createContext, useContext } from 'react';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import type {
  VideoEditorAssetResolver,
  VideoEditorExporter,
  VideoEditorHostContext,
} from '@/tools/video-editor/lib/browser-runtime.ts';
import type {
  VideoEditorAgentChatHost,
  VideoEditorAuthHost,
  VideoEditorMediaLightboxHost,
  VideoEditorProjectHost,
  VideoEditorShotsHost,
  VideoEditorTelemetryHost,
  VideoEditorToastHost,
} from '@/tools/video-editor/runtime/ports.ts';
import type {
  VideoEditorExtensionRuntimeConfig,
  ExtensionRuntime,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { CommandRegistry } from '@/tools/video-editor/runtime/commandRegistry.ts';
import type { AgentToolRegistry } from '@/tools/video-editor/runtime/agentToolRegistry.ts';
import type { DiagnosticCollection } from '@reigh/editor-sdk';
import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
import type { LivePermissionService } from '@/tools/video-editor/runtime/livePermissions.ts';
import type { ExtensionStateRepository } from '@/tools/video-editor/runtime/extensionStateRepository';
import type { ExtensionSettingsNotificationRegistry } from '@/tools/video-editor/runtime/extensionSettingsNotification';

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
  extensionRuntime?: ExtensionRuntime;
  /** M4: Provider-scoped command registry (commands, keybindings, context menus). */
  commandRegistry?: CommandRegistry;
  /** M10: Provider-scoped agent tool registry for host-mediated, proposal-backed agent tools. */
  agentToolRegistry?: AgentToolRegistry;
  /** M11: Provider-scoped live data registry for source lifecycle, channels, samples, and bake. */
  liveDataRegistry?: LiveDataRegistry;
  /** M11: Provider-scoped live permission service for browser-gated permission probes/requests. */
  livePermissionService?: LivePermissionService;
  /** Provider-scoped diagnostics surfaced by status and diagnostic panels. */
  diagnosticCollection?: DiagnosticCollection;
  /** M5: Extension state repository for enable/disable persistence. */
  extensionStateRepository?: ExtensionStateRepository | null;
  /** M5: Trigger extension re-resolution after persistence writes. */
  triggerExtensionRefresh?: () => void;
  /** T9: Host-visible settings notification registry for manager/runtime coherence. */
  settingsNotificationRegistry?: ExtensionSettingsNotificationRegistry;
  /** M5: Recovery key facade backed by ExtensionLifecycleHost.
   *  Returns the current monotonic recovery key for an extension, or "0"
   *  for unknown/disposed extension IDs. */
  getRecoveryKey?: (extensionId: string) => string;
  /** M5: Increment the recovery key for an extension and return the new key.
   *  This is the programmatic retry signal for ContributionErrorBoundary.
   *  No-op for unknown/disposed extension IDs (returns "0"). */
  incrementRecoveryKey?: (extensionId: string) => string;
}

export const DataProviderContext = createContext<VideoEditorRuntimeContextValue | null>(null);

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

export function useOptionalVideoEditorRuntime(): VideoEditorRuntimeContextValue | null {
  return useContext(DataProviderContext);
}
