import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const candidates = [
  process.env.CHROME_BIN,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  process.env.PROGRAMFILES && `${process.env.PROGRAMFILES}\\Google\\Chrome\\Application\\chrome.exe`,
  process.env['PROGRAMFILES(X86)'] && `${process.env['PROGRAMFILES(X86)']}\\Google\\Chrome\\Application\\chrome.exe`,
  process.env.LOCALAPPDATA && `${process.env.LOCALAPPDATA}\\Google\\Chrome\\Application\\chrome.exe`,
].filter(Boolean);

for (const candidate of candidates) {
  if (existsSync(candidate)) {
    process.stdout.write(candidate);
    process.exit(0);
  }
}

const command = process.platform === 'win32' ? 'where' : 'which';
for (const name of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome']) {
  const result = spawnSync(command, [name], { encoding: 'utf8', windowsHide: true });
  const candidate = result.status === 0 ? result.stdout.trim().split(/\r?\n/)[0] : '';
  if (candidate && existsSync(candidate)) {
    process.stdout.write(candidate);
    process.exit(0);
  }
}

process.stderr.write('Chrome or Chromium was not found. Set CHROME_BIN to its executable path.\n');
process.exit(1);
