// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DataProviderWrapper, type VideoEditorRuntimeContextValue } from '@/tools/video-editor/contexts/DataProviderContext';
import { createCommandRegistry, type CommandRegistry } from '@/tools/video-editor/runtime/commandRegistry';
import { TrackLabelContent } from '@/tools/video-editor/components/TimelineEditor/TrackLabel';
import { TrackListRenderer } from '@/tools/video-editor/components/TimelineEditor/TrackListRenderer';
import type { TrackDefinition } from '@/tools/video-editor/types';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas';
import type { ReighExtension } from '@reigh/editor-sdk';

const tracks: TrackDefinition[] = [
  { id: 'V1', kind: 'visual', label: 'V1' },
  { id: 'V2', kind: 'visual', label: 'V2' },
];

const rows: TimelineRow[] = [
  {
    id: 'V1',
    actions: [{ id: 'clip-1', start: 0, end: 2, effectId: 'effect-clip-1' }],
  },
  {
    id: 'V2',
    actions: [{ id: 'clip-2', start: 2, end: 4, effectId: 'effect-clip-2' }],
  },
];

function buildRuntime(commandRegistry: CommandRegistry): VideoEditorRuntimeContextValue {
  const extension = {
    manifest: {
      id: 'ext.track',
      version: '1.0.0',
      label: 'Track Extension',
    },
  } as ReighExtension;

  return {
    provider: {} as VideoEditorRuntimeContextValue['provider'],
    assetResolver: {} as VideoEditorRuntimeContextValue['assetResolver'],
    auth: { userId: 'user-1' },
    project: { projectId: 'project-1' },
    shots: {} as VideoEditorRuntimeContextValue['shots'],
    mediaLightbox: {} as VideoEditorRuntimeContextValue['mediaLightbox'],
    agentChat: {} as VideoEditorRuntimeContextValue['agentChat'],
    toast: {
      error: vi.fn(),
      success: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
    telemetry: {
      log: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    },
    timelineId: 'timeline-1',
    userId: 'user-1',
    extensions: {
      slots: {},
      dialogHost: { dialogs: [] },
      registry: { panels: [], inspectorSections: [] },
      overlays: [],
    },
    extensionRuntime: {
      extensions: [extension],
      byId: new Map([['ext.track', extension]]),
    } as VideoEditorRuntimeContextValue['extensionRuntime'],
    commandRegistry,
  };
}

function registerTrackMenuCommand(
  registry: CommandRegistry,
  options: {
    command?: string;
    label?: string;
    menuLabel?: string;
    when?: string;
    handler?: Parameters<CommandRegistry['registerCommand']>[2];
  } = {},
) {
  const command = options.command ?? 'ext.track.run';
  registry.ingestCommandContribution('ext.track', {
    id: `${command}.command` as never,
    kind: 'command',
    command,
    label: options.label ?? 'Run track command',
  });
  registry.ingestContextMenuItemContribution('ext.track', {
    id: `${command}.menu` as never,
    kind: 'contextMenuItem',
    command,
    target: 'track',
    label: options.menuLabel,
    when: options.when,
  });
  registry.registerCommand('ext.track', command, options.handler ?? vi.fn());
}

describe('TrackListRenderer', () => {
  it('keeps unaffected row action renders stable when the clamp ring changes for another row', () => {
    const getActionRender = vi.fn((_action, _row, _width) => <div>clip</div>);
    const props = {
      rows,
      tracks,
      rowHeight: 48,
      startLeft: 0,
      pixelsPerSecond: 100,
      selectedTrackId: null,
      resizeClampedActionId: null,
      rowResizePreview: [{}, {}],
      resizeHandleWidth: 8,
      getActionRender,
      onSelectTrack: vi.fn(),
      onTrackChange: vi.fn(),
      onRemoveTrack: vi.fn(),
      onTrackDragEnd: vi.fn(),
      trackSensors: [] as never,
    } satisfies React.ComponentProps<typeof TrackListRenderer>;

    const { rerender } = render(<TrackListRenderer {...props} />);

    expect(getActionRender).toHaveBeenCalledTimes(2);
    expect(getActionRender.mock.calls.map(([action]) => action.id)).toEqual(['clip-1', 'clip-2']);

    rerender(
      <TrackListRenderer
        {...props}
        resizeClampedActionId="clip-1"
      />,
    );

    expect(getActionRender).toHaveBeenCalledTimes(3);
    expect(getActionRender.mock.calls.at(-1)?.[0].id).toBe('clip-1');
  });

  it('renders eligible extension track menu items and invokes with a snapshotted track target', async () => {
    const registry = createCommandRegistry();
    const handler = vi.fn();
    registerTrackMenuCommand(registry, {
      menuLabel: 'Analyze track',
      when: 'target.target == "track" && target.trackId == "V1"',
      handler,
    });
    const onSelectTrack = vi.fn();
    const props = {
      rows,
      tracks,
      rowHeight: 48,
      startLeft: 0,
      pixelsPerSecond: 100,
      selectedTrackId: null,
      resizeClampedActionId: null,
      rowResizePreview: [{}, {}],
      resizeHandleWidth: 8,
      getActionRender: vi.fn((_action, _row, _width) => <div>clip</div>),
      onSelectTrack,
      onTrackChange: vi.fn(),
      onRemoveTrack: vi.fn(),
      onTrackDragEnd: vi.fn(),
      trackSensors: [] as never,
    } satisfies React.ComponentProps<typeof TrackListRenderer>;

    const { container } = render(
      <DataProviderWrapper value={buildRuntime(registry)}>
        <TrackListRenderer {...props} />
      </DataProviderWrapper>,
    );

    fireEvent.contextMenu(container.querySelector('[data-track-id="V1"]') as HTMLElement);
    fireEvent.click(screen.getByText('Analyze track'));

    await waitFor(() => expect(handler).toHaveBeenCalledTimes(1));
    expect(onSelectTrack).toHaveBeenCalledWith('V1');
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({
      commandId: 'ext.track.run',
      extensionId: 'ext.track',
      target: { target: 'track', trackId: 'V1' },
    }));
  });

  it('preserves the native track context menu when no extension items are eligible', () => {
    const registry = createCommandRegistry();
    registerTrackMenuCommand(registry, {
      menuLabel: 'Hidden track action',
      when: 'target.trackId == "missing"',
    });
    const onSelectTrack = vi.fn();
    const { container } = render(
      <DataProviderWrapper value={buildRuntime(registry)}>
        <TrackLabelContent
          track={tracks[0]}
          isSelected={false}
          hasClips
          onSelect={onSelectTrack}
          onChange={vi.fn()}
          onRemove={vi.fn()}
        />
      </DataProviderWrapper>,
    );
    const event = new MouseEvent('contextmenu', { bubbles: true, cancelable: true });

    container.firstElementChild?.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
    expect(onSelectTrack).not.toHaveBeenCalled();
    expect(screen.queryByText('Hidden track action')).not.toBeInTheDocument();
  });

  it('filters track context menu contributions by predicate without hiding eligible items', () => {
    const registry = createCommandRegistry();
    registerTrackMenuCommand(registry, {
      command: 'ext.track.visible',
      menuLabel: 'Visible track action',
      when: 'target.target == "track" && target.trackId == "V1"',
    });
    registerTrackMenuCommand(registry, {
      command: 'ext.track.hidden',
      menuLabel: 'Hidden track action',
      when: 'target.trackId == "V2"',
    });
    const { container } = render(
      <DataProviderWrapper value={buildRuntime(registry)}>
        <TrackLabelContent
          track={tracks[0]}
          isSelected={false}
          hasClips
          onSelect={vi.fn()}
          onChange={vi.fn()}
          onRemove={vi.fn()}
        />
      </DataProviderWrapper>,
    );

    fireEvent.contextMenu(container.firstElementChild as HTMLElement);

    expect(screen.getByText('Visible track action')).toBeInTheDocument();
    expect(screen.queryByText('Hidden track action')).not.toBeInTheDocument();
  });

  it('invokes track items with the target captured when the menu opened', async () => {
    const registry = createCommandRegistry();
    const handler = vi.fn();
    registerTrackMenuCommand(registry, {
      command: 'ext.track.snapshot',
      menuLabel: 'Snapshot track',
      handler,
    });
    const renderTrack = (track: TrackDefinition) => (
      <DataProviderWrapper value={buildRuntime(registry)}>
        <TrackLabelContent
          track={track}
          isSelected={false}
          hasClips={false}
          onSelect={vi.fn()}
          onChange={vi.fn()}
          onRemove={vi.fn()}
        />
      </DataProviderWrapper>
    );
    const { container, rerender } = render(renderTrack(tracks[0]));

    fireEvent.contextMenu(container.firstElementChild as HTMLElement);
    rerender(renderTrack({ ...tracks[0], label: 'Renamed V1' }));
    fireEvent.click(screen.getByText('Snapshot track'));

    await waitFor(() => expect(handler).toHaveBeenCalledTimes(1));
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({
      commandId: 'ext.track.snapshot',
      extensionId: 'ext.track',
      target: { target: 'track', trackId: 'V1' },
    }));
  });

  it('diagnoses stale snapshotted track targets instead of invoking extension handlers', async () => {
    const registry = createCommandRegistry();
    const staleToast = vi.fn();
    registry.setCallbacks({
      onContextMenuStaleTarget: staleToast,
    });
    const handler = vi.fn();
    registerTrackMenuCommand(registry, {
      command: 'ext.track.stale',
      menuLabel: 'Use stale track',
      handler,
    });
    const renderTrack = (track: TrackDefinition) => (
      <DataProviderWrapper value={buildRuntime(registry)}>
        <TrackLabelContent
          track={track}
          isSelected={false}
          hasClips={false}
          onSelect={vi.fn()}
          onChange={vi.fn()}
          onRemove={vi.fn()}
        />
      </DataProviderWrapper>
    );
    const { container, rerender } = render(renderTrack(tracks[0]));

    fireEvent.contextMenu(container.firstElementChild as HTMLElement);
    rerender(renderTrack({ id: 'V9', kind: 'visual', label: 'V9' }));
    fireEvent.click(screen.getByText('Use stale track'));

    expect(handler).not.toHaveBeenCalled();
    expect(staleToast).toHaveBeenCalledWith(
      'ext.track.stale',
      'ext.track',
      'Track "V1" is no longer available.',
    );
    expect(registry.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'command-registry/context-menu-stale-target',
        extensionId: 'ext.track',
      }),
    ]));
  });
});
