const path = require('path');
const { test, expect } = require('@playwright/test');

test('planner supports drag, keyboard movement, validation, and screenshot evidence', async ({ page }) => {
  await page.route('**/api/v1/plans/validate', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ valid: true, violations: [] }) });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Shape a feasible term sequence/i })).toBeVisible();

  const cs101 = page.getByRole('button', { name: /CS101 Foundations/i });
  const termColumns = page.locator('.term-column');
  await cs101.dragTo(termColumns.nth(1));
  await expect(termColumns.nth(1)).toContainText('CS101');

  const ma101 = page.getByRole('button', { name: /MA101 Calculus I/i });
  await ma101.focus();
  await page.keyboard.press('ArrowRight');
  await expect(termColumns.nth(1)).toContainText('MA101');

  await page.getByRole('button', { name: /Validate plan/i }).click();
  await expect(page.getByRole('status')).toContainText('Server validation passed.');
  await page.screenshot({ path: path.join(__dirname, '../../docs/screenshots/planner.png'), fullPage: true });
});
