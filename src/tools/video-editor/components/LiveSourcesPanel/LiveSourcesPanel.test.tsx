// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import {
  LiveSourcesPanel,
  removeLiveBindingsFromResolvedConfig,
} from '@/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel';
import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry';
import type { LivePermissionService } from '@/tools/video-editor/runtime/livePermissions';
import type { ResolvedTimelineConfig, TimelineConfig } from '@/tools/video-editor/types/index';
import type { LiveChannelDescriptor } from '@reigh/editor-sdk';

function makeTimelineConfig(sourceId: string, status?: string): TimelineConfig {
  return {
    output: { fps: 30, resolution: '1920x1080' },
    tracks: [{ id: 'V1', kind: 'video', label: 'Video' }],
    clips: [
      {
        id: 'clip-1',
        at: 0,
        track: 'V1',
        asset: 'asset-1',
        from: 0,
        to: 2,
        app: {
          live: {
            bindings: [
              {
                bindingId: 'binding-1',
                sourceId,
                sourceKind: 'generated',
                targetParamName: 'opacity',
                ...(status ? { sourceStatus: status } : {}),
              },
            ],
          },
        },
      },
    ],
  };
}

function makeResolvedConfig(): ResolvedTimelineConfig {
  return {
    output: { fps: 30, resolution: '1920x1080' },
    tracks: [{ id: 'V1', kind: 'video', label: 'Video' }],
    registry: {},
    clips: [
      {
        id: 'clip-1',
        at: 0,
        track: 'V1',
        asset: 'asset-1',
        from: 0,
        to: 2,
        app: {
          live: {
            bindings: [
              { bindingId: 'a', sourceId: 'src-a', sourceKind: 'generated' },
              { bindingId: 'b', sourceId: 'src-b', sourceKind: 'generated' },
            ],
          },
        },
        params: {
          liveBindings: [
            { bindingId: 'c', sourceId: 'src-a', sourceKind: 'midi' },
          ],
          prompt: 'keep me',
        },
      },
    ],
  };
}

function fakePermissionService(): LivePermissionService {
  return {
    probe: (sourceKind) => ({
      sourceKind,
      apiKind: 'none',
      apiAvailable: true,
      permission: { state: 'prompt', reason: 'Connect live source' },
    }),
    request: vi.fn(async (sourceKind) => ({
      sourceKind,
      apiKind: 'none',
      apiAvailable: true,
      userGranted: true,
      permission: { state: 'granted', reason: 'Connect live source' },
    })),
    release: vi.fn(),
    releaseAll: vi.fn(),
    getDisposeHandle: () => ({ dispose: vi.fn() }),
    get isDisposed() {
      return false;
    },
  };
}

