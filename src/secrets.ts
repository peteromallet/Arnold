import { config } from './config.js';
import type { ToolResult } from './types.js';

/**
 * Best-effort redaction of secret values from any text we might send to Discord.
 * This is defense-in-depth; we still avoid exposing secrets structurally.
 */
export function redactSecrets(text: string): string {
  let redacted = text;

  const secretValues: Array<string | null | undefined> = [
    config.discord.token,
    config.anthropic.apiKey,
    config.supabase.serviceRoleKey,
    config.github.token,
    config.runpod.apiKey,
    config.runpod.sshPrivateKey,
  ];

  for (const secret of secretValues) {
    if (secret && secret.length >= 8) {
      // Replace exact occurrences
      redacted = redacted.split(secret).join('[REDACTED]');
    }
  }

  // Common token patterns (best effort)
  redacted = redacted.replace(/sk-[a-zA-Z0-9]{20,}/g, '[REDACTED]');
  redacted = redacted.replace(/ghp_[a-zA-Z0-9]{36}/g, '[REDACTED]');
  redacted = redacted.replace(/gho_[a-zA-Z0-9]{36}/g, '[REDACTED]');
  redacted = redacted.replace(/github_pat_[a-zA-Z0-9_]{22,}/g, '[REDACTED]');

  // Supabase service role keys often look like long JWT-ish strings
  redacted = redacted.replace(/eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}/g, '[REDACTED]');

  return redacted;
}

function redactOptionalString(v: string | undefined): string | undefined {
  if (typeof v !== 'string') return v;
  return redactSecrets(v);
}

function redactNullableString(v: string | null): string | null {
  if (typeof v !== 'string') return v;
  return redactSecrets(v);
}

/**
 * Deep-ish sanitize of tool results before they are returned to the model and/or user.
 * Only targets string fields and common nested shapes used by Arnold.
 */
export function redactToolResult(result: ToolResult): ToolResult {
  const copy: ToolResult = { ...result };

  // Top-level common fields
  copy.message = redactOptionalString(copy.message);
  copy.error = redactOptionalString(copy.error);
  copy.stdout = redactOptionalString(copy.stdout);
  copy.stderr = redactOptionalString(copy.stderr);

  // Task payloads
  if (copy.task) {
    copy.task = { ...copy.task };
    copy.task.title = redactSecrets(copy.task.title);
    copy.task.description = redactNullableString(copy.task.description);
    copy.task.notes = redactNullableString(copy.task.notes);
  }

  if (Array.isArray(copy.tasks)) {
    copy.tasks = copy.tasks.map((t: unknown) => {
      if (!t || typeof t !== 'object') return t;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const task: any = { ...(t as any) };
      if (typeof task.title === 'string') task.title = redactSecrets(task.title);
      if (typeof task.description === 'string') task.description = redactSecrets(task.description);
      if (typeof task.notes === 'string') task.notes = redactSecrets(task.notes);
      return task;
    });
  }

  // RunPod tool sometimes returns arrays with error strings
  if (Array.isArray(copy.failed)) {
    copy.failed = copy.failed.map((f: unknown) => {
      if (!f || typeof f !== 'object') return f;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const fail: any = { ...(f as any) };
      if (typeof fail.error === 'string') fail.error = redactSecrets(fail.error);
      return fail;
    });
  }

  return copy;
}

