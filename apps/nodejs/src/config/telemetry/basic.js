/**
 * Basic Telemetry (Core Path)
 * 
 * Console-only logging for the Core Path tutorial.
 * Logs go to stdout/stderr and are captured by:
 *   - App Service Log Stream
 *   - Application Insights (auto-instrumented via App Service extension)
 * 
 * This is the simplest setup - no external dependencies beyond console.
 * For advanced observability with Winston + OpenTelemetry, see ./advanced.js
 */

const logLevels = {
  error: 0,
  warn: 1,
  info: 2,
  http: 3,
  debug: 4,
};

const currentLevel = logLevels[process.env.LOG_LEVEL] ?? logLevels.info;

/**
 * Format log entry as JSON for structured logging.
 * App Service and Application Insights can parse JSON logs automatically.
 */
function formatLog(level, message, meta = {}) {
  return JSON.stringify({
    timestamp: new Date().toISOString(),
    level,
    message,
    service: 'azure-appservice-reference',
    environment: process.env.NODE_ENV || 'development',
    ...meta,
  });
}

/**
 * Simple logger using console with JSON formatting.
 * 
 * Usage:
 *   const { logger } = require('./config/telemetry/basic');
 *   logger.info('Server started', { port: 3000 });
 */
const logger = {
  error: (message, meta) => {
    if (currentLevel >= logLevels.error) {
      console.error(formatLog('error', message, meta));
    }
  },

  warn: (message, meta) => {
    if (currentLevel >= logLevels.warn) {
      console.warn(formatLog('warn', message, meta));
    }
  },

  info: (message, meta) => {
    if (currentLevel >= logLevels.info) {
      console.log(formatLog('info', message, meta));
    }
  },

  http: (message, meta) => {
    if (currentLevel >= logLevels.http) {
      console.log(formatLog('http', message, meta));
    }
  },

  debug: (message, meta) => {
    if (currentLevel >= logLevels.debug) {
      console.log(formatLog('debug', message, meta));
    }
  },

  /**
   * Create a child logger with bound metadata.
   * Useful for adding correlationId to all logs in a request.
   */
  child: (boundMeta) => ({
    error: (msg, meta) => logger.error(msg, { ...boundMeta, ...meta }),
    warn: (msg, meta) => logger.warn(msg, { ...boundMeta, ...meta }),
    info: (msg, meta) => logger.info(msg, { ...boundMeta, ...meta }),
    http: (msg, meta) => logger.http(msg, { ...boundMeta, ...meta }),
    debug: (msg, meta) => logger.debug(msg, { ...boundMeta, ...meta }),
    child: (moreMeta) => logger.child({ ...boundMeta, ...moreMeta }),
  }),
};

// Startup log
logger.info('Basic telemetry initialized', {
  logLevel: process.env.LOG_LEVEL || 'info',
});

module.exports = { logger };
