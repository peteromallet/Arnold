import { describe, it, expect } from 'vitest';

describe('supabase client runtime contracts', () => {
  it('exports canonical client accessor and keeps debug helpers outside the client facade', async () => {
    const clientExports = await import('@/integrations/supabase/client') as Record<string, unknown>;
    const debugModule = await import('@/integrations/supabase/support/debug/initializeSupabaseDebugGlobals');
    const debugExports = debugModule as Record<string, unknown>;

    expect(typeof clientExports.initializeSupabase).toBe('function');
    expect(typeof clientExports.initializeSupabaseResult).toBe('function');
    expect(typeof clientExports.getSupabaseClient).toBe('function');
    expect(typeof clientExports.getSupabaseClientResult).toBe('function');
    expect(typeof clientExports.supabaseClientRegistry).toBe('object');
    expect(clientExports.initializeSupabaseDebugGlobals).toBeUndefined();
    expect(clientExports.supabase).toBeUndefined();
    expect(clientExports.getLegacySupabaseClient).toBeUndefined();
    expect(clientExports.getOrInitializeSupabaseClientResult).toBeUndefined();
    expect(typeof debugExports.initializeSupabaseDebugGlobals).toBe('function');
  }, 15_000);

  it('does not expose deprecated legacy proxy module from canonical client path', async () => {
    expect(
      (await import('@/integrations/supabase/client') as Record<string, unknown>).legacySupabaseProxy,
    ).toBeUndefined();
  });
});
