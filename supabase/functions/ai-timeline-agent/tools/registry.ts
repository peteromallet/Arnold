import { parseCommand, validateCommand, type ParsedCommand } from "../command-parser.ts";
import { loadTimelineState, saveTimelineConfigVersioned } from "../db.ts";
import {
  buildTimelineCommandData,
  createTimelineCommandRunner,
  MEDIA_COMMAND_DESCRIPTORS,
  provisionTimelineMedia,
  type AssetRegistryEntry,
  type AddMediaCommand,
  type JsonObject,
  type SwapMediaCommand,
  type TimelineCommand,
  type TimelineCommandDescriptor,
  type TimelineCommandExecutionResult,
  type TimelineCommandInput,
  type TimelineCommandRunMode,
  type TimelineCommandTransaction,
} from "../../../../src/tools/video-editor/index.ts";
import type {
  EdgeProposal,
  SupabaseAdmin,
  TimelineState,
  ToolResult,
} from "../types.ts";
import {
  addTextClip,
  deleteClip,
  duplicateClip,
  findIssues,
  moveClip,
  queryTimeline,
  setClipParams,
  setClipProperty,
  setTextContent,
  setTheme,
  setThemeOverrides,
  splitClip,
  trimClip,
  viewTimeline,
} from "./timeline.ts";
import { createGenerationTask } from "./generation.ts";

type MoveCommand = TimelineCommand<'move', { clipId: string; at: number }>;
type SplitCommand = TimelineCommand<'split', { clipId: string; time: number }>;
type TrimCommand = TimelineCommand<'trim', { clipId: string; from?: number; to?: number; duration?: number }>;
type DeleteCommand = TimelineCommand<'delete', { clipId: string }>;
type SetPropertyCommand = TimelineCommand<'set', { clipId: string; property: string; value: number }>;
type AddTextCommand = TimelineCommand<'add-text', { track: string; at: number; duration: number; text: string }>;
type SetTextCommand = TimelineCommand<'set-text', { clipId: string; text: string }>;
type DuplicateCommand = TimelineCommand<'duplicate', { clipId: string; count: number }>;
type SetParamsCommand = TimelineCommand<'set-params', { clipId: string; params: JsonObject }>;
type SetThemeCommand = TimelineCommand<'set-theme', { themeId: string }>;
type SetThemeOverridesCommand = TimelineCommand<'set-theme-overrides', { overrides: JsonObject }>;

type AgentMutationCommand =
  | AddMediaCommand
  | SwapMediaCommand
  | MoveCommand
  | SplitCommand
  | TrimCommand
  | DeleteCommand
  | SetPropertyCommand
  | AddTextCommand
  | SetTextCommand
  | DuplicateCommand
  | SetParamsCommand
  | SetThemeCommand
  | SetThemeOverridesCommand;

type RunToolArgs = {
  command?: string;
  transaction?: TimelineCommandInput<AgentMutationCommand> | unknown;
  mode?: TimelineCommandRunMode | "proposal";
};

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null && !Array.isArray(value);
};

const isToolFailureMessage = (message: string): boolean => {
  const normalized = message.toLowerCase();
  return normalized.includes("not found")
    || normalized.includes("does not exist")
    || normalized.includes("requires")
    || normalized.includes("must be")
    || normalized.includes("invalid")
    || normalized.includes("failed")
    || normalized.includes("unknown")
    || normalized.includes("cannot")
    || normalized.includes("exceeds")
    || normalized.includes("only accepts");
};

