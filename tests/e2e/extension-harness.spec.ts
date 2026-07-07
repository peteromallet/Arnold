/**
 * Extension Harness — Playwright e2e tests.
 *
 * Exercises the deterministic test harness route for extension activity region
 * and Extension Manager states: populated, empty, package-error, and repaired-settings.
 *
 * Viewports covered:
 *   - Desktop (1280×720 via Desktop Chrome device)
 *   - Condensed (768×1024 via iPad Mini device)
 *   - Mobile (390×844 via iPhone 13 device)
 *
 * Scenarios:
 *   - /tools/video-editor/harness?scenario=populated
 *   - /tools/video-editor/harness?scenario=empty
 *   - /tools/video-editor/harness?scenario=package-error
 *   - /tools/video-editor/harness?scenario=repaired-settings
 *   - /tools/video-editor/harness?scenario=manager-cycle
 *   - /tools/video-editor/harness?scenario=all
 */

import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

const HARNESS_BASE = '/tools/video-editor/harness';

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

/** Navigate to a harness scenario and wait for DOM content loaded. */
async function goToScenario(page: Page, scenario: string) {
  await page.goto(`${HARNESS_BASE}?scenario=${scenario}`, { waitUntil: 'domcontentloaded' });
}

/**
 * Assert that two locators do not visually overlap.
 *
 * "Overlap" is defined as their bounding boxes intersecting by at least
 * 1px in both axes.  Elements that touch but do not overlap (shared edge)
 * are allowed.
 */
async function expectNoOverlap(a: Locator, b: Locator, labelA: string, labelB: string) {
  const boxA = await a.boundingBox();
  const boxB = await b.boundingBox();

  if (!boxA || !boxB) {
    // One or both elements are not visible / no bounding box — skip check.
    return;
  }

  const overlapX = boxA.x < boxB.x + boxB.width && boxA.x + boxA.width > boxB.x;
  const overlapY = boxA.y < boxB.y + boxB.height && boxA.y + boxA.height > boxB.y;
  const hasAreaOverlap =
    overlapX &&
    overlapY &&
    Math.min(boxA.x + boxA.width, boxB.x + boxB.width) - Math.max(boxA.x, boxB.x) > 0 &&
    Math.min(boxA.y + boxA.height, boxB.y + boxB.height) - Math.max(boxA.y, boxB.y) > 0;

  expect(hasAreaOverlap, `${labelA} and ${labelB} should not overlap`).toBe(false);
}

/** Assert that all child elements of a container do not overlap with each other. */
async function expectNoMutualOverlap(
  container: Locator,
  childSelector: string,
  containerLabel: string,
) {
  const items = container.locator(childSelector);
  const count = await items.count();
  for (let i = 0; i < count; i++) {
    for (let j = i + 1; j < count; j++) {
      await expectNoOverlap(items.nth(i), items.nth(j), `${containerLabel}[${i}]`, `${containerLabel}[${j}]`);
    }
  }
}

// ---------------------------------------------------------------------------
// Desktop viewport tests (1280×720 — chromium-desktop project default)
// ---------------------------------------------------------------------------

test.describe('Extension Harness — Populated', () => {
  test('renders the activity region with status events', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expect(page.locator('[data-video-editor-activity-region="true"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-activity-event]')).toHaveCount(3);
  });

  test('renders the Extension Manager with package cards', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expect(page.locator('[data-video-editor-extension-trust-warning="true"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.inspector-tools"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.shader-pack"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.effect-bundle"]')).toBeVisible();
  });

  test('shows Loaded badges for active extensions', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.inspector-tools"] [data-video-editor-extension-package-state="loaded"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.shader-pack"] [data-video-editor-extension-package-state="loaded"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.effect-bundle"] [data-video-editor-extension-package-state="loaded"]')).toBeVisible();
  });

  test('renders the summary bar with correct counts', async ({ page }) => {
    await goToScenario(page, 'populated');
    const summaryBar = page.locator('[aria-label="Extension summary: 3 packages, 3 loaded"]');
    await expect(summaryBar).toBeVisible();
    await expect(summaryBar).toContainText('3 packages');
    await expect(summaryBar).toContainText('3 loaded');
  });

  test('shows diagnostic badges per package', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.inspector-tools"] [data-video-editor-extension-diag-count="info"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.shader-pack"] [data-video-editor-extension-diag-count="warning"]')).toBeVisible();
  });

  test('activity region and extension manager do not overlap', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expectNoOverlap(
      page.locator('[data-video-editor-activity-region="true"]'),
      page.locator('[data-video-editor-extension-trust-warning="true"]'),
      'activity-region',
      'trust-warning',
    );
  });

  test('package cards do not overlap each other', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-extension-package-id]',
      'package-card',
    );
  });
});

