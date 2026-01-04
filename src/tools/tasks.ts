import { insertTask, updateTask, searchTasks, getTask } from '../supabase.js';
import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult, CreateTaskInput, UpdateTaskInput, TaskSearchFilters } from '../types.js';

/**
 * Create a new development task
 */
export const createTask: RegisteredTool = {
  name: 'create_task',
  schema: {
    name: 'create_task',
    description: 'Create a new development task. Defaults to backlog unless user explicitly asks to do it now/immediately.',
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
          description: 'queued = do now (only if explicitly requested), upcoming = backlog (default)',
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
      required: ['title'],
    },
  },
  handler: async (input: CreateTaskInput, _context: ToolContext): Promise<ToolResult> => {
    const task = await insertTask({
      title: input.title,
      description: input.description || null,
      status: input.status || 'upcoming', // Default to backlog
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
          enum: ['queued', 'upcoming', 'in_progress', 'stuck', 'done', 'cancelled', 'needs_info'],
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
  handler: async (
    input: { task_id: string } & UpdateTaskInput,
    _context: ToolContext
  ): Promise<ToolResult> => {
    const updates: UpdateTaskInput = {};
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
    description:
      'Search for tasks by text query, status, or area. Returns matching tasks with their IDs.',
    input_schema: {
      type: 'object' as const,
      properties: {
        query: {
          type: 'string',
          description: 'Text to search for in title/description (optional)',
        },
        status: {
          type: 'string',
          enum: ['todo', 'backlog', 'in_progress', 'stuck', 'done', 'cancelled', 'needs_info'],
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
  handler: async (input: TaskSearchFilters, _context: ToolContext): Promise<ToolResult> => {
    const tasks = await searchTasks({
      query: input.query,
      status: input.status,
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
 * Provide additional information for a task that needs more context
 * Appends info to the task description and re-queues it for execution
 */
export const provideInfo: RegisteredTool = {
  name: 'provide_info',
  schema: {
    name: 'provide_info',
    description:
      'Provide additional information for a task that needs more context. Appends the info to the task and re-queues it for execution.',
    input_schema: {
      type: 'object' as const,
      properties: {
        task_id: {
          type: 'string',
          description: 'The UUID of the task to update',
        },
        info: {
          type: 'string',
          description: 'Additional information, clarification, or context to help complete the task',
        },
      },
      required: ['task_id', 'info'],
    },
  },
  handler: async (
    input: { task_id: string; info: string },
    _context: ToolContext
  ): Promise<ToolResult> => {
    // Get the current task to append to its description
    const currentTask = await getTask(input.task_id);

    // Only allow this on tasks in needs_info status
    if (currentTask.status !== 'needs_info') {
      return {
        success: false,
        action: 'provide_info',
        error: `Task is in '${currentTask.status}' status, not 'needs_info'. Use update_task to modify it instead.`,
      };
    }

    // Append the new info to the description (master source of truth)
    const updatedDescription = currentTask.description
      ? `${currentTask.description}\n\n---\n**Additional Info:**\n${input.info}`
      : `**Additional Info:**\n${input.info}`;

    // Append the new info to notes (conversation log)
    const timestamp = new Date().toISOString().split('T')[0];
    const infoEntry = `\n\n---\n**[${timestamp}] User provided info:**\n${input.info}`;
    const updatedNotes = (currentTask.notes || '') + infoEntry;

    // Update the task with new info and reset to 'todo' status
    const task = await updateTask(input.task_id, {
      description: updatedDescription,
      notes: updatedNotes,
      status: 'queued', // Maps to 'todo' in the DB
    });

    return {
      success: true,
      action: 'info_provided',
      task,
      message: `Added info and re-queued task for execution`,
    };
  },
};

/**
 * All task-related tools
 */
export const taskTools: RegisteredTool[] = [createTask, updateTaskTool, searchTasksTool, provideInfo];

