import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from 'react';
import { createEffectRegistry } from '@/tools/video-editor/effects/registry/EffectRegistry.ts';
import type {
  EffectRegistry,
  EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/types.ts';

export interface EffectRegistryContextValue {
  readonly registry: EffectRegistry;
  readonly snapshot: EffectRegistrySnapshot;
}

const EMPTY_EFFECT_REGISTRY_SNAPSHOT: EffectRegistrySnapshot = Object.freeze({
  records: Object.freeze([]),
  diagnostics: Object.freeze([]),
  get: () => undefined,
  has: () => false,
});

const EffectRegistryContext = createContext<EffectRegistryContextValue | null>(null);

export interface EffectRegistryProviderProps {
  children: ReactNode;
}

export function EffectRegistryProvider({
  children,
}: EffectRegistryProviderProps) {
  const registry = useMemo(() => createEffectRegistry(), []);
  const subscribe = useCallback((onStoreChange: () => void) => {
    const handle = registry.subscribe(() => onStoreChange());
    return () => handle.dispose();
  }, [registry]);
  const getSnapshot = useCallback(() => registry.getSnapshot(), [registry]);
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  useEffect(() => () => {
    registry.dispose();
  }, [registry]);

  const value = useMemo<EffectRegistryContextValue>(
    () => ({ registry, snapshot }),
    [registry, snapshot],
  );

  return (
    <EffectRegistryContext.Provider value={value}>
      {children}
    </EffectRegistryContext.Provider>
  );
}

export function useEffectRegistrySnapshot(): EffectRegistrySnapshot {
  return useOptionalEffectRegistryContext()?.snapshot ?? EMPTY_EFFECT_REGISTRY_SNAPSHOT;
}

export function useEffectRegistryContext(): EffectRegistryContextValue {
  const context = useOptionalEffectRegistryContext();
  if (!context) {
    throw new Error('useEffectRegistryContext must be called inside an EffectRegistryProvider');
  }
  return context;
}

export function useOptionalEffectRegistryContext(): EffectRegistryContextValue | null {
  return useContext(EffectRegistryContext);
}
