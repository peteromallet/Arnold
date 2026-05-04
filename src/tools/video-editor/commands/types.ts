import type { ClipMeta, ClipOrderMap, TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas';

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];
export type JsonObject = { [key: string]: JsonValue };

export type TimelineCommand<
  TType extends string = string,
  TPayload extends JsonObject = JsonObject,
> = {
  type: TType;
  payload?: TPayload;
  commandId?: string;
  metadata?: JsonObject;
};

export type TimelineCommandTransaction<TCommand extends TimelineCommand = TimelineCommand> = {
  transactionId?: string;
  commands: readonly TCommand[];
};

export type TimelineCommandInput<TCommand extends TimelineCommand = TimelineCommand> =
  | TCommand
  | TimelineCommandTransaction<TCommand>;

export type TimelineCommandExecutionMode = 'atomic' | 'compat_partial';
export type TimelineCommandRunMode = 'validate' | 'dry_run' | 'apply';

export type TimelineCommandValidationError = {
  path: string;
  code: string;
  message: string;
  detail?: JsonValue;
};

export type TimelineCommandErrorCode =
  | 'invalid_command'
  | 'invalid_transaction'
  | 'unknown_command'
  | 'validation_failed'
  | 'dry_run_failed'
  | 'apply_failed'
  | 'invert_failed';

export type TimelineCommandError = {
  code: TimelineCommandErrorCode;
  message: string;
  path: string;
  transactionId?: string;
  commandType?: string;
  commandId?: string;
  commandIndex?: number;
  validationErrors?: TimelineCommandValidationError[];
  detail?: JsonValue;
};

export type TimelineCommandMutation =
  | {
      type: 'rows';
      rows: TimelineRow[];
      metaUpdates?: Record<string, Partial<ClipMeta>>;
      metaDeletes?: string[];
      clipOrderOverride?: ClipOrderMap;
      pinnedShotGroupsOverride?: TimelineData['config']['pinnedShotGroups'];
    }
  | {
      type: 'config';
      config: TimelineData['config'];
    }
  | {
      type: 'resolved-config';
      resolvedConfig: TimelineData['resolvedConfig'];
      pinnedShotGroupsOverride?: TimelineData['config']['pinnedShotGroups'];
    }
  | {
      type: 'pinnedShotGroups';
      pinnedShotGroups: NonNullable<TimelineData['config']['pinnedShotGroups']>;
    }
  | {
      type: 'data';
      data: TimelineData;
    };

export type TimelineCommandEffect = {
  mutation: TimelineCommandMutation;
  summary?: string;
  detail?: JsonObject;
};

export type TimelineCommandContext<TCommand extends TimelineCommand = TimelineCommand> = {
  command: TCommand;
  currentData: TimelineData;
  commandIndex: number;
  transaction: TimelineCommandTransaction<TCommand>;
  previousResults: readonly TimelineCommandStepResult<TCommand>[];
};

export type TimelineCommandInvertContext<TCommand extends TimelineCommand = TimelineCommand> = {
  command: TCommand;
  currentData: TimelineData;
  nextData: TimelineData;
  effect: TimelineCommandEffect;
  commandIndex: number;
  transaction: TimelineCommandTransaction<TCommand>;
  previousResults: readonly TimelineCommandStepResult<TCommand>[];
};

export type TimelineCommandDescriptor<TCommand extends TimelineCommand = TimelineCommand> = {
  type: TCommand['type'];
  validate: (
    context: TimelineCommandContext<TCommand>,
  ) => readonly TimelineCommandValidationError[] | null | undefined;
  dryRun: (context: TimelineCommandContext<TCommand>) => TimelineCommandEffect;
  apply: (context: TimelineCommandContext<TCommand>) => TimelineCommandEffect;
  invert: (
    context: TimelineCommandInvertContext<TCommand>,
  ) => TimelineCommandInput | null | undefined;
};

export type TimelineCommandRegistry<TCommand extends TimelineCommand = TimelineCommand> =
  ReadonlyMap<string, TimelineCommandDescriptor<TCommand>>;

export type TimelineCommandStepStatus =
  | 'validated'
  | 'dry_run'
  | 'applied'
  | 'failed';

export type TimelineCommandStepResult<TCommand extends TimelineCommand = TimelineCommand> = {
  command: TCommand;
  commandIndex: number;
  status: TimelineCommandStepStatus;
  beforeSignature: string;
  afterSignature: string;
  summary?: string;
  detail?: JsonObject;
  inverse: TimelineCommandTransaction | null;
  error?: TimelineCommandError;
};

export type TimelineCommandHistoryStrategy =
  | 'inverse_transaction'
  | 'snapshot_fallback';

export type TimelineCommandHistoryMetadata = {
  kind: 'command';
  transactionId?: string;
  commandTypes: string[];
  commandIds: string[];
  strategy: TimelineCommandHistoryStrategy;
  inverseTransaction: TimelineCommandTransaction | null;
  executionMode: TimelineCommandExecutionMode;
  runMode: TimelineCommandRunMode;
  appliedCount: number;
  failedCount: number;
  partial: boolean;
};

export type TimelineCommandExecutionStatus = 'ok' | 'partial' | 'rejected';

export type TimelineCommandExecutionResult<TCommand extends TimelineCommand = TimelineCommand> = {
  status: TimelineCommandExecutionStatus;
  transaction: TimelineCommandTransaction<TCommand>;
  runMode: TimelineCommandRunMode;
  executionMode: TimelineCommandExecutionMode;
  initialData: TimelineData;
  nextData: TimelineData;
  commandResults: TimelineCommandStepResult<TCommand>[];
  errors: TimelineCommandError[];
  history: TimelineCommandHistoryMetadata;
};

export type TimelineCommandRunOptions = {
  executionMode?: TimelineCommandExecutionMode;
  maxErrors?: number;
};

export type TimelineCommandRunner<TCommand extends TimelineCommand = TimelineCommand> = {
  registry: TimelineCommandRegistry<TCommand>;
  validate: (
    data: TimelineData,
    input: TimelineCommandInput<TCommand> | unknown,
    options?: TimelineCommandRunOptions,
  ) => TimelineCommandExecutionResult<TCommand>;
  dryRun: (
    data: TimelineData,
    input: TimelineCommandInput<TCommand> | unknown,
    options?: TimelineCommandRunOptions,
  ) => TimelineCommandExecutionResult<TCommand>;
  apply: (
    data: TimelineData,
    input: TimelineCommandInput<TCommand> | unknown,
    options?: TimelineCommandRunOptions,
  ) => TimelineCommandExecutionResult<TCommand>;
};
