import { defineConfig } from 'vitest/config';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createEdgeVitestTestConfig } from './vitest.edge.shared';
import { buildEdgeAliasMap } from './vitest.edge.aliases';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const EDGE_UNIT_INCLUDE = [
  'supabase/functions/_shared/**/*.test.ts',
  'supabase/functions/ai-generate-effect/**/*.test.ts',
  'supabase/functions/ai-prompt/**/*.test.ts',
  'supabase/functions/ai-timeline-agent/**/*.test.ts',
  'supabase/functions/ai-voice-prompt/**/*.test.ts',
  'supabase/functions/broadcast-realtime/**/*.test.ts',
  'supabase/functions/calculate-task-cost/**/*.test.ts',
  'supabase/functions/claim-next-task/**/*.test.ts',
  'supabase/functions/complete-auto-topup-setup/**/*.test.ts',
  'supabase/functions/create-task/**/*.test.ts',
  'supabase/functions/delete-project/**/*.test.ts',
  'supabase/functions/discord-daily-stats/**/*.test.ts',
  'supabase/functions/generate-pat/**/*.test.ts',
  'supabase/functions/generate-thumbnail/**/*.test.ts',
  'supabase/functions/generate-upload-url/**/*.test.ts',
  'supabase/functions/get-completed-segments/**/*.test.ts',
  'supabase/functions/get-task-output/**/*.test.ts',
  'supabase/functions/get-task-status/**/*.test.ts',
  'supabase/functions/get-orchestrator-children/**/*.test.ts',
  'supabase/functions/get-predecessor-output/**/*.test.ts',
  'supabase/functions/huggingface-upload/**/*.test.ts',
  'supabase/functions/process-auto-topup/**/*.test.ts',
  'supabase/functions/reigh-data-fetch/**/*.test.ts',
  'supabase/functions/revoke-pat/**/*.test.ts',
  'supabase/functions/setup-auto-topup/**/*.test.ts',
  'supabase/functions/grant-credits/**/*.test.ts',
  'supabase/functions/task-counts/**/*.test.ts',
  'supabase/functions/trim-video/**/*.test.ts',
  'supabase/functions/update-shot-pair-prompts/**/*.test.ts',
  'supabase/functions/complete_task/**/*.test.ts',
  'supabase/functions/tasks-list/**/*.test.ts',
  'supabase/functions/update-task-status/*.test.ts',
  'supabase/functions/stripe-checkout/**/*.test.ts',
  'supabase/functions/stripe-webhook/**/*.test.ts',
  'supabase/functions/trigger-auto-topup/**/*.test.ts',
  'supabase/functions/update-worker-model/**/*.test.ts',
] as const;

const EDGE_UNIT_EXCLUDE = [
  'supabase/functions/_tests/**/*.test.ts',
  'supabase/functions/complete_task/index.test.ts',
  'supabase/functions/update-task-status/index.test.ts',
  'supabase/functions/**/node_modules/**',
] as const;

const MOCKS_DIR = path.resolve(__dirname, '../../supabase/functions/_tests/mocks');
const STRIPE_ESM_SPECIFIER = 'https:' + '//esm.sh/stripe@14.21.0';
const GROQ_NPM_SPECIFIER = 'npm' + ':groq-sdk@0.26.0';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '../../src'),
      ...buildEdgeAliasMap(MOCKS_DIR),
      [STRIPE_ESM_SPECIFIER]: path.resolve(
        MOCKS_DIR,
        'stripe.ts',
      ),
      [GROQ_NPM_SPECIFIER]: path.resolve(
        MOCKS_DIR,
        'groqSdk.ts',
      ),
    },
  },
  test: createEdgeVitestTestConfig({
    include: EDGE_UNIT_INCLUDE,
    exclude: EDGE_UNIT_EXCLUDE,
  }),
});
