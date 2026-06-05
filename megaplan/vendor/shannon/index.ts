#!/usr/bin/env bun
// MEGAPLAN_SHANNON_VENDORED v1 — patches: P1..P15

import { randomUUID } from "node:crypto";
import { basename, join, resolve } from "node:path";
import { Command } from "commander";

type OutputFormat = "stream-json" | "json" | "text";

type CliOptions = {
  prompt?: string;
  inputFormat: "text" | "stream-json";
  outputFormat: OutputFormat;
  verbose: boolean;
  replayUserMessages: boolean;
  cwd: string;
  claudeArgs: string[];
};

type JsonRecord = Record<string, unknown>;

type TranscriptRow = JsonRecord & {
  type?: string;
  subtype?: string;
  sessionId?: string;
  session_id?: string;
  cwd?: string;
  uuid?: string;
  timestamp?: string;
  message?: {
    role?: string;
    content?: unknown;
    usage?: JsonRecord;
    model?: string;
    stop_reason?: string | null;
  };
  attachment?: {
    type?: string;
    hookName?: string;
    toolUseID?: string;
    hookEvent?: string;
    content?: string;
    stdout?: string;
    stderr?: string;
    exitCode?: number;
    addedNames?: unknown;
    removedNames?: unknown;
  };
};

type SessionMetadata = {
  sessionId: string;
  projectFolder: string;
  transcriptPath: string;
  tmuxSession: string;
  cwd: string;
};

type SessionDiscovery = {
  meta: SessionMetadata;
  rows: TranscriptRow[];
};

type ShutdownSignal = "SIGINT" | "SIGTERM";

type AssistantDiscovery = {
  row: TranscriptRow;
  rows: TranscriptRow[];
};

const POLL_MS = 100;
const START_TIMEOUT_MS = Number(Bun.env.SHANNON_START_TIMEOUT_MS ?? 20_000);
const TURN_TIMEOUT_MS = Number(Bun.env.SHANNON_TURN_TIMEOUT_MS ?? 900_000);
const WEB_SEARCH_COST_USD = 0.01;
const SEND_DELAY_MIN_MS = Number(Bun.env.SHANNON_SEND_DELAY_MIN_MS ?? 350);
const SEND_DELAY_MAX_MS = Number(Bun.env.SHANNON_SEND_DELAY_MAX_MS ?? 2500);
const TYPE_PROMPT_MAX_CHARS = Number(Bun.env.SHANNON_TYPE_PROMPT_MAX_CHARS ?? 0);

type ModelPricing = {
  inputPerMTok: number;
  outputPerMTok: number;
  contextWindow?: number;
  maxOutputTokens?: number;
};

const MODEL_PRICING: Array<{ pattern: RegExp; pricing: ModelPricing }> = [
  {
    pattern: /claude-haiku-4-5|haiku/i,
    pricing: { inputPerMTok: 1, outputPerMTok: 5, contextWindow: 200_000, maxOutputTokens: 32_000 },
  },
  {
    pattern: /claude-sonnet-(4|3-7)|sonnet/i,
    pricing: { inputPerMTok: 3, outputPerMTok: 15, contextWindow: 200_000, maxOutputTokens: 64_000 },
  },
  {
    pattern: /claude-opus-4-(5|6|7)|opus-(4-5|4-6|4-7)/i,
    pricing: { inputPerMTok: 5, outputPerMTok: 25, contextWindow: 200_000, maxOutputTokens: 32_000 },
  },
  {
    pattern: /claude-opus|opus/i,
    pricing: { inputPerMTok: 15, outputPerMTok: 75, contextWindow: 200_000, maxOutputTokens: 32_000 },
  },
];

export const DEFAULT_CLAUDE_TOOLS = [
  "Task",
  "AskUserQuestion",
  "Bash",
  "CronCreate",
  "CronDelete",
  "CronList",
  "Edit",
  "EnterPlanMode",
  "EnterWorktree",
  "ExitPlanMode",
  "ExitWorktree",
  "Glob",
  "Grep",
  "Monitor",
  "NotebookEdit",
  "PushNotification",
  "Read",
  "RemoteTrigger",
  "ScheduleWakeup",
  "Skill",
  "TaskOutput",
  "TaskStop",
  "TodoWrite",
  "WebFetch",
  "WebSearch",
  "Write",
];

