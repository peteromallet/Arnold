import { getUsageStats } from '../supabase.js';
import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult } from '../types.js';

/**
 * Input for get_usage_stats tool
 */
interface GetUsageStatsInput {
  period: 'today' | 'yesterday' | 'week' | 'month' | 'all';
  start_date?: string;
  end_date?: string;
}

/**
 * Get usage statistics for a time period
 */
export const getUsageStatsTool: RegisteredTool = {
  name: 'get_usage_stats',
  schema: {
    name: 'get_usage_stats',
    description: 'Get a report of task execution statistics including cost, tokens, and task counts for a time period. Use this when the user asks about spending, costs, usage, or wants a summary of work done.',
    input_schema: {
      type: 'object' as const,
      properties: {
        period: {
          type: 'string',
          enum: ['today', 'yesterday', 'week', 'month', 'all'],
          description: 'Preset time period. Use "today" for current day, "week" for last 7 days, "month" for last 30 days.',
        },
        start_date: {
          type: 'string',
          description: 'Custom start date (ISO format, e.g., "2025-01-01"). Only used if period is not specified.',
        },
        end_date: {
          type: 'string',
          description: 'Custom end date (ISO format). Defaults to now if not specified.',
        },
      },
      required: ['period'],
    },
  },
  handler: async (input: GetUsageStatsInput, _context: ToolContext): Promise<ToolResult> => {
    const stats = await getUsageStats(input.period, input.start_date, input.end_date);
    
    return {
      success: true,
      action: 'get_usage_stats',
      message: formatStatsReport(stats, input.period),
      ...stats,
    };
  },
};

/**
 * Format stats into a human-readable report
 */
function formatStatsReport(
  stats: {
    period: string;
    totalTasks: number;
    completedTasks: number;
    stuckTasks: number;
    totalCostUsd: number;
    totalTokens: number;
    avgCostPerTask: number;
    avgTokensPerTask: number;
    tasksByStatus: Record<string, number>;
    tasksByArea: Record<string, number>;
  },
  period: string,
): string {
  const lines = [
    `📊 **Usage Report: ${period}**`,
    '',
    `**Tasks:** ${stats.totalTasks} total (${stats.completedTasks} done, ${stats.stuckTasks} stuck)`,
    `**Cost:** $${stats.totalCostUsd.toFixed(4)} total ($${stats.avgCostPerTask.toFixed(4)} avg/task)`,
    `**Tokens:** ${stats.totalTokens.toLocaleString()} total (${Math.round(stats.avgTokensPerTask).toLocaleString()} avg/task)`,
  ];

  // Add breakdown by status if there are tasks
  if (stats.totalTasks > 0) {
    const statusBreakdown = Object.entries(stats.tasksByStatus)
      .map(([status, count]) => `${status}: ${count}`)
      .join(', ');
    lines.push(`**By Status:** ${statusBreakdown}`);

    // Add breakdown by area if available
    const areaEntries = Object.entries(stats.tasksByArea).filter(([area]) => area !== 'null');
    if (areaEntries.length > 0) {
      const areaBreakdown = areaEntries
        .map(([area, count]) => `${area}: ${count}`)
        .join(', ');
      lines.push(`**By Area:** ${areaBreakdown}`);
    }
  }

  return lines.join('\n');
}

/**
 * All stats-related tools
 */
export const statsTools: RegisteredTool[] = [getUsageStatsTool];
