// Shared prompt-envelope parser for AI codegen edge functions.
// Lifts the `// FIELD: <value>` line / `// FIELD: <json>` block extraction
// from ai-generate-effect/templates.ts so that other codegen functions
// (e.g. ai-generate-sequence-component) can reuse it.
//
// Domain-specific concerns (KNOWN_TYPOS, validateExtractedEffectCode,
// auto-typo-fix on the code body) intentionally stay in their owning
// templates module, NOT here.

export interface TextRange {
  start: number;
  end: number;
}

export interface ParseEnvelopeOptions {
  /** Field names whose value should be parsed as a balanced JSON array. */
  jsonArrayFields?: string[];
  /** Field names whose value should be parsed as a balanced JSON object. */
  jsonObjectFields?: string[];
}

export interface ParseEnvelopeResult {
  /** Trimmed string values, keyed by field name (empty string when absent). */
  values: Record<string, string>;
  /** Parsed JSON values for fields listed in jsonArrayFields/jsonObjectFields. */
  jsonValues: Record<string, unknown>;
  /** The source text with all matched field ranges and surrounding markdown fences stripped. */
  codeBody: string;
  /** The text ranges that were stripped from the source to form codeBody. */
  ranges: Array<TextRange | null>;
}

export function stripMarkdownFences(text: string): string {
  return text
    .trim()
    .replace(/^\s*```(?:tsx?|jsx?|javascript|typescript)?\s*$/gim, '')
    .replace(/^\s*```\s*$/gim, '')
    .trim();
}

export function getLineEnd(text: string, start: number): number {
  const newlineIndex = text.indexOf('\n', start);
  return newlineIndex === -1 ? text.length : newlineIndex + 1;
}

function escapeFieldName(field: string): string {
  return field.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function buildLinePattern(field: string): RegExp {
  return new RegExp(`^\\s*//\\s*${escapeFieldName(field)}\\s*:\\s*(.*)$`, 'im');
}

function buildMarkerPattern(field: string): RegExp {
  return new RegExp(`^\\s*//\\s*${escapeFieldName(field)}\\s*:\\s*`, 'im');
}

interface BalancedJsonResult {
  raw: string;
  end: number;
}

function findBalanced(
  text: string,
  startIndex: number,
  open: string,
  close: string,
): BalancedJsonResult | null {
  let index = startIndex;
  while (index < text.length && /\s/.test(text[index] ?? '')) {
    index += 1;
  }

  if (text[index] !== open) {
    return null;
  }

  let depth = 0;
  let inString = false;
  let isEscaped = false;

  for (let cursor = index; cursor < text.length; cursor += 1) {
    const char = text[cursor];

    if (inString) {
      if (isEscaped) {
        isEscaped = false;
        continue;
      }

      if (char === '\\') {
        isEscaped = true;
        continue;
      }

      if (char === '"') {
        inString = false;
      }

      continue;
    }

    if (char === '"') {
      inString = true;
      continue;
    }

    if (char === open) {
      depth += 1;
      continue;
    }

    if (char === close) {
      depth -= 1;
      if (depth === 0) {
        return {
          raw: text.slice(index, cursor + 1),
          end: cursor + 1,
        };
      }
    }
  }

  return null;
}

export function findBalancedJsonArray(
  text: string,
  startIndex: number,
): BalancedJsonResult | null {
  return findBalanced(text, startIndex, '[', ']');
}

export function findBalancedJsonObject(
  text: string,
  startIndex: number,
): BalancedJsonResult | null {
  return findBalanced(text, startIndex, '{', '}');
}

function extractLineField(
  text: string,
  field: string,
): { value: string; range: TextRange | null } {
  const match = buildLinePattern(field).exec(text);
  if (!match || match.index === undefined) {
    return { value: '', range: null };
  }

  return {
    value: match[1]?.trim() ?? '',
    range: {
      start: match.index,
      end: getLineEnd(text, match.index),
    },
  };
}

function extractJsonField(
  text: string,
  field: string,
  kind: 'array' | 'object',
): { raw: string; parsed: unknown; range: TextRange | null } {
  const markerMatch = buildMarkerPattern(field).exec(text);
  if (!markerMatch || markerMatch.index === undefined) {
    return { raw: '', parsed: null, range: null };
  }

  const markerStart = markerMatch.index;
  const markerEnd = markerMatch.index + markerMatch[0].length;
  const finder = kind === 'array' ? findBalancedJsonArray : findBalancedJsonObject;
  const balanced = finder(text, markerEnd);

  if (!balanced) {
    return {
      raw: '',
      parsed: null,
      range: {
        start: markerStart,
        end: getLineEnd(text, markerStart),
      },
    };
  }

  let parsed: unknown = null;
  try {
    parsed = JSON.parse(balanced.raw);
  } catch {
    parsed = null;
  }

  return {
    raw: balanced.raw,
    parsed,
    range: {
      start: markerStart,
      end: balanced.end,
    },
  };
}

export function stripRanges(text: string, ranges: Array<TextRange | null>): string {
  return ranges
    .filter((range): range is TextRange => range !== null)
    .sort((left, right) => right.start - left.start)
    .reduce((result, range) => result.slice(0, range.start) + result.slice(range.end), text)
    .trim();
}

export function parseEnvelope(
  text: string,
  fields: string[],
  opts?: ParseEnvelopeOptions,
): ParseEnvelopeResult {
  const normalized = stripMarkdownFences(text);
  const jsonArrayFields = new Set(opts?.jsonArrayFields ?? []);
  const jsonObjectFields = new Set(opts?.jsonObjectFields ?? []);

  const values: Record<string, string> = {};
  const jsonValues: Record<string, unknown> = {};
  const ranges: Array<TextRange | null> = [];

  for (const field of fields) {
    if (jsonArrayFields.has(field) || jsonObjectFields.has(field)) {
      const kind = jsonArrayFields.has(field) ? 'array' : 'object';
      const { raw, parsed, range } = extractJsonField(normalized, field, kind);
      values[field] = raw;
      jsonValues[field] = parsed;
      ranges.push(range);
    } else {
      const { value, range } = extractLineField(normalized, field);
      values[field] = value;
      ranges.push(range);
    }
  }

  const codeBody = stripRanges(normalized, ranges);

  return { values, jsonValues, codeBody, ranges };
}
