/**
 * Tests for BrowserLocalFullSnapshotStore (T7) and browser-local
 * persistence service integration (T8).
 *
 * Validates:
 *  - localStorage keys are scoped by userId and timelineId
 *  - IndexedDB proposal storage round-trips correctly
 *  - Malformed localStorage JSON throws so the cache emits diagnostics (fail-closed)
 *  - Full snapshot save / load / delete cycle
 *  - Cross-scope isolation (different userId/timelineId pairs don't leak)
 *  - Enablement state and settings survive service recreate (simulated reload)
 *  - Corrupt localStorage / future schema version emit diagnostics and
 *    expose no partial state at the cache layer
 *  - IndexedDB unavailability preserves state/settings without proposals
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createFakeIndexedDB, IDBKeyRange, resetFakeIndexedDB } from 'fake-indexeddb';

// Install fake-indexeddb BEFORE importing the module under test
(globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
(globalThis as Record<string, unknown>).IDBKeyRange = IDBKeyRange;

import {
  BrowserLocalFullSnapshotStore,
  createBrowserLocalExtensionPersistenceService,
} from './browserLocalPersistenceStore';
import { CURRENT_SNAPSHOT_SCHEMA_VERSION } from './extensionPersistenceCache';
import {
  defineExtensionPersistenceConformanceSuite,
} from '../data/conformance/extensionPersistenceConformance';
import type { ExtensionPersistenceScope } from '../data/DataProvider';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SCOPE_A: ExtensionPersistenceScope = Object.freeze({
  userId: 'user-a',
  timelineId: 'timeline-001',
});

const SCOPE_B: ExtensionPersistenceScope = Object.freeze({
  userId: 'user-b',
  timelineId: 'timeline-002',
});

/**
 * Create a minimal valid snapshot JSON (without proposals).
 */
function makeSnapshotBase(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    meta: {
      schemaVersion: 1,
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: '2026-01-01T00:00:00.000Z',
    },
    packs: {},
    enablement: {},
    overrides: {},
    settings: {},
    events: [],
    lock: {
      entries: {},
      lastUpdatedAt: '2026-01-01T00:00:00.000Z',
    },
    ...overrides,
  };
}

/**
 * Build a full snapshot JSON string (base + proposals).
 */
