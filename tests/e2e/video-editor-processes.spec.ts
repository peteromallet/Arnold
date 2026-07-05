import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const HARNESS_BASE = '/video-editor-process-harness.html';

test.use({ browserName: 'chromium' });

async function goToScenario(page: Page, scenario: 'happy-path' | 'stopped-repair') {
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