function createConfigDescriptor<TCommand extends AgentMutationCommand>(
  type: TCommand["type"],
  execute: (
    state: Pick<TimelineState, "config" | "registry">,
    payload: TCommand["payload"],
  ) => ToolResult,
): TimelineCommandDescriptor<TCommand> {
  return {
    type,
    validate: (context) => {
      const result = execute({
        config: context.currentData.config,
        registry: context.currentData.registry,
      }, (context.command.payload ?? {}) as TCommand["payload"]);

      if (!result.config && isToolFailureMessage(result.result)) {
        return [{
          path: `$.commands[${context.commandIndex}]`,
          code: "invalid_command",
          message: result.result,
        }];
      }

      return [];
    },
    dryRun: (context) => {
      const result = execute({
        config: context.currentData.config,
        registry: context.currentData.registry,
      }, (context.command.payload ?? {}) as TCommand["payload"]);

      if (!result.config) {
        if (isToolFailureMessage(result.result)) {
          throw new Error(result.result);
        }

        return {
          mutation: {
            type: "data",
            data: context.currentData,
          },
          summary: result.result,
        };
      }

      return {
        mutation: {
          type: "config",
          config: result.config,
        },
        summary: result.result,
      };
    },
    apply: (context) => {
      const result = execute({
        config: context.currentData.config,
        registry: context.currentData.registry,
      }, (context.command.payload ?? {}) as TCommand["payload"]);

      if (!result.config) {
        if (isToolFailureMessage(result.result)) {
          throw new Error(result.result);
        }

        return {
          mutation: {
            type: "data",
            data: context.currentData,
          },
          summary: result.result,
        };
      }

      return {
        mutation: {
          type: "config",
          config: result.config,
        },
        summary: result.result,
      };
    },
    invert: () => null,
  };
}

const agentCommandRunner = createTimelineCommandRunner<AgentMutationCommand>([
  ...(MEDIA_COMMAND_DESCRIPTORS as readonly TimelineCommandDescriptor<AgentMutationCommand>[]),
  createConfigDescriptor("move", (state, payload) => moveClip(state.config, state.registry, payload)),
  createConfigDescriptor("split", (state, payload) => splitClip(state.config, state.registry, payload)),
  createConfigDescriptor("trim", (state, payload) => trimClip(state.config, state.registry, payload)),
  createConfigDescriptor("delete", (state, payload) => deleteClip(state.config, state.registry, payload)),
  createConfigDescriptor("set", (state, payload) => setClipProperty(state.config, state.registry, payload)),
  createConfigDescriptor("add-text", (state, payload) => addTextClip(state.config, state.registry, payload)),
  createConfigDescriptor("set-text", (state, payload) => setTextContent(state.config, state.registry, payload)),
  createConfigDescriptor("duplicate", (state, payload) => duplicateClip(state.config, state.registry, payload)),
  createConfigDescriptor("set-params", (state, payload) => setClipParams(state.config, state.registry, payload)),
  createConfigDescriptor("set-theme", (state, payload) => setTheme(state.config, state.registry, payload)),
  createConfigDescriptor("set-theme-overrides", (state, payload) => setThemeOverrides(state.config, state.registry, payload)),
]);

const formatExecutionResult = (
  result: TimelineCommandExecutionResult<AgentMutationCommand>,
  runMode: TimelineCommandRunMode,
  preserveSingleSummary = false,
): string => {
  const successfulResults = result.commandResults.filter((entry) => entry.error === undefined);
  if (
    preserveSingleSummary
    && runMode === "apply"
    && result.errors.length === 0
    && successfulResults.length === 1
    && successfulResults[0]?.summary
  ) {
    return successfulResults[0].summary;
  }

  const verb = runMode === "validate"
    ? "Validated"
    : runMode === "dry_run"
      ? "Dry ran"
      : "Applied";
  const lines = [`${verb} ${successfulResults.length}/${result.transaction.commands.length} command(s).`];

  for (let index = 0; index < result.commandResults.length; index += 1) {
    const step = result.commandResults[index];
    if (step.summary) {
      lines.push(`${index + 1}. ${step.summary}`);
      continue;
    }

    if (step.error) {
      const validationMessage = step.error.validationErrors?.[0]?.message;
      lines.push(`${index + 1}. ${validationMessage ?? step.error.message}`);
    }
  }

  for (const error of result.errors) {
    if (result.commandResults.some((step) => step.error === error)) {
      continue;
    }
    const validationMessage = error.validationErrors?.[0]?.message;
    lines.push(validationMessage ?? error.message);
  }

  return lines.join("\n");
};

/** Proposal-compatible patch operation produced by the registry. */
interface ProposalPatchOperation {
  op: string;
  target: string;
  payload?: Record<string, unknown>;
  order?: number;
}

/** Proposal-compatible patch produced by the registry. */
interface ProposalPatch {
  version: number;
  operations: readonly ProposalPatchOperation[];
  source?: string;
  meta?: Record<string, unknown>;
}

