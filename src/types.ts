/**
 * Task status values as stored in the database
 */
export type TaskStatus = 'backlog' | 'todo' | 'in_progress' | 'stuck' | 'done' | 'cancelled';

/**
 * User-friendly status aliases (mapped to TaskStatus in supabase.ts)
 */
export type UserStatus = 'queued' | 'upcoming' | TaskStatus;

/**
 * Task area categories
 */
export type TaskArea = 'ui' | 'api' | 'backend' | 'frontend' | 'database' | 'tools' | 'docs' | 'infra' | string;

/**
 * Execution details from Claude Code
 */
export interface ExecutionDetails {
  num_turns?: number;
  total_cost_usd?: number;
  duration_ms?: number;
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
    cache_creation_input_tokens?: number;
    cache_read_input_tokens?: number;
  };
}

/**
 * A development task from the dev_tasks table
 */
export interface Task {
  id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  area: TaskArea | null;
  notes: string | null;
  commit_hash: string | null;
  execution_details: ExecutionDetails | null;
  created_at: string;
  completed_at: string | null;
}

/**
 * Input for creating a new task
 */
export interface CreateTaskInput {
  title: string;
  description?: string | null;
  status?: UserStatus;
  area?: TaskArea | null;
  notes?: string | null;
}

/**
 * Input for updating an existing task
 */
export interface UpdateTaskInput {
  title?: string;
  description?: string;
  status?: UserStatus;
  area?: string;
  notes?: string;
}

/**
 * Search filters for tasks
 */
export interface TaskSearchFilters {
  query?: string;
  status?: UserStatus;
  area?: string;
  limit?: number;
}

/**
 * Executor state
 */
export interface ExecutorState {
  running: boolean;
  currentTask: {
    id: string;
    title: string;
  } | null;
}

/**
 * Result from executor operations
 */
export interface ExecutorResult {
  success: boolean;
  message: string;
}

/**
 * Result from Claude Code execution
 */
export interface ClaudeCodeResult {
  success: boolean;
  devNotes?: string | null;
  error?: string;
  isSystemError?: boolean;
  /** Full execution details from Claude Code */
  executionDetails?: ExecutionDetails;
  /** If task was flagged as potentially harmful, the reason */
  flaggedReason?: string | null;
}

/**
 * Result from git push operation
 */
export interface GitPushResult {
  success: boolean;
  message: string;
  commitHash?: string;
  shortHash?: string;
  commitMessage?: string;
  commitUrl?: string;
  branch?: string;
}

/**
 * Tool execution result - standardized shape for all tools
 */
export interface ToolResult {
  success: boolean;
  action: string;
  error?: string;
  // Tool-specific fields
  task?: Task;
  tasks?: Task[];
  count?: number;
  message?: string;
  updatedFields?: string[];
  running?: boolean;
  currentTask?: { id: string; title: string } | null;
}

/**
 * A recorded action from tool execution
 */
export interface ToolAction {
  tool: string;
  input: Record<string, unknown>;
  result: ToolResult;
}

/**
 * Result from parseTask
 */
export interface ParseTaskResult {
  actions: ToolAction[];
  reply: string | null;
}

/**
 * Callback for sending notifications
 */
export type NotifyCallback = (message: string) => void;

/**
 * Conversation message for context
 */
export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
}
