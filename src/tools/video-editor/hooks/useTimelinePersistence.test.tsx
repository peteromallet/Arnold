// @vitest-environment jsdom
import React from 'react';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTimelinePersistence } from './useTimelinePersistence';
import { TimelineEventBus } from './useTimelineEventBus';
import { createInteractionState, notifyInteractionEndIfIdle, type InteractionStateRef } from '../lib/interaction-state';
import { configToRows, type TimelineData } from '../lib/timeline-data';
import { getConfigSignature, getStableConfigSignature } from '../lib/config-utils';
import { createDefaultTimelineConfig } from '../lib/defaults';
import type { AssetResolver } from '../data/AssetResolver';
import { TimelineVersionConflictError, type DataProvider } from '../data/DataProvider';
import type { AssetRegistry } from '../types';

function makeRegistry(label: string): AssetRegistry {
  return {
    assets: {
      [`asset-${label}`]: {
        file: `media/${label}.mp4`,
        type: 'video/mp4',
        generationId: `gen-${label}`,
        variantId: `variant-${label}`,
      },
    },
  };
}

function makeTimelineData(label: string, registry: AssetRegistry = { assets: {} }): TimelineData {
  const base = createDefaultTimelineConfig();
  const config = {
    ...base,
    output: { ...base.output, file: `output-${label}.mp4` },
    tracks: (base.tracks ?? []).map((track) => ({ ...track })),
    clips: [{
      id: `clip-${label}`,
      at: 0,
      track: 'V1' as const,
      clipType: 'hold' as const,
      hold: 1,
    }],
  };
  const rowData = configToRows(config);
  const assetMap = Object.fromEntries(
    Object.entries(registry.assets).map(([assetId, entry]) => [assetId, entry.file]),
  );
  const resolvedRegistry = Object.fromEntries(
    Object.entries(registry.assets).map(([assetId, entry]) => [assetId, { ...entry, src: entry.file }]),
  );
  const resolvedConfig = {
    output: { ...config.output },
    tracks: (config.tracks ?? []).map((track) => ({ ...track })),
    clips: config.clips.map((clip) => ({ ...clip, assetEntry: undefined })),
    registry: resolvedRegistry,
  };
  return {
    config,
    configVersion: 1,
    registry,
    resolvedConfig,
    rows: rowData.rows,
    meta: rowData.meta,
    effects: rowData.effects,
    assetMap,
    output: { ...config.output },
    tracks: (config.tracks ?? []).map((track) => ({ ...track })),
    clipOrder: rowData.clipOrder,
    signature: getConfigSignature(resolvedConfig),
    stableSignature: getStableConfigSignature(config, registry),
  };
}

interface TestHarness {
  provider: DataProvider;
  assetResolver: AssetResolver;
  saveTimeline: ReturnType<typeof vi.fn>;
  loadTimeline: ReturnType<typeof vi.fn>;
  loadAssetRegistry: ReturnType<typeof vi.fn>;
  interactionStateRef: InteractionStateRef;
  dataRef: { current: TimelineData | null };
  scheduleSave: (data: TimelineData) => void;
  reloadFromServer: () => Promise<void>;
}

interface SetupOptions {
  initialData?: TimelineData;
  persistenceEnabled?: boolean;
  saveTimelineImpl?: (
    timelineId: string,
    config: TimelineData['config'],
    expectedVersion: number,
    registry?: AssetRegistry,
  ) => Promise<number>;
  loadTimelineImpl?: DataProvider['loadTimeline'];
  loadAssetRegistryImpl?: DataProvider['loadAssetRegistry'];
}