// ---------------------------------------------------------------------------

test.describe('Extension Harness — Empty', () => {
  test('renders the trust warning banner', async ({ page }) => {
    await goToScenario(page, 'empty');
    await expect(page.locator('[data-video-editor-extension-trust-warning="true"]')).toBeVisible();
  });

  test('shows empty state message', async ({ page }) => {
    await goToScenario(page, 'empty');
    await expect(page.locator('[aria-label="No packages in inventory"]')).toBeVisible();
  });

  test('activity region is not rendered when there are no events and no children', async ({ page }) => {
    await goToScenario(page, 'empty');
    await expect(page.locator('[data-video-editor-activity-region="true"]')).not.toBeVisible();
  });

  test('trust warning does not overlap with empty state message', async ({ page }) => {
    await goToScenario(page, 'empty');
    await expectNoOverlap(
      page.locator('[data-video-editor-extension-trust-warning="true"]'),
      page.locator('[aria-label="No packages in inventory"]'),
      'trust-warning',
      'empty-state',
    );
  });
});

// ---------------------------------------------------------------------------

test.describe('Extension Harness — Package Error', () => {
  test('renders all error-state packages', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.broken-config"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.runtime-crash"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.invalid-manifest"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.old-api"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.duplicate-pack"]')).toBeVisible();
  });

  test('shows correct package state badges', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.broken-config"] [data-video-editor-extension-package-state="settings-error"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.runtime-crash"] [data-video-editor-extension-package-state="runtime-error"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.invalid-manifest"] [data-video-editor-extension-package-state="invalid"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.old-api"] [data-video-editor-extension-package-state="incompatible"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.duplicate-pack"] [data-video-editor-extension-package-state="duplicate"]')).toBeVisible();
  });

  test('displays state reasons for error packages', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.broken-config"]')).toContainText('Settings schema validation failed');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.runtime-crash"]')).toContainText('Uncaught TypeError');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.invalid-manifest"]')).toContainText('missing required field');
  });

  test('shows no enable/disable toggles for error packages', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expect(page.locator('[data-video-editor-extension-toggle]')).toHaveCount(0);
  });

  test('renders activity region with error events', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expect(page.locator('[data-video-editor-activity-region="true"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-activity-event-kind="error"]')).toHaveCount(3);
    await expect(page.locator('[data-video-editor-activity-event-kind="warning"]')).toHaveCount(1);
  });

  test('summary bar shows issue counts', async ({ page }) => {
    await goToScenario(page, 'package-error');
    const summaryBar = page.locator('[aria-label="Extension summary: 5 packages, 0 loaded"]');
    await expect(summaryBar).toBeVisible();
    await expect(summaryBar).toContainText('5 packages');
    await expect(summaryBar).toContainText('5 issues');
  });

  test('error package cards do not overlap each other', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-extension-package-id]',
      'error-package-card',
    );
  });

  test('activity region and trust warning do not overlap', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expectNoOverlap(
      page.locator('[data-video-editor-activity-region="true"]'),
      page.locator('[data-video-editor-extension-trust-warning="true"]'),
      'activity-region',
      'trust-warning',
    );
  });
});

// ---------------------------------------------------------------------------

