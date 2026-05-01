// deno-lint-ignore-file
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { NO_SESSION_RUNTIME_OPTIONS, withEdgeRequest } from "../_shared/edgeHandler.ts";
import { toErrorMessage } from "../_shared/errorMessage.ts";
import {
  getSubTaskOrchestratorId,
  fetchCompletedSubTasksForOrchestrator,
  SubTaskLookupError,
  type CompletedSubTaskRow,
} from "../_shared/billing.ts";
import { ensureTaskActor } from "../_shared/requestGuards.ts";
import { authorizeTaskActor } from "../_shared/taskActorPolicy.ts";
import {
  calculateTaskCost,
  errorResponse,
  jsonResponse,
  parseTaskWithProject,
} from "./costHelpers.ts";

serve((req) => {
  return withEdgeRequest(req, {
    functionName: "calculate-task-cost",
    logPrefix: "[CALCULATE-TASK-COST]",
    parseBody: "strict",
    auth: {
      required: true,
    },
    ...NO_SESSION_RUNTIME_OPTIONS,
  }, async ({ supabaseAdmin, logger, auth, body: requestBody }) => {
    const authResult = ensureTaskActor(auth, logger);
    if (!authResult.ok) {
      return authResult.response;
    }

    try {
    const task_id = typeof requestBody.task_id === 'string' ? requestBody.task_id : undefined;

    if (!task_id) {
      logger.error("Missing task_id in request");
      return errorResponse('missing_task_id', 'task_id is required', 400);
    }

    const actor = await authorizeTaskActor({
      supabaseAdmin,
      taskId: task_id,
      auth: auth!,
      logPrefix: "[CALCULATE-TASK-COST]",
    });
    if (!actor.ok) {
      logger.warn("Task ownership verification failed", {
        task_id,
        user_id: auth?.userId,
        reason: actor.error,
      });
      return errorResponse(
        actor.statusCode === 404 ? 'task_not_found' : actor.statusCode === 401 ? 'authentication_failed' : 'forbidden',
        actor.error || "Forbidden",
        actor.statusCode || 403,
      );
    }

    // Set task_id for all subsequent logs
    logger.setDefaultTaskId(task_id);
    logger.info("Calculating task cost", { task_id });

    // Get task details with task_types joined via FK (eliminates separate task_types query)
    const { data: task, error: taskError } = await supabaseAdmin
      .from('tasks')
      .select(`
        id,
        task_type,
        params,
        status,
        generation_started_at,
        generation_processed_at,
        project_id,
        projects(user_id),
        task_types!tasks_task_type_fkey(id, billing_type, base_cost_per_second, unit_cost, cost_factors, is_active)
      `)
      .eq('id', task_id)
      .single();

    if (taskError) {
      logger.error("Task not found", { error: taskError?.message });
      return errorResponse('task_not_found', 'Task not found', 404);
    }

    const typedTaskResult = parseTaskWithProject(task);
    if (!typedTaskResult.ok) {
      logger.error("Task payload shape invalid", {
        failure: typedTaskResult.failure,
        task_id,
      });
      return errorResponse(
        typedTaskResult.failure.errorCode,
        typedTaskResult.failure.message,
        422,
      );
    }
    const typedTask = typedTaskResult.task;

    logger.debug("Task found", {
      task_type: typedTask.task_type,
      status: typedTask.status,
      has_timestamps: !!(typedTask.generation_started_at && typedTask.generation_processed_at)
    });

    // Check if task has both start and end times
    if (!typedTask.generation_started_at || !typedTask.generation_processed_at) {
      logger.error("Missing timestamps", {
        has_started_at: !!typedTask.generation_started_at,
        has_processed_at: !!typedTask.generation_processed_at
      });
      return errorResponse(
        'missing_generation_timestamps',
        'Task must have both generation_started_at and generation_processed_at timestamps',
        400,
      );
    }

    // Check if task is a sub-task of an orchestrator - skip billing if so (parent will be billed)
    // Uses shared detection: checks all param paths, validates UUID, guards against self-reference
    const subTaskOrchestratorId = getSubTaskOrchestratorId(typedTask.params, typedTask.id);

    if (subTaskOrchestratorId) {
      logger.info("Skipping cost calculation (sub-task)", {
        orchestrator_task_id: subTaskOrchestratorId
      });
      return jsonResponse({
        success: true,
        skipped: true,
        reason: 'Task is sub-task of orchestrator, parent task will be billed',
        orchestrator_task_id: subTaskOrchestratorId,
        task_id: typedTask.id
      });
    }

    // Check if this is an orchestrator task - calculate cost based on sub-task durations
    let subTasks: CompletedSubTaskRow[] = [];
    try {
      subTasks = await fetchCompletedSubTasksForOrchestrator(supabaseAdmin, task_id);
    } catch (subTaskLookupError) {
      const stage = subTaskLookupError instanceof SubTaskLookupError
        ? subTaskLookupError.stage
        : 'unknown';
      const errorCode = stage === 'canonical'
        ? 'subtask_query_failed_canonical'
        : stage === 'legacy'
          ? 'subtask_query_failed_legacy'
          : 'subtask_query_failed';
      logger.error("Failed to query sub-task references", {
        error: subTaskLookupError instanceof Error
          ? subTaskLookupError.message
          : String(subTaskLookupError),
        stage,
      });
      return errorResponse(errorCode, 'Failed to query sub-task references', 500, true);
    }

    let durationSeconds;
    if (subTasks && subTasks.length > 0) {
      // This is an orchestrator task with sub-tasks - sum their durations
      logger.info("Orchestrator task detected", { sub_task_count: subTasks.length });

      let totalSubTaskDuration = 0;
      for (const subTask of subTasks) {
        if (subTask.generation_started_at && subTask.generation_processed_at) {
          const subStartTime = new Date(subTask.generation_started_at);
          const subEndTime = new Date(subTask.generation_processed_at);
          const subDuration = Math.max(1, Math.ceil((subEndTime.getTime() - subStartTime.getTime()) / 1000));
          totalSubTaskDuration += subDuration;
        }
      }

      durationSeconds = totalSubTaskDuration;
      logger.debug("Orchestrator duration calculated", { 
        sub_task_count: subTasks.length, 
        total_duration_seconds: durationSeconds 
      });
    } else {
      // Regular task - use its own duration
      const startTime = new Date(typedTask.generation_started_at);
      const endTime = new Date(typedTask.generation_processed_at);
      durationSeconds = Math.max(1, Math.ceil((endTime.getTime() - startTime.getTime()) / 1000));
    }

    // Idempotency: avoid double-billing if this function is called multiple times for the same task.
    // The credits ledger is intended to be immutable, so we should skip if a spend entry already exists.
    const { data: existingSpendEntries, error: existingSpendError } = await supabaseAdmin
      .from('credits_ledger')
      .select('id, amount, created_at')
      .eq('task_id', typedTask.id)
      .eq('type', 'spend')
      .order('created_at', { ascending: false })
      .limit(1);

    if (existingSpendError) {
      logger.error("Failed to check existing credit ledger entries", { error: existingSpendError.message });
      return errorResponse('cost_record_check_failed', 'Failed to check existing cost records', 500, true);
    }

    if (existingSpendEntries && existingSpendEntries.length > 0) {
      const existing = existingSpendEntries[0];
      logger.info("Cost already recorded - skipping", {
        ledger_id: existing.id,
        existing_amount: existing.amount
      });
      return jsonResponse({
        success: true,
        skipped: true,
        reason: 'Cost already recorded for this task',
        task_id: typedTask.id,
        ledger_id: existing.id,
        existing_amount: existing.amount
      });
    }

    // Get task type configuration (already joined via FK in the task query)
    const taskType = typedTask.task_type_config;

    if (!taskType || !taskType.is_active) {
      logger.error("No task type config found, using defaults", { task_type: typedTask.task_type });

      // Use default cost if no config found — must match DB-level get_task_cost() default of 0.0278
      const defaultCostPerSecond = 0.0278;
      const cost = defaultCostPerSecond * durationSeconds;

      const { error: ledgerError } = await supabaseAdmin.from('credits_ledger').insert({
        user_id: typedTask.projects.user_id,
        task_id: typedTask.id,
        amount: -cost,
        type: 'spend',
        metadata: {
          task_type: typedTask.task_type,
          duration_seconds: durationSeconds,
          base_cost_per_second: defaultCostPerSecond,
          billing_type: 'per_second',
          calculated_at: new Date().toISOString(),
          cost_fallback_used: true,
          note: 'Default cost used - no task type configuration found'
        }
      });

      if (ledgerError) {
        logger.error("Failed to insert into credit ledger (default)", { error: ledgerError.message });
        return errorResponse('ledger_write_failed', 'Failed to record cost in ledger', 500, true);
      }

      logger.info("Cost calculated (default rates)", { 
        cost,
        duration_seconds: durationSeconds,
        billing_type: 'per_second'
      });

      return jsonResponse({
        success: true,
        cost: cost,
        duration_seconds: durationSeconds,
        base_cost_per_second: defaultCostPerSecond,
        billing_type: 'per_second',
        note: 'Default cost used - no task type configuration found'
      });
    }

    // Calculate cost based on task type configuration
    const costResult = calculateTaskCost(
      typedTask.task_type,
      taskType.billing_type,
      taskType.base_cost_per_second,
      taskType.unit_cost,
      durationSeconds,
      taskType.cost_factors,
      typedTask.params
    );
    const cost = costResult.cost;
    const costBreakdown = costResult.breakdown;

    // Validate cost calculation
    if (isNaN(cost) || cost < 0) {
      logger.error("Invalid cost calculated", {
        cost,
        billing_type: taskType.billing_type,
        base_cost_per_second: taskType.base_cost_per_second,
        unit_cost: taskType.unit_cost,
        duration: durationSeconds,
        breakdown: costBreakdown
      });
      return errorResponse('invalid_cost_calculation', 'Invalid cost calculation', 500);
    }

    // Ensure user exists before inserting credit ledger entry
    const { data: user, error: userError } = await supabaseAdmin
      .from('users')
      .select('id')
      .eq('id', typedTask.projects.user_id)
      .single();

    if (userError || !user) {
      logger.error("User not found for credit ledger", { 
        user_id: typedTask.projects.user_id, 
        error: userError?.message 
      });
      return errorResponse('billing_user_not_found', 'User not found for credit calculation', 400);
    }

    // Insert cost into credit ledger
    const { error: ledgerError } = await supabaseAdmin.from('credits_ledger').insert({
      user_id: typedTask.projects.user_id,
      task_id: typedTask.id,
      amount: -cost,
      type: 'spend',
      metadata: {
        task_type: typedTask.task_type,
        billing_type: taskType.billing_type,
        duration_seconds: durationSeconds,
        base_cost_per_second: taskType.base_cost_per_second,
        unit_cost: taskType.unit_cost,
        cost_factors: taskType.cost_factors,
        task_params: typedTask.params,
        calculated_at: new Date().toISOString(),
        task_type_id: taskType.id,
        // Include breakdown for compound pricing (e.g., video_enhance)
        ...(costBreakdown ? { cost_breakdown: costBreakdown } : {})
      }
    });

    if (ledgerError) {
      logger.error("Failed to insert into credit ledger", { 
        error: ledgerError.message,
        user_id: typedTask.projects.user_id,
        cost
      });
      return errorResponse('ledger_write_failed', 'Failed to record cost in ledger', 500, true);
    }

    logger.info("Cost calculated and recorded", {
      cost,
      billing_type: taskType.billing_type,
      duration_seconds: durationSeconds,
      user_id: typedTask.projects.user_id,
      ...(costBreakdown ? { breakdown: costBreakdown } : {})
    });

    return jsonResponse({
      success: true,
      cost: cost,
      billing_type: taskType.billing_type,
      duration_seconds: durationSeconds,
      base_cost_per_second: taskType.base_cost_per_second,
      unit_cost: taskType.unit_cost,
      cost_factors: taskType.cost_factors,
      task_type: typedTask.task_type,
      task_id: typedTask.id,
      // Include breakdown for compound pricing (e.g., video_enhance)
      ...(costBreakdown ? { cost_breakdown: costBreakdown } : {})
    });

  } catch (error: unknown) {
    const errorMessage = toErrorMessage(error);
    const errorStack = error instanceof Error ? error.stack?.substring(0, 500) : undefined;
    logger.critical("Unexpected error", { error: errorMessage, stack: errorStack });
    return errorResponse('internal_server_error', 'Internal server error', 500, false);
  }});
});
