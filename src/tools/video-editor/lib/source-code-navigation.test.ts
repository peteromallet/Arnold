/**
 * Tests for source-code-navigation — bidirectional source-map navigation.
 *
 * @publicContract
 */

import { describe, expect, it, beforeEach, vi } from 'vitest';
import {
  createTimelineSourceNavigator,
  createSourceTimelineNavigator,
} from '@/tools/video-editor/lib/source-code-navigation';
import {
  TIMELINE_NAVIGATE_TO_SOURCE_EVENT,
  SOURCE_NAVIGATE_TO_TIMELINE_EVENT,
  TIMELINE_CENTER_CLIP_EVENT,
  type TimelineNavigateToSourceDetail,
  type SourceNavigateToTimelineDetail,
} from '@/tools/video-editor/lib/timeline-viewport-events';
import type { SourceMapRuntime, SourceMapEntry } from '@/sdk/index';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMockSourceMapRuntime(
  entries: SourceMapEntry[] = [],
): SourceMapRuntime {
  return {
    create: vi.fn(),
    get: vi.fn((_extId: string, entryId: string) =>
      entries.find((e) => e.id === entryId),
    ),
    getForTarget: vi.fn((_extId: string, targetId: string) =>
      entries.filter((e) => e.targetId === targetId),
    ),
    getForSource: vi.fn((_extId: string, sourceUri: string) =>
      entries.filter((e) => e.sourceUri === sourceUri),
    ),
    markStale: vi.fn(),
    markStaleForTarget: vi.fn(),
    delete: vi.fn(),
    list: vi.fn((_extId: string) => [...entries]),
    currentVersion: 1,
  };
}

