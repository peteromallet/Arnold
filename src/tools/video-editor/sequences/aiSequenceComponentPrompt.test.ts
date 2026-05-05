/**
 * Regression guard for the agent's system prompt. The CONTROLS manifest
 * contract is the load-bearing instruction that drives the new
 * primary/secondary controls UI — silently dropping it would let the agent
 * stop emitting CONTROLS, which the validator would then reject as a hard
 * error for every generation. This test reads the templates source as text
 * so the assertion runs in the standard vitest pass without needing the
 * Deno edge runtime.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const templatesPath = path.resolve(
  __dirname,
  '../../../../supabase/functions/ai-generate-sequence-component/templates.ts',
);

describe('ai-generate-sequence-component system prompt', () => {
  const source = readFileSync(templatesPath, 'utf8');

  it('declares the controls manifest contract section', () => {
    expect(source).toContain('Controls manifest contract');
  });

  it('lists every supported control type and forbids inventing new ones', () => {
    for (const t of ['number', 'boolean', 'text', 'color', 'enum', 'slider']) {
      expect(source).toContain(`"${t}"`);
    }
    expect(source).toMatch(/Type allowlist is FIXED/);
  });

  it('requires an explicit primary/secondary priority on every control', () => {
    expect(source).toMatch(/"priority": "primary" \| "secondary"/);
    expect(source).toMatch(/Mark a control "primary" only if/);
    expect(source).toMatch(/Most controls should be "secondary"/);
  });

  it('exposes CONTROLS in the envelope output rules', () => {
    expect(source).toMatch(/\/\/ CONTROLS:/);
  });

  it('teaches cross-coverage between manifest entries and params accesses', () => {
    // Source uses escaped backticks (\`...\`) inside the template literal.
    expect(source).toContain('Every entry\'s "name" MUST be referenced as \\`params.<name>\\`');
    expect(source).toContain('matching CONTROLS entry');
  });
});