/** Proposal metadata returned alongside patches. */
interface ProposalMetadata {
  rationale: string;
  source: string;
  baseVersion: number;
  /** Parsed summary of the proposed change. */
  summary: string;
}

/** Result type for proposal mode — patches + metadata, no config saved. */
interface ProposalResult {
  patches: ProposalPatch[];
  metadata: ProposalMetadata;
}

const PROPOSAL_SUPPORTED_COMMANDS_FOR_PATCHES = new Set<string>([
  "move",
  "split",
  "trim",
  "delete",
  "set",
  "add-text",
  "set-text",
  "duplicate",
  "set-params",
  "set-theme",
  "set-theme-overrides",
  "add-media",
  "swap",
]);

/**
 * Convert a parsed mutation command to a ProposalPatchOperation.
 * Returns null for unsupported or error-typed commands.
 */
function parsedCommandToProposalPatchOp(
  parsed: ParsedCommand,
): ProposalPatchOperation | null {
  switch (parsed.type) {
    case "move":
      return {
        op: "clip.move",
        target: parsed.clipId,
        payload: { at: parsed.at },
      };
    case "split":
      return {
        op: "clip.split",
        target: parsed.clipId,
        payload: { time: parsed.time },
      };
    case "trim":
      return {
        op: "clip.update",
        target: parsed.clipId,
        payload: Object.fromEntries(
          Object.entries({
            from: parsed.from,
            to: parsed.to,
            duration: parsed.duration,
          }).filter(([, v]) => v !== undefined),
        ) as Record<string, unknown>,
      };
    case "delete":
      return {
        op: "clip.remove",
        target: parsed.clipId,
      };
    case "set":
      return {
        op: "clip.update",
        target: parsed.clipId,
        payload: { [parsed.property]: parsed.value },
      };
    case "add-text":
      return {
        op: "clip.add",
        target: parsed.track,
        payload: { at: parsed.at, duration: parsed.duration, text: parsed.text },
      };
    case "set-text":
      return {
        op: "clip.update",
        target: parsed.clipId,
        payload: { text: parsed.text },
      };
    case "duplicate":
      return {
        op: "clip.add",
        target: parsed.clipId,
        payload: { count: parsed.count },
      };
    case "add-media":
      return {
        op: "clip.add",
        target: parsed.track,
        payload: {
          at: parsed.at,
          generationId: parsed.generationId,
          url: parsed.url,
          mediaType: parsed.mediaType,
        },
      };
    case "swap":
      return {
        op: "clip.update",
        target: parsed.clipId,
        payload: {
          generationId: parsed.generationId,
          url: parsed.url,
          mediaType: parsed.mediaType,
        },
      };
    default:
      return null;
  }
}

/**
 * Build a human-readable summary for a proposal patch operation.
 */
function proposalPatchOpSummary(op: ProposalPatchOperation): string {
  const payload = op.payload ?? {};
  switch (op.op) {
    case "clip.move":
      return `Move clip "${op.target}" to ${payload.at ?? "?"}s`;
    case "clip.split":
      return `Split clip "${op.target}" at ${payload.time ?? "?"}s`;
    case "clip.update":
      return `Update clip "${op.target}": ${JSON.stringify(payload)}`;
    case "clip.remove":
      return `Delete clip "${op.target}"`;
    case "clip.add":
      return `Add clip to track "${op.target}": ${JSON.stringify(payload)}`;
    case "app.update":
      return `Update app setting "${op.target}": ${JSON.stringify(payload)}`;
    default:
      return `${op.op} on "${op.target}"`;
  }
}

/**
 * Execute a command in proposal mode.
 *
 * Runs validation (dry-run) for the supported subset, converts to
 * TimelinePatch[]-compatible proposal patches with metadata, and returns
 * without saving timeline config.
 *
 * Read-only commands (view, query, find-issues) execute normally and
 * return their usual result text alongside empty patches.
 */
