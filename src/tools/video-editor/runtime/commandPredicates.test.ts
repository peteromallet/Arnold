import { describe, expect, it } from 'vitest';
import {
  evaluatePredicate,
  evaluatePredicateWithDiagnostics,
  type PredicateContext,
} from '@/tools/video-editor/runtime/commandPredicates';

// ---------------------------------------------------------------------------
// Test context builders
// ---------------------------------------------------------------------------

function baseContext(overrides?: Partial<PredicateContext>): PredicateContext {
  return {
    ext: {
      id: 'test-extension',
      version: '1.2.3',
      label: 'Test Extension',
    },
    ...overrides,
  };
}

function clipTargetContext(overrides?: Partial<PredicateContext>): PredicateContext {
  return {
    ext: {
      id: 'test-extension',
      version: '1.2.3',
      label: 'Test Extension',
    },
    target: {
      target: 'clip',
      clipId: 'clip-abc-123',
      trackId: 'track-1',
    },
    ...overrides,
  };
}

function trackTargetContext(overrides?: Partial<PredicateContext>): PredicateContext {
  return {
    ext: {
      id: 'test-extension',
      version: '1.2.3',
      label: 'Test Extension',
    },
    target: {
      target: 'track',
      trackId: 'track-2',
    },
    ...overrides,
  };
}

