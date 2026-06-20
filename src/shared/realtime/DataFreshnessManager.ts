/**
 * DataFreshnessManager - Single source of truth for data freshness and polling decisions
 *
 * This class centralizes all decisions about:
 * - Whether data is fresh (based on realtime events)
 * - What polling intervals React Query should use
 * - Realtime connection health status
 */

import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { registerDebugGlobal } from '@/shared/runtime/debugRegistry';
import {
  classifyRealtimeFetchError,
  toUserFriendlyRealtimeErrorMessage,
  type RealtimeFetchErrorType,
} from '@/shared/realtime/dataFreshness/errorPolicy';

type QueryKeyLike = readonly unknown[];
type RealtimeStatus = 'connected' | 'disconnected' | 'error';
type PollingInterval = number | false; // false = no polling
type FreshnessSubscriber = () => void;

function serializeQueryKey(queryKey: QueryKeyLike): string {
  return JSON.stringify(queryKey);
}

function markQueryKeysFresh(
  lastEventTimes: Map<string, number>,
  queryKeys: readonly QueryKeyLike[],
  now: number,
): void {
  queryKeys.forEach((queryKey) => {
    lastEventTimes.set(serializeQueryKey(queryKey), now);
  });
}

function getLastEventTime(
  lastEventTimes: Map<string, number>,
  queryKey: QueryKeyLike,
): number | undefined {
  return lastEventTimes.get(serializeQueryKey(queryKey));
}

function isQueryFresh(
  lastEventTimes: Map<string, number>,
  queryKey: QueryKeyLike,
  freshnessThreshold: number,
  now: number,
): boolean {
  const lastEvent = getLastEventTime(lastEventTimes, queryKey);
  if (!lastEvent) {
    return false;
  }
  return now - lastEvent < freshnessThreshold;
}

function buildQueryAgeDiagnostics(
  lastEventTimes: Map<string, number>,
  now: number,
  parseQueryKey: (rawKey: string) => unknown,
): Array<{ query: unknown; ageMs: number; ageSec: number }> {
  return Array.from(lastEventTimes.entries()).map(([key, time]) => ({
    query: parseQueryKey(key),
    ageMs: now - time,
    ageSec: Math.round((now - time) / 1000),
  }));
}

interface DataFreshnessState {
  realtimeStatus: RealtimeStatus;
  lastEventTimes: Map<string, number>;
  lastStatusChange: number;
  /** Track consecutive fetch failures per query for circuit breaker */
  fetchFailures: Map<string, { count: number; lastFailure: number }>;
}

class DataFreshnessManager {
  private state: DataFreshnessState = {
    realtimeStatus: 'disconnected',
    lastEventTimes: new Map(),
    lastStatusChange: Date.now(),
    fetchFailures: new Map()
  };

  private subscribers = new Set<FreshnessSubscriber>();

  // Circuit breaker settings
  private readonly CIRCUIT_BREAKER_THRESHOLD = 3; // failures before backing off
  private readonly CIRCUIT_BREAKER_RESET_MS = 60_000; // 1 minute to reset failure count

  // Toast throttling - prevent spamming error toasts
  private lastErrorToastTime = 0;
  private readonly ERROR_TOAST_THROTTLE_MS = 30_000; // Only show error toast every 30 seconds

  private parseQueryKey(rawKey: string): unknown {
    try {
      return JSON.parse(rawKey);
    } catch {
      return rawKey;
    }
  }

  /**
   * Report realtime connection status change
   */
  onRealtimeStatusChange(status: RealtimeStatus, _reason?: string) {
    const previousStatus = this.state.realtimeStatus;
    const now = Date.now();

    // Ignore duplicate status changes to keep lastStatusChange stable.
    // This allows the "recently connected" grace period in getPollingInterval to actually expire.
    if (previousStatus === status) {
      return; // Don't update state or notify subscribers for duplicates
    }

    // Actual status transition - update state
    this.state.realtimeStatus = status;
    this.state.lastStatusChange = now;

    // Notify all subscribers that polling intervals may have changed
    this.notifySubscribers();
  }

