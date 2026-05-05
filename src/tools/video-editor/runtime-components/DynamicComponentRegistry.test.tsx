import { describe, expect, it } from 'vitest';
import type { FC } from 'react';
import { DynamicComponentRegistry } from '@/tools/video-editor/runtime-components/DynamicComponentRegistry';

type Props = { a: number };

function makeComponent(_label: string): FC<Props> {
  return function MockComponent(_props: Props) {
    return null;
  };
}

describe('DynamicComponentRegistry', () => {
  it('registers and resolves a generic component, including the custom: prefix lookup', () => {
    const componentForCode: Record<string, FC<Props>> = {
      'code-v1': makeComponent('v1'),
    };

    const registry = new DynamicComponentRegistry<Props>({
      builtIn: {},
      compile: (code) => componentForCode[code] ?? makeComponent(`fallback:${code}`),
      compileAsync: async (code) => componentForCode[code] ?? makeComponent(`fallback:${code}`),
    });

    registry.register('my-component', 'code-v1');

    expect(registry.get('my-component')).toBe(componentForCode['code-v1']);
    // Default normalizeName strips the `custom:` prefix
    expect(registry.get('custom:my-component')).toBe(componentForCode['code-v1']);
    expect(registry.getCode('custom:my-component')).toBe('code-v1');
    expect(registry.isDynamic('my-component')).toBe(true);
  });

  it('drops the slower async registration when a newer code arrives during the await window', async () => {
    const resolvers = new Map<string, (component: FC<Props>) => void>();
    const componentForCode = new Map<string, FC<Props>>();

    const registry = new DynamicComponentRegistry<Props>({
      builtIn: {},
      compile: () => makeComponent('sync'),
      compileAsync: (code) =>
        new Promise<FC<Props>>((resolve) => {
          resolvers.set(code, resolve);
        }),
    });

    // Start two async registrations for the same key with different code.
    const stale = registry.registerAsync('race', 'old-code');
    const newest = registry.registerAsync('race', 'new-code');

    // Resolve the newer one first — it should win.
    const newComponent = makeComponent('new');
    componentForCode.set('new-code', newComponent);
    resolvers.get('new-code')!(newComponent);
    await newest;

    expect(registry.get('race')).toBe(newComponent);
    expect(registry.getCode('race')).toBe('new-code');

    // Now resolve the stale one. The stale-pending guard MUST drop it
    // because the pendingAsync entry is for `new-code`, not `old-code`.
    const staleComponent = makeComponent('stale');
    componentForCode.set('old-code', staleComponent);
    resolvers.get('old-code')!(staleComponent);
    await stale;

    expect(registry.get('race')).toBe(newComponent);
    expect(registry.getCode('race')).toBe('new-code');
  });
});
