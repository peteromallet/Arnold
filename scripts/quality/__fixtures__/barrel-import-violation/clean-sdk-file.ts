/**
 * NEGATIVE FIXTURE — clean file (no barrel import)
 *
 * This file imports directly from a canonical SDK module, NOT from the
 * public barrel.  The no-barrel-import gate should NOT flag this file.
 * Used by check-sdk-no-barrel-imports.test.mjs.
 */

import type { DisposeHandle } from '../dispose';

export const CLEAN_FIXTURE = 'clean-direct-import';
