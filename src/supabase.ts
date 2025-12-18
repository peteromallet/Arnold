import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { config } from './config.js';
import { logger } from './logger.js';
import { ExternalServiceError, TaskNotFoundError } from './errors.js';
import type {
  Task,
  TaskStatus,
  UserStatus,
  CreateTaskInput,
  UpdateTaskInput,
  TaskSearchFilters,
} from './types.js';

/**
 * Map user-friendly status to database status
 */
function mapStatusToDb(status: UserStatus): TaskStatus {
  const statusMap: Record<string, TaskStatus> = {
    queued: 'todo',
    upcoming: 'backlog',
  };
  return (statusMap[status] as TaskStatus) || (status as TaskStatus);
}

/**
 * Supabase client instance
 */
export const supabase: SupabaseClient = createClient(
  config.supabase.url,
  config.supabase.serviceRoleKey,
);

/**
 * Insert a new task into the dev_tasks table
 */
export async function insertTask(input: CreateTaskInput): Promise<Task> {
  const dbStatus = mapStatusToDb(input.status || 'backlog');

  const { data, error } = await supabase
    .from('dev_tasks')
    .insert({
      title: input.title,
      description: input.description || null,
      status: dbStatus,
      area: input.area || null,
      notes: input.notes || null,
    })
    .select()
    .single();

  if (error) {
    logger.error('Failed to insert task', error, { title: input.title });
    throw new ExternalServiceError('supabase', `Failed to insert task: ${error.message}`);
  }

  logger.info('Task created', { taskId: data.id, title: data.title, status: data.status });
  return data as Task;
}

/**
 * Get recent tasks from the database
 */
export async function getRecentTasks(limit: number = 10): Promise<Task[]> {
  const { data, error } = await supabase
    .from('dev_tasks')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(limit);

  if (error) {
    logger.error('Failed to fetch recent tasks', error);
    throw new ExternalServiceError('supabase', `Failed to fetch tasks: ${error.message}`);
  }

  return data as Task[];
}

/**
 * Update an existing task by ID
 */
export async function updateTask(taskId: string, updates: UpdateTaskInput): Promise<Task> {
  // Map status if provided
  const dbUpdates: Record<string, unknown> = { ...updates };
  if (updates.status) {
    dbUpdates.status = mapStatusToDb(updates.status);
  }

  const { data, error } = await supabase
    .from('dev_tasks')
    .update(dbUpdates)
    .eq('id', taskId)
    .select()
    .single();

  if (error) {
    if (error.code === 'PGRST116') {
      throw new TaskNotFoundError(taskId);
    }
    logger.error('Failed to update task', error, { taskId });
    throw new ExternalServiceError('supabase', `Failed to update task: ${error.message}`);
  }

  logger.info('Task updated', { taskId, updates: Object.keys(updates) });
  return data as Task;
}

/**
 * Get a task by ID
 */
export async function getTask(taskId: string): Promise<Task> {
  const { data, error } = await supabase
    .from('dev_tasks')
    .select('*')
    .eq('id', taskId)
    .single();

  if (error) {
    if (error.code === 'PGRST116') {
      throw new TaskNotFoundError(taskId);
    }
    logger.error('Failed to get task', error, { taskId });
    throw new ExternalServiceError('supabase', `Failed to get task: ${error.message}`);
  }

  return data as Task;
}

/**
 * Search tasks by various criteria
 */
export async function searchTasks(filters: TaskSearchFilters): Promise<Task[]> {
  let query = supabase.from('dev_tasks').select('*');

  // Filter by status if provided
  if (filters.status) {
    const dbStatus = mapStatusToDb(filters.status);
    query = query.eq('status', dbStatus);
  }

  // Filter by area if provided
  if (filters.area) {
    query = query.eq('area', filters.area);
  }

  // Text search on title and description if query provided
  if (filters.query) {
    query = query.or(`title.ilike.%${filters.query}%,description.ilike.%${filters.query}%`);
  }

  const { data, error } = await query
    .order('created_at', { ascending: false })
    .limit(filters.limit || 10);

  if (error) {
    logger.error('Failed to search tasks', error, { filters });
    throw new ExternalServiceError('supabase', `Failed to search tasks: ${error.message}`);
  }

  logger.debug('Task search completed', { filters, count: data.length });
  return data as Task[];
}

/**
 * Update task status with optional notes, commit hash, and execution details
 * Used by executor when completing tasks
 */
export async function updateTaskStatus(
  taskId: string,
  status: TaskStatus,
  notes?: string | null,
  commitHash?: string | null,
  executionDetails?: object | null,
): Promise<void> {
  const updates: Record<string, unknown> = { status };

  if (status === 'done') {
    updates.completed_at = new Date().toISOString();
  }

  if (notes !== undefined) {
    updates.notes = notes;
  }

  if (commitHash !== undefined) {
    updates.commit_hash = commitHash;
  }

  if (executionDetails !== undefined && executionDetails !== null) {
    updates.execution_details = executionDetails;
  }

  const { error } = await supabase.from('dev_tasks').update(updates).eq('id', taskId);

  if (error) {
    logger.error('Failed to update task status', error, { taskId, status });
    throw new ExternalServiceError('supabase', `Failed to update task status: ${error.message}`);
  }

  logger.info('Task status updated', { taskId, status, hasCostData: !!executionDetails });
}

