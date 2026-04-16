import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  extractSettingsFromCache,
  updateToolSettingsSupabase,
  useToolSettings,
} from '@/shared/hooks/settings/useToolSettings';
import { joinClipsSettings, type JoinClipsSettings } from '@/shared/lib/joinClips/defaults';
import { queryKeys } from '@/shared/lib/queryKeys';
import { TOOL_IDS } from '@/shared/lib/tooling/toolIds';
import { deepEqual } from '@/shared/lib/utils/deepEqual';
import { createEntityStore } from '@/shared/state/createEntityStore';

const DISABLED_ENTITY_ID = '__join-clips-disabled__';

function cloneSettings(settings: JoinClipsSettings): JoinClipsSettings {
  return structuredClone(settings);
}

function getSettingsQueryKey(projectId: string) {
  return queryKeys.settings.tool(TOOL_IDS.JOIN_CLIPS, projectId, undefined);
}

function readCachedSettings(
  queryClient: QueryClient | null,
  projectId: string
): JoinClipsSettings | null {
  if (!queryClient) {
    return null;
  }

  const cached = extractSettingsFromCache<JoinClipsSettings>(
    queryClient.getQueryData(getSettingsQueryKey(projectId))
  );

  return cached ? cloneSettings(cached) : null;
}

function writeCachedSettings(queryClient: QueryClient | null, projectId: string, settings: JoinClipsSettings): void {
  if (!queryClient) {
    return;
  }

  queryClient.setQueryData(getSettingsQueryKey(projectId), {
    settings: cloneSettings(settings),
    hasShotSettings: false,
  });
}

const joinClipsStoreRuntime = {
  queryClient: null as QueryClient | null,
  authoritativeSettings: new Map<string, JoinClipsSettings>(),
};

const joinClipsStore = createEntityStore<JoinClipsSettings>({
  toolId: TOOL_IDS.JOIN_CLIPS,
  defaults: joinClipsSettings.defaults,
  load: async (entityId) => {
    if (entityId === DISABLED_ENTITY_ID) {
      return { db: null, lastUsed: null };
    }

    const authoritative =
      joinClipsStoreRuntime.authoritativeSettings.get(entityId)
      ?? readCachedSettings(joinClipsStoreRuntime.queryClient, entityId);

    return {
      db: authoritative ? cloneSettings(authoritative) : null,
      lastUsed: null,
    };
  },
  save: async (entityId, data) => {
    if (entityId === DISABLED_ENTITY_ID) {
      return;
    }

    const snapshot = cloneSettings(data);

    await updateToolSettingsSupabase(
      {
        scope: 'project',
        id: entityId,
        toolId: TOOL_IDS.JOIN_CLIPS,
        patch: snapshot,
      },
      { mode: 'immediate' }
    );

    joinClipsStoreRuntime.authoritativeSettings.set(entityId, snapshot);
    writeCachedSettings(joinClipsStoreRuntime.queryClient, entityId, snapshot);
    await joinClipsStoreRuntime.queryClient?.invalidateQueries({
      queryKey: getSettingsQueryKey(entityId),
    });
  },
});

/**
 * Hook for managing Join Clips tool settings at the project level.
 * Local edits live in the entity store; authoritative merged reads still come from useToolSettings.
 */