export function parseArgs(argv: string[], cwd = process.cwd()): CliOptions {
  const program = new Command()
    .name("shannon")
    .description("Run a Claude prompt through an interactive Claude CLI session.")
    .exitOverride()
    .allowExcessArguments(false)
    .option("-p, --print <prompt>", "prompt to send to Claude")
    .argument("[prompt]", "prompt to send to Claude")
    .option("--input-format <format>", "input format", "text")
    .option("--output-format <format>", "output format", "stream-json")
    .option("--verbose", "emit verbose stream JSON", false)
    .option("--add-dir <directories...>", "additional directories to allow tool access")
    .option("--agent <agent>", "agent for the current session")
    .option("--agents <json>", "JSON object defining custom agents")
    .option("--allow-dangerously-skip-permissions", "enable bypassing all permission checks as an option")
    .option("--allowedTools, --allowed-tools <tools...>", "tool names to allow")
    .option("--append-system-prompt <prompt>", "append to the default system prompt")
    .option("--bare", "minimal Claude mode")
    .option("--betas <betas...>", "beta headers to include")
    .option("--brief", "enable SendUserMessage tool")
    .option("--chrome", "enable Claude in Chrome integration")
    .option("-c, --continue", "continue the most recent conversation")
    .option("--dangerously-skip-permissions", "bypass all permission checks")
    .option("-d, --debug [filter]", "enable debug mode")
    .option("--debug-file <path>", "write debug logs to a path")
    .option("--disable-slash-commands", "disable all skills")
    .option("--disallowedTools, --disallowed-tools <tools...>", "tool names to deny")
    .option("--effort <level>", "effort level")
    .option("--exclude-dynamic-system-prompt-sections", "exclude dynamic system prompt sections")
    .option("--fallback-model <model>", "fallback model")
    .option("--file <specs...>", "file resources to download at startup")
    .option("--fork-session", "fork when resuming")
    .option("--from-pr [value]", "resume a session linked to a PR")
    .option("--ide", "auto-connect to IDE")
    .option("--include-hook-events", "include hook lifecycle events")
    .option("--include-partial-messages", "include partial message chunks")
    .option("--json-schema <schema>", "JSON schema for structured output")
    .option("--max-budget-usd <amount>", "maximum API budget")
    .option("--mcp-config <configs...>", "MCP configs")
    .option("--mcp-debug", "enable MCP debug mode")
    .option("--model <model>", "model for the session")
    .option("-n, --name <name>", "display name for session")
    .option("--no-chrome", "disable Claude in Chrome integration")
    .option("--no-session-persistence", "disable session persistence")
    .option("--permission-mode <mode>", "permission mode")
    .option("--plugin-dir <path>", "plugin directory", collect, [])
    .option("--plugin-url <url>", "plugin URL", collect, [])
    .option("--remote-control [name]", "start an interactive session with Remote Control enabled")
    .option("--remote-control-session-name-prefix <prefix>", "Remote Control session name prefix")
    .option("-r, --resume [value]", "resume a conversation")
    .option("--replay-user-messages", "re-emit stream-json input user messages")
    .option("--session-id <uuid>", "specific session UUID")
    .option("--setting-sources <sources>", "setting sources")
    .option("--settings <file-or-json>", "settings file or JSON")
    .option("--strict-mcp-config", "strict MCP config")
    .option("--system-prompt <prompt>", "system prompt")
    .option("--tools <tools...>", "available tools")
    .option("--tmux [mode]", "create a tmux session for the worktree")
    .option("-w, --worktree [name]", "create a new git worktree for this session")
    .configureOutput({
      writeOut: () => undefined,
      writeErr: () => undefined,
    });

  try {
    program.parse(argv, { from: "user" });
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : String(error));
  }

  const parsed = program.opts<{
    print?: string;
    inputFormat: string;
    outputFormat: string;
    verbose: boolean;
    replayUserMessages?: boolean;
    [key: string]: unknown;
  }>();
  const prompt = parsed.print ?? program.args.join(" ");
  const inputFormat = parsed.inputFormat;
  const outputFormat = parsed.outputFormat;

  if (inputFormat !== "text" && inputFormat !== "stream-json") {
    throw new Error(`Unsupported --input-format ${inputFormat || "<missing>"}`);
  }

  if (!prompt && inputFormat === "text") {
    throw new Error("Expected a prompt via -p, --print, or positional prompt");
  }

  if (!isOutputFormat(outputFormat)) {
    throw new Error(`Unsupported --output-format ${outputFormat || "<missing>"}`);
  }

  return {
    prompt: prompt || undefined,
    inputFormat,
    outputFormat,
    verbose: parsed.verbose,
    replayUserMessages: parsed.replayUserMessages === true,
    cwd: resolve(cwd),
    claudeArgs: buildClaudeArgs(parsed),
  };
}

function collect(value: string, previous: string[]) {
  return previous.concat(value);
}

function isOutputFormat(value: string): value is OutputFormat {
  return value === "stream-json" || value === "json" || value === "text";
}

export function projectKeyForCwd(cwd: string): string {
  return resolve(cwd).normalize("NFC").replace(/[^a-zA-Z0-9_-]/g, "-");
}

export function claudeProjectsRoot(
  claudeConfigDir = Bun.env.CLAUDE_CONFIG_DIR,
  home = Bun.env.HOME ?? "",
): string {
  // Claude Code v2.1.x scopes only the config file (.claude.json) to
  // CLAUDE_CONFIG_DIR; transcripts/projects ALWAYS land under
  // ~/.claude/projects (verified live: isolated config dir gets
  // .claude.json+backups written, transcripts appear in the home root).
  // Polling <configDir>/projects therefore waits forever on a folder
  // Claude never writes.
  void claudeConfigDir;
  return join(home, ".claude", "projects");
}

export function claudeProjectFolder(
  cwd: string,
  claudeConfigDir = Bun.env.CLAUDE_CONFIG_DIR,
  home = Bun.env.HOME ?? "",
): string {
  return join(claudeProjectsRoot(claudeConfigDir, home), projectKeyForCwd(cwd));
}

function isRootProcess() {
  return typeof process.getuid === "function" && process.getuid() === 0;
}

function rootSafeClaudeArgs(args: string[]): string[] {
  if (!isRootProcess()) return args;

  const filtered: string[] = [];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--dangerously-skip-permissions" || arg === "--allow-dangerously-skip-permissions") {
      continue;
    }
    if (arg === "--permission-mode" && args[index + 1] === "bypassPermissions") {
      filtered.push("--permission-mode", "auto");
      index += 1;
      continue;
    }
    if (arg === "--session-id" || arg === "--resume") {
      index += 1;
      continue;
    }
    if (arg === "--continue") {
      continue;
    }
    filtered.push(arg);
  }
  return filtered;
}

async function maybeSendStartupEnterKeys(tmuxSession: string) {
  const count = Number(Bun.env.MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_COUNT ?? 0);
  if (!Number.isFinite(count) || count <= 0) return;
  const delayMs = Number(Bun.env.MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_DELAY_MS ?? 1000);
  for (let index = 0; index < count; index += 1) {
    await sleep(Math.max(100, delayMs));
    await runCommand(["tmux", "send-keys", "-t", tmuxSession, "C-m"], false);
  }
}

// >>> megaplan-shannon-helpers v1 >>>
function megaplanSlashCommand(prompt: unknown): string | undefined {
  if (typeof prompt !== "string") return undefined;
  const trimmed = prompt.trimStart();
  if (!trimmed.startsWith("/")) return undefined;
  return trimmed.trim().split(/\s+/)[0];
}

function megaplanSlashPromptMatches(prompt: unknown, content: unknown): boolean {
  const cmd = megaplanSlashCommand(prompt);
  if (!cmd || typeof content !== "string") return false;
  return content.includes("<command-name>" + cmd);
}

function megaplanRowText(row: TranscriptRow): string {
  const top = typeof row.content === "string" ? row.content : "";
  const msg = typeof row.message?.content === "string" ? row.message.content : "";
  return top + "\n" + msg;
}