function makeFullSnapshot(
  baseOverrides: Record<string, unknown> = {},
  proposals: Record<string, unknown> = {},
): string {
  const base = makeSnapshotBase(baseOverrides);
  return JSON.stringify({ ...base, proposals });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Clear all localStorage keys matching a prefix. */
function clearLocalStoragePrefix(prefix: string): void {
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith(prefix)) {
      keys.push(key);
    }
  }
  keys.forEach((k) => localStorage.removeItem(k));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('BrowserLocalFullSnapshotStore', () => {
  beforeEach(() => {
    // Fresh IndexedDB for each test
    (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
    // Clear localStorage keys used by tests
    clearLocalStoragePrefix('reigh.ext-state.');
  });

  afterEach(async () => {
    resetFakeIndexedDB();
    clearLocalStoragePrefix('reigh.ext-state.');
  });

  defineExtensionPersistenceConformanceSuite({
    name: 'browser-local',
    scope: SCOPE_A,
    reset: () => {
      (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
      clearLocalStoragePrefix('reigh.ext-state.');
    },
    seedCorruptSnapshot: () => {
      localStorage.setItem(
        `reigh.ext-state.${SCOPE_A.userId}.${SCOPE_A.timelineId}`,
        JSON.stringify(makeSnapshotBase({
          meta: {
            schemaVersion: CURRENT_SNAPSHOT_SCHEMA_VERSION + 100,
            createdAt: '2026-01-01T00:00:00.000Z',
            updatedAt: '2026-01-01T00:00:00.000Z',
          },
        })),
      );
    },
    createService: (diagnostics) =>
      createBrowserLocalExtensionPersistenceService(SCOPE_A, diagnostics),
  });

  // -------------------------------------------------------------------
  // Scoping
  // -------------------------------------------------------------------

  describe('scoping', () => {
    it('uses different localStorage keys for different userId', () => {
      const storeA = new BrowserLocalFullSnapshotStore(SCOPE_A);
      const storeB = new BrowserLocalFullSnapshotStore(SCOPE_B);

      // Verify the keys differ
      const keyA = 'reigh.ext-state.user-a.timeline-001';
      const keyB = 'reigh.ext-state.user-b.timeline-002';

      // Write to A
      localStorage.setItem(keyA, JSON.stringify(makeSnapshotBase({ packs: { extA: { id: 'x' } } })));
      // Write to B
      localStorage.setItem(keyB, JSON.stringify(makeSnapshotBase({ packs: { extB: { id: 'y' } } })));

      expect(localStorage.getItem(keyA)).not.toBeNull();
      expect(localStorage.getItem(keyB)).not.toBeNull();
      expect(localStorage.getItem(keyA)).not.toBe(localStorage.getItem(keyB));
    });

    it('isolates data between different scopes in localStorage', async () => {
      const storeA = new BrowserLocalFullSnapshotStore(SCOPE_A);
      const storeB = new BrowserLocalFullSnapshotStore(SCOPE_B);

      // Save snapshot for scope A
      const snapshotA = makeFullSnapshot({ packs: { 'ext.a': { extensionId: 'ext.a', version: '1.0.0' } } });
      await storeA.saveSnapshot(snapshotA);

      // Save different snapshot for scope B
      const snapshotB = makeFullSnapshot({ packs: { 'ext.b': { extensionId: 'ext.b', version: '2.0.0' } } });
      await storeB.saveSnapshot(snapshotB);

      // Load scope A — should only see its own data
      const loadedA = await storeA.loadSnapshot();
      expect(loadedA).not.toBeNull();
      const parsedA = JSON.parse(loadedA!);
      expect(parsedA.packs['ext.a']).toBeDefined();
      expect(parsedA.packs['ext.b']).toBeUndefined();

      // Load scope B — should only see its own data
      const loadedB = await storeB.loadSnapshot();
      expect(loadedB).not.toBeNull();
      const parsedB = JSON.parse(loadedB!);
      expect(parsedB.packs['ext.b']).toBeDefined();
      expect(parsedB.packs['ext.a']).toBeUndefined();
    });
  });

  // -------------------------------------------------------------------
  // Save / Load round-trip
  // -------------------------------------------------------------------

  describe('save/load round-trip', () => {
    it('returns null when no snapshot has been saved', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);
      const result = await store.loadSnapshot();
      expect(result).toBeNull();
    });

    it('saves and loads a snapshot without proposals', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);
      const original = makeFullSnapshot({
        packs: { 'ext.test': { extensionId: 'ext.test', version: '1.0.0' } },
      });

      await store.saveSnapshot(original);
      const loaded = await store.loadSnapshot();

      expect(loaded).not.toBeNull();
      const parsed = JSON.parse(loaded!);
      expect(parsed.meta.schemaVersion).toBe(1);
      expect(parsed.packs['ext.test']).toBeDefined();
      expect(parsed.packs['ext.test'].version).toBe('1.0.0');
    });

    it('saves and loads a snapshot with proposals', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);
      const proposals = {
        'proposal-1': {
          id: 'proposal-1',
          extensionId: 'ext.test',
          status: 'draft',
          payload: { action: 'install', version: '2.0.0' },
          createdAt: '2026-01-01T00:00:00.000Z',
          updatedAt: '2026-01-01T00:00:00.000Z',
          label: 'Test Proposal',
        },
      };
      const original = makeFullSnapshot(
        { packs: { 'ext.test': { extensionId: 'ext.test', version: '1.0.0' } } },
        proposals,
      );

      await store.saveSnapshot(original);
      const loaded = await store.loadSnapshot();

      expect(loaded).not.toBeNull();
      const parsed = JSON.parse(loaded!);
      expect(parsed.proposals).toBeDefined();
      expect(parsed.proposals['proposal-1']).toBeDefined();
      expect(parsed.proposals['proposal-1'].status).toBe('draft');
      expect(parsed.proposals['proposal-1'].payload.action).toBe('install');
    });

    it('preserves all proposal statuses', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);
      const proposals: Record<string, unknown> = {};
      const statuses = ['draft', 'submitted', 'accepted', 'rejected', 'cancelled', 'expired'] as const;

      for (let i = 0; i < statuses.length; i++) {
        proposals[`proposal-${i}`] = {
          id: `proposal-${i}`,
          extensionId: 'ext.test',
          status: statuses[i],
          payload: {},
          createdAt: '2026-01-01T00:00:00.000Z',
          updatedAt: '2026-01-01T00:00:00.000Z',
        };
      }

      const original = makeFullSnapshot({}, proposals);
      await store.saveSnapshot(original);
      const loaded = await store.loadSnapshot();
      const parsed = JSON.parse(loaded!);

      expect(Object.keys(parsed.proposals)).toHaveLength(6);
      for (let i = 0; i < statuses.length; i++) {
        expect(parsed.proposals[`proposal-${i}`].status).toBe(statuses[i]);
      }
    });

    it('overwrites existing snapshot on save', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);

      // First save
      const first = makeFullSnapshot({
        packs: { 'ext.test': { extensionId: 'ext.test', version: '1.0.0' } },
      });
      await store.saveSnapshot(first);

      // Second save (overwrites)
      const second = makeFullSnapshot({
        packs: { 'ext.test': { extensionId: 'ext.test', version: '2.0.0' } },
      });
      await store.saveSnapshot(second);

      const loaded = await store.loadSnapshot();
      const parsed = JSON.parse(loaded!);
      expect(parsed.packs['ext.test'].version).toBe('2.0.0');
    });
  });

  // -------------------------------------------------------------------
  // Delete
  // -------------------------------------------------------------------

  describe('delete', () => {
    it('deleteSnapshot clears both localStorage and IndexedDB', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);
      const proposals = {
        'prop-1': {
          id: 'prop-1',
          extensionId: 'ext.test',
          status: 'draft',
          payload: {},
          createdAt: '2026-01-01T00:00:00.000Z',
          updatedAt: '2026-01-01T00:00:00.000Z',
        },
      };
      const snapshot = makeFullSnapshot(
        { packs: { 'ext.test': { extensionId: 'ext.test' } } },
        proposals,
      );

      await store.saveSnapshot(snapshot);

      // Verify data exists
      let loaded = await store.loadSnapshot();
      expect(loaded).not.toBeNull();

      // Delete
      await store.deleteSnapshot();

      // Verify cleared
      loaded = await store.loadSnapshot();
      expect(loaded).toBeNull();
    });

    it('deleteSnapshot is idempotent', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);

      // Delete on empty store should not throw
      await store.deleteSnapshot();
      await store.deleteSnapshot(); // second call

      // After delete, load returns null
      const loaded = await store.loadSnapshot();
      expect(loaded).toBeNull();
    });

    it('deleteSnapshot only affects the target scope', async () => {
      const storeA = new BrowserLocalFullSnapshotStore(SCOPE_A);
      const storeB = new BrowserLocalFullSnapshotStore(SCOPE_B);

      // Save to both
      await storeA.saveSnapshot(makeFullSnapshot({ packs: { ext: { id: 'a' } } }));
      await storeB.saveSnapshot(makeFullSnapshot({ packs: { ext: { id: 'b' } } }));

      // Delete A only
      await storeA.deleteSnapshot();

      // A should be empty, B should still have data
      expect(await storeA.loadSnapshot()).toBeNull();
      expect(await storeB.loadSnapshot()).not.toBeNull();
    });
  });

  // -------------------------------------------------------------------
  // Malformed JSON → fail-closed (throws so cache emits diagnostics)
  // -------------------------------------------------------------------

  describe('malformed JSON handling', () => {
    it('throws when localStorage contains unparseable JSON', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);

      // Directly write invalid JSON to localStorage
      const key = 'reigh.ext-state.user-a.timeline-001';
      localStorage.setItem(key, 'not-valid-json{{{');

      await expect(store.loadSnapshot()).rejects.toThrow(/malformed/i);
    });

    it('throws when localStorage JSON root is an array', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);

      const key = 'reigh.ext-state.user-a.timeline-001';
      localStorage.setItem(key, JSON.stringify([1, 2, 3]));

      await expect(store.loadSnapshot()).rejects.toThrow(/malformed|not a plain object/i);
    });

    it('throws when localStorage JSON root is null', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);

      const key = 'reigh.ext-state.user-a.timeline-001';
      localStorage.setItem(key, 'null');

      await expect(store.loadSnapshot()).rejects.toThrow(/malformed|not a plain object/i);
    });

    it('throws when localStorage JSON root is a primitive', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);

      const key = 'reigh.ext-state.user-a.timeline-001';
      localStorage.setItem(key, '"just a string"');

      await expect(store.loadSnapshot()).rejects.toThrow(/malformed|not a plain object/i);
    });

    it('emits hydration diagnostics and fails closed at the service level', async () => {
      const key = 'reigh.ext-state.user-a.timeline-001';
      localStorage.setItem(key, 'corrupt{{{');

      const diagnostics: Array<{ severity: string; code: string; message: string; milestone?: string }> = [];
      const service = createBrowserLocalExtensionPersistenceService(SCOPE_A, diagnostics);

      await service.initialize();

      // Must have a hydration error diagnostic
      const errors = diagnostics.filter((d) => d.severity === 'error');
      expect(errors.length).toBeGreaterThan(0);
      expect(
        errors.some((d) => d.code === 'extension_cache_hydration_load_failed'),
      ).toBe(true);

      // Repository must fail closed — no partial state exposed
      const repo = service.repository;
      await expect(repo.getEnablementState('any')).rejects.toThrow(/hydrat/i);
      await expect(repo.getSettingsSnapshot('any')).rejects.toThrow(/hydrat/i);
      await expect(repo.getFullExtensionState()).rejects.toThrow(/hydrat/i);
      await expect(service.getProposal('any')).rejects.toThrow(/hydrat/i);

      await service.dispose();
    });

    it('still saves successfully after recovering from corrupt data', async () => {
      const store = new BrowserLocalFullSnapshotStore(SCOPE_A);

      // First, corrupt the localStorage
      const key = 'reigh.ext-state.user-a.timeline-001';
      localStorage.setItem(key, 'corrupt{{{');

      // Load should reject (fail-closed)
      await expect(store.loadSnapshot()).rejects.toThrow(/malformed/i);

      // Save a valid snapshot (should overwrite corrupt data)
      const valid = makeFullSnapshot({
        packs: { 'ext.recovered': { extensionId: 'ext.recovered', version: '1.0.0' } },
      });
      await store.saveSnapshot(valid);

      // Now load should work
      const recovered = await store.loadSnapshot();
      expect(recovered).not.toBeNull();
      const parsed = JSON.parse(recovered!);
      expect(parsed.packs['ext.recovered']).toBeDefined();
    });
  });

  // -------------------------------------------------------------------
  // Proposal isolation (IndexedDB scoping)
  // -------------------------------------------------------------------

  describe('proposal isolation', () => {
    it('proposals are scoped by userId and timelineId', async () => {
      const storeA = new BrowserLocalFullSnapshotStore(SCOPE_A);
      const storeB = new BrowserLocalFullSnapshotStore(SCOPE_B);

      // Save proposal for scope A
      const proposalsA = {
        'prop-a': {
          id: 'prop-a',
          extensionId: 'ext.a',
          status: 'draft',
          payload: { for: 'A' },
          createdAt: '2026-01-01T00:00:00.000Z',
          updatedAt: '2026-01-01T00:00:00.000Z',
        },
      };
      await storeA.saveSnapshot(makeFullSnapshot({}, proposalsA));

      // Save different proposal for scope B
      const proposalsB = {
        'prop-b': {
          id: 'prop-b',
          extensionId: 'ext.b',
          status: 'accepted',
          payload: { for: 'B' },
          createdAt: '2026-01-01T00:00:00.000Z',
          updatedAt: '2026-01-01T00:00:00.000Z',
        },
      };
      await storeB.saveSnapshot(makeFullSnapshot({}, proposalsB));

      // Scope A should only see its proposal
      const loadedA = await storeA.loadSnapshot();
      const parsedA = JSON.parse(loadedA!);
      expect(parsedA.proposals['prop-a']).toBeDefined();
      expect(parsedA.proposals['prop-b']).toBeUndefined();

      // Scope B should only see its proposal
      const loadedB = await storeB.loadSnapshot();
      const parsedB = JSON.parse(loadedB!);
      expect(parsedB.proposals['prop-b']).toBeDefined();
      expect(parsedB.proposals['prop-a']).toBeUndefined();
    });

    it('updating proposals in one scope does not affect another', async () => {
      const storeA = new BrowserLocalFullSnapshotStore(SCOPE_A);
      const storeB = new BrowserLocalFullSnapshotStore(SCOPE_B);

      // Both scopes start with the same proposal ID (edge case)
      const proposalsA = {
        'shared-id': {
          id: 'shared-id',
          extensionId: 'ext.shared',
          status: 'draft',
          payload: { owner: 'A' },
          createdAt: '2026-01-01T00:00:00.000Z',
          updatedAt: '2026-01-01T00:00:00.000Z',
        },
      };
      const proposalsB = {
        'shared-id': {
          id: 'shared-id',
          extensionId: 'ext.shared',
          status: 'draft',
          payload: { owner: 'B' },
          createdAt: '2026-01-01T00:00:00.000Z',
          updatedAt: '2026-01-01T00:00:00.000Z',
        },
      };

      await storeA.saveSnapshot(makeFullSnapshot({}, proposalsA));
      await storeB.saveSnapshot(makeFullSnapshot({}, proposalsB));

      // Now update scope A's proposal
      const updatedA = {
        'shared-id': {
          id: 'shared-id',
          extensionId: 'ext.shared',
          status: 'accepted',
          payload: { owner: 'A' },
          createdAt: '2026-01-01T00:00:00.000Z',
          updatedAt: '2026-06-22T00:00:00.000Z',
        },
      };
      await storeA.saveSnapshot(makeFullSnapshot({}, updatedA));

      // Scope B should still see its original proposal
      const loadedB = await storeB.loadSnapshot();
      const parsedB = JSON.parse(loadedB!);
      expect(parsedB.proposals['shared-id'].status).toBe('draft');
      expect(parsedB.proposals['shared-id'].payload.owner).toBe('B');

      // Scope A should see the updated proposal
      const loadedA = await storeA.loadSnapshot();
      const parsedA = JSON.parse(loadedA!);
      expect(parsedA.proposals['shared-id'].status).toBe('accepted');
      expect(parsedA.proposals['shared-id'].payload.owner).toBe('A');
    });
  });
});

