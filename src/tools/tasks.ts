import { insertTask, updateTask, searchTasks } from '../supabase.js';
import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult } from '../types.js';

/**
 * Input for create_task tool
 */
interface CreateTaskInput {
  title: string;
  description?: string;
  status?: 'queued' | 'upcoming';
  area?: string;
  notes?: string;
}

/**
 * Input for update_task tool
 */
interface UpdateTaskInput {
  task_id: string;
  title?: string;
  description?: string;
  status?: string;
  area?: string;
  notes?: string;
}

/**
 * Input for search_tasks tool
 */
interface SearchTasksInput {
  query?: string;
  status?: string;
  area?: string;
  limit?: number;
}

/**
 * Create a new development task
 */
export const createTask: RegisteredTool = {
  name: 'create_task',
  schema: {
    name: 'create_task',
    description: 'Create a new development task',
    input_schema: {
      type: 'object' as const,
      properties: {
        title: {
          type: 'string',
          description: 'Concise, actionable task title',
        },
        description: {
          type: 'string',
          description: 'More detailed description (optional)',
        },
        status: {
          type: 'string',
          enum: ['queued', 'upcoming'],
          description: 'queued = do now, upcoming = for later',
        },
        area: {
          type: 'string',
          description: 'Category: ui, api, backend, frontend, database, tools, docs, infra, etc.',
        },
        notes: {
          type: 'string',
          description: 'Any additional context or notes',
        },
      },
      required: ['title', 'status'],
    },
  },
  handler: async (input: CreateTaskInput, _context: ToolContext): Promise<ToolResult> => {
    const task = await insertTask({
      title: input.title,
      description: input.description || null,
      status: input.status || 'upcoming',
      area: input.area || null,
      notes: input.notes || null,
    });
    return {
      success: true,
      action: 'created',
      task,
    };
  },
};

/**
 * Update an existing task by ID
 */
export const updateTaskTool: RegisteredTool = {
  name: 'update_task',
  schema: {
    name: 'update_task',
    description: 'Update an existing task by ID.',
    input_schema: {
      type: 'object' as const,
      properties: {
        task_id: {
          type: 'string',
          description: 'The UUID of the task to update',
        },
        title: {
          type: 'string',
          description: 'New title (optional)',
        },
        description: {
          type: 'string',
          description: 'New description (optional)',
        },
        status: {
          type: 'string',
          enum: ['queued', 'upcoming', 'in_progress', 'stuck', 'done', 'cancelled'],
          description: 'New status (optional)',
        },
        area: {
          type: 'string',
          description: 'New area (optional)',
        },
        notes: {
          type: 'string',
          description: 'New notes (optional)',
        },
      },
      required: ['task_id'],
    },
  },
  handler: async (input: UpdateTaskInput, _context: ToolContext): Promise<ToolResult> => {
    const updates: Record<string, string> = {};
    if (input.title) updates.title = input.title;
    if (input.description) updates.description = input.description;
    if (input.status) updates.status = input.status;
    if (input.area) updates.area = input.area;
    if (input.notes) updates.notes = input.notes;

    const task = await updateTask(input.task_id, updates);
    return {
      success: true,
      action: 'updated',
      task,
      updatedFields: Object.keys(updates),
    };
  },
};

/**
 * Search for tasks by text query, status, or area
 */
export const searchTasksTool: RegisteredTool = {
  name: 'search_tasks',
  schema: {
    name: 'search_tasks',
    description: 'Search for tasks by text query, status, or area. Returns matching tasks with their IDs.',
    input_schema: {
      type: 'object' as const,
      properties: {
        query: {
          type: 'string',
          description: 'Text to search for in title/description (optional)',
        },
        status: {
          type: 'string',
          enum: ['todo', 'backlog', 'in_progress', 'stuck', 'done', 'cancelled'],
          description: 'Filter by status (optional)',
        },
        area: {
          type: 'string',
          description: 'Filter by area (optional)',
        },
        limit: {
          type: 'number',
          description: 'Max results to return (default 10)',
        },
      },
    },
  },
  handler: async (input: SearchTasksInput, _context: ToolContext): Promise<ToolResult> => {
    const tasks = await searchTasks({
      query: input.query,
      status: input.status as any,
      area: input.area,
      limit: input.limit || 10,
    });
    return {
      success: true,
      action: 'searched',
      tasks,
      count: tasks.length,
    };
  },
};

/**
 * All task-related tools
 */
export const taskTools: RegisteredTool[] = [createTask, updateTaskTool, searchTasksTool];
