// @vitest-environment jsdom

import type { FC, PropsWithChildren } from 'react';
import { useEffect } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createTransitionRegistry,
  TransitionRegistryProvider,
  useTransitionRegistryContext,
  type TransitionRegistryRecord,
} from '@/tools/video-editor/transitions/registry/index.ts';
import { VisualClip } from '@/tools/video-editor/compositions/VisualClip.tsx';
import type { ResolvedTimelineClip, TrackDefinition } from '@/tools/video-editor/types/index.ts';
import type { RenderMaterialRef } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Remotion mocks (mirrors ClipEffectsSnapshot.test.tsx)
// ---------------------------------------------------------------------------

let currentFrame = 0;

vi.mock('remotion', async () => ({
  AbsoluteFill: ({ children, style, ...props }: PropsWithChildren<Record<string, unknown>>) => (
    <div data-testid="absolute-fill" data-style={JSON.stringify(style)} {...props}>{children}</div>
  ),
  Img: ({ src, ...props }: Record<string, unknown>) => (
    <div data-testid="image-asset" data-src={String(src)} {...props} />
  ),
  Sequence: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
    <div data-testid="sequence" {...props}>{children}</div>
  ),
  interpolate: () => 0.5,
  useCurrentFrame: () => currentFrame,
  useVideoConfig: () => ({ fps: 30, width: 1920, height: 1080 }),
}));

