import type { Session } from '@supabase/supabase-js';

export interface RenderRuntime {
  projectId: string;
  orchestratorBaseUrl: string;
  getSupabaseSession: () => Promise<Session | null>;
  getWorkerJwt: () => Promise<string | null>;
}

export const FALLBACK_RENDER_RUNTIME: RenderRuntime = {
  projectId: '',
  orchestratorBaseUrl: '',
  getSupabaseSession: async () => null,
  getWorkerJwt: async () => null,
};

export function createRenderRuntime(input: {
  projectId: string;
  orchestratorBaseUrl: string;
  getSupabaseSession?: () => Promise<Session | null>;
  getWorkerJwt?: () => Promise<string | null>;
}): RenderRuntime {
  const getSupabaseSession = input.getSupabaseSession ?? (async () => null);
  return {
    projectId: input.projectId,
    orchestratorBaseUrl: input.orchestratorBaseUrl,
    getSupabaseSession,
    getWorkerJwt: input.getWorkerJwt ?? (async () => {
      const session = await getSupabaseSession();
      return session?.access_token ?? null;
    }),
  };
}
