import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { useRenderLogger } from '@/shared/lib/debug/debugRendering';
import { deepEqual } from '@/shared/lib/utils/deepEqual';
import { createEntityStore, type EntityStoreApi } from '@/shared/state/createEntityStore';

type AutoSaveStatus = 'idle' | 'loading' | 'ready' | 'saving' | 'error';

interface CustomLoadSave<T> {
  load: (entityId: string) => Promise<T | null>;
  save: (entityId: string, data: T) => Promise<void>;
  entityId: string | null;
  domainKey?: string;
  onFlush?: (entityId: string, data: T) => void;
}

interface UseAutoSaveSettingsOptions<T> {
  toolId?: string;
  shotId?: string | null;
  projectId?: string | null;
  scope?: 'shot' | 'project';
  debounceMs?: number;
  defaults: T;
  enabled?: boolean;
  debug?: boolean;
  debugTag?: string;
  onSaveSuccess?: () => void;
  onSaveError?: (error: Error) => void;
  bootstrapData?: T | null;
  customLoadSave?: CustomLoadSave<T>;
}

interface UseAutoSaveSettingsReturn<T> {
  settings: T;
  status: AutoSaveStatus;
  entityId: string | null;
  isDirty: boolean;
  error: Error | null;
  hasShotSettings: boolean;
  hasPersistedData: boolean;
  updateField: <K extends keyof T>(key: K, value: T[K]) => void;
  updateFields: (updates: Partial<T>) => void;
  updateTextField: <K extends keyof T>(key: K, value: T[K]) => void;
  updateTextFields: (updates: Partial<T>) => void;
  save: () => Promise<void>;
  saveImmediate: (dataToSave?: T) => Promise<void>;
  revert: () => void;
  reset: (newDefaults?: T) => void;
  initializeFrom: (data: Partial<T>) => void;
}

interface AutoSaveStoreRuntime<T extends object> {
  mode: 'custom' | 'react-query';
  loadRef: { current: ((entityId: string) => Promise<T | null>) | null };
  saveRef: { current: ((entityId: string, data: T) => Promise<void>) | null };
  updateRef: { current: ((scope: 'shot' | 'project', settings: Partial<T>) => Promise<void>) | null };
  scopeRef: { current: 'shot' | 'project' };
  onSaveSuccessRef: { current: (() => void) | undefined };
  onSaveErrorRef: { current: ((error: Error) => void) | undefined };
  onFlushRef: { current: ((entityId: string, data: T) => void) | undefined };
  bootstrapRef: { current: T | null };
}

const DISABLED_ENTITY_ID = '__auto-save-settings-disabled__';
const autoSaveStoreRegistry = new Map<string, EntityStoreApi<any>>();
const autoSaveRuntimeRegistry = new Map<string, AutoSaveStoreRuntime<any>>();

