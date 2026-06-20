import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from 'react';
import { createShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts';
import type {
  ShaderEffectRegistry,
  ShaderEffectRegistrySnapshot,
} from '@/tools/video-editor/shaders/registry/types.ts';

export interface ShaderEffectRegistryContextValue {
  readonly registry: ShaderEffectRegistry;
  readonly snapshot: ShaderEffectRegistrySnapshot;
}

const EMPTY_SHADER_EFFECT_REGISTRY_SNAPSHOT: ShaderEffectRegistrySnapshot = Object.freeze({
  records: Object.freeze([]),
  diagnostics: Object.freeze([]),
  get: () => undefined,
  getByLookup: () => undefined,
  has: () => false,
  hasByLookup: () => false,
});

const ShaderEffectRegistryContext = createContext<ShaderEffectRegistryContextValue | null>(null);

export interface ShaderEffectRegistryProviderProps {
  children: ReactNode;
}

export function ShaderEffectRegistryProvider({
  children,
}: ShaderEffectRegistryProviderProps) {
  const registry = useMemo(() => createShaderEffectRegistry(), []);
  const subscribe = useCallback((onStoreChange: () => void) => {
    const handle = registry.subscribe(() => onStoreChange());
    return () => handle.dispose();
  }, [registry]);
  const getSnapshot = useCallback(() => registry.getSnapshot(), [registry]);
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  useEffect(() => () => {
    registry.dispose();
  }, [registry]);

  const value = useMemo<ShaderEffectRegistryContextValue>(
    () => ({ registry, snapshot }),
    [registry, snapshot],
  );

  return (
    <ShaderEffectRegistryContext.Provider value={value}>
      {children}
    </ShaderEffectRegistryContext.Provider>
  );
}

export function useShaderEffectRegistrySnapshot(): ShaderEffectRegistrySnapshot {
  return useOptionalShaderEffectRegistryContext()?.snapshot ?? EMPTY_SHADER_EFFECT_REGISTRY_SNAPSHOT;
}

export function useShaderEffectRegistryContext(): ShaderEffectRegistryContextValue {
  const context = useOptionalShaderEffectRegistryContext();
  if (!context) {
    throw new Error('useShaderEffectRegistryContext must be called inside a ShaderEffectRegistryProvider');
  }
  return context;
}

export function useOptionalShaderEffectRegistryContext(): ShaderEffectRegistryContextValue | null {
  return useContext(ShaderEffectRegistryContext);
}