function setup(options?: SetupOptions): TestHarness {
  const saveTimeline = vi.fn(
    options?.saveTimelineImpl
      ?? (async (_id: string, _config: TimelineData['config'], _version: number, _registry?: AssetRegistry) => 2),
  );
  const loadTimeline = vi.fn(
    options?.loadTimelineImpl
      ?? (async () => ({ config: createDefaultTimelineConfig(), configVersion: 1 })),
  );
  const loadAssetRegistry = vi.fn(options?.loadAssetRegistryImpl ?? (async () => ({ assets: {} })));
  const provider: DataProvider = {
    persistenceEnabled: options?.persistenceEnabled,
    loadTimeline,
    saveTimeline,
    loadAssetRegistry,
    resolveAssetUrl: vi.fn((file: string) => file),
  };
  const assetResolver: AssetResolver = {
    resolveAssetUrl: vi.fn((file: string) => Promise.resolve(file)),
  };

  const eventBus = new TimelineEventBus();
  const dataRef = { current: options?.initialData ?? makeTimelineData('initial') };
  const interactionStateRef: InteractionStateRef = { current: createInteractionState() };
  const commitData = vi.fn();
  const selectedClipIdRef = { current: null };
  const selectedTrackIdRef = { current: null };
  const editSeqRef = { current: 1 };
  const savedSeqRef = { current: 0 };
  const configVersionRef = { current: 1 };
  const lastSavedSignatureRef = { current: '' };

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);

  const hook = renderHook(
    () => useTimelinePersistence({
      provider,
      assetResolver,
      timelineId: 'timeline-1',
      eventBus,
      dataRef,
      commitData,
      selectedClipIdRef,
      selectedTrackIdRef,
      editSeqRef,
      savedSeqRef,
      configVersionRef,
      lastSavedSignatureRef,
      interactionStateRef,
    }),
    { wrapper },
  );

  return {
    provider,
    assetResolver,
    saveTimeline,
    loadTimeline,
    loadAssetRegistry,
    interactionStateRef,
    dataRef,
    scheduleSave: (data) => {
      dataRef.current = data;
      act(() => {
        hook.result.current.scheduleSave(data);
      });
    },
    reloadFromServer: () => hook.result.current.reloadFromServer(),
  };
}

