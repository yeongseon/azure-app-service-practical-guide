#!/usr/bin/env node
// The only supported way to produce a committed Azure Portal screenshot.
//
// Attaches over CDP to the human's signed-in, device-compliant Chrome, forces
// the conditions in capture-profile.json, refuses to capture if any of them do
// not hold, and verifies the PNG it wrote. See AGENTS.md "Portal Screenshot
// Capture" and scripts/capture/README.md.
//
// Usage:
//   CAPTURE_CDP_URL=http://172.30.96.1:9222 node scripts/capture/capture.cjs \
//     --url 'https://ms.portal.azure.com/#@<tenant>/resource/...' \
//     --ready 'text=Overview' --out /tmp/raw.png
//
// --ready accepts a Playwright selector ("text=...", "css=...", or plain CSS).

'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const { applyPiiReplacements, capturePortalScreenshot } = require('../portal-capture-helpers');

const PROFILE_PATH = path.join(__dirname, 'capture-profile.json');
const PROFILE_BYTES = fs.readFileSync(PROFILE_PATH);
const PROFILE = JSON.parse(PROFILE_BYTES.toString('utf8'));
const PROFILE_SHA256 = crypto.createHash('sha256').update(PROFILE_BYTES).digest('hex');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    if (!key.startsWith('--') || i + 1 >= argv.length) {
      throw new Error(`Unexpected argument ${key}`);
    }
    args[key.slice(2)] = argv[i + 1];
  }
  for (const required of ['url', 'ready', 'out']) {
    if (!args[required]) throw new Error(`--${required} is required`);
  }
  return args;
}

function pngDimensions(file) {
  const buf = fs.readFileSync(file);
  const signature = '89504e470d0a1a0a';
  if (buf.subarray(0, 8).toString('hex') !== signature) {
    throw new Error(`${file} is not a PNG`);
  }
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

async function applyProfile(page, cdp) {
  const { viewport, emulation } = PROFILE;
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: viewport.width,
    height: viewport.height,
    deviceScaleFactor: viewport.deviceScaleFactor,
    mobile: viewport.mobile,
    screenWidth: viewport.width,
    screenHeight: viewport.height,
  });
  // Chrome rejects a second identical locale override; that is the only error
  // tolerated here, and the locale is asserted independently afterwards.
  await cdp.send('Emulation.setLocaleOverride', { locale: emulation.locale }).catch((err) => {
    if (!/already|override/i.test(String(err && err.message))) throw err;
  });
  await cdp.send('Emulation.setTimezoneOverride', { timezoneId: emulation.timezoneId });
  await page.emulateMedia({
    colorScheme: emulation.colorScheme,
    reducedMotion: emulation.reducedMotion,
    forcedColors: emulation.forcedColors,
  });
}

// Returns a list of human-readable violations; empty means the page matches.
async function profileViolations(page) {
  const { viewport, emulation, portal } = PROFILE;
  const violations = [];
  const top = await page.evaluate(() => ({
    w: window.innerWidth,
    h: window.innerHeight,
    dpr: window.devicePixelRatio,
    scale: window.visualViewport ? window.visualViewport.scale : 1,
    lang: document.documentElement.lang || '',
  }));
  if (top.w !== viewport.width || top.h !== viewport.height) {
    violations.push(`viewport is ${top.w}x${top.h}, expected ${viewport.width}x${viewport.height}`);
  }
  if (top.dpr !== viewport.deviceScaleFactor) {
    violations.push(`devicePixelRatio is ${top.dpr}, expected ${viewport.deviceScaleFactor}`);
  }
  if (top.scale !== 1) violations.push(`visual viewport scale is ${top.scale}, expected 1 (browser zoom)`);
  if (!top.lang.toLowerCase().startsWith(portal.languagePrefix)) {
    violations.push(`Portal language is "${top.lang}", expected ${portal.languagePrefix}*`);
  }
  for (const frame of page.frames()) {
    let env;
    try {
      env = await frame.evaluate(() => ({
        light: matchMedia('(prefers-color-scheme: light)').matches,
        reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
        forced: matchMedia('(forced-colors: active)').matches,
        tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
        locale: Intl.DateTimeFormat().resolvedOptions().locale,
        navLang: navigator.language,
      }));
    } catch (_) {
      continue;
    }
    const where = frame === page.mainFrame() ? 'main frame' : `frame ${frame.url().slice(0, 60)}`;
    if (emulation.colorScheme === 'light' && !env.light) violations.push(`${where}: color scheme is not light`);
    if (emulation.reducedMotion === 'reduce' && !env.reduced) violations.push(`${where}: reduced motion not active`);
    if (env.forced) violations.push(`${where}: forced colors (high contrast) is active`);
    if (env.tz !== emulation.timezoneId) violations.push(`${where}: timezone is ${env.tz}, expected ${emulation.timezoneId}`);
    if (env.locale !== emulation.locale || env.navLang !== emulation.locale) {
      violations.push(`${where}: locale is ${env.locale} / navigator ${env.navLang}, expected ${emulation.locale}`);
    }
  }
  const overlaySelector = '[role="dialog"]:visible, [role="alertdialog"]:visible, .fxs-popup:visible, .fxs-toast:visible';
  for (const frame of page.frames()) {
    let open;
    try {
      open = await frame.locator(overlaySelector).count();
    } catch (err) {
      if (frame === page.mainFrame()) throw new Error(`overlay check failed: ${err.message}`);
      continue;
    }
    if (open > 0) violations.push(`${open} dialog/flyout/toast open in ${frame === page.mainFrame() ? 'main frame' : 'a child frame'}`);
  }
  return violations;
}

