import type { SupabaseClient } from 'https://esm.sh/@supabase/supabase-js@2.49.4';
import { toErrorMessage } from '../_shared/errorMessage.ts';
import type {
  CompletionFollowUpIssue,
  MaterializedInputRecord,
  TaskContext,
} from './completionHelpers.ts';
import { cleanupFile } from './storage.ts';
import type { CompletionLogger } from './types.ts';

function isMaterializedInputRecord(value: unknown): value is MaterializedInputRecord {
  if (!value || typeof value !== 'object') return false;
  const r = value as Record<string, unknown>;
  return (
    typeof r.generation_id === 'string' &&
    (r.kind === 'file' || r.kind === 'remote') &&
    typeof r.target === 'string'
  );
}

export async function cleanupMaterializedInputs(
  supabaseAdmin: SupabaseClient,
  taskContext: TaskContext,
  logger?: CompletionLogger,
): Promise<CompletionFollowUpIssue[]> {
  const raw = taskContext.materialized_inputs;
  if (!raw || !Array.isArray(raw) || raw.length === 0) {
    return [];
  }

  const issues: CompletionFollowUpIssue[] = [];

  for (const record of raw) {
    if (!isMaterializedInputRecord(record)) {
      issues.push({
        step: 'materialized_input_cleanup',
        code: 'materialized_input_cleanup_failed',
        message: `Skipping malformed materialized_inputs entry: ${JSON.stringify(record)}`,
      });
      continue;
    }

    if (record.kind === 'file') {
      logger?.info(
        `[MaterializedInputCleanup] worker-side cleanup for path=${record.target}`,
        { generation_id: record.generation_id },
      );
      continue;
    }

    try {
      await cleanupFile(supabaseAdmin, record.target);
    } catch (error) {
      issues.push({
        step: 'materialized_input_cleanup',
        code: 'materialized_input_cleanup_failed',
        message: `Failed to remove materialized remote target ${record.target}: ${toErrorMessage(error)}`,
      });
    }
  }

  return issues;
}