describe('useTimelinePersistence — interaction gating', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('does NOT fire saveTimeline while a drag interaction is active', async () => {
    const harness = setup();
    harness.interactionStateRef.current.drag = true;

    harness.scheduleSave(makeTimelineData('mid-drag'));

    // Advance well past the 500ms debounce.
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(harness.saveTimeline).not.toHaveBeenCalled();
  });

  it('does NOT fire saveTimeline while a resize interaction is active', async () => {
    const harness = setup();
    harness.interactionStateRef.current.resize = true;

    harness.scheduleSave(makeTimelineData('mid-resize'));

    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(harness.saveTimeline).not.toHaveBeenCalled();
  });

  it('flushes the newest deferred payload after the gesture ends', async () => {
    const harness = setup();
    harness.interactionStateRef.current.drag = true;

    // First scheduled mid-drag — should be deferred and replaced.
    harness.scheduleSave(makeTimelineData('drag-1'));
    harness.scheduleSave(makeTimelineData('drag-2'));
    harness.scheduleSave(makeTimelineData('drag-3'));

    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });
    expect(harness.saveTimeline).not.toHaveBeenCalled();

    // End the gesture.
    await act(async () => {
      harness.interactionStateRef.current.drag = false;
      notifyInteractionEndIfIdle(harness.interactionStateRef);
      // Now scheduleSave's setTimeout(500) should fire.
      vi.advanceTimersByTime(600);
      await Promise.resolve();
    });

    expect(harness.saveTimeline).toHaveBeenCalledTimes(1);
    // Should have flushed the newest payload — output.file ends with 'drag-3'.
    const args = harness.saveTimeline.mock.calls[0]?.[1];
    expect(args?.output.file).toBe('output-drag-3.mp4');
  });

  it('keeps save deferred until both drag and resize interactions are idle', async () => {
    const harness = setup();
    harness.interactionStateRef.current.drag = true;
    harness.interactionStateRef.current.resize = true;

    harness.scheduleSave(makeTimelineData('both-active'));

    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });
    expect(harness.saveTimeline).not.toHaveBeenCalled();

    await act(async () => {
      harness.interactionStateRef.current.drag = false;
      notifyInteractionEndIfIdle(harness.interactionStateRef);
      vi.advanceTimersByTime(600);
      await Promise.resolve();
    });

    expect(harness.saveTimeline).not.toHaveBeenCalled();

    await act(async () => {
      harness.interactionStateRef.current.resize = false;
      notifyInteractionEndIfIdle(harness.interactionStateRef);
      vi.advanceTimersByTime(600);
      await Promise.resolve();
    });

    expect(harness.saveTimeline).toHaveBeenCalledTimes(1);
    const args = harness.saveTimeline.mock.calls[0]?.[1];
    expect(args?.output.file).toBe('output-both-active.mp4');
  });

  it('schedules saves normally when no interaction is active', async () => {
    const harness = setup();

    harness.scheduleSave(makeTimelineData('normal'));

    await act(async () => {
      vi.advanceTimersByTime(600);
      await Promise.resolve();
    });

    expect(harness.saveTimeline).toHaveBeenCalledTimes(1);
  });

  it('suppresses autosave when provider persistence is disabled', async () => {
    const harness = setup({ persistenceEnabled: false });

    harness.scheduleSave(makeTimelineData('read-only'));

    await act(async () => {
      vi.advanceTimersByTime(600);
      await Promise.resolve();
    });

    expect(harness.saveTimeline).not.toHaveBeenCalled();
  });

  it('doSave passes registry to saveTimeline', async () => {
    const harness = setup();
    const registry = makeRegistry('save');
    const nextData = makeTimelineData('with-registry', registry);

    harness.scheduleSave(nextData);

    await act(async () => {
      vi.advanceTimersByTime(600);
      await Promise.resolve();
    });

    expect(harness.saveTimeline).toHaveBeenCalledTimes(1);
    expect(harness.saveTimeline).toHaveBeenCalledWith('timeline-1', nextData.config, 1, registry);
  });

  it('conflict retry reloads registry and updates dataRef', async () => {
    const staleRegistry = makeRegistry('stale');
    const freshRegistry = makeRegistry('fresh');
    const nextData = makeTimelineData('conflict', staleRegistry);
    let saveAttempt = 0;
    const harness = setup({
      initialData: nextData,
      saveTimelineImpl: async (_id, _config, _version, _registry) => {
        saveAttempt += 1;
        if (saveAttempt === 1) {
          throw new TimelineVersionConflictError();
        }
        return 2;
      },
      loadTimelineImpl: async () => ({ config: nextData.config, configVersion: 2 }),
      loadAssetRegistryImpl: async () => freshRegistry,
    });

    harness.scheduleSave(nextData);

    await act(async () => {
      vi.advanceTimersByTime(600);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(harness.loadAssetRegistry).toHaveBeenCalledWith('timeline-1');
    expect(harness.saveTimeline).toHaveBeenCalledTimes(2);
    expect(harness.saveTimeline.mock.calls[0]?.[3]).toEqual(staleRegistry);
    expect(harness.saveTimeline.mock.calls[1]?.[3]).toEqual(freshRegistry);
    expect(harness.dataRef.current?.registry).toEqual(freshRegistry);
  });

  it('reloadFromServer rebuilds timeline data through the asset resolver', async () => {
    const registry = makeRegistry('reload');
    const base = createDefaultTimelineConfig();
    const loadedConfig = {
      ...base,
      output: { ...base.output, file: 'output-reload.mp4' },
      tracks: (base.tracks ?? []).map((track) => ({ ...track })),
      clips: [{
        id: 'clip-reload',
        at: 0,
        track: 'V1' as const,
        clipType: 'media' as const,
        asset: 'asset-reload',
        from: 0,
        to: 2,
      }],
    };
    const harness = setup({
      initialData: makeTimelineData('reload-initial', registry),
      loadTimelineImpl: async () => ({ config: loadedConfig, configVersion: 3 }),
      loadAssetRegistryImpl: async () => registry,
    });

    harness.assetResolver.onResolve = vi.fn(async ({ file }) => `resolved:${file}`);

    await act(async () => {
      await harness.reloadFromServer();
    });

    expect(harness.assetResolver.onResolve).toHaveBeenCalledWith({
      file: 'media/reload.mp4',
      timelineId: 'timeline-1',
    });
  });
});
