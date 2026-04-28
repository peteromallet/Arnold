import {
  extractAssistantText,
  isRecord,
  parseToolArgsSafely,
} from "./llm/messages.ts";

export type ExtractedToolCall = {
  id: string;
  name: string;
  args: Record<string, unknown>;
  parseError: string | null;
};

const COMMAND_VERBS = /^(?:view|move|split|trim|delete|rm|set|set-text|settext|add-text|addtext|text|swap|duplicate|dup|clone|query|undo|find-issues|findissues|issues|generate|gen)\b/;
const FALLBACK_TOOL_NAMES = new Set([
  "run",
  "create_task",
  "duplicate_generation",
  "search_loras",
  "set_lora",
  "create_shot",
  "get_tasks",
  // Sprint 4 (SD-018): themed-editing direct tools.
  "set_params",
  "set_theme",
  "set_theme_overrides",
  // Sprint 7 (SD-020 + SD-034): bulk generative delegation.
  "delegateToBanodocoAgent",
]);

function cleanCommand(raw: string): string {
  return raw
    .replace(/\\"/g, "\"")
    .replace(/\\'/g, "'")
    .replace(/^["']+|["']+$/g, "")
    .trim();
}

function extractBalancedBlock(
  text: string,
  startIndex: number,
  openChar: string,
  closeChar: string,
): { content: string; endIndex: number } | null {
  if (text[startIndex] !== openChar) {
    return null;
  }

  let depth = 0;
  let inString = false;
  let stringQuote = "";
  let escaped = false;

  for (let index = startIndex; index < text.length; index += 1) {
    const char = text[index];

    if (inString) {
      if (escaped) {
        escaped = false;
        continue;
      }
      if (char === "\\") {
        escaped = true;
        continue;
      }
      if (char === stringQuote) {
        inString = false;
        stringQuote = "";
      }
      continue;
    }

    if (char === "\"" || char === "'") {
      inString = true;
      stringQuote = char;
      continue;
    }

    if (char === openChar) {
      depth += 1;
      continue;
    }

    if (char !== closeChar) {
      continue;
    }

    depth -= 1;
    if (depth === 0) {
      return {
        content: text.slice(startIndex, index + 1),
        endIndex: index + 1,
      };
    }
  }

  return null;
}

function buildToolCall(name: string, rawArguments: string): ExtractedToolCall {
  const { args, error } = parseToolArgsSafely(rawArguments);
  return {
    id: crypto.randomUUID(),
    name,
    args,
    parseError: error,
  };
}

function extractTextFormattedToolCalls(text: string): ExtractedToolCall[] {
  const toolCalls: ExtractedToolCall[] = [];

  const toolCallHeaderRe = /Tool call\s+([a-z_]+)\s*:/gi;
  let headerMatch: RegExpExecArray | null;
  while ((headerMatch = toolCallHeaderRe.exec(text)) !== null) {
    const name = headerMatch[1];
    if (!FALLBACK_TOOL_NAMES.has(name)) {
      continue;
    }

    const jsonStart = text.indexOf("{", headerMatch.index + headerMatch[0].length);
    if (jsonStart < 0) {
      continue;
    }

    const balancedJson = extractBalancedBlock(text, jsonStart, "{", "}");
    if (!balancedJson) {
      continue;
    }

    toolCalls.push(buildToolCall(name, balancedJson.content));
    toolCallHeaderRe.lastIndex = balancedJson.endIndex;
  }
  if (toolCalls.length > 0) {
    return toolCalls;
  }

  const invocationRe = /\b([a-z_]+)\s*\(\s*/gi;
  let invocationMatch: RegExpExecArray | null;
  while ((invocationMatch = invocationRe.exec(text)) !== null) {
    const name = invocationMatch[1];
    if (!FALLBACK_TOOL_NAMES.has(name)) {
      continue;
    }

    const argsStart = invocationRe.lastIndex;
    const firstNonSpaceIndex = text.slice(argsStart).search(/\S/);
    if (firstNonSpaceIndex < 0) {
      continue;
    }

    const jsonStart = argsStart + firstNonSpaceIndex;
    if (text[jsonStart] !== "{") {
      continue;
    }

    const balancedJson = extractBalancedBlock(text, jsonStart, "{", "}");
    if (!balancedJson) {
      continue;
    }

    const closingParenIndex = text.slice(balancedJson.endIndex).search(/\)/);
    if (closingParenIndex < 0) {
      continue;
    }

    toolCalls.push(buildToolCall(name, balancedJson.content));
    invocationRe.lastIndex = balancedJson.endIndex + closingParenIndex + 1;
  }

  return toolCalls;
}

export function extractToolCalls(responseMessage: Record<string, unknown>): ExtractedToolCall[] {
  const rawToolCalls = Array.isArray((responseMessage as { tool_calls?: unknown[] }).tool_calls)
    ? (responseMessage as { tool_calls: unknown[] }).tool_calls
    : [];
  const structuredToolCalls = rawToolCalls.flatMap((toolCall) => {
    if (!isRecord(toolCall)) return [];
    const fn = isRecord(toolCall.function) ? toolCall.function : undefined;
    if (!fn || typeof fn.name !== "string" || !fn.name.trim()) return [];
    const { args, error } = parseToolArgsSafely(typeof fn.arguments === "string" ? fn.arguments : "{}");
    return [{
      id: typeof toolCall.id === "string" && toolCall.id.trim() ? toolCall.id : crypto.randomUUID(),
      name: fn.name,
      args,
      parseError: error,
    }];
  });
  if (structuredToolCalls.length > 0) return structuredToolCalls;

  const text = extractAssistantText(responseMessage);
  if (!text) return [];

  const textFormattedToolCalls = extractTextFormattedToolCalls(text);
  if (textFormattedToolCalls.length > 0) return textFormattedToolCalls;

  const toolCalls: ExtractedToolCall[] = [];
  const runRe = /run\s*\(\s*(?:command\s*=\s*)?["']([^"']+)["']\s*\)/g;
  let match: RegExpExecArray | null;
  while ((match = runRe.exec(text)) !== null) {
    toolCalls.push({
      id: crypto.randomUUID(),
      name: "run",
      args: { command: cleanCommand(match[1]) },
      parseError: null,
    });
  }
  if (toolCalls.length > 0) return toolCalls;

  for (const line of text.split("\n")) {
    const stripped = line.replace(/^\s*\d+[.):-]\s*/, "").trim();
    if (!stripped || !COMMAND_VERBS.test(stripped)) continue;
    toolCalls.push({
      id: crypto.randomUUID(),
      name: "run",
      args: { command: cleanCommand(stripped) },
      parseError: null,
    });
  }
  if (toolCalls.length > 0) return toolCalls;

  const patterns = [
    /Tool call run:\s*\n?\{?\s*"?command"?\s*[:=]\s*"([^"]+)"/,
    /<parameter\s+name="command">([^<]+)<\/parameter>/,
    /\[TOOL_CALL\][\s\S]*?--command\s+"([^"]+)"[\s\S]*?\[\/TOOL_CALL\]/,
    /command["\s:=]+["']([^"']+)["']/i,
  ];
  for (const pattern of patterns) {
    const inlineMatch = text.match(pattern);
    if (!inlineMatch) continue;
    return [{
      id: crypto.randomUUID(),
      name: "run",
      args: { command: cleanCommand(inlineMatch[1]) },
      parseError: null,
    }];
  }

  return [];
}

export function isToolError(result: string): boolean {
  return result.includes("not found")
    || result.includes("does not exist")
    || result.includes("requires")
    || result.includes("must be")
    || result.includes("Failed")
    || result.includes("Unknown command")
    || result.includes("Unknown tool")
    || result.includes("error");
}
