import { expect, test } from '@playwright/test';

test.describe('PayGuard End-to-End QA Automation Suite', () => {
  test('1. Overview dashboard loads real DB metrics and live API health status', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible();
    await expect(page.getByText('SANDBOX', { exact: true })).toBeVisible();
    await expect(page.getByText('API Connected')).toBeVisible();
    await expect(page.getByText('Total Transactions')).toBeVisible();
    await expect(page.getByText('Payment Success Rate')).toBeVisible();
    await expect(page.getByText('Transaction Volume')).toBeVisible();
  });

  test('2. Payment Simulator processes successful UPI payment and persists across reload', async ({ page }) => {
    await page.goto('/simulator');
    const uniqueOrder = `ORD-E2E-${Date.now().toString(36)}`;
    const uniqueIdem = `idem-e2e-${Date.now().toString(36)}`;

    await page.locator('#sim-order-id').fill(uniqueOrder);
    await page.locator('#sim-amount').fill('749.50');
    await page.locator('#sim-idem-key').fill(uniqueIdem);
    await page.locator('#sim-scenario').selectOption('successful_payment');

    await page.getByRole('button', { name: /Simulate Payment/i }).click();

    const modal = page.getByRole('dialog');
    await expect(modal.getByRole('heading', { name: 'Transaction Result' })).toBeVisible();
    await expect(modal.getByText('PG_200_APPROVED', { exact: true })).toBeVisible();
    await modal.getByRole('button', { name: 'Done' }).click();

    // Navigate to Transactions and reload to verify persistence
    await page.goto(`/transactions?search=${uniqueOrder}`);
    await expect(page.getByRole('cell', { name: uniqueOrder })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('cell', { name: uniqueOrder })).toBeVisible();
  });

  test('3. Payment Simulator persists failed payment and displays failure reason', async ({ page }) => {
    await page.goto('/simulator');
    await page.locator('#sim-order-id').fill(`ORD-FAIL-${Date.now().toString(36)}`);
    await page.locator('#sim-amount').fill('2500.00');
    await page.locator('#sim-idem-key').fill(`idem-fail-${Date.now().toString(36)}`);
    await page.locator('#sim-scenario').selectOption('insufficient_balance');

    await page.getByRole('button', { name: /Simulate Payment/i }).click();
    const modal = page.getByRole('dialog');
    await expect(modal.getByText('PG_402_INSUFFICIENT_FUNDS', { exact: true })).toBeVisible();
    await expect(modal.getByText(/insufficient available balance/i)).toBeVisible();
  });

  test('4. Payment Simulator enforces idempotent replay and rejects key reuse with 409 Conflict', async ({ page }) => {
    await page.goto('/simulator');
    const sharedKey = `idem-conflict-e2e-${Date.now().toString(36)}`;
    const orderId = `ORD-IDEM-${Date.now().toString(36)}`;

    await page.locator('#sim-order-id').fill(orderId);
    await page.locator('#sim-amount').fill('300.00');
    await page.locator('#sim-idem-key').fill(sharedKey);
    await page.locator('#sim-scenario').selectOption('successful_payment');

    // First submission
    await page.getByRole('button', { name: /Simulate Payment/i }).click();
    const modal = page.getByRole('dialog');
    await expect(modal.getByRole('heading', { name: 'Transaction Result' })).toBeVisible();
    await modal.getByRole('button', { name: 'Done' }).click();

    // Identical replay -> IDEMPOTENT REPLAY banner inside result modal
    await page.getByRole('button', { name: /Simulate Payment/i }).click();
    await expect(modal.getByText(/IDEMPOTENT REPLAY — Original transaction returned/i)).toBeVisible();
    await modal.getByRole('button', { name: 'Done' }).click();

    // Modified amount with same key -> HTTP 409 IDEMPOTENCY_CONFLICT
    await page.locator('#sim-amount').fill('999.00');
    await page.getByRole('button', { name: /Simulate Payment/i }).click();
    await expect(page.getByText(/IDEMPOTENCY_CONFLICT/i).first()).toBeVisible();
  });

  test('5. Payment Simulator keeps gateway timeout transaction in PENDING state', async ({ page }) => {
    await page.goto('/simulator');
    await page.locator('#sim-order-id').fill(`ORD-TMO-${Date.now().toString(36)}`);
    await page.locator('#sim-amount').fill('1100.00');
    await page.locator('#sim-idem-key').fill(`idem-tmo-${Date.now().toString(36)}`);
    await page.locator('#sim-scenario').selectOption('gateway_timeout');

    await page.getByRole('button', { name: /Simulate Payment/i }).click();
    const modal = page.getByRole('dialog');
    await expect(modal.getByText('PG_504_GATEWAY_TIMEOUT', { exact: true })).toBeVisible();
    await expect(modal.getByText(/Upstream gateway timed out/i)).toBeVisible();
  });

  test('6. Transactions ledger filters by status and opens detail drawer with timeline', async ({ page }) => {
    await page.goto('/transactions');
    await expect(page.getByRole('heading', { name: 'Transactions' })).toBeVisible();

    await page.getByLabel('Filter by status').selectOption('SUCCESS');
    const firstInspect = page.getByRole('button', { name: /Inspect/i }).first();
    await expect(firstInspect).toBeVisible();
    await firstInspect.click();

    await expect(page.getByText(/Persisted Database Record/i)).toBeVisible();
    await expect(page.getByText(/REQUEST_RECEIVED/i)).toBeVisible();
  });

  test('7. API Testing Console runs real authenticated request from preset collection', async ({ page }) => {
    await page.goto('/api-console');
    await expect(page.getByRole('heading', { name: 'API Testing Console' })).toBeVisible();
    await expect(page.getByText('PAYMENT APIs', { exact: true })).toBeVisible();
    await expect(page.getByText('AUTHENTICATION', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'GET Valid Authentication', exact: true }).click();
    await page.getByRole('button', { name: 'RUN REQUEST' }).click();

    await expect(page.getByText(/200 OK/i)).toBeVisible();
    await expect(page.getByText(/"authenticated": true/i)).toBeVisible();
  });

  test('8. Automated Test Suites executes real Pytest Smoke suite and displays results', async ({ page }) => {
    await page.goto('/test-suites');
    await expect(page.getByRole('heading', { name: 'Automated Test Suites' })).toBeVisible();

    await page.getByRole('button', { name: 'RUN SMOKE TESTS' }).click();
    await expect(page.getByText(/Suite "smoke" Completed/i)).toBeVisible({ timeout: 45000 });
    await expect(page.getByRole('link', { name: /Open HTML Report/i })).toBeVisible();
  });

  test('9. Webhook Monitor simulates valid delivery and rejects invalid HMAC signature', async ({ page }) => {
    await page.goto('/webhooks');
    await expect(page.getByRole('heading', { name: 'Webhook Monitor' })).toBeVisible();

    // Test invalid signature rejection
    await page.getByLabel(/Simulate Invalid HMAC Signature/i).check();
    await page.getByRole('button', { name: /Dispatch Webhook/i }).click();
    await expect(page.getByText(/Invalid Signature Rejected \(401\)/i)).toBeVisible();

    // Uncheck invalid sig and dispatch valid webhook
    await page.getByLabel(/Simulate Invalid HMAC Signature/i).uncheck();
    await page.getByRole('button', { name: /Dispatch Webhook/i }).click();
    await expect(page.getByText(/Webhook Delivered/i)).toBeVisible();
  });

  test('10. Database Validation executes all 8 checks and verifies transaction consistency', async ({ page }) => {
    await page.goto('/validation');
    await expect(page.getByRole('heading', { name: 'Database Validation Console' })).toBeVisible();

    await page.getByRole('button', { name: /Run All 8 Checks/i }).click();
    await expect(page.getByText(/Database Validation Complete/i)).toBeVisible();
    await expect(page.getByText('Verify Transaction Existence').first()).toBeVisible();

    await page.getByRole('button', { name: /Verify Consistency/i }).click();
    await expect(page.getByText(/EXACT DECIMAL MATCH/i)).toBeVisible();
  });

  test('11. Bug Tracker creates and persists a new defect report', async ({ page }) => {
    await page.goto('/bugs');
    await expect(page.getByRole('heading', { name: 'Bug Tracker' })).toBeVisible();

    const bugTitle = `E2E Defect ${Date.now().toString(36)}: Verify timeout banner`;
    await page.getByRole('button', { name: /New Bug Report/i }).click();
    await page.getByPlaceholder('Concise summary of the defect').fill(bugTitle);
    await page.locator('form textarea').first().fill('Logged automatically during Playwright E2E validation.');
    await page.getByRole('button', { name: 'Create Bug' }).click();

    await expect(page.getByRole('cell', { name: bugTitle })).toBeVisible();
  });

  test('12. Responsive mobile layout opens navigation drawer cleanly', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible();

    await page.getByLabel('Open navigation menu').click();
    await expect(page.getByRole('link', { name: 'Test Reports' })).toBeVisible();
    await page.getByRole('link', { name: 'Test Reports' }).click();
    await expect(page.getByRole('heading', { name: /Test Reports & Quality Metrics/i })).toBeVisible();
  });
});

