import 'dotenv/config';

/**
 * Get a required environment variable or throw
 */
function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

/**
 * Get an optional environment variable with a default
 */
function optionalEnv(name: string, defaultValue: string): string {
  return process.env[name] || defaultValue;
}

/**
 * Validated configuration - fails fast on missing required vars
 */
export const config = {
  /** Node environment */
  nodeEnv: optionalEnv('NODE_ENV', 'development'),
  
  /** Is production environment */
  isProd: process.env.NODE_ENV === 'production',
  
  discord: {
    /** Discord bot token (required) */
    token: requireEnv('DISCORD_TOKEN'),
    /** Restrict commands to this user ID (optional) */
    allowedUserId: process.env.DISCORD_USER_ID || null,
    /** Command prefix for non-DM messages */
    prefix: '!task',
  },
  
  anthropic: {
    /** Anthropic API key (required) */
    apiKey: requireEnv('ANTHROPIC_API_KEY'),
    /** Model to use for task parsing */
    model: 'claude-sonnet-4-5-20250929',
  },
  
  supabase: {
    /** Supabase project URL (required) */
    url: process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL || '',
    /** Supabase service role key (required) */
    serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY || '',
  },
  
  groq: {
    /** Groq API key for voice transcription (optional) */
    apiKey: process.env.GROQ_API_KEY || null,
  },
  
  github: {
    /** GitHub personal access token (optional, needed for push) */
    token: process.env.GITHUB_API_KEY || null,
    /** Repository owner */
    repoOwner: optionalEnv('GITHUB_REPO_OWNER', 'peteromallet'),
    /** Repository name */
    repoName: optionalEnv('GITHUB_REPO_NAME', 'Reigh'),
    /** Branch to work on */
    repoBranch: optionalEnv('GITHUB_REPO_BRANCH', 'main'),
  },
  
  executor: {
    /** Workspace directory for cloning repos */
    workspaceDir: optionalEnv('WORKSPACE_DIR', '/tmp/workspace'),
    /** Path to claude CLI */
    claudePath: optionalEnv('CLAUDE_PATH', 'claude'),
    /** Git user name for commits */
    gitUserName: optionalEnv('GIT_USER_NAME', 'Arnold Bot'),
    /** Git user email for commits */
    gitUserEmail: optionalEnv('GIT_USER_EMAIL', 'bot@example.com'),
    /** Polling interval in ms */
    pollIntervalMs: 10_000,
    /** Task execution timeout in ms */
    taskTimeoutMs: 10 * 60 * 1000, // 10 minutes
    /** Graceful shutdown timeout in ms */
    shutdownTimeoutMs: 30_000,
  },
  
  runpod: {
    /** RunPod API key (optional, needed for GPU instance management) */
    apiKey: process.env.RUNPOD_API_KEY || null,
    /** Prefix for Arnold-created pods (for identification/cleanup) */
    podPrefix: optionalEnv('RUNPOD_POD_PREFIX', 'arnold_'),
    /** Default GPU type */
    gpuType: optionalEnv('RUNPOD_GPU_TYPE', 'NVIDIA GeForce RTX 4090'),
    /** Default Docker image */
    image: optionalEnv('RUNPOD_IMAGE', 'runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04'),
    /** Disk size in GB */
    diskSizeGb: parseInt(optionalEnv('RUNPOD_DISK_SIZE_GB', '50')),
    /** Container disk size in GB */
    containerDiskGb: parseInt(optionalEnv('RUNPOD_CONTAINER_DISK_GB', '50')),
  },
} as const;

// Validate Supabase config separately (allows either naming convention)
if (!config.supabase.url || !config.supabase.serviceRoleKey) {
  console.error('Missing Supabase configuration:');
  console.error('  - SUPABASE_URL (or VITE_SUPABASE_URL):', config.supabase.url ? '✓' : '✗');
  console.error('  - SUPABASE_SERVICE_ROLE_KEY:', config.supabase.serviceRoleKey ? '✓' : '✗');
  throw new Error('Missing Supabase configuration');
}

export type Config = typeof config;
