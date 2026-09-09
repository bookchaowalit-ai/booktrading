import { expect, test } from '@playwright/test';

test.describe('BookFinance public landing page', () => {
  test('renders the Thai landing page and dashboard entry point', async ({ page }) => {
    await page.goto('/th');

    await expect(page).toHaveTitle(/BookFinance/);
    await expect(page.getByRole('heading', { name: /เทรดอย่างชาญฉลาด/ })).toBeVisible();
    await expect(page.getByText('ระบบเทรดอัตโนมัติ', { exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'ดูแดชบอร์ด', exact: true })).toHaveAttribute(
      'href',
      '/th/dashboard',
    );
  });

  test('redirects the root route to a supported locale', async ({ page }) => {
    await page.goto('/');

    await expect(page).toHaveURL(/\/((en)|(th))$/);
    await expect(page).toHaveTitle(/BookFinance/);
  });
});
