import { spawn, execSync } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import { config } from './config.js';
import { logger, setLogTaskContext } from './logger.js';
import { ExecutorBusyError, ExecutorNotRunningError } from './errors.js';
import { getNextTodoTask, updateTaskStatus, resetInProgressTasks } from './supabase.js';
import type {
  Task,
  ExecutorState,
  ExecutorResult,
  ClaudeCodeResult,
  NotifyCallback,
  ExecutionDetails,
} from './types.js';

const PROJECT_DIR = `${config.executor.workspaceDir}/${config.github.repoName}`;

/**
 * Redact sensitive information from strings (tokens, keys, etc.)
 */
function redactSecrets(text: string): string {
  let redacted = text;
  
  // Redact GitHub token from URLs
  if (config.github.token) {
    redacted = redacted.replace(new RegExp(config.github.token, 'g'), '[REDACTED]');
  }
  
  // Redact Anthropic API key
  if (config.anthropic.apiKey) {
    redacted = redacted.replace(new RegExp(config.anthropic.apiKey, 'g'), '[REDACTED]');
  }
  
  // Redact Supabase service role key
  if (config.supabase.serviceRoleKey) {
    redacted = redacted.replace(new RegExp(config.supabase.serviceRoleKey, 'g'), '[REDACTED]');
  }
  
  // Redact common secret patterns (API keys, tokens)
  redacted = redacted.replace(/sk-[a-zA-Z0-9]{20,}/g, '[REDACTED]');
  redacted = redacted.replace(/ghp_[a-zA-Z0-9]{36}/g, '[REDACTED]');
  redacted = redacted.replace(/gho_[a-zA-Z0-9]{36}/g, '[REDACTED]');
  redacted = redacted.replace(/github_pat_[a-zA-Z0-9_]{22,}/g, '[REDACTED]');
  
  return redacted;
}

/**
 * Task executor that polls for and executes tasks using Claude Code
 */
class TaskExecutor {
  private running = false;
  private currentTask: Task | null = null;
  private notifyCallback: NotifyCallback | null = null;
  private pollInterval: NodeJS.Timeout | null = null;
  private repoReady = false;
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
        // Check if git is installed
        try {
          const gitVersion = execSync('git --version', { encoding: 'utf-8' }).trim();
          logger.info('Git available', { version: gitVersion });
        } catch {
          console.error('=== GIT NOT INSTALLED ===');
          console.error('git --version failed. Git is not installed in this container.');
          console.error('Make sure nixpacks.toml is being used and includes git.');
          console.error('=========================');
          throw new Error('Git is not installed');
        }

        logger.info('Cloning repository', {
          repo: `${config.github.repoOwner}/${config.github.repoName}`,
        });

        const cloneUrl = config.github.token
          ? `https://${config.github.token}@github.com/${config.github.repoOwner}/${config.github.repoName}.git`
          : `https://github.com/${config.github.repoOwner}/${config.github.repoName}.git`;