function megaplanSlashSynthReply(cmd: string, sessionId: string | undefined, row: TranscriptRow): JsonRecord {
  const sid = (row && (row.sessionId ?? row.session_id)) ?? sessionId;
  return {
    type: "assistant",
    message: {
      role: "assistant",
      content: [{ type: "text", text: "[megaplan] slash command " + cmd + " completed" }],
      stop_reason: "end_turn",
      usage: {},
      model: "unknown",
    },
    sessionId: sid,
    session_id: sid,
    uuid: (row && row.uuid) ?? randomUUID(),
  };
}

function megaplanSlashCompletionRow(prompt: unknown, rows: TranscriptRow[]): JsonRecord | undefined {
  const cmd = megaplanSlashCommand(prompt);
  if (!cmd) return undefined;
  let cmdIdx = -1;
  for (let i = 0; i < rows.length; i += 1) {
    if (megaplanRowText(rows[i]).includes("<command-name>" + cmd)) cmdIdx = i;
  }
  if (cmdIdx < 0) return undefined;
  let sessionId = rows[cmdIdx].sessionId ?? rows[cmdIdx].session_id;
  if (cmd === "/clear") return megaplanSlashSynthReply(cmd, sessionId, rows[cmdIdx]);
  for (let i = cmdIdx + 1; i < rows.length; i += 1) {
    const row = rows[i];
    sessionId = row.sessionId ?? row.session_id ?? sessionId;
    const text = megaplanRowText(row);
    if (row.subtype === "compact_boundary" || row.isCompactSummary === true) {
      return megaplanSlashSynthReply(cmd, sessionId, row);
    }
    if (text.includes("<local-command-stdout>") || text.includes("Compacted") || text.includes("Not enough messages to compact")) {
      return megaplanSlashSynthReply(cmd, sessionId, row);
    }
    if (row.type === "assistant" && row.message?.role === "assistant" && row.message?.stop_reason !== "tool_use" && textFromContent(row.message?.content)) {
      return megaplanSlashSynthReply(cmd, sessionId, row);
    }
  }
  return undefined;
}
// <<< megaplan-shannon-helpers <<<

export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {
  const args: string[] = [];

  addRepeated(args, "--add-dir", parsed.addDir);
  addString(args, "--agent", parsed.agent);
  addString(args, "--agents", parsed.agents);
  addBoolean(args, "--allow-dangerously-skip-permissions", parsed.allowDangerouslySkipPermissions);
  addRepeated(args, "--allowed-tools", parsed.allowedTools);
  addString(args, "--append-system-prompt", parsed.appendSystemPrompt);
  addBoolean(args, "--bare", parsed.bare);
  addRepeated(args, "--betas", parsed.betas);
  addBoolean(args, "--brief", parsed.brief);
  addBoolean(args, "--chrome", parsed.chrome);
  addBoolean(args, "--continue", parsed.continue);
  addBoolean(args, "--dangerously-skip-permissions", parsed.dangerouslySkipPermissions);
  addOptionalString(args, "--debug", parsed.debug);
  addString(args, "--debug-file", parsed.debugFile);
  addBoolean(args, "--disable-slash-commands", parsed.disableSlashCommands);
  addRepeated(args, "--disallowed-tools", parsed.disallowedTools);
  addString(args, "--effort", parsed.effort);
  addBoolean(args, "--exclude-dynamic-system-prompt-sections", parsed.excludeDynamicSystemPromptSections);
  addString(args, "--fallback-model", parsed.fallbackModel);
  addRepeated(args, "--file", parsed.file);
  addBoolean(args, "--fork-session", parsed.forkSession);
  addOptionalString(args, "--from-pr", parsed.fromPr);
  addBoolean(args, "--ide", parsed.ide);
  addBoolean(args, "--include-hook-events", parsed.includeHookEvents);
  addBoolean(args, "--include-partial-messages", parsed.includePartialMessages);
  addString(args, "--json-schema", parsed.jsonSchema);
  addString(args, "--max-budget-usd", parsed.maxBudgetUsd);
  addRepeated(args, "--mcp-config", parsed.mcpConfig);
  addBoolean(args, "--mcp-debug", parsed.mcpDebug);
  addString(args, "--model", parsed.model);
  addString(args, "--name", parsed.name);
  if (parsed.chrome === false) args.push("--no-chrome");
  addBoolean(args, "--no-session-persistence", parsed.sessionPersistence === false);
  addString(args, "--permission-mode", parsed.permissionMode);
  addRepeatedFlag(args, "--plugin-dir", parsed.pluginDir);
  addRepeatedFlag(args, "--plugin-url", parsed.pluginUrl);
  addOptionalString(args, "--remote-control", parsed.remoteControl);
  addString(args, "--remote-control-session-name-prefix", parsed.remoteControlSessionNamePrefix);
  addOptionalString(args, "--resume", parsed.resume);
  addString(args, "--session-id", parsed.sessionId);
  addString(args, "--setting-sources", parsed.settingSources);
  addString(args, "--settings", parsed.settings);
  addBoolean(args, "--strict-mcp-config", parsed.strictMcpConfig);
  addString(args, "--system-prompt", parsed.systemPrompt);
  addRepeated(args, "--tools", parsed.tools);
  addOptionalString(args, "--tmux", parsed.tmux);
  addOptionalString(args, "--worktree", parsed.worktree);

  return args;
}

function addString(args: string[], flag: string, value: unknown) {
  if (typeof value === "string" && value.length > 0) args.push(flag, value);
}

function addOptionalString(args: string[], flag: string, value: unknown) {
  if (value === true) args.push(flag);
  else addString(args, flag, value);
}

function addBoolean(args: string[], flag: string, value: unknown) {
  if (value === true) args.push(flag);
}

function addRepeated(args: string[], flag: string, value: unknown) {
  if (Array.isArray(value)) {
    const strings = value.filter((item): item is string => typeof item === "string");
    if (strings.length > 0) args.push(flag, ...strings);
  } else {
    addString(args, flag, value);
  }
}

