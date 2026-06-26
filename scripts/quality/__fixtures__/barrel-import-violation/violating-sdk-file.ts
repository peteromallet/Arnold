/**
 * NEGATIVE FIXTURE — barrel-import violation
 *
 * This file deliberately imports from the public barrel (./index) from
 * within the SDK directory.  The no-barrel-import gate MUST flag this.
 * Used by check-sdk-no-barrel-imports.test.mjs.
 */

// eslint-disable-next-line @typescript-eslint/no-unused-vars
import type { ExtensionContext } from './index';

export const FIXTURE_VIOLATION = 'deliberate-barrel-import';
