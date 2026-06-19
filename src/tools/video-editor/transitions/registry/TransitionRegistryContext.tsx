import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from 'react';
import { createTransitionRegistry } from '@/tools/video-editor/transitions/registry/TransitionRegistry.ts';
import type {
  TransitionRegistry,
  TransitionRegistrySnapshot,
} from '@/tools/video-editor/transitions/registry/types.ts';

export interface TransitionRegistryContextValue {
  readonly registry: TransitionRegistry;
  readonly snapshot: TransitionRegistrySnapshot;
}

const EMPTY_TRANSITION_REGISTRY_SNAPSHOT: TransitionRegistrySnapshot = Object.freeze({
  records: Object.freeze([]),
  diagnostics: Object.freeze([]),
  get: () => undefined,
  has: () => false,
});

const TransitionRegistryContext = createContext<TransitionRegistryContextValue | null>(null);

export interface TransitionRegistryProviderProps {
  children: ReactNode;
}

export function TransitionRegistryProvider({
  children,
}: TransitionRegistryProviderProps) {
  const registry = useMemo(() => createTransitionRegistry(), []);
  const subscribe = useCallback((onStoreChange: () => void) => {
    const handle = registry.subscribe(() => onStoreChange());
    return () => handle.dispose();
  }, [registry]);
  const getSnapshot = useCallback(() => registry.getSnapshot(), [registry]);
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  useEffect(() => () => {
    registry.dispose();
  }, [registry]);

  const value = useMemo<TransitionRegistryContextValue>(
    () => ({ registry, snapshot }),
    [registry, snapshot],
  );

  return (
    <TransitionRegistryContext.Provider value={value}>
      {children}
    </TransitionRegistryContext.Provider>
  );
}

export function useTransitionRegistrySnapshot(): TransitionRegistrySnapshot {
  return useOptionalTransitionRegistryContext()?.snapshot ?? EMPTY_TRANSITION_REGISTRY_SNAPSHOT;
}

export function useTransitionRegistryContext(): TransitionRegistryContextValue {
  const context = useOptionalTransitionRegistryContext();
  if (!context) {
    throw new Error('useTransitionRegistryContext must be called inside a TransitionRegistryProvider');
  }
  return context;
}

export function useOptionalTransitionRegistryContext(): TransitionRegistryContextValue | null {
  return useContext(TransitionRegistryContext);
}
