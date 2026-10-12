import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const prototype = path.join(root, 'design-prototype', 'index.html');
const chromePath = execFileSync(process.execPath, [path.join(path.dirname(fileURLToPath(import.meta.url)), 'chrome_path.mjs')], { encoding: 'utf8' }).trim();
const port = 9334;
const userData = '/tmp/dgn005-a11y-chrome-profile';
const routes = [
  'signin', 'signin/forgot', 'onboarding/basics', 'onboarding/experience', 'onboarding/documents', 'onboarding/ai',
  'home/empty', 'home/returning', 'profile/summary', 'profile/documents', 'profile/providers',
  'applications/list', 'applications/detail', 'applications/evidence', 'email/draft', 'email/review',
  'email/handoff', 'email/confirm', 'email/sent', 'alerts/setup', 'alerts/digest', 'alerts/partial',
  'alerts/failure', 'alerts/paused', 'notifications/inbox', 'notifications/empty', 'notifications/error',
  'notifications/revoked', 'settings/privacy', 'settings/export', 'settings/deletion',
  'extension/detected', 'extension/analyzing', 'extension/suggestions', 'extension/manual',
  'extension/filled', 'extension/review', 'extension/tracking',
];

const chrome = spawn(chromePath, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--no-sandbox',
  `--remote-debugging-port=${port}`, '--remote-allow-origins=*', `--user-data-dir=${userData}`, 'about:blank',
], { stdio: 'ignore' });
let ws;
try {
  let targets;
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      if (targets.length) break;
    } catch {}
    await delay(250);
  }
  const target = targets?.find((item) => item.type === 'page');
  if (!target) throw new Error('Chrome DevTools page target was not available');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let nextId = 0;
  const pending = new Map();
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id); pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message)); else resolve(message.result);
    }
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++nextId; pending.set(id, { resolve, reject }); ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression) => (await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })).result.value;
  await send('Page.enable'); await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 320, height: 780, deviceScaleFactor: 1, mobile: true });
  const base = `file://${prototype}`;
  await send('Page.navigate', { url: `${base}#signin` });
  await delay(300);
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
  const firstTab = await evaluate('document.activeElement?.classList.contains("skip-link")');
  const initialChecks = await evaluate(`(() => {
    const controls = [...document.querySelectorAll('input,select,textarea')];
    const unlabeled = controls.filter((el) => !(el.labels?.length || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby'))).map((el) => el.outerHTML.slice(0, 100));
    const shortTargets = [...document.querySelectorAll('button,input,select,textarea')].filter((el) => {
      const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.height < 44 || r.width < 24);
    }).map((el) => ({ tag: el.tagName, text: el.innerText || el.getAttribute('aria-label'), width: Math.round(el.getBoundingClientRect().width), height: Math.round(el.getBoundingClientRect().height) }));
    return { unlabeled, shortTargets, focusVisible: getComputedStyle(document.activeElement).outlineStyle !== 'none' };
  })()`);
  const failures = [];
  if (!firstTab) failures.push('The first Tab does not focus the skip link.');
  if (initialChecks.unlabeled.length) failures.push(`Unlabeled form controls: ${JSON.stringify(initialChecks.unlabeled)}`);
  if (!initialChecks.focusVisible) failures.push('The initial keyboard focus has no visible outline.');
  const skipLinkFocus = await evaluate(`(() => {
    const previousHash = location.hash;
    document.querySelector('.skip-link')?.click();
    return location.hash === previousHash && document.activeElement === document.querySelector('main');
  })()`);
  if (!skipLinkFocus) failures.push('Activating the skip link changes routes or does not focus the current main content.');

  const screens = [];
  for (const route of routes) {
    await send('Runtime.evaluate', { expression: `location.hash = ${JSON.stringify(`#${route}`)}` });
    await delay(100);
    const result = await evaluate(`(() => {
      const main = document.querySelectorAll('main');
      const h1 = document.querySelectorAll('main h1');
      const controls = [...document.querySelectorAll('input,select,textarea')];
      const unlabeled = controls.filter((el) => !(el.labels?.length || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby'))).map((el) => ({ tag: el.tagName, markup: el.outerHTML.slice(0, 180) }));
      const unnamedActions = [...document.querySelectorAll('a,button')].filter((el) => !(el.innerText.trim() || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby'))).length;
      const shortTargets = [...document.querySelectorAll('a[href],button,input:not([type="checkbox"]),select,textarea,label.checkline')].filter((el) => {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height) return false;
        if (el.tagName === 'A') {
          const inlineTextLink = getComputedStyle(el).display === 'inline' && el.closest('p,li');
          return !inlineTextLink && (r.height < 24 || r.width < 24);
        }
        return r.height < 44 || (el.tagName !== 'LABEL' && r.width < 24);
      }).map((el) => ({ tag: el.tagName, type: el.type, text: el.innerText || el.getAttribute('aria-label'), width: Math.round(el.getBoundingClientRect().width), height: Math.round(el.getBoundingClientRect().height) }));
      return { route: location.hash.slice(1), mainCount: main.length, headingCount: h1.length, unlabeled, unnamedActions, shortTargets, width: document.documentElement.scrollWidth, viewport: innerWidth };
    })()`);
    screens.push(result);
    if (result.mainCount !== 1 || result.headingCount !== 1 || result.unlabeled.length || result.unnamedActions || result.shortTargets.length || result.width > result.viewport) failures.push(`Accessibility/layout check failed: ${JSON.stringify(result)}`);
  }
  await send('Runtime.evaluate', { expression: 'location.hash = "#home/empty"' });
  await delay(100);
  const routeFocus = await evaluate('document.activeElement === document.querySelector("main h1")');
  if (!routeFocus) failures.push('Route changes do not move focus to the page heading.');
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  const reducedMotion = await evaluate('matchMedia("(prefers-reduced-motion: reduce)").matches && getComputedStyle(document.documentElement).scrollBehavior !== "smooth"');
  if (!reducedMotion) failures.push('Reduced-motion preference is not respected.');
  console.log(JSON.stringify({ routesChecked: screens.length, viewport: 320, firstTabSkipLink: firstTab, skipLinkFocus, routeFocus, reducedMotion, initialChecks, overflowRoutes: screens.filter((item) => item.width > item.viewport).map((item) => item.route), failures }, null, 2));
  if (failures.length) process.exitCode = 1;
} finally {
  ws?.close(); chrome.kill('SIGTERM');
}
