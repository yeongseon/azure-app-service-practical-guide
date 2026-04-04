/**
 * Telemetry Configuration
 * 
 * Selects between basic (console-only) and advanced (Winston + OTel) telemetry
 * based on the TELEMETRY_MODE environment variable.
 * 
 * Environment Variables:
 *   TELEMETRY_MODE - 'basic' or 'advanced' (default: 'basic')
 * 
 * Usage:
 *   const { logger } = require('./config/telemetry');
 */

const mode = process.env.TELEMETRY_MODE || 'basic';

if (mode === 'advanced') {
  module.exports = require('./advanced');
} else {
  module.exports = require('./basic');
}