test.describe('Extension Harness — Repaired Settings', () => {
  test('renders repaired, needs-review, and blocked packages', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.repaired-config"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.needs-review"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.settings-blocked"]')).toBeVisible();
  });

  test('all packages show loaded state badge', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.repaired-config"] [data-video-editor-extension-package-state="loaded"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.needs-review"] [data-video-editor-extension-package-state="loaded"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.settings-blocked"] [data-video-editor-extension-package-state="loaded"]')).toBeVisible();
  });

  test('shows repaired settings diagnostic', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.repaired-config"] [data-video-editor-extension-diag-count="info"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.needs-review"] [data-video-editor-extension-diag-count="warning"]')).toBeVisible();
  });

  test('renders activity region with repaired/needs-review/blocked events', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expect(page.locator('[data-video-editor-activity-region="true"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-activity-event-kind="success"]')).toHaveCount(1);
    await expect(page.locator('[data-video-editor-activity-event-kind="warning"]')).toHaveCount(2);
  });

  test('repaired package cards do not overlap each other', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-extension-package-id]',
      'repaired-package-card',
    );
  });
});

// ---------------------------------------------------------------------------

test.describe('Extension Harness — Integrated Manager Cycle', () => {
  test('disable/enable persists through the repository and re-renders the smoke contribution without page refresh', async ({ page }) => {
    await goToScenario(page, 'manager-cycle');

    const extensionId = 'com.reigh.smoke.extension-smoke';
    const packageCard = page.locator(`[data-video-editor-extension-package-id="${extensionId}"]`);
    const toggle = page.locator(`[data-video-editor-extension-toggle="${extensionId}"]`);
    const persistedEnablement = page.getByTestId('extension-manager-cycle-persisted-enablement');
    const packageState = page.getByTestId('extension-manager-cycle-package-state');
    const smokeContribution = page.getByTestId('extension-smoke-status');

    await expect(packageCard).toBeVisible();
    await expect(packageCard).toHaveAttribute('data-video-editor-extension-package-state', 'loaded');
    await expect(packageState).toHaveText('loaded');
    await expect(persistedEnablement).toHaveText('enabled');
    await expect(toggle).toHaveAttribute('aria-label', `Disable ${extensionId}`);
    await expect(smokeContribution).toBeVisible();

    await toggle.click();

    await expect(packageCard).toHaveAttribute('data-video-editor-extension-package-state', 'disabled-by-user');
    await expect(packageState).toHaveText('disabled-by-user');
    await expect(persistedEnablement).toHaveText('disabled');
    await expect(toggle).toHaveAttribute('aria-label', `Enable ${extensionId}`);
    await expect(smokeContribution).toHaveCount(0);

    await toggle.click();

    await expect(packageCard).toHaveAttribute('data-video-editor-extension-package-state', 'loaded');
    await expect(packageState).toHaveText('loaded');
    await expect(persistedEnablement).toHaveText('enabled');
    await expect(toggle).toHaveAttribute('aria-label', `Disable ${extensionId}`);
    await expect(smokeContribution).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// All scenarios grid
// ---------------------------------------------------------------------------

test.describe('Extension Harness — All Scenarios Grid', () => {
  test('renders all four scenario cards', async ({ page }) => {
    await goToScenario(page, 'all');
    await expect(page.locator('[data-video-editor-harness-scenario="populated"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-harness-scenario="empty"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-harness-scenario="package-error"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-harness-scenario="repaired-settings"]')).toBeVisible();
  });

  test('each scenario card has activity region and extension manager', async ({ page }) => {
    await goToScenario(page, 'all');
    const cards = page.locator('[data-video-editor-harness-scenario]');
    const count = await cards.count();
    expect(count).toBe(4);

    for (let i = 0; i < count; i++) {
      const card = cards.nth(i);
      await expect(card.locator('[data-video-editor-activity-region="true"]')).toBeVisible();
      await expect(card.locator('[data-video-editor-extension-trust-warning="true"]')).toBeVisible();
    }
  });

  test('empty scenario card shows "No packages in inventory"', async ({ page }) => {
    await goToScenario(page, 'all');
    const emptyCard = page.locator('[data-video-editor-harness-scenario="empty"]');
    await expect(emptyCard.locator('[aria-label="No packages in inventory"]')).toBeVisible();
  });

  test('package-error scenario card shows 5 packages', async ({ page }) => {
    await goToScenario(page, 'all');
    const errorCard = page.locator('[data-video-editor-harness-scenario="package-error"]');
    await expect(errorCard.locator('[aria-label="Extension summary: 5 packages, 0 loaded"]')).toBeVisible();
  });

  test('scenario cards do not overlap each other', async ({ page }) => {
    await goToScenario(page, 'all');
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-harness-scenario]',
      'scenario-card',
    );
  });
});

// ---------------------------------------------------------------------------
// Condensed viewport tests (iPad Mini: 768×1024)
// ---------------------------------------------------------------------------

test.describe('Extension Harness — Condensed Viewport', () => {
  test.use({ viewport: { width: 768, height: 1024 } });

  test('populated: renders trust warning, package cards, and summary', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expect(page.locator('[data-video-editor-extension-trust-warning="true"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.inspector-tools"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.shader-pack"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.effect-bundle"]')).toBeVisible();
    await expect(page.locator('[aria-label="Extension summary: 3 packages, 3 loaded"]')).toBeVisible();
  });

  test('populated: activity region renders with status events', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expect(page.locator('[data-video-editor-activity-region="true"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-activity-event]')).toHaveCount(3);
  });

  test('populated: no overlap between trust warning, activity region, and package cards', async ({ page }) => {
    await goToScenario(page, 'populated');
    const trust = page.locator('[data-video-editor-extension-trust-warning="true"]');
    const activity = page.locator('[data-video-editor-activity-region="true"]');
    await expectNoOverlap(trust, activity, 'trust-warning', 'activity-region');
    await expectNoMutualOverlap(page.locator('body'), '[data-video-editor-extension-package-id]', 'package-card');
  });

  test('empty: renders trust warning and empty state', async ({ page }) => {
    await goToScenario(page, 'empty');
    await expect(page.locator('[data-video-editor-extension-trust-warning="true"]')).toBeVisible();
    await expect(page.locator('[aria-label="No packages in inventory"]')).toBeVisible();
  });

  test('empty: trust warning and empty state do not overlap', async ({ page }) => {
    await goToScenario(page, 'empty');
    await expectNoOverlap(
      page.locator('[data-video-editor-extension-trust-warning="true"]'),
      page.locator('[aria-label="No packages in inventory"]'),
      'trust-warning',
      'empty-state',
    );
  });

  test('package-error: renders all error-state packages with correct badges', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.broken-config"] [data-video-editor-extension-package-state="settings-error"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.runtime-crash"] [data-video-editor-extension-package-state="runtime-error"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.invalid-manifest"] [data-video-editor-extension-package-state="invalid"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.old-api"] [data-video-editor-extension-package-state="incompatible"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.duplicate-pack"] [data-video-editor-extension-package-state="duplicate"]')).toBeVisible();
  });

  test('package-error: error cards do not overlap', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-extension-package-id]',
      'error-package-card',
    );
  });

  test('package-error: summary bar shows issue counts', async ({ page }) => {
    await goToScenario(page, 'package-error');
    const summaryBar = page.locator('[aria-label="Extension summary: 5 packages, 0 loaded"]');
    await expect(summaryBar).toBeVisible();
    await expect(summaryBar).toContainText('5 issues');
  });

  test('repaired-settings: renders all packages with loaded state badges', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.repaired-config"] [data-video-editor-extension-package-state="loaded"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.needs-review"] [data-video-editor-extension-package-state="loaded"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.settings-blocked"] [data-video-editor-extension-package-state="loaded"]')).toBeVisible();
  });

  test('repaired-settings: repaired cards do not overlap', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-extension-package-id]',
      'repaired-package-card',
    );
  });

  test('repaired-settings: activity region shows success and warning events', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expect(page.locator('[data-video-editor-activity-event-kind="success"]')).toHaveCount(1);
    await expect(page.locator('[data-video-editor-activity-event-kind="warning"]')).toHaveCount(2);
  });

  test('all: grid cards render and do not overlap', async ({ page }) => {
    await goToScenario(page, 'all');
    await expect(page.locator('[data-video-editor-harness-scenario="populated"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-harness-scenario="empty"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-harness-scenario="package-error"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-harness-scenario="repaired-settings"]')).toBeVisible();
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-harness-scenario]',
      'scenario-card',
    );
  });
});

