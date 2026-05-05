import type { FC } from 'react';

export type CompileResult<TProps> =
  | { ok: true; component: FC<TProps> }
  | { ok: false; error: string };

export interface CompileWithGlobalsOptions {
  transforms?: Array<'jsx' | 'typescript' | 'imports' | 'flow'>;
  jsxRuntime?: 'classic' | 'automatic';
  production?: boolean;
}

let transformSync: typeof import('sucrase').transform | null = null;

async function getTransform(): Promise<typeof import('sucrase').transform> {
  if (!transformSync) {
    const sucrase = await import('sucrase');
    transformSync = sucrase.transform;
  }
  return transformSync;
}

export async function preloadSucrase(): Promise<void> {
  await getTransform();
}

function compileWithTransform<TProps>(
  code: string,
  globals: Record<string, unknown>,
  transform: typeof import('sucrase').transform,
  options?: CompileWithGlobalsOptions,
): CompileResult<TProps> {
  try {
    const result = transform(code, {
      transforms: options?.transforms ?? ['jsx', 'typescript'],
      jsxRuntime: options?.jsxRuntime ?? 'classic',
      production: options?.production ?? true,
    });

    const wrappedCode = `
      var exports = {};
      var module = { exports: exports };
      ${result.code}
      return exports.default || module.exports.default || module.exports;
    `;

    const argNames = Object.keys(globals);
    const argValues = Object.values(globals);

    const factory = new Function(...argNames, wrappedCode) as (
      ...args: unknown[]
    ) => unknown;

    const component = factory(...argValues);

    if (typeof component !== 'function') {
      throw new Error(
        'Compiled code did not produce a valid component (expected a function as default export)',
      );
    }

    return {
      ok: true,
      component: component as FC<TProps>,
    };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export function compileWithGlobalsSync<TProps>(
  code: string,
  globals: Record<string, unknown>,
  options?: CompileWithGlobalsOptions,
): CompileResult<TProps> {
  if (!transformSync) {
    return { ok: false, error: 'Sucrase is not loaded yet.' };
  }
  return compileWithTransform<TProps>(code, globals, transformSync, options);
}

export async function compileWithGlobalsAsync<TProps>(
  code: string,
  globals: Record<string, unknown>,
  options?: CompileWithGlobalsOptions,
): Promise<CompileResult<TProps>> {
  const transform = await getTransform();
  return compileWithTransform<TProps>(code, globals, transform, options);
}