function cloneValue<T>(value: T): T {
  return structuredClone(value);
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

function getDomainKey<T extends object>(
  toolId: string,
  scope: 'shot' | 'project',
  debounceMs: number,
  customLoadSave?: CustomLoadSave<T>
): string {
  if (customLoadSave) {
    return `custom:${customLoadSave.domainKey ?? toolId ?? 'default'}:${debounceMs}`;
  }

  return `tool:${toolId}:${scope}:${debounceMs}`;
}

function getStoreForDomain<T extends object>(
  domainKey: string,
  defaults: T,
  debounceMs: number,
  mode: 'custom' | 'react-query'
): {
  store: EntityStoreApi<T>;
  runtime: AutoSaveStoreRuntime<T>;
} {
  const existingStore = autoSaveStoreRegistry.get(domainKey) as EntityStoreApi<T> | undefined;
  const existingRuntime = autoSaveRuntimeRegistry.get(domainKey) as AutoSaveStoreRuntime<T> | undefined;

  if (existingStore && existingRuntime) {
    return { store: existingStore, runtime: existingRuntime };
  }

  const runtime: AutoSaveStoreRuntime<T> = {
    mode,
    loadRef: { current: null },
    saveRef: { current: null },
    updateRef: { current: null },
    scopeRef: { current: 'shot' },
    onSaveSuccessRef: { current: undefined },
    onSaveErrorRef: { current: undefined },
    onFlushRef: { current: undefined },
    bootstrapRef: { current: null },
  };

  const store = createEntityStore<T>({
    toolId: domainKey,
    defaults: cloneValue(defaults),
    persistenceDebounceMs: debounceMs,
    load: async (entityId) => {
      if (entityId === DISABLED_ENTITY_ID) {
        return { db: null, lastUsed: null };
      }

      if (runtime.mode === 'custom') {
        const loaded = await runtime.loadRef.current?.(entityId);
        if (loaded) {
          return { db: cloneValue(loaded), lastUsed: null };
        }

        return {
          db: null,
          lastUsed: runtime.bootstrapRef.current ? cloneValue(runtime.bootstrapRef.current) : null,
        };
      }

      return { db: null, lastUsed: null };
    },
    save: async (entityId, data) => {
      if (entityId === DISABLED_ENTITY_ID) {
        return;
      }

      const snapshot = cloneValue(data);

      try {
        if (runtime.mode === 'custom') {
          await runtime.saveRef.current?.(entityId, snapshot);
        } else {
          await runtime.updateRef.current?.(runtime.scopeRef.current, snapshot);
        }

        runtime.onSaveSuccessRef.current?.();
        runtime.onFlushRef.current?.(entityId, snapshot);
      } catch (error) {
        const normalized = asError(error);
        normalizeAndPresentError(normalized, { context: 'useAutoSaveSettings.save', showToast: false });
        runtime.onSaveErrorRef.current?.(normalized);
        throw normalized;
      }
    },
  });

  autoSaveStoreRegistry.set(domainKey, store);
  autoSaveRuntimeRegistry.set(domainKey, runtime);
  return { store, runtime };
}

export function useAutoSaveSettings<T extends object>(
  options: UseAutoSaveSettingsOptions<T>
): UseAutoSaveSettingsReturn<T> {
  const {
    toolId = '',
    shotId,
    projectId,
    scope = 'shot',
    debounceMs = 300,
    defaults,
    enabled = true,
    onSaveSuccess,
    onSaveError,
    bootstrapData,
    customLoadSave,
  } = options;

  const isCustomMode = !!customLoadSave;
  const entityId = isCustomMode
    ? customLoadSave.entityId
    : (scope === 'shot' ? shotId : projectId) ?? null;
  const isEntityValid = enabled && !!entityId;
  const activeEntityId = isEntityValid ? entityId : DISABLED_ENTITY_ID;
  const domainKey = getDomainKey(toolId, scope, debounceMs, customLoadSave);
  const { store, runtime } = useMemo(
    () => getStoreForDomain<T>(domainKey, defaults, debounceMs, isCustomMode ? 'custom' : 'react-query'),
    [debounceMs, defaults, domainKey, isCustomMode]
  );

  runtime.mode = isCustomMode ? 'custom' : 'react-query';
  runtime.loadRef.current = customLoadSave?.load ?? null;
  runtime.saveRef.current = customLoadSave?.save ?? null;
  runtime.scopeRef.current = scope;
  runtime.onSaveSuccessRef.current = onSaveSuccess;
  runtime.onSaveErrorRef.current = onSaveError;
  runtime.onFlushRef.current = customLoadSave?.onFlush;
  runtime.bootstrapRef.current = bootstrapData ? cloneValue(bootstrapData) : null;

  const {
    settings: authoritativeSettings,
    isLoading: authoritativeIsLoading,
    error: authoritativeError,
    update: updateSettings,
    hasShotSettings,
  } = useToolSettings<T>(toolId, {
    shotId: !isCustomMode && scope === 'shot' ? (shotId ?? undefined) : undefined,
    projectId: !isCustomMode ? (projectId ?? undefined) : undefined,
    enabled: !isCustomMode && isEntityValid,
  });

  runtime.updateRef.current = updateSettings;

  const localEntity = store.useEntity(activeEntityId);
  const storeState = store.getState();
  const bootstrapEntity = storeState.bootstrapEntity;
  const updateStoredField = storeState.updateField;
  const updateStoredFields = storeState.updateFields;
  const updateStoredTextField = storeState.updateTextField;
  const saveStoredEntity = storeState.save;
  const saveStoredEntityImmediate = storeState.saveImmediate;
  const revertStoredEntity = storeState.revert;
  const resetStoredEntity = storeState.reset;
  const isStoredEntityDirty = storeState.isDirty;
  const reloadStoredEntity = storeState.reloadEntity;
  const activeEntityRef = useRef<string | null>(entityId ?? null);
  const lastBootstrapRef = useRef<{
    entityId: string | null;
    seed: T | null;
    hasShotSettings: boolean;
  }>({ entityId: null, seed: null, hasShotSettings: false });

  useEffect(() => {
    activeEntityRef.current = entityId ?? null;
  }, [entityId]);

  useEffect(() => {
    const currentEntityId = entityId;

    return () => {
      if (!currentEntityId) {
        return;
      }

      void store.getState().saveImmediate(currentEntityId);
    };
  }, [entityId, store]);

  useEffect(() => {
    const handleBeforeUnload = () => {
      const currentEntityId = activeEntityRef.current;
      if (!currentEntityId) {
        return;
      }

      void store.getState().saveImmediate(currentEntityId);
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [store]);

  useEffect(() => {
    if (!isCustomMode || !isEntityValid) {
      return;
    }

    void reloadStoredEntity(activeEntityId).catch(() => {});
  }, [activeEntityId, isCustomMode, isEntityValid, reloadStoredEntity]);

  useEffect(() => {
    if (!isCustomMode || !isEntityValid || !bootstrapData) {
      return;
    }

    const currentEntity = store.getState().entities[activeEntityId];
    if (!currentEntity || currentEntity.status === 'loading' || currentEntity.hasPersistedData) {
      return;
    }

    const bootstrapSnapshot = cloneValue(bootstrapData);
    if (currentEntity.loaded && deepEqual(currentEntity.cleanSnapshot, bootstrapSnapshot)) {
      return;
    }

    bootstrapEntity({
      entityId: activeEntityId,
      db: null,
      lastUsed: bootstrapSnapshot,
    });
  }, [
    activeEntityId,
    bootstrapData,
    bootstrapEntity,
    isCustomMode,
    isEntityValid,
    store,
  ]);

  useEffect(() => {
    if (isCustomMode || !isEntityValid || authoritativeIsLoading || authoritativeError) {
      return;
    }

    const seed = cloneValue(authoritativeSettings ?? defaults);

    // Self-tracking guard: this effect is the one-and-only writer for
    // RQ→store sync here, so it compares against its own last-known seed
    // (not against store state, which can be mutated by other paths and
    // cause a feedback loop).
    if (
      lastBootstrapRef.current.entityId === activeEntityId
      && lastBootstrapRef.current.hasShotSettings === hasShotSettings
      && deepEqual(lastBootstrapRef.current.seed, seed)
    ) {
      return;
    }

    // Secondary guard: if the store already has the same clean snapshot
    // from some earlier path, skip re-bootstrapping but still record it.
    const currentEntity = store.getState().entities[activeEntityId];
    if (
      currentEntity
      && currentEntity.loaded
      && currentEntity.hasPersistedData === hasShotSettings
      && deepEqual(currentEntity.cleanSnapshot, seed)
    ) {
      lastBootstrapRef.current = { entityId: activeEntityId, seed, hasShotSettings };
      return;
    }

    lastBootstrapRef.current = { entityId: activeEntityId, seed, hasShotSettings };

    bootstrapEntity({
      entityId: activeEntityId,
      db: hasShotSettings ? seed : null,
      lastUsed: hasShotSettings ? null : seed,
    });
  }, [
    activeEntityId,
    authoritativeIsLoading,
    authoritativeError,
    authoritativeSettings,
    defaults,
    hasShotSettings,
    isCustomMode,
    isEntityValid,
    bootstrapEntity,
    store,
  ]);

  useRenderLogger(`AutoSaveSettings:${toolId || domainKey}`, {
    entityId,
    status: localEntity.status,
  });

  const updateField = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
    if (!isEntityValid) {
      return;
    }

    updateStoredField(activeEntityId, key, value, {
      deferPersistence: !isCustomMode && authoritativeIsLoading,
    });
  }, [activeEntityId, authoritativeIsLoading, isCustomMode, isEntityValid, updateStoredField]);

  const updateFields = useCallback((updates: Partial<T>) => {
    if (!isEntityValid) {
      return;
    }

    const deferKeys = !isCustomMode && authoritativeIsLoading
      ? (Object.keys(updates) as Array<keyof T>)
      : undefined;
    updateStoredFields(activeEntityId, updates, deferKeys ? { deferKeys } : undefined);
  }, [activeEntityId, authoritativeIsLoading, isCustomMode, isEntityValid, updateStoredFields]);

  const updateTextField = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
    if (!isEntityValid) {
      return;
    }

    updateStoredTextField(activeEntityId, key, value);
  }, [activeEntityId, isEntityValid, updateStoredTextField]);

  const updateTextFields = useCallback((updates: Partial<T>) => {
    if (!isEntityValid) {
      return;
    }

    for (const [key, value] of Object.entries(updates) as Array<[keyof T, T[keyof T]]>) {
      updateStoredTextField(activeEntityId, key, value);
    }
  }, [activeEntityId, isEntityValid, updateStoredTextField]);

  const save = useCallback(async () => {
    if (!isEntityValid) {
      return;
    }

    await saveStoredEntity(activeEntityId);
  }, [activeEntityId, isEntityValid, saveStoredEntity]);

  const saveImmediate = useCallback(async (dataToSave?: T) => {
    if (!isEntityValid) {
      return;
    }

    if (dataToSave) {
      updateStoredFields(activeEntityId, dataToSave);
    }

    await saveStoredEntityImmediate(activeEntityId);
  }, [activeEntityId, isEntityValid, saveStoredEntityImmediate, updateStoredFields]);

  const revert = useCallback(() => {
    if (!isEntityValid) {
      return;
    }

    revertStoredEntity(activeEntityId);
  }, [activeEntityId, isEntityValid, revertStoredEntity]);

  const reset = useCallback((newDefaults?: T) => {
    if (!isEntityValid) {
      return;
    }

    resetStoredEntity(activeEntityId, newDefaults ?? defaults);
  }, [activeEntityId, defaults, isEntityValid, resetStoredEntity]);

  const initializeFrom = useCallback((data: Partial<T>) => {
    if (!isCustomMode || !isEntityValid || localEntity.hasPersistedData || localEntity.status === 'loading') {
      return;
    }

    const deferKeys = Object.keys(data) as Array<keyof T>;
    if (deferKeys.length === 0) {
      return;
    }

    updateStoredFields(activeEntityId, data, { deferKeys });
  }, [
    activeEntityId,
    isCustomMode,
    isEntityValid,
    localEntity.hasPersistedData,
    localEntity.status,
    updateStoredFields,
  ]);

  const disabledSettings = useMemo(() => cloneValue(defaults), [defaults]);
  const resolvedStatus: AutoSaveStatus = useMemo(() => {
    if (!isEntityValid) {
      return 'idle';
    }

    if (!isCustomMode && authoritativeIsLoading) {
      return 'loading';
    }

    if (!isCustomMode && authoritativeError) {
      return 'error';
    }

    return localEntity.status;
  }, [authoritativeError, authoritativeIsLoading, isCustomMode, isEntityValid, localEntity.status]);

  const resolvedError = isCustomMode ? localEntity.error : authoritativeError ?? localEntity.error;
  const resolvedSettings = isEntityValid ? localEntity.settings : disabledSettings;
  const resolvedPersistedData = isCustomMode ? localEntity.hasPersistedData : hasShotSettings;
  const isDirty = isEntityValid ? isStoredEntityDirty(activeEntityId) : false;

  return useMemo(() => ({
    settings: resolvedSettings,
    status: resolvedStatus,
    entityId: isEntityValid ? entityId : null,
    isDirty,
    error: isEntityValid ? resolvedError : null,
    hasShotSettings: isEntityValid ? resolvedPersistedData : false,
    hasPersistedData: isEntityValid ? resolvedPersistedData : false,
    updateField,
    updateFields,
    updateTextField,
    updateTextFields,
    save,
    saveImmediate,
    revert,
    reset,
    initializeFrom,
  }), [
    entityId,
    initializeFrom,
    isDirty,
    isEntityValid,
    reset,
    resolvedError,
    resolvedPersistedData,
    resolvedSettings,
    resolvedStatus,
    revert,
    save,
    saveImmediate,
    updateField,
    updateFields,
    updateTextField,
    updateTextFields,
  ]);
}
