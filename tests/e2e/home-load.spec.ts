import { expect, test } from '@playwright/test';

test('loads the unauthenticated home route', async ({ page }) => {
  const response = await page.goto('/home', { waitUntil: 'domcontentloaded' });

  expect(response?.ok()).toBe(true);
  await expect(page.locator('#root')).toBeAttached();
  await expect(page.locator('body')).toBeVisible();
  await expect(page.locator('vite-error-overlay')).toHaveCount(0);
});
