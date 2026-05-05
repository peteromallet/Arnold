import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { DynamicEffectRegistry } from '@/tools/video-editor/effects/DynamicEffectRegistry.ts';
import {
  continuousEffects,
  entranceEffects,
  exitEffects,
  getEffectRegistry,
  replaceEffectRegistry,
} from '@/tools/video-editor/effects/index.tsx';
import { loadDraftEffects } from '@/tools/video-editor/effects/effect-store.ts';
import type { EffectResource } from '@/tools/video-editor/hooks/useEffectResources.ts';

const BUILT_INS = {
  ...entranceEffects,
  ...exitEffects,
  ...continuousEffects,
};

/**
 * Dual-read registry: registers effects from both the legacy `effects` table
 * (keyed by slug) and the newer `resources` table (keyed by resource UUID).
 * Resource-based effects are stored in clips as `custom:{resourceId}`.
 */
export function useEffectRegistry(
  dbEffects: Array<{ slug: string; code: string }> | undefined,
  resourceEffects?: EffectResource[],
) {
  const draftEffects = useMemo(() => loadDraftEffects(), []);
  const registry = useMemo(() => new DynamicEffectRegistry(BUILT_INS), []);
  if (getEffectRegistry() !== registry) replaceEffectRegistry(registry);
  useSyncExternalStore(registry.subscribe, registry.getSnapshot);

  useEffect(() => {
    let stale = false;
    const drafts = Object.entries(draftEffects);
    const db = dbEffects ?? [];
    const resources = resourceEffects ?? [];
    if (db.length > 0) {
      console.warn('[EffectRegistry] legacy DB effects are deprecated; migrate to resource-based effects via useEffectResources.');
    }

    void registry.batch(async () => {
      for (const [name, code] of drafts) {
        if (stale) return;
        await registry.registerAsync(name, code);
      }
      for (const effect of db) {
        if (stale) return;
        await registry.registerAsync(effect.slug, effect.code);
      }
      for (const effect of resources) {
        if (stale) return;
        await registry.registerAsync(effect.id, effect.code, effect.parameterSchema);
      }
    });

    return () => {
      stale = true;
    };
  }, [dbEffects, draftEffects, registry, resourceEffects]);

  return registry;
}
