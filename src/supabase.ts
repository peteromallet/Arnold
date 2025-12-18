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
 * Update task status with optional notes and commit hash
 * Used by executor when completing tasks
 */
export async function updateTaskStatus(
  taskId: string,
  status: TaskStatus,
  notes?: string | null,
  commitHash?: string | null,
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

  const { error } = await supabase.from('dev_tasks').update(updates).eq('id', taskId);

  if (error) {
    logger.error('Failed to update task status', error, { taskId, status });
    throw new ExternalServiceError('supabase', `Failed to update task status: ${error.message}`);
  }

  logger.info('Task status updated', { taskId, status });
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
