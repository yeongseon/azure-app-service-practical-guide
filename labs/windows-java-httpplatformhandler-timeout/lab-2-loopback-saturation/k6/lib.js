// Azure App Service Lab 2 - Windows Java SE + httpPlatformHandler + loopback saturation
// See ../design-proposal.md for arrival-rate rationale and Oracle-approved thresholds.
// See ../README.md (when authored) for the runbook.

// Shared configuration for Lab 2 k6 scenarios.
// Base URL is provided via BASE_URL env var (e.g. https://app-name.azurewebsites.net).
// Endpoint is /slow/240 (Spring Boot backend sleeps 240s then returns).

export const BASE_URL = __ENV.BASE_URL || (() => { throw new Error('BASE_URL env var is required'); })();
export const ENDPOINT = '/slow/240';
export const REQUEST_TIMEOUT = '260s'; // > 240s backend + 20s slack for TCP RST