function addRepeatedFlag(args: string[], flag: string, value: unknown) {
  if (!Array.isArray(value)) return;
  for (const item of value) {
    if (typeof item === "string" && item.length > 0) args.push(flag, item);
  }
}

export function textFromContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";

  return content
    .map((block) => {
      if (block && typeof block === "object" && "type" in block && block.type === "text") {
        return "text" in block && typeof block.text === "string" ? block.text : "";
      }
      return "";
    })
    .join("");
}

export function toSdkAssistant(row: TranscriptRow): JsonRecord {
  return {
    type: "assistant",
    message: row.message,
    parent_tool_use_id: row.parent_tool_use_id ?? null,
    session_id: row.sessionId ?? row.session_id,
    uuid: row.uuid,
  };
}

export function toSdkHookResponse(row: TranscriptRow): JsonRecord | undefined {
  const attachment = row.attachment;
  if (attachment?.type !== "hook_success") return undefined;

  return {
    type: "system",
    subtype: "hook_response",
    hook_id: attachment.toolUseID ?? row.uuid ?? randomUUID(),
    hook_name: attachment.hookName ?? "unknown",
    hook_event: attachment.hookEvent ?? "unknown",
    output: attachment.content || attachment.stdout || attachment.stderr || "",
    stdout: attachment.stdout ?? "",
    stderr: attachment.stderr ?? "",
    exit_code: attachment.exitCode,
    outcome: "success",
    uuid: row.uuid ?? randomUUID(),
    session_id: row.sessionId ?? row.session_id,
  };
}

export function toSdkHookStarted(row: TranscriptRow): JsonRecord | undefined {
  const attachment = row.attachment;
  if (attachment?.type !== "hook_success") return undefined;

  return {
    type: "system",
    subtype: "hook_started",
    hook_id: attachment.toolUseID ?? row.uuid ?? randomUUID(),
    hook_name: attachment.hookName ?? "unknown",
    hook_event: attachment.hookEvent ?? "unknown",
    uuid: row.uuid ?? randomUUID(),
    session_id: row.sessionId ?? row.session_id,
  };
}

export function toSdkInit(meta: SessionMetadata, rows: TranscriptRow[], claudeArgs: string[] = []): JsonRecord {
  const nativeInit = rows.find((row) => row.type === "system" && row.subtype === "init");
  if (nativeInit) {
    return {
      ...nativeInit,
      cwd: typeof nativeInit.cwd === "string" ? nativeInit.cwd : meta.cwd,
      session_id: nativeInit.session_id ?? nativeInit.sessionId ?? meta.sessionId,
      uuid: nativeInit.uuid ?? randomUUID(),
    };
  }

  const userRow = rows.find((row) => row.type === "user");
  const versionedRow = rows.find((row) => typeof row.version === "string");
  const assistantRow = rows.find((row) => typeof row.message?.model === "string");
  const skillNames = skillNamesFromRows(rows);
  const rowMcpServers = firstArrayField(rows, "mcp_servers");
  const mcpServers = rowMcpServers ?? mcpServersFromRows(rows);
  const rowTools = firstArrayField(rows, "tools");
  const tools = rowTools ?? toolsFromMcpServers(mcpServers as Array<{ name: string }>);
  const rowAgents = firstArrayField(rows, "agents");
  const rowPlugins = firstArrayField(rows, "plugins");

  return {
    type: "system",
    subtype: "init",
    cwd: meta.cwd,
    session_id: meta.sessionId,
    tools,
    mcp_servers: mcpServers,
    model: assistantRow?.message?.model ?? stringArgValue(claudeArgs, "--model") ?? "unknown",
    permissionMode: typeof userRow?.permissionMode === "string"
      ? userRow.permissionMode
      : stringArgValue(claudeArgs, "--permission-mode") ?? "unknown",
    apiKeySource: "none",
    claude_code_version: typeof versionedRow?.version === "string" ? versionedRow.version : undefined,
    output_style: "default",
    agents: rowAgents ?? [],
    slash_commands: skillNames,
    skills: skillNames,
    plugins: rowPlugins ?? [],
    uuid: randomUUID(),
  };
}

function firstArrayField(rows: TranscriptRow[], field: string): unknown[] | undefined {
  for (const row of rows) {
    const value = row[field];
    if (Array.isArray(value)) return value;
  }
  return undefined;
}

function stringArgValue(args: string[], flag: string): string | undefined {
  const index = args.indexOf(flag);
  if (index < 0) return undefined;
  const value = args[index + 1];
  return typeof value === "string" && !value.startsWith("--") ? value : undefined;
}

export function toolsFromMcpServers(mcpServers: Array<{ name: string }>): string[] {
  return [
    ...DEFAULT_CLAUDE_TOOLS,
    ...mcpServers.flatMap((server) => mcpToolNames(server.name)),
  ];
}

function mcpToolNames(serverName: string) {
  switch (serverName) {
    case "context7":
      return ["mcp__context7__query-docs", "mcp__context7__resolve-library-id"];
    case "morph-mcp":
      return ["mcp__morph-mcp__codebase_search"];
    default:
      return [];
  }
}

export function mcpServersFromRows(rows: TranscriptRow[]): Array<{ name: string; status: string }> {
  const servers = new Map<string, { name: string; status: string }>();

  for (const row of rows) {
    if (row.attachment?.type !== "mcp_instructions_delta") continue;

    for (const name of stringArrayFromUnknown(row.attachment.addedNames)) {
      servers.set(name, { name, status: "connected" });
    }

    for (const name of stringArrayFromUnknown(row.attachment.removedNames)) {
      servers.delete(name);
    }
  }

  return [...servers.values()];
}

