import { useCallback } from 'react';
import { useEditorSettings } from '@/tools/video-editor/settings/useEditorSettings.ts';

export type ClipTab = 'effects' | 'timing' | 'position' | 'audio' | 'text';

export interface EditorPreferences {
  scaleWidth: number;
  activeClipTab: ClipTab;
  assetPanel: {
    showAll: boolean;
    showHidden: boolean;
    hidden: string[];
  };
}

export const defaultPreferences: EditorPreferences = {
  scaleWidth: 160,
  activeClipTab: 'effects',
  assetPanel: {
    showAll: false,
    showHidden: false,
    hidden: [],
  },
};

export function useEditorPreferences(timelineId: string) {
  const [preferences, setPreferences] = useEditorSettings<EditorPreferences>(
    `video-editor:preferences:${timelineId}`,
    defaultPreferences,
  );

  const scale = 5;
  const scaleWidth = preferences.scaleWidth;

  const setScaleWidth = useCallback((updater: number | ((value: number) => number)) => {
    setPreferences((current) => ({
      ...current,
      scaleWidth: typeof updater === 'function' ? (updater as (value: number) => number)(current.scaleWidth) : updater,
    }));
  }, [setPreferences]);

  const setActiveClipTab = useCallback((tab: ClipTab) => {
    setPreferences((current) => ({
      ...current,
      activeClipTab: tab,
    }));
  }, [setPreferences]);

  const setAssetPanelState = useCallback((patch: Partial<EditorPreferences['assetPanel']>) => {
    setPreferences((current) => ({
      ...current,
      assetPanel: {
        ...current.assetPanel,
        ...patch,
      },
    }));
  }, [setPreferences]);

  return {
    preferences,
    scaleWidth,
    scale,
    setScaleWidth,
    setActiveClipTab,
    setAssetPanelState,
  };
}
