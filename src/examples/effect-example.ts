/**
 * effect-example — M7 trusted component effect contribution example.
 *
 * Demonstrates:
 *   1. An `EffectContribution` declared in the extension manifest.
 *   2. `ctx.effects.registerComponent()` during activation with an optional
 *      parameter schema that defines effect parameters (number, select,
 *      boolean, color) backed by the host parameter system.
 *   3. A placeholder component (trusted local component reference) that
 *      would render in the browser preview.
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
  EffectContribution,
  EffectComponent,
  EffectParameterDefinition,
  EffectParameterSchema,
  EffectRegistrationOptions,
  EffectRegistrationService,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Parameter schema — these params are surfaced in the effect inspector
// ---------------------------------------------------------------------------

const EXAMPLE_EFFECT_SCHEMA: EffectParameterSchema = [
  {
    name: 'intensity',
    label: 'Intensity',
    description: 'Effect intensity (0–1).',
    type: 'number',
    default: 0.5,
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    name: 'mode',
    label: 'Mode',
    description: 'Blend mode for the effect.',
    type: 'select',
    default: 'overlay',
    options: [
      { label: 'Overlay', value: 'overlay' },
      { label: 'Multiply', value: 'multiply' },
      { label: 'Screen', value: 'screen' },
    ],
  },
  {
    name: 'enableVignette',
    label: 'Vignette',
    description: 'Whether to apply a vignette overlay.',
    type: 'boolean',
    default: true,
  },
  {
    name: 'tintColor',
    label: 'Tint Color',
    description: 'Hex color tint applied as a CSS filter.',
    type: 'color',
    default: '#ffcc00',
  },
];

// ---------------------------------------------------------------------------
// Placeholder component — trusted local component reference
// ---------------------------------------------------------------------------

/**
 * A placeholder effect component. In a real extension this would be a
 * React component or similar renderable unit. The SDK accepts any
 * `EffectComponent` (Record<string, unknown> | function) and the host
 * registry validates at registration time.
 */
const exampleEffectComponent: EffectComponent = {
  displayName: 'ExampleEffect',
  __effectPlaceholder: true,
};

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export const effectExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.effect' as any,
    version: '1.0.0',
    label: 'Effect Example',
    description:
      'Demonstrates effect contribution with parameter schema via M7 SDK surface.',
    apiVersion: 1,
    contributions: [
      {
        id: 'example-effect' as any,
        kind: 'effect',
        effectId: 'com.reigh.examples.effect.exampleEffect',
        label: 'Example Effect',
        allowBrowserExport: false,
        allowWorkerExport: false,
        order: 10,
      } as EffectContribution,
    ],
    messages: {
      activated: 'Effect example activated.',
      disposed: 'Effect example disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    const effects = ctx.effects as EffectRegistrationService;

    const options: EffectRegistrationOptions = {
      label: 'Example Effect',
      parameterSchema: EXAMPLE_EFFECT_SCHEMA,
    };

    const handle = effects.registerComponent(
      'com.reigh.examples.effect.exampleEffect',
      exampleEffectComponent,
      options,
    );

    ctx.chrome.toast(ctx.services.i18n.t('activated'), 'info');

    return {
      dispose(): void {
        ctx.chrome.toast(ctx.services.i18n.t('disposed'), 'info');
        handle.dispose();
      },
    };
  },
});

/** Re-export types for SDK consumers. */
export type {
  EffectContribution,
  EffectComponent,
  EffectParameterDefinition,
  EffectParameterSchema,
  EffectRegistrationOptions,
  EffectRegistrationService,
};
