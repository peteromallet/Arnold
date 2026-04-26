import { useEffect, useMemo } from 'react';
import { shallow } from 'zustand/shallow';
import { useStoreWithEqualityFn } from 'zustand/traditional';
import { createStore } from 'zustand/vanilla';
import { deepEqual } from '@/shared/lib/utils/deepEqual';

export type EntityStatus = 'idle' | 'loading' | 'ready' | 'saving' | 'error';

export interface EntityStoreConfig<T extends object> {
  toolId: string;
  defaults: T;
  load: (entityId: string) => Promise<{ db: T | null; lastUsed: T | null }>;
  save: (entityId: string, data: T) => Promise<void>;
  textFieldKeys?: readonly (keyof T)[];
  persistenceDebounceMs?: number;
}

export interface EntityView<T extends object> {
  settings: T;
  status: EntityStatus;
  error: Error | null;
  hasPersistedData: boolean;
  updateField: <K extends keyof T>(key: K, value: T[K]) => void;
  updateFields: (patch: Partial<T>) => void;
  updateTextField: <K extends keyof T>(key: K, value: T[K]) => void;
  flushTextFields: () => Promise<void>;
  save: () => Promise<void>;
  saveImmediate: () => Promise<void>;
  revert: () => void;
  reset: (nextSettings?: T) => void;
}

export interface EntityBootstrapInput<T extends object> {
  entityId: string;
  db: T | null;
  lastUsed: T | null;
}

export interface EntityRecord<T extends object> {
  settings: T;
  status: EntityStatus;
  error: Error | null;
  hasPersistedData: boolean;
  cleanSnapshot: T;
  savedSettings: T;
  pendingTextFieldKeys: Array<keyof T>;
  loaded: boolean;
}

export interface EntityStoreState<T extends object> {
  entities: Record<string, EntityRecord<T>>;
  bootstrapEntity: (input: EntityBootstrapInput<T>) => void;
  ensureEntity: (entityId: string) => Promise<void>;
  reloadEntity: (entityId: string) => Promise<void>;
  updateField: <K extends keyof T>(
    entityId: string,
    key: K,
    value: T[K],
    options?: { deferPersistence?: boolean }
  ) => void;
  updateFields: (
    entityId: string,
    patch: Partial<T>,
    options?: { deferKeys?: readonly (keyof T)[] }
  ) => void;
  updateTextField: <K extends keyof T>(entityId: string, key: K, value: T[K]) => void;
  flushTextFields: (entityId: string) => Promise<void>;
  save: (entityId: string) => Promise<void>;
  saveImmediate: (entityId: string) => Promise<void>;
  revert: (entityId: string) => void;
  reset: (entityId: string, nextSettings?: T) => void;
  isDirty: (entityId: string) => boolean;
  hasPendingPersistence: (entityId: string) => boolean;
  syncExternalEntity: (input: EntityBootstrapInput<T>) => boolean;
}

export interface EntityStoreApi<T extends object> {
  useEntity: (entityId: string) => EntityView<T>;
  getState: () => EntityStoreState<T>;
}

type TimeoutHandle = ReturnType<typeof setTimeout>;

