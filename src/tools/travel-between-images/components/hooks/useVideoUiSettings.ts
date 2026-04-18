import { useCallback } from 'react';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';

/** Per-shot UI toggle persistence (accelerated mode, random seed). Own external hook dep. */
export function useVideoUiSettings(isOpen: boolean, shotId: string) {
  const { settings: shotUISettings, update: updateShotUISettings } = useToolSettings<{
    acceleratedMode?: boolean;
    randomSeed?: boolean;
  }>(SETTINGS_IDS.TRAVEL_UI_STATE, {
    shotId: isOpen ? shotId : undefined,
    enabled: isOpen && Boolean(shotId),
  });

  const accelerated = shotUISettings?.acceleratedMode ?? false;
  const randomSeed = shotUISettings?.randomSeed ?? false;

  const setAccelerated = useCallback(
    (value: boolean) => {
      updateShotUISettings('shot', { acceleratedMode: value });
    },
    [updateShotUISettings],
  );

  const setRandomSeed = useCallback(
    (value: boolean) => {
      updateShotUISettings('shot', { randomSeed: value });
    },
    [updateShotUISettings],
  );

  return { accelerated, randomSeed, setAccelerated, setRandomSeed };
}
