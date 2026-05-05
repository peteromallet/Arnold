import type { FC } from 'react';
import type { CompileResult } from './compileWithGlobals.ts';

export interface DynamicComponentRegistryOptions<TProps, TSchema> {
  builtIn: Record<string, FC<TProps>>;
  compile: (code: string) => FC<TProps>;
  compileAsync: (code: string) => Promise<FC<TProps>>;
  /** Equality check used to skip redundant register calls. Default: deep JSON. */
  schemasEqual?: (a?: TSchema, b?: TSchema) => boolean;
  /** Lookup-name normalizer. Default strips a `custom:` prefix. */
  normalizeName?: (name: string) => string;
}

interface DynamicRecord<TProps, TSchema> {
  component: FC<TProps>;
  code: string;
  schema?: TSchema;
}

export class DynamicComponentRegistry<TProps, TSchema = unknown> {
  protected builtIn: Record<string, FC<TProps>>;
  protected dynamic: Record<string, DynamicRecord<TProps, TSchema>> = {};
  protected pendingAsync: Record<string, { code: string; schema?: TSchema }> = {};
  protected _version = 0;
  protected _batchDepth = 0;
  protected _pendingNotify = false;
  protected _listeners = new Set<() => void>();
  protected compile: (code: string) => FC<TProps>;
  protected compileAsync: (code: string) => Promise<FC<TProps>>;
  protected _schemasEqual: (a?: TSchema, b?: TSchema) => boolean;
  protected _normalizeName: (name: string) => string;

  constructor(options: DynamicComponentRegistryOptions<TProps, TSchema>) {
    this.builtIn = { ...options.builtIn };
    this.compile = options.compile;
    this.compileAsync = options.compileAsync;
    this._schemasEqual =
      options.schemasEqual ?? ((a, b) => a === b || JSON.stringify(a) === JSON.stringify(b));
    this._normalizeName =
      options.normalizeName ?? ((name) => (name.startsWith('custom:') ? name.slice(7) : name));
  }

  subscribe = (listener: () => void): (() => void) => {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  };

  getSnapshot = (): number => this._version;

  async batch(fn: () => void | Promise<void>): Promise<void> {
    this._batchDepth += 1;
    try {
      await fn();
    } finally {
      this._batchDepth -= 1;
      if (this._batchDepth === 0 && this._pendingNotify) {
        this._pendingNotify = false;
        this._notify();
      }
    }
  }

  register(name: string, code: string, schema?: TSchema): void {
    const normalized = this._normalizeName(name);
    const existing = this.dynamic[normalized];
    if (existing?.code === code && this._schemasEqual(existing.schema, schema)) return;
    delete this.pendingAsync[normalized];
    const component = this.compile(code);
    this.dynamic[normalized] = { component, code, schema };
    this._notify();
  }

  async registerAsync(name: string, code: string, schema?: TSchema): Promise<void> {
    const normalized = this._normalizeName(name);
    const existing = this.dynamic[normalized];
    if (existing?.code === code && this._schemasEqual(existing.schema, schema)) return;
    this.pendingAsync[normalized] = { code, schema };
    const component = await this.compileAsync(code);
    const pending = this.pendingAsync[normalized];
    if (!pending || pending.code !== code || !this._schemasEqual(pending.schema, schema)) return;
    delete this.pendingAsync[normalized];
    this.dynamic[normalized] = { component, code, schema };
    this._notify();
  }

  unregister(name: string): void {
    const normalized = this._normalizeName(name);
    if (!(normalized in this.dynamic)) return;
    delete this.pendingAsync[normalized];
    delete this.dynamic[normalized];
    this._notify();
  }

  get(name: string): FC<TProps> | undefined {
    const normalized = this._normalizeName(name);
    return this.builtIn[normalized] ?? this.dynamic[normalized]?.component;
  }

  getCode(name: string): string | undefined {
    return this.dynamic[this._normalizeName(name)]?.code;
  }

  getSchema(name: string): TSchema | undefined {
    return this.dynamic[this._normalizeName(name)]?.schema;
  }

  listAll(): string[] {
    return [...new Set([...Object.keys(this.builtIn), ...Object.keys(this.dynamic)])];
  }

  isDynamic(name: string): boolean {
    const normalized = this._normalizeName(name);
    return normalized in this.dynamic && !(normalized in this.builtIn);
  }

  getAllDynamicCode(): Record<string, string> {
    return Object.fromEntries(
      Object.entries(this.dynamic).map(([name, { code }]) => [name, code]),
    );
  }

  protected _notify(): void {
    if (this._batchDepth > 0) {
      this._pendingNotify = true;
      return;
    }
    this._version += 1;
    this._listeners.forEach((listener) => listener());
  }
}

export type { CompileResult };