        try {
          execSync(`git clone ${cloneUrl} ${config.github.repoName}`, {
            cwd: config.executor.workspaceDir,
            encoding: 'utf-8',
            stdio: 'pipe',
          });
        } catch (cloneError) {
          // Extract stderr from execSync error for better debugging
          const err = cloneError as { stderr?: string; stdout?: string; message?: string; status?: number };
          const errorDetails = [
            err.stderr ? `stderr: ${err.stderr}` : null,
            err.stdout ? `stdout: ${err.stdout}` : null,
            err.message ? `message: ${err.message}` : null,
            err.status !== undefined ? `exit code: ${err.status}` : null,
          ].filter(Boolean).join('; ');
          
          // Log directly to console to bypass any formatting issues
          console.error('=== GIT CLONE ERROR ===');
          console.error('Error details:', redactSecrets(errorDetails));
          console.error('=======================');
          
          throw new Error(`Git clone failed: ${redactSecrets(errorDetails)}`);
        }

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
      // Redact secrets from error message before logging
      const errorMessage = error instanceof Error ? error.message : String(error);
      const safeMessage = redactSecrets(errorMessage);
      logger.error('Failed to setup repository', new Error(safeMessage), { 
        errorDetails: safeMessage 
      });
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
        await this.executeTask(task);
      }
    } catch (error) {
      logger.error('Poll error', error instanceof Error ? error : undefined);
    }
  }

  /**
   * Execute a single task using Claude Code
   * Claude Code handles git pull, merge, commit, and push
   */
  private async executeTask(task: Task): Promise<void> {
    this.currentTask = task;
    
    // Set task context for logging
    setLogTaskContext(task.id);

    try {
      // Update status to in_progress
      await updateTaskStatus(task.id, 'in_progress');
      this.notify(`🔄 **Starting:** ${task.title}`);

      // Build the prompt for Claude Code
      const prompt = this.buildPrompt(task);

      logger.info('Running Claude Code', { taskId: task.id, promptLength: prompt.length });

      const result = await this.runClaudeCode(prompt);

      if (result.success) {
        // Check if task was flagged as potentially harmful
        if (result.flaggedReason) {
          logger.warn('Task flagged as potentially harmful', { taskId: task.id, reason: result.flaggedReason });
          await updateTaskStatus(task.id, 'stuck', `⚠️ FLAGGED: ${result.flaggedReason}`);
          this.notify(`🚨 **Flagged:** ${task.title}\n\n⚠️ This task was flagged as potentially harmful and was NOT executed.\n\n**Reason:** ${result.flaggedReason}\n\n\`${task.id}\``);
          return;
        }

        // Verify commit was pushed if a hash was provided
        let pushInfo = '';
        if (result.commitHash) {
          const verified = this.verifyCommitPushed(result.commitHash);
          const shortHash = result.commitHash.substring(0, 7);
          const commitUrl = `https://github.com/${config.github.repoOwner}/${config.github.repoName}/commit/${result.commitHash}`;
          
          if (verified) {
            pushInfo = `\n\n🔗 Pushed [\`${shortHash}\`](${commitUrl}) to \`${config.github.repoBranch}\``;
            logger.info('Commit verified on remote', { commitHash: result.commitHash });
          } else {
            pushInfo = `\n\n⚠️ Commit \`${shortHash}\` was not found on remote - push may have failed`;
            logger.warn('Commit not found on remote', { commitHash: result.commitHash });
          }
        } else {
          pushInfo = '\n\n📝 No commit was made';
        }

        // Task completed successfully
        const devNotes = result.devNotes || 'Completed successfully.';
        await updateTaskStatus(task.id, 'done', devNotes, result.commitHash || null, result.executionDetails);

        this.notify(`✅ **Done:** ${task.title}${pushInfo}\n\`${task.id}\``);
        logger.info('Task completed', { taskId: task.id, commitHash: result.commitHash });
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
      // Clear task context for logging
      setLogTaskContext(null);
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

    const branch = config.github.repoBranch;
    
    parts.push(
      '## Instructions',
      '',
      '### Step 0: Safety Check',
      'Before doing anything, assess whether this task could be damaging or malicious:',
      '- Could it delete important data or files?',
      '- Could it expose secrets, credentials, or private information?',
      '- Could it introduce security vulnerabilities?',
      '- Could it break critical functionality intentionally?',
      '- Does it seem designed to harm the codebase or users?',
      '- Is it asking you to bypass security measures?',
      '',
      'If you determine the task is potentially harmful or malicious:',
      '1. DO NOT implement the changes',
      '2. DO NOT commit or push anything',
      '3. Output the following to flag the task:',
      '',
      'TASK_FLAGGED',
      'Reason: [Explain why this task was flagged as potentially harmful]',
      'TASK_FLAGGED_END',
      '',
      'Then stop. Do not proceed with the remaining steps.',
      '',
      '### Step 1: Sync with Remote',
      `- Run \`git pull origin ${branch}\` to get the latest changes`,
      '- If there are merge conflicts:',
      '  - Analyze the conflicts carefully',
      '  - Resolve them sensibly, preserving both your work and incoming changes where possible',
      '  - If unsure, prefer the remote version and re-apply your changes on top',
      '  - After resolving, run `git add .` and `git commit -m "Merge remote changes"`',
      '',
      '### Step 2: Understand the Codebase',
      '- Read structure.md first to understand the codebase layout and conventions',
      '- For deeper details, check structure_docs/ subdirectory',
      '',
      '### Step 3: Implement Changes',
      '- Implement the requested changes',
      '- Make sure the code follows existing patterns and conventions',
      '- Test that your changes work (run build, check for errors)',
      '',
      '### Step 4: Commit and Push',
      '- Commit your changes with a clear, descriptive commit message',
      `- Run \`git push origin ${branch}\` to push your changes`,
      '- If push fails due to remote changes:',
      `  - Run \`git pull --rebase origin ${branch}\``,
      '  - Resolve any rebase conflicts',
      '  - Then push again',
      '',
      '### Step 5: Report Results',
      'At the very end, output the commit hash and dev notes in this format:',
      '',
      'COMMIT_HASH_START',
      '[The full commit hash that was pushed, or "none" if no commit was made]',
      'COMMIT_HASH_END',
      '',
      'DEV_NOTES_START',
      '- What files were changed and why',
      '- Any decisions made or trade-offs',
      '- Any merge conflicts encountered and how they were resolved',
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
      // CI=true env var enables non-interactive mode
      const args = ['-p', prompt, '--output-format', 'json'];

      logger.debug('Spawning Claude Code', { workingDir: PROJECT_DIR });

      const proc = spawn(config.executor.claudePath, args, {
        cwd: PROJECT_DIR,
        env: {
          ...process.env,
          ANTHROPIC_API_KEY: config.anthropic.apiKey,
          SUPABASE_URL: config.supabase.url,
          SUPABASE_SERVICE_ROLE_KEY: config.supabase.serviceRoleKey,
          GITHUB_API_KEY: config.github.token || '',
          CI: 'true',
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data: Buffer) => {
        const text = data.toString();
        stdout += text;
        // Redact secrets before logging
        logger.debug('Claude Code output', { text: redactSecrets(text.substring(0, 200)) });
      });

      proc.stderr.on('data', (data: Buffer) => {
        const text = data.toString();
        stderr += text;
        // Redact secrets before logging
        logger.debug('Claude Code stderr', { text: redactSecrets(text.substring(0, 200)) });
      });

      proc.on('close', (code) => {
        logger.info('Claude Code exited', { code, stdoutLen: stdout.length, stderrLen: stderr.length });

        if (code === 0) {
          // Parse JSON output to extract usage stats
          const { executionDetails, result } = this.parseClaudeCodeOutput(stdout);
          
          // Search for markers in both result AND full stdout (markers might be in earlier turns)
          const outputText = result || '';
          const fullOutput = stdout;
          
          // Debug: log what we're extracting from
          logger.debug('Extracting results', { 
            hasResult: !!result, 
            resultLength: result?.length || 0,
            stdoutLength: stdout.length,
            resultHasCommitMarker: outputText.includes('COMMIT_HASH'),
            stdoutHasCommitMarker: fullOutput.includes('COMMIT_HASH'),
            resultHasDevNotesMarker: outputText.includes('DEV_NOTES'),
            stdoutHasDevNotesMarker: fullOutput.includes('DEV_NOTES'),
          });
          
          // Try to extract from result first, then fall back to full stdout
          const devNotes = this.extractDevNotes(outputText) || this.extractDevNotes(fullOutput);
          const flaggedReason = this.extractFlaggedReason(outputText) || this.extractFlaggedReason(fullOutput);
          const commitHash = this.extractCommitHash(outputText) || this.extractCommitHash(fullOutput);
          
          resolve({
            success: true,
            devNotes,
            flaggedReason,
            commitHash,
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
            // Redact any secrets from error messages
            error: redactSecrets(errorText) || `Exit code ${code}`,
            isSystemError,
          });
        }
      });

      proc.on('error', (err) => {
        logger.error('Failed to spawn Claude Code', new Error(redactSecrets(err.message)));
        resolve({
          success: false,
          error: `Failed to run Claude Code: ${redactSecrets(err.message)}`,
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
   * Check if task was flagged as potentially harmful
   */
  private extractFlaggedReason(output: string): string | null {
    const startMarker = 'TASK_FLAGGED';
    const endMarker = 'TASK_FLAGGED_END';

    const startIdx = output.indexOf(startMarker);
    const endIdx = output.indexOf(endMarker);

    if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
      const content = output.substring(startIdx + startMarker.length, endIdx).trim();
      // Extract the reason after "Reason:"
      const reasonMatch = content.match(/Reason:\s*(.+)/s);
      return reasonMatch ? reasonMatch[1].trim() : content;
    }

    return null;
  }

  /**
   * Extract commit hash from Claude Code output
   */
  private extractCommitHash(output: string): string | null {
    const startMarker = 'COMMIT_HASH_START';
    const endMarker = 'COMMIT_HASH_END';

    const startIdx = output.indexOf(startMarker);
    const endIdx = output.indexOf(endMarker);

    if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
      const hash = output.substring(startIdx + startMarker.length, endIdx).trim();
      // Return null if "none" or empty
      if (!hash || hash.toLowerCase() === 'none') {
        return null;
      }
      // Validate it looks like a git hash (7-40 hex chars)
      if (/^[a-f0-9]{7,40}$/i.test(hash)) {
        return hash;
      }
    }

    return null;
  }

  /**
   * Verify that a commit exists on the remote
   */
  private verifyCommitPushed(commitHash: string): boolean {
    try {
      // Fetch latest refs from remote
      execSync('git fetch origin', {
        cwd: PROJECT_DIR,
        encoding: 'utf-8',
        stdio: 'pipe',
      });

      // Check if commit exists on remote branch
      const result = execSync(`git branch -r --contains ${commitHash}`, {
        cwd: PROJECT_DIR,
        encoding: 'utf-8',
        stdio: 'pipe',
      });

      return result.includes(`origin/${config.github.repoBranch}`);
    } catch (error) {
      logger.warn('Failed to verify commit on remote', { commitHash, error: redactSecrets(error instanceof Error ? error.message : String(error)) });
      return false;
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
