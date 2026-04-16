import { useCallback, useEffect, useMemo } from 'react';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';
import { deepEqual } from '@/shared/lib/utils/deepEqual';
import { createEntityStore, type EntityStoreApi } from '@/shared/state/createEntityStore';

import {
  type LastUsedEditSettings,
  type VideoEditSubMode,
  type PanelMode,
  DEFAULT_LAST_USED,
} from '../model/editSettingsTypes';

export type { LastUsedEditSettings, VideoEditSubMode, PanelMode };

const STORAGE_KEY_PROJECT = (projectId: string) => `lightbox-edit-last-used-${projectId}`;
const STORAGE_KEY_GLOBAL = 'lightbox-edit-last-used-global';
const DISABLED_ENTITY_ID = '__lightbox-last-used-disabled__';
const LAST_USED_DOMAIN_KEY = 'lightbox-last-used-edit-settings';

interface UseLastUsedEditSettingsReturn {
  lastUsed: LastUsedEditSettings;
  updateLastUsed: (settings: Partial<LastUsedEditSettings>) => void;
  isLoading: boolean;
}

interface UseLastUsedEditSettingsProps {
  projectId: string | null;
  enabled?: boolean;
}

interface LastUsedStoreRuntime {
  updateDbSettingsRef: {
    current: ((scope: 'user' | 'project' | 'shot', settings: Partial<LastUsedEditSettings>) => Promise<void>) | null;
  };
}

function hasSettingsChanged(prev: LastUsedEditSettings, next: LastUsedEditSettings): boolean {
  return !deepEqual(prev, next);
}

function readLocalStorageSettings(projectId: string | null): LastUsedEditSettings {
  if (!projectId) {
    return DEFAULT_LAST_USED;
  }

  try {
    const projectStored = localStorage.getItem(STORAGE_KEY_PROJECT(projectId));
    if (projectStored) {
      return { ...DEFAULT_LAST_USED, ...JSON.parse(projectStored) };
    }

    const globalStored = localStorage.getItem(STORAGE_KEY_GLOBAL);
    if (globalStored) {
      return { ...DEFAULT_LAST_USED, ...JSON.parse(globalStored) };
    }
  } catch {
    // Ignore storage corruption and fall back to defaults.
  }

  return DEFAULT_LAST_USED;
}

function writeLocalStorageSettings(projectId: string, settings: LastUsedEditSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY_PROJECT(projectId), JSON.stringify(settings));
    localStorage.setItem(STORAGE_KEY_GLOBAL, JSON.stringify(settings));
  } catch {
    // Ignore storage write failures; DB sync remains best effort.
  }
}

let lastUsedStoreCache:
  | {
      store: EntityStoreApi<LastUsedEditSettings>;
      runtime: LastUsedStoreRuntime;
    }
  | null = null;

function getLastUsedStore(): {
  store: EntityStoreApi<LastUsedEditSettings>;
  runtime: LastUsedStoreRuntime;
} {
  if (lastUsedStoreCache) {
    return lastUsedStoreCache;
  }

  const runtime: LastUsedStoreRuntime = {
    updateDbSettingsRef: { current: null },
  };

  const store = createEntityStore<LastUsedEditSettings>({
    toolId: LAST_USED_DOMAIN_KEY,
    defaults: DEFAULT_LAST_USED,
    load: async (entityId) => ({
      db: null,
      lastUsed: entityId === DISABLED_ENTITY_ID ? null : readLocalStorageSettings(entityId),
    }),
    save: async (entityId, data) => {
      if (entityId === DISABLED_ENTITY_ID) {
        return;
      }

      writeLocalStorageSettings(entityId, data);
      try {
        await runtime.updateDbSettingsRef.current?.('user', data);
      } catch {
        // Preserve local writes even if cross-device sync fails.
      }
    },
  });

  lastUsedStoreCache = { store, runtime };
  return lastUsedStoreCache;
}

export function useLastUsedEditSettings({
  projectId,
  enabled = true,
}: UseLastUsedEditSettingsProps): UseLastUsedEditSettingsReturn {
  const entityId = enabled && projectId ? projectId : null;
  const activeEntityId = entityId ?? DISABLED_ENTITY_ID;
  const { store, runtime } = useMemo(() => getLastUsedStore(), []);

  const {
    settings: dbSettings,
    isLoading: isDbLoading,
    update: updateDbSettings,
  } = useToolSettings<LastUsedEditSettings>(SETTINGS_IDS.LIGHTBOX_EDIT, {
    projectId: projectId || undefined,
    enabled: enabled && !!projectId,
  });

  runtime.updateDbSettingsRef.current = updateDbSettings;

  const entity = store.useEntity(activeEntityId);
  const storeState = store.getState();
  const bootstrapEntity = storeState.bootstrapEntity;
  const updateStoredFields = storeState.updateFields;
  const saveStoredEntityImmediately = storeState.saveImmediate;
  const reloadStoredEntity = storeState.reloadEntity;
  const fallbackLastUsed = useMemo(
    () => (entityId ? readLocalStorageSettings(entityId) : DEFAULT_LAST_USED),
    [entityId]
  );

  useEffect(() => {
    if (!entityId) {
      return;
    }

    void reloadStoredEntity(entityId).catch(() => {});
  }, [entityId, reloadStoredEntity]);

  useEffect(() => {
    if (!entityId) {
      return;
    }

    const localSettings = readLocalStorageSettings(entityId);
    const dbSnapshot = dbSettings ? { ...localSettings, ...dbSettings } : null;
    const currentEntity = store.getState().entities[entityId];
    const nextSeed = dbSnapshot ?? localSettings;

    if (
      currentEntity
      && currentEntity.loaded
      && currentEntity.hasPersistedData === (dbSnapshot !== null)
      && deepEqual(currentEntity.cleanSnapshot, nextSeed)
    ) {
      return;
    }

    bootstrapEntity({
      entityId,
      db: dbSnapshot,
      lastUsed: localSettings,
    });
  }, [bootstrapEntity, dbSettings, entityId, store]);

  const updateLastUsed = useCallback((updates: Partial<LastUsedEditSettings>) => {
    if (!entityId) {
      return;
    }

    const currentSettings = store.getState().entities[entityId]?.settings ?? readLocalStorageSettings(entityId);
    const nextSettings = { ...currentSettings, ...updates };
    if (!hasSettingsChanged(currentSettings, nextSettings)) {
      return;
    }

    updateStoredFields(entityId, updates);
    void saveStoredEntityImmediately(entityId).catch(() => {});
  }, [entityId, saveStoredEntityImmediately, store, updateStoredFields]);

  const currentEntity = entityId ? store.getState().entities[entityId] : undefined;
  const lastUsed = entityId
    ? (currentEntity?.loaded ? entity.settings : fallbackLastUsed)
    : DEFAULT_LAST_USED;

  return useMemo(() => ({
    lastUsed,
    updateLastUsed,
    isLoading: !!entityId && isDbLoading,
  }), [entityId, isDbLoading, lastUsed, updateLastUsed]);
}