  /**
   * Report that realtime events were received for specific queries
   */
  onRealtimeEvent(_eventType: string, affectedQueries: readonly QueryKeyLike[]) {
    const now = Date.now();
    markQueryKeysFresh(this.state.lastEventTimes, affectedQueries, now);

    // Notify subscribers that data freshness has changed
    this.notifySubscribers();
  }

  /**
   * Get the appropriate polling interval for a query
   * Returns false to disable polling when realtime is working well
   */
  getPollingInterval(queryKey: QueryKeyLike): PollingInterval {
    const key = serializeQueryKey(queryKey);
    const lastEvent = getLastEventTime(this.state.lastEventTimes, queryKey);
    const now = Date.now();
    const timeSinceStatusChange = now - this.state.lastStatusChange;

    // If realtime is connected, trust it after it's been stable
    if (this.state.realtimeStatus === 'connected') {
      // If realtime just connected (< 30 seconds), give it time to prove it's stable
      if (timeSinceStatusChange < 30000) {
        return 30000; // 30 seconds - wait for realtime to prove it's stable
      }

      // If realtime has been stable for >30 seconds, trust it.
      // "No events" just means "nothing changed" — not "realtime is broken".

      if (lastEvent) {
        const eventAge = now - lastEvent;

        if (eventAge < 60000) { // Events within 1 minute
          return false; // Disable polling — realtime is working
        } else if (eventAge < 3 * 60 * 1000) { // Events within 3 minutes
          return 60000; // 60 seconds - light backup polling
        }
      }

      // Realtime stable for >30s but no events — this is normal when idle.
      // Use very light polling as a safety net only.
      if (timeSinceStatusChange > 5 * 60 * 1000) {
        // Realtime been stable for >5 minutes - fully trust it
        return false; // Disable polling — realtime is stable, idle is OK
      } else {
        // Realtime stable for 30s-5min - use safety net polling
        return 60000; // 60 seconds - safety net while realtime proves long-term stability
      }
    }

    // If realtime is disconnected or errored, use GRADUATED backoff polling
    // to prevent thundering herd and connection overload
    const disconnectedDuration = now - this.state.lastStatusChange;

    // Check circuit breaker - if this query has had many failures, back off more
    const failureInfo = this.state.fetchFailures.get(key);
    const hasRecentFailures = failureInfo &&
      (now - failureInfo.lastFailure) < this.CIRCUIT_BREAKER_RESET_MS &&
      failureInfo.count >= this.CIRCUIT_BREAKER_THRESHOLD;

    let pollingInterval: number;

    if (hasRecentFailures) {
      // Circuit breaker triggered - use much longer interval
      pollingInterval = 60_000; // 60 seconds
    } else if (disconnectedDuration < 30_000) {
      // First 30 seconds: 15s polling (give realtime time to reconnect)
      pollingInterval = 15_000;
    } else if (disconnectedDuration < 2 * 60_000) {
      // 30s - 2 minutes: 30s polling
      pollingInterval = 30_000;
    } else if (disconnectedDuration < 5 * 60_000) {
      // 2-5 minutes: 45s polling
      pollingInterval = 45_000;
    } else {
      // >5 minutes: 60s polling (realtime probably has issues)
      pollingInterval = 60_000;
    }

    return pollingInterval;
  }