describe('LiveSourcesPanel', () => {
  it('renders live source status, permission, recording, preview health, diagnostics, and export blockers', () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({
      id: 'src-live',
      kind: 'generated',
      label: 'Preview generator',
      permission: { state: 'prompt', reason: 'Connect live source' },
      recording: { active: true, mode: 'take', takeIndex: 2 },
    });
    const channelId = registry.openChannel('src-live', 'video');
    registry.emitDiagnostic('src-live', {
      severity: 'warning',
      code: 'live/test-warning',
      message: 'Preview frame is late.',
    });
    registry.pushSample(channelId, {
      timestamp: 42,
      format: 'json',
      data: { src: 'frame.png' },
    });

    render(
      <LiveSourcesPanel
        timelineConfig={makeTimelineConfig('src-live')}
        liveDataRegistry={registry}
        livePermissionService={fakePermissionService()}
      />,
    );

    expect(screen.getByText('Live Sources')).toBeTruthy();
    expect(screen.getByText('Export blocked')).toBeTruthy();
    expect(screen.getByText('Preview generator')).toBeTruthy();
    expect(screen.getByText('active')).toBeTruthy();
    expect(screen.getByText('permission prompt')).toBeTruthy();
    expect(screen.getByText('recording (take 2)')).toBeTruthy();
    expect(screen.getByText(/1 samples/)).toBeTruthy();
    expect(screen.getByText(/latest 0 @ 42ms/)).toBeTruthy();
    expect(screen.getByText('Preview frame is late.')).toBeTruthy();
  });

  it('requests permission and updates the prompt state', async () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({
      id: 'src-permission',
      kind: 'generated',
      label: 'Prompted source',
      permission: { state: 'prompt' },
    });
    const permissions = fakePermissionService();

    render(
      <LiveSourcesPanel
        timelineConfig={makeTimelineConfig('src-permission', 'inactive')}
        liveDataRegistry={registry}
        livePermissionService={permissions}
      />,
    );

    fireEvent.click(screen.getByText('Permit'));

    await waitFor(() => expect(permissions.request).toHaveBeenCalledWith('generated'));
    await waitFor(() => expect(screen.getByText('permission granted')).toBeTruthy());
  });

  it('runs bake, remove, and reconnect actions for a runtime source', async () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-actions', kind: 'generated', label: 'Action source' });
    const channelId = registry.openChannel('src-actions', 'data');
    registry.pushSample(channelId, {
      timestamp: 10,
      format: 'json',
      data: { value: 1 },
    });
    registry.transitionSource('src-actions', 'inactive', 'test');
    const bakeSpy = vi.spyOn(registry, 'bake');
    const removeSpy = vi.spyOn(registry, 'removeLiveBindings');
    const onRemoveSourceBindings = vi.fn();

    render(
      <LiveSourcesPanel
        timelineConfig={makeTimelineConfig('src-actions', 'inactive')}
        liveDataRegistry={registry}
        onRemoveSourceBindings={onRemoveSourceBindings}
      />,
    );

    fireEvent.click(screen.getByText('Bake'));
    expect(bakeSpy).toHaveBeenCalledWith(expect.objectContaining({
      sourceId: 'src-actions',
      channelIds: [channelId as LiveChannelDescriptor],
    }));
    expect(screen.getByText(/Bake queued deterministic refs|Bake failed/)).toBeTruthy();

    fireEvent.click(screen.getByText('Remove'));
    expect(removeSpy).toHaveBeenCalledWith('src-actions');
    expect(onRemoveSourceBindings).toHaveBeenCalledWith('src-actions');

    fireEvent.click(screen.getByText('Reconnect'));
    await waitFor(() => expect(screen.getByText('activating')).toBeTruthy());
  });

  it('passes selected partial-bake range and take ID to the registry bake action', () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-range', kind: 'generated', label: 'Range source' });
    const channelId = registry.openChannel('src-range', 'video');
    registry.pushSample(channelId, {
      timestamp: 10,
      format: 'raw',
      data: new Uint8Array([1]),
      metadata: { frameIndex: 12, takeId: 'take-a' },
    });
    const bakeSpy = vi.spyOn(registry, 'bake');

    render(
      <LiveSourcesPanel
        timelineConfig={makeTimelineConfig('src-range')}
        liveDataRegistry={registry}
      />,
    );

    fireEvent.change(screen.getByLabelText('Bake range start for src-range'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('Bake range end for src-range'), { target: { value: '20' } });
    fireEvent.change(screen.getByLabelText('Bake take ID for src-range'), { target: { value: 'take-a' } });
    fireEvent.click(screen.getByText('Bake'));

    expect(bakeSpy).toHaveBeenCalledWith(expect.objectContaining({
      sourceId: 'src-range',
      channelIds: [channelId as LiveChannelDescriptor],
      frameRange: [10, 20],
      takeId: 'take-a',
    }));
  });

  it('validates mapping starts and shows learn-mode feedback through candidate acceptance', async () => {
    const invalidRegistry = createLiveDataRegistry();
    invalidRegistry.registerSource({ id: 'src-invalid-map', kind: 'midi', label: 'No channel source' });

    const invalid = render(
      <LiveSourcesPanel
        timelineConfig={makeTimelineConfig('src-invalid-map')}
        liveDataRegistry={invalidRegistry}
      />,
    );

    fireEvent.click(screen.getByText('Learn'));
    expect(screen.getByText('Learn mapping requires an active channel.')).toBeTruthy();
    invalid.unmount();

    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-learn', kind: 'midi', label: 'Learn source', learnMode: 'mapping' });
    const channelId = registry.openChannel('src-learn', 'control');
    const { unmount } = render(
      <LiveSourcesPanel
        timelineConfig={makeTimelineConfig('src-learn')}
        liveDataRegistry={registry}
      />,
    );

    expect(screen.getByText('mapping')).toBeTruthy();
    fireEvent.click(screen.getByText('Learn'));
    expect(screen.getByText(/Waiting for the next sample/)).toBeTruthy();

    registry.pushSample(channelId, {
      timestamp: 16,
      format: 'json',
      data: { controller: { knob: 0.7 } },
    });

    await waitFor(() => expect(screen.getByText('Mapping candidate captured.')).toBeTruthy());
    fireEvent.click(screen.getByText('Accept mapping'));

    await waitFor(() => expect(screen.getByText('Mapping accepted.')).toBeTruthy());
    expect(screen.getByText('opacity')).toBeTruthy();

    unmount();
  });

  it('renders audio-analysis overlay empty and error states', async () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-audio', kind: 'microphone', label: 'Mic source' });
    const channelId = registry.openChannel('src-audio', 'audio');

    render(
      <LiveSourcesPanel
        timelineConfig={makeTimelineConfig('src-audio')}
        liveDataRegistry={registry}
      />,
    );

    expect(screen.getByText('Audio analysis waiting for samples.')).toBeTruthy();

    registry.pushSample(channelId, {
      timestamp: 20,
      format: 'json',
      data: { note: 'not analysis' },
    });

    await waitFor(() => expect(screen.getByText('Audio analysis sample has no rms, amplitude, peak, or fft values.')).toBeTruthy());
  });

  it('accepts and discards takes from the take-review player', async () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-takes', kind: 'generated', label: 'Take source' });
    const channelId = registry.openChannel('src-takes', 'control');
    registry.pushSample(channelId, {
      timestamp: 25,
      format: 'json',
      data: { value: 1 },
    });

    render(
      <LiveSourcesPanel
        timelineConfig={makeTimelineConfig('src-takes')}
        liveDataRegistry={registry}
      />,
    );

    fireEvent.click(screen.getByText('Start'));
    fireEvent.click(screen.getByText('Stop'));
    expect(screen.getByText(/Take 1 · captured · 1 samples/)).toBeTruthy();

    fireEvent.click(screen.getByText('Accept'));
    await waitFor(() => expect(screen.getByText('Take take-1 accepted.')).toBeTruthy());
    expect(screen.getByText(/Take 1 · accepted · 1 samples/)).toBeTruthy();

    fireEvent.click(screen.getByText('Start'));
    fireEvent.click(screen.getByText('Stop'));
    expect(screen.getByText(/Take 2 · captured · 1 samples/)).toBeTruthy();

    fireEvent.click(screen.getAllByText('Discard')[1]);
    await waitFor(() => expect(screen.getByText('Take take-2 discarded.')).toBeTruthy());
    expect(screen.getByText(/Take 2 · discarded · 1 samples/)).toBeTruthy();
  });

  it('shows orphaned and disposed guidance for persisted bindings without a live source', () => {
    const registry = createLiveDataRegistry();
    const handle = registry.registerSource({ id: 'src-disposed', kind: 'generated', label: 'Disposed source' });
    handle.dispose();

    render(
      <LiveSourcesPanel
        timelineConfig={makeTimelineConfig('src-disposed')}
        liveDataRegistry={registry}
      />,
    );

    expect(screen.getByText('disposed')).toBeTruthy();
    expect(screen.getByText('Export blocked')).toBeTruthy();
    expect(screen.getByText(/Persisted bindings remain export-blocking/)).toBeTruthy();
    expect(screen.getByTitle('Cannot reconnect a missing, disposed, or orphaned runtime source')).toBeDisabled();
  });

  it('removes persisted live binding metadata for one source without deleting other params', () => {
    const resolved = makeResolvedConfig();
    const next = removeLiveBindingsFromResolvedConfig(resolved, 'src-a');

    expect(next).not.toBeNull();
    expect(next!.clips[0].app?.live).toEqual({
      bindings: [{ bindingId: 'b', sourceId: 'src-b', sourceKind: 'generated' }],
    });
    expect(next!.clips[0].params).toEqual({ prompt: 'keep me' });
    expect(removeLiveBindingsFromResolvedConfig(next!, 'missing-source')).toBeNull();
  });
});
