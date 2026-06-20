/**
 * transition-example — M8 trusted component transition contribution example.
 *
 * Demonstrates:
 *   1. A `TransitionContribution` declared in the extension manifest.
 *   2. `ctx.transitions.registerRenderer()` during activation with an optional
 *      parameter schema that defines transition parameters (number, select,
 *      boolean, color) backed by the host parameter system.
 *   3. A placeholder renderer (trusted local component reference) that
 *      would render transitions between clips in the browser preview.
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
  TransitionContribution,
  TransitionRenderer,
  TransitionParameterDefinition,
  TransitionParameterSchema,
  TransitionRegistrationOptions,
  TransitionRegistrationService,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Parameter schema — these params are surfaced in the transition inspector
// ---------------------------------------------------------------------------

const EXAMPLE_TRANSITION_SCHEMA: TransitionParameterSchema = [
  {
    name: 'duration',
    label: 'Duration',
    description: 'Transition duration in seconds.',
    type: 'number',
    default: 1.0,
    min: 0.1,
    max: 5.0,
    step: 0.1,
  },
  {
    name: 'easing',
    label: 'Easing',
    description: 'Easing function for the transition.',
    type: 'select',
    default: 'ease-in-out',
    options: [
      { label: 'Ease In Out', value: 'ease-in-out' },
      { label: 'Ease In', value: 'ease-in' },
      { label: 'Ease Out', value: 'ease-out' },
      { label: 'Linear', value: 'linear' },
    ],
  },
  {
    name: 'direction',
    label: 'Direction',
    description: 'Swipe or fade direction.',
    type: 'select',
    default: 'left-to-right',
    options: [
      { label: 'Left to Right', value: 'left-to-right' },
      { label: 'Right to Left', value: 'right-to-left' },
      { label: 'Top to Bottom', value: 'top-to-bottom' },
      { label: 'Bottom to Top', value: 'bottom-to-top' },
    ],
  },
  {
    name: 'softEdges',
    label: 'Soft Edges',
    description: 'Whether to feather the transition edges.',
    type: 'boolean',
    default: true,
  },
];

// ---------------------------------------------------------------------------
// Placeholder renderer — trusted local component reference
// ---------------------------------------------------------------------------

/**
 * A placeholder transition renderer. In a real extension this would be a
 * React component or similar renderable unit. The SDK accepts any
 * `TransitionRenderer` (Record<string, unknown> | function) and the host
 * registry validates at registration time.
 */
const exampleTransitionRenderer: TransitionRenderer = {
  displayName: 'ExampleSwipeTransition',
  __transitionPlaceholder: true,
};

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export const transitionExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.transition' as any,
    version: '1.0.0',
    label: 'Transition Example',
    description:
      'Demonstrates transition contribution with parameter schema via M8 SDK surface.',
    apiVersion: 1,
    contributions: [
      {
        id: 'example-transition' as any,
        kind: 'transition',
        transitionId: 'com.reigh.examples.transition.exampleSwipe',
        label: 'Example Swipe Transition',
        allowBrowserExport: false,
        allowWorkerExport: false,
        order: 10,
      } as TransitionContribution,
    ],
    messages: {
      activated: 'Transition example activated.',
      disposed: 'Transition example disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    const transitions = ctx.transitions as TransitionRegistrationService;

    const options: TransitionRegistrationOptions = {
      label: 'Example Swipe Transition',
      parameterSchema: EXAMPLE_TRANSITION_SCHEMA,
    };

    const handle = transitions.registerRenderer(
      'com.reigh.examples.transition.exampleSwipe',
      exampleTransitionRenderer,
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
  TransitionContribution,
  TransitionRenderer,
  TransitionParameterDefinition,
  TransitionParameterSchema,
  TransitionRegistrationOptions,
  TransitionRegistrationService,
};
