/**
 * clip-type-keyframed-example — M9 procedural clip type with schema-backed
 * keyframed parameters.
 *
 * Demonstrates:
 *   1. A `ClipTypeContribution` declared in the extension manifest.
 *   2. `ctx.clipTypes.registerClipType()` during activation with a
 *      parameter schema that defines keyframable parameters (number,
 *      select, boolean, color) backed by the host interpolator.
 *   3. A procedural renderer that receives host-interpolated params
 *      through `ClipRendererProps` and never implements its own
 *      interpolation.
 *   4. An optional callback-style inspector that receives live params
 *      and an `onParamsChange` callback so the host can persist edits.
 *
 * In the composition graph (M4), this clip-type contribution projects a
 * `contribution:clipType:<extensionId>:<contributionId>` node.  Each clip
 * using this clip type emits a `consumes` edge to that node, with
 * resolved/missing/disabled reference-state diagnostics.
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 *
 * @publicContract
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  ClipTypeContribution,
  ClipRenderer,
  ClipInspector,
  ClipParameterDefinition,
  ClipParameterSchema,
  ClipTypeRegistrationOptions,
  ClipTypeRegistrationService,
  KeyframeInterpolation,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Parameter schema — these params are keyframed by the host interpolator
// ---------------------------------------------------------------------------

const KEYFRAMED_CLIP_SCHEMA: ClipParameterSchema = [
  {
    name: 'opacity',
    label: 'Opacity',
    description: 'Clip opacity (0–1). Keyframed with linear interpolation.',
    type: 'number',
    default: 1,
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    name: 'scale',
    label: 'Scale',
    description: 'Uniform scale factor (0.1–5). Keyframed with linear interpolation.',
    type: 'number',
    default: 1,
    min: 0.1,
    max: 5,
    step: 0.01,
  },
  {
    name: 'rotation',
    label: 'Rotation',
    description: 'Rotation in degrees. Keyframed with linear interpolation.',
    type: 'number',
    default: 0,
    min: -360,
    max: 360,
    step: 1,
  },
  {
    name: 'tintColor',
    label: 'Tint Color',
    description: 'Hex color tint applied as a CSS filter. Keyframed with hold interpolation.',
    type: 'color',
    default: '#ffffff',
  },
  {
    name: 'enableTint',
    label: 'Enable Tint',
    description: 'Whether tinting is active. Keyframed with hold interpolation.',
    type: 'boolean',
    default: false,
  },
  {
    name: 'blendMode',
    label: 'Blend Mode',
    description: 'CSS mix-blend-mode for the clip. Keyframed with hold interpolation.',
    type: 'select',
    default: 'normal',
    options: [
      { label: 'Normal', value: 'normal' },
      { label: 'Multiply', value: 'multiply' },
      { label: 'Screen', value: 'screen' },
      { label: 'Overlay', value: 'overlay' },
    ],
  },
];

// ---------------------------------------------------------------------------
// Renderer callbacks
// ---------------------------------------------------------------------------

/**
 * Procedural clip renderer.
 *
 * Receives host-interpolated params. The host guarantees that params
 * are already interpolated from keyframe data before this function is called,
 * so the renderer is purely presentational.
 *
 * The renderer contract is a function that receives ClipRendererProps-like
 * args (clipId, clipTypeId, time, params, width, height) and returns
 * rendering instructions.
 */
const proceduralRenderer: ClipRenderer = (
  _props: Record<string, unknown>,
): Record<string, unknown> => {
  // Resolve params with schema defaults
  const props = _props as {
    clipId: string;
    clipTypeId: string;
    time: number;
    params: Record<string, unknown>;
    width: number;
    height: number;
  };

  const params = props.params ?? {};

  const opacity = (params.opacity as number) ?? 1;
  const scale = (params.scale as number) ?? 1;
  const rotation = (params.rotation as number) ?? 0;
  const tintColor = (params.tintColor as string) ?? '#ffffff';
  const enableTint = (params.enableTint as boolean) ?? false;
  const blendMode = (params.blendMode as string) ?? 'normal';

  // Build a style record the host can apply to the visual clip element
  const style: Record<string, unknown> = {
    opacity: clamp01(opacity),
    transform: `scale(${scale}) rotate(${rotation}deg)`,
    mixBlendMode: blendMode,
  };

  if (enableTint && tintColor !== '#ffffff') {
    // Apply a CSS filter-based tint using sepia/saturate/hue-rotate
    // This is a deterministic pure-function transform.
    style.filter = buildTintFilter(tintColor, 0.5);
  }

  return {
    style,
    debug: {
      clipId: props.clipId,
      time: props.time,
      interpolatedParams: { opacity, scale, rotation, tintColor, enableTint, blendMode },
    },
  };
};