function stringArrayFromUnknown(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

export function skillNamesFromRows(rows: TranscriptRow[]): string[] {
  const names = new Set<string>();

  for (const row of rows) {
    if (row.attachment?.type !== "skill_listing" || typeof row.attachment.content !== "string") continue;
    for (const name of skillNamesFromListing(row.attachment.content)) {
      names.add(name);
    }
  }

  return [...names];
}

export function skillNamesFromListing(content: string): string[] {
  const names: string[] = [];

  for (const line of content.split("\n")) {
    const match = /^-\s+(.+?)(?::\s|\s*$)/.exec(line);
    if (!match) continue;
    const name = match[1]?.trim();
    if (name) names.push(name);
  }

  return names;
}

export function toSdkResult(row: TranscriptRow, startedAt: number, numTurns = 1): JsonRecord {
  const text = textFromContent(row.message?.content);
  const usage = row.message?.usage ?? {};
  const model = row.message?.model ?? "unknown";
  const durationMs = Date.now() - startedAt;
  const modelUsage = toModelUsage(model, usage);
  const totalCostUsd = modelUsage.costUSD;

  return {
    type: "result",
    subtype: "success",
    is_error: false,
    duration_ms: durationMs,
    duration_api_ms: durationMs,
    num_turns: numTurns,
    result: text,
    stop_reason: row.message?.stop_reason ?? "end_turn",
    session_id: row.sessionId ?? row.session_id,
    total_cost_usd: totalCostUsd,
    usage,
    modelUsage: {
      [model]: modelUsage,
    },
    permission_denials: [],
    terminal_reason: "completed",
    uuid: randomUUID(),
  };
}

export function estimateCostUSD(model: string, usage: JsonRecord): number {
  const pricing = pricingForModel(model);
  if (!pricing) return 0;

  const inputTokens = numberFromUsage(usage.input_tokens);
  const outputTokens = numberFromUsage(usage.output_tokens);
  const cacheReadInputTokens = numberFromUsage(usage.cache_read_input_tokens);
  const cacheCreationInputTokens = numberFromUsage(usage.cache_creation_input_tokens);
  const webSearchRequests = webSearchRequestsFromUsage(usage);

  const tokenCost = (
    inputTokens * pricing.inputPerMTok
    + cacheCreationInputTokens * pricing.inputPerMTok * 1.25
    + cacheReadInputTokens * pricing.inputPerMTok * 0.1
    + outputTokens * pricing.outputPerMTok
  ) / 1_000_000;

  return tokenCost + webSearchRequests * WEB_SEARCH_COST_USD;
}

function toModelUsage(model: string, usage: JsonRecord): JsonRecord {
  const pricing = pricingForModel(model);
  const costUSD = estimateCostUSD(model, usage);

  return {
    inputTokens: numberFromUsage(usage.input_tokens),
    outputTokens: numberFromUsage(usage.output_tokens),
    cacheReadInputTokens: numberFromUsage(usage.cache_read_input_tokens),
    cacheCreationInputTokens: numberFromUsage(usage.cache_creation_input_tokens),
    webSearchRequests: webSearchRequestsFromUsage(usage),
    costUSD,
    ...(pricing?.contextWindow !== undefined ? { contextWindow: pricing.contextWindow } : {}),
    ...(pricing?.maxOutputTokens !== undefined ? { maxOutputTokens: pricing.maxOutputTokens } : {}),
  };
}

function pricingForModel(model: string): ModelPricing | undefined {
  return MODEL_PRICING.find(({ pattern }) => pattern.test(model))?.pricing;
}

function numberFromUsage(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function webSearchRequestsFromUsage(usage: JsonRecord): number {
  const serverToolUse = usage.server_tool_use;
  if (!serverToolUse || typeof serverToolUse !== "object") return 0;
  return numberFromUsage((serverToolUse as JsonRecord).web_search_requests);
}

export function toShannonMetadata(meta: SessionMetadata, cleanup: JsonRecord): JsonRecord {
  return {
    type: "shannon_session",
    subtype: "metadata",
    session_id: meta.sessionId,
    session_folder: meta.projectFolder,
    transcript_path: meta.transcriptPath,
    tmux_session: meta.tmuxSession,
    cwd: meta.cwd,
    cleanup,
    uuid: randomUUID(),
  };
}

export function toUserReplay(prompt: string): JsonRecord {
  return {
    type: "user",
    message: {
      role: "user",
      content: prompt,
    },
    parent_tool_use_id: null,
    session_id: "",
    uuid: randomUUID(),
  };
}

export function promptFromUserMessage(message: JsonRecord): string | undefined {
  if (message.type !== "user") return undefined;
  const nested = message.message;
  if (!nested || typeof nested !== "object") return undefined;
  const content = (nested as JsonRecord).content;
  const text = textFromContent(content);
  return text || undefined;
}

export function assistantReplyFromRows(prompt: string, rows: TranscriptRow[]): TranscriptRow | undefined {
  const megaplanSlashReply = megaplanSlashCompletionRow(prompt, rows);
  if (megaplanSlashReply) return megaplanSlashReply;
  let sawPrompt = false;

  for (const row of rows) {
    if (row.type === "user" && row.message?.content === prompt) {
      sawPrompt = true;
      continue;
    }

    if (!sawPrompt || row.type !== "assistant" || row.message?.role !== "assistant") continue;
    if (row.message?.stop_reason === "tool_use") continue;
    if (textFromContent(row.message.content)) return row;
  }
}

async function main() {
  const options = parseArgs(Bun.argv.slice(2));
  await runShannon(options);
}

export async function runShannon(options: CliOptions) {
  await validateRuntime();

  const tmuxSession = Bun.env.SHANNON_TMUX_SESSION_NAME ?? `shannon-${randomUUID()}`;
  const projectFolder = claudeProjectFolder(options.cwd);
  const before = await listTranscriptPaths(projectFolder);
  const startedAt = Date.now();
  const prompts = options.prompt
    ? asyncIterableFromArray([options.prompt])
    : readPromptsFromStdin(options.inputFormat);
  const promptIterator = prompts[Symbol.asyncIterator]();
  let meta: SessionMetadata | undefined;
  let transcriptRowCount = 0;
  let cleanup: JsonRecord = { tmux_killed: false };
  let promptCount = 0;
  let cleanupStarted = false;
  let metadataEmitted = false;
  const jsonMessages: JsonRecord[] = [];

  const cleanupOnce = async () => {
    if (cleanupStarted) return cleanup;
    cleanupStarted = true;
    cleanup = await killTmux(tmuxSession);
    return cleanup;
  };

  const emitMetadataOnce = () => {
    if (
      !meta
      || metadataEmitted
      || options.outputFormat !== "stream-json"
      || Bun.env.SHANNON_EMIT_METADATA !== "1"
    ) return;
    metadataEmitted = true;
    emitJson(toShannonMetadata(meta, cleanup));
  };

  const disposeSignalHandlers = installSignalHandlers({
    cleanup: cleanupOnce,
    emitMetadata: emitMetadataOnce,
  });

  try {
    let prompt = await nextPrompt(promptIterator);
    if (!prompt) {
      throw new Error("Expected at least one user message on stdin for --input-format=stream-json");
    }

    const _mpScrubKeys = Object.keys(Bun.env).filter((k) => /^(MEGAPLAN_|SHANNON_)/.test(k));
    // tmux spawns the command with the SERVER's environment (not this
    // process's) when a server already exists, so CLAUDE_CONFIG_DIR silently
    // vanishes: Claude then writes transcripts to ~/.claude while we poll the
    // isolated dir (transcript timeout), and deterministic --session-id
    // retries collide with the stray ~/.claude session file (instant exit,
    // "can't find pane"). Inject it explicitly into the spawned command.
    const _mpEnvSets = Bun.env.CLAUDE_CONFIG_DIR ? [`CLAUDE_CONFIG_DIR=${Bun.env.CLAUDE_CONFIG_DIR}`] : [];
    const _mpEnvPrefix = _mpScrubKeys.length > 0 || _mpEnvSets.length > 0
      ? ["env", ..._mpScrubKeys.flatMap((k) => ["-u", k]), ..._mpEnvSets]
      : [];
    const claudeLaunchArgs = [
      ..._mpEnvPrefix,
      "claude",
      ...(isRootProcess() ? rootSafeClaudeArgs(options.claudeArgs) : options.claudeArgs),
    ];
    await runCommand([
      "tmux",
      "new-session",
      "-d",
      "-s",
      tmuxSession,
      "-c",
      options.cwd,
      ...claudeLaunchArgs,
    ]);

    void maybeSendStartupEnterKeys(tmuxSession);

    while (prompt) {
      promptCount += 1;

      await waitUntilReadyToSend(tmuxSession);
      const promptSentAt = Date.now();
      await sendPrompt(tmuxSession, prompt);

      if (options.replayUserMessages && options.outputFormat === "stream-json") {
        emitJson(toUserReplay(prompt));
      }

      if (!meta) {
        const discovery = await waitForSessionWithPrompt(
          projectFolder,
          before,
          tmuxSession,
          options.cwd,
          prompt,
          promptSentAt,
        );
        meta = discovery.meta;
        transcriptRowCount = 0;

        for (const row of discovery.rows) {
          const hookStarted = toSdkHookStarted(row);
          if (hookStarted) {
            if (options.outputFormat === "stream-json") {
              emitJson(hookStarted);
            } else if (options.outputFormat === "json") {
              jsonMessages.push(hookStarted);
            }
          }

          const hookResponse = toSdkHookResponse(row);
          if (!hookResponse) continue;
          if (options.outputFormat === "stream-json") {
            emitJson(hookResponse);
          } else if (options.outputFormat === "json") {
            jsonMessages.push(hookResponse);
          }
        }

        const init = toSdkInit(meta, discovery.rows, options.claudeArgs);
        if (options.outputFormat === "stream-json") {
          emitJson(init);
        } else if (options.outputFormat === "json") {
          jsonMessages.push(init);
        }
      }

      const assistant = await waitForAssistantReply(
        meta.transcriptPath,
        prompt,
        startedAt,
        transcriptRowCount,
      );
      transcriptRowCount = assistant.rows.length;
      const result = toSdkResult(assistant.row, startedAt, promptCount);
      const turnMessages = [toSdkAssistant(assistant.row), result];
      if (options.outputFormat === "json") {
        jsonMessages.push(...turnMessages);
      } else {
        emitOutput(options.outputFormat, turnMessages);
      }

      prompt = await nextPrompt(promptIterator);
    }

    if (options.outputFormat === "json") {
      process.stdout.write(`${JSON.stringify(jsonMessages)}\n`);
    }
  } finally {
    disposeSignalHandlers();
    cleanup = await cleanupOnce();
    emitMetadataOnce();
  }
}

export function signalExitCode(signal: ShutdownSignal) {
  return signal === "SIGINT" ? 130 : 143;
}

function installSignalHandlers({
  cleanup,
  emitMetadata,
}: {
  cleanup: () => Promise<JsonRecord>;
  emitMetadata: () => void;
}) {
  let shuttingDown = false;

  const handler = (signal: ShutdownSignal) => {
    if (shuttingDown) return;
    shuttingDown = true;

    cleanup()
      .then(() => {
        emitMetadata();
      })
      .catch((error) => {
        process.stderr.write(
          `Failed to clean up Shannon tmux session after ${signal}: ${
            error instanceof Error ? error.message : String(error)
          }\n`,
        );
      })
      .finally(() => {
        process.exit(signalExitCode(signal));
      });
  };

  process.once("SIGINT", handler);
  process.once("SIGTERM", handler);

  return () => {
    process.off("SIGINT", handler);
    process.off("SIGTERM", handler);
  };
}

export async function validateRuntime() {
  const [claude, tmux] = await Promise.all([
    findExecutable("claude"),
    findExecutable("tmux"),
  ]);

  if (!claude) {
    throw new Error("Missing required executable: claude. Install Claude Code and make sure `claude` is on PATH.");
  }

  if (!tmux) {
    throw new Error("Missing required executable: tmux. Install tmux and make sure `tmux` is on PATH.");
  }

  return { claude, tmux };
}

async function* asyncIterableFromArray(values: string[]): AsyncIterable<string> {
  for (const value of values) yield value;
}

async function* readPromptsFromStdin(inputFormat: "text" | "stream-json"): AsyncIterable<string> {
  if (inputFormat === "text") {
    const stdin = await Bun.stdin.text();
    const prompt = stdin.trimEnd();
    if (prompt) yield prompt;
    return;
  }

  for await (const line of readStdinLines()) {
    if (!line.trim()) continue;
    const prompt = promptFromUserMessage(JSON.parse(line) as JsonRecord);
    if (prompt) yield prompt;
  }
}

async function* readStdinLines(initialText?: string): AsyncIterable<string> {
  if (initialText !== undefined) {
    yield* initialText.split("\n");
    return;
  }

  const reader = Bun.stdin.stream().getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) yield line;
  }

  buffer += decoder.decode();
  if (buffer) yield buffer;
}