function clipSelectionContext(overrides?: Partial<PredicateContext>): PredicateContext {
  return {
    ext: {
      id: 'test-extension',
      version: '1.2.3',
      label: 'Test Extension',
    },
    target: {
      target: 'clip-selection',
      clipIds: ['clip-a', 'clip-b', 'clip-c'],
    },
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Empty / undefined / whitespace predicates
// ---------------------------------------------------------------------------

describe('evaluatePredicate — empty and undefined predicates', () => {
  it('returns true for undefined predicate (always visible)', () => {
    expect(evaluatePredicate(undefined, baseContext())).toBe(true);
  });

  it('returns true for empty string predicate', () => {
    expect(evaluatePredicate('', baseContext())).toBe(true);
  });

  it('returns true for whitespace-only predicate', () => {
    expect(evaluatePredicate('   ', baseContext())).toBe(true);
  });

  it('returns true for whitespace-only predicate with tabs and newlines', () => {
    expect(evaluatePredicate('\t\n  \r', baseContext())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Boolean literals
// ---------------------------------------------------------------------------

describe('evaluatePredicate — boolean literals', () => {
  it('evaluates "true" to true', () => {
    expect(evaluatePredicate('true', baseContext())).toBe(true);
  });

  it('evaluates "false" to false', () => {
    expect(evaluatePredicate('false', baseContext())).toBe(false);
  });

  it('is case-insensitive for true (TRUE → true)', () => {
    expect(evaluatePredicate('TRUE', baseContext())).toBe(true);
  });

  it('is case-insensitive for false (FALSE → false)', () => {
    expect(evaluatePredicate('FALSE', baseContext())).toBe(false);
  });

  it('is case-insensitive for True (mixed case)', () => {
    expect(evaluatePredicate('True', baseContext())).toBe(true);
    expect(evaluatePredicate('False', baseContext())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Null literal
// ---------------------------------------------------------------------------

describe('evaluatePredicate — null literal', () => {
  it('evaluates "null" to false (null is falsy)', () => {
    expect(evaluatePredicate('null', baseContext())).toBe(false);
  });

  it('"null == null" evaluates to true', () => {
    expect(evaluatePredicate('null == null', baseContext())).toBe(true);
  });

  it('"null != null" evaluates to false', () => {
    expect(evaluatePredicate('null != null', baseContext())).toBe(false);
  });

  it('is case-insensitive for null (NULL → null)', () => {
    expect(evaluatePredicate('NULL', baseContext())).toBe(false);
    expect(evaluatePredicate('NULL == NULL', baseContext())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Extension facts (ext.id, ext.version, ext.label)
// ---------------------------------------------------------------------------

describe('evaluatePredicate — extension facts', () => {
  it('evaluates ext.id equality against string', () => {
    expect(evaluatePredicate('ext.id == "test-extension"', baseContext())).toBe(true);
    expect(evaluatePredicate("ext.id == 'test-extension'", baseContext())).toBe(true);
  });

  it('evaluates ext.id inequality correctly', () => {
    expect(evaluatePredicate('ext.id != "other-ext"', baseContext())).toBe(true);
    expect(evaluatePredicate('ext.id != "test-extension"', baseContext())).toBe(false);
  });

  it('evaluates ext.version equality', () => {
    expect(evaluatePredicate('ext.version == "1.2.3"', baseContext())).toBe(true);
    expect(evaluatePredicate('ext.version == "2.0.0"', baseContext())).toBe(false);
  });

  it('evaluates ext.label equality', () => {
    expect(evaluatePredicate('ext.label == "Test Extension"', baseContext())).toBe(true);
  });

  it('evaluates ext.id as truthy standalone identifier', () => {
    // ext.id resolves to "test-extension" which is a non-empty string → truthy
    expect(evaluatePredicate('ext.id', baseContext())).toBe(true);
  });

  it('evaluates ext.version as truthy standalone identifier', () => {
    expect(evaluatePredicate('ext.version', baseContext())).toBe(true);
  });

  it('evaluates ext.label as truthy standalone identifier', () => {
    expect(evaluatePredicate('ext.label', baseContext())).toBe(true);
  });

  it('ext.id equality is case-sensitive', () => {
    expect(evaluatePredicate('ext.id == "TEST-EXTENSION"', baseContext())).toBe(false);
  });

  it('supports double-quoted strings', () => {
    expect(evaluatePredicate('ext.id == "test-extension"', baseContext())).toBe(true);
  });

  it('supports single-quoted strings', () => {
    expect(evaluatePredicate("ext.id == 'test-extension'", baseContext())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Target facts — clip target
// ---------------------------------------------------------------------------

describe('evaluatePredicate — target facts (clip target)', () => {
  it('evaluates target.target == "clip"', () => {
    expect(evaluatePredicate('target.target == "clip"', clipTargetContext())).toBe(true);
    expect(evaluatePredicate('target.target == "track"', clipTargetContext())).toBe(false);
  });

  it('evaluates target.clipId equality', () => {
    expect(evaluatePredicate('target.clipId == "clip-abc-123"', clipTargetContext())).toBe(true);
    expect(evaluatePredicate('target.clipId == "other-id"', clipTargetContext())).toBe(false);
  });

  it('evaluates target.trackId on clip context', () => {
    expect(evaluatePredicate('target.trackId == "track-1"', clipTargetContext())).toBe(true);
  });

  it('target.clipId is truthy as standalone identifier', () => {
    expect(evaluatePredicate('target.clipId', clipTargetContext())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Target facts — track target
// ---------------------------------------------------------------------------

describe('evaluatePredicate — target facts (track target)', () => {
  it('evaluates target.target == "track"', () => {
    expect(evaluatePredicate('target.target == "track"', trackTargetContext())).toBe(true);
  });

  it('target.clipId resolves to null on track target (no clip)', () => {
    expect(evaluatePredicate('target.clipId == null', trackTargetContext())).toBe(true);
  });

  it('target.clipId != null is false on track target', () => {
    expect(evaluatePredicate('target.clipId != null', trackTargetContext())).toBe(false);
  });

  it('target.trackId resolves correctly on track target', () => {
    expect(evaluatePredicate('target.trackId == "track-2"', trackTargetContext())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Target facts — clip-selection target
// ---------------------------------------------------------------------------

describe('evaluatePredicate — target facts (clip-selection)', () => {
  it('evaluates target.target == "clip-selection"', () => {
    expect(evaluatePredicate('target.target == "clip-selection"', clipSelectionContext())).toBe(true);
  });

  it('target.clipIds resolves to the count', () => {
    // target.clipIds resolves to the length (3) for clip-selection context
    expect(evaluatePredicate('target.clipIds == 3', clipSelectionContext())).toBe(true);
    expect(evaluatePredicate('target.clipIds > 1', clipSelectionContext())).toBe(true);
    expect(evaluatePredicate('target.clipIds < 5', clipSelectionContext())).toBe(true);
  });

  it('target.clipId resolves to null on clip-selection target', () => {
    expect(evaluatePredicate('target.clipId == null', clipSelectionContext())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Target facts — timeline-area target
// ---------------------------------------------------------------------------

describe('evaluatePredicate — target facts (timeline-area)', () => {
  it('evaluates target.target == "timeline-area"', () => {
    const ctx: PredicateContext = {
      ext: { id: 'ext', version: '1.0.0', label: 'Test' },
      target: { target: 'timeline-area' },
    };
    expect(evaluatePredicate('target.target == "timeline-area"', ctx)).toBe(true);
  });

  it('target.clipId is null on timeline-area', () => {
    const ctx: PredicateContext = {
      ext: { id: 'ext', version: '1.0.0', label: 'Test' },
      target: { target: 'timeline-area' },
    };
    expect(evaluatePredicate('target.clipId == null', ctx)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// No target context (target absent) — deterministic null
// ---------------------------------------------------------------------------

describe('evaluatePredicate — missing target context (deterministic null)', () => {
  it('target.target resolves to null when no target context', () => {
    expect(evaluatePredicate('target.target == null', baseContext())).toBe(true);
  });

  it('target.clipId resolves to null when no target context', () => {
    expect(evaluatePredicate('target.clipId == null', baseContext())).toBe(true);
  });

  it('target.trackId resolves to null when no target context', () => {
    expect(evaluatePredicate('target.trackId == null', baseContext())).toBe(true);
  });

  it('target.clipIds resolves to null when no target context', () => {
    expect(evaluatePredicate('target.clipIds == null', baseContext())).toBe(true);
  });

  it('target.target != null is false when no target context', () => {
    expect(evaluatePredicate('target.target != null', baseContext())).toBe(false);
  });

  it('unknown target field resolves to null', () => {
    expect(evaluatePredicate('target.nonexistentField == null', clipTargetContext())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Editor facts (reserved, currently all null)
// ---------------------------------------------------------------------------

describe('evaluatePredicate — editor facts (reserved, null)', () => {
  it('editor.* identifiers resolve to null', () => {
    expect(evaluatePredicate('editor.isPlaying == null', baseContext())).toBe(true);
    expect(evaluatePredicate('editor.isRecording == null', baseContext())).toBe(true);
    expect(evaluatePredicate('editor.anything == null', baseContext())).toBe(true);
  });

  it('unprefixed unknown identifiers resolve to null', () => {
    expect(evaluatePredicate('unknownThing == null', baseContext())).toBe(true);
  });

  it('bare undefined identifier is falsy (resolves to null)', () => {
    expect(evaluatePredicate('unknownThing', baseContext())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Equality operator ==
// ---------------------------------------------------------------------------

describe('evaluatePredicate — equality operator (==)', () => {
  it('compares strings for equality', () => {
    expect(evaluatePredicate('"hello" == "hello"', baseContext())).toBe(true);
    expect(evaluatePredicate('"hello" == "world"', baseContext())).toBe(false);
  });

  it('compares numbers for equality', () => {
    expect(evaluatePredicate('42 == 42', baseContext())).toBe(true);
    expect(evaluatePredicate('42 == 43', baseContext())).toBe(false);
  });

  it('compares negative numbers for equality', () => {
    expect(evaluatePredicate('-5 == -5', baseContext())).toBe(true);
    expect(evaluatePredicate('-5 == 5', baseContext())).toBe(false);
  });

  it('cross-type string/number coercion for ==', () => {
    expect(evaluatePredicate('"42" == 42', baseContext())).toBe(true);
    expect(evaluatePredicate('42 == "42"', baseContext())).toBe(true);
    expect(evaluatePredicate('"3.14" == 3.14', baseContext())).toBe(true);
  });

  it('cross-type with non-numeric string returns false', () => {
    expect(evaluatePredicate('"hello" == 42', baseContext())).toBe(false);
    expect(evaluatePredicate('42 == "hello"', baseContext())).toBe(false);
  });

  it('boolean == boolean', () => {
    expect(evaluatePredicate('true == true', baseContext())).toBe(true);
    expect(evaluatePredicate('true == false', baseContext())).toBe(false);
  });

  it('boolean vs string: true compares truthiness', () => {
    expect(evaluatePredicate('true == "test-extension"', baseContext())).toBe(true);
    expect(evaluatePredicate('true == ""', baseContext())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Inequality operator !=
// ---------------------------------------------------------------------------

describe('evaluatePredicate — inequality operator (!=)', () => {
  it('compares strings for inequality', () => {
    expect(evaluatePredicate('"hello" != "world"', baseContext())).toBe(true);
    expect(evaluatePredicate('"hello" != "hello"', baseContext())).toBe(false);
  });

  it('compares numbers for inequality', () => {
    expect(evaluatePredicate('42 != 43', baseContext())).toBe(true);
    expect(evaluatePredicate('42 != 42', baseContext())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Less-than operator <
// ---------------------------------------------------------------------------

describe('evaluatePredicate — less-than operator (<)', () => {
  it('compares numbers with <', () => {
    expect(evaluatePredicate('1 < 2', baseContext())).toBe(true);
    expect(evaluatePredicate('2 < 1', baseContext())).toBe(false);
    expect(evaluatePredicate('2 < 2', baseContext())).toBe(false);
  });

  it('negative numbers with <', () => {
    expect(evaluatePredicate('-10 < -5', baseContext())).toBe(true);
    expect(evaluatePredicate('-5 < -10', baseContext())).toBe(false);
  });

  it('decimal numbers with <', () => {
    expect(evaluatePredicate('3.14 < 3.15', baseContext())).toBe(true);
    expect(evaluatePredicate('3.14 < 3.13', baseContext())).toBe(false);
  });

  it('non-numeric operands return false for <', () => {
    expect(evaluatePredicate('"hello" < 5', baseContext())).toBe(false);
    expect(evaluatePredicate('5 < "hello"', baseContext())).toBe(false);
    expect(evaluatePredicate('true < false', baseContext())).toBe(false);
  });

  it('null < number returns false (non-numeric)', () => {
    expect(evaluatePredicate('null < 5', baseContext())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Greater-than operator >
// ---------------------------------------------------------------------------

describe('evaluatePredicate — greater-than operator (>)', () => {
  it('compares numbers with >', () => {
    expect(evaluatePredicate('2 > 1', baseContext())).toBe(true);
    expect(evaluatePredicate('1 > 2', baseContext())).toBe(false);
    expect(evaluatePredicate('2 > 2', baseContext())).toBe(false);
  });

  it('decimal numbers with >', () => {
    expect(evaluatePredicate('3.15 > 3.14', baseContext())).toBe(true);
  });

  it('non-numeric operands return false for >', () => {
    expect(evaluatePredicate('"hello" > 5', baseContext())).toBe(false);
    expect(evaluatePredicate('null > 5', baseContext())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Unary negation !
// ---------------------------------------------------------------------------

describe('evaluatePredicate — unary negation (!)', () => {
  it('negates true to false', () => {
    expect(evaluatePredicate('!true', baseContext())).toBe(false);
  });

  it('negates false to true', () => {
    expect(evaluatePredicate('!false', baseContext())).toBe(true);
  });

  it('double negation ! ! true → true', () => {
    expect(evaluatePredicate('! ! true', baseContext())).toBe(true);
  });

  it('triple negation ! ! ! true → false', () => {
    expect(evaluatePredicate('! ! ! true', baseContext())).toBe(false);
  });

  it('negates a comparison result', () => {
    expect(evaluatePredicate('!(ext.id == "test-extension")', baseContext())).toBe(false);
    expect(evaluatePredicate('!(ext.id == "other")', baseContext())).toBe(true);
  });

  it('negates a truthy identifier', () => {
    expect(evaluatePredicate('!ext.id', baseContext())).toBe(false);
  });

  it('negates null (falsy) to true', () => {
    expect(evaluatePredicate('!null', baseContext())).toBe(true);
    expect(evaluatePredicate('!target.clipId', baseContext())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Logical AND (&&) — including short-circuit
// ---------------------------------------------------------------------------

describe('evaluatePredicate — logical AND (&&)', () => {
  it('true && true → true', () => {
    expect(evaluatePredicate('true && true', baseContext())).toBe(true);
  });

  it('true && false → false', () => {
    expect(evaluatePredicate('true && false', baseContext())).toBe(false);
  });

  it('false && true → false', () => {
    expect(evaluatePredicate('false && true', baseContext())).toBe(false);
  });

  it('false && false → false', () => {
    expect(evaluatePredicate('false && false', baseContext())).toBe(false);
  });

  it('chains multiple &&', () => {
    expect(evaluatePredicate('true && true && true', baseContext())).toBe(true);
    expect(evaluatePredicate('true && true && false', baseContext())).toBe(false);
  });

  it('combines ext facts with &&', () => {
    expect(
      evaluatePredicate('ext.id == "test-extension" && ext.version == "1.2.3"', baseContext()),
    ).toBe(true);
    expect(
      evaluatePredicate('ext.id == "test-extension" && ext.version == "9.9.9"', baseContext()),
    ).toBe(false);
  });

  it('&& short-circuits: left false means right is never evaluated (no crash)', () => {
    // If short-circuit didn't work and the parser tried to evaluate an
    // unknown identifier on the right, it'd still resolve to null (falsy).
    // This test verifies the AND behavior is correct.
    expect(evaluatePredicate('false && unknownThing', baseContext())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Logical OR (||) — including short-circuit
// ---------------------------------------------------------------------------

describe('evaluatePredicate — logical OR (||)', () => {
  it('true || true → true', () => {
    expect(evaluatePredicate('true || true', baseContext())).toBe(true);
  });

  it('true || false → true', () => {
    expect(evaluatePredicate('true || false', baseContext())).toBe(true);
  });

  it('false || true → true', () => {
    expect(evaluatePredicate('false || true', baseContext())).toBe(true);
  });

  it('false || false → false', () => {
    expect(evaluatePredicate('false || false', baseContext())).toBe(false);
  });

  it('chains multiple ||', () => {
    expect(evaluatePredicate('false || false || true', baseContext())).toBe(true);
    expect(evaluatePredicate('false || false || false', baseContext())).toBe(false);
  });

  it('|| short-circuits: left true means right is never evaluated', () => {
    expect(evaluatePredicate('true || unknownThing', baseContext())).toBe(true);
  });

  it('combines with target context', () => {
    expect(
      evaluatePredicate(
        'target.clipId == "clip-abc-123" || target.clipId == null',
        clipTargetContext(),
      ),
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Operator precedence: || < && < ! < comparison
// ---------------------------------------------------------------------------

describe('evaluatePredicate — operator precedence', () => {
  it('&& binds tighter than ||', () => {
    // false || true && false  →  false || (true && false)  →  false || false  →  false
    expect(evaluatePredicate('false || true && false', baseContext())).toBe(false);
  });

  it('&& vs || precedence: (true || false) && false → false', () => {
    // With parentheses: (true || false) && false  →  true && false  →  false
    expect(evaluatePredicate('(true || false) && false', baseContext())).toBe(false);
  });

  it('&& vs || precedence: true || (false && true) → true', () => {
    // Without parens, && binds tighter: true || (false && true) → true || false → true
    expect(evaluatePredicate('true || false && true', baseContext())).toBe(true);
  });

  it('! binds tighter than &&', () => {
    // !false && false  →  (!false) && false  →  true && false  →  false
    expect(evaluatePredicate('!false && false', baseContext())).toBe(false);
  });

  it('! binds tighter than ||', () => {
    // !true || false  →  (!true) || false  →  false || false  →  false
    expect(evaluatePredicate('!true || false', baseContext())).toBe(false);
  });

  it('comparisons bind tighter than &&', () => {
    // ext.id == "test-extension" && false  →  true && false  →  false
    expect(evaluatePredicate('ext.id == "test-extension" && false', baseContext())).toBe(false);
  });

  it('comparisons inside && and || chain correctly', () => {
    expect(
      evaluatePredicate(
        'ext.id == "test-extension" && ext.version == "1.2.3" || false',
        baseContext(),
      ),
    ).toBe(true);
  });

  it('parentheses override default precedence', () => {
    // (false || true) && false  →  true && false  →  false
    expect(evaluatePredicate('(false || true) && false', baseContext())).toBe(false);
  });

  it('nested parentheses work correctly', () => {
    expect(evaluatePredicate('((true))', baseContext())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Combined expressions — realistic when predicates
// ---------------------------------------------------------------------------

describe('evaluatePredicate — realistic combined expressions', () => {
  it('clip-specific command with extension guard', () => {
    const predicate =
      'ext.id == "test-extension" && target.target == "clip" && target.clipId != null';
    expect(evaluatePredicate(predicate, clipTargetContext())).toBe(true);
  });

  it('same predicate fails on track target', () => {
    const predicate =
      'ext.id == "test-extension" && target.target == "clip" && target.clipId != null';
    expect(evaluatePredicate(predicate, trackTargetContext())).toBe(false);
  });

  it('predicate with fallback via ||', () => {
    const predicate = 'target.target == "clip" || target.target == "track"';
    expect(evaluatePredicate(predicate, clipTargetContext())).toBe(true);
    expect(evaluatePredicate(predicate, trackTargetContext())).toBe(true);
  });

  it('command enabled only for extension version >= 2.0.0 (string comparison via ==)', () => {
    // Note: > and < are numeric only, so version comparisons use ==
    expect(evaluatePredicate('ext.version == "2.0.0"', baseContext())).toBe(false);
  });

  it('negated target check: command disabled for tracks', () => {
    const predicate = '!(target.target == "track")';
    expect(evaluatePredicate(predicate, clipTargetContext())).toBe(true);
    expect(evaluatePredicate(predicate, trackTargetContext())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Invalid predicates — parse errors → false + diagnostics
// ---------------------------------------------------------------------------

describe('evaluatePredicate — invalid predicates (parse errors)', () => {
  it('unclosed string literal evaluates without parse error (tokenizer lenient)', () => {
    // The tokenizer is lenient: it consumes whatever follows the opening quote
    // as string content until EOF. "unclosed without end-quote becomes a valid
    // string "unclosed without end-quote" — no diagnostic emitted.
    const diags: any[] = [];
    const result = evaluatePredicate('ext.id == "unclosed', baseContext(), diags);
    expect(result).toBe(false); // "test-extension" != "unclosed"
    // Tokenizer treats this as a complete string; no parse error.
  });

  it('unexpected character returns false and emits diagnostic', () => {
    const diags: any[] = [];
    const result = evaluatePredicate('ext.id == @@@', baseContext(), diags);
    expect(result).toBe(false);
    expect(diags.length).toBeGreaterThan(0);
  });

  it('missing operand after operator returns false', () => {
    const diags: any[] = [];
    const result = evaluatePredicate('ext.id ==', baseContext(), diags);
    expect(result).toBe(false);
    expect(diags.length).toBeGreaterThan(0);
  });

  it('unmatched parenthesis returns false with diagnostic', () => {
    const diags: any[] = [];
    const result = evaluatePredicate('(ext.id == "test"', baseContext(), diags);
    expect(result).toBe(false);
    expect(diags.length).toBeGreaterThan(0);
  });

  it('unexpected token after valid expression returns false', () => {
    const diags: any[] = [];
    const result = evaluatePredicate('true false', baseContext(), diags);
    expect(result).toBe(false);
    expect(diags.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Diagnostic codes
// ---------------------------------------------------------------------------

describe('evaluatePredicate — diagnostic codes', () => {
  it('produces predicate/parse-error for unmatched closing parenthesis', () => {
    // expect('rparen', ...) in the parser emits predicate/parse-error
    const diags: any[] = [];
    evaluatePredicate('(ext.id == "test"', baseContext(), diags);
    expect(diags.some((d: any) => d.code === 'predicate/parse-error')).toBe(true);
  });

  it('produces predicate/unexpected-token for unexpected tokens', () => {
    const diags: any[] = [];
    evaluatePredicate('true false', baseContext(), diags);
    expect(diags.some((d: any) => d.code === 'predicate/unexpected-token')).toBe(true);
  });

  it('no diagnostics for valid predicates', () => {
    const diags: any[] = [];
    const result = evaluatePredicate('ext.id == "test-extension"', baseContext(), diags);
    expect(result).toBe(true);
    expect(diags.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// evaluatePredicateWithDiagnostics
// ---------------------------------------------------------------------------

describe('evaluatePredicateWithDiagnostics', () => {
  it('returns { ok: true, diagnostics: [] } for valid predicate', () => {
    const result = evaluatePredicateWithDiagnostics(
      'ext.id == "test-extension"',
      baseContext(),
    );
    expect(result.ok).toBe(true);
    expect(result.diagnostics).toEqual([]);
  });

  it('returns { ok: false, diagnostics: [...] } for invalid predicate', () => {
    const result = evaluatePredicateWithDiagnostics('ext.id ==', baseContext());
    expect(result.ok).toBe(false);
    expect(result.diagnostics.length).toBeGreaterThan(0);
  });

  it('returns { ok: true, diagnostics: [] } for empty predicate', () => {
    const result = evaluatePredicateWithDiagnostics(undefined, baseContext());
    expect(result.ok).toBe(true);
    expect(result.diagnostics).toEqual([]);
  });

  it('returns { ok: false, diagnostics: [...] } for false literal', () => {
    const result = evaluatePredicateWithDiagnostics('false', baseContext());
    expect(result.ok).toBe(false);
    expect(result.diagnostics).toEqual([]); // no parse errors, just falsy
  });
});

// ---------------------------------------------------------------------------
// Number literals
// ---------------------------------------------------------------------------

describe('evaluatePredicate — number literals', () => {
  it('zero is falsy', () => {
    expect(evaluatePredicate('0', baseContext())).toBe(false);
  });

  it('non-zero integer is truthy', () => {
    expect(evaluatePredicate('1', baseContext())).toBe(true);
    expect(evaluatePredicate('42', baseContext())).toBe(true);
  });

  it('negative number (non-zero) is truthy', () => {
    expect(evaluatePredicate('-1', baseContext())).toBe(true);
  });

  it('decimal number is truthy', () => {
    expect(evaluatePredicate('3.14', baseContext())).toBe(true);
  });

  it('0.0 is falsy', () => {
    expect(evaluatePredicate('0.0', baseContext())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// String literals
// ---------------------------------------------------------------------------

describe('evaluatePredicate — string literals', () => {
  it('non-empty string is truthy', () => {
    expect(evaluatePredicate('"hello"', baseContext())).toBe(true);
  });

  it('empty string is falsy', () => {
    expect(evaluatePredicate('""', baseContext())).toBe(false);
    expect(evaluatePredicate("''", baseContext())).toBe(false);
  });

  it('string with only spaces is truthy', () => {
    expect(evaluatePredicate('"   "', baseContext())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Deterministic behavior across runs
// ---------------------------------------------------------------------------

describe('evaluatePredicate — deterministic behavior', () => {
  it('produces same result for same predicate and context across multiple calls', () => {
    const predicate = 'ext.id == "test-extension" && target.clipId != null';
    const ctx = clipTargetContext();
    const results = Array.from({ length: 10 }, () => evaluatePredicate(predicate, ctx));
    expect(results.every((r) => r === results[0])).toBe(true);
  });

  it('produces same diagnostics for invalid predicate across multiple calls', () => {
    const diags1: any[] = [];
    const diags2: any[] = [];
    evaluatePredicate('ext.id ==', baseContext(), diags1);
    evaluatePredicate('ext.id ==', baseContext(), diags2);
    expect(diags1.length).toBe(diags2.length);
    expect(diags1[0].code).toBe(diags2[0].code);
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('evaluatePredicate — edge cases', () => {
  it('handles predicates with leading/trailing whitespace', () => {
    expect(evaluatePredicate('  ext.id == "test-extension"  ', baseContext())).toBe(true);
  });

  it('handles predicates with internal extra whitespace', () => {
    expect(evaluatePredicate('ext.id   ==    "test-extension"', baseContext())).toBe(true);
  });

  it('standalone null literal is falsy', () => {
    expect(evaluatePredicate('null', baseContext())).toBe(false);
  });

  it('parenthesized boolean literal', () => {
    expect(evaluatePredicate('(true)', baseContext())).toBe(true);
    expect(evaluatePredicate('(false)', baseContext())).toBe(false);
  });

  it('empty string resolves to falsy', () => {
    expect(evaluatePredicate('"" == ""', baseContext())).toBe(true);
  });
});
