import { spawn, execSync } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import { config } from './config.js';
import { logger } from './logger.js';
import { GitError, ExecutorBusyError, ExecutorNotRunningError } from './errors.js';
import { getNextTodoTask, updateTaskStatus, resetInProgressTasks } from './supabase.js';
import type {
  Task,
  ExecutorState,
  ExecutorResult,
  ClaudeCodeResult,
  GitPushResult,
  NotifyCallback,
  ExecutionDetails,
} from './types.js';

const PROJECT_DIR = `${config.executor.workspaceDir}/${config.github.repoName}`;

/**
 * Task executor that polls for and executes tasks using Claude Code
 */
class TaskExecutor {
  private running = false;
  private currentTask: Task | null = null;
  private notifyCallback: NotifyCallback | null = null;
  private pollInterval: NodeJS.Timeout | null = null;
  private repoReady = false;
  private lastPullTime = 0;
  private idleResolvers: Array<() => void> = [];

  /**
   * Start the executor - begins polling for and executing tasks
   */
  async start(onNotify: NotifyCallback): Promise<ExecutorResult> {
    if (this.running) {
      throw new ExecutorBusyError();
    }

    // Ensure repo is cloned and ready
    const ready = await this.ensureRepoReady();
    if (!ready) {
      return { success: false, message: 'Failed to setup repository' };
    }

    this.running = true;
    this.notifyCallback = onNotify;

    logger.info('Executor started', { projectDir: PROJECT_DIR });

    // Reset any stuck "in_progress" tasks back to "todo"
    try {
      const resetCount = await resetInProgressTasks();
      if (resetCount > 0) {
        logger.info('Reset stuck tasks', { count: resetCount });
      }
    } catch (error) {
      logger.error('Failed to reset in_progress tasks', error instanceof Error ? error : undefined);
    }

    // Start polling
    this.pollForTasks();
    this.pollInterval = setInterval(() => this.pollForTasks(), config.executor.pollIntervalMs);

    return { success: true, message: 'Executor started' };
  }

  /**
   * Stop the executor
   */
  stop(): ExecutorResult {
    if (!this.running) {
      throw new ExecutorNotRunningError();
    }

    this.running = false;
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }

    logger.info('Executor stopped', {
      currentTask: this.currentTask?.title || null,
    });