async function waitForSessionWithPrompt(
  projectFolder: string,
  before: Set<string>,
  tmuxSession: string,
  cwd: string,
  prompt: string,
  promptSentAt: number,
): Promise<SessionDiscovery> {
  const startedAt = Date.now();

  while (Date.now() - startedAt < START_TIMEOUT_MS) {
    const paths = await listTranscriptPaths(projectFolder);
    const fresh = [...paths].filter((path) => !before.has(path)).sort();
    const existing = [...paths].filter((path) => before.has(path)).sort();
    const candidates = [...fresh, ...existing];

    for (const transcriptPath of candidates) {
      const rows = await readTranscript(transcriptPath);
      const hasPrompt = rows.some((row) => rowContainsPromptAfter(row, prompt, promptSentAt, !before.has(transcriptPath)));
      if (!hasPrompt) continue;

      const sessionId = basename(transcriptPath).replace(/\.jsonl$/, "");
      return {
        meta: { sessionId, projectFolder, transcriptPath, tmuxSession, cwd },
        rows,
      };
    }

    await sleep(POLL_MS);
  }

  const pane = await capturePane(tmuxSession);
  throw new Error(
    `Timed out waiting for Claude transcript containing the submitted prompt in ${projectFolder}\n\nCaptured tmux pane:\n${pane}`,
  );
}

