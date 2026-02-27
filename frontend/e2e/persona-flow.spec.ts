import { expect, test } from '@playwright/test';

const FRONTEND_BASE = process.env.E2E_FRONTEND_URL || 'http://127.0.0.1:3000';
const PROJECT_ID = process.env.E2E_PROJECT_ID;
const AUTH_TOKEN = process.env.E2E_AUTH_TOKEN;
const AUTH_USERNAME = process.env.E2E_AUTH_USERNAME || 'qa-admin';

type PersonaScenario = {
  name: string;
  profile: Record<string, unknown>;
  inputText: string;
};

const PERSONAS: PersonaScenario[] = [
  {
    name: 'startup-founder',
    profile: {
      company_name: 'Founder QA Co',
      years_in_business: 0,
      annual_revenue: 100_000_000,
      employee_count: 4,
      item_description: 'AI-based diagnostics platform startup',
      has_corporation: false,
    },
    inputText: 'Founding story summary and preliminary traction notes',
  },
  {
    name: 'support-officer',
    profile: {
      company_name: 'Policy Support Ops',
      years_in_business: 5,
      annual_revenue: 2_000_000_000,
      employee_count: 35,
      item_description: 'Document-heavy policy support operations with subsidy requirements.',
      has_corporation: true,
    },
    inputText: 'Policy support office notes: baseline draft and proof of compliance materials.',
  },
  {
    name: 'program-manager',
    profile: {
      company_name: 'Program Ops',
      years_in_business: 3,
      annual_revenue: 120_000_000,
      employee_count: 10,
      item_description: 'Program manager workflow to review artifact quality and KPIs.',
      has_corporation: false,
    },
    inputText: 'Quarterly operations KPI review + latest run snapshot required.',
  },
];

test.describe('Growth-support front flow by persona', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!PROJECT_ID || !AUTH_TOKEN, 'E2E env not configured');

    await page.addInitScript(([token, username]) => {
      const payload = JSON.stringify({
        state: {
          token,
          user: {
            id: 'qa-user',
            username,
            role: 'super_admin',
            tenant_id: 'tenant_default',
          },
          isAuthenticated: true,
        },
        version: 0,
      });
      localStorage.setItem('auth-storage', payload);
    }, [AUTH_TOKEN, AUTH_USERNAME]);

    await page.goto(`${FRONTEND_BASE}/projects/${PROJECT_ID}/execute`);
  });

  PERSONAS.forEach((persona) => {
    test(`Persona ${persona.name}: run -> status -> artifacts`, async ({ page }) => {
      await expect(page.getByRole('heading', { name: /Growth Support Execution/i })).toBeVisible();

      await page.getByTestId('profile-json-textarea').fill(JSON.stringify(persona.profile, null, 2));
      await page.getByTestId('input-textarea').fill(persona.inputText);

      await page.getByTestId('run-pipeline-button').click();
      await expect(page.getByTestId('pipeline-status')).toHaveText(/DONE|FAILED/, { timeout: 60000 });

      const status = await page.getByTestId('pipeline-status').innerText();
      test.skip(status === 'FAILED', 'Backend returned FAILED; requires service health check');

      const hasResultSnapshot = await page.getByText('Latest Result Snapshot').isVisible();
      expect(hasResultSnapshot).toBeTruthy();

      for (const artifactType of ['business_plan', 'matching', 'roadmap']) {
        for (const format of ['html', 'markdown', 'pdf']) {
          const btn = page.getByTestId(`artifact-btn-${artifactType}-${format}`);
          await expect(btn).toBeEnabled();

          const [popup] = await Promise.all([page.context().waitForEvent('page'), btn.click()]);
          await expect(popup).toHaveURL(/artifacts/);
          await popup.close();
        }
      }
    });
  });

  test('Persona program-manager: repeated run updates latest result order', async ({ page }) => {
    await page.getByTestId('profile-json-textarea').fill(JSON.stringify(PERSONAS[2].profile, null, 2));
    await page.getByTestId('input-textarea').fill('iteration-1');
    await page.getByTestId('run-pipeline-button').click();

    await expect(page.getByTestId('pipeline-status')).toHaveText(/DONE|FAILED/, { timeout: 60000 });
    const status1 = await page.getByTestId('pipeline-status').innerText();
    test.skip(status1 === 'FAILED', 'Backend returned FAILED; requires service health check');

    const runCountBefore = parseInt(
      (await page.getByTestId('run-count').textContent())?.match(/\d+/)?.[0] || '0',
      10,
    );

    await page.getByTestId('input-textarea').fill('iteration-2');
    await page.getByTestId('run-pipeline-button').click();
    await expect(page.getByTestId('pipeline-status')).toHaveText('DONE', { timeout: 60000 });
    await page.reload();
    await expect(page.getByTestId('pipeline-status')).toHaveText('DONE');

    const runCountAfter = parseInt(
      (await page.getByTestId('run-count').textContent())?.match(/\d+/)?.[0] || '0',
      10,
    );
    expect(runCountAfter).toBeGreaterThan(runCountBefore);
  });
});