async function executeProposal(
  runArgs: RunToolArgs,
  state: TimelineState,
  timelineId: string,
  supabaseAdmin: SupabaseAdmin,
): Promise<ToolResult> {
  const patches: ProposalPatch[] = [];
  const summaries: string[] = [];

  // --- Handle transaction input ---
  if (typeof runArgs.transaction !== "undefined") {
    const transaction = await normalizeTransactionInput(
      runArgs.transaction,
      state,
      timelineId,
      supabaseAdmin,
    );

    for (const command of transaction.commands) {
      // We can't directly convert typed commands back to ParsedCommand,
      // so we use the command type and payload to build patch ops.
      const cmdType = command.type as string;
      if (!PROPOSAL_SUPPORTED_COMMANDS_FOR_PATCHES.has(cmdType)) {
        return {
          result: `Proposal mode does not support command type "${cmdType}" in transactions.`,
        };
      }

      const op: ProposalPatchOperation = {
        op: mapCommandTypeToPatchOp(cmdType),
        target: extractTargetFromCommand(command),
        payload: (command.payload ?? {}) as Record<string, unknown>,
      };
      summaries.push(proposalPatchOpSummary(op));

      patches.push({
        version: state.configVersion,
        operations: [op],
        source: `ai-timeline-agent/proposal#${cmdType}`,
      });
    }
  } else if (typeof runArgs.command === "string" && runArgs.command.trim().length > 0) {
    // --- Handle string command ---
    const parsed = parseCommand(runArgs.command);

    if (parsed.type === "error") {
      return { result: parsed.message };
    }

    const validationError = validateCommand(parsed, state.config, state.registry);
    if (validationError) {
      return { result: validationError };
    }

    // Read-only commands: execute normally, return info with empty patches
    if (
      parsed.type === "view" ||
      parsed.type === "query" ||
      parsed.type === "find-issues"
    ) {
      let readResult: ToolResult;
      if (parsed.type === "view") {
        readResult = viewTimeline(state.config, state.registry, state.shotNamesById);
      } else if (parsed.type === "query") {
        readResult = queryTimeline(state.config, state.registry);
      } else {
        readResult = findIssues(state.config, state.registry);
      }

      return {
        result: `[PROPOSAL MODE — read-only, no patches]\n${readResult.result}`,
      };
    }

    // Unsupported command types in proposal mode
    if (!PROPOSAL_SUPPORTED_COMMANDS_FOR_PATCHES.has(parsed.type)) {
      return {
        result: `Proposal mode does not support command type "${parsed.type}". Supported types: ${Array.from(PROPOSAL_SUPPORTED_COMMANDS_FOR_PATCHES).join(", ")}.`,
      };
    }

    const op = parsedCommandToProposalPatchOp(parsed);
    if (!op) {
      return { result: `Could not convert command "${parsed.type}" to a proposal patch.` };
    }

    summaries.push(proposalPatchOpSummary(op));

    patches.push({
      version: state.configVersion,
      operations: [op],
      source: `ai-timeline-agent/proposal#${parsed.type}`,
    });
  } else {
    return { result: "Proposal mode requires a command string or transaction object." };
  }

  // Build proposal metadata
  const metadata: ProposalMetadata = {
    rationale: `Proposed by ai-timeline-agent at config version ${state.configVersion}. ${summaries.join("; ")}`,
    source: "ai-timeline-agent/proposal",
    baseVersion: state.configVersion,
    summary: summaries.join("\n"),
  };

  // Build structured EdgeProposal[] for client consumption.
  // Each ProposalPatch maps to a single EdgeProposal.
  const defaultExpiresAt = Date.now() + 5 * 60 * 1000; // 5-minute TTL
  const proposals: EdgeProposal[] = patches.map((patch, index) => ({
    id: `proposal-${crypto.randomUUID().slice(0, 8)}`,
    source: patch.source ?? metadata.source,
    rationale: index === 0 ? metadata.rationale : undefined,
    state: "pending" as const,
    baseVersion: metadata.baseVersion,
    expiresAt: defaultExpiresAt,
    patch: {
      version: patch.version,
      operations: patch.operations.map((op) => ({
        op: op.op,
        target: op.target,
        ...(op.payload !== undefined ? { payload: op.payload } : {}),
      })),
    },
  }));

  // Return proposal result — no config saved
  return {
    result: `[PROPOSAL — not applied]\n${metadata.summary}\n\nBase version: ${metadata.baseVersion}\nPatches: ${patches.length}`,
    config: state.config, // Return current config as-is (unchanged)
    proposals,
  };
}