export function rowContainsPromptAfter(
  row: TranscriptRow,
  prompt: string,
  promptSentAt: number,
  allowMissingTimestamp = false,
) {
  if (row.type !== "user") return false;
  if (row.message?.content !== prompt && !megaplanSlashPromptMatches(prompt, row.message?.content)) return false;
  if (typeof row.timestamp !== "string") return allowMissingTimestamp;
  const timestamp = Date.parse(row.timestamp);
  return Number.isFinite(timestamp) && timestamp >= promptSentAt - 1_000;
}

async function waitForPrompt(tmuxSession: string) {
  const startedAt = Date.now();
  const dbg = Bun.env.SHANNON_DEBUG_READINESS_LOG;

  while (Date.now() - startedAt < START_TIMEOUT_MS) {
    const pane = await runCommand(["tmux", "capture-pane", "-pt", tmuxSession, "-S", "-40"]);
    if (dbg) {
      const ready = paneLooksReadyForUserMessage(pane.stdout);
      await Bun.write(dbg, `[${Date.now() - startedAt}ms] exit=${pane.exitCode} ready=${ready} len=${pane.stdout.length}\n--PANE--\n${pane.stdout}\n--END--\n`, { createPath: true });
    }
    const blocker = classifyClaudeStartupBlocker(pane.stdout);
    if (blocker) {
      throw new Error(
        `Claude is waiting at a ${blocker.kind} prompt before Shannon can send a message: ${blocker.detail}\n\nCaptured tmux pane:\n${pane.stdout}`,
      );
    }
    if (paneLooksReadyForUserMessage(pane.stdout)) return;
    await sleep(POLL_MS);
  }

  const pane = await capturePane(tmuxSession);
  throw new Error(`Timed out waiting for Claude prompt\n\nCaptured tmux pane:\n${pane}`);
}

type StartupBlocker = {
  kind: "approval" | "auth" | "trust" | "onboarding";
  detail: string;
};

export function classifyClaudeStartupBlocker(pane: string): StartupBlocker | undefined {
  const normalized = pane.toLowerCase().replace(/\s+/g, " ");

  if (
    normalized.includes("do you trust")
    || normalized.includes("project you trust")
    || normalized.includes("trust this folder")
    || normalized.includes("trust this workspace")
  ) {
    return { kind: "trust", detail: "workspace trust confirmation is blocking startup" };
  }

  if (
    // One-time "Bypass Permissions mode" acceptance dialog (fresh config dir).
    // Its "❯ 1. No, exit" default both matches the readiness regex AND exits
    // Claude when Enter confirms it — classify it before readiness can see it.
    normalized.includes("you accept all responsibility")
    || normalized.includes("yes, i accept")
  ) {
    return { kind: "permission", detail: "bypass-permissions acceptance dialog is blocking startup" };
  }

  if (
    normalized.includes("not logged in")
    || normalized.includes("run /login")
    || normalized.includes("please log in")
    || normalized.includes("please login")
    || normalized.includes("login required")
    || normalized.includes("authentication required")
  ) {
    return { kind: "auth", detail: "Claude authentication is required" };
  }

  if (
    normalized.includes("do you want to proceed")
    || normalized.includes("allow this command")
    || normalized.includes("approve this")
    || normalized.includes("approval required")
    || normalized.includes("permission required")
    || normalized.includes("yes, and don't ask again")
    || normalized.includes("yes, and don’t ask again")
    || normalized.includes("no, and tell")
  ) {
    return { kind: "approval", detail: "Claude is waiting for an approval decision" };
  }

  if (
    normalized.includes("press enter to continue")
    || normalized.includes("accept the terms")
    || normalized.includes("cost threshold")
    || normalized.includes("onboarding")
  ) {
    return { kind: "onboarding", detail: "Claude onboarding or acknowledgement is blocking startup" };
  }

  return undefined;
}

export function paneLooksReadyForUserMessage(pane: string) {
  const lines = pane.split(/\r?\n/).map((line) => line.trimEnd());
  // tmux capture-pane pads the capture to the full pane height, so a short
  // TUI leaves trailing blank lines that push the composer line out of a
  // fixed last-N window. Drop the padding before windowing.
  while (lines.length && lines[lines.length - 1] === "") lines.pop();
  const recent = lines.slice(-12);
  return recent.some((line) => {
    // Legacy: a bare prompt marker at end of line ("❯" / "│ ❯").
    if (/(^|\s)[❯>]\s*$/.test(line)) return true;
    // Composer input line with placeholder/typed text. Claude Code >=2.1.x
    // renders the empty composer as `❯ Try "how do I log an error?"`, so the
    // marker is no longer at end-of-line and the legacy regex misses a visibly
    // ready prompt (Shannon then times out its readiness probe). Match the
    // marker at the START of the line (after any box-drawing/whitespace prefix)
    // followed by text — robust to the placeholder without matching a "❯" that
    // appears mid-output.
    const stripped = line.replace(/^[│|\s]+/, "");
    return /^[❯>]\s+\S/.test(stripped);
  });
}