export function useJoinClipsSettings(projectId: string | null | undefined) {
  const queryClient = useQueryClient();
  joinClipsStoreRuntime.queryClient = queryClient;

  const isRealEntity = !!projectId;
  const entityId = isRealEntity ? projectId : DISABLED_ENTITY_ID;
  const authoritative = useToolSettings<JoinClipsSettings>(TOOL_IDS.JOIN_CLIPS, {
    projectId: isRealEntity ? projectId : undefined,
    enabled: isRealEntity,
  });
  const localEntity = joinClipsStore.useEntity(entityId);
  const [reconciledEntityId, setReconciledEntityId] = useState<string | null>(null);
  const activeEntityRef = useRef<string | null>(isRealEntity ? projectId : null);

  useEffect(() => {
    activeEntityRef.current = isRealEntity ? projectId : null;
  }, [isRealEntity, projectId]);

  useEffect(() => {
    if (!isRealEntity) {
      setReconciledEntityId(null);
      return;
    }

    setReconciledEntityId((current) => (current === projectId ? current : null));
  }, [isRealEntity, projectId]);

  useEffect(() => {
    if (!isRealEntity || !projectId) {
      return;
    }

    if (authoritative.isLoading) {
      return;
    }

    if (authoritative.error) {
      setReconciledEntityId(projectId);
      return;
    }

    const authoritativeSettings = cloneSettings(authoritative.settings ?? joinClipsSettings.defaults);
    const previousAuthoritativeSettings = joinClipsStoreRuntime.authoritativeSettings.get(projectId);
    joinClipsStoreRuntime.authoritativeSettings.set(projectId, authoritativeSettings);
    const currentEntity = joinClipsStore.getState().entities[projectId];
    const currentSettings = currentEntity?.settings ?? joinClipsSettings.defaults;

    if (
      previousAuthoritativeSettings
      && deepEqual(previousAuthoritativeSettings, authoritativeSettings)
    ) {
      if (
        currentEntity
        && !currentEntity.hasPersistedData
        && !deepEqual(currentSettings, authoritativeSettings)
      ) {
        const didSync = joinClipsStore.getState().syncExternalEntity({
          entityId: projectId,
          db: authoritativeSettings,
          lastUsed: null,
        });

        if (didSync) {
          setReconciledEntityId(projectId);
        }
        return;
      }

      setReconciledEntityId(projectId);
      return;
    }

    if (deepEqual(currentSettings, authoritativeSettings)) {
      setReconciledEntityId(projectId);
      return;
    }

    const didSync = joinClipsStore.getState().syncExternalEntity({
      entityId: projectId,
      db: authoritativeSettings,
      lastUsed: null,
    });

    if (didSync) {
      setReconciledEntityId(projectId);
    }
  }, [
    authoritative.error,
    authoritative.isLoading,
    authoritative.settings,
    isRealEntity,
    localEntity.settings,
    localEntity.status,
    projectId,
  ]);

  useEffect(() => {
    const currentEntityId = isRealEntity ? projectId : null;

    return () => {
      if (!currentEntityId) {
        return;
      }

      void joinClipsStore.getState().saveImmediate(currentEntityId);
    };
  }, [isRealEntity, projectId]);

  useEffect(() => {
    const handleBeforeUnload = () => {
      const currentEntityId = activeEntityRef.current;
      if (!currentEntityId) {
        return;
      }

      void joinClipsStore.getState().saveImmediate(currentEntityId);
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  const isReconciled = isRealEntity && reconciledEntityId === projectId;
  const resolvedStatus = useMemo(() => {
    if (!isRealEntity) {
      return 'idle' as const;
    }

    if (!isReconciled) {
      return 'loading' as const;
    }

    if (authoritative.error) {
      return 'error' as const;
    }

    return localEntity.status;
  }, [authoritative.error, isRealEntity, isReconciled, localEntity.status]);

  const resolvedError = useMemo(() => {
    if (!isRealEntity) {
      return null;
    }

    if (!isReconciled && !authoritative.error) {
      return null;
    }

    return authoritative.error ?? localEntity.error;
  }, [authoritative.error, isRealEntity, isReconciled, localEntity.error]);

  const storeApi = joinClipsStore.getState();

  const updateTextFields = useCallback((updates: Partial<JoinClipsSettings>) => {
    if (!isRealEntity || !projectId) {
      return;
    }

    for (const [key, value] of Object.entries(updates) as Array<
      [keyof JoinClipsSettings, JoinClipsSettings[keyof JoinClipsSettings]]
    >) {
      storeApi.updateTextField(projectId, key, value);
    }
  }, [isRealEntity, projectId, storeApi]);

  const saveImmediate = useCallback(async (dataToSave?: JoinClipsSettings) => {
    if (!isRealEntity || !projectId) {
      return;
    }

    if (dataToSave) {
      storeApi.updateFields(projectId, dataToSave);
    }

    await storeApi.saveImmediate(projectId);
  }, [isRealEntity, projectId, storeApi]);

  const reset = useCallback((nextSettings?: JoinClipsSettings) => {
    if (!isRealEntity || !projectId) {
      return;
    }

    storeApi.reset(projectId, nextSettings ?? joinClipsSettings.defaults);
  }, [isRealEntity, projectId, storeApi]);

  const noOpInitializeFrom = useCallback((_data: Partial<JoinClipsSettings>) => {}, []);

  if (!isRealEntity || !projectId) {
    return {
      settings: cloneSettings(joinClipsSettings.defaults),
      status: 'idle' as const,
      entityId: null,
      isDirty: false,
      error: null,
      hasShotSettings: false,
      hasPersistedData: false,
      updateField: <K extends keyof JoinClipsSettings>(_key: K, _value: JoinClipsSettings[K]) => {},
      updateFields: (_updates: Partial<JoinClipsSettings>) => {},
      updateTextField: <K extends keyof JoinClipsSettings>(_key: K, _value: JoinClipsSettings[K]) => {},
      updateTextFields: (_updates: Partial<JoinClipsSettings>) => {},
      save: async () => {},
      saveImmediate,
      revert: () => {},
      reset,
      initializeFrom: noOpInitializeFrom,
    };
  }

  return {
    settings: localEntity.settings,
    status: resolvedStatus,
    entityId: projectId,
    isDirty: storeApi.isDirty(projectId),
    error: resolvedError,
    hasShotSettings: authoritative.hasShotSettings,
    hasPersistedData: authoritative.hasShotSettings,
    updateField: localEntity.updateField,
    updateFields: localEntity.updateFields,
    updateTextField: localEntity.updateTextField,
    updateTextFields,
    save: localEntity.save,
    saveImmediate,
    revert: localEntity.revert,
    reset,
    initializeFrom: noOpInitializeFrom,
  };
}
