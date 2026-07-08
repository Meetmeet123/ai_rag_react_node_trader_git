import { test, expect } from '@playwright/test';

function generateUniqueUser() {
  const suffix = Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  return {
    username: `e2e_${suffix}`,
    email: `e2e_${suffix}@example.com`,
    password: 'TestPass123!',
  };
}

test.describe('auth smoke', () => {
  test('register, logout, and login', async ({ page }) => {
    const user = generateUniqueUser();

    await page.goto('/register');

    await page.getByTestId('register-email').fill(user.email);
    await page.getByTestId('register-username').fill(user.username);
    await page.getByTestId('register-password').fill(user.password);
    await page.getByTestId('register-confirm-password').fill(user.password);
    await page.getByTestId('register-submit').click();

    await expect(page.getByText('Dashboard')).toBeVisible();

    // Open user menu and logout
    await page.getByRole('button', { name: user.username.slice(0, 2).toUpperCase() }).click();
    await page.getByRole('button', { name: 'Logout' }).click();

    await expect(page.getByText('Welcome back')).toBeVisible();

    await page.getByTestId('login-email').fill(user.username);
    await page.getByTestId('login-password').fill(user.password);
    await page.getByTestId('login-submit').click();

    await expect(page.getByText('Dashboard')).toBeVisible();
  });
});
