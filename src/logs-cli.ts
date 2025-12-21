#!/usr/bin/env node
/**
 * CLI utility for viewing Arnold system logs from Supabase
 * 
 * Usage:
 *   npx ts-node src/logs-cli.ts [options]
 *   npm run logs -- [options]
 * 
 * Options:
 *   --level, -l     Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
 *   --task, -t      Filter by task ID
 *   --since, -s     Show logs since (e.g., "1h", "30m", "2024-01-01")
 *   --search, -q    Search in message text
 *   --limit, -n     Number of logs to show (default: 50)
 *   --errors, -e    Show only errors (shortcut for --level ERROR,CRITICAL)
 *   --follow, -f    Poll for new logs (refresh every 5s)
 *   --json, -j      Output as JSON
 */

import 'dotenv/config';
import { querySystemLogs, getRecentErrors, getTaskLogs, type SystemLog, type DbLogLevel } from './supabase.js';

// Parse command line arguments
const args = process.argv.slice(2);

interface CliOptions {
  level?: DbLogLevel[];
  taskId?: string;
  since?: Date;
  search?: string;
  limit: number;
  errorsOnly: boolean;
  follow: boolean;
  json: boolean;
  help: boolean;
}

function parseArgs(): CliOptions {
  const options: CliOptions = {
    limit: 50,
    errorsOnly: false,
    follow: false,
    json: false,
    help: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const nextArg = args[i + 1];

    switch (arg) {
      case '--help':
      case '-h':
        options.help = true;
        break;

      case '--level':
      case '-l':
        if (nextArg) {
          options.level = nextArg.toUpperCase().split(',') as DbLogLevel[];
          i++;
        }
        break;

      case '--task':
      case '-t':
        if (nextArg) {
          options.taskId = nextArg;
          i++;
        }
        break;

      case '--since':
      case '-s':
        if (nextArg) {
          options.since = parseSince(nextArg);
          i++;
        }
        break;

      case '--search':
      case '-q':
        if (nextArg) {
          options.search = nextArg;
          i++;
        }
        break;

      case '--limit':
      case '-n':
        if (nextArg) {
          options.limit = parseInt(nextArg, 10) || 50;
          i++;
        }
        break;

      case '--errors':
      case '-e':
        options.errorsOnly = true;
        break;

      case '--follow':
      case '-f':
        options.follow = true;
        break;

      case '--json':
      case '-j':
        options.json = true;
        break;
    }
  }

  return options;
}

function parseSince(value: string): Date {
  // Check for relative time (e.g., "1h", "30m", "7d")
  const relativeMatch = value.match(/^(\d+)([mhd])$/);
  if (relativeMatch) {
    const amount = parseInt(relativeMatch[1], 10);
    const unit = relativeMatch[2];
    const now = new Date();
    
    switch (unit) {
      case 'm':
        return new Date(now.getTime() - amount * 60 * 1000);
      case 'h':
        return new Date(now.getTime() - amount * 60 * 60 * 1000);
      case 'd':
        return new Date(now.getTime() - amount * 24 * 60 * 60 * 1000);
    }
  }
  
  // Try to parse as date string
  return new Date(value);
}

function printHelp(): void {
  console.log(`
Arnold Log Viewer

Usage: npm run logs -- [options]

Options:
  --help, -h        Show this help message
  --level, -l       Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                    Can be comma-separated: -l ERROR,WARNING
  --task, -t        Filter by task ID (UUID)
  --since, -s       Show logs since time
                    Relative: "30m", "1h", "7d"
                    Absolute: "2024-01-01" or ISO timestamp
  --search, -q      Search in message text (case-insensitive)
  --limit, -n       Number of logs to show (default: 50)
  --errors, -e      Show only errors (ERROR and CRITICAL)
  --follow, -f      Poll for new logs every 5 seconds
  --json, -j        Output as JSON (one object per line)

Examples:
  npm run logs                          # Show recent 50 logs
  npm run logs -- -e                    # Show recent errors
  npm run logs -- -l WARNING -n 20      # Show 20 recent warnings
  npm run logs -- -t abc123 -s 1h       # Logs for task abc123 in last hour
  npm run logs -- -q "Claude Code" -f   # Follow logs containing "Claude Code"
  npm run logs -- -j | jq '.message'    # JSON output piped to jq
`);
}

const levelColors: Record<string, string> = {
  DEBUG: '\x1b[90m',    // Gray
  INFO: '\x1b[36m',     // Cyan
  WARNING: '\x1b[33m',  // Yellow
  ERROR: '\x1b[31m',    // Red
  CRITICAL: '\x1b[35m', // Magenta
};

const resetColor = '\x1b[0m';

function formatLog(log: SystemLog, useJson: boolean): string {
  if (useJson) {
    return JSON.stringify(log);
  }

  const timestamp = new Date(log.timestamp).toLocaleString();
  const color = levelColors[log.log_level] || '';
  const levelPadded = log.log_level.padEnd(8);
  
  let output = `${color}[${timestamp}] ${levelPadded}${resetColor} ${log.message}`;
  
  if (log.task_id) {
    output += ` \x1b[90m(task: ${log.task_id.substring(0, 8)})\x1b[0m`;
  }
  
  // Show metadata if present and non-empty
  if (log.metadata && Object.keys(log.metadata).length > 0) {
    output += `\n  \x1b[90m${JSON.stringify(log.metadata)}\x1b[0m`;
  }
  
  return output;
}

async function fetchAndPrintLogs(options: CliOptions, seenIds: Set<string>): Promise<void> {
  let logs: SystemLog[];
  
  if (options.errorsOnly) {
    logs = await getRecentErrors(options.limit);
  } else if (options.taskId && !options.level && !options.search && !options.since) {
    logs = await getTaskLogs(options.taskId, options.limit);
  } else {
    logs = await querySystemLogs({
      level: options.level,
      taskId: options.taskId,
      since: options.since,
      search: options.search,
      limit: options.limit,
    });
  }
  
  // Reverse to show oldest first (more natural for reading)
  logs.reverse();
  
  for (const log of logs) {
    // In follow mode, skip already-seen logs
    if (options.follow && seenIds.has(log.id)) {
      continue;
    }
    
    seenIds.add(log.id);
    console.log(formatLog(log, options.json));
  }
}

async function main(): Promise<void> {
  const options = parseArgs();
  
  if (options.help) {
    printHelp();
    process.exit(0);
  }
  
  const seenIds = new Set<string>();
  
  try {
    await fetchAndPrintLogs(options, seenIds);
    
    if (options.follow) {
      console.log('\n\x1b[90m--- Following logs (Ctrl+C to stop) ---\x1b[0m\n');
      
      // Poll every 5 seconds
      setInterval(async () => {
        try {
          await fetchAndPrintLogs(options, seenIds);
        } catch (err) {
          console.error('Error fetching logs:', err);
        }
      }, 5000);
    }
  } catch (err) {
    console.error('Error:', err);
    process.exit(1);
  }
}

main();
