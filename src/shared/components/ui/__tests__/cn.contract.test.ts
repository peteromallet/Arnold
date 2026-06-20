import { describe, expect, it } from 'vitest';
import { cn } from '../contracts/cn';

describe('ui cn contract', () => {
  it('exports only the canonical cn helper from ui contract entrypoint', async () => {
    const moduleExports = await import('../contracts/cn');
    expect(Object.keys(moduleExports).sort()).toEqual(['cn']);
    expect(typeof moduleExports.cn).toBe('function');
  });

  it('keeps cn callable for class merge behavior', () => {
    const includeB = false;
    expect(cn('a', includeB && 'b', 'c')).toBe('a c');
  });
});