// ---------------------------------------------------------------------------
// Mobile viewport tests (iPhone 13: 390×844)
// ---------------------------------------------------------------------------

test.describe('Extension Harness — Mobile Viewport', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('populated: renders trust warning, package cards, and summary', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expect(page.locator('[data-video-editor-extension-trust-warning="true"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.inspector-tools"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.shader-pack"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.effect-bundle"]')).toBeVisible();
  });

  test('populated: no incoherent overlap between key UI regions', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expectNoOverlap(
      page.locator('[data-video-editor-extension-trust-warning="true"]'),
      page.locator('[data-video-editor-activity-region="true"]'),
      'trust-warning',
      'activity-region',
    );
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-extension-package-id]',
      'package-card',
    );
  });

  test('populated: summary bar is visible', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expect(page.locator('[aria-label="Extension summary: 3 packages, 3 loaded"]')).toBeVisible();
  });

  test('empty: renders trust warning and empty state, no overlap', async ({ page }) => {
    await goToScenario(page, 'empty');
    await expect(page.locator('[data-video-editor-extension-trust-warning="true"]')).toBeVisible();
    await expect(page.locator('[aria-label="No packages in inventory"]')).toBeVisible();
    await expectNoOverlap(
      page.locator('[data-video-editor-extension-trust-warning="true"]'),
      page.locator('[aria-label="No packages in inventory"]'),
      'trust-warning',
      'empty-state',
    );
  });

  test('package-error: renders all error badges and state reasons', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.broken-config"] [data-video-editor-extension-package-state="settings-error"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.runtime-crash"] [data-video-editor-extension-package-state="runtime-error"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.invalid-manifest"] [data-video-editor-extension-package-state="invalid"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.old-api"] [data-video-editor-extension-package-state="incompatible"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.duplicate-pack"] [data-video-editor-extension-package-state="duplicate"]')).toBeVisible();
  });

  test('package-error: error cards do not overlap', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-extension-package-id]',
      'error-package-card',
    );
  });

  test('package-error: summary bar shows 5 packages 0 loaded', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expect(page.locator('[aria-label="Extension summary: 5 packages, 0 loaded"]')).toBeVisible();
  });

  test('package-error: activity region shows error events', async ({ page }) => {
    await goToScenario(page, 'package-error');
    await expect(page.locator('[data-video-editor-activity-event-kind="error"]')).toHaveCount(3);
  });

  test('repaired-settings: all packages visible with loaded badges', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.repaired-config"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.needs-review"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.settings-blocked"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-extension-package-id="ext.repaired-config"] [data-video-editor-extension-package-state="loaded"]')).toBeVisible();
  });

  test('repaired-settings: repaired cards do not overlap', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-extension-package-id]',
      'repaired-package-card',
    );
  });

  test('repaired-settings: activity region events are visible', async ({ page }) => {
    await goToScenario(page, 'repaired-settings');
    await expect(page.locator('[data-video-editor-activity-event-kind="success"]')).toHaveCount(1);
    await expect(page.locator('[data-video-editor-activity-event-kind="warning"]')).toHaveCount(2);
  });

  test('all: grid renders four cards without overlap', async ({ page }) => {
    await goToScenario(page, 'all');
    await expect(page.locator('[data-video-editor-harness-scenario="populated"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-harness-scenario="empty"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-harness-scenario="package-error"]')).toBeVisible();
    await expect(page.locator('[data-video-editor-harness-scenario="repaired-settings"]')).toBeVisible();
    await expectNoMutualOverlap(
      page.locator('body'),
      '[data-video-editor-harness-scenario]',
      'scenario-card',
    );
  });
});

// ---------------------------------------------------------------------------
// Route accessibility
// ---------------------------------------------------------------------------

test.describe('Extension Harness — Route accessibility', () => {
  test('harness route loads without errors', async ({ page }) => {
    const response = await page.goto(`${HARNESS_BASE}?scenario=populated`, { waitUntil: 'domcontentloaded' });
    expect(response?.ok()).toBe(true);
    await expect(page.locator('vite-error-overlay')).toHaveCount(0);
  });

  test('harness page has correct title', async ({ page }) => {
    await goToScenario(page, 'populated');
    await expect(page.locator('h1')).toContainText('Extension Harness');
  });

  test('invalid scenario param falls back to populated', async ({ page }) => {
    await page.goto(`${HARNESS_BASE}?scenario=nonexistent`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Populated');
    await expect(page.locator('[data-video-editor-extension-package-id="ext.inspector-tools"]')).toBeVisible();
  });
});