    return {
      success: true,
      message: this.currentTask
        ? `Stopping after current task: ${this.currentTask.title}`
        : 'Stopped',
    };
  }

  /**
   * Get current executor status
   */
  getStatus(): ExecutorState {
    return {
      running: this.running,
      currentTask: this.currentTask
        ? { id: this.currentTask.id, title: this.currentTask.title }
        : null,
    };
  }

  /**
   * Wait for the executor to become idle (no current task)
   * Used for graceful shutdown
   */
  async waitForIdle(timeoutMs: number): Promise<void> {
    if (!this.currentTask) {
      return;
    }

    logger.info('Waiting for executor to become idle', {
      currentTask: this.currentTask.title,
      timeoutMs,
    });

    return new Promise<void>((resolve) => {
      // Set up timeout
      const timeout = setTimeout(() => {
        const idx = this.idleResolvers.indexOf(resolve);
        if (idx !== -1) {
          this.idleResolvers.splice(idx, 1);
        }
        logger.warn('Executor idle wait timed out');
        resolve();
      }, timeoutMs);

      // Add resolver to be called when task completes
      this.idleResolvers.push(() => {
        clearTimeout(timeout);
        resolve();
      });
    });
  }

  /**
   * Ensure the repo is cloned and ready
   */
  private async ensureRepoReady(): Promise<boolean> {
    if (this.repoReady) return true;

    try {
      // Create workspace dir if needed
      if (!existsSync(config.executor.workspaceDir)) {
        logger.info('Creating workspace directory', { path: config.executor.workspaceDir });
        mkdirSync(config.executor.workspaceDir, { recursive: true });
      }

      // Clone if not exists
      if (!existsSync(PROJECT_DIR)) {
        logger.info('Cloning repository', {
          repo: `${config.github.repoOwner}/${config.github.repoName}`,
        });

        const cloneUrl = config.github.token
          ? `https://${config.github.token}@github.com/${config.github.repoOwner}/${config.github.repoName}.git`
          : `https://github.com/${config.github.repoOwner}/${config.github.repoName}.git`;

        execSync(`git clone ${cloneUrl} ${config.github.repoName}`, {
          cwd: config.executor.workspaceDir,
          encoding: 'utf-8',
          stdio: 'pipe',
        });

        logger.info('Repository cloned', { path: PROJECT_DIR });
      }

      // Configure git user
      execSync(`git config user.name "${config.executor.gitUserName}"`, { cwd: PROJECT_DIR });
      execSync(`git config user.email "${config.executor.gitUserEmail}"`, { cwd: PROJECT_DIR });

      // Checkout the right branch
      execSync(`git checkout ${config.github.repoBranch}`, { cwd: PROJECT_DIR, stdio: 'pipe' });

      this.repoReady = true;
      return true;
    } catch (error) {
      logger.error('Failed to setup repository', error instanceof Error ? error : undefined);
      return false;
    }
  }

  /**
   * Poll for pending tasks and execute them
   */
  private async pollForTasks(): Promise<void> {
    if (!this.running || this.currentTask) {
      return;
    }

    try {
      const task = await getNextTodoTask();

      if (task) {
        logger.info('Found task to execute', { taskId: task.id, title: task.title });
        await this.gitPull();
        await this.executeTask(task);
      } else {
        // No tasks - pull periodically to stay in sync
        const now = Date.now();
        if (now - this.lastPullTime > 60_000) {
          await this.gitPull();
          this.lastPullTime = now;
        }
      }
    } catch (error) {
      logger.error('Poll error', error instanceof Error ? error : undefined);
    }
  }

  /**
   * Pull latest changes from GitHub
   */
  private async gitPull(): Promise<{ success: boolean; output?: string }> {
    try {
      logger.debug('Pulling latest changes');
      const output = execSync('git pull', {
        cwd: PROJECT_DIR,
        encoding: 'utf-8',
        stdio: 'pipe',
      });

      if (!output.includes('Already up to date')) {
        logger.info('Pulled changes', { output: output.trim() });
      }

      return { success: true, output };
    } catch (error) {
      logger.error('Git pull failed', error instanceof Error ? error : undefined);
      return { success: false };
    }
  }

  /**
   * Execute a single task using Claude Code
   */
  private async executeTask(task: Task): Promise<void> {
    this.currentTask = task;

    try {
      // Update status to in_progress
      await updateTaskStatus(task.id, 'in_progress');
      this.notify(`🔄 **Starting:** ${task.title}`);

      // Build the prompt for Claude Code
      const prompt = this.buildPrompt(task);

      logger.info('Running Claude Code', { taskId: task.id, promptLength: prompt.length });

      const result = await this.runClaudeCode(prompt);

      if (result.success) {
        // Try to push changes to GitHub
        let pushResult: GitPushResult = { success: false, message: 'Push not attempted' };
        try {
          pushResult = await this.pushToGitHub();
        } catch (error) {
          logger.error('Push failed', error instanceof Error ? error : undefined);
          pushResult = {
            success: false,
            message: error instanceof Error ? error.message : String(error),
          };
        }

        // Task completed successfully
        const devNotes = result.devNotes || 'Completed successfully.';
        await updateTaskStatus(task.id, 'done', devNotes, pushResult.commitHash || null, result.executionDetails);

        let pushInfo: string;
        if (pushResult.success) {
          pushInfo = `\n\n🔗 ${pushResult.message}`;
          if (pushResult.commitMessage) {
            pushInfo += `\n📝 *"${pushResult.commitMessage}"*`;
          }
        } else {
          pushInfo = `\n\n⚠️ Changes committed locally but push failed: ${pushResult.message}`;
        }

        this.notify(`✅ **Done:** ${task.title}${pushInfo}\n\`${task.id}\``);
        logger.info('Task completed', { taskId: task.id, pushed: pushResult.success });
      } else {
        // Task failed - mark as stuck
        logger.error('Task failed', undefined, { taskId: task.id, error: result.error });
        await updateTaskStatus(task.id, 'stuck', result.error || 'Unknown error');
        this.notify(`⚠️ **Stuck:** ${task.title}\n${result.error}`);
      }
    } catch (error) {
      // Unexpected error - mark as stuck
      const message = error instanceof Error ? error.message : String(error);
      logger.error('Unexpected task execution error', error instanceof Error ? error : undefined, {
        taskId: task.id,
      });
      await updateTaskStatus(task.id, 'stuck', message);
      this.notify(`⚠️ **Stuck:** ${task.title}\n${message}`);
    } finally {
      this.currentTask = null;
      // Resolve any waitForIdle promises
      this.idleResolvers.forEach((resolve) => resolve());
      this.idleResolvers = [];
    }
  }

  /**
   * Build a prompt for Claude Code based on the task
   */
  private buildPrompt(task: Task): string {
    const parts: string[] = [`# Task: ${task.title}`, ''];

    if (task.description) {
      parts.push('## Description', task.description, '');
    }

    if (task.area) {
      parts.push(`## Area: ${task.area}`, '');
    }

    if (task.notes) {
      parts.push('## Notes', task.notes, '');
    }

    parts.push(
      '## Instructions',
      '1. Read structure.md first to understand the codebase layout and conventions. For deeper details, check structure_docs/ subdirectory.',
      '2. Implement the requested changes',
      '3. Make sure the code follows existing patterns and conventions',
      '4. Test that your changes work (run build, check for errors)',
      '5. Commit your changes with a clear, descriptive commit message',
      '6. At the very end, output dev notes in this format:',
      '',
      'DEV_NOTES_START',
      '- What files were changed and why',
      '- Any decisions made or trade-offs',
      '- Anything to watch out for',
      'DEV_NOTES_END',
    );

    return parts.join('\n');
  }

  /**
   * Run Claude Code with a prompt
   */
  private runClaudeCode(prompt: string): Promise<ClaudeCodeResult> {
    return new Promise((resolve) => {
      const args = ['-p', prompt, '--permission-mode', 'bypassPermissions', '--output-format', 'json'];

      logger.debug('Spawning Claude Code', { workingDir: PROJECT_DIR });

      const proc = spawn(config.executor.claudePath, args, {
        cwd: PROJECT_DIR,
        env: {
          ...process.env,
          ANTHROPIC_API_KEY: config.anthropic.apiKey,
          CI: 'true',
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data: Buffer) => {
        const text = data.toString();
        stdout += text;
        logger.debug('Claude Code output', { text: text.substring(0, 200) });
      });

      proc.stderr.on('data', (data: Buffer) => {
        const text = data.toString();
        stderr += text;
        logger.debug('Claude Code stderr', { text: text.substring(0, 200) });
      });

      proc.on('close', (code) => {
        logger.info('Claude Code exited', { code, stdoutLen: stdout.length, stderrLen: stderr.length });

        if (code === 0) {
          // Parse JSON output to extract usage stats
          const { executionDetails, result } = this.parseClaudeCodeOutput(stdout);
          
          resolve({
            success: true,
            devNotes: this.extractDevNotes(result || stdout),
            executionDetails,
          });
        } else {
          const errorText = stderr || stdout || '';
          const isSystemError =
            errorText.includes('unknown option') ||
            errorText.includes('command not found') ||
            errorText.includes('ENOENT') ||
            errorText.includes('spawn') ||
            errorText.includes('permission denied') ||
            errorText.includes('API key') ||
            errorText.includes('authentication') ||
            errorText.includes('rate limit');

          resolve({
            success: false,
            error: errorText || `Exit code ${code}`,
            isSystemError,
          });
        }
      });

      proc.on('error', (err) => {
        logger.error('Failed to spawn Claude Code', err);
        resolve({
          success: false,
          error: `Failed to run Claude Code: ${err.message}`,
          isSystemError: true,
        });
      });

      // Timeout
      setTimeout(() => {
        if (proc.exitCode === null) {
          logger.warn('Claude Code timed out');
          proc.kill();
          resolve({
            success: false,
            error: 'Task timed out after 10 minutes',
          });
        }
      }, config.executor.taskTimeoutMs);
    });
  }

  /**
   * Parse Claude Code JSON output to extract usage stats
   */
  private parseClaudeCodeOutput(output: string): { executionDetails?: ExecutionDetails; result?: string } {
    try {
      const json = JSON.parse(output);
      
      const executionDetails: ExecutionDetails = {
        num_turns: json.num_turns,
        total_cost_usd: json.total_cost_usd,
        duration_ms: json.duration_ms,
        usage: json.usage ? {
          input_tokens: json.usage.input_tokens,
          output_tokens: json.usage.output_tokens,
          cache_creation_input_tokens: json.usage.cache_creation_input_tokens,
          cache_read_input_tokens: json.usage.cache_read_input_tokens,
        } : undefined,
      };
      
      const result = json.result || undefined;
      
      logger.info('Claude Code usage', { 
        numTurns: executionDetails.num_turns,
        costUsd: executionDetails.total_cost_usd,
        durationMs: executionDetails.duration_ms,
      });
      
      return { executionDetails, result };
    } catch {
      // Not JSON or parse error - return empty
      logger.debug('Could not parse Claude Code output as JSON');
      return {};
    }
  }

  /**
   * Extract dev notes from Claude Code output
   */
  private extractDevNotes(output: string): string | null {
    const startMarker = 'DEV_NOTES_START';
    const endMarker = 'DEV_NOTES_END';

    const startIdx = output.indexOf(startMarker);
    const endIdx = output.indexOf(endMarker);

    if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
      const notes = output.substring(startIdx + startMarker.length, endIdx).trim();
      return notes || null;
    }

    return null;
  }

  /**
   * Push changes to GitHub
   */
  private async pushToGitHub(): Promise<GitPushResult> {
    if (!config.github.token) {
      return { success: false, message: 'GITHUB_API_KEY not configured' };
    }

    try {
      // Get current branch
      const branch = execSync('git rev-parse --abbrev-ref HEAD', {
        cwd: PROJECT_DIR,
        encoding: 'utf-8',
      }).trim();

      // Get the commit hash
      const commitHash = execSync('git rev-parse HEAD', {
        cwd: PROJECT_DIR,
        encoding: 'utf-8',
      }).trim();

      const shortHash = commitHash.substring(0, 7);

      // Get commit message
      const commitMessage = execSync('git log -1 --pretty=%B', {
        cwd: PROJECT_DIR,
        encoding: 'utf-8',
      })
        .trim()
        .split('\n')[0];

      logger.info('Pushing to GitHub', { branch, shortHash, commitMessage });

      // Push changes
      const repoUrl = `https://${config.github.token}@github.com/${config.github.repoOwner}/${config.github.repoName}.git`;
      execSync(`git push ${repoUrl} ${branch}`, {
        cwd: PROJECT_DIR,
        encoding: 'utf-8',
        stdio: 'pipe',
      });

      const commitUrl = `https://github.com/${config.github.repoOwner}/${config.github.repoName}/commit/${commitHash}`;

      logger.info('Pushed to GitHub', { branch, commitUrl });

      return {
        success: true,
        message: `Pushed [\`${shortHash}\`](${commitUrl}) to \`${branch}\``,
        commitHash,
        shortHash,
        commitMessage,
        commitUrl,
        branch,
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('Git push failed', error instanceof Error ? error : undefined);
      throw new GitError('push', errorMessage);
    }
  }

  /**
   * Send notification via callback
   */
  private notify(message: string): void {
    if (this.notifyCallback) {
      this.notifyCallback(message);
    }
  }
}

// Export singleton instance
export const executor = new TaskExecutor();

// Export convenience functions for backward compatibility
export const startExecutor = (onNotify: NotifyCallback) => executor.start(onNotify);
export const stopExecutor = () => executor.stop();
export const getExecutorStatus = () => executor.getStatus();
