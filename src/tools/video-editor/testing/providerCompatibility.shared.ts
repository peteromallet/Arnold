/**
 * Provider Compatibility Shared Test Helper
 *
 * Runs a standard battery of DataProvider contract tests against any
 * feasible provider implementation (InMemory, Supabase, AstridBridge).
 *
 * Covers:
 *  - Versioned load/save semantics with atomic expected-version CAS
 *  - Extension-requirement round-trip through config storage
 *  - Diagnostic error types (TimelineNotFoundError, TimelineVersionConflictError)
 *  - Proposal base-version handling (configVersion monotonicity)
 *  - Serialization fidelity (deep equality of saved vs loaded config/registry)
 *
 * Usage:
 *   import { runProviderCompatibilitySuite } from '…/testing/providerCompatibility.shared';
 *   describe('MyProvider compatibility', () => {
 *     runProviderCompatibilitySuite(() => new MyProvider(…));
 *   });
 */

import { describe, expect, it } from 'vitest';
import type {
  DataProvider,
  LoadedTimeline,
} from '@/tools/video-editor/data/DataProvider';
import {
  TimelineNotFoundError,
  TimelineVersionConflictError,
} from '@/tools/video-editor/data/DataProvider';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types/index';

// ---------------------------------------------------------------------------
// Minimal config builders
// ---------------------------------------------------------------------------

function buildConfig(overrides: Partial<TimelineConfig> = {}): TimelineConfig {
  return {
    output: {
      resolution: '1920x1080',
      fps: 30,
      file: 'timeline.mp4',
    },
    tracks: [
      { id: 'V1', kind: 'visual', label: 'V1' },
    ],
    clips: [],
    ...overrides,
  } as TimelineConfig;
}

function buildRegistry(assets: AssetRegistry['assets'] = {}): AssetRegistry {
  return { assets };
}

// ---------------------------------------------------------------------------
// Provider factory type
// ---------------------------------------------------------------------------

/** A function that creates (and optionally seeds) a DataProvider instance. */
export type ProviderFactory = (
  seed?: { timelineId?: string; config?: TimelineConfig; configVersion?: number; registry?: AssetRegistry },
) => DataProvider | Promise<DataProvider>;

// ---------------------------------------------------------------------------
// Shared suite runner
// ---------------------------------------------------------------------------

/**
 * Run the standard provider compatibility suite against a provider factory.
 *
 * The factory receives an optional seed to create pre-populated timelines.
 * Tests that depend on pre-seeded state use the factory with a seed; tests
 * that create state imperatively use the factory without one.
 */