async function waitForReady(page, ready, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const frame of page.frames()) {
      const visible = await frame.locator(ready).first().isVisible().catch(() => false);
      if (visible) return;
    }
    await page.waitForTimeout(250);
  }
  throw new Error(`ready signal ${JSON.stringify(ready)} did not appear within ${timeoutMs} ms`);
}

async function layoutSample(page, ready) {
  const parts = [];
  for (const frame of page.frames()) {
    const geometry = await frame
      .evaluate(() => {
        const root = document.scrollingElement || document.documentElement;
        return [root.scrollWidth, root.scrollHeight, document.querySelectorAll('*').length];
      })
      .catch(() => null);
    if (geometry) parts.push(geometry);
    const box = await frame.locator(ready).first().boundingBox().catch(() => null);
    if (box) parts.push([Math.round(box.x), Math.round(box.y), Math.round(box.width), Math.round(box.height)]);
  }
  return JSON.stringify(parts);
}

async function waitForStableLayout(page, ready) {
  const { stableSamples, sampleIntervalMs, timeoutMs, fontsReady } = PROFILE.readiness;
  if (fontsReady) {
    for (const frame of page.frames()) {
      await frame.evaluate(() => document.fonts && document.fonts.ready).catch(() => {});
    }
  }
  const deadline = Date.now() + timeoutMs;
  let last = '';
  let streak = 0;
  while (Date.now() < deadline) {
    const sample = await layoutSample(page, ready);
    streak = sample === last ? streak + 1 : 0;
    last = sample;
    if (streak >= stableSamples) return;
    await page.waitForTimeout(sampleIntervalMs);
  }
  throw new Error('layout did not stabilise before the readiness timeout');
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  // A previous run's file must never be mistaken for this run's capture.
  fs.rmSync(args.out, { force: true });
  try {
    await capture(args);
  } catch (err) {
    fs.rmSync(args.out, { force: true });
    throw err;
  }
}

async function capture(args) {
  const endpoint = process.env.CAPTURE_CDP_URL || 'http://127.0.0.1:9222';
  const browser = await chromium.connectOverCDP(endpoint);
  try {
    const page = browser
      .contexts()
      .flatMap((c) => c.pages())
      .find((p) => p.url().includes('portal.azure.com'));
    if (!page) throw new Error('no open tab on portal.azure.com; sign in first');
    const cdp = await page.context().newCDPSession(page);

    await applyProfile(page, cdp);
    await page.goto(args.url, { waitUntil: 'domcontentloaded', timeout: PROFILE.readiness.timeoutMs });
    await applyProfile(page, cdp);
    await waitForReady(page, args.ready, PROFILE.readiness.timeoutMs);
    await waitForStableLayout(page, args.ready);

    const violations = await profileViolations(page);
    if (violations.length) {
      throw new Error(`refusing to capture, ${PROFILE.id} not met:\n  - ${violations.join('\n  - ')}`);
    }

    await applyPiiReplacements(page);
    await page.waitForTimeout(PROFILE.readiness.postPiiSettleMs);
    await applyProfile(page, cdp);
    const finalViolations = await profileViolations(page);
    if (finalViolations.length) {
      throw new Error(`profile drifted before capture:\n  - ${finalViolations.join('\n  - ')}`);
    }
    await capturePortalScreenshot(page, args.out);

    const { width, height } = pngDimensions(args.out);
    const expected = PROFILE.capture;
    if (width !== expected.expectedPixelWidth || height !== expected.expectedPixelHeight) {
      throw new Error(`captured ${width}x${height}, expected ${expected.expectedPixelWidth}x${expected.expectedPixelHeight}`);
    }
    const version = browser.version();
    process.stdout.write(
      `${JSON.stringify({ out: args.out, profile: PROFILE.id, profile_sha256: PROFILE_SHA256, browser: version, width, height })}\n`,
    );
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  main().catch((err) => {
    process.stderr.write(`capture failed: ${err.message}\n`);
    process.exit(1);
  });
}

module.exports = { PROFILE, PROFILE_SHA256, pngDimensions, parseArgs };
