'use strict';

// Synthetic lab application. It does NOT model a platform fault.
// The only way a file disappears in this lab is the explicit, instrumented
// POST /lab/remove-asset action that the experimenter calls.
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 8080;
// Per-run token (app setting). Required for every /lab action so only the experimenter can trigger them.
const LAB_TOKEN = process.env.LAB_TOKEN || '';
// The one asset this lab is allowed to remove.
const REMOVABLE_ASSET = '/assets/probe.txt';
const PUBLIC_DIR = path.join(__dirname, 'public');
const startedAt = new Date().toISOString();

function audit(event, fields) {
  // One structured line per lab action; this is the instrumented ground truth.
  console.log('LAB_AUDIT ' + JSON.stringify({ event, at: new Date().toISOString(), ...fields }));
}

function send(res, status, body, type) {
  res.writeHead(status, { 'Content-Type': type || 'application/json' });
  res.end(typeof body === 'string' ? body : JSON.stringify(body));
}

function authorized(req) {
  return LAB_TOKEN.length > 0 && req.headers['x-lab-token'] === LAB_TOKEN;
}

function runIdOf(url) {
  // Non-secret experiment identifier recorded in the audit line.
  const raw = url.searchParams.get('run') || 'unspecified';
  return raw.replace(/[^A-Za-z0-9._-]/g, '').slice(0, 40) || 'unspecified';
}

function resolveAsset(urlPath) {
  const target = path.normalize(path.join(PUBLIC_DIR, urlPath));
  return target.startsWith(PUBLIC_DIR + path.sep) ? target : null;
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');

  if (url.pathname === '/healthz') {
    return send(res, 200, { status: 'ok', startedAt, contentRoot: __dirname });
  }

  if (url.pathname === '/lab/remove-asset' && req.method === 'POST') {
    if (!authorized(req)) {
      return send(res, 403, { error: 'forbidden' });
    }
    const name = url.searchParams.get('name') || '';
    const run = runIdOf(url);
    if (name !== REMOVABLE_ASSET) {
      audit('asset-remove-rejected', { asset: name, run });
      return send(res, 400, { error: 'only ' + REMOVABLE_ASSET + ' can be removed' });
    }
    const target = resolveAsset(name);
    try {
      fs.unlinkSync(target);
      audit('asset-removed', { asset: name, run });
      return send(res, 200, { removed: name, at: new Date().toISOString(), run });
    } catch (err) {
      audit('asset-remove-failed', { asset: name, code: err.code, run });
      return send(res, 500, { error: err.code || 'UNKNOWN', asset: name, run });
    }
  }

  if (url.pathname === '/lab/fs') {
    // Token-protected, read-only summary of the content root. Raw mount data is not returned.
    if (!authorized(req)) {
      return send(res, 403, { error: 'forbidden' });
    }
    const result = { contentRoot: __dirname };
    try {
      const lines = fs.readFileSync('/proc/self/mountinfo', 'utf8').split('\n');
      const entry = lines.find((line) => line.includes(' /home/site/wwwroot '));
      result.wwwrootMount = entry
        ? entry.replace(/^\d+ \d+ [\d:]+ \S+ /, '')
        : 'no separate mount at /home/site/wwwroot';
    } catch (err) {
      result.wwwrootMount = 'unreadable:' + (err.code || 'UNKNOWN');
    }
    const probePath = path.join(__dirname, '.lab-write-test');
    try {
      fs.writeFileSync(probePath, 'x');
      fs.unlinkSync(probePath);
      result.writeTest = 'ok';
    } catch (err) {
      result.writeTest = err.code || 'UNKNOWN';
    }
    for (const [key, dir] of [['home_data', '/home/data'], ['home_data_SitePackages', '/home/data/SitePackages']]) {
      try {
        result[key] = fs.readdirSync(dir);
      } catch (err) {
        result[key] = err.code;
      }
    }
    return send(res, 200, result);
  }

  if (url.pathname === '/lab/state') {
    const name = url.searchParams.get('name') || '';
    const target = resolveAsset(name);
    return send(res, 200, {
      asset: name,
      present: target ? fs.existsSync(target) : false,
      contentRoot: __dirname,
      startedAt
    });
  }

  const target = resolveAsset(url.pathname);
  if (target && fs.existsSync(target) && fs.statSync(target).isFile()) {
    return send(res, 200, fs.readFileSync(target), 'text/plain');
  }
  return send(res, 404, { error: 'not found', path: url.pathname });
});

server.listen(PORT, () => {
  audit('server-started', { port: PORT, contentRoot: __dirname });
});
