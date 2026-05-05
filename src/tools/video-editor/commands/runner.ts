import { buildTrackClipOrder } from '@/tools/video-editor/lib/coordinate-utils.ts';
import { serializeForDisk, validateSerializedConfig } from '@/tools/video-editor/lib/serialize.ts';
import { buildDataFromCurrentRegistry } from '@/tools/video-editor/lib/timeline-save-utils.ts';
import {
  preserveUploadingClips,
  rowsToConfig,
  type ClipMeta,
  type TimelineData,
} from '@/tools/video-editor/lib/timeline-data.ts';
import type {
  JsonObject,
  JsonValue,
  TimelineCommand,
  TimelineCommandContext,
  TimelineCommandDescriptor,
  TimelineCommandEffect,
  TimelineCommandError,
  TimelineCommandExecutionMode,
  TimelineCommandExecutionResult,
  TimelineCommandHistoryMetadata,
  TimelineCommandInput,
  TimelineCommandRegistry,
  TimelineCommandRunMode,
  TimelineCommandRunOptions,
  TimelineCommandRunner,
  TimelineCommandStepResult,
  TimelineCommandTransaction,
  TimelineCommandValidationError,
} from './types.ts';

const DEFAULT_EXECUTION_MODE: TimelineCommandExecutionMode = 'atomic';
const DEFAULT_MAX_ERRORS = Number.POSITIVE_INFINITY;

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isJsonValue = (value: unknown): value is JsonValue => {
  if (
    value === null
    || typeof value === 'string'
    || typeof value === 'boolean'
  ) {
    return true;
  }

  if (typeof value === 'number') {
    return Number.isFinite(value);
  }

  if (Array.isArray(value)) {
    return value.every(isJsonValue);
  }

  if (isRecord(value)) {
    return Object.values(value).every(isJsonValue);
  }

  return false;
};

const normalizeJsonObject = (value: unknown): JsonObject | null => {
  if (!isRecord(value)) {
    return null;
  }

  if (!Object.values(value).every(isJsonValue)) {
    return null;
  }

  return value as JsonObject;
};

const normalizeCommand = (
  input: unknown,
  commandIndex: number,
): { command: TimelineCommand | null; errors: TimelineCommandValidationError[] } => {
  if (!isRecord(input)) {
    return {
      command: null,
      errors: [{
        path: `$.commands[${commandIndex}]`,
        code: 'invalid_command',
        message: 'Command must be an object.',
      }],
    };
  }

  const errors: TimelineCommandValidationError[] = [];
  const type = input.type;
  if (typeof type !== 'string' || type.trim().length === 0) {
    errors.push({
      path: `$.commands[${commandIndex}].type`,
      code: 'invalid_command_type',
      message: 'Command type must be a non-empty string.',
    });
  }

  const payloadInput = input.payload ?? {};
  const payload = normalizeJsonObject(payloadInput);
  if (payload === null) {
    errors.push({
      path: `$.commands[${commandIndex}].payload`,
      code: 'invalid_command_payload',
      message: 'Command payload must be a JSON object.',
    });
  }

  if (input.commandId !== undefined && typeof input.commandId !== 'string') {
    errors.push({
      path: `$.commands[${commandIndex}].commandId`,
      code: 'invalid_command_id',
      message: 'commandId must be a string when present.',
    });
  }

  if (input.metadata !== undefined && normalizeJsonObject(input.metadata) === null) {
    errors.push({
      path: `$.commands[${commandIndex}].metadata`,
      code: 'invalid_command_metadata',
      message: 'metadata must be a JSON object when present.',
    });
  }

  if (errors.length > 0) {
    return { command: null, errors };
  }

  return {
    command: {
      type: type.trim(),
      payload: payload ?? {},
      ...(typeof input.commandId === 'string' ? { commandId: input.commandId } : {}),
      ...(input.metadata !== undefined ? { metadata: input.metadata as JsonObject } : {}),
    },
    errors: [],
  };
};

