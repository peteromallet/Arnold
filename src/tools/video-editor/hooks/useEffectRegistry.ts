import { useCallback, useEffect, useMemo, useSyncExternalStore } from 'react';
import type { DisposeHandle } from '@reigh/editor-sdk';
import {
  continuousEffects,
  entranceEffects,
  exitEffects,
} from '@/tools/video-editor/effects/index.tsx';
import { compileEffect } from '@/tools/video-editor/effects/compileEffect.tsx';
import { loadDraftEffects } from '@/tools/video-editor/effects/effect-store.ts';
import { createEffectRegistry } from '@/tools/video-editor/effects/registry/EffectRegistry.ts';
import { useOptionalEffectRegistryContext } from '@/tools/video-editor/effects/registry/EffectRegistryContext.tsx';
import {
  builtInEffectsToRegistryRecords,
  effectResourcesToRegistryRecords,
  legacyDbEffectsToRegistryRecords,
  localDraftEffectsToRegistryRecords,
} from '@/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts';
import type { EffectRegistry } from '@/tools/video-editor/effects/registry/types.ts';
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
): EffectRegistry {
  const draftEffects = useMemo(() => loadDraftEffects(), []);
  const standaloneRegistry = useMemo(() => createEffectRegistry(), []);
  const registryContext = useOptionalEffectRegistryContext();
  const registry = registryContext?.registry ?? standaloneRegistry;

  const subscribe = useCallback((onStoreChange: () => void) => {
    const handle = registry.subscribe(() => onStoreChange());
    return () => handle.dispose();
  }, [registry]);
  const getSnapshot = useCallback(() => registry.getSnapshot(), [registry]);
  useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  useEffect(() => {
    return () => {
      standaloneRegistry.dispose();
    };
  }, [standaloneRegistry]);

  useEffect(() => {
    const handles: DisposeHandle[] = [];
    const drafts = Object.entries(draftEffects);
    const db = dbEffects ?? [];
    const resources = resourceEffects ?? [];
    if (db.length > 0) {
      console.warn('[EffectRegistry] legacy DB effects are deprecated; migrate to resource-based effects via useEffectResources.');
    }

    const records = [
      ...builtInEffectsToRegistryRecords(BUILT_INS),
      ...localDraftEffectsToRegistryRecords(
        Object.fromEntries(drafts),
        (code) => compileEffect(code),
      ),
      ...legacyDbEffectsToRegistryRecords(
        db,
        (code) => compileEffect(code),
      ),
      ...effectResourcesToRegistryRecords(
        resources,
        (code) => compileEffect(code),
      ),
    ];

    records.forEach((record) => {
      handles.push(registry.register(record));
    });

    return () => {
      handles.forEach((handle) => handle.dispose());
    };
  }, [dbEffects, draftEffects, registry, resourceEffects]);

  return registry;
}