function cloneValue<T>(value: T): T {
  return structuredClone(value);
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

function uniqueKeys<T>(keys: Iterable<keyof T>): Array<keyof T> {
  return Array.from(new Set(keys));
}

function getChangedKeys<T extends object>(current: T, baseline: T): Array<keyof T> {
  const keys = new Set<keyof T>([
    ...(Object.keys(current) as Array<keyof T>),
    ...(Object.keys(baseline) as Array<keyof T>),
  ]);

  return Array.from(keys).filter((key) => !deepEqual(current[key], baseline[key]));
}

export function createEntityStore<T extends object>(
  config: EntityStoreConfig<T>
): EntityStoreApi<T> {
  const debounceMs = config.persistenceDebounceMs ?? 300;
  const textFieldKeySet = new Set<keyof T>(config.textFieldKeys ?? []);
  const pendingTimers = new Map<string, TimeoutHandle>();
  const loadPromises = new Map<string, Promise<void>>();
  const placeholderEntities = new Map<string, EntityRecord<T>>();

  const createRecord = (seed: T, overrides?: Partial<EntityRecord<T>>): EntityRecord<T> => ({
    settings: cloneValue(seed),
    status: 'idle',
    error: null,
    hasPersistedData: false,
    cleanSnapshot: cloneValue(seed),
    savedSettings: cloneValue(seed),
    pendingTextFieldKeys: [],
    loaded: false,
    ...overrides,
  });

  const getPlaceholder = (entityId: string): EntityRecord<T> => {
    const existing = placeholderEntities.get(entityId);
    if (existing) {
      return existing;
    }

    const placeholder = createRecord(config.defaults);
    placeholderEntities.set(entityId, placeholder);
    return placeholder;
  };

  const getSeed = ({ db, lastUsed }: Omit<EntityBootstrapInput<T>, 'entityId'>): T => {
    const source = db ?? lastUsed;
    if (!source) return cloneValue(config.defaults);
    // Backfill any missing keys from defaults so partial DB rows (saved before a field was added)
    // don't surface `undefined` to consumers that read the field directly.
    return { ...cloneValue(config.defaults), ...source } as T;
  };

  const store = createStore<EntityStoreState<T>>((set, get) => {
    const clearPendingTimer = (entityId: string): void => {
      const timer = pendingTimers.get(entityId);
      if (!timer) {
        return;
      }
      clearTimeout(timer);
      pendingTimers.delete(entityId);
    };

    const ensureStoredEntity = (entityId: string): EntityRecord<T> => {
      const existing = get().entities[entityId];
      if (existing) {
        return existing;
      }

      const nextRecord = createRecord(config.defaults);
      set((state) => ({
        entities: {
          ...state.entities,
          [entityId]: nextRecord,
        },
      }));
      return get().entities[entityId];
    };

    const isDirtyRecord = (record: EntityRecord<T> | undefined): boolean => {
      if (!record) {
        return false;
      }
      return !deepEqual(record.settings, record.cleanSnapshot);
    };

    const hasPendingPersistenceRecord = (
      entityId: string,
      record: EntityRecord<T> | undefined
    ): boolean => {
      if (!record) {
        return false;
      }

      return (
        record.status === 'saving' ||
        pendingTimers.has(entityId) ||
        record.pendingTextFieldKeys.length > 0
      );
    };

    const persistEntity = async (entityId: string): Promise<void> => {
      clearPendingTimer(entityId);
      const current = get().entities[entityId] ?? ensureStoredEntity(entityId);

      if (!isDirtyRecord(current)) {
        if (current.pendingTextFieldKeys.length > 0) {
          set((state) => ({
            entities: {
              ...state.entities,
              [entityId]: {
                ...state.entities[entityId],
                pendingTextFieldKeys: [],
              },
            },
          }));
        }
        return;
      }

      const snapshot = cloneValue(current.settings);
      set((state) => {
        const entity = state.entities[entityId];
        if (!entity) {
          return state;
        }

        return {
          entities: {
            ...state.entities,
            [entityId]: {
              ...entity,
              status: 'saving',
              error: null,
            },
          },
        };
      });

      try {
        await config.save(entityId, cloneValue(snapshot));

        set((state) => {
          const entity = state.entities[entityId];
          if (!entity) {
            return state;
          }

          const stillDirty = !deepEqual(entity.settings, snapshot);

          return {
            entities: {
              ...state.entities,
              [entityId]: {
                ...entity,
                status: 'ready',
                error: null,
                hasPersistedData: true,
                cleanSnapshot: snapshot,
                savedSettings: snapshot,
                pendingTextFieldKeys: stillDirty ? entity.pendingTextFieldKeys : [],
              },
            },
          };
        });
      } catch (error) {
        set((state) => {
          const entity = state.entities[entityId];
          if (!entity) {
            return state;
          }

          return {
            entities: {
              ...state.entities,
              [entityId]: {
                ...entity,
                status: 'error',
                error: asError(error),
              },
            },
          };
        });
        throw error;
      }
    };

    const scheduleSave = (entityId: string): void => {
      clearPendingTimer(entityId);
      pendingTimers.set(
        entityId,
        setTimeout(() => {
          pendingTimers.delete(entityId);
          void persistEntity(entityId);
        }, debounceMs)
      );
    };

    const applyPatch = (
      entityId: string,
      patch: Partial<T>,
      options?: { deferKeys?: readonly (keyof T)[] }
    ): void => {
      const current = get().entities[entityId] ?? ensureStoredEntity(entityId);
      const patchEntries = Object.entries(patch) as Array<[keyof T, T[keyof T]]>;
      const changedEntries = patchEntries.filter(([key, value]) => !deepEqual(current.settings[key], value));

      if (changedEntries.length === 0) {
        return;
      }

      const nextSettings = {
        ...current.settings,
        ...Object.fromEntries(changedEntries),
      } as T;
      const explicitDeferredKeys = new Set<keyof T>(options?.deferKeys ?? []);
      const deferredKeys = uniqueKeys(
        changedEntries
          .map(([key]) => key)
          .filter((key) => textFieldKeySet.has(key) || explicitDeferredKeys.has(key))
      );
      const shouldScheduleSave =
        current.status !== 'loading'
        && changedEntries.some(([key]) => !deferredKeys.includes(key));

      set((state) => {
        const entity = state.entities[entityId] ?? current;
        return {
          entities: {
            ...state.entities,
            [entityId]: {
              ...entity,
              settings: nextSettings,
              status:
                entity.status === 'loading'
                  ? 'loading'
                  : entity.status === 'saving'
                    ? 'saving'
                    : 'ready',
              error: null,
              pendingTextFieldKeys: uniqueKeys([
                ...entity.pendingTextFieldKeys,
                ...deferredKeys,
              ]),
            },
          },
        };
      });

      if (shouldScheduleSave) {
        scheduleSave(entityId);
      }
    };

    return {
      entities: {},

      bootstrapEntity: ({ entityId, db, lastUsed }) => {
        clearPendingTimer(entityId);
        const seed = getSeed({ db, lastUsed });
        const current = get().entities[entityId];
        const currentHasPendingPersistence = hasPendingPersistenceRecord(entityId, current);
        const currentIsDirty = isDirtyRecord(current);
        const shouldPreserveLocalState = !!current && (currentHasPendingPersistence || currentIsDirty);
        const changedKeys = shouldPreserveLocalState
          ? getChangedKeys(current.settings, seed)
          : [];
        const pendingTextFieldKeys = shouldPreserveLocalState
          ? uniqueKeys([
              ...current.pendingTextFieldKeys,
              ...changedKeys.filter((key) => textFieldKeySet.has(key)),
            ])
          : [];
        const shouldScheduleSave = shouldPreserveLocalState
          && changedKeys.some((key) => !pendingTextFieldKeys.includes(key));

        set((state) => ({
          entities: {
            ...state.entities,
            [entityId]: createRecord(seed, shouldPreserveLocalState
              ? {
                  settings: cloneValue(current.settings),
                  status: 'ready',
                  error: null,
                  hasPersistedData: db !== null,
                  cleanSnapshot: cloneValue(seed),
                  savedSettings: cloneValue(seed),
                  pendingTextFieldKeys,
                  loaded: true,
                }
              : {
                  status: 'ready',
                  error: null,
                  hasPersistedData: db !== null,
                  savedSettings: cloneValue(seed),
                  pendingTextFieldKeys: [],
                  loaded: true,
                }),
          },
        }));

        if (shouldScheduleSave) {
          scheduleSave(entityId);
        }
      },

      ensureEntity: async (entityId) => {
        const current = get().entities[entityId];
        if (current?.loaded) {
          return;
        }

        const inFlight = loadPromises.get(entityId);
        if (inFlight) {
          return inFlight;
        }

        set((state) => {
          const existing = state.entities[entityId] ?? createRecord(config.defaults);
          return {
            entities: {
              ...state.entities,
              [entityId]: {
                ...existing,
                status: 'loading',
                error: null,
              },
            },
          };
        });

        const loadPromise = config
          .load(entityId)
          .then((result) => {
            get().bootstrapEntity({
              entityId,
              db: result.db,
              lastUsed: result.lastUsed,
            });
          })
          .catch((error) => {
            set((state) => {
              const existing = state.entities[entityId] ?? createRecord(config.defaults);
              return {
                entities: {
                  ...state.entities,
                  [entityId]: {
                    ...existing,
                    status: 'error',
                    error: asError(error),
                  },
                },
              };
            });
            throw error;
          })
          .finally(() => {
            loadPromises.delete(entityId);
          });

        loadPromises.set(entityId, loadPromise);
        return loadPromise;
      },

      reloadEntity: async (entityId) => {
        clearPendingTimer(entityId);
        loadPromises.delete(entityId);
        set((state) => {
          const existing = state.entities[entityId] ?? createRecord(config.defaults);
          return {
            entities: {
              ...state.entities,
              [entityId]: {
                ...existing,
                status: 'loading',
                error: null,
                loaded: false,
              },
            },
          };
        });

        await get().ensureEntity(entityId);
      },

      updateField: (entityId, key, value, options) => {
        get().updateFields(
          entityId,
          { [key]: value } as Partial<T>,
          options?.deferPersistence ? { deferKeys: [key] } : undefined
        );
      },

      updateFields: (entityId, patch, options) => {
        applyPatch(entityId, patch, options);
      },

      updateTextField: (entityId, key, value) => {
        get().updateFields(entityId, { [key]: value } as Partial<T>, { deferKeys: [key] });
      },

      flushTextFields: async (entityId) => {
        const entity = get().entities[entityId];
        if (!entity) {
          return;
        }

        if (!hasPendingPersistenceRecord(entityId, entity) && !isDirtyRecord(entity)) {
          return;
        }

        await persistEntity(entityId);
      },

      save: async (entityId) => {
        await persistEntity(entityId);
      },

      saveImmediate: async (entityId) => {
        await persistEntity(entityId);
      },

      revert: (entityId) => {
        clearPendingTimer(entityId);
        const current = get().entities[entityId] ?? ensureStoredEntity(entityId);
        set((state) => ({
          entities: {
            ...state.entities,
            [entityId]: {
              ...state.entities[entityId],
              settings: cloneValue(current.cleanSnapshot),
              status: 'ready',
              error: null,
              pendingTextFieldKeys: [],
            },
          },
        }));
      },

      reset: (entityId, nextSettings) => {
        clearPendingTimer(entityId);
        const current = get().entities[entityId] ?? ensureStoredEntity(entityId);
        const resetSnapshot = cloneValue(nextSettings ?? config.defaults);
        set((state) => ({
          entities: {
            ...state.entities,
            [entityId]: {
              ...state.entities[entityId],
              settings: resetSnapshot,
              cleanSnapshot: cloneValue(resetSnapshot),
              savedSettings: cloneValue(resetSnapshot),
              status: 'ready',
              error: null,
              hasPersistedData: current.hasPersistedData,
              pendingTextFieldKeys: [],
            },
          },
        }));
      },

      isDirty: (entityId) => {
        return isDirtyRecord(get().entities[entityId]);
      },

      hasPendingPersistence: (entityId) => {
        return hasPendingPersistenceRecord(entityId, get().entities[entityId]);
      },

      syncExternalEntity: ({ entityId, db, lastUsed }) => {
        const current = get().entities[entityId];
        if (!current) {
          get().bootstrapEntity({ entityId, db, lastUsed });
          return true;
        }

        if (isDirtyRecord(current) || hasPendingPersistenceRecord(entityId, current)) {
          return false;
        }

        clearPendingTimer(entityId);
        get().bootstrapEntity({ entityId, db, lastUsed });
        return true;
      },
    };
  });

  function useEntity(entityId: string): EntityView<T> {
    const entitySlice = useStoreWithEqualityFn(
      store,
      (state) => {
        const entity = state.entities[entityId] ?? getPlaceholder(entityId);
        return {
          settings: entity.settings,
          status: entity.status,
          error: entity.error,
          hasPersistedData: entity.hasPersistedData,
        };
      },
      shallow
    );

    useEffect(() => {
      void store.getState().ensureEntity(entityId).catch(() => {});
    }, [entityId]);

    const actions = useMemo(
      () => ({
        updateField: <K extends keyof T>(key: K, value: T[K]) => {
          store.getState().updateField(entityId, key, value);
        },
        updateFields: (patch: Partial<T>) => {
          store.getState().updateFields(entityId, patch);
        },
        updateTextField: <K extends keyof T>(key: K, value: T[K]) => {
          store.getState().updateTextField(entityId, key, value);
        },
        flushTextFields: () => store.getState().flushTextFields(entityId),
        save: () => store.getState().save(entityId),
        saveImmediate: () => store.getState().saveImmediate(entityId),
        revert: () => {
          store.getState().revert(entityId);
        },
        reset: (nextSettings?: T) => {
          store.getState().reset(entityId, nextSettings);
        },
      }),
      [entityId]
    );

    return useMemo(
      () => ({
        ...entitySlice,
        ...actions,
      }),
      [actions, entitySlice]
    );
  }

  return {
    useEntity,
    getState: store.getState,
  };
}
