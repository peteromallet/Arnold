/**
 * SDK-local in-memory state repository for extension settings tests.
 *
 * Replaces host `ProviderBackedExtensionStateRepository` + `InMemoryProviderStore`
 * so that SDK tests no longer import from `@/tools/video-editor/...`.
 *
 * Implements the subset of `StateRepository` needed by settings service and
 * migration tests: initialize/dispose lifecycle, settings snapshot CRUD, and
 * lifecycle event append+query.
 */

import type { SettingsSnapshot, StateRepository, LifecycleEvent } from '../contracts';

// ---------------------------------------------------------------------------
// InMemoryStateRepository
// ---------------------------------------------------------------------------

export class InMemoryStateRepository implements StateRepository {
  private _disposed = false;
  private _initialized = false;
  private _settingsSnapshots = new Map<string, SettingsSnapshot>();
  private _lifecycleEvents: LifecycleEvent[] = [];

  // -- StateRepository members -----------------------------------------------

  get isDisposed(): boolean {
    return this._disposed;
  }

  async putSettingsSnapshot(snapshot: SettingsSnapshot): Promise<void> {
    this._guardNotDisposed();
    this._settingsSnapshots.set(snapshot.extensionId, { ...snapshot });
  }

  async appendLifecycleEvent(event: LifecycleEvent): Promise<void> {
    this._guardNotDisposed();
    this._lifecycleEvents.push({ ...event });
  }

  // -- Extended methods needed by integration tests --------------------------

  async initialize(): Promise<void> {
    if (this._disposed) {
      throw new Error('Cannot initialize a disposed repository');
    }
    this._initialized = true;
  }

  async dispose(): Promise<void> {
    this._disposed = true;
    this._settingsSnapshots.clear();
    this._lifecycleEvents = [];
  }

  async getSettingsSnapshot(
    extensionId: string,
  ): Promise<SettingsSnapshot | null> {
    this._guardNotDisposed();
    return this._settingsSnapshots.get(extensionId) ?? null;
  }

  async getLifecycleEvents(
    extensionId: string,
    _limit?: number,
  ): Promise<LifecycleEvent[]> {
    this._guardNotDisposed();
    const events = this._lifecycleEvents
      .filter((e) => e.extensionId === extensionId)
      .sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
      );
    return _limit != null ? events.slice(0, _limit) : events;
  }

  // -- Internal helpers ------------------------------------------------------

  private _guardNotDisposed(): void {
    if (this._disposed) {
      throw new Error('Repository is disposed');
    }
  }
}
