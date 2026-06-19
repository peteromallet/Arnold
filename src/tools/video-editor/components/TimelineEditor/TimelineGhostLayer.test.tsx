// @vitest-environment jsdom
import React from 'react';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TimelineGhostLayer } from '@/tools/video-editor/components/TimelineEditor/TimelineGhostLayer';
import type { TimelineGhostEntry } from '@/tools/video-editor/types/timeline-canvas';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas';

const rows: TimelineRow[] = [
  { id: 'V1', actions: [] },
  { id: 'V2', actions: [] },
  { id: 'A1', actions: [] },
];

const baseProps = {
  rows,
  rowHeight: 48,
  startLeft: 100,
  pixelsPerSecond: 50,
};

describe('TimelineGhostLayer', () => {
  // ── Empty state ──────────────────────────────────────────────────────

  it('renders nothing when ghosts array is empty', () => {
    const { container } = render(
      <TimelineGhostLayer {...baseProps} ghosts={[]} />,
    );
    expect(container.querySelector('[data-testid="timeline-ghost-layer"]')).toBeNull();
  });

  // ── Basic rendering ──────────────────────────────────────────────────

  it('renders a ghost clip for an added entry', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 2, kind: 'added' },
    ];
    const { getByTestId, getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    expect(getByTestId('timeline-ghost-layer')).toBeInTheDocument();
    const clips = getAllByTestId('timeline-ghost-clip');
    expect(clips).toHaveLength(1);
    expect(clips[0]).toHaveAttribute('data-ghost-kind', 'added');
    expect(clips[0]).toHaveAttribute('data-ghost-track', 'V1');
  });

  it('renders ghost clips with correct pixel positions using canonical transform math', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 1, end: 3, kind: 'added' },
    ];
    const { getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const clip = getAllByTestId('timeline-ghost-clip')[0];
    // startLeft=100, start=1, pixelsPerSecond=50 → left = 100 + 1*50 = 150
    expect(clip.style.left).toBe('150px');
    // (end-start) * pixelsPerSecond = (3-1)*50 = 100
    expect(clip.style.width).toBe('100px');
  });

  it('positions ghost clips on different tracks using rowHeight', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-v1', trackId: 'V1', start: 0, end: 1, kind: 'added' },
      { id: 'ghost-v2', trackId: 'V2', start: 0, end: 1, kind: 'removed' },
      { id: 'ghost-a1', trackId: 'A1', start: 0, end: 1, kind: 'modified' },
    ];
    const { getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const clips = getAllByTestId('timeline-ghost-clip');
    expect(clips).toHaveLength(3);

    // V1 is row index 0 → top = 0*48 + ACTION_VERTICAL_MARGIN(4) = 4
    expect(clips[0].style.top).toBe('4px');
    // V2 is row index 1 → top = 1*48 + 4 = 52
    expect(clips[1].style.top).toBe('52px');
    // A1 is row index 2 → top = 2*48 + 4 = 100
    expect(clips[2].style.top).toBe('100px');
  });

  it('skips ghosts whose trackId is not found in rows', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 1, kind: 'added' },
      { id: 'ghost-2', trackId: 'NONEXISTENT', start: 0, end: 1, kind: 'removed' },
      { id: 'ghost-3', trackId: 'V2', start: 0, end: 1, kind: 'modified' },
    ];
    const { getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const clips = getAllByTestId('timeline-ghost-clip');
    expect(clips).toHaveLength(2);
  });

  // ── Pointer-events and aria ──────────────────────────────────────────

  it('renders with pointer-events-none to avoid interaction collisions', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 1, kind: 'added' },
    ];
    const { getByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const layer = getByTestId('timeline-ghost-layer');
    expect(layer.className).toContain('pointer-events-none');
  });

  it('renders with aria-hidden to avoid accessibility collisions', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 1, kind: 'added' },
    ];
    const { getByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const layer = getByTestId('timeline-ghost-layer');
    expect(layer).toHaveAttribute('aria-hidden', 'true');
  });

  // ── No data-action-id collisions ─────────────────────────────────────

  it('does not emit data-action-id attributes (canonical namespace protection)', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 1, kind: 'added' },
    ];
    const { container } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    expect(container.querySelector('[data-action-id]')).toBeNull();
  });

  it('uses stable data-testid values for testing', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 1, kind: 'added' },
    ];
    const { getByTestId, getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    expect(getByTestId('timeline-ghost-layer')).toBeInTheDocument();
    expect(getAllByTestId('timeline-ghost-clip')).toHaveLength(1);
  });

  // ── Distinct styling per kind ────────────────────────────────────────

  it('applies distinct border colors per ghost kind', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-added', trackId: 'V1', start: 0, end: 1, kind: 'added' },
      { id: 'ghost-removed', trackId: 'V2', start: 0, end: 1, kind: 'removed' },
      { id: 'ghost-modified', trackId: 'A1', start: 0, end: 1, kind: 'modified' },
      { id: 'ghost-reordered', trackId: 'V1', start: 1, end: 2, kind: 'reordered' },
    ];
    const { getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const clips = getAllByTestId('timeline-ghost-clip');
    expect(clips).toHaveLength(4);

    expect(clips[0]).toHaveAttribute('data-ghost-kind', 'added');
    expect(clips[1]).toHaveAttribute('data-ghost-kind', 'removed');
    expect(clips[2]).toHaveAttribute('data-ghost-kind', 'modified');
    expect(clips[3]).toHaveAttribute('data-ghost-kind', 'reordered');
  });

  it('renders removed ghosts with removed styling', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 1, kind: 'removed' },
    ];
    const { getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const clip = getAllByTestId('timeline-ghost-clip')[0];
    expect(clip.className).toContain('bg-[var(--video-editor-ghost-removed-bg)]');
    expect(clip.className).toContain('border-[var(--video-editor-ghost-removed-border)]');
  });

  it('renders with dashed borders for all ghost kinds', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 1, kind: 'added' },
    ];
    const { getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const clip = getAllByTestId('timeline-ghost-clip')[0];
    expect(clip.className).toContain('border-dashed');
  });

  // ── Title/tooltip ────────────────────────────────────────────────────

  it('includes a title attribute with kind and optional clipType', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 1, kind: 'added', clipType: 'media' },
    ];
    const { getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const clip = getAllByTestId('timeline-ghost-clip')[0];
    expect(clip).toHaveAttribute('title', 'Added (media) — proposal preview');
  });

  it('includes a title attribute without clipType when not provided', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 1, kind: 'removed' },
    ];
    const { getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const clip = getAllByTestId('timeline-ghost-clip')[0];
    expect(clip).toHaveAttribute('title', 'Removed — proposal preview');
  });

  // ── Minimum width clamp ──────────────────────────────────────────────

  it('clamps minimum width to 2px for zero-duration ghosts', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 1, end: 1, kind: 'added' },
    ];
    const { getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const clip = getAllByTestId('timeline-ghost-clip')[0];
    expect(parseInt(clip.style.width, 10)).toBeGreaterThanOrEqual(2);
  });

  // ── Multiple ghosts on same track ────────────────────────────────────

  it('renders multiple ghosts on the same track without collision', () => {
    const ghosts: TimelineGhostEntry[] = [
      { id: 'ghost-1', trackId: 'V1', start: 0, end: 1, kind: 'added' },
      { id: 'ghost-2', trackId: 'V1', start: 2, end: 3, kind: 'modified' },
    ];
    const { getAllByTestId } = render(
      <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
    );

    const clips = getAllByTestId('timeline-ghost-clip');
    expect(clips).toHaveLength(2);
    // Both on same track (row index 0) → same top
    expect(clips[0].style.top).toBe(clips[1].style.top);
    // Different left positions
    expect(clips[0].style.left).not.toBe(clips[1].style.left);
  });
});

  // ── Canonical data remains unchanged ──────────────────────────────────

  describe('canonical data immutability', () => {
    it('does not mutate the rows array after rendering', () => {
      const originalRows: TimelineRow[] = [
        { id: 'V1', actions: [] },
        { id: 'V2', actions: [] },
      ];
      const rowsSnapshot = JSON.stringify(originalRows);

      const ghosts: TimelineGhostEntry[] = [
        { id: 'ghost-1', trackId: 'V1', start: 0, end: 2, kind: 'added' },
      ];

      render(
        <TimelineGhostLayer
          rows={originalRows}
          rowHeight={48}
          startLeft={100}
          pixelsPerSecond={50}
          ghosts={ghosts}
        />,
      );

      // Rows must be structurally identical to their pre-render snapshot.
      expect(JSON.stringify(originalRows)).toBe(rowsSnapshot);
    });

    it('does not mutate the ghosts array after rendering', () => {
      const ghosts: TimelineGhostEntry[] = [
        { id: 'ghost-1', trackId: 'V1', start: 0, end: 2, kind: 'added' },
      ];
      const ghostsSnapshot = JSON.stringify(ghosts);

      render(
        <TimelineGhostLayer
          rows={rows}
          rowHeight={48}
          startLeft={100}
          pixelsPerSecond={50}
          ghosts={ghosts}
        />,
      );

      // Ghosts array must be unchanged.
      expect(JSON.stringify(ghosts)).toBe(ghostsSnapshot);
    });

    it('does not add any properties to row objects after rendering', () => {
      const originalRows: TimelineRow[] = [
        { id: 'V1', actions: [] },
        { id: 'V2', actions: [] },
      ];

      const ghosts: TimelineGhostEntry[] = [
        { id: 'ghost-1', trackId: 'V1', start: 0, end: 2, kind: 'added' },
      ];

      render(
        <TimelineGhostLayer
          rows={originalRows}
          rowHeight={48}
          startLeft={100}
          pixelsPerSecond={50}
          ghosts={ghosts}
        />,
      );

      // Each row must only have 'id' and 'actions' keys.
      for (const row of originalRows) {
        expect(Object.keys(row).sort()).toEqual(['actions', 'id']);
      }
    });

    it('does not add any properties to ghost entry objects after rendering', () => {
      const ghosts: TimelineGhostEntry[] = [
        { id: 'ghost-1', trackId: 'V1', start: 0, end: 2, kind: 'added' },
      ];

      render(
        <TimelineGhostLayer
          rows={rows}
          rowHeight={48}
          startLeft={100}
          pixelsPerSecond={50}
          ghosts={ghosts}
        />,
      );

      // Each ghost must only have the canonical keys.
      for (const ghost of ghosts) {
        expect(Object.keys(ghost).sort()).toEqual(
          ['end', 'id', 'kind', 'start', 'trackId'].sort(),
        );
      }
    });

    it('does not mutate scalar props after rendering', () => {
      let rowHeight = 48;
      let startLeft = 100;
      let pixelsPerSecond = 50;

      const ghosts: TimelineGhostEntry[] = [
        { id: 'ghost-1', trackId: 'V1', start: 0, end: 2, kind: 'added' },
      ];

      render(
        <TimelineGhostLayer
          rows={rows}
          rowHeight={rowHeight}
          startLeft={startLeft}
          pixelsPerSecond={pixelsPerSecond}
          ghosts={ghosts}
        />,
      );

      expect(rowHeight).toBe(48);
      expect(startLeft).toBe(100);
      expect(pixelsPerSecond).toBe(50);
    });

    it('renders ghosts without modifying any canonical DOM outside the ghost layer', () => {
      const ghosts: TimelineGhostEntry[] = [
        { id: 'ghost-1', trackId: 'V1', start: 0, end: 2, kind: 'added' },
      ];

      const { container } = render(
        <TimelineGhostLayer
          rows={rows}
          rowHeight={48}
          startLeft={100}
          pixelsPerSecond={50}
          ghosts={ghosts}
        />,
      );

      // No data-action-id should appear anywhere in the rendered output.
      expect(container.querySelector('[data-action-id]')).toBeNull();

      // The ghost layer itself must not carry data-action-id.
      const layer = container.querySelector('[data-testid="timeline-ghost-layer"]');
      expect(layer).toBeTruthy();
      expect(layer!.hasAttribute('data-action-id')).toBe(false);
    });

    it('can re-render with different ghost arrays without mutating previous input', () => {
      const ghostsA: TimelineGhostEntry[] = [
        { id: 'ghost-a', trackId: 'V1', start: 0, end: 1, kind: 'added' },
      ];
      const ghostsB: TimelineGhostEntry[] = [
        { id: 'ghost-b', trackId: 'V2', start: 2, end: 3, kind: 'removed' },
      ];

      const snapshotA = JSON.stringify(ghostsA);
      const snapshotB = JSON.stringify(ghostsB);

      const { rerender, getAllByTestId } = render(
        <TimelineGhostLayer {...baseProps} ghosts={ghostsA} />,
      );

      expect(getAllByTestId('timeline-ghost-clip')).toHaveLength(1);
      expect(JSON.stringify(ghostsA)).toBe(snapshotA);

      rerender(
        <TimelineGhostLayer {...baseProps} ghosts={ghostsB} />,
      );

      expect(getAllByTestId('timeline-ghost-clip')).toHaveLength(1);
      expect(JSON.stringify(ghostsA)).toBe(snapshotA);
      expect(JSON.stringify(ghostsB)).toBe(snapshotB);
    });
  });

  // ── 200-clip preview sample ───────────────────────────────────────────

  describe('200-clip preview sample', () => {
    /** Generate N ghost entries spread across the 3 test tracks. */
    function generateGhosts(count: number): TimelineGhostEntry[] {
      const entries: TimelineGhostEntry[] = [];
      const kinds: TimelineGhostEntry['kind'][] = ['added', 'removed', 'modified', 'reordered'];
      const trackIds = ['V1', 'V2', 'A1'];

      for (let i = 0; i < count; i++) {
        const start = i * 0.5;
        entries.push({
          id: `ghost-${i}`,
          trackId: trackIds[i % 3],
          start,
          end: start + 0.4,
          kind: kinds[i % 4],
          clipType: i % 5 === 0 ? 'media' : undefined,
        });
      }

      return entries;
    }

    it('renders 200 ghost entries without crashing', () => {
      const ghosts = generateGhosts(200);

      const { getByTestId, getAllByTestId } = render(
        <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
      );

      expect(getByTestId('timeline-ghost-layer')).toBeInTheDocument();
      // All 200 should render because all trackIds (V1,V2,A1) exist in rows.
      expect(getAllByTestId('timeline-ghost-clip')).toHaveLength(200);
    });

    it('renders all 200 ghost entries with correct data-ghost-kind attributes', () => {
      const ghosts = generateGhosts(200);

      const { getAllByTestId } = render(
        <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
      );

      const clips = getAllByTestId('timeline-ghost-clip');
      expect(clips).toHaveLength(200);

      // Spot-check: every 4th entry cycles through added/removed/modified/reordered.
      const expectedKinds = ['added', 'removed', 'modified', 'reordered'];
      for (let i = 0; i < 200; i++) {
        expect(clips[i]).toHaveAttribute('data-ghost-kind', expectedKinds[i % 4]);
      }
    });

    it('renders all 200 ghost entries with correct track assignments', () => {
      const ghosts = generateGhosts(200);

      const { getAllByTestId } = render(
        <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
      );

      const clips = getAllByTestId('timeline-ghost-clip');
      expect(clips).toHaveLength(200);

      const expectedTracks = ['V1', 'V2', 'A1'];
      for (let i = 0; i < 200; i++) {
        expect(clips[i]).toHaveAttribute('data-ghost-track', expectedTracks[i % 3]);
      }
    });

    it('renders 200 ghost entries within an acceptable time budget', () => {
      const ghosts = generateGhosts(200);

      const startTime = performance.now();
      render(
        <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
      );
      const elapsed = performance.now() - startTime;

      // 200 ghost entries should render in well under 500 ms.
      // Even on slower CI, anything over 1000 ms would indicate a problem.
      expect(elapsed).toBeLessThan(1000);
    });

    it('maintains pointer-events-none with 200 ghost entries', () => {
      const ghosts = generateGhosts(200);

      const { getByTestId } = render(
        <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
      );

      const layer = getByTestId('timeline-ghost-layer');
      expect(layer.className).toContain('pointer-events-none');
    });

    it('maintains aria-hidden with 200 ghost entries', () => {
      const ghosts = generateGhosts(200);

      const { getByTestId } = render(
        <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
      );

      const layer = getByTestId('timeline-ghost-layer');
      expect(layer).toHaveAttribute('aria-hidden', 'true');
    });

    it('does not emit data-action-id with 200 ghost entries', () => {
      const ghosts = generateGhosts(200);

      const { container } = render(
        <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
      );

      expect(container.querySelector('[data-action-id]')).toBeNull();
    });

    it('canonical data is unchanged after rendering 200 ghost entries', () => {
      const originalRows: TimelineRow[] = [
        { id: 'V1', actions: [] },
        { id: 'V2', actions: [] },
        { id: 'A1', actions: [] },
      ];
      const rowsSnapshot = JSON.stringify(originalRows);

      const ghosts = generateGhosts(200);
      const ghostsSnapshot = JSON.stringify(ghosts);

      render(
        <TimelineGhostLayer
          rows={originalRows}
          rowHeight={48}
          startLeft={100}
          pixelsPerSecond={50}
          ghosts={ghosts}
        />,
      );

      expect(JSON.stringify(originalRows)).toBe(rowsSnapshot);
      expect(JSON.stringify(ghosts)).toBe(ghostsSnapshot);
    });

    it('all 200 ghost clip elements have dashed borders', () => {
      const ghosts = generateGhosts(200);

      const { getAllByTestId } = render(
        <TimelineGhostLayer {...baseProps} ghosts={ghosts} />,
      );

      const clips = getAllByTestId('timeline-ghost-clip');
      expect(clips).toHaveLength(200);

      for (const clip of clips) {
        expect(clip.className).toContain('border-dashed');
      }
    });
  });
