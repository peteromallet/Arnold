/**
 * Command predicate evaluator — small host-parsed expression language.
 *
 * Evaluates `when` predicates from contributions against stable ExtensionContext
 * and TargetContext facts.  No arbitrary JavaScript evaluation — the grammar is
 * hand-parsed and evaluated deterministically.
 *
 * Grammar (EBNF-ish, in order of increasing precedence):
 *   expr         := or_expr
 *   or_expr      := and_expr ("||" and_expr)*
 *   and_expr     := not_expr ("&&" not_expr)*
 *   not_expr     := "!" not_expr | comparison
 *   comparison   := primary (("==" | "!=" | "<" | ">") primary)?
 *   primary      := "(" expr ")" | IDENTIFIER | LITERAL
 *   IDENTIFIER   := "ext." field | "target." field | "editor." field
 *   LITERAL      := STRING | NUMBER | "null" | "true" | "false"
 *
 *   field        := alpha alphanum*
 *   STRING       := single-quoted or double-quoted string literal
 *   NUMBER       := optional minus, digits, optional decimal point + digits
 *
 * Behaviour:
 * - Invalid predicates (parse errors) evaluate to `false` and emit diagnostics.
 * - Missing-target fields (e.g. `target.clipId` when target is track) evaluate
 *   to `null` — comparisons with `!= null` can still succeed.
 * - Unknown identifiers evaluate to `null`.
 * - Type coercion: `<` and `>` only on numbers; non-numeric operands produce
 *   `false`.
 */

