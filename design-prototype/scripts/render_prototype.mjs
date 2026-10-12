import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const prototype = path.join(root, 'design-prototype', 'index.html');
const output = path.join(root, 'design-prototype', 'rendered', 'screens');
const chromePath = execFileSync(process.execPath, [path.join(path.dirname(fileURLToPath(import.meta.url)), 'chrome_path.mjs')], { encoding: 'utf8' }).trim();
const port = 9333;
const userData = '/tmp/dgn003-render-chrome-profile';
const base = `file://${prototype}`;
const routes = [
  ['signin', 'signin', 1440, 960],
  ['signin-320', 'signin', 320, 780],
  ['signin-forgot', 'signin/forgot', 1280, 900],
  ...['basics','experience','documents','ai'].map((state) => [`onboarding-${state}`, `onboarding/${state}`, 1280, 900]),
  ['home-empty-1440', 'home/empty', 1440, 1000], ['home-returning-1280', 'home/returning', 1280, 900], ['home-empty-390', 'home/empty', 390, 844], ['home-returning-390', 'home/returning', 390, 844],
  ['home-empty-320', 'home/empty', 320, 780],
  ...['summary','documents','providers'].map((state) => [`profile-${state}`, `profile/${state}`, 1280, 900]),
  ...['list','detail','evidence'].map((state) => [`applications-${state}`, `applications/${state}`, 1280, 900]),
  ...['draft','review','handoff','confirm','sent'].map((state) => [`email-${state}`, `email/${state}`, 1280, 900]),
  ...['setup','digest','partial','failure','paused'].map((state) => [`alerts-${state}`, `alerts/${state}`, 1280, 900]),
  ...['inbox','empty','error','revoked'].map((state) => [`notifications-${state}`, `notifications/${state}`, 1280, 900]),
  ...['privacy','export','deletion'].map((state) => [`settings-${state}`, `settings/${state}`, 1280, 900]),
  ...['detected','analyzing','suggestions','manual','filled','review','tracking'].map((state) => [`extension-${state}-360`, `extension/${state}`, 360, 860]),
  ['extension-detected-320', 'extension/detected', 320, 780], ['extension-review-320', 'extension/review', 320, 780],
  ['extension-detected-420', 'extension/detected', 420, 860], ['extension-review-420', 'extension/review', 420, 860],
];

await mkdir(output, { recursive: true });
const chrome = spawn(chromePath, [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--no-default-browser-check', '--no-sandbox',
  `--remote-debugging-port=${port}`, '--remote-allow-origins=*', `--user-data-dir=${userData}`, 'about:blank'
], { stdio: 'ignore' });
let ws;
const errors = [];
try {
  let targets;
  for (let attempt=0; attempt<40; attempt++) {
    try {
      targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      if (targets.length) break;
    } catch {}
    await delay(250);
  }
  const target = targets?.find((item) => item.type === 'page');
  if (!target) throw new Error('Chrome DevTools page target was not available');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject) => { ws.onopen=resolve; ws.onerror=reject; });
  let nextId=0;
  const pending=new Map();
  ws.onmessage=(event) => {
    const message=JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(`runtime exception: ${JSON.stringify(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text)}`);
    if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error') errors.push(`console error: ${message.params.entry.text}`);
    if (message.id && pending.has(message.id)) {
      const {resolve,reject}=pending.get(message.id); pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message)); else resolve(message.result);
    }
  };
  const send=(method,params={}) => new Promise((resolve,reject) => {
    const id=++nextId; pending.set(id,{resolve,reject}); ws.send(JSON.stringify({id,method,params}));
  });
  await send('Page.enable'); await send('Runtime.enable'); await send('Log.enable');
  const results=[];
  for (const [name,route,width,height] of routes) {
    await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
    await send('Page.navigate',{url:`${base}#${route}`});
    await delay(220);
    const evaluated=await send('Runtime.evaluate',{expression:'({heading:document.querySelector("h1")?.textContent || document.title, scrollWidth:document.documentElement.scrollWidth, viewport:window.innerWidth, bodyText:document.body.innerText.length})',returnByValue:true});
    const info=evaluated.result.value;
    const png=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false,fromSurface:true});
    await writeFile(path.join(output,`${name}.png`),Buffer.from(png.data,'base64'));
    const result = {name,route,width,height,...info,horizontalOverflow:info.scrollWidth>info.viewport};
    results.push(result);
    if (result.horizontalOverflow || result.bodyText < 80) errors.push(`${name}: ${result.horizontalOverflow ? 'horizontal overflow' : 'empty render'}`);
  }
  await writeFile(path.join(output,'render-results.json'),JSON.stringify({count:results.length,errors:[...new Set(errors)],screens:results},null,2)+'\n');
  console.log(`Rendered ${results.length} screens; ${new Set(errors).size} unique browser errors.`);
  console.log(results.filter((r)=>r.horizontalOverflow||r.bodyText<80).map((r)=>JSON.stringify(r)).join('\n')||'No empty/overflowing render states detected.');
  if (errors.length) throw new Error(`Prototype render checks failed: ${[...new Set(errors)].join('; ')}`);
} finally {
  ws?.close(); chrome.kill('SIGTERM');
}