const normalizeTimelineCommandInput = (
  input: TimelineCommandInput | unknown,
): { transaction: TimelineCommandTransaction; errors: TimelineCommandValidationError[] } => {
  if (isRecord(input) && Array.isArray(input.commands)) {
    const transactionId = typeof input.transactionId === 'string' ? input.transactionId : undefined;
    const errors: TimelineCommandValidationError[] = [];

    if (input.transactionId !== undefined && typeof input.transactionId !== 'string') {
      errors.push({
        path: '$.transactionId',
        code: 'invalid_transaction_id',
        message: 'transactionId must be a string when present.',
      });
    }

    const commands = input.commands.map((entry, commandIndex) => {
      const normalized = normalizeCommand(entry, commandIndex);
      errors.push(...normalized.errors);
      return normalized.command;
    }).filter((entry): entry is TimelineCommand => entry !== null);

    if (input.commands.length === 0) {
      errors.push({
        path: '$.commands',
        code: 'empty_transaction',
        message: 'Transaction must include at least one command.',
      });
    }

    return {
      transaction: {
        ...(transactionId ? { transactionId } : {}),
        commands,
      },
      errors,
    };
  }

  const normalized = normalizeCommand(input, 0);
  return {
    transaction: {
      commands: normalized.command ? [normalized.command] : [],
    },
    errors: normalized.errors,
  };
};

const toCommandError = (
  error: TimelineCommandValidationError,
  transaction: TimelineCommandTransaction,
): TimelineCommandError => ({
  code: error.code === 'invalid_command' || error.code.startsWith('invalid_command_')
    ? 'invalid_command'
    : 'invalid_transaction',
  message: error.message,
  path: error.path,
  transactionId: transaction.transactionId,
  detail: error.detail,
  validationErrors: [error],
});

const toExecutionError = (
  params: Omit<TimelineCommandError, 'path'> & { path?: string },
): TimelineCommandError => ({
  path: params.path ?? '$',
  ...params,
});

const asErrorMessage = (error: unknown): string => {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return String(error);
};

const withPinnedShotGroups = (
  config: TimelineData['config'],
  pinnedShotGroups: TimelineData['config']['pinnedShotGroups'],
): TimelineData['config'] => ({
  ...config,
  pinnedShotGroups: pinnedShotGroups && pinnedShotGroups.length > 0
    ? pinnedShotGroups
    : undefined,
});

export const applyTimelineCommandEffect = (
  current: TimelineData,
  effect: TimelineCommandEffect,
): TimelineData => {
  switch (effect.mutation.type) {
    case 'data': {
      validateSerializedConfig(effect.mutation.data.config);
      return effect.mutation.data;
    }
    case 'config': {
      validateSerializedConfig(effect.mutation.config);
      return preserveUploadingClips(
        current,
        buildDataFromCurrentRegistry(effect.mutation.config, current),
      );
    }
    case 'resolved-config': {
      const config = serializeForDisk(
        effect.mutation.resolvedConfig,
        effect.mutation.pinnedShotGroupsOverride ?? current.config.pinnedShotGroups,
      );

      return preserveUploadingClips(
        current,
        buildDataFromCurrentRegistry(config, current),
      );
    }
    case 'pinnedShotGroups': {
      return preserveUploadingClips(
        current,
        buildDataFromCurrentRegistry(
          withPinnedShotGroups(current.config, effect.mutation.pinnedShotGroups),
          current,
        ),
      );
    }
    case 'rows': {
      const nextMeta: Record<string, ClipMeta> = { ...current.meta };

      if (effect.mutation.metaUpdates) {
        for (const [clipId, patch] of Object.entries(effect.mutation.metaUpdates)) {
          nextMeta[clipId] = nextMeta[clipId]
            ? { ...nextMeta[clipId], ...patch }
            : (patch as ClipMeta);
        }
      }

      if (effect.mutation.metaDeletes) {
        for (const clipId of effect.mutation.metaDeletes) {
          delete nextMeta[clipId];
        }
      }

      const nextConfig = rowsToConfig(
        effect.mutation.rows,
        nextMeta,
        current.output,
        effect.mutation.clipOrderOverride
          ?? buildTrackClipOrder(current.tracks, current.clipOrder, effect.mutation.metaDeletes),
        current.tracks,
        effect.mutation.pinnedShotGroupsOverride ?? current.config.pinnedShotGroups,
        current.config,
      );

      return preserveUploadingClips(
        { ...current, rows: effect.mutation.rows, meta: nextMeta } as TimelineData,
        buildDataFromCurrentRegistry(nextConfig, current),
      );
    }
  }
};

export const createTimelineCommandRegistry = <
  TCommand extends TimelineCommand = TimelineCommand,
>(
  descriptors: readonly TimelineCommandDescriptor<TCommand>[],
): TimelineCommandRegistry<TCommand> => {
  const registry = new Map<string, TimelineCommandDescriptor<TCommand>>();

  for (const descriptor of descriptors) {
    if (registry.has(descriptor.type)) {
      throw new Error(`Duplicate timeline command descriptor registered for "${descriptor.type}".`);
    }

    registry.set(descriptor.type, descriptor);
  }

  return registry;
};