import type {
  TargetContext,
  ExtensionDiagnostic,
  DiagnosticSeverity,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/** Facts available to `when` predicates at evaluation time. */
export interface PredicateContext {
  /** Extension metadata from ExtensionContext. */
  readonly ext: {
    readonly id: string;
    readonly version: string;
    readonly label: string;
  };
  /** Target context payload (present only for context-menu / target-scoped triggers). */
  readonly target?: {
    readonly target: TargetContext;
    readonly clipId?: string;
    readonly trackId?: string;
    readonly clipIds?: readonly string[];
  };
  /** Editor-scoped facts (extensible; currently minimal). */
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  readonly editor?: {
    // Reserved for future editor facts.
    // readonly isPlaying?: boolean;
    // readonly isRecording?: boolean;
  };
}

/** Result of evaluating a `when` predicate. */
export interface PredicateResult {
  /** Whether the predicate evaluated to `true`. */
  readonly ok: boolean;
  /** Diagnostics produced during evaluation (parse errors, type mismatches). */
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Tokenizer
// ---------------------------------------------------------------------------

type TokenKind =
  | 'identifier'
  | 'string'
  | 'number'
  | 'null'
  | 'true'
  | 'false'
  | 'eq'       // ==
  | 'ne'       // !=
  | 'lt'       // <
  | 'gt'       // >
  | 'not'      // !
  | 'and'      // &&
  | 'or'       // ||
  | 'lparen'   // (
  | 'rparen'   // )
  | 'eof';

interface Token {
  readonly kind: TokenKind;
  readonly value: string;
  readonly pos: number; // 0-indexed offset in source
}

function tokenize(source: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;

  function push(kind: TokenKind, value: string, pos: number): void {
    tokens.push({ kind, value, pos });
  }

  while (i < source.length) {
    const ch = source[i];

    // Whitespace
    if (ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r') {
      i++;
      continue;
    }

    // Two-character operators
    if (ch === '=' && source[i + 1] === '=') {
      push('eq', '==', i);
      i += 2;
      continue;
    }
    if (ch === '!' && source[i + 1] === '=') {
      push('ne', '!=', i);
      i += 2;
      continue;
    }
    if (ch === '&' && source[i + 1] === '&') {
      push('and', '&&', i);
      i += 2;
      continue;
    }
    if (ch === '|' && source[i + 1] === '|') {
      push('or', '||', i);
      i += 2;
      continue;
    }

    // Single-character tokens
    if (ch === '<') { push('lt', '<', i); i++; continue; }
    if (ch === '>') { push('gt', '>', i); i++; continue; }
    if (ch === '!') { push('not', '!', i); i++; continue; }
    if (ch === '(') { push('lparen', '(', i); i++; continue; }
    if (ch === ')') { push('rparen', ')', i); i++; continue; }

    // Strings: single-quoted or double-quoted
    if (ch === "'" || ch === '"') {
      const quote = ch;
      const start = i;
      i++; // skip opening quote
      let val = '';
      while (i < source.length && source[i] !== quote) {
        if (source[i] === '\\' && i + 1 < source.length) {
          i++;
          val += source[i];
        } else {
          val += source[i];
        }
        i++;
      }
      if (i < source.length) {
        i++; // skip closing quote
      }
      push('string', val, start);
      continue;
    }

    // Numbers (including negative)
    if ((ch >= '0' && ch <= '9') || (ch === '-' && i + 1 < source.length && source[i + 1] >= '0' && source[i + 1] <= '9')) {
      const start = i;
      let num = '';
      if (source[i] === '-') { num += '-'; i++; }
      while (i < source.length && source[i] >= '0' && source[i] <= '9') {
        num += source[i];
        i++;
      }
      if (i < source.length && source[i] === '.') {
        num += '.';
        i++;
        while (i < source.length && source[i] >= '0' && source[i] <= '9') {
          num += source[i];
          i++;
        }
      }
      push('number', num, start);
      continue;
    }

    // Identifiers and keywords (null, true, false)
    if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || ch === '_' || ch === '.') {
      const start = i;
      let ident = '';
      while (
        i < source.length &&
        ((source[i] >= 'a' && source[i] <= 'z') ||
          (source[i] >= 'A' && source[i] <= 'Z') ||
          (source[i] >= '0' && source[i] <= '9') ||
          source[i] === '_' ||
          source[i] === '.')
      ) {
        ident += source[i];
        i++;
      }

      // Check for reserved literal keywords
      const lower = ident.toLowerCase();
      if (lower === 'null') { push('null', 'null', start); continue; }
      if (lower === 'true') { push('true', 'true', start); continue; }
      if (lower === 'false') { push('false', 'false', start); continue; }

      push('identifier', ident, start);
      continue;
    }

    // Unrecognized character → treat as a parse error at the token level
    // (the parser will report the error)
    push('identifier', source[i], i);
    i++;
  }

  push('eof', '', source.length);
  return tokens;
}

// ---------------------------------------------------------------------------
// AST
// ---------------------------------------------------------------------------

type AstNode =
  | { readonly kind: 'literal'; readonly type: 'null' | 'boolean' | 'number' | 'string'; readonly value: string | number | boolean | null }
  | { readonly kind: 'identifier'; readonly name: string }
  | { readonly kind: 'unary'; readonly operator: '!'; readonly operand: AstNode }
  | { readonly kind: 'binary'; readonly operator: '==' | '!=' | '<' | '>' | '&&' | '||'; readonly left: AstNode; readonly right: AstNode };

// ---------------------------------------------------------------------------
// Parser (recursive descent)
// ---------------------------------------------------------------------------

class Parser {
  private pos = 0;
  private readonly tokens: Token[];
  private readonly source: string;
  private readonly errors: ExtensionDiagnostic[] = [];

  constructor(source: string, tokens: Token[]) {
    this.source = source;
    this.tokens = tokens;
  }

  getErrors(): readonly ExtensionDiagnostic[] {
    return this.errors;
  }

  private emit(code: string, message: string, pos: number): void {
    this.errors.push({
      severity: 'warning' as DiagnosticSeverity,
      code,
      message,
      detail: { predicate: this.source, position: pos },
    });
  }

  private current(): Token {
    return this.tokens[this.pos] ?? this.tokens[this.tokens.length - 1];
  }

  private advance(): Token {
    const t = this.current();
    if (this.pos < this.tokens.length) this.pos++;
    return t;
  }

  private expect(kind: TokenKind, context: string): Token | null {
    const t = this.current();
    if (t.kind === kind) return this.advance();
    this.emit(
      'predicate/parse-error',
      `Expected ${kind} but found ${t.kind} '${t.value}' at position ${t.pos} in ${context}.`,
      t.pos,
    );
    return null;
  }

  // ---- Entry point --------------------------------------------------------

  parse(): AstNode | null {
    this.pos = 0;
    this.errors.length = 0;

    if (this.current().kind === 'eof') {
      // Empty predicate → treat as true (no condition = always visible).
      return { kind: 'literal', type: 'boolean', value: true };
    }

    const node = this.parseOrExpr();
    if (this.errors.length > 0) return null;

    // Ensure we consumed all tokens
    if (this.current().kind !== 'eof') {
      this.emit(
        'predicate/unexpected-token',
        `Unexpected token '${this.current().value}' at position ${this.current().pos}.`,
        this.current().pos,
      );
      return null;
    }

    return node;
  }

  // ---- or_expr := and_expr ("||" and_expr)* -------------------------------

  private parseOrExpr(): AstNode {
    let left = this.parseAndExpr();
    if (!left) return null as unknown as AstNode; // errors already emitted

    while (this.current().kind === 'or') {
      const op = this.advance().value as '||';
      const right = this.parseAndExpr();
      if (!right) return null as unknown as AstNode;
      left = { kind: 'binary', operator: op, left, right };
    }

    return left;
  }

  // ---- and_expr := not_expr ("&&" not_expr)* ------------------------------

  private parseAndExpr(): AstNode {
    let left = this.parseNotExpr();
    if (!left) return null as unknown as AstNode;

    while (this.current().kind === 'and') {
      const op = this.advance().value as '&&';
      const right = this.parseNotExpr();
      if (!right) return null as unknown as AstNode;
      left = { kind: 'binary', operator: op, left, right };
    }

    return left;
  }

  // ---- not_expr := "!" not_expr | comparison ------------------------------

  private parseNotExpr(): AstNode {
    if (this.current().kind === 'not') {
      this.advance(); // consume '!'
      const operand = this.parseNotExpr();
      if (!operand) return null as unknown as AstNode;
      return { kind: 'unary', operator: '!', operand };
    }

    return this.parseComparison();
  }

  // ---- comparison := primary (("==" | "!=" | "<" | ">") primary)? ---------

  private parseComparison(): AstNode {
    const left = this.parsePrimary();
    if (!left) return null as unknown as AstNode;

    const opKind = this.current().kind;
    if (opKind === 'eq' || opKind === 'ne' || opKind === 'lt' || opKind === 'gt') {
      const op = this.advance().value as '==' | '!=' | '<' | '>';
      const right = this.parsePrimary();
      if (!right) return null as unknown as AstNode;
      return { kind: 'binary', operator: op, left, right };
    }

    return left;
  }

  // ---- primary := "(" expr ")" | IDENTIFIER | LITERAL ---------------------

  private parsePrimary(): AstNode {
    const t = this.current();

    if (t.kind === 'lparen') {
      this.advance(); // consume '('
      const expr = this.parseOrExpr();
      if (!expr) return null as unknown as AstNode;
      if (!this.expect('rparen', 'parenthesized expression')) {
        return null as unknown as AstNode;
      }
      return expr;
    }

    if (t.kind === 'identifier') {
      this.advance();
      return { kind: 'identifier', name: t.value };
    }

    if (t.kind === 'null') { this.advance(); return { kind: 'literal', type: 'null', value: null }; }
    if (t.kind === 'true') { this.advance(); return { kind: 'literal', type: 'boolean', value: true }; }
    if (t.kind === 'false') { this.advance(); return { kind: 'literal', type: 'boolean', value: false }; }
    if (t.kind === 'string') { this.advance(); return { kind: 'literal', type: 'string', value: t.value }; }
    if (t.kind === 'number') {
      this.advance();
      return { kind: 'literal', type: 'number', value: Number(t.value) };
    }

    this.emit(
      'predicate/unexpected-token',
      `Unexpected token '${t.value}' at position ${t.pos}. Expected identifier, literal, or '('.`,
      t.pos,
    );
    return null as unknown as AstNode;
  }
}

// ---------------------------------------------------------------------------
// Evaluator
// ---------------------------------------------------------------------------

type EvalValue = string | number | boolean | null;

/**
 * Resolve an identifier against the PredicateContext.
 * Returns the resolved value, or `null` for unknown/missing facts.
 *
 * Supported facts:
 * - `ext.id`, `ext.version`, `ext.label`
 * - `target.target`, `target.clipId`, `target.trackId`, `target.clipIds`
 * - `editor.*` (reserved, currently all `null`)
 */
function resolveIdentifier(name: string, ctx: PredicateContext): EvalValue {
  // ext.* facts
  if (name === 'ext.id') return ctx.ext.id;
  if (name === 'ext.version') return ctx.ext.version;
  if (name === 'ext.label') return ctx.ext.label;

  // target.* facts
  if (name.startsWith('target.')) {
    const field = name.slice(7); // strip "target."
    if (!ctx.target) return null; // no target context available

    if (field === 'target') return ctx.target.target;
    if (field === 'clipId') return ctx.target.clipId ?? null;
    if (field === 'trackId') return ctx.target.trackId ?? null;
    if (field === 'clipIds') return ctx.target.clipIds ? ctx.target.clipIds.length : null;

    return null; // unknown target field
  }

  // editor.* facts (reserved, currently all null)
  if (name.startsWith('editor.')) {
    return null; // no editor facts defined in M4
  }

  // Unknown identifier
  return null;
}

function evalNode(node: AstNode, ctx: PredicateContext): EvalValue {
  switch (node.kind) {
    case 'literal': {
      return node.value;
    }

    case 'identifier': {
      return resolveIdentifier(node.name, ctx);
    }

    case 'unary': {
      const operand = evalNode(node.operand, ctx);
      // ! operator: coerce to boolean and negate
      return !isTruthy(operand);
    }

    case 'binary': {
      const { operator } = node;

      // Short-circuit evaluation for && and ||
      if (operator === '&&') {
        const leftVal = evalNode(node.left, ctx);
        if (!isTruthy(leftVal)) return false;
        const rightVal = evalNode(node.right, ctx);
        return isTruthy(rightVal);
      }
      if (operator === '||') {
        const leftVal = evalNode(node.left, ctx);
        if (isTruthy(leftVal)) return true;
        const rightVal = evalNode(node.right, ctx);
        return isTruthy(rightVal);
      }

      // Comparison operators
      const left = evalNode(node.left, ctx);
      const right = evalNode(node.right, ctx);

      switch (operator) {
        case '==': return isEqual(left, right);
        case '!=': return !isEqual(left, right);
        case '<': {
          if (typeof left !== 'number' || typeof right !== 'number') return false;
          return left < right;
        }
        case '>': {
          if (typeof left !== 'number' || typeof right !== 'number') return false;
          return left > right;
        }
        default:
          return false;
      }
    }

    default:
      return false;
  }
}

// ---------------------------------------------------------------------------
// Value helpers
// ---------------------------------------------------------------------------

/** Null/empty-string is falsy; everything else is truthy. */
function isTruthy(value: EvalValue): boolean {
  if (value === null) return false;
  if (value === '') return false;
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value !== 0;
  return true; // non-empty strings
}

/** Equality comparison (null-safe, type-coercing for string<->number). */
function isEqual(a: EvalValue, b: EvalValue): boolean {
  // null == null
  if (a === null && b === null) return true;
  if (a === null || b === null) return false;

  // Same type
  if (typeof a === typeof b) return a === b;

  // Cross-type: number vs string → coerce string to number
  if (typeof a === 'number' && typeof b === 'string') {
    const bNum = Number(b);
    return !Number.isNaN(bNum) && a === bNum;
  }
  if (typeof a === 'string' && typeof b === 'number') {
    const aNum = Number(a);
    return !Number.isNaN(aNum) && aNum === b;
  }

  // Boolean vs anything: compare as truthy/falsy
  if (typeof a === 'boolean') return a === isTruthy(b);
  if (typeof b === 'boolean') return isTruthy(a) === b;

  return false;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Evaluate a `when` predicate string against extension and target context.
 *
 * @param when         The predicate string (from a contribution's `when` field),
 *                     or `undefined`/empty (treated as always-visible).
 * @param context      The evaluation context (extension facts, optional target).
 * @param diagnostics  Optional array to which parse/evaluation diagnostics are
 *                     appended.  The caller owns the array lifetime.
 * @returns `true` if the predicate evaluates to true, `false` otherwise.
 *          Invalid predicates and parse errors always return `false`.
 */
export function evaluatePredicate(
  when: string | undefined,
  context: PredicateContext,
  diagnostics?: ExtensionDiagnostic[],
): boolean {
  // No predicate → always visible
  if (!when || when.trim().length === 0) return true;

  const source = when.trim();
  const tokens = tokenize(source);
  const parser = new Parser(source, tokens);

  const ast = parser.parse();

  // Collect parser errors into diagnostics
  const parserErrors = parser.getErrors();
  if (diagnostics) {
    for (const err of parserErrors) {
      diagnostics.push(err);
    }
  }

  // Parse failure → invalid-as-false
  if (!ast || parserErrors.length > 0) return false;

  // Evaluate
  try {
    const result = evalNode(ast, context);
    const ok = isTruthy(result);

    // Standalone identifier not in a comparison context is truthiness-checked.
    // This is already handled: the parser returns the identifier node which
    // evaluates to its resolved value, and isTruthy() determines the result.

    return ok;
  } catch (_err) {
    // Should not happen with our evaluator, but guard anyway.
    if (diagnostics) {
      diagnostics.push({
        severity: 'error',
        code: 'predicate/eval-error',
        message: `Unexpected error evaluating predicate: ${String(_err)}`,
        detail: { predicate: source },
      });
    }
    return false;
  }
}

/**
 * Convenience: evaluate and return a structured result with diagnostics.
 *
 * This is the recommended API for callers that want both the boolean result
 * and any diagnostics in a single call.
 */
export function evaluatePredicateWithDiagnostics(
  when: string | undefined,
  context: PredicateContext,
): PredicateResult {
  const diagnostics: ExtensionDiagnostic[] = [];
  const ok = evaluatePredicate(when, context, diagnostics);
  return { ok, diagnostics };
}
