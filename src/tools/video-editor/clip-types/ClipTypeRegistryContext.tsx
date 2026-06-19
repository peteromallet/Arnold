import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from 'react';
import { createClipTypeRegistry } from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import type {
  ClipTypeRegistry,
  ClipTypeRegistrySnapshot,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';

export interface ClipTypeRegistryContextValue {
  readonly registry: ClipTypeRegistry;
  readonly snapshot: ClipTypeRegistrySnapshot;
}

const EMPTY_CLIP_TYPE_REGISTRY_SNAPSHOT: ClipTypeRegistrySnapshot = Object.freeze({
  records: Object.freeze([]),
  diagnostics: Object.freeze([]),
  get: () => undefined,
  has: () => false,
});

const ClipTypeRegistryContext = createContext<ClipTypeRegistryContextValue | null>(null);

export interface ClipTypeRegistryProviderProps {
  children: ReactNode;
}

export function ClipTypeRegistryProvider({
  children,
}: ClipTypeRegistryProviderProps) {
  const registry = useMemo(() => createClipTypeRegistry(), []);
  const subscribe = useCallback((onStoreChange: () => void) => {
    const handle = registry.subscribe(() => onStoreChange());
    return () => handle.dispose();
  }, [registry]);
  const getSnapshot = useCallback(() => registry.getSnapshot(), [registry]);
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  useEffect(() => () => {
    registry.dispose();
  }, [registry]);

  const value = useMemo<ClipTypeRegistryContextValue>(
    () => ({ registry, snapshot }),
    [registry, snapshot],
  );

  return (
    <ClipTypeRegistryContext.Provider value={value}>
      {children}
    </ClipTypeRegistryContext.Provider>
  );
}

export function useClipTypeRegistrySnapshot(): ClipTypeRegistrySnapshot {
  return useOptionalClipTypeRegistryContext()?.snapshot ?? EMPTY_CLIP_TYPE_REGISTRY_SNAPSHOT;
}

export function useClipTypeRegistryContext(): ClipTypeRegistryContextValue {
  const context = useOptionalClipTypeRegistryContext();
  if (!context) {
    throw new Error('useClipTypeRegistryContext must be called inside a ClipTypeRegistryProvider');
  }
  return context;
}

export function useOptionalClipTypeRegistryContext(): ClipTypeRegistryContextValue | null {
  return useContext(ClipTypeRegistryContext);
}