type RunTimelineCommandInternalArgs<TCommand extends TimelineCommand = TimelineCommand> = {
  data: TimelineData;
  transaction: TimelineCommandTransaction<TCommand>;
  registry: TimelineCommandRegistry<TCommand>;
  runMode: TimelineCommandRunMode;
  executionMode: TimelineCommandExecutionMode;
  maxErrors: number;
};

const runTimelineCommandsInternal = <TCommand extends TimelineCommand = TimelineCommand>({
  data,
  transaction,
  registry,
  runMode,
  executionMode,
  maxErrors,
}: RunTimelineCommandInternalArgs<TCommand>): TimelineCommandExecutionResult<TCommand> => {
  const normalizedTransaction = transaction;
  let workingData = data;
  const commandResults: TimelineCommandStepResult<TCommand>[] = [];
  const errors: TimelineCommandError[] = [];

  for (let commandIndex = 0; commandIndex < normalizedTransaction.commands.length; commandIndex += 1) {
    const command = normalizedTransaction.commands[commandIndex];
    const descriptor = registry.get(command.type);

    if (!descriptor) {
      const error = toExecutionError({
        code: 'unknown_command',
        message: `No timeline command descriptor is registered for "${command.type}".`,
        path: `$.commands[${commandIndex}].type`,
        transactionId: normalizedTransaction.transactionId,
        commandType: command.type,
        commandId: command.commandId,
        commandIndex,
      });
      commandResults.push({
        command,
        commandIndex,
        status: 'failed',
        beforeSignature: workingData.stableSignature,
        afterSignature: workingData.stableSignature,
        inverse: null,
        error,
      });
      errors.push(error);
    } else {
      const context: TimelineCommandContext<TCommand> = {
        command,
        currentData: workingData,
        commandIndex,
        transaction: normalizedTransaction,
        previousResults: commandResults,
      };

      try {
        const validationErrors = descriptor.validate(context) ?? [];
        if (validationErrors.length > 0) {
          const error = toExecutionError({
            code: 'validation_failed',
            message: `Timeline command "${command.type}" failed validation.`,
            path: `$.commands[${commandIndex}]`,
            transactionId: normalizedTransaction.transactionId,
            commandType: command.type,
            commandId: command.commandId,
            commandIndex,
            validationErrors: [...validationErrors],
          });

          commandResults.push({
            command,
            commandIndex,
            status: 'failed',
            beforeSignature: workingData.stableSignature,
            afterSignature: workingData.stableSignature,
            inverse: null,
            error,
          });
          errors.push(error);
        } else {
          const effect = runMode === 'apply'
            ? descriptor.apply(context)
            : descriptor.dryRun(context);
          const nextData = applyTimelineCommandEffect(workingData, effect);
          let inverse: TimelineCommandTransaction | null = null;

          try {
            const inverseInput = descriptor.invert({
              ...context,
              nextData,
              effect,
            });
            if (inverseInput) {
              const normalizedInverse = normalizeTimelineCommandInput(inverseInput);
              if (normalizedInverse.errors.length > 0) {
                throw new Error(normalizedInverse.errors.map((error) => error.message).join(' '));
              }
              inverse = normalizedInverse.transaction;
            }
          } catch (error) {
            const executionError = toExecutionError({
              code: 'invert_failed',
              message: `Timeline command "${command.type}" could not produce an inverse transaction: ${asErrorMessage(error)}`,
              path: `$.commands[${commandIndex}]`,
              transactionId: normalizedTransaction.transactionId,
              commandType: command.type,
              commandId: command.commandId,
              commandIndex,
            });
            commandResults.push({
              command,
              commandIndex,
              status: 'failed',
              beforeSignature: workingData.stableSignature,
              afterSignature: workingData.stableSignature,
              inverse: null,
              error: executionError,
            });
            errors.push(executionError);
            if (executionMode === 'atomic') {
              break;
            }
            continue;
          }

          commandResults.push({
            command,
            commandIndex,
            status: runMode === 'apply'
              ? 'applied'
              : runMode === 'dry_run'
                ? 'dry_run'
                : 'validated',
            beforeSignature: workingData.stableSignature,
            afterSignature: nextData.stableSignature,
            summary: effect.summary,
            detail: effect.detail,
            inverse,
          });
          workingData = nextData;
        }
      } catch (error) {
        const executionError = toExecutionError({
          code: runMode === 'apply' ? 'apply_failed' : 'dry_run_failed',
          message: `Timeline command "${command.type}" failed during ${runMode === 'apply' ? 'apply' : 'dry run'}: ${asErrorMessage(error)}`,
          path: `$.commands[${commandIndex}]`,
          transactionId: normalizedTransaction.transactionId,
          commandType: command.type,
          commandId: command.commandId,
          commandIndex,
        });
        commandResults.push({
          command,
          commandIndex,
          status: 'failed',
          beforeSignature: workingData.stableSignature,
          afterSignature: workingData.stableSignature,
          inverse: null,
          error: executionError,
        });
        errors.push(executionError);
      }
    }

    if (errors.length > 0 && executionMode === 'atomic') {
      break;
    }

    if (errors.length >= maxErrors) {
      break;
    }
  }

  const succeededResults = commandResults.filter((result) => result.error === undefined);
  const shouldRollback = executionMode === 'atomic' && errors.length > 0;
  const committedResults = shouldRollback ? [] : succeededResults;
  const inverseCommands = committedResults
    .slice()
    .reverse()
    .flatMap((result) => result.inverse?.commands ?? []);
  const canInvert = committedResults.length > 0 && committedResults.every((result) => result.inverse !== null);
  const inverseTransaction = canInvert
    ? {
        ...(normalizedTransaction.transactionId ? { transactionId: `${normalizedTransaction.transactionId}:undo` } : {}),
        commands: inverseCommands,
      }
    : null;

  const history: TimelineCommandHistoryMetadata = {
    kind: 'command',
    transactionId: normalizedTransaction.transactionId,
    commandTypes: committedResults.map((result) => result.command.type),
    commandIds: committedResults
      .map((result) => result.command.commandId)
      .filter((commandId): commandId is string => typeof commandId === 'string'),
    strategy: inverseTransaction ? 'inverse_transaction' : 'snapshot_fallback',
    inverseTransaction,
    executionMode,
    runMode,
    appliedCount: committedResults.length,
    failedCount: errors.length,
    partial: executionMode === 'compat_partial' && errors.length > 0 && committedResults.length > 0,
  };

  return {
    status: errors.length === 0
      ? 'ok'
      : committedResults.length > 0
        ? 'partial'
        : 'rejected',
    transaction: normalizedTransaction,
    runMode,
    executionMode,
    initialData: data,
    nextData: shouldRollback ? data : workingData,
    commandResults,
    errors,
    history,
  };
};