/** Map a command type string to a TimelinePatchOpFamily. */
function mapCommandTypeToPatchOp(cmdType: string): string {
  switch (cmdType) {
    case "move":
      return "clip.move";
    case "split":
      return "clip.split";
    case "trim":
    case "set":
    case "set-text":
    case "set-params":
    case "swap":
      return "clip.update";
    case "delete":
      return "clip.remove";
    case "add-text":
    case "add-media":
    case "duplicate":
      return "clip.add";
    case "set-theme":
    case "set-theme-overrides":
      return "app.update";
    default:
      return "extension.noop";
  }
}

/** Extract a target identifier from a typed command for proposal patches. */
function extractTargetFromCommand(command: { type: string; payload?: unknown }): string {
  const payload = command.payload as Record<string, unknown> | undefined;
  if (!payload) return command.type;

  // Prefer clipId, then track, then command type as fallback
  if (typeof payload.clipId === "string") return payload.clipId;
  if (typeof payload.trackId === "string") return payload.trackId;
  if (typeof payload.track === "string") return payload.track;
  if (command.type === "set-theme" || command.type === "set-theme-overrides") {
    return "theme";
  }
  return command.type;
}

const extractMode = (input: RunToolArgs | string): TimelineCommandRunMode | "proposal" => {
  if (typeof input === "string") {
    return "apply";
  }

  if (input.mode === "proposal") return "proposal";
  return input.mode === "validate" || input.mode === "dry_run" ? input.mode : "apply";
};

const registerExternalMediaAsset = async (
  state: TimelineState,
  timelineId: string,
  supabaseAdmin: SupabaseAdmin,
  url: string,
  mediaType: "image" | "video",
  generationId: string,
) => {
  return provisionTimelineMedia({
    kind: "external-media",
    url,
    mediaType,
    generationId,
  }, {
    getAssetEntry: (assetKey) => state.registry.assets?.[assetKey] ?? null,
    registerExternalAsset: async (_source, entry) => {
      const assetKey = `asset-${crypto.randomUUID().slice(0, 6)}`;
      const { error } = await supabaseAdmin.rpc("upsert_asset_registry_entry", {
        p_timeline_id: timelineId,
        p_asset_id: assetKey,
        p_entry: entry,
      }).maybeSingle();
      if (error) {
        throw new Error(`Failed to register asset ${assetKey}: ${error.message}`);
      }

      state.registry = {
        ...state.registry,
        assets: {
          ...state.registry.assets,
          [assetKey]: entry as AssetRegistryEntry,
        },
      };
      return { assetKey };
    },
  });
};

const toTransactionCommand = async (
  parsed: Exclude<ParsedCommand, { type: "error" | "view" | "query" | "find-issues" | "repeat" | "undo" | "generate" }>,
  state: TimelineState,
  timelineId: string,
  supabaseAdmin: SupabaseAdmin,
): Promise<AgentMutationCommand> => {
  switch (parsed.type) {
    case "move":
      return { type: "move", payload: { clipId: parsed.clipId, at: parsed.at } };
    case "split":
      return { type: "split", payload: { clipId: parsed.clipId, time: parsed.time } };
    case "trim":
      return { type: "trim", payload: { clipId: parsed.clipId, ...(parsed.from !== undefined ? { from: parsed.from } : {}), ...(parsed.to !== undefined ? { to: parsed.to } : {}), ...(parsed.duration !== undefined ? { duration: parsed.duration } : {}) } };
    case "delete":
      return { type: "delete", payload: { clipId: parsed.clipId } };
    case "set":
      return { type: "set", payload: { clipId: parsed.clipId, property: parsed.property, value: parsed.value } };
    case "add-text":
      return { type: "add-text", payload: { track: parsed.track, at: parsed.at, duration: parsed.duration, text: parsed.text } };
    case "set-text":
      return { type: "set-text", payload: { clipId: parsed.clipId, text: parsed.text } };
    case "duplicate":
      return { type: "duplicate", payload: { clipId: parsed.clipId, count: parsed.count } };
    case "add-media": {
      const asset = await registerExternalMediaAsset(
        state,
        timelineId,
        supabaseAdmin,
        parsed.url,
        parsed.mediaType,
        parsed.generationId,
      );
      return {
        type: "add-media",
        payload: {
          trackId: parsed.track,
          at: parsed.at,
          asset,
        },
      };
    }
    case "swap": {
      const asset = await registerExternalMediaAsset(
        state,
        timelineId,
        supabaseAdmin,
        parsed.url,
        parsed.mediaType,
        parsed.generationId,
      );
      return {
        type: "swap",
        payload: {
          clipId: parsed.clipId,
          asset,
        },
      };
    }
  }
};

