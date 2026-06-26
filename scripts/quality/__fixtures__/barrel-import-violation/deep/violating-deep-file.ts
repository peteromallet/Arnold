/**
 * NEGATIVE FIXTURE — barrel-import violation (deep path)
 *
 * This file deliberately imports from the public barrel (../../index) from
 * deep within the SDK directory tree.  The no-barrel-import gate MUST flag
 * both `./index` and `../index` patterns.
 * Used by check-sdk-no-barrel-imports.test.mjs.
 */

// eslint-disable-next-line @typescript-eslint/no-unused-vars
import type { ExtensionManifest } from '../../index';

export const DEEP_FIXTURE_VIOLATION = 'deliberate-deep-barrel-import';
