import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from 'react';
import { DynamicSequenceRegistry } from '@/tools/video-editor/sequences/DynamicSequenceRegistry';
import type { SequenceComponentResource } from '@/tools/video-editor/lib/sequence-component-catalog';
import type { DynamicSequenceComponentEntry } from '@/tools/video-editor/sequences/registry';

// Implementation note (FLAG-003 divergence — intentional):
// The effects side uses a module-level singleton + `lookupEffect()` pattern
// (effects/index.tsx:80-110), but sequences use a real React context with
// `useSyncExternalStore`. Do NOT propagate the DEBT-047 render-time
// `replaceEffectRegistry()` mutation pattern from the effects side: the
// `registry.batch(...)` call MUST run inside a `useEffect`, never during
// render.

interface SequenceComponentRegistryContextValue {
  registry: DynamicSequenceRegistry;
  /** Snapshot version (changes when register/registerAsync resolves). */
  version: number;
  /** Catalog entries currently registered (built-in + DB-stored). */
  entries: DynamicSequenceComponentEntry[];
}

const SequenceComponentRegistryContext = createContext<SequenceComponentRegistryContextValue | null>(null);

export interface SequenceComponentRegistryProviderProps {
  /** DB-stored sequence components from useSequenceResources. */
  components?: readonly SequenceComponentResource[];
  children: ReactNode;
}

export function SequenceComponentRegistryProvider({
  components,
  children,
}: SequenceComponentRegistryProviderProps) {
  // Singleton per provider. Mirrors hooks/useEffectRegistry.ts:24-63 — one
  // registry instance per editor mount.
  const registry = useMemo(() => new DynamicSequenceRegistry({}), []);

  // Subscribe to registry version changes so consumers re-render when
  // register/registerAsync completes.
  const version = useSyncExternalStore(registry.subscribe, registry.getSnapshot);

  // CRITICAL: register inside useEffect, NEVER during render. This avoids
  // the render-time-mutation pattern that effects/useEffectRegistry.ts:30
  // currently has (DEBT-047).
  useEffect(() => {
    let stale = false;
    void registry.batch(async () => {
      for (const component of components ?? []) {
        if (stale) return;
        // NOTE: register by `entry.clipType` (NOT by `custom:` prefix) —
        // DynamicComponentRegistry.normalizeName strips the prefix on lookup,
        // so callers querying via `custom:my-pulse` resolve to the entry
        // stored as `my-pulse`.
        await registry.registerAsync(
          component.clipType,
          component.code,
          component.schemaJson,
        );
      }
    });
    return () => {
      stale = true;
    };
  }, [components, registry]);

  // Build the entries array consumers (e.g. TimelineRenderer) read at
  // render time. We rebuild this whenever `version` ticks so dynamic
  // dispatch picks up newly compiled components.
  const entries = useMemo<DynamicSequenceComponentEntry[]>(() => {
    void version; // dependency: rebuild when registry version ticks
    const list: DynamicSequenceComponentEntry[] = [];
    for (const component of components ?? []) {
      const compiled = registry.get(component.clipType);
      if (!compiled) continue;
      list.push({
        clipType: component.clipType,
        component: compiled as DynamicSequenceComponentEntry['component'],
        schemaJson: component.schemaJson,
        themeId: component.themeId,
      });
    }
    return list;
  }, [components, registry, version]);

  const value = useMemo<SequenceComponentRegistryContextValue>(
    () => ({ registry, version, entries }),
    [registry, version, entries],
  );

  return (
    <SequenceComponentRegistryContext.Provider value={value}>
      {children}
    </SequenceComponentRegistryContext.Provider>
  );
}

const EMPTY_SNAPSHOT: { entries: DynamicSequenceComponentEntry[]; version: number } = {
  entries: [],
  version: 0,
};

/**
 * Read the current dynamic-registry snapshot. Returns an empty entries array
 * when the provider is not mounted (so non-editor renderers like
 * standalone <TimelineRenderer> usages outside the editor still work — they
 * just won't see DB-stored sequences).
 */
export function useSequenceComponentRegistrySnapshot(): {
  entries: DynamicSequenceComponentEntry[];
  version: number;
} {
  const ctx = useContext(SequenceComponentRegistryContext);
  if (!ctx) return EMPTY_SNAPSHOT;
  return { entries: ctx.entries, version: ctx.version };
}

/**
 * Read the underlying DynamicSequenceRegistry. Throws if the provider is
 * not mounted — this hook is only for callers that *need* the registry
 * instance (e.g. registering a one-off draft). Most read-path callers
 * should use `useSequenceComponentRegistrySnapshot` instead.
 */
export function useSequenceComponentRegistry(): DynamicSequenceRegistry {
  const ctx = useContext(SequenceComponentRegistryContext);
  if (!ctx) {
    throw new Error(
      'useSequenceComponentRegistry must be called inside a SequenceComponentRegistryProvider',
    );
  }
  return ctx.registry;
}