const normalizeTypedCommand = async (
  command: unknown,
  state: TimelineState,
  timelineId: string,
  supabaseAdmin: SupabaseAdmin,
): Promise<AgentMutationCommand> => {
  if (!isRecord(command) || typeof command.type !== "string") {
    throw new Error("Each transaction command must be an object with a string type.");
  }

  if (command.type === "add-media") {
    const payload = isRecord(command.payload) ? command.payload : {};
    if (isRecord(payload.asset)) {
      return command as AgentMutationCommand;
    }

    const trackId = typeof payload.trackId === "string"
      ? payload.trackId
      : typeof payload.track === "string"
        ? payload.track
        : "";
    const at = typeof payload.at === "number" ? payload.at : Number.NaN;
    const generationId = typeof payload.generationId === "string" ? payload.generationId : "";
    const url = typeof payload.url === "string" ? payload.url : "";
    const mediaType = payload.mediaType === "video" ? "video" : "image";
    const asset = await registerExternalMediaAsset(state, timelineId, supabaseAdmin, url, mediaType, generationId);
    return {
      ...command,
      type: "add-media",
      payload: {
        trackId,
        at,
        asset,
      },
    } as AgentMutationCommand;
  }

  if (command.type === "swap") {
    const payload = isRecord(command.payload) ? command.payload : {};
    if (isRecord(payload.asset)) {
      return command as AgentMutationCommand;
    }

    const clipId = typeof payload.clipId === "string" ? payload.clipId : "";
    const generationId = typeof payload.generationId === "string" ? payload.generationId : "";
    const url = typeof payload.url === "string" ? payload.url : "";
    const mediaType = payload.mediaType === "video" ? "video" : "image";
    const asset = await registerExternalMediaAsset(state, timelineId, supabaseAdmin, url, mediaType, generationId);
    return {
      ...command,
      type: "swap",
      payload: {
        clipId,
        asset,
      },
    } as AgentMutationCommand;
  }

  return command as AgentMutationCommand;
};

const normalizeTransactionInput = async (
  input: unknown,
  state: TimelineState,
  timelineId: string,
  supabaseAdmin: SupabaseAdmin,
): Promise<TimelineCommandTransaction<AgentMutationCommand>> => {
  if (!isRecord(input)) {
    throw new Error("run.transaction must be an object.");
  }

  const commandsInput = Array.isArray(input.commands)
    ? input.commands
    : [];
  if (commandsInput.length === 0) {
    throw new Error("run.transaction.commands must contain at least one command.");
  }

  const commands: AgentMutationCommand[] = [];
  for (const command of commandsInput) {
    commands.push(await normalizeTypedCommand(command, state, timelineId, supabaseAdmin));
  }

  return {
    ...(typeof input.transactionId === "string" ? { transactionId: input.transactionId } : {}),
    commands,
  };
};