/**
 * Get the oldest task with 'todo' status
 */
export async function getNextTodoTask(): Promise<Task | null> {
  const { data, error } = await supabase
    .from('dev_tasks')
    .select('*')
    .eq('status', 'todo')
    .order('created_at', { ascending: true })
    .limit(1);

  if (error) {
    logger.error('Failed to get next todo task', error);
    throw new ExternalServiceError('supabase', `Failed to get next task: ${error.message}`);
  }

  return data.length > 0 ? (data[0] as Task) : null;
}

/**
 * Reset all in_progress tasks back to todo
 * Used on executor startup to handle interrupted tasks
 */
export async function resetInProgressTasks(): Promise<number> {
  const { data, error } = await supabase
    .from('dev_tasks')
    .update({ status: 'todo' })
    .eq('status', 'in_progress')
    .select();

  if (error) {
    logger.error('Failed to reset in_progress tasks', error);
    throw new ExternalServiceError('supabase', `Failed to reset tasks: ${error.message}`);
  }

  const count = data?.length || 0;
  if (count > 0) {
    logger.info('Reset in_progress tasks', { count });
  }
  return count;
}

/**
 * Usage statistics result
 */
export interface UsageStats {
  period: string;
  startDate: string;
  endDate: string;
  totalTasks: number;
  completedTasks: number;
  stuckTasks: number;
  totalCostUsd: number;
  totalTokens: number;
  avgCostPerTask: number;
  avgTokensPerTask: number;
  tasksByStatus: Record<string, number>;
  tasksByArea: Record<string, number>;
}

/**
 * Get usage statistics for a time period
 */
export async function getUsageStats(
  period: 'today' | 'yesterday' | 'week' | 'month' | 'all',
  customStartDate?: string,
  customEndDate?: string,
): Promise<UsageStats> {
  // Calculate date range based on period
  const now = new Date();
  let startDate: Date;
  let endDate: Date = now;
  let periodLabel: string = period;

  switch (period) {
    case 'today':
      startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      break;
    case 'yesterday':
      startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
      endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      break;
    case 'week':
      startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      periodLabel = 'Last 7 days';
      break;
    case 'month':
      startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      periodLabel = 'Last 30 days';
      break;
    case 'all':
      startDate = new Date(0); // Beginning of time
      periodLabel = 'All time';
      break;
    default:
      startDate = customStartDate ? new Date(customStartDate) : new Date(0);
      endDate = customEndDate ? new Date(customEndDate) : now;
      periodLabel = `${startDate.toISOString().split('T')[0]} to ${endDate.toISOString().split('T')[0]}`;
  }

  // Query tasks in the date range
  let query = supabase.from('dev_tasks').select('*');

  if (period !== 'all') {
    query = query
      .gte('created_at', startDate.toISOString())
      .lt('created_at', endDate.toISOString());
  }

  const { data: tasks, error } = await query;

  if (error) {
    logger.error('Failed to get usage stats', error);
    throw new ExternalServiceError('supabase', `Failed to get usage stats: ${error.message}`);
  }

  // Calculate aggregates
  let totalCostUsd = 0;
  let totalTokens = 0;
  const tasksByStatus: Record<string, number> = {};
  const tasksByArea: Record<string, number> = {};

  for (const task of tasks || []) {
    // Count by status
    tasksByStatus[task.status] = (tasksByStatus[task.status] || 0) + 1;

    // Count by area
    const area = task.area || 'unspecified';
    tasksByArea[area] = (tasksByArea[area] || 0) + 1;

    // Sum execution details if available
    if (task.execution_details) {
      const details = task.execution_details as { total_cost_usd?: number; usage?: { input_tokens?: number; output_tokens?: number; cache_creation_input_tokens?: number; cache_read_input_tokens?: number } };
      totalCostUsd += details.total_cost_usd || 0;
      
      if (details.usage) {
        totalTokens += details.usage.input_tokens || 0;
        totalTokens += details.usage.output_tokens || 0;
        totalTokens += details.usage.cache_creation_input_tokens || 0;
        totalTokens += details.usage.cache_read_input_tokens || 0;
      }
    }
  }

  const totalTasks = tasks?.length || 0;
  const completedTasks = tasksByStatus['done'] || 0;
  const stuckTasks = tasksByStatus['stuck'] || 0;

  return {
    period: periodLabel,
    startDate: startDate.toISOString(),
    endDate: endDate.toISOString(),
    totalTasks,
    completedTasks,
    stuckTasks,
    totalCostUsd,
    totalTokens,
    avgCostPerTask: totalTasks > 0 ? totalCostUsd / totalTasks : 0,
    avgTokensPerTask: totalTasks > 0 ? totalTokens / totalTasks : 0,
    tasksByStatus,
    tasksByArea,
  };
}
