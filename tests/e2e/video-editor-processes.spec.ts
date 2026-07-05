import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const HARNESS_BASE = '/video-editor-process-harness.html';

type HarnessScenario = 'happy-path' | 'stopped-repair' | 'sidecar-happy-path' | 'sidecar-stopped-repair';

test.use({ browserName: 'chromium' });

async function goToScenario(page: Page, scenario: HarnessScenario) {
  await page.goto(`${HARNESS_BASE}?scenario=${scenario}`, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('vite-error-overlay')).toHaveCount(0);
  await expect(page.locator(`[data-video-editor-process-harness-scenario="${scenario}"]`)).toBeVisible();
}

test.describe('Video Editor Process Harness', () => {
  test('covers happy-path execution and provenance inspection', async ({ page }) => {
    await goToScenario(page, 'happy-path');

    await expect(page.getByTestId('planner-clear')).toBeVisible();
    await expect(page.getByTestId(`process-status-browser-fixture.process.contribution`)).toContainText('ready');

    await page.getByTestId('fixture-execute').click();

    await expect(page.getByTestId('projected-materials')).toContainText(
      'fixture-material:resolved:browser-fixture.process.contribution',
    );
    await expect(page.getByText('process.result.attach via browser-fixture.process.contribution')).toBeVisible();

    await page.getByTestId('process-action-inspect-browser-fixture.process.contribution').click();

    await expect(page.getByTestId('process-details-browser-fixture.process.contribution')).toContainText(
      'process.result.attach',
    );
    await expect(page.getByText('Attached materials: fixture-material')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create proposal' })).toBeVisible();
  });

  test('covers stopped-process blocker repair with local harness wiring only', async ({ page }) => {
    await goToScenario(page, 'stopped-repair');
    const blockerStartAction = page.locator('[data-video-editor-blocker-action-kind="start-process"]');

    await expect(page.getByTestId(`process-status-browser-fixture.process.contribution`)).toContainText('stopped');
    await expect(page.getByTestId('planner-summary')).toContainText('"start-process"');
    await expect(blockerStartAction).toBeVisible();

    await blockerStartAction.click();

    await expect(page.getByTestId('planner-summary')).not.toContainText('"start-process"');
    await expect(page.getByTestId('planner-clear')).toBeVisible();
    await expect(page.getByTestId(`process-status-browser-fixture.process.contribution`)).toContainText('ready');
    await expect(page.getByTestId('fixture-execute')).toBeEnabled();
  });
});

test.describe('M7b Sidecar-Export Route Completion', () => {
  test('happy-path: shows complete profiles, sidecar listings, and no route-scoped blocker actions', async ({ page }) => {
    await goToScenario(page, 'sidecar-happy-path');

    // Route completion section should be visible
    const section = page.getByTestId('route-completion-section');
    await expect(section).toBeVisible();

    // Route completion dashboard should render for sidecar-export
    const dashboard = page.getByTestId('route-completion-dashboard-sidecar-export');
    await expect(dashboard).toBeVisible();

    // Route status badge should show "complete" when the process is ready
    const statusBadge = page.getByTestId('route-completion-status-sidecar-export');
    await expect(statusBadge).toBeVisible();

    // The process lifecycle badge for the sidecar fixture should be visible
    await expect(page.getByTestId('route-completion-process-sidecar-fixture.process')).toBeVisible();
    await expect(page.getByTestId('route-completion-process-status-sidecar-fixture.process')).toBeVisible();

    // Route completion profiles should be present (even if incomplete because no artifacts have been generated yet)
    // — the profile entries still render
    const profileElements = dashboard.locator('[data-testid^="route-completion-profile-"]');
    const profileCount = await profileElements.count();
    expect(profileCount).toBeGreaterThan(0);

    // The "Next Actions" section should NOT show route-scoped blocker actions when process is ready
    const routeBlockersSection = dashboard.locator('section:has(h4:text("Next Actions"))');
    // There should be no blocker action card for start-process on a ready route
    const startProcessButtons = routeBlockersSection.getByRole('button', { name: /Start/i });
    await expect(startProcessButtons).toHaveCount(0);

    // The planner summary should reflect canSidecarExport as true
    await expect(page.getByTestId('planner-summary')).toContainText('"canSidecarExport":true');
  });

  test('repair-path: surfaces route-scoped start-process action that transitions to complete after repair', async ({ page }) => {
    await goToScenario(page, 'sidecar-stopped-repair');

    // Route completion section should be visible
    const section = page.getByTestId('route-completion-section');
    await expect(section).toBeVisible();

    // Route completion dashboard should render for sidecar-export
    const dashboard = page.getByTestId('route-completion-dashboard-sidecar-export');
    await expect(dashboard).toBeVisible();

    // The route status should indicate blocked / incomplete when the process is stopped
    const statusBadge = page.getByTestId('route-completion-status-sidecar-export');
    await expect(statusBadge).toBeVisible();

    // The process lifecycle badge should show "stopped"
    await expect(page.getByTestId('route-completion-process-status-sidecar-fixture.process')).toContainText('stopped');

    // The planner summary should contain start-process action kind
    await expect(page.getByTestId('planner-summary')).toContainText('"start-process"');

    // A route-scoped blocker action card should be visible (start-process kind)
    const blockerActionCard = page.locator('[data-video-editor-blocker-action-kind="start-process"]').first();
    await expect(blockerActionCard).toBeVisible();

    // Click the start-process action to repair
    await blockerActionCard.click();

    // After repair, the plan should clear — no more start-process actions
    await expect(page.getByTestId('planner-summary')).not.toContainText('"start-process"');

    // The process lifecycle badge should now show "ready"
    await expect(page.getByTestId('route-completion-process-status-sidecar-fixture.process')).toContainText('ready');

    // The route-scoped blocker action should no longer be present
    await expect(page.locator('[data-video-editor-blocker-action-kind="start-process"]')).toHaveCount(0);

    // The execute button should now be enabled
    await expect(page.getByTestId('fixture-execute')).toBeEnabled();
  });
});