const executePreparedTransaction = async (
  transaction: TimelineCommandInput<AgentMutationCommand>,
  runMode: TimelineCommandRunMode,
  state: TimelineState,
  timelineId: string,
  supabaseAdmin: SupabaseAdmin,
  preserveSingleSummary = false,
): Promise<ToolResult> => {
  const run = (config = state.config, registry = state.registry) => {
    const currentData = buildTimelineCommandData(config, registry);
    if (runMode === "validate") {
      return agentCommandRunner.validate(currentData, transaction);
    }
    if (runMode === "dry_run") {
      return agentCommandRunner.dryRun(currentData, transaction);
    }
    return agentCommandRunner.apply(currentData, transaction);
  };

  let result = run();
  const formatted = formatExecutionResult(result, runMode, preserveSingleSummary);
  if (runMode !== "apply" || result.status === "rejected") {
    return { result: formatted };
  }

  if (result.nextData.stableSignature === result.initialData.stableSignature) {
    return { result: formatted };
  }

  state.previousConfig = structuredClone(state.config);

  let nextVersion = await saveTimelineConfigVersioned(
    supabaseAdmin,
    timelineId,
    state.configVersion,
    result.nextData.config,
  );

  if (nextVersion !== null) {
    state.config = result.nextData.config;
    state.configVersion = nextVersion;
    return {
      config: state.config,
      result: formatted,
    };
  }

  const refreshedState = await loadTimelineState(supabaseAdmin, timelineId);
  state.config = refreshedState.config;
  state.configVersion = refreshedState.configVersion;
  state.registry = refreshedState.registry;
  state.projectId = refreshedState.projectId;
  state.shotNamesById = refreshedState.shotNamesById;

  result = run(state.config, state.registry);
  const retriedFormatted = `${formatExecutionResult(result, runMode, preserveSingleSummary)} (retried after reload.)`;
  if (result.status === "rejected" || result.nextData.stableSignature === result.initialData.stableSignature) {
    return { result: retriedFormatted };
  }

  nextVersion = await saveTimelineConfigVersioned(
    supabaseAdmin,
    timelineId,
    state.configVersion,
    result.nextData.config,
  );

  if (nextVersion === null) {
    return { result: "Version conflict. Please retry." };
  }

  state.config = result.nextData.config;
  state.configVersion = nextVersion;
  return {
    config: state.config,
    result: retriedFormatted,
  };
};

const handleRepeat = async (
  parsed: Extract<ParsedCommand, { type: "repeat" }>,
  state: TimelineState,
  timelineId: string,
  supabaseAdmin: SupabaseAdmin,
): Promise<ToolResult> => {
  const errorMessages: string[] = [];
  let errors = 0;
  let succeeded = 0;
  let workingConfig = state.config;
  let workingRegistry = state.registry;

  for (let i = 0; i < parsed.count; i += 1) {
    const value = parsed.from + parsed.step * i;
    const roundedValue = Math.round(value * 1000) / 1000;
    const expanded = parsed.template.replace(
      new RegExp(`\\{${parsed.varName}\\}`, "g"),
      String(roundedValue),
    );

    const subParsed = parseCommand(expanded);
    if (subParsed.type === "error") {
      errorMessages.push(`${i + 1}. ${subParsed.message}`);
      errors += 1;
      if (errors >= 3) {
        errorMessages.push("Stopped after 3 errors.");
        break;
      }
      continue;
    }

    const subValidation = validateCommand(subParsed, workingConfig, workingRegistry);
    if (subValidation) {
      errorMessages.push(`${i + 1}. ${subValidation}`);
      errors += 1;
      if (errors >= 3) {
        errorMessages.push("Stopped after 3 errors.");
        break;
      }
      continue;
    }

    if (subParsed.type === "add-media" || subParsed.type === "swap") {
      errorMessages.push(`${i + 1}. ${subParsed.type} is not supported inside repeat.`);
      errors += 1;
      if (errors >= 3) {
        errorMessages.push("Stopped after 3 errors.");
        break;
      }
      continue;
    }

    if (
      subParsed.type === "view"
      || subParsed.type === "query"
      || subParsed.type === "find-issues"
      || subParsed.type === "repeat"
      || subParsed.type === "undo"
      || subParsed.type === "generate"
    ) {
      errorMessages.push(`${i + 1}. No handler for "${subParsed.type}".`);
      errors += 1;
      if (errors >= 3) {
        errorMessages.push("Stopped after 3 errors.");
        break;
      }
      continue;
    }

    const command = await toTransactionCommand(subParsed, {
      ...state,
      config: workingConfig,
      registry: workingRegistry,
    }, timelineId, supabaseAdmin);
    const execution = agentCommandRunner.apply(
      buildTimelineCommandData(workingConfig, workingRegistry),
      { commands: [command] },
    );

    if (execution.status === "rejected") {
      errorMessages.push(`${i + 1}. ${formatExecutionResult(execution, "apply", true)}`);
      errors += 1;
      if (errors >= 3) {
        errorMessages.push("Stopped after 3 errors.");
        break;
      }
      continue;
    }

    succeeded += 1;
    workingConfig = execution.nextData.config;
    workingRegistry = execution.nextData.registry;
  }

  if (succeeded === 0) {
    return {
      result: `Repeated 0/${parsed.count}.${errorMessages.length > 0 ? `\n${errorMessages.join("\n")}` : ""}`,
    };
  }

  state.previousConfig = structuredClone(state.config);
  const nextVersion = await saveTimelineConfigVersioned(
    supabaseAdmin,
    timelineId,
    state.configVersion,
    workingConfig,
  );
  if (nextVersion === null) {
    return { result: `Executed ${succeeded} commands in memory but failed to save — version conflict.` };
  }

  state.config = workingConfig;
  state.registry = workingRegistry;
  state.configVersion = nextVersion;
  return {
    config: state.config,
    result: `Repeated ${succeeded}/${parsed.count}.${errorMessages.length > 0 ? `\n${errorMessages.join("\n")}` : ""}`,
  };
};

