/**
 * hello-world-extension — Minimal extension example using @reigh/editor-sdk.
 *
 * Demonstrates the simplest valid extension: a manifest-only declaration
 * with no contributions or activate function.
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 */

import { defineExtension } from '@reigh/editor-sdk';
import type { ReighExtension } from '@reigh/editor-sdk';

export const helloWorldExtension: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.hello-world' as any,
    version: '1.0.0',
    label: 'Hello World Extension',
    description: 'A minimal extension that demonstrates SDK usage.',
    apiVersion: 1,
  },
});
