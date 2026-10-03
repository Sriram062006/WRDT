// Browser end-to-end flow (Playwright). Not part of the build; see docs/TESTING.md.
// Needs: a running API on :8000 with a bootstrapped Owner (owner@wrdt.example.org / OwnerPass123!),
// `vite preview` on :4173, and `npm i -D playwright && npx playwright install chromium`.
import { chromium } from 'playwright';
const BASE = 'http://127.0.0.1:4173';
const results = []; const consoleErrors = []; const badResponses = [];
const step = async (name, fn) => {
  try { await fn(); results.push(['PASS', name]); }
  catch (e) { results.push(['FAIL', name + ' :: ' + String(e.message).split('\n')[0]]); }
};
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } });
const p = await ctx.newPage();
p.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
p.on('response', r => { if (r.url().includes('/api/') && r.status() >= 500) badResponses.push(r.status() + ' ' + r.url()); });
const main = () => p.locator('main');
const nav = (n) => p.locator('aside').getByRole('button', { name: n, exact: true }).click();

await step('login rejects wrong password with a visible error', async () => {
  await p.goto(BASE);
  await p.fill('input[type=email]', 'owner@wrdt.example.org');
  await p.fill('input[type=password]', 'WrongPassword1');
  await p.getByRole('button', { name: 'Login' }).click();
  await p.getByRole('alert').waitFor({ timeout: 8000 });
});
await step('login succeeds and shows dashboard', async () => {
  await p.fill('input[type=password]', 'OwnerPass123!');
  await p.getByRole('button', { name: 'Login' }).click();
  await p.getByRole('heading', { name: 'Dashboard' }).waitFor({ timeout: 8000 });
});
await step('empty dashboard shows zero, not invented numbers', async () => {
  await main().getByText('No collections recorded yet.').waitFor({ timeout: 8000 });
  const txt = await main().innerText();
  if (txt.includes('145,600') || txt.includes('153')) throw new Error('mock figures present');
});
await step('create region via UI', async () => {
  await nav('Regions');
  await main().getByRole('button', { name: 'Add Region' }).first().click();
  await p.getByPlaceholder('e.g. Jagadevi').fill('Jagadevi');
  await p.getByRole('dialog').getByRole('button', { name: 'Save' }).click();
  await main().getByRole('button', { name: 'Jagadevi' }).waitFor();
});
await step('duplicate region name shows server error', async () => {
  await main().getByRole('button', { name: 'Add Region' }).first().click();
  await p.getByPlaceholder('e.g. Jagadevi').fill('jagadevi');
  await p.getByRole('dialog').getByRole('button', { name: 'Save' }).click();
  await p.getByRole('dialog').getByRole('alert').waitFor();
  await p.keyboard.press('Escape');
});
await step('create group inside region', async () => {
  await main().getByRole('button', { name: 'Jagadevi' }).click();
  await main().getByRole('button', { name: 'Add Group' }).first().click();
  await p.getByPlaceholder('e.g. Lakshmi SHG').fill('Lakshmi SHG');
  await p.getByRole('dialog').getByRole('button', { name: 'Save' }).click();
  await main().getByText('Lakshmi SHG').waitFor();
});
await step('add two members', async () => {
  await main().getByRole('button', { name: 'Members' }).click();
  for (const [name, seed] of [['R. Lakshmi', '4400'], ['R. Selvi', '5200']]) {
    await main().getByRole('button', { name: 'Add Member' }).click();
    await p.getByLabel('Member Name').fill(name);
    await p.getByLabel('Previous Savings').fill(seed);
    await p.getByRole('dialog').getByRole('button', { name: 'Save' }).click();
    await main().getByText(name).waitFor();
  }
});
await step('start meeting and open register', async () => {
  await main().getByRole('button', { name: 'Groups' }).click();
  await main().getByRole('button', { name: 'Meetings' }).click();
  await main().getByRole('button', { name: 'Start Meeting' }).first().click();
  await p.getByRole('heading', { name: /Meeting #1/ }).waitFor();
  await p.getByText('R. Lakshmi').first().waitFor();
});
await step('register edit -> unsaved flag -> save', async () => {
  await p.locator('input.cell-input[type=number]').first().fill('5000'); // loan given, row 1
  await p.getByText('Unsaved changes').waitFor();
  await p.getByRole('button', { name: 'Save Register' }).click();
  await p.getByText('All changes saved').waitFor();
  await p.getByText('Unsaved changes').waitFor({ state: 'detached' });
});
await step('server totals: cash in hand = 600 savings - 5000 loan', async () => {
  const t = await main().innerText();
  if (!t.includes('-4,400')) throw new Error('cash in hand not -4,400; got: ' + t.slice(-300));
});
await step('add expense', async () => {
  await p.locator('input[placeholder="₹"]').fill('250');
  await p.getByRole('button', { name: '+', exact: true }).click();
  await main().getByText('₹250').first().waitFor();
});
await step('complete meeting locks the register', async () => {
  await p.getByRole('button', { name: 'Complete Meeting' }).click();
  await p.getByRole('button', { name: 'Yes, complete' }).click();
  await p.getByText('permanently locked').first().waitFor();
  if (await p.getByRole('button', { name: 'Save Register' }).count()) throw new Error('save still offered');
  if (await p.locator('input.cell-input').count()) throw new Error('inputs still editable');
});
await step('dashboard & loans show real, un-multiplied data', async () => {
  await nav('Dashboard');
  await p.getByText('₹5,000').first().waitFor({ timeout: 8000 });
  await nav('Loans');
  await main().getByText('R. Lakshmi').waitFor();
});
await step('member ledger opens', async () => {
  await main().getByRole('button', { name: 'R. Lakshmi' }).click();
  await main().getByText('#1').first().waitFor();
});
await step('reports, expenses, activity render', async () => {
  await nav('Reports'); await main().getByText('Monthly Report').waitFor();
  await nav('Expenses'); await main().getByText('₹250').first().waitFor();
  await nav('Activity'); await main().getByText('Completed a meeting').waitFor();
});
await step('excel import template download works', async () => {
  await nav('Excel Import');
  const [dl] = await Promise.all([p.waitForEvent('download'), main().getByRole('button', { name: 'Download Template' }).click()]);
  if (!dl.suggestedFilename().endsWith('.xlsx')) throw new Error('bad filename');
});
await step('owner creates supervisor and assigns the group', async () => {
  await nav('Settings');
  await main().getByRole('button', { name: 'Add User' }).click();
  const dlg = p.getByRole('dialog');
  await dlg.getByLabel('Name', { exact: true }).fill('Field Sup');
  await dlg.getByLabel('Email').fill('sup@wrdt.example.org');
  await dlg.getByLabel(/^Password/).fill('SupervisorPass1!');
  await p.getByRole('dialog').getByRole('button', { name: 'Save' }).click();
  await main().getByText('sup@wrdt.example.org').waitFor();
  await main().getByRole('button', { name: 'Assigned Groups' }).click();
  await p.getByRole('dialog').getByText('Lakshmi SHG').click();
  await p.getByText('Assignments updated').waitFor();
  await p.getByRole('dialog').getByRole('button', { name: 'Close' }).last().click();
});
await step('logout clears tokens', async () => {
  await p.getByRole('button', { name: 'Log out' }).click();
  await p.locator('input[type=email]').waitFor();
  const t = await p.evaluate(() => localStorage.getItem('wrdt.access'));
  if (t) throw new Error('token left behind');
});
await step('supervisor sees only permitted nav and assigned group', async () => {
  await p.fill('input[type=email]', 'sup@wrdt.example.org');
  await p.fill('input[type=password]', 'SupervisorPass1!');
  await p.getByRole('button', { name: 'Login' }).click();
  await p.getByRole('heading', { name: 'Dashboard' }).waitFor();
  for (const hidden of ['Regions', 'Excel Import', 'Activity']) {
    if (await p.locator('aside').getByRole('button', { name: hidden, exact: true }).count()) throw new Error(hidden + ' visible to supervisor');
  }
  await nav('Groups');
  await main().getByText('Lakshmi SHG').waitFor();
  await nav('Loans'); await main().getByText('R. Lakshmi').waitFor();
});
await step('session survives a page reload', async () => {
  await p.reload();
  await p.getByRole('heading', { name: 'Dashboard' }).waitFor({ timeout: 8000 });
});

// ---- responsive ----
for (const [label, w, h] of [['desktop', 1440, 900], ['tablet', 820, 1100], ['mobile', 375, 740]]) {
  await step(`responsive ${label}: no horizontal page overflow`, async () => {
    await p.setViewportSize({ width: w, height: h });
    for (const n of ['Dashboard', 'Groups', 'Loans']) {
      if (w <= 900) await p.getByLabel('Open menu').click();
      await nav(n);
      await p.waitForTimeout(400);
      const over = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (over > 1) throw new Error(`${n} overflows by ${over}px`);
    }
    await p.screenshot({ path: `/tmp/e2e/shots/${label}.png` });
  });
}
await step('mobile: sidebar is off-canvas and hamburger opens it', async () => {
  const visible = await p.locator('aside').evaluate(e => e.getBoundingClientRect().right > 0);
  if (visible) throw new Error('sidebar covering content');
  await p.getByLabel('Open menu').click();
  await p.locator('aside').getByRole('button', { name: 'Dashboard', exact: true }).waitFor();
});

await b.close();
for (const r of results) console.log(r[0], '-', r[1]);
console.log('\n5xx responses:', badResponses.length ? badResponses : 'none');
console.log('console errors:', consoleErrors.length ? consoleErrors.slice(0, 8) : 'none');
console.log(results.filter(r => r[0] === 'FAIL').length ? 'RESULT: FAILURES' : 'RESULT: ALL PASSED');