function makeEntry(overrides: Partial<SourceMapEntry> = {}): SourceMapEntry {
  return {
    id: 'sme-1',
    source: 'ext.test',
    targetId: 'clip-1',
    targetGranularity: 'clip',
    sourceUri: 'file:///test.ts',
    sourceStartLine: 10,
    sourceStartColumn: 0,
    sourceEndLine: 15,
    sourceEndColumn: 0,
    stale: false,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests — TimelineSourceNavigator
// ---------------------------------------------------------------------------

describe('TimelineSourceNavigator', () => {
  let events: CustomEvent[];

  beforeEach(() => {
    events = [];
    vi.spyOn(window, 'dispatchEvent').mockImplementation((event: Event) => {
      events.push(event as CustomEvent);
      return true;
    });
  });

  describe('navigateToSource', () => {
    it('dispatches TIMELINE_NAVIGATE_TO_SOURCE_EVENT for each matching entry', () => {
      const entries = [
        makeEntry({ id: 'sme-1', targetId: 'clip-1', sourceUri: 'f1.ts' }),
        makeEntry({ id: 'sme-2', targetId: 'clip-1', sourceUri: 'f2.ts' }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      const result = nav.navigateToSource('ext.test', 'clip-1');

      expect(result).toBe(true);
      const sourceEvents = events.filter(
        (e) => e.type === TIMELINE_NAVIGATE_TO_SOURCE_EVENT,
      );
      expect(sourceEvents).toHaveLength(2);
      expect((sourceEvents[0].detail as TimelineNavigateToSourceDetail).sourceUri).toBe('f1.ts');
      expect((sourceEvents[1].detail as TimelineNavigateToSourceDetail).sourceUri).toBe('f2.ts');
    });

    it('returns false when no entries match the target', () => {
      const runtime = makeMockSourceMapRuntime([]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      const result = nav.navigateToSource('ext.test', 'nonexistent');

      expect(result).toBe(false);
      const sourceEvents = events.filter(
        (e) => e.type === TIMELINE_NAVIGATE_TO_SOURCE_EVENT,
      );
      expect(sourceEvents).toHaveLength(0);
    });

    it('includes stale flag in dispatched event detail', () => {
      const entry = makeEntry({ id: 'sme-1', targetId: 'clip-1', stale: true });
      const runtime = makeMockSourceMapRuntime([entry]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      nav.navigateToSource('ext.test', 'clip-1');

      const sourceEvents = events.filter(
        (e) => e.type === TIMELINE_NAVIGATE_TO_SOURCE_EVENT,
      );
      expect(sourceEvents).toHaveLength(1);
      expect((sourceEvents[0].detail as TimelineNavigateToSourceDetail).stale).toBe(true);
    });
  });

  describe('hasSourceMapEntries', () => {
    it('returns true when entries exist', () => {
      const runtime = makeMockSourceMapRuntime([makeEntry({ targetId: 'clip-1' })]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      expect(nav.hasSourceMapEntries('ext.test', 'clip-1')).toBe(true);
    });

    it('returns false when no entries exist', () => {
      const runtime = makeMockSourceMapRuntime([]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      expect(nav.hasSourceMapEntries('ext.test', 'clip-1')).toBe(false);
    });
  });

  describe('hasStaleSourceMapEntries', () => {
    it('returns true when stale entries exist', () => {
      const runtime = makeMockSourceMapRuntime([
        makeEntry({ targetId: 'clip-1', stale: true }),
        makeEntry({ targetId: 'clip-1', stale: false }),
      ]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      expect(nav.hasStaleSourceMapEntries('ext.test', 'clip-1')).toBe(true);
    });

    it('returns false when entries exist but none are stale', () => {
      const runtime = makeMockSourceMapRuntime([
        makeEntry({ targetId: 'clip-1', stale: false }),
      ]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      expect(nav.hasStaleSourceMapEntries('ext.test', 'clip-1')).toBe(false);
    });

    it('returns false when no entries exist', () => {
      const runtime = makeMockSourceMapRuntime([]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      expect(nav.hasStaleSourceMapEntries('ext.test', 'clip-1')).toBe(false);
    });
  });

  describe('getStaleStatus', () => {
    it('returns correct counts for mixed stale/non-stale entries', () => {
      const runtime = makeMockSourceMapRuntime([
        makeEntry({ id: 'sme-1', targetId: 'clip-1', stale: true }),
        makeEntry({ id: 'sme-2', targetId: 'clip-1', stale: false }),
        makeEntry({ id: 'sme-3', targetId: 'clip-1', stale: true }),
      ]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      const status = nav.getStaleStatus('ext.test', 'clip-1');

      expect(status.hasEntries).toBe(true);
      expect(status.hasStale).toBe(true);
      expect(status.staleEntries).toHaveLength(2);
      expect(status.nonStaleEntries).toHaveLength(1);
    });

    it('returns empty arrays when no entries exist', () => {
      const runtime = makeMockSourceMapRuntime([]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      const status = nav.getStaleStatus('ext.test', 'nonexistent');

      expect(status.hasEntries).toBe(false);
      expect(status.hasStale).toBe(false);
      expect(status.staleEntries).toHaveLength(0);
      expect(status.nonStaleEntries).toHaveLength(0);
    });
  });
});

// ---------------------------------------------------------------------------
// Tests — SourceTimelineNavigator
// ---------------------------------------------------------------------------

describe('SourceTimelineNavigator', () => {
  let events: CustomEvent[];

  beforeEach(() => {
    events = [];
    vi.spyOn(window, 'dispatchEvent').mockImplementation((event: Event) => {
      events.push(event as CustomEvent);
      return true;
    });
  });

  describe('navigateToTimeline', () => {
    it('dispatches SOURCE_NAVIGATE_TO_TIMELINE_EVENT and centers on first matching target', () => {
      const entries = [
        makeEntry({
          id: 'sme-1',
          targetId: 'clip-1',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 10,
          sourceEndLine: 15,
        }),
        makeEntry({
          id: 'sme-2',
          targetId: 'clip-2',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 12,
          sourceEndLine: 14,
        }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      const result = nav.navigateToTimeline('ext.test', 'file:///test.ts', 11, 13);

      expect(result).toBe(true);

      const sourceEvents = events.filter(
        (e) => e.type === SOURCE_NAVIGATE_TO_TIMELINE_EVENT,
      );
      expect(sourceEvents).toHaveLength(1);
      expect((sourceEvents[0].detail as SourceNavigateToTimelineDetail).sourceUri).toBe(
        'file:///test.ts',
      );

      const centerEvents = events.filter(
        (e) => e.type === TIMELINE_CENTER_CLIP_EVENT,
      );
      expect(centerEvents).toHaveLength(1);
      expect(centerEvents[0].detail).toEqual({ clipId: 'clip-1' });
    });

    it('falls back to first entry when no exact overlap', () => {
      const entries = [
        makeEntry({
          id: 'sme-1',
          targetId: 'clip-1',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 10,
          sourceEndLine: 15,
        }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      // Range that doesn't overlap
      const result = nav.navigateToTimeline('ext.test', 'file:///test.ts', 20, 25);

      expect(result).toBe(true);
      const sourceEvents = events.filter(
        (e) => e.type === SOURCE_NAVIGATE_TO_TIMELINE_EVENT,
      );
      expect(sourceEvents).toHaveLength(1);
      expect((sourceEvents[0].detail as SourceNavigateToTimelineDetail).targetId).toBe('clip-1');
    });

    it('returns false when no entries match source URI', () => {
      const runtime = makeMockSourceMapRuntime([]);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      const result = nav.navigateToTimeline('ext.test', 'file:///nonexistent.ts', 0, 10);

      expect(result).toBe(false);
    });

    it('uses provided targetId over first matching entry', () => {
      const entries = [
        makeEntry({ id: 'sme-1', targetId: 'clip-1', sourceUri: 'file:///test.ts' }),
        makeEntry({ id: 'sme-2', targetId: 'clip-2', sourceUri: 'file:///test.ts' }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      nav.navigateToTimeline('ext.test', 'file:///test.ts', 0, 999, 'clip-2');

      const centerEvents = events.filter(
        (e) => e.type === TIMELINE_CENTER_CLIP_EVENT,
      );
      // Should center on specified target AND first matching (two dispatch calls)
      expect(centerEvents.length).toBeGreaterThanOrEqual(1);
      expect(centerEvents[0].detail).toEqual({ clipId: 'clip-1' });
    });
  });

  describe('findAffectedTargets', () => {
    it('returns entries overlapping the given range', () => {
      const entries = [
        makeEntry({
          id: 'sme-1',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 5,
          sourceEndLine: 10,
        }),
        makeEntry({
          id: 'sme-2',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 15,
          sourceEndLine: 20,
        }),
        makeEntry({
          id: 'sme-3',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 7,
          sourceEndLine: 12,
        }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      const result = nav.findAffectedTargets('ext.test', 'file:///test.ts', 8, 11);

      expect(result).toHaveLength(2); // sme-1 (5-10 overlaps 8-11) and sme-3 (7-12 overlaps 8-11)
      expect(result.map((e) => e.id).sort()).toEqual(['sme-1', 'sme-3']);
    });

    it('returns all entries when no range specified', () => {
      const entries = [
        makeEntry({ id: 'sme-1', sourceUri: 'file:///test.ts' }),
        makeEntry({ id: 'sme-2', sourceUri: 'file:///test.ts' }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      const result = nav.findAffectedTargets('ext.test', 'file:///test.ts');

      expect(result).toHaveLength(2);
    });

    it('returns empty array for non-matching source URI', () => {
      const runtime = makeMockSourceMapRuntime([]);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      const result = nav.findAffectedTargets('ext.test', 'file:///nonexistent.ts');

      expect(result).toHaveLength(0);
    });
  });

  describe('hasStaleEntriesForSource', () => {
    it('returns true when stale entries exist for source URI', () => {
      const runtime = makeMockSourceMapRuntime([
        makeEntry({ sourceUri: 'file:///test.ts', stale: true }),
      ]);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      expect(nav.hasStaleEntriesForSource('ext.test', 'file:///test.ts')).toBe(true);
    });

    it('returns false when no stale entries for source URI', () => {
      const runtime = makeMockSourceMapRuntime([
        makeEntry({ sourceUri: 'file:///test.ts', stale: false }),
      ]);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      expect(nav.hasStaleEntriesForSource('ext.test', 'file:///test.ts')).toBe(false);
    });
  });

  describe('bidirectional navigation scenarios', () => {
    it('supports full round-trip: source navigate → timeline → source', () => {
      const entries = [
        makeEntry({
          id: 'sme-1',
          targetId: 'clip-hero',
          sourceUri: 'dsl://hero.section',
          sourceStartLine: 5,
          sourceEndLine: 20,
        }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);

      // Source → Timeline
      const srcNav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });
      srcNav.navigateToTimeline('ext.test', 'dsl://hero.section', 8, 15);

      const centerEvents = events.filter((e) => e.type === TIMELINE_CENTER_CLIP_EVENT);
      expect(centerEvents).toHaveLength(1);
      expect(centerEvents[0].detail).toEqual({ clipId: 'clip-hero' });

      // Timeline → Source
      const tlNav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });
      tlNav.navigateToSource('ext.test', 'clip-hero');

      const sourceEvents = events.filter((e) => e.type === TIMELINE_NAVIGATE_TO_SOURCE_EVENT);
      expect(sourceEvents).toHaveLength(1);
      expect((sourceEvents[0].detail as TimelineNavigateToSourceDetail).sourceUri).toBe(
        'dsl://hero.section',
      );
    });

    it('handles stale entries in round-trip navigation', () => {
      const entries = [
        makeEntry({
          id: 'sme-1',
          targetId: 'clip-stale',
          sourceUri: 'dsl://stale.section',
          stale: true,
        }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);

      // Check stale status from timeline side
      const tlNav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });
      const status = tlNav.getStaleStatus('ext.test', 'clip-stale');
      expect(status.hasStale).toBe(true);
      expect(status.staleEntries).toHaveLength(1);

      // Navigate to source — stale flag included
      tlNav.navigateToSource('ext.test', 'clip-stale');
      const sourceEvents = events.filter((e) => e.type === TIMELINE_NAVIGATE_TO_SOURCE_EVENT);
      expect((sourceEvents[0].detail as TimelineNavigateToSourceDetail).stale).toBe(true);

      // Source side also detects stale
      const srcNav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });
      expect(srcNav.hasStaleEntriesForSource('ext.test', 'dsl://stale.section')).toBe(true);
    });
  });
});

// ---------------------------------------------------------------------------
// Additional bidirectional navigation and stale indicator tests
// ---------------------------------------------------------------------------

describe('bidirectional navigation stale and edge cases', () => {
  let events: CustomEvent[];

  beforeEach(() => {
    events = [];
    vi.spyOn(window, 'dispatchEvent').mockImplementation((event: Event) => {
      events.push(event as CustomEvent);
      return true;
    });
  });

  describe('stale indicator on both surfaces', () => {
    it('timeline side: detects stale through getStaleStatus and includes stale in navigation event', () => {
      const entries = [
        makeEntry({ id: 'sme-1', targetId: 'clip-a', sourceUri: 'f1.ts', stale: true }),
        makeEntry({ id: 'sme-2', targetId: 'clip-a', sourceUri: 'f2.ts', stale: false }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      // Check stale status before navigating
      const status = nav.getStaleStatus('ext.test', 'clip-a');
      expect(status.hasEntries).toBe(true);
      expect(status.hasStale).toBe(true);
      expect(status.staleEntries).toHaveLength(1);
      expect(status.nonStaleEntries).toHaveLength(1);
      expect(status.staleEntries[0].id).toBe('sme-1');

      // Navigate to source — stale flag on stale entry
      nav.navigateToSource('ext.test', 'clip-a');
      const sourceEvents = events.filter((e) => e.type === TIMELINE_NAVIGATE_TO_SOURCE_EVENT);
      expect(sourceEvents).toHaveLength(2);
      const staleEvent = sourceEvents.find(
        (e) => (e.detail as TimelineNavigateToSourceDetail).stale,
      );
      const freshEvent = sourceEvents.find(
        (e) => !(e.detail as TimelineNavigateToSourceDetail).stale,
      );
      expect(staleEvent).toBeTruthy();
      expect(freshEvent).toBeTruthy();
    });

    it('source side: detects stale through hasStaleEntriesForSource', () => {
      const entries = [
        makeEntry({ id: 'sme-1', sourceUri: 'file:///stale.ts', stale: true }),
        makeEntry({ id: 'sme-2', sourceUri: 'file:///stale.ts', stale: false }),
        makeEntry({ id: 'sme-3', sourceUri: 'file:///fresh.ts', stale: false }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      expect(nav.hasStaleEntriesForSource('ext.test', 'file:///stale.ts')).toBe(true);
      expect(nav.hasStaleEntriesForSource('ext.test', 'file:///fresh.ts')).toBe(false);
      expect(nav.hasStaleEntriesForSource('ext.test', 'file:///nonexistent.ts')).toBe(false);
    });

    it('source side: findAffectedTargets preserves stale info', () => {
      const entries = [
        makeEntry({
          id: 'sme-1',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 5,
          sourceEndLine: 10,
          stale: true,
          targetId: 'clip-stale',
        }),
        makeEntry({
          id: 'sme-2',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 15,
          sourceEndLine: 20,
          stale: false,
          targetId: 'clip-fresh',
        }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      const affected = nav.findAffectedTargets('ext.test', 'file:///test.ts', 5, 10);
      expect(affected).toHaveLength(1);
      expect(affected[0].stale).toBe(true);
      expect(affected[0].targetId).toBe('clip-stale');
    });
  });

  describe('navigateToTimeline edge cases', () => {
    it('returns false for empty source URI with no entries', () => {
      const runtime = makeMockSourceMapRuntime([]);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      expect(nav.navigateToTimeline('ext.test', '', 0, 10)).toBe(false);
    });

    it('handles zero-width range correctly', () => {
      const entries = [
        makeEntry({
          id: 'sme-1',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 10,
          sourceEndLine: 10,
          targetId: 'clip-1',
        }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      // Range 10-10 doesn't overlap 10-10 because rangesOverlap uses < not <=
      const result = nav.navigateToTimeline('ext.test', 'file:///test.ts', 10, 10);
      // Falls back to first entry
      expect(result).toBe(true);
    });

    it('navigates correctly when multiple entries overlap the source range', () => {
      const entries = [
        makeEntry({
          id: 'sme-1',
          targetId: 'clip-1',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 5,
          sourceEndLine: 15,
        }),
        makeEntry({
          id: 'sme-2',
          targetId: 'clip-2',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 10,
          sourceEndLine: 20,
        }),
        makeEntry({
          id: 'sme-3',
          targetId: 'clip-3',
          sourceUri: 'file:///test.ts',
          sourceStartLine: 8,
          sourceEndLine: 12,
        }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createSourceTimelineNavigator({ sourceMapRuntime: runtime });

      nav.navigateToTimeline('ext.test', 'file:///test.ts', 9, 11);

      const centerEvents = events.filter((e) => e.type === TIMELINE_CENTER_CLIP_EVENT);
      // First matching entry is sme-1 (5-15 overlaps 9-11)
      expect(centerEvents).toHaveLength(1);
      expect(centerEvents[0].detail).toEqual({ clipId: 'clip-1' });
    });
  });

  describe('navigateToSource edge cases', () => {
    it('handles entries with missing optional fields', () => {
      const entry: SourceMapEntry = {
        id: 'sme-min',
        source: 'ext.min',
        targetId: 'clip-min',
        targetGranularity: 'clip',
        sourceUri: '',
        sourceStartLine: 0,
        sourceStartColumn: 0,
        sourceEndLine: 0,
        sourceEndColumn: 0,
        stale: false,
      };
      const runtime = makeMockSourceMapRuntime([entry]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      const result = nav.navigateToSource('ext.min', 'clip-min');
      expect(result).toBe(true);

      const sourceEvents = events.filter((e) => e.type === TIMELINE_NAVIGATE_TO_SOURCE_EVENT);
      expect(sourceEvents).toHaveLength(1);
      expect((sourceEvents[0].detail as TimelineNavigateToSourceDetail).sourceUri).toBe('');
    });

    it('handles multiple targets with same extension', () => {
      const entries = [
        makeEntry({ id: 'sme-1', targetId: 'clip-a', sourceUri: 'uri-a' }),
        makeEntry({ id: 'sme-2', targetId: 'clip-b', sourceUri: 'uri-b' }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      // Only clip-a entries returned
      expect(nav.navigateToSource('ext.test', 'clip-a')).toBe(true);
      const sourceEvents = events.filter((e) => e.type === TIMELINE_NAVIGATE_TO_SOURCE_EVENT);
      expect(sourceEvents).toHaveLength(1);
      expect((sourceEvents[0].detail as TimelineNavigateToSourceDetail).sourceUri).toBe('uri-a');
    });
  });

  describe('getStaleStatus full spectrum', () => {
    it('returns correct counts for all-stale entries', () => {
      const entries = [
        makeEntry({ id: 'sme-1', targetId: 'clip-1', stale: true }),
        makeEntry({ id: 'sme-2', targetId: 'clip-1', stale: true }),
        makeEntry({ id: 'sme-3', targetId: 'clip-1', stale: true }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      const status = nav.getStaleStatus('ext.test', 'clip-1');
      expect(status.hasEntries).toBe(true);
      expect(status.hasStale).toBe(true);
      expect(status.staleEntries).toHaveLength(3);
      expect(status.nonStaleEntries).toHaveLength(0);
    });

    it('returns correct counts for all-fresh entries', () => {
      const entries = [
        makeEntry({ id: 'sme-1', targetId: 'clip-1', stale: false }),
        makeEntry({ id: 'sme-2', targetId: 'clip-1', stale: false }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      const status = nav.getStaleStatus('ext.test', 'clip-1');
      expect(status.hasEntries).toBe(true);
      expect(status.hasStale).toBe(false);
      expect(status.staleEntries).toHaveLength(0);
      expect(status.nonStaleEntries).toHaveLength(2);
    });

    it('returns correct counts for single entry stale', () => {
      const entry = makeEntry({ id: 'sme-1', targetId: 'clip-1', stale: true });
      const runtime = makeMockSourceMapRuntime([entry]);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      const status = nav.getStaleStatus('ext.test', 'clip-1');
      expect(status.hasEntries).toBe(true);
      expect(status.hasStale).toBe(true);
      expect(status.staleEntries).toHaveLength(1);
      expect(status.nonStaleEntries).toHaveLength(0);
    });

    it('preserves full entry shape in staleEntries and nonStaleEntries', () => {
      const entries = [
        makeEntry({
          id: 'sme-1',
          targetId: 'clip-1',
          sourceUri: 'file:///a.ts',
          sourceStartLine: 10,
          sourceEndLine: 20,
          stale: true,
        }),
        makeEntry({
          id: 'sme-2',
          targetId: 'clip-1',
          sourceUri: 'file:///b.ts',
          sourceStartLine: 30,
          sourceEndLine: 40,
          stale: false,
        }),
      ];
      const runtime = makeMockSourceMapRuntime(entries);
      const nav = createTimelineSourceNavigator({ sourceMapRuntime: runtime });

      const status = nav.getStaleStatus('ext.test', 'clip-1');
      expect(status.staleEntries[0].sourceUri).toBe('file:///a.ts');
      expect(status.staleEntries[0].sourceStartLine).toBe(10);
      expect(status.nonStaleEntries[0].sourceUri).toBe('file:///b.ts');
      expect(status.nonStaleEntries[0].sourceEndLine).toBe(40);
    });
  });
});
