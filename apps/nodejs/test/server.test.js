const assert = require('node:assert/strict');
const http = require('node:http');
const test = require('node:test');

const { app } = require('../src/server');

let server;
let baseUrl;

test.before(async () => {
  server = http.createServer(app);
  await new Promise((resolve) => {
    server.listen(0, '127.0.0.1', resolve);
  });
  const { port } = server.address();
  baseUrl = `http://127.0.0.1:${port}`;
});

test.after(async () => {
  await new Promise((resolve, reject) => {
    server.close((error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
});

test('GET /health returns healthy status', async () => {
  const response = await fetch(`${baseUrl}/health`);
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.equal(body.status, 'healthy');
  assert.match(body.timestamp, /^\d{4}-\d{2}-\d{2}T/);
});

test('GET /info returns app metadata', async () => {
  const response = await fetch(`${baseUrl}/info`);
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.equal(body.name, 'azure-appservice-nodejs-guide');
  assert.equal(body.version, '1.0.0');
  assert.equal(body.telemetryMode, process.env.TELEMETRY_MODE || 'basic');
});

test('unknown route returns JSON 404 with correlation ID', async () => {
  const response = await fetch(`${baseUrl}/does-not-exist`, {
    headers: {
      'x-correlation-id': 'test-correlation-id',
    },
  });
  const body = await response.json();

  assert.equal(response.status, 404);
  assert.equal(body.error, 'Not Found');
  assert.equal(body.correlationId, 'test-correlation-id');
  assert.equal(response.headers.get('x-correlation-id'), 'test-correlation-id');
});