const normalizeRunArgs = (input: string | RunToolArgs): RunToolArgs => {
  if (typeof input === "string") {
    return { command: input };
  }

  return input;
};

export async function executeCommand(
  input: string | RunToolArgs,
  state: TimelineState,
  timelineId: string,
  supabaseAdmin: SupabaseAdmin,
): Promise<ToolResult> {
  const runArgs = normalizeRunArgs(input);
  const runMode = extractMode(input);

  // Route proposal mode to the dedicated handler before reaching the standard pipeline
  if (runMode === "proposal") {
    return await executeProposal(runArgs, state, timelineId, supabaseAdmin);
  }

  if (typeof runArgs.transaction !== "undefined") {
    try {
      const transaction = await normalizeTransactionInput(runArgs.transaction, state, timelineId, supabaseAdmin);
      return await executePreparedTransaction(transaction, runMode as TimelineCommandRunMode, state, timelineId, supabaseAdmin);
    } catch (error) {
      return { result: error instanceof Error ? error.message : String(error) };
    }
  }

  if (typeof runArgs.command !== "string" || runArgs.command.trim().length === 0) {
    return { result: "run requires either a command string or a transaction object." };
  }

  const parsed = parseCommand(runArgs.command);
  if (parsed.type === "error") {
    return { result: parsed.message };
  }

  const validationError = validateCommand(parsed, state.config, state.registry);
  if (validationError) {
    return { result: validationError };
  }

  if (parsed.type === "repeat") {
    return await handleRepeat(parsed, state, timelineId, supabaseAdmin);
  }

  if (parsed.type === "generate") {
    return await createGenerationTask({
      project_id: state.projectId,
      prompt: parsed.prompt,
      count: 1,
    });
  }

  if (parsed.type === "undo") {
    if (!state.previousConfig) {
      return { result: "Nothing to undo." };
    }

    const nextVersion = await saveTimelineConfigVersioned(
      supabaseAdmin,
      timelineId,
      state.configVersion,
      state.previousConfig,
    );

    if (nextVersion === null) {
      return { result: "Version conflict. Please retry." };
    }

    const oldConfig = state.config;
    state.config = state.previousConfig;
    state.previousConfig = oldConfig;
    state.configVersion = nextVersion;
    return {
      config: state.config,
      result: "Undid the last timeline change.",
    };
  }

  if (parsed.type === "view" || parsed.type === "query" || parsed.type === "find-issues") {
    if (parsed.type === "view") {
      return viewTimeline(state.config, state.registry, state.shotNamesById);
    }
    if (parsed.type === "query") {
      return queryTimeline(state.config, state.registry);
    }
    return findIssues(state.config, state.registry);
  }

  const transaction = {
    commands: [await toTransactionCommand(parsed, state, timelineId, supabaseAdmin)],
  } satisfies TimelineCommandTransaction<AgentMutationCommand>;
  return await executePreparedTransaction(transaction, runMode, state, timelineId, supabaseAdmin, true);
}