export const runTimelineCommands = <TCommand extends TimelineCommand = TimelineCommand>(
  data: TimelineData,
  input: TimelineCommandInput<TCommand> | unknown,
  registry: TimelineCommandRegistry<TCommand>,
  runMode: TimelineCommandRunMode,
  options: TimelineCommandRunOptions = {},
): TimelineCommandExecutionResult<TCommand> => {
  const normalized = normalizeTimelineCommandInput(input);
  const normalizationErrors = normalized.errors.map((error) => toCommandError(error, normalized.transaction));

  if (normalizationErrors.length > 0) {
    return {
      status: 'rejected',
      transaction: normalized.transaction as TimelineCommandTransaction<TCommand>,
      runMode,
      executionMode: options.executionMode ?? DEFAULT_EXECUTION_MODE,
      initialData: data,
      nextData: data,
      commandResults: [],
      errors: normalizationErrors,
      history: {
        kind: 'command',
        transactionId: normalized.transaction.transactionId,
        commandTypes: [],
        commandIds: [],
        strategy: 'snapshot_fallback',
        inverseTransaction: null,
        executionMode: options.executionMode ?? DEFAULT_EXECUTION_MODE,
        runMode,
        appliedCount: 0,
        failedCount: normalizationErrors.length,
        partial: false,
      },
    };
  }

  return runTimelineCommandsInternal({
    data,
    transaction: normalized.transaction as TimelineCommandTransaction<TCommand>,
    registry,
    runMode,
    executionMode: options.executionMode ?? DEFAULT_EXECUTION_MODE,
    maxErrors: options.maxErrors ?? DEFAULT_MAX_ERRORS,
  });
};

export const createTimelineCommandRunner = <
  TCommand extends TimelineCommand = TimelineCommand,
>(
  registryInput: TimelineCommandRegistry<TCommand> | readonly TimelineCommandDescriptor<TCommand>[],
): TimelineCommandRunner<TCommand> => {
  const registry = registryInput instanceof Map
    ? registryInput
    : createTimelineCommandRegistry(registryInput);

  return {
    registry,
    validate: (data, input, options) => runTimelineCommands(data, input, registry, 'validate', options),
    dryRun: (data, input, options) => runTimelineCommands(data, input, registry, 'dry_run', options),
    apply: (data, input, options) => runTimelineCommands(data, input, registry, 'apply', options),
  };
};
