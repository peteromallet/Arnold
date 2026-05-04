import { defineConfig } from 'vitest/config';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildEdgeAliasMap } from '../../config/testing/vitest.edge.aliases';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const EDGE_UNIT_INCLUDE = [
  'supabase/functions/*.test.ts',
  'supabase/functions/_shared/**/*.test.ts',
  'supabase/functions/create-task/**/*.test.ts',
  'supabase/functions/calculate-task-cost/**/*.test.ts',
  'supabase/functions/complete_task/**/*.test.ts',
  'supabase/functions/get-task-output/**/*.test.ts',
  'supabase/functions/tasks-list/**/*.test.ts',
  'supabase/functions/update-task-status/*.test.ts',
  'supabase/functions/get-orchestrator-children/**/*.test.ts',
  'supabase/functions/get-predecessor-output/**/*.test.ts',
  'supabase/functions/stripe-checkout/**/*.test.ts',
  'supabase/functions/stripe-webhook/**/*.test.ts',
  'supabase/functions/trigger-auto-topup/**/*.test.ts',
  'supabase/functions/update-worker-model/**/*.test.ts',
  'supabase/functions/huggingface-upload/**/*.test.ts',
  'supabase/functions/timeline-import/**/*.test.ts',
  'supabase/functions/task-status/**/*.test.ts',
] as const;

export const EDGE_UNIT_EXCLUDE = [
  'supabase/functions/_tests/**/*.test.ts',
  'supabase/functions/complete_task/index.test.ts',
  'supabase/functions/update-task-status/index.test.ts',
  'supabase/functions/**/node_modules/**',
] as const;

const MOCKS_DIR = path.resolve(__dirname, '_tests/mocks');

export default defineConfig({
  resolve: {
    alias: {
      ...buildEdgeAliasMap(MOCKS_DIR),
    },
  },
  test: {
    environment: 'node',
    include: [...EDGE_UNIT_INCLUDE],
    exclude: [...EDGE_UNIT_EXCLUDE],
    globals: true,
    sequence: {
      concurrent: false,
    },
    testTimeout: 30_000,
    hookTimeout: 180_000,
  },
});