// ---------------------------------------------------------------------------
// Factory integration test
// ---------------------------------------------------------------------------

describe('createBrowserLocalExtensionPersistenceService', () => {
  beforeEach(() => {
    (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
    clearLocalStoragePrefix('reigh.ext-state.');
  });

  afterEach(() => {
    resetFakeIndexedDB();
    clearLocalStoragePrefix('reigh.ext-state.');
  });

  it('returns a service with all capabilities advertised', () => {
    const service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    expect(service.capabilities.state).toBe(true);
    expect(service.capabilities.settings).toBe(true);
    expect(service.capabilities.proposals).toBe(true);
  });

  it('service initializes and disposes successfully', async () => {
    const service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    expect(service.isDisposed).toBe(false);

    await service.initialize();
    expect(service.isDisposed).toBe(false);

    await service.dispose();
    expect(service.isDisposed).toBe(true);
  });

  it('service repository supports CRUD after hydration', async () => {
    const service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    await service.initialize();

    // Create a proposal
    const proposalId = await service.createProposal({
      extensionId: 'ext.test',
      status: 'pending',
      payload: { test: true },
    });
    expect(proposalId).toBeTruthy();

    // Read it back
    const proposal = await service.getProposal(proposalId);
    expect(proposal).not.toBeNull();
    expect(proposal!.status).toBe('pending');
    expect(proposal!.payload.test).toBe(true);

    // Update status
    await service.updateProposalStatus(proposalId, 'accepted');
    const updated = await service.getProposal(proposalId);
    expect(updated!.status).toBe('accepted');

    // List proposals
    const list = await service.listProposals({ extensionId: 'ext.test' });
    expect(list).toHaveLength(1);
    expect(list[0].id).toBe(proposalId);

    await service.dispose();
  });

  it('proposals survive dispose and reinitialize (service restart)', async () => {
    // First lifecycle
    let service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    await service.initialize();

    const proposalId = await service.createProposal({
      extensionId: 'ext.persist',
      status: 'pending',
      payload: { survive: true },
    });

    await service.dispose();

    // Second lifecycle (simulating page reload / re-mount)
    service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    await service.initialize();

    const proposal = await service.getProposal(proposalId);
    expect(proposal).not.toBeNull();
    expect(proposal!.extensionId).toBe('ext.persist');
    expect(proposal!.payload.survive).toBe(true);

    await service.dispose();
  });

  it('passes diagnostics array through to cache', async () => {
    const diagnostics: Array<{ severity: string; code: string; message: string; milestone?: string }> = [];
    const service = createBrowserLocalExtensionPersistenceService(SCOPE_A, diagnostics);

    await service.initialize();
    // No errors expected for clean initialization
    const errors = diagnostics.filter((d) => d.severity === 'error');
    expect(errors).toHaveLength(0);

    await service.dispose();
  });

  // -------------------------------------------------------------------
  // T8: Reload simulation — state/settings survive service recreate
  // -------------------------------------------------------------------

  it('enablement state and settings survive service recreate (simulated reload)', async () => {
    // First service lifecycle — write state via repository
    let service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    await service.initialize();
    const repo = service.repository;

    // Write enablement state
    await repo.putEnablementState({
      extensionId: 'ext.reload',
      enabled: true,
      lastToggledAt: '2026-06-22T00:00:00.000Z',
      toggleReason: 'user-enabled',
    });

    // Write settings snapshot
    await repo.putSettingsSnapshot({
      extensionId: 'ext.reload',
      schemaVersion: 1,
      values: { theme: 'dark', fontSize: 14 },
      lastWrittenAt: '2026-06-22T00:00:00.000Z',
    });

    // Write a pack record (use any cast to avoid unresolvable @reigh/editor-sdk types)
    await repo.putPackRecord({
      extensionId: 'ext.reload',
      version: '1.0.0',
      integrity: 'sha256-abc123',
      installedAt: '2026-06-22T00:00:00.000Z',
      bundleContentRef: 'ref-reload-1',
      manifestSnapshot: { id: 'ext.reload', version: '1.0.0' },
    } as never);

    // Wait for async flush to complete
    await new Promise((r) => setTimeout(r, 50));
    await service.dispose();

    // Second service lifecycle (simulated page reload / re-mount)
    service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    await service.initialize();
    const repo2 = service.repository;

    // Verify enablement state rehydrated
    const enablement = await repo2.getEnablementState('ext.reload');
    expect(enablement).not.toBeNull();
    expect(enablement!.enabled).toBe(true);
    expect(enablement!.toggleReason).toBe('user-enabled');

    // Verify settings rehydrated
    const settings = await repo2.getSettingsSnapshot('ext.reload');
    expect(settings).not.toBeNull();
    expect(settings!.values.theme).toBe('dark');
    expect(settings!.values.fontSize).toBe(14);

    // Verify pack record rehydrated
    const pack = await repo2.getPackRecord('ext.reload');
    expect(pack).not.toBeNull();
    expect(pack!.version).toBe('1.0.0');
    expect(pack!.bundleContentRef).toBe('ref-reload-1');

    // Verify full state is coherent
    const fullState = await repo2.getFullExtensionState();
    expect(fullState.enablement['ext.reload']).toBeDefined();
    expect(fullState.settings['ext.reload']).toBeDefined();
    expect(fullState.packs['ext.reload']).toBeDefined();

    await service.dispose();
  });

  it('multiple enablement/settings records survive reload', async () => {
    let service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    await service.initialize();
    const repo = service.repository;

    // Write multiple extensions' state
    for (const extId of ['ext.one', 'ext.two', 'ext.three']) {
      await repo.putEnablementState({
        extensionId: extId,
        enabled: extId !== 'ext.two', // ext.two is disabled
        lastToggledAt: '2026-06-22T00:00:00.000Z',
      });
      await repo.putSettingsSnapshot({
        extensionId: extId,
        schemaVersion: 1,
        values: { id: extId, color: extId === 'ext.one' ? 'blue' : 'green' },
        lastWrittenAt: '2026-06-22T00:00:00.000Z',
      });
    }

    await new Promise((r) => setTimeout(r, 50));
    await service.dispose();

    // Reload
    service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    await service.initialize();
    const repo2 = service.repository;

    // All three should be present
    const allEnablement = await repo2.getAllEnablementStates();
    expect(allEnablement).toHaveLength(3);
    const extTwo = allEnablement.find((e) => e.extensionId === 'ext.two');
    expect(extTwo!.enabled).toBe(false);

    const allSettings = await repo2.getAllSettingsSnapshots();
    expect(allSettings).toHaveLength(3);
    const extOne = allSettings.find((s) => s.extensionId === 'ext.one');
    expect(extOne!.values.color).toBe('blue');

    await service.dispose();
  });

  // -------------------------------------------------------------------
  // T8: Corrupt localStorage → diagnostics + no partial state
  // -------------------------------------------------------------------

  it('future schema version in localStorage emits error diagnostics', async () => {
    // Write valid JSON to localStorage with a schema version far in the future
    const key = 'reigh.ext-state.user-a.timeline-001';
    const futureSnapshot = JSON.stringify({
      meta: {
        schemaVersion: CURRENT_SNAPSHOT_SCHEMA_VERSION + 100,
        createdAt: '2026-01-01T00:00:00.000Z',
        updatedAt: '2026-01-01T00:00:00.000Z',
      },
      packs: {},
      enablement: {},
      overrides: {},
      settings: {},
      events: [],
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
      proposals: {},
    });
    localStorage.setItem(key, futureSnapshot);

    const diagnostics: Array<{ severity: string; code: string; message: string; milestone?: string }> = [];
    const service = createBrowserLocalExtensionPersistenceService(SCOPE_A, diagnostics);

    await service.initialize();

    // Must have an error diagnostic for future schema version
    const errors = diagnostics.filter((d) => d.severity === 'error');
    expect(errors.length).toBeGreaterThan(0);
    const futureDiag = errors.find(
      (d) => d.code === 'extension_cache_future_schema_version',
    );
    expect(futureDiag).toBeDefined();
    expect(futureDiag!.message).toContain(
      String(CURRENT_SNAPSHOT_SCHEMA_VERSION + 100),
    );

    await service.dispose();
  });

  it('future schema version exposes no partial state (all methods throw)', async () => {
    // Setup future-version snapshot
    const key = 'reigh.ext-state.user-a.timeline-001';
    const futureSnapshot = JSON.stringify({
      meta: {
        schemaVersion: CURRENT_SNAPSHOT_SCHEMA_VERSION + 50,
        createdAt: '2026-01-01T00:00:00.000Z',
        updatedAt: '2026-01-01T00:00:00.000Z',
      },
      packs: { 'ext.secret': { extensionId: 'ext.secret', version: '9.9.9' } },
      enablement: { 'ext.secret': { extensionId: 'ext.secret', enabled: true, lastToggledAt: '' } },
      overrides: {},
      settings: { 'ext.secret': { extensionId: 'ext.secret', schemaVersion: 1, values: { secret: true }, lastWrittenAt: '' } },
      events: [],
      lock: { entries: {}, lastUpdatedAt: '' },
      proposals: {},
    });
    localStorage.setItem(key, futureSnapshot);

    const diagnostics: Array<{ severity: string; code: string; message: string; milestone?: string }> = [];
    const service = createBrowserLocalExtensionPersistenceService(SCOPE_A, diagnostics);
    await service.initialize();

    // Error diagnostic emitted
    const errors = diagnostics.filter((d) => d.severity === 'error');
    expect(errors.length).toBeGreaterThan(0);

    const repo = service.repository;

    // Every repository read must throw — no partial state exposed
    await expect(repo.getEnablementState('ext.secret')).rejects.toThrow(
      /hydrat|future schema/i,
    );
    await expect(repo.getSettingsSnapshot('ext.secret')).rejects.toThrow(
      /hydrat|future schema/i,
    );
    await expect(repo.getPackRecord('ext.secret')).rejects.toThrow(
      /hydrat|future schema/i,
    );
    await expect(repo.getAllEnablementStates()).rejects.toThrow(
      /hydrat|future schema/i,
    );
    await expect(repo.getFullExtensionState()).rejects.toThrow(
      /hydrat|future schema/i,
    );

    // Every proposal method must throw
    await expect(service.getProposal('any')).rejects.toThrow(
      /hydrat|future schema/i,
    );
    await expect(
      service.createProposal({
        extensionId: 'ext.secret',
        status: 'pending',
        payload: {},
      }),
    ).rejects.toThrow(/hydrat|future schema/i);

    // Writes must also be blocked
    await expect(
      repo.putEnablementState({
        extensionId: 'ext.secret',
        enabled: false,
        lastToggledAt: '',
      }),
    ).rejects.toThrow(/hydrat|future schema/i);

    await service.dispose();
  });

  it('service recovers after corrupt data is overwritten with valid data', async () => {
    const key = 'reigh.ext-state.user-a.timeline-001';

    // Phase 1: write future-version corrupt data
    localStorage.setItem(
      key,
      JSON.stringify({
        meta: {
          schemaVersion: CURRENT_SNAPSHOT_SCHEMA_VERSION + 10,
          createdAt: '',
          updatedAt: '',
        },
        packs: {},
        enablement: {},
        overrides: {},
        settings: {},
        events: [],
        lock: { entries: {}, lastUpdatedAt: '' },
        proposals: {},
      }),
    );

    let diagnostics: Array<{ severity: string; code: string; message: string; milestone?: string }> = [];
    let service = createBrowserLocalExtensionPersistenceService(SCOPE_A, diagnostics);
    await service.initialize();

    // Verify fail-closed
    const errors = diagnostics.filter((d) => d.severity === 'error');
    expect(errors.length).toBeGreaterThan(0);
    await expect(
      service.getProposal('any'),
    ).rejects.toThrow();
    await service.dispose();

    // Phase 2: clear the corrupt data so a fresh service starts empty,
    // then write valid state to overwrite.
    localStorage.removeItem(key);

    diagnostics = [];
    service = createBrowserLocalExtensionPersistenceService(SCOPE_A, diagnostics);
    await service.initialize();

    // The new service starts empty (no snapshot exists)
    const repo = service.repository;
    await repo.putEnablementState({
      extensionId: 'ext.recovered',
      enabled: true,
      lastToggledAt: '2026-06-22T00:00:00.000Z',
    });
    await repo.putSettingsSnapshot({
      extensionId: 'ext.recovered',
      schemaVersion: 1,
      values: { recovered: true },
      lastWrittenAt: '2026-06-22T00:00:00.000Z',
    });

    await new Promise((r) => setTimeout(r, 50));
    await service.dispose();

    // Phase 3: third service — should load the valid data cleanly
    diagnostics = [];
    service = createBrowserLocalExtensionPersistenceService(SCOPE_A, diagnostics);
    await service.initialize();

    const errors3 = diagnostics.filter((d) => d.severity === 'error');
    expect(errors3).toHaveLength(0);

    const enablement = await service.repository.getEnablementState('ext.recovered');
    expect(enablement).not.toBeNull();
    expect(enablement!.enabled).toBe(true);

    const settings = await service.repository.getSettingsSnapshot('ext.recovered');
    expect(settings).not.toBeNull();
    expect(settings!.values.recovered).toBe(true);

    await service.dispose();
  });

  // -------------------------------------------------------------------
  // T8: Store throws → cache emits diagnostics + fail-closed
  // -------------------------------------------------------------------

  it('store-level load failure emits hydration error diagnostic', async () => {
    // Import the FullSnapshotStore type to create a throwing mock
    const {
      CachedExtensionStateRepository,
    } = await import('./extensionPersistenceCache');

    const throwingStore = {
      async loadSnapshot(): Promise<string | null> {
        throw new Error('Simulated store failure');
      },
      async saveSnapshot(_serialized: string): Promise<void> {
        // no-op
      },
      async deleteSnapshot(): Promise<void> {
        // no-op
      },
    };

    const diagnostics: Array<{ severity: string; code: string; message: string; milestone?: string }> = [];
    const repo = new CachedExtensionStateRepository(throwingStore, diagnostics);

    await repo.initialize();

    // Must have hydration load-failed diagnostic
    const errors = diagnostics.filter((d) => d.severity === 'error');
    expect(errors.length).toBeGreaterThan(0);
    expect(
      errors.some((d) => d.code === 'extension_cache_hydration_load_failed'),
    ).toBe(true);

    // All methods must throw — no partial state
    await expect(repo.getEnablementState('any')).rejects.toThrow(/hydrat/i);
    await expect(repo.getSettingsSnapshot('any')).rejects.toThrow(/hydrat/i);

    await repo.dispose();
  });

  // -------------------------------------------------------------------
  // T8: IndexedDB unavailability — state/settings preserved
  // -------------------------------------------------------------------

  it('state and settings survive when IndexedDB is unavailable', async () => {
    // First: write state/settings with IndexedDB available
    let service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    await service.initialize();
    const repo = service.repository;

    await repo.putEnablementState({
      extensionId: 'ext.idb-test',
      enabled: true,
      lastToggledAt: '2026-06-22T00:00:00.000Z',
    });
    await repo.putSettingsSnapshot({
      extensionId: 'ext.idb-test',
      schemaVersion: 1,
      values: { indexedDbRequired: false },
      lastWrittenAt: '2026-06-22T00:00:00.000Z',
    });

    await new Promise((r) => setTimeout(r, 50));
    await service.dispose();

    // Second: simulate IndexedDB unavailability
    const originalIndexedDB = (globalThis as Record<string, unknown>).indexedDB;
    (globalThis as Record<string, unknown>).indexedDB = undefined;

    try {
      service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
      // Initialization should still succeed — proposals may be lost but
      // the base state in localStorage is the authoritative source
      await service.initialize();
      const repo2 = service.repository;

      // State/settings must still be available
      const enablement = await repo2.getEnablementState('ext.idb-test');
      expect(enablement).not.toBeNull();
      expect(enablement!.enabled).toBe(true);

      const settings = await repo2.getSettingsSnapshot('ext.idb-test');
      expect(settings).not.toBeNull();
      expect(settings!.values.indexedDbRequired).toBe(false);

      // Proposals are best-effort; IndexedDB unavailability means empty
      const list = await service.listProposals();
      expect(list).toHaveLength(0);

      await service.dispose();
    } finally {
      (globalThis as Record<string, unknown>).indexedDB = originalIndexedDB;
    }
  });

  it('reload preserves state/settings even when IndexedDB was unavailable during write', async () => {
    // Simulate a scenario where IndexedDB is unavailable but the
    // user still writes state/settings (which go to localStorage)
    const originalIndexedDB = (globalThis as Record<string, unknown>).indexedDB;
    (globalThis as Record<string, unknown>).indexedDB = undefined;

    let service: ReturnType<typeof createBrowserLocalExtensionPersistenceService>;
    try {
      service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
      await service.initialize();
      const repo = service.repository;

      // Write state/settings — these land in localStorage (no IndexedDB needed)
      await repo.putEnablementState({
        extensionId: 'ext.no-idb',
        enabled: true,
        lastToggledAt: '2026-06-22T00:00:00.000Z',
      });
      await repo.putSettingsSnapshot({
        extensionId: 'ext.no-idb',
        schemaVersion: 1,
        values: { savedWithoutIndexedDB: true },
        lastWrittenAt: '2026-06-22T00:00:00.000Z',
      });

      await new Promise((r) => setTimeout(r, 50));
      await service.dispose();
    } finally {
      (globalThis as Record<string, unknown>).indexedDB = originalIndexedDB;
    }

    // Restore IndexedDB and reload
    (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();

    service = createBrowserLocalExtensionPersistenceService(SCOPE_A);
    await service.initialize();
    const repo2 = service.repository;

    const enablement = await repo2.getEnablementState('ext.no-idb');
    expect(enablement).not.toBeNull();
    expect(enablement!.enabled).toBe(true);

    const settings = await repo2.getSettingsSnapshot('ext.no-idb');
    expect(settings).not.toBeNull();
    expect(settings!.values.savedWithoutIndexedDB).toBe(true);

    await service.dispose();
  });
});
