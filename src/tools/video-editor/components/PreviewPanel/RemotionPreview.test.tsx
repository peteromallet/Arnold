// @vitest-environment jsdom
import React, { createRef } from 'react';
import { act, render } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { RemotionPreview } from '@/tools/video-editor/components/PreviewPanel/RemotionPreview';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';

const playerListeners = new Map<string, Set<(...args: any[]) => void>>();
const playerPropsHistory: Array<{ config: ResolvedTimelineConfig }> = [];
const playerHandles: Array<{ seekTo: ReturnType<typeof vi.fn> }> = [];

vi.mock('@remotion/player', async () => {
  const React = await import('react');

  return {
    Player: React.forwardRef(function MockPlayer(props: any, ref) {
      playerPropsHistory.push({ config: props.inputProps.config });
      React.useImperativeHandle(ref, () => ({
        addEventListener: (name: string, listener: (...args: any[]) => void) => {
          if (!playerListeners.has(name)) {
            playerListeners.set(name, new Set());
          }
          playerListeners.get(name)!.add(listener);
        },
        removeEventListener: (name: string, listener: (...args: any[]) => void) => {
          playerListeners.get(name)?.delete(listener);
        },
        seekTo: (() => {
          const seekTo = vi.fn();
          playerHandles.push({ seekTo });
          return seekTo;
        })(),
        play: vi.fn(),
        pause: vi.fn(),
        toggle: vi.fn(),
        isPlaying: vi.fn(() => false),
      }), []);

      return <div data-testid="mock-player" />;
    }),
  };
});

function emitPlayerEvent(name: string, detail: unknown = undefined) {
  const listeners = playerListeners.get(name);
  if (!listeners) {
    return;
  }

  for (const listener of listeners) {
    listener({ detail });
  }
}

function makeConfig(label: string): ResolvedTimelineConfig {
  return {
    output: {
      fps: 30,
      resolution: '1280x720',
      file: `${label}.mp4`,
    },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [{
      id: `clip-${label}`,
      at: 0,
      track: 'V1',
      clipType: 'hold',
      hold: 1,
    }],
    registry: {},
  };
}

describe('RemotionPreview', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    playerListeners.clear();
    playerPropsHistory.length = 0;
    playerHandles.length = 0;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('holds config updates while playing and flushes them on pause', async () => {
    const onTimeUpdate = vi.fn();
    const playerContainerRef = createRef<HTMLDivElement>();
    const initialConfig = makeConfig('initial');
    const nextConfig = makeConfig('next');

    const { rerender } = render(
      <RemotionPreview
        config={initialConfig}
        onTimeUpdate={onTimeUpdate}
        playerContainerRef={playerContainerRef}
      />,
    );

    act(() => {
      vi.runAllTimers();
    });

    expect(playerPropsHistory.at(-1)?.config).toBe(initialConfig);

    act(() => {
      emitPlayerEvent('play');
    });

    rerender(
      <RemotionPreview
        config={nextConfig}
        onTimeUpdate={onTimeUpdate}
        playerContainerRef={playerContainerRef}
      />,
    );

    act(() => {
      vi.runAllTimers();
    });

    expect(playerPropsHistory.at(-1)?.config).toBe(initialConfig);

    act(() => {
      emitPlayerEvent('pause');
    });

    await act(async () => {});

    expect(playerPropsHistory.at(-1)?.config).toBe(nextConfig);
  });

  it('seeks the player when timeline playback context currentTime changes outside playback', () => {
    const onTimeUpdate = vi.fn();
    const playerContainerRef = createRef<HTMLDivElement>();
    const config = makeConfig('seek');

    const { rerender } = render(
      <RemotionPreview
        config={config}
        currentTime={0}
        onTimeUpdate={onTimeUpdate}
        playerContainerRef={playerContainerRef}
      />,
    );

    expect(playerHandles.at(-1)?.seekTo).toHaveBeenLastCalledWith(0);

    rerender(
      <RemotionPreview
        config={config}
        currentTime={0.5}
        onTimeUpdate={onTimeUpdate}
        playerContainerRef={playerContainerRef}
      />,
    );

    expect(playerHandles.at(-1)?.seekTo).toHaveBeenLastCalledWith(15);

    act(() => {
      emitPlayerEvent('play');
    });

    rerender(
      <RemotionPreview
        config={config}
        currentTime={0.75}
        onTimeUpdate={onTimeUpdate}
        playerContainerRef={playerContainerRef}
      />,
    );

    expect(playerHandles.at(-1)?.seekTo).not.toHaveBeenLastCalledWith(23);
  });
});
