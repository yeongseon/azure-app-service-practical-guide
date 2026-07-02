// Azure App Service Lab 2 - Windows Java SE + httpPlatformHandler + loopback saturation
// See ../design-proposal.md for arrival-rate rationale and Oracle-approved thresholds.
// See ../README.md (when authored) for the runbook.

import http from 'k6/http';
import { BASE_URL, ENDPOINT, REQUEST_TIMEOUT } from './lib.js';

const RATE = parseFloat(__ENV.RATE);
if (isNaN(RATE) || RATE <= 0) {
  throw new Error('RATE env var is required and must be a positive number (req/s)');
}

const DURATION = __ENV.DURATION || '15m';
const MAX_VUS = parseInt(__ENV.MAX_VUS, 10) || 500;
const PREALLOCATED_VUS = parseInt(__ENV.PREALLOCATED_VUS, 10) || 300;

const INTERVAL_MS = Math.round(1000 / RATE);

export const options = {
  scenarios: {
    slow: {
      executor: 'constant-arrival-rate',
      rate: 1,
      timeUnit: `${INTERVAL_MS}ms`,
      duration: DURATION,
      preAllocatedVUs: PREALLOCATED_VUS,
      maxVUs: MAX_VUS,
    },
  },
};

export default function () {
  http.get(BASE_URL + ENDPOINT, { timeout: REQUEST_TIMEOUT });
}

export function handleSummary(data) {
  const summary = {
    metrics: {
      iterations: (data.metrics.iterations || {}).values || {},
      dropped_iterations: (data.metrics.dropped_iterations || {}).values || {},
      http_reqs: (data.metrics.http_reqs || {}).values || {},
      vus_max: (data.metrics.vus_max || {}).values || {},
      http_req_failed: (data.metrics.http_req_failed || {}).values || {},
      http_req_duration: (data.metrics.http_req_duration || {}).values || {},
    },
    root_group: data.root_group || {},
    state: data.state || {},
  };

  const output = JSON.stringify(summary, null, 2);
  return {
    stdout: output,
    'summary.json': output,
  };
}