/**
 * Optional clip inspector — a callback-style inspector that receives
 * current params and an onParamsChange handler.
 */
const proceduralInspector: ClipInspector = (
  _props: Record<string, unknown>,
): Record<string, unknown> => {
  const props = _props as {
    clipId: string;
    clipTypeId: string;
    params: Record<string, unknown>;
    onParamsChange: (params: Record<string, unknown>) => void;
  };

  // Return inspector metadata so the host can build a UI panel.
  // The host owns the actual form rendering; this returns the schema
  // and current values so the host can generate the appropriate controls.
  return {
    clipId: props.clipId,
    clipTypeId: props.clipTypeId,
    params: props.params,
    schema: KEYFRAMED_CLIP_SCHEMA,
  };
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

/**
 * Build a deterministic CSS filter string for a hex tint color.
 *
 * Uses a sepia → saturate → hue-rotate pipeline to approximate a tint.
 * This is deterministic — same color always produces the same filter.
 */
function buildTintFilter(hexColor: string, intensity: number): string {
  // Parse hex to RGB
  const r = parseInt(hexColor.slice(1, 3), 16) / 255;
  const g = parseInt(hexColor.slice(3, 5), 16) / 255;
  const b = parseInt(hexColor.slice(5, 7), 16) / 255;

  // Convert RGB to HSL hue (approximate)
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;

  let h = 0;
  if (max !== min) {
    const d = max - min;
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) * 60;
    else if (max === g) h = ((b - r) / d + 2) * 60;
    else h = ((r - g) / d + 4) * 60;
  }

  // Saturate adjustment
  const s = max === 0 ? 0 : (max - min) / max;

  // Build deterministic filter using the hue rotation
  const effectiveIntensity = clamp01(intensity);
  const saturateAmount = 1 + s * effectiveIntensity * 2;

  return `sepia(${effectiveIntensity * 0.3}) saturate(${saturateAmount}) hue-rotate(${h.toFixed(1)}deg)`;
}

// ---------------------------------------------------------------------------
// Extension definition
// ---------------------------------------------------------------------------

export const clipTypeKeyframedExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.clip-type-keyframed' as any,
    version: '1.0.0',
    label: 'Clip-Type Keyframed Example',
    description:
      'Demonstrates a contributed procedural clip type with schema-backed keyframed params via ctx.clipTypes.registerClipType().',
    apiVersion: 1,

    contributions: [
      {
        id: 'clip-type-keyframed-contrib' as any,
        kind: 'clipType',
        label: 'Keyframed Procedural Clip',
        clipTypeId: 'com.reigh.examples.clipType.keyframed',
        allowBrowserExport: false,
        allowWorkerExport: false,
        order: 10,
      } satisfies ClipTypeContribution,
    ],

    messages: {
      'activated':
        'Clip type keyframed example v{{version}} activated — procedural clip type registered.',
      'disposed': 'Clip type keyframed example disposed.',
      'clipType.registered':
        'Registered clip type "{{clipTypeId}}" with {{paramCount}}-param schema.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'clip-type-keyframed/activated',
      message: ctx.services.i18n.t('activated', {
        version: ctx.extension.version,
      }),
    });

    const handle = ctx.clipTypes.registerClipType(
      'com.reigh.examples.clipType.keyframed',
      proceduralRenderer,
      proceduralInspector,
      {
        label: 'Keyframed Procedural Clip',
        parameterSchema: KEYFRAMED_CLIP_SCHEMA,
      } satisfies ClipTypeRegistrationOptions,
    );

    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'clip-type-keyframed/registered',
      message: ctx.services.i18n.t('clipType.registered', {
        clipTypeId: 'com.reigh.examples.clipType.keyframed',
        paramCount: KEYFRAMED_CLIP_SCHEMA.length,
      }),
    });

    return {
      dispose(): void {
        handle.dispose();
        ctx.services.diagnostics.report({
          severity: 'info',
          code: 'clip-type-keyframed/disposed',
          message: ctx.services.i18n.t('disposed'),
        });
      },
    };
  },
});
