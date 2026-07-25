// Manual shell-exploration script (not a test).
//
// Logs in on the target environment and dumps the authenticated app shell so we
// can design real monitoring flows from the actual DOM: the sidenav items, the
// header controls, and — the point of this run — how the sidenav changes when
// the active company is switched in the company selector.
//
// Output goes to stdout (readable in the Actions log) and to exploration/ as
// JSON + screenshots (uploaded as an artifact you can open in the Actions UI).
//
//   TARGET_ENV=dev TEST_USER_USERNAME=... TEST_USER_PASSWORD=... node scripts/explore-shell.mjs
import { chromium } from '@playwright/test';
import config from '../config.js';
import { mkdirSync, writeFileSync } from 'node:fs';

const OUT = 'exploration';
mkdirSync(OUT, { recursive: true });

const USERNAME = process.env.TEST_USER_USERNAME;
const PASSWORD = process.env.TEST_USER_PASSWORD;
const BASE = config.baseURL;

const log = (...a) => console.log(...a);
const save = (name, data) => writeFileSync(`${OUT}/${name}`, data);

if (!USERNAME || !PASSWORD) {
  log('MISSING_CREDENTIALS: set TEST_USER_USERNAME_DEV / TEST_USER_PASSWORD_DEV as');
  log('repo Actions secrets so this exploration can log in. Nothing else to do.');
  process.exit(0);
}

log(`### Exploring ${BASE} as an authenticated user`);

const browser = await chromium.launch();
const context = await browser.newContext({ ignoreHTTPSErrors: true });
const page = await context.newPage();

// ---- capture the shape of the app shell -------------------------------------
async function snapshot(label) {
  const shot = `${label}.png`;
  await page.screenshot({ path: `${OUT}/${shot}`, fullPage: false }).catch(() => {});

  const sidenav = await page
    .$$eval('nav a, [role="navigation"] a, aside a, mat-sidenav a', (els) =>
      [...new Map(
        els
          .filter((e) => (e.innerText || '').trim())
          .map((e) => [
            (e.getAttribute('href') || '') + '|' + e.innerText.trim(),
            { text: e.innerText.trim().replace(/\s+/g, ' '), href: e.getAttribute('href') },
          ])
      ).values()]
    )
    .catch(() => []);

  const headerControls = await page
    .$$eval('header button, [role="toolbar"] button, [role="banner"] button, button[aria-label]', (els) =>
      [...new Set(
        els.map((e) => (e.getAttribute('aria-label') || e.innerText || '').trim().replace(/\s+/g, ' ')).filter(Boolean)
      )].slice(0, 40)
    )
    .catch(() => []);

  const headings = await page
    .$$eval('h1, h2, h3, [role="heading"]', (els) =>
      [...new Set(els.map((e) => e.innerText.trim()).filter(Boolean))].slice(0, 12)
    )
    .catch(() => []);

  const data = { label, url: page.url(), title: await page.title().catch(() => ''), headings, sidenav, headerControls };
  save(`${label}.json`, JSON.stringify(data, null, 2));

  log(`\n===== SHELL [${label}] =====`);
  log(`url      : ${data.url}`);
  log(`title    : ${data.title}`);
  log(`headings : ${JSON.stringify(data.headings)}`);
  log(`sidenav  : (${sidenav.length})`);
  sidenav.forEach((i) => log(`   - ${i.text}  ->  ${i.href ?? ''}`));
  log(`headerControls : ${JSON.stringify(headerControls)}`);
  log(`screenshot -> ${OUT}/${shot}`);
  return data;
}

try {
  // ---- log in ---------------------------------------------------------------
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 30_000 });
  await page.fill('input#username', USERNAME);
  await page.fill('input#password', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 20_000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(1500);
  log('logged in OK');

  const before = await snapshot('01-before');

  // ---- find the company selector -------------------------------------------
  // Heuristic: a header control that is NOT one of the known shell buttons and
  // looks like it names/opens a company/organization/tenant switcher.
  const KNOWN = /^(menu|user menu|language selector|language|show filter menu|notifications?|help|search)$/i;
  const candidates = before.headerControls.filter((c) => !KNOWN.test(c));
  log(`\ncompany-selector candidates (header): ${JSON.stringify(candidates)}`);

  const selectorLocators = [
    'header [role="combobox"]',
    'header [aria-haspopup]',
    'button:has-text("company")',
    '[class*="company"] button, button[class*="company"]',
    '[class*="tenant"], [class*="organization"], [class*="org-"]',
  ];

  let opened = false;
  for (const sel of selectorLocators) {
    const loc = page.locator(sel).first();
    if (await loc.count().then((n) => n > 0).catch(() => false)) {
      log(`trying company-selector locator: ${sel}`);
      await loc.click({ timeout: 4000 }).catch((e) => log(`  click failed: ${e.message.split('\n')[0]}`));
      await page.waitForTimeout(1200);
      const options = await page
        .$$eval('[role="option"], [role="menuitem"], [role="listbox"] li, mat-option, .cdk-overlay-container li', (els) =>
          [...new Set(els.map((e) => e.innerText.trim().replace(/\s+/g, ' ')).filter(Boolean))].slice(0, 40)
        )
        .catch(() => []);
      if (options.length) {
        log(`OPENED via ${sel}. options (${options.length}): ${JSON.stringify(options)}`);
        save('company-options.json', JSON.stringify({ via: sel, options }, null, 2));
        await page.screenshot({ path: `${OUT}/02-selector-open.png` }).catch(() => {});
        opened = true;
        break;
      }
      log(`  no option list appeared for ${sel}`);
    }
  }

  if (!opened) {
    log('\nCould not confidently open the company selector automatically.');
    log('The BEFORE snapshot + screenshot above show the header; we will pin the');
    log('real selector from that. (This is expected on first discovery.)');
  }

  await browser.close();
  log('\n### done');
} catch (err) {
  log(`\nEXPLORATION ERROR: ${err.message.split('\n')[0]}`);
  await page.screenshot({ path: `${OUT}/error.png` }).catch(() => {});
  await browser.close().catch(() => {});
  // Exit 0 so the artifact/log still surface; this is discovery, not a gate.
  process.exit(0);
}