  /**
   * Report a fetch failure for circuit breaker tracking
   */
  onFetchFailure(queryKey: QueryKeyLike, error: Error) {
    const key = serializeQueryKey(queryKey);
    const now = Date.now();
    const existing = this.state.fetchFailures.get(key);

    // Reset count if last failure was too long ago
    const shouldReset = existing && (now - existing.lastFailure) > this.CIRCUIT_BREAKER_RESET_MS;

    const newCount = shouldReset ? 1 : (existing?.count || 0) + 1;
    this.state.fetchFailures.set(key, { count: newCount, lastFailure: now });

    const isCircuitBreakerTriggered = newCount >= this.CIRCUIT_BREAKER_THRESHOLD;

    const errorType = classifyRealtimeFetchError(error);

    // Notify subscribers so polling intervals can adjust
    if (isCircuitBreakerTriggered) {
      this.notifySubscribers();

      // Show user-facing error toast (throttled to prevent spam)
      if (now - this.lastErrorToastTime > this.ERROR_TOAST_THROTTLE_MS) {
        this.lastErrorToastTime = now;

        this.reportCircuitBreakerError({
          queryKey: key,
          failureCount: newCount,
          errorType,
          error,
        });
      }
    }
  }

  private reportCircuitBreakerError(input: {
    queryKey: string;
    failureCount: number;
    errorType: RealtimeFetchErrorType;
    error: Error;
  }) {
    const userMessage = toUserFriendlyRealtimeErrorMessage(input.errorType, input.failureCount);
    normalizeAndPresentError(new Error('Data may be outdated. Will retry automatically.'), {
      context: 'DataFreshnessManager.onFetchFailure',
      toastTitle: userMessage,
      showToast: true,
      logData: {
        queryKey: this.parseQueryKey(input.queryKey),
        failureCount: input.failureCount,
        errorType: input.errorType,
        errorMessage: input.error.message,
      },
    });
  }


  /**
   * Report a successful fetch (resets circuit breaker)
   */
  onFetchSuccess(queryKey: QueryKeyLike) {
    const key = serializeQueryKey(queryKey);
    const existing = this.state.fetchFailures.get(key);

    if (existing && existing.count > 0) {
      // Reset failure count on success
      this.state.fetchFailures.delete(key);
    }
  }


  /**
   * Check if data for a query is considered fresh
   */
  isDataFresh(queryKey: QueryKeyLike, freshnessThreshold: number = 30000): boolean {
    return isQueryFresh(this.state.lastEventTimes, queryKey, freshnessThreshold, Date.now());
  }

  /**
   * Get current freshness state for debugging
   */
  getDiagnostics() {
    const now = Date.now();
    return {
      realtimeStatus: this.state.realtimeStatus,
      timeSinceStatusChange: now - this.state.lastStatusChange,
      trackedQueries: this.state.lastEventTimes.size,
      queryAges: buildQueryAgeDiagnostics(this.state.lastEventTimes, now, this.parseQueryKey),
      subscriberCount: this.subscribers.size,
      timestamp: now
    };
  }

  /**
   * Subscribe to freshness changes
   * Returns unsubscribe function
   */
  subscribe(callback: () => void): () => void {
    this.subscribers.add(callback);
    return () => this.subscribers.delete(callback);
  }

  /**
   * Clear all event history (useful for testing or project changes)
   */
  reset() {
    this.state.lastEventTimes.clear();
    this.state.fetchFailures.clear();
    this.state.realtimeStatus = 'disconnected';
    this.state.lastStatusChange = Date.now();
    this.notifySubscribers();
  }

  /**
   * Manually mark queries as fresh (useful for mutations)
   */
  markQueriesFresh(queryKeys: readonly QueryKeyLike[]) {
    const now = Date.now();
    markQueryKeysFresh(this.state.lastEventTimes, queryKeys, now);

    this.notifySubscribers();
  }

  private notifySubscribers() {
    this.subscribers.forEach((callback) => {
      try {
        callback();
      } catch (error) {
        normalizeAndPresentError(error, { context: 'DataFreshnessManager', showToast: false });
      }
    });
  }
}

// Singleton instance - single source of truth for the entire app
export const dataFreshnessManager = new DataFreshnessManager();

/** Dev-only helper for wiring debug globals during app bootstrap. */
export function registerDataFreshnessManagerDebugGlobal(): void {
  if (!import.meta.env.DEV || typeof window === 'undefined') {
    return;
  }

  registerDebugGlobal(
    '__DATA_FRESHNESS_MANAGER__',
    dataFreshnessManager,
    'DataFreshnessManager',
  );
}