vi.mock('@remotion/media', () => ({
  Video: ({ src, ...props }: Record<string, unknown>) => (
    <div data-testid="video-asset" data-src={String(src)} {...props} />
  ),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const track: TrackDefinition = {
  id: 'V1',
  type: 'video',
};

function mediaClip(overrides?: Partial<ResolvedTimelineClip>): ResolvedTimelineClip {
  return {
    id: 'clip-1',
    clipType: 'media',
    track: 'V1',
    at: 0,
    hold: 1,
    assetEntry: {
      id: 'asset-1',
      type: 'image/png',
      src: 'https://example.test/image.png',
    },
    ...overrides,
  };
}

function makeTransitionRecord(
  transitionId: string,
  renderer: TransitionRegistryRecord['renderer'],
  overrides?: Partial<TransitionRegistryRecord>,
): TransitionRegistryRecord {
  return {
    transitionId,
    contributionId: `test:${transitionId}`,
    renderer,
    provenance: 'trusted-loader',
    ownerExtensionId: 'test-extension',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

function materialRef(overrides: Partial<RenderMaterialRef> = {}): RenderMaterialRef {
  return {
    id: 'mat-1',
    mediaKind: 'image',
    locator: { kind: 'url', uri: 'https://example.test/material.png' },
    producerExtensionId: 'ext.materials',
    determinism: 'live-unbaked',
    replacementPolicy: 'materialize-on-export',
    ...overrides,
  };
}

// Provider-mounted record helper: registers a transition into the provider
// registry so it can be resolved by VisualClip.
function ProviderRecord({
  transitionId,
  renderer,
  children,
}: PropsWithChildren<{
  transitionId: string;
  renderer: TransitionRegistryRecord['renderer'];
}>) {
  const { registry } = useTransitionRegistryContext();

  useEffect(() => {
    const handle = registry.register(makeTransitionRecord(transitionId, renderer));
    return () => handle.dispose();
  }, [transitionId, renderer, registry]);

  return <>{children}</>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('VisualClip transition rendering', () => {
  afterEach(() => {
    currentFrame = 0;
    vi.restoreAllMocks();
  });

  it('renders pending, materializing, and failed material placeholders with diagnostics', () => {
    const ref = materialRef();
    const { rerender } = render(
      <VisualClip
        clip={mediaClip()}
        track={track}
        fps={30}
        materialRefs={[ref]}
        materialStatuses={[{ materialRefId: 'mat-1', state: 'unbaked', message: 'Queued for materialization' }]}
      />,
    );

    expect(screen.getByTestId('pending-material-placeholder')).toHaveAttribute('data-material-state', 'unbaked');
    expect(screen.getByText(/pending materialization: mat-1/)).toBeInTheDocument();

    rerender(
      <VisualClip
        clip={mediaClip()}
        track={track}
        fps={30}
        materialRefs={[ref]}
        materialStatuses={[{ materialRefId: 'mat-1', state: 'stale', message: 'Refreshing bytes' }]}
      />,
    );
    expect(screen.getByTestId('pending-material-placeholder')).toHaveAttribute('data-material-state', 'stale');
    expect(screen.getByText('Refreshing bytes')).toBeInTheDocument();

    rerender(
      <VisualClip
        clip={mediaClip()}
        track={track}
        fps={30}
        materialRefs={[ref]}
        materialStatuses={[{ materialRefId: 'mat-1', state: 'missing' }]}
        materialDiagnostics={[{ id: 'diag-1', severity: 'error', materialRefId: 'mat-1', message: 'Materialization failed' }]}
      />,
    );
    expect(screen.getByTestId('pending-material-placeholder')).toHaveAttribute('data-material-state', 'missing');
    expect(screen.getByText('Materialization failed')).toBeInTheDocument();
  });

  it('renders concrete material-backed clips normally when material is resolved', async () => {
    render(
      <VisualClip
        clip={mediaClip()}
        track={track}
        fps={30}
        materialRefs={[materialRef({ determinism: 'deterministic' })]}
        materialStatuses={[{ materialRefId: 'mat-1', state: 'resolved' }]}
      />,
    );

    await waitFor(() => expect(screen.getByTestId('image-asset')).toBeInTheDocument());
    expect(screen.queryByTestId('pending-material-placeholder')).not.toBeInTheDocument();
  });

  // -- Built-in transitions -------------------------------------------------

  it('resolves and renders a built-in transition (crossfade)', async () => {
    render(
      <TransitionRegistryProvider>
        <VisualClip
          clip={mediaClip({ transition: { type: 'crossfade', duration: 0.5 } })}
          track={track}
          fps={30}
        />
      </TransitionRegistryProvider>,
    );

    // The clip content should still render inside an AbsoluteFill with transition style
    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });
    // The AbsoluteFill should have overflow:hidden plus transition style
    const fill = screen.getByTestId('absolute-fill');
    const style = JSON.parse(fill.getAttribute('data-style') ?? '{}');
    expect(style.overflow).toBe('hidden');
  });

  it('resolves and renders built-in wipe transition', async () => {
    render(
      <TransitionRegistryProvider>
        <VisualClip
          clip={mediaClip({ transition: { type: 'wipe', duration: 0.5 } })}
          track={track}
          fps={30}
        />
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });
  });

  it('resolves and renders built-in slide-push transition', async () => {
    render(
      <TransitionRegistryProvider>
        <VisualClip
          clip={mediaClip({ transition: { type: 'slide-push', duration: 0.5 } })}
          track={track}
          fps={30}
        />
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });
  });

  it('resolves and renders built-in zoom-through transition', async () => {
    render(
      <TransitionRegistryProvider>
        <VisualClip
          clip={mediaClip({ transition: { type: 'zoom-through', duration: 0.5 } })}
          track={track}
          fps={30}
        />
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });
  });

  // -- Contributed transitions -----------------------------------------------

  it('resolves and renders a contributed transition from the provider registry', async () => {
    const contributedRenderer = vi.fn(() => ({ transform: 'scale(0.5)' }));

    render(
      <TransitionRegistryProvider>
        <ProviderRecord transitionId="custom-spin" renderer={contributedRenderer}>
          <VisualClip
            clip={mediaClip({ transition: { type: 'custom-spin', duration: 0.5 } })}
            track={track}
            fps={30}
          />
        </ProviderRecord>
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });

    // The contributed renderer should have been called
    expect(contributedRenderer).toHaveBeenCalled();
  });

  it('passes transition progress and params to contributed renderer', async () => {
    const contributedRenderer = vi.fn(() => ({ opacity: 0.5 }));

    render(
      <TransitionRegistryProvider>
        <ProviderRecord transitionId="custom-wipe" renderer={contributedRenderer}>
          <VisualClip
            clip={mediaClip({
              transition: {
                type: 'custom-wipe',
                duration: 0.8,
                params: { direction: 'left', intensity: 0.7 },
              },
            })}
            track={track}
            fps={30}
          />
        </ProviderRecord>
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });

    // The renderer should be called with progress (0.5 from mock) and params
    expect(contributedRenderer).toHaveBeenCalledWith(
      0.5,
      { direction: 'left', intensity: 0.7 },
    );
  });

  it('passes empty params object when clip transition has no params', async () => {
    const contributedRenderer = vi.fn(() => ({}));

    render(
      <TransitionRegistryProvider>
        <ProviderRecord transitionId="plain-transition" renderer={contributedRenderer}>
          <VisualClip
            clip={mediaClip({
              transition: { type: 'plain-transition', duration: 0.5 },
            })}
            track={track}
            fps={30}
          />
        </ProviderRecord>
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });

    expect(contributedRenderer).toHaveBeenCalledWith(0.5, {});
  });

  it('handles object-style renderer (static CSSProperties)', async () => {
    const staticStyle = { opacity: 0.3, filter: 'blur(2px)' };

    render(
      <TransitionRegistryProvider>
        <ProviderRecord transitionId="static-blur" renderer={staticStyle}>
          <VisualClip
            clip={mediaClip({
              transition: { type: 'static-blur', duration: 0.5 },
            })}
            track={track}
            fps={30}
          />
        </ProviderRecord>
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });

    // The AbsoluteFill should have the static style applied
    const fill = screen.getByTestId('absolute-fill');
    const style = JSON.parse(fill.getAttribute('data-style') ?? '{}');
    expect(style.opacity).toBe(0.3);
    expect(style.filter).toBe('blur(2px)');
  });

  // -- Missing / unrenderable transitions (no crossfade fallback!) -----------

  it('renders diagnostic placeholder for missing transition (no crossfade fallback)', async () => {
    render(
      <TransitionRegistryProvider>
        <VisualClip
          clip={mediaClip({ transition: { type: 'nonexistent-transition', duration: 0.5 } })}
          track={track}
          fps={30}
        />
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('missing-transition-placeholder')).toBeInTheDocument();
    });

    const placeholder = screen.getByTestId('missing-transition-placeholder');
    expect(placeholder).toHaveAttribute('data-clip-id', 'clip-1');
    expect(placeholder).toHaveAttribute('data-transition-type', 'nonexistent-transition');
    expect(placeholder.textContent).toContain("transition 'nonexistent-transition' not found");
  });

  it('does NOT fall back to crossfade for missing contributed transition', async () => {
    // This is the critical invariant: a missing transition must never
    // silently become crossfade. We ensure the diagnostic placeholder
    // is rendered instead.
    render(
      <TransitionRegistryProvider>
        <VisualClip
          clip={mediaClip({ transition: { type: 'removed-contrib-transition', duration: 0.5 } })}
          track={track}
          fps={30}
        />
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('missing-transition-placeholder')).toBeInTheDocument();
    });

    // No image asset should be rendered when transition is missing
    // (the placeholder replaces the entire clip output)
    expect(screen.queryByTestId('image-asset')).not.toBeInTheDocument();
  });

  it('renders clip normally when there is no transition at all', async () => {
    render(
      <TransitionRegistryProvider>
        <VisualClip
          clip={mediaClip({ transition: undefined })}
          track={track}
          fps={30}
        />
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });

    // No placeholder should be present (no transition is fine)
    expect(screen.queryByTestId('missing-transition-placeholder')).not.toBeInTheDocument();
  });

  // -- Built-in priority over contributed ------------------------------------

  it('prefers built-in transition over contributed with same ID', async () => {
    // Register a contributed renderer for 'crossfade' — it should be ignored
    // in favor of the built-in crossfade renderer.
    const contributedCrossfade = vi.fn(() => ({ opacity: 0.1 }));

    render(
      <TransitionRegistryProvider>
        <ProviderRecord transitionId="crossfade" renderer={contributedCrossfade}>
          <VisualClip
            clip={mediaClip({ transition: { type: 'crossfade', duration: 0.5 } })}
            track={track}
            fps={30}
          />
        </ProviderRecord>
      </TransitionRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });

    // The contributed renderer should NOT have been called (built-in takes priority)
    expect(contributedCrossfade).not.toHaveBeenCalled();
  });

  // -- No context fallback ---------------------------------------------------

  it('renders built-in transitions even without a TransitionRegistryProvider', async () => {
    // Without a provider, the optional context returns null, and
    // createTransitionSnapshot still includes built-in transitions.
    render(
      <VisualClip
        clip={mediaClip({ transition: { type: 'crossfade', duration: 0.5 } })}
        track={track}
        fps={30}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    });
  });

  it('renders diagnostic placeholder for unknown transition without provider', async () => {
    render(
      <VisualClip
        clip={mediaClip({ transition: { type: 'unknown-transition', duration: 0.5 } })}
        track={track}
        fps={30}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('missing-transition-placeholder')).toBeInTheDocument();
    });
  });
});