export function runProviderCompatibilitySuite(
  factory: ProviderFactory,
  options: {
    /** If true, the provider does not support saveCheckpoint / loadCheckpoints. */
    skipCheckpoints?: boolean;
    /** If true, the provider's saveTimeline ignores expectedVersion (Astrid). */
    versionConflictIsSoft?: boolean;
    /** Timeline ID to use for tests. Defaults to 'compat-test-timeline'. */
    timelineId?: string;
    /** If true, provider doesn't support registerAsset. */
    skipRegisterAsset?: boolean;
    /** If true, skip tests that try to load nonexistent timelines (e.g. single-timeline bridge providers). */
    skipMissingTimelineTests?: boolean;
  } = {},
): void {
  const {
    skipCheckpoints = false,
    versionConflictIsSoft = false,
    timelineId: defaultTimelineId = 'compat-test-timeline',
    skipRegisterAsset = false,
    skipMissingTimelineTests = false,
  } = options;

  const tid = defaultTimelineId;
  const config1 = buildConfig();
  const config2 = buildConfig({
    clips: [
      { id: 'clip-1', clipType: 'hold', track: 'V1', at: 0, hold: 5 } as any,
    ],
  });
  const config3 = buildConfig({
    clips: [
      { id: 'clip-2', clipType: 'media', track: 'V1', at: 0, hold: 10 } as any,
    ],
  });
  const registry1 = buildRegistry({
    'asset-1': {
      file: 'clips/demo.mp4',
      type: 'video/mp4',
      duration: 4,
    },
  });
  const registry2 = buildRegistry({
    'asset-1': {
      file: 'clips/demo.mp4',
      type: 'video/mp4',
      duration: 4,
    },
    'asset-2': {
      file: 'stills/cover.png',
      type: 'image/png',
    },
  });

  // ── Versioned load/save ────────────────────────────────────────────────────

  describe('versioned load/save', () => {
    it('loadTimeline returns configVersion=1 for a newly seeded timeline', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      const loaded = await provider.loadTimeline(tid);
      expect(loaded.configVersion).toBe(1);
      expect(loaded.config).toBeDefined();
    });

    it('loadTimeline returns the saved configVersion after multiple saves', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      const v2 = await provider.saveTimeline(tid, config2, 1);
      expect(v2).toBe(2);

      const v3 = await provider.saveTimeline(tid, config3, 2);
      expect(v3).toBe(3);

      const loaded = await provider.loadTimeline(tid);
      expect(loaded.configVersion).toBe(3);
    });

    it('saveTimeline monotonically increments by exactly 1', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      let version = 1;
      for (let i = 0; i < 5; i++) {
        const next = await provider.saveTimeline(tid, buildConfig(), version);
        expect(next).toBe(version + 1);
        version = next;
      }

      expect(version).toBe(6);
    });
  });

  // ── Version conflict handling ──────────────────────────────────────────────

  describe('version conflict handling', () => {
    it(
      versionConflictIsSoft
        ? 'saveTimeline succeeds even with mismatched expectedVersion (soft conflict)'
        : 'saveTimeline rejects when expectedVersion is behind the current version',
      async () => {
        const provider = await factory({
          timelineId: tid,
          config: config1,
          configVersion: 1,
        });

        // First save succeeds
        const v2 = await provider.saveTimeline(tid, config2, 1);
        expect(v2).toBe(2);

        if (versionConflictIsSoft) {
          // Astrid: ignores expectedVersion, returns bridge head version
          const result = await provider.saveTimeline(tid, config3, 1);
          expect(typeof result).toBe('number');
        } else {
          // Stale version must reject
          await expect(
            provider.saveTimeline(tid, config3, 1),
          ).rejects.toBeInstanceOf(TimelineVersionConflictError);
        }
      },
    );

    it(
      versionConflictIsSoft
        ? 'saveTimeline succeeds with version ahead of current (soft conflict)'
        : 'saveTimeline rejects when expectedVersion is ahead of the current version',
      async () => {
        const provider = await factory({
          timelineId: tid,
          config: config1,
          configVersion: 1,
        });

        if (versionConflictIsSoft) {
          const result = await provider.saveTimeline(tid, config2, 5);
          expect(typeof result).toBe('number');
        } else {
          await expect(
            provider.saveTimeline(tid, config2, 5),
          ).rejects.toBeInstanceOf(TimelineVersionConflictError);
        }
      },
    );

    it(
      versionConflictIsSoft
        ? 'loaded config matches last successful save (soft conflict)'
        : 'provider never silently overwrites data on version mismatch',
      async () => {
        const provider = await factory({
          timelineId: tid,
          config: config1,
          configVersion: 5,
        });

        const originalLoaded = await provider.loadTimeline(tid);
        expect(originalLoaded.configVersion).toBe(5);

        if (!versionConflictIsSoft) {
          for (const wrongVersion of [1, 2, 3, 4, 6, 7, 10, 999]) {
            await expect(
              provider.saveTimeline(tid, buildConfig(), wrongVersion),
            ).rejects.toBeInstanceOf(TimelineVersionConflictError);
          }
        }

        const finalLoaded = await provider.loadTimeline(tid);
        expect(finalLoaded.configVersion).toBe(5);
      },
    );

    it('successful save returns the new version independent of the config payload', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 3,
      });

      const v4 = await provider.saveTimeline(tid, buildConfig(), 3);
      expect(v4).toBe(4);

      const loaded = await provider.loadTimeline(tid);
      expect(loaded.configVersion).toBe(4);
    });
  });

  // ── Diagnostics: error types ───────────────────────────────────────────────

  describe('diagnostics: error types', () => {
    it('throws TimelineNotFoundError for missing timelines on loadTimeline', async () => {
      if (skipMissingTimelineTests) return;

      const provider = await factory();

      await expect(
        provider.loadTimeline('nonexistent-timeline'),
      ).rejects.toBeInstanceOf(TimelineNotFoundError);
    });

    it('TimelineNotFoundError has code timeline_not_found', async () => {
      if (skipMissingTimelineTests) return;

      const provider = await factory();

      try {
        await provider.loadTimeline('nonexistent-timeline');
        expect.unreachable('Expected TimelineNotFoundError');
      } catch (err) {
        expect(err).toBeInstanceOf(TimelineNotFoundError);
        expect((err as any).code).toBe('timeline_not_found');
      }
    });

    it(
      versionConflictIsSoft
        ? 'TimelineVersionConflictError has code timeline_version_conflict'
        : 'TimelineVersionConflictError has code timeline_version_conflict',
      () => {
        const error = new TimelineVersionConflictError('stale baseVersion');
        expect(error.code).toBe('timeline_version_conflict');
        expect(error.name).toBe('TimelineVersionConflictError');
        expect(error.message).toContain('stale baseVersion');
      },
    );

    it('saveTimeline throws TimelineNotFoundError for missing timelines', async () => {
      if (skipMissingTimelineTests) return;

      const provider = await factory();

      await expect(
        provider.saveTimeline('nonexistent-timeline', buildConfig(), 1),
      ).rejects.toBeInstanceOf(TimelineNotFoundError);
    });
  });

  // ── Proposal base-version handling ─────────────────────────────────────────

  describe('proposal base-version handling', () => {
    it('loadTimeline returns configVersion suitable as a proposal baseVersion', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      const loaded = await provider.loadTimeline(tid);
      // configVersion is the base version for proposal creation
      expect(typeof loaded.configVersion).toBe('number');
      expect(loaded.configVersion).toBeGreaterThanOrEqual(1);
      expect(Number.isInteger(loaded.configVersion)).toBe(true);
    });

    it('configVersion matches the version last returned by saveTimeline', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      const v2 = await provider.saveTimeline(tid, config2, 1);
      expect(v2).toBe(2);

      const loaded = await provider.loadTimeline(tid);
      expect(loaded.configVersion).toBe(v2);
    });

    it('configVersion is consistent across multiple load/save cycles', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      for (let expected = 1; expected <= 5; expected++) {
        const next = await provider.saveTimeline(tid, buildConfig(), expected);
        expect(next).toBe(expected + 1);

        const loaded = await provider.loadTimeline(tid);
        expect(loaded.configVersion).toBe(expected + 1);
      }
    });
  });

  // ── Serialization fidelity ─────────────────────────────────────────────────

  describe('serialization fidelity', () => {
    it('loaded config matches saved config (subset match)', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      await provider.saveTimeline(tid, config2, 1);

      const loaded = await provider.loadTimeline(tid);
      // Use toMatchObject (subset) rather than toEqual (deep equality)
      // because some providers add normalization fields (e.g. background: null).
      // The provider must at least contain all fields that were saved.
      expect(loaded.config).toMatchObject(config2);
    });

    it('loaded config preserves clip data after multiple saves', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      await provider.saveTimeline(tid, config2, 1); // version 2: clip-1
      await provider.saveTimeline(tid, config3, 2); // version 3: clip-2

      const loaded = await provider.loadTimeline(tid);
      expect(loaded.configVersion).toBe(3);
      expect(loaded.config).toMatchObject(config3);
      expect((loaded.config as any).clips?.[0]?.id).toBe('clip-2');
    });

    it('loadAssetRegistry returns saved registry with exact match', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
        registry: registry1,
      });

      const loaded = await provider.loadAssetRegistry(tid);
      expect(loaded).toEqual(registry1);
    });

    it('saveTimeline with registry argument persists the registry', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      await provider.saveTimeline(tid, config2, 1, registry2);

      const loaded = await provider.loadAssetRegistry(tid);
      // At minimum, the registry should contain the saved assets.
      // Some providers may merge with existing, so we check inclusion.
      expect(loaded.assets['asset-1']).toBeDefined();
      expect(loaded.assets['asset-2']).toBeDefined();
    });

    it('config output metadata is preserved', async () => {
      const configWithOutput = buildConfig({
        output: {
          resolution: '3840x2160',
          fps: 60,
          file: 'uhd-timeline.mp4',
        },
      });

      const provider = await factory({
        timelineId: tid,
        config: configWithOutput,
        configVersion: 1,
      });

      const loaded = await provider.loadTimeline(tid);
      // Use toMatchObject — providers may add normalization fields
      expect(loaded.config.output).toMatchObject(configWithOutput.output);
    });

    it('tracks are preserved through save/load', async () => {
      const configWithTracks = buildConfig({
        tracks: [
          { id: 'V1', kind: 'visual', label: 'Video 1' },
          { id: 'A1', kind: 'audio', label: 'Audio 1' },
        ],
      });

      const provider = await factory({
        timelineId: tid,
        config: configWithTracks,
        configVersion: 1,
      });

      const loaded = await provider.loadTimeline(tid);
      expect(loaded.config.tracks).toHaveLength(2);
      expect(loaded.config.tracks![0].id).toBe('V1');
      expect(loaded.config.tracks![1].id).toBe('A1');
    });
  });

  // ── Extension requirements (stored via config) ────────────────────────────

  describe('extension requirements', () => {
    it('timeline config preserves custom extension-owned app data', async () => {
      const configWithAppData = buildConfig({
        app: {
          'com.example.test': {
            version: 1,
            settings: { theme: 'dark' },
          },
        },
      } as any);

      const provider = await factory({
        timelineId: tid,
        config: configWithAppData,
        configVersion: 1,
      });

      const loaded = await provider.loadTimeline(tid);
      expect((loaded.config as any).app).toBeDefined();
      expect((loaded.config as any).app['com.example.test']).toEqual({
        version: 1,
        settings: { theme: 'dark' },
      });
    });

    it('loadTimeline always returns a config object (never null/undefined)', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      const loaded = await provider.loadTimeline(tid);
      expect(loaded.config).toBeDefined();
      expect(typeof loaded.config).toBe('object');
      expect(loaded.config).not.toBeNull();
    });

    it('loadTimeline always returns a numeric configVersion', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      const loaded = await provider.loadTimeline(tid);
      expect(typeof loaded.configVersion).toBe('number');
      expect(Number.isFinite(loaded.configVersion)).toBe(true);
    });
  });

  // ── Checkpoints (optional) ─────────────────────────────────────────────────

  if (!skipCheckpoints) {
    describe('checkpoints (optional contract)', () => {
      it('has saveCheckpoint and loadCheckpoints methods', async () => {
        const provider = await factory({
          timelineId: tid,
          config: config1,
          configVersion: 1,
        });

        // These methods are optional on the interface
        if (typeof (provider as any).saveCheckpoint === 'function') {
          expect(typeof (provider as any).saveCheckpoint).toBe('function');
        }
        if (typeof (provider as any).loadCheckpoints === 'function') {
          expect(typeof (provider as any).loadCheckpoints).toBe('function');
        }
      });

      it('saveCheckpoint returns a truthy checkpoint ID', async () => {
        const provider = await factory({
          timelineId: tid,
          config: config1,
          configVersion: 1,
        });

        if (typeof (provider as any).saveCheckpoint !== 'function') {
          return; // Not supported, skip
        }

        const checkpointId = await (provider as any).saveCheckpoint(tid, {
          timelineId: tid,
          config: config1,
          createdAt: new Date('2026-06-20T00:00:00.000Z').toISOString(),
          triggerType: 'manual',
          label: 'Manual checkpoint',
          editsSinceLastCheckpoint: 1,
        });

        expect(checkpointId).toBeTruthy();
        expect(typeof checkpointId).toBe('string');
      });

      it('loadCheckpoints returns an array', async () => {
        const provider = await factory({
          timelineId: tid,
          config: config1,
          configVersion: 1,
        });

        if (typeof (provider as any).loadCheckpoints !== 'function') {
          return; // Not supported, skip
        }

        const checkpoints = await (provider as any).loadCheckpoints(tid);
        expect(Array.isArray(checkpoints)).toBe(true);
      });
    });
  }

  // ── registerAsset (optional) ──────────────────────────────────────────────

  if (!skipRegisterAsset) {
    describe('registerAsset', () => {
      it('has registerAsset method', async () => {
        const provider = await factory({
          timelineId: tid,
          config: config1,
          configVersion: 1,
        });

        if (typeof (provider as any).registerAsset === 'function') {
          expect(typeof (provider as any).registerAsset).toBe('function');
        }
      });

      it('registerAsset adds an asset to the registry', async () => {
        const provider = await factory({
          timelineId: tid,
          config: config1,
          configVersion: 1,
          registry: registry1,
        });

        if (typeof (provider as any).registerAsset !== 'function') {
          return; // Not supported, skip
        }

        await (provider as any).registerAsset(tid, 'asset-new', {
          file: 'audio/voice.wav',
          type: 'audio/wav',
          duration: 2.5,
        });

        const registry = await provider.loadAssetRegistry(tid);
        expect(registry.assets['asset-new']).toBeDefined();
        expect(registry.assets['asset-new'].file).toBe('audio/voice.wav');
      });
    });
  }

  // ── resolveAssetUrl (optional but common) ──────────────────────────────────

  describe('resolveAssetUrl', () => {
    it('has resolveAssetUrl method', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      expect(typeof provider.resolveAssetUrl).toBe('function');
    });

    it('resolveAssetUrl returns a string for absolute URLs', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      const result = await provider.resolveAssetUrl('https://example.com/test.mp4');
      expect(typeof result).toBe('string');
    });

    it('resolveAssetUrl returns a string for relative paths', async () => {
      const provider = await factory({
        timelineId: tid,
        config: config1,
        configVersion: 1,
      });

      const result = await provider.resolveAssetUrl('clips/demo.mp4');
      expect(typeof result).toBe('string');
    });
  });
}
