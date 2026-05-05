// Headless smoke render gate (T14).
//
// Compiles a sequence component via compileSequenceComponentAsync and renders
// one frame using react-dom/server.renderToString. Catches compile errors and
// obvious runtime errors (missing globals, undefined params accesses, etc.)
// before the panel persists the resource to the DB.
//
// FLAG-005 caveat (best-effort gate, NOT a full Remotion mount):
// - This renders via react-dom/server.renderToString, NOT Remotion's Player.
// - It does NOT exercise ThemeProvider — components calling useTheme() outside
//   of a wrapping ThemeProvider may render fine in this gate but fail in the
//   real Remotion Player.
// - It does NOT exercise SequenceContext — components wrapping children in
//   <Sequence> rely on Remotion's runtime context which renderToString does
//   not provide; those components may pass the gate but fail at preview time.
// - useCurrentFrame and useVideoConfig are mocked locally (returning 0 and
//   { fps: 30, width: 320, height: 320 } respectively) so simple draws work.
// A 5-second Promise.race timeout protects against pathological renders.
//
// Caller (SequenceCreatorPanel Save) treats `{ ok: false }` as a hard gate:
// the resource is NOT persisted on failure; the error message surfaces inline.

import { renderToString } from 'react-dom/server.browser';
import {
  Component,
  createElement,
  type ErrorInfo,
  type FC,
  type ReactNode,
} from 'react';
import { compileSequenceComponentAsync } from '@/tools/video-editor/sequences/compileSequenceComponent';
import type { ResolvedTimelineClip } from '@/tools/video-editor/types';

export interface SmokeRenderInput {
  code: string;
  schemaJson: object;
  defaultsJson: object;
  themeId?: string;
  fps?: number;
}

export type SmokeRenderResult =
  | { ok: true }
  | { ok: false; error: string };

const SMOKE_RENDER_TIMEOUT_MS = 5_000;

interface SmokeBoundaryState {
  error: Error | null;
}

class SmokeRenderBoundary extends Component<{ children: ReactNode }, SmokeBoundaryState> {
  state: SmokeBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): SmokeBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, _info: ErrorInfo): void {
    void _info;
    this.state = { error };
  }

  render(): ReactNode {
    if (this.state.error) {
      return createElement('div', {
        'data-testid': 'smoke-render-error',
        'data-error': this.state.error.message,
      });
    }
    return this.props.children;
  }
}

function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | null = null;
  const timeout = new Promise<T>((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
  });
  return Promise.race([
    promise.then((value) => {
      if (timer) clearTimeout(timer);
      return value;
    }),
    timeout,
  ]);
}

const FAKE_CLIP: ResolvedTimelineClip = {
  id: 'smoke-clip',
  clipType: 'smoke-render',
  track: 'smoke-track',
  at: 0,
  from: 0,
  to: 1,
  asset: undefined,
} as unknown as ResolvedTimelineClip;

/**
 * Run a one-frame headless render of `code` to surface compile + obvious
 * runtime errors before persisting the component. Returns `{ ok: true }` on
 * success or `{ ok: false, error }` on failure (compile error, render throw,
 * or 5-second timeout).
 */
export async function smokeRenderSequenceComponent(
  input: SmokeRenderInput,
): Promise<SmokeRenderResult> {
  try {
    return await withTimeout(runSmoke(input), SMOKE_RENDER_TIMEOUT_MS, 'smoke render');
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

async function runSmoke(input: SmokeRenderInput): Promise<SmokeRenderResult> {
  let Component: FC<unknown>;
  try {
    Component = (await compileSequenceComponentAsync(input.code)) as unknown as FC<unknown>;
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }

  const fps = input.fps ?? 30;
  const params = input.defaultsJson ?? {};

  let html = '';
  try {
    const componentProps = {
      clip: FAKE_CLIP,
      params,
      theme: undefined,
      fps,
    };
    html = renderToString(
      createElement(SmokeRenderBoundary, null,
        // Cast through Record<string, unknown> because component accepts a
        // sequence-component prop shape (clip/params/theme/fps), not the
        // standard React Attributes type.
        createElement(Component as FC<Record<string, unknown>>, componentProps as Record<string, unknown>),
      ),
    );
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }

  // The boundary swallows render throws and emits a marker div with the
  // error message. Detect that and surface as a failure.
  if (html.includes('data-testid="smoke-render-error"')) {
    const match = html.match(/data-error="([^"]*)"/);
    return { ok: false, error: match?.[1] ?? 'render error (caught by boundary)' };
  }

  return { ok: true };
}
