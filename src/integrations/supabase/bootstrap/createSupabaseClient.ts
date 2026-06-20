import { createClient } from '@supabase/supabase-js';
import { normalizeAndLogError } from '@/shared/lib/errorHandling/runtimeErrorReporting';
import type { Database } from '@/integrations/supabase/databasePublicTypes';
import {
  getSupabasePublishableKey,
  getSupabaseUrl,
} from '@/integrations/supabase/config/env';
import { fetchWithTimeout } from './fetchWithTimeout';
import { readAccessTokenFromStorage } from '@/shared/lib/supabaseSession';

const REALTIME_HEARTBEAT_INTERVAL_MS = 30_000;
const REALTIME_MAX_RECONNECT_DELAY_MS = 10_000;

export function createSupabaseClient() {
  try {
    // Cache the access token to avoid navigator.locks contention.
    // Every supabase.rpc()/from() call normally goes through fetchWithAuth →
    // _getAccessToken() → GoTrueClient.getSession() → _acquireLock(-1) →
    // navigator.locks (exclusive). When the lock is held by a concurrent token
    // refresh, ALL data requests queue indefinitely — blocking timeline drag RPCs
    // for 8+ seconds even when the DB responds in 60ms.
    //
    // Fix: replace PostgrestClient.fetch (a public property, read dynamically on
    // every from()/rpc() call) with a version that injects the cached token
    // directly, bypassing getSession/navigator.locks entirely for data requests.
    // Auth operations (supabase.auth.*) are unaffected.
    let cachedToken: string | null = readAccessTokenFromStorage();

    const url = getSupabaseUrl();
    const key = getSupabasePublishableKey();

    const client = createClient<Database>(url, key, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
      realtime: {
        params: { eventsPerSecond: 10 },
        heartbeatIntervalMs: REALTIME_HEARTBEAT_INTERVAL_MS,
        reconnectAfterMs: (tries: number) => Math.min(tries * 1000, REALTIME_MAX_RECONNECT_DELAY_MS),
      },
      global: {
        fetch: fetchWithTimeout,
      },
      db: { schema: 'public' },
    });

    // Replace PostgrestClient.fetch to use the cached token.
    // PostgrestClient reads this.fetch on each from()/rpc() call, so the
    // replacement takes effect immediately without recreating any clients.
    const dataFetch = (input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> => {
      const headers = new Headers(init.headers ?? {});
      if (!headers.has('apikey')) headers.set('apikey', key);
      if (!headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${cachedToken ?? key}`);
      }
      return fetchWithTimeout(input as Parameters<typeof fetchWithTimeout>[0], { ...init, headers });
    };
     
    (client as unknown as { rest: { fetch: typeof dataFetch } }).rest.fetch = dataFetch;

    // Keep the cached token in sync with auth state changes.
    client.auth.onAuthStateChange((_event, session) => {
      cachedToken = session?.access_token ?? null;
    });

    return client;
  } catch (error: unknown) {
    normalizeAndLogError(error, { context: 'SupabaseClient' });
    throw error;
  }
}
