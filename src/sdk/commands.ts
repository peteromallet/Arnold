// ---------------------------------------------------------------------------
// M2a — Core SDK boundary: command contracts
// ---------------------------------------------------------------------------
//
// These contracts define the type surface for command registration, handler
// invocation, and target-context discrimination.  The module is kept
// modality-neutral: it exports only the interface contracts with no runtime
// dependency on any video-editor subsystem.
//
// Extracted from src/sdk/index.ts during M2a Step 9 (T11).
// ---------------------------------------------------------------------------

/**
 * Sealed target context union for context-menu contributions.
 *
 * - `clip` — right-click on a single clip
 * - `clip-selection` — right-click when multiple clips are selected
 * - `track` — right-click on a track header or track area
 * - `timeline-area` — right-click on empty timeline area
 *
 * Shot-group contributions are **reserved** and diagnosed rather than
 * silently ignored until the shot-group ambiguity is resolved.
 */
export type TargetContext = 'clip' | 'clip-selection' | 'track' | 'timeline-area';

/**
 * Typed payload discriminator for command invocations originating
 * from a context menu or other target-scoped trigger.
 */
export type TargetContextPayload =
  | { readonly target: 'clip'; readonly clipId: string; readonly trackId: string }
  | { readonly target: 'clip-selection'; readonly clipIds: readonly string[]; readonly trackId: string }
  | { readonly target: 'track'; readonly trackId: string }
  | { readonly target: 'timeline-area' };

/**
 * Context passed to a command handler on invocation.
 *
 * Handlers receive the fully-qualified command ID, the owning extension ID,
 * and an optional `target` payload populated when the command is triggered
 * from a context-menu or other target-scoped surface.
 */
export interface CommandRunContext {
  /** The fully-qualified command ID that was invoked. */
  readonly commandId: string;
  /** The extension that registered the handler. */
  readonly extensionId: string;
  /** The target context, with its typed payload, when applicable. */
  readonly target?: TargetContextPayload;
}

/**
 * A command handler function registered by an extension during activate().
 *
 * May be synchronous or async.  Thrown errors (or rejected promises) are
 * caught by the runtime and published as diagnostics + host toasts — they
 * must not crash the palette, menus, or editor shell.
 */
export type CommandHandler = (ctx: CommandRunContext) => void | Promise<void>;

/** Options for imperative command registration via ctx.commands.registerCommand(). */
export interface CommandRegistrationOptions {
  /** Human-readable label for the palette (defaults to command ID when absent). */
  label?: string;
  /** Category for palette grouping. */
  category?: string;
}