async function waitUntilReadyToSend(tmuxSession: string) {
  await waitForPrompt(tmuxSession);
  await sleep(randomSendDelayMs());
}

function randomSendDelayMs() {
  const min = Number.isFinite(SEND_DELAY_MIN_MS) ? Math.max(0, SEND_DELAY_MIN_MS) : 350;
  const maxRaw = Number.isFinite(SEND_DELAY_MAX_MS) ? Math.max(0, SEND_DELAY_MAX_MS) : 2500;
  const max = Math.max(min, maxRaw);
  return Math.floor(min + Math.random() * (max - min + 1));
}

async function sendPrompt(tmuxSession: string, prompt: string) {
  if (canTypePromptLiterally(prompt)) {
    await runCommand(["tmux", "send-keys", "-t", tmuxSession, "-l", prompt]);
    await runCommand(["tmux", "send-keys", "-t", tmuxSession, "C-m"]);
    return;
  }

  const _mpBuf = randomUUID();
  let primaryError: unknown;
  try {
    const _mpLoad = Bun.spawn(["tmux", "load-buffer", "-b", _mpBuf, "-"], { stdin: "pipe", stdout: "pipe", stderr: "pipe" });
    _mpLoad.stdin.write(prompt);
    await _mpLoad.stdin.end();
    if ((await _mpLoad.exited) !== 0) {
      throw new Error(`tmux load-buffer failed: ${await new Response(_mpLoad.stderr).text()}`);
    }
    await runCommand(["tmux", "paste-buffer", "-p", "-b", _mpBuf, "-t", tmuxSession]);
    await runCommand(["tmux", "send-keys", "-t", tmuxSession, "C-m"]);
  } catch (error) {
    primaryError = error;
    throw error;
  } finally {
    try {
      await runCommand(["tmux", "delete-buffer", "-b", _mpBuf]);
    } catch (deleteError) {
      if (primaryError === undefined) {
        throw deleteError;
      }
    }
  }
}

function canTypePromptLiterally(prompt: string) {
  return (
    Number.isFinite(TYPE_PROMPT_MAX_CHARS)
    && TYPE_PROMPT_MAX_CHARS > 0
    && prompt.length <= TYPE_PROMPT_MAX_CHARS
    && !/[\r\n\x00-\x1F\x7F]/.test(prompt)
  );
}

async function nextPrompt(iterator: AsyncIterator<string>): Promise<string | undefined> {
  while (true) {
    const next = await iterator.next();
    if (next.done) return undefined;
    if (next.value) return next.value;
  }
}

async function waitForAssistantReply(
  transcriptPath: string,
  prompt: string,
  startedAt: number,
  afterRowCount: number,
): Promise<AssistantDiscovery> {
  while (Date.now() - startedAt < TURN_TIMEOUT_MS) {
    const rows = await readTranscript(transcriptPath);
    const newRows = rows.slice(afterRowCount);
    const row = assistantReplyFromRows(prompt, newRows);
    if (row) return { row, rows };

    await sleep(POLL_MS);
  }

  throw new Error(`Timed out waiting for assistant reply in ${transcriptPath}`);
}

async function readTranscript(transcriptPath: string): Promise<TranscriptRow[]> {
  const file = Bun.file(transcriptPath);
  if (!(await file.exists())) return [];

  const text = await file.text();
  return text
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as TranscriptRow;
      } catch {
        return { type: "shannon_parse_error", line };
      }
    });
}

async function listTranscriptPaths(projectFolder: string): Promise<Set<string>> {
  const glob = new Bun.Glob("*.jsonl");
  const paths = new Set<string>();

  try {
    for await (const name of glob.scan(projectFolder)) {
      paths.add(join(projectFolder, name));
    }
  } catch {
    return paths;
  }

  return paths;
}

async function killTmux(tmuxSession: string): Promise<JsonRecord> {
  const result = await runCommand(["tmux", "kill-session", "-t", tmuxSession], false);
  return {
    tmux_killed: result.exitCode === 0,
    exit_code: result.exitCode,
    stderr: result.stderr.trim(),
  };
}

async function capturePane(tmuxSession: string) {
  const result = await runCommand(
    ["tmux", "capture-pane", "-pt", tmuxSession, "-S", "-80"],
    false,
  );
  return result.stdout.trimEnd() || result.stderr.trimEnd();
}

async function findExecutable(name: string) {
  const result = await runCommand(["which", name], false);
  return result.exitCode === 0 ? result.stdout.trim() : undefined;
}

async function runCommand(args: string[], throwOnFailure = true) {
  const proc = Bun.spawn(args, {
    stdout: "pipe",
    stderr: "pipe",
  });

  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ]);

  if (throwOnFailure && exitCode !== 0) {
    throw new Error(`${args.join(" ")} failed with ${exitCode}: ${stderr}`);
  }

  return { stdout, stderr, exitCode };
}

function emitJson(value: JsonRecord) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function emitOutput(outputFormat: OutputFormat, messages: JsonRecord[]) {
  if (outputFormat === "stream-json") {
    for (const message of messages) emitJson(message);
    return;
  }

  const result = messages.find((message) => message.type === "result") ?? {};
  if (outputFormat === "json") {
    emitJson(result);
    return;
  }

  const text = typeof result.result === "string" ? result.result : "";
  process.stdout.write(text ? `${text}\n` : "");
}

function sleep(ms: number) {
  return new Promise((resolveSleep) => setTimeout(resolveSleep, ms));
}

function usage() {
  return "Usage: shannon -p <prompt> --output-format=stream-json --verbose";
}

if (import.meta.main) {
  main().catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  });
}
