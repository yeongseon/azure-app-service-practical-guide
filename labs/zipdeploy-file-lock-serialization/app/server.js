'use strict';

// Synthetic lab application for the ZIP deploy file-lock comparison (Windows, iisnode).
// It does not model a platform fault. The only lock is the one this app creates on
// request, by starting a child PowerShell process that holds an exclusive handle for 120 seconds
// (it releases itself, so a lock cannot outlive one experiment arm).
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

const startedAt = new Date().toISOString();
// Per-run token (app setting). Required for every /lab action that changes or probes state.
const LAB_TOKEN = process.env.LAB_TOKEN || '';
let holder = null;

function authorized(req) {
  return LAB_TOKEN.length > 0 && req.headers['x-lab-token'] === LAB_TOKEN;
}

function readBuild() {
  try {
    return fs.readFileSync(path.join(__dirname, 'build.txt'), 'utf8').split('\n')[0].replace('build=', '').trim();
  } catch (err) {
    return 'unreadable:' + (err.code || 'UNKNOWN');
  }
}

function send(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

function lockProbe() {
  // Opening for write fails (EBUSY/EPERM) while another process holds an exclusive handle.
  const target = path.join(__dirname, 'data', 'lockme.txt');
  let size = null;
  try {
    size = fs.statSync(target).size;
  } catch (err) {
    return { writeOpen: err.code || 'UNKNOWN', size };
  }
  try {
    const fd = fs.openSync(target, 'r+');
    fs.closeSync(fd);
    return { writeOpen: 'ok', size };
  } catch (err) {
    return { writeOpen: err.code || 'UNKNOWN', size };
  }
}

function isAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return false;
  }
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');

  if (url.pathname === '/healthz' || url.pathname === '/lab/state') {
    return send(res, 200, {
      startedAt,
      pid: process.pid,
      build: readBuild(),
      contentRoot: __dirname,
      lockFile: lockProbe(),
      lockHolder: holder ? { pid: holder.pid, file: holder.file, alive: isAlive(holder.pid) } : null
    });
  }

  if (url.pathname === '/lab/ps-test' && req.method === 'POST') {
    // Diagnostic: does PowerShell run here, in which language mode, and can it open the file exclusively?
    if (!authorized(req)) {
      return send(res, 403, { error: 'forbidden' });
    }
    const target = path.join(__dirname, 'data', 'lockme.txt');
    const script = "$ErrorActionPreference='Continue'; 'mode=' + $ExecutionContext.SessionState.LanguageMode; try { $f=[System.IO.File]::Open('" + target.replace(/'/g, "''") + "','Open','Read','None'); 'opened'; $f.Close() } catch { 'open-error=' + $_.Exception.Message }";
    const out = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', script], { timeout: 30000, encoding: 'utf8' });
    return send(res, 200, { status: out.status, signal: out.signal, error: out.error ? out.error.code : null, stdout: out.stdout, stderr: (out.stderr || '').slice(0, 400) });
  }

  if (url.pathname === '/lab/hold-lock' && req.method === 'POST') {
    if (!authorized(req)) {
      return send(res, 403, { error: 'forbidden' });
    }
    const name = url.searchParams.get('file') || 'data/lockme.txt';
    const target = path.normalize(path.join(__dirname, name));
    if (!target.startsWith(__dirname + path.sep)) {
      return send(res, 400, { error: 'invalid file' });
    }
    const script = "$f=[System.IO.File]::Open('" + target.replace(/'/g, "''") + "','Open','Read','None'); Start-Sleep -Seconds 120";
    const child = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', script], {
      detached: true,
      stdio: 'ignore'
    });
    child.on('error', () => {});
    child.unref();
    holder = { pid: child.pid, file: name };
    return setTimeout(() => send(res, 200, { holding: name, pid: child.pid, alive: isAlive(child.pid) }), 3000);
  }

  if (url.pathname === '/lab/release-lock' && req.method === 'POST') {
    if (!authorized(req)) {
      return send(res, 403, { error: 'forbidden' });
    }
    if (holder && isAlive(holder.pid)) {
      try {
        process.kill(holder.pid);
      } catch (err) {
        return send(res, 500, { error: err.code || 'UNKNOWN' });
      }
    }
    const released = holder;
    holder = null;
    return send(res, 200, { released });
  }

  return send(res, 404, { error: 'not found', path: url.pathname });
});

server.listen(process.env.PORT || 8080);
