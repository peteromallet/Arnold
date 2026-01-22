import { spawn } from 'child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'fs';
import os from 'os';
import path from 'path';
import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult } from '../types.js';
import { redactSecrets } from '../secrets.js';

const DEFAULT_TIMEOUT_MS = 10_000;
const MAX_OUTPUT_CHARS = 20_000;

function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return text.slice(0, maxChars) + `\n[truncated to ${maxChars} chars]`;
}

function minimalEnv(): NodeJS.ProcessEnv {
  // Intentionally do NOT pass through secrets from process.env.
  // Keep only what's needed to run `node` reliably.
  return {
    PATH: process.env.PATH || '',
    HOME: process.env.HOME || '',
    TMPDIR: process.env.TMPDIR || '',
    TEMP: process.env.TEMP || '',
    TMP: process.env.TMP || '',
    NODE_ENV: process.env.NODE_ENV || '',
  };
}

/**
 * Execute a JavaScript snippet with Node, capturing stdout/stderr.
 * Note: this executes locally where the bot runs; it is intentionally restricted to the bot owner.
 */
export const runCodeTool: RegisteredTool = {
  name: 'run_code',
  schema: {
    name: 'run_code',
    description:
      'Execute a short JavaScript snippet using Node.js and return stdout/stderr + exit code. Owner-only.',
    input_schema: {
      type: 'object' as const,
      properties: {
        code: {
          type: 'string',
          description: 'JavaScript code to run (executed with `node`)',
        },
        timeout_ms: {
          type: 'number',
          description: `Execution timeout in milliseconds (default ${DEFAULT_TIMEOUT_MS})`,
        },
      },
      required: ['code'],
    },
  },
  handler: async (
    input: { code: string; timeout_ms?: number },
    _context: ToolContext,
  ): Promise<ToolResult> => {
    const major = parseInt(process.versions.node.split('.')[0] || '0', 10);
    if (!Number.isFinite(major) || major < 20) {
      return {
        success: false,
        action: 'run_code',
        error:
          `Refusing to execute code: Node ${process.versions.node} does not support the permission sandbox we require (need Node >= 20).`,
      };
    }

    const started = Date.now();
    const timeoutMs =
      typeof input.timeout_ms === 'number' && Number.isFinite(input.timeout_ms) && input.timeout_ms > 0
        ? Math.floor(input.timeout_ms)
        : DEFAULT_TIMEOUT_MS;

    // Write to a temp file so stack traces include line numbers.
    const dir = mkdtempSync(path.join(os.tmpdir(), 'arnold-run-'));
    const file = path.join(dir, 'snippet.js');
    writeFileSync(file, input.code, { encoding: 'utf-8' });

    return await new Promise<ToolResult>((resolve) => {
      // Run with Node permissions:
      // - Only allow fs read/write within the temp dir
      // - Do NOT allow network
      // - Do NOT allow child_process
      const nodeArgs = [
        '--experimental-permission',
        `--allow-fs-read=${dir}`,
        `--allow-fs-write=${dir}`,
        file,
      ];

      const proc = spawn('node', nodeArgs, {
        cwd: dir,
        env: minimalEnv(),
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';
      let timedOut = false;

      const killTimer = setTimeout(() => {
        timedOut = true;
        proc.kill('SIGKILL');
      }, timeoutMs);

      proc.stdout.on('data', (d: Buffer) => {
        stdout += d.toString();
        if (stdout.length > MAX_OUTPUT_CHARS * 2) {
          stdout = stdout.slice(0, MAX_OUTPUT_CHARS * 2);
        }
      });

      proc.stderr.on('data', (d: Buffer) => {
        stderr += d.toString();
        if (stderr.length > MAX_OUTPUT_CHARS * 2) {
          stderr = stderr.slice(0, MAX_OUTPUT_CHARS * 2);
        }
      });

      proc.on('close', (code: number | null) => {
        clearTimeout(killTimer);
        const durationMs = Date.now() - started;

        try {
          rmSync(dir, { recursive: true, force: true });
        } catch {
          // ignore
        }

        const out = redactSecrets(truncate(stdout, MAX_OUTPUT_CHARS));
        const err = redactSecrets(truncate(stderr, MAX_OUTPUT_CHARS));

        // If the permission flags aren't supported for some reason, refuse (don't fall back to unsafe execution).
        const sandboxUnsupported =
          (code !== 0) &&
          (err.includes('bad option') ||
            err.includes('unknown option') ||
            err.includes('experimental-permission') ||
            err.includes('not allowed') && err.includes('permission'));

        if (sandboxUnsupported) {
          resolve({
            success: false,
            action: 'run_code',
            error:
              'Refusing to execute code: Node permission sandbox is not available/working in this runtime.',
            stdout: out,
            stderr: err,
            exit_code: code,
            timed_out: false,
            duration_ms: durationMs,
          });
          return;
        }

        resolve({
          success: !timedOut && code === 0,
          action: 'run_code',
          stdout: out,
          stderr: err,
          exit_code: code,
          timed_out: timedOut,
          duration_ms: durationMs,
          message: timedOut
            ? `Timed out after ${timeoutMs}ms`
            : code === 0
              ? 'Executed successfully'
              : `Exited with code ${code}`,
        });
      });

      proc.on('error', (err: Error) => {
        clearTimeout(killTimer);
        const durationMs = Date.now() - started;

        try {
          rmSync(dir, { recursive: true, force: true });
        } catch {
          // ignore
        }

        resolve({
          success: false,
          action: 'run_code',
          error: redactSecrets(err.message),
          stdout: redactSecrets(truncate(stdout, MAX_OUTPUT_CHARS)),
          stderr: redactSecrets(truncate(stderr, MAX_OUTPUT_CHARS)),
          exit_code: null,
          timed_out: false,
          duration_ms: durationMs,
        });
      });
    });
  },
};

const CONFIGURED_KEY_NAMES = [
  'NODE_ENV',
  'DISCORD_TOKEN',
  'DISCORD_USER_ID',
  'ANTHROPIC_API_KEY',
  'SUPABASE_URL',
  'VITE_SUPABASE_URL',
  'SUPABASE_SERVICE_ROLE_KEY',
  'GROQ_API_KEY',
  'GITHUB_API_KEY',
  'GITHUB_REPO_OWNER',
  'GITHUB_REPO_NAME',
  'GITHUB_REPO_BRANCH',
  'WORKSPACE_DIR',
  'CLAUDE_PATH',
  'GIT_USER_NAME',
  'GIT_USER_EMAIL',
  'RUNPOD_API_KEY',
  'RUNPOD_POD_PREFIX',
  'RUNPOD_GPU_TYPE',
  'RUNPOD_IMAGE',
  'RUNPOD_TEMPLATE_ID',
  'RUNPOD_ALLOWED_CUDA_VERSIONS',
  'RUNPOD_DISK_SIZE_GB',
  'RUNPOD_CONTAINER_DISK_GB',
  'RUNPOD_STORAGE_VOLUMES',
  'RUNPOD_VOLUME_MOUNT_PATH',
  'RUNPOD_SSH_PUBLIC_KEY',
  'RUNPOD_SSH_PRIVATE_KEY',
  'RUNPOD_ANTHROPIC_API_KEY',
] as const;

export const listKeyNamesTool: RegisteredTool = {
  name: 'list_key_names',
  schema: {
    name: 'list_key_names',
    description:
      'List the names of the environment keys Arnold is configured to use. Returns names only (no values). Owner-only.',
    input_schema: {
      type: 'object' as const,
      properties: {},
    },
  },
  handler: async (_input: Record<string, never>, _context: ToolContext): Promise<ToolResult> => {
    const keyStatus: Record<string, boolean> = {};
    for (const k of CONFIGURED_KEY_NAMES) {
      keyStatus[k] = !!process.env[k];
    }

    return {
      success: true,
      action: 'list_key_names',
      keys: [...CONFIGURED_KEY_NAMES],
      key_status: keyStatus,
      message: `Keys (${CONFIGURED_KEY_NAMES.length}): ${CONFIGURED_KEY_NAMES.join(', ')}`,
    };
  },
};

export const codeTools: RegisteredTool[] = [runCodeTool, listKeyNamesTool];

