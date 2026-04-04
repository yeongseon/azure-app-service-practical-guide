/**
 * Advanced Telemetry (Operations Path)
 * 
 * Winston + OpenTelemetry integration for production-grade observability.
 * This module must be imported FIRST in your application entry point.
 * 
 * Features:
 *   - Structured JSON logging (Winston)
 *   - Automatic instrumentation (OpenTelemetry → Application Insights)
 *   - Request correlation
 *   - Custom metrics and traces
 * 
 * Prerequisites:
 *   npm install winston @azure/monitor-opentelemetry @opentelemetry/api
 * 
 * Usage:
 *   const { logger } = require('./config/telemetry/advanced');
 *   logger.info('Application started');
 */

const winston = require('winston');
const { useAzureMonitor } = require('@azure/monitor-opentelemetry');

// ============================================================================
// Application Insights (OpenTelemetry) Initialization
// ============================================================================

/**
 * Initialize Application Insights using OpenTelemetry SDK.
 * 
 * Enables automatic instrumentation for:
 *   - HTTP/HTTPS requests (AppRequests table)
 *   - Outgoing dependencies (AppDependencies table)
 *   - Exceptions (AppExceptions table)
 *   - Console logs (AppTraces table)
 * 
 * Requires environment variable:
 *   APPLICATIONINSIGHTS_CONNECTION_STRING
 */

if (!process.env.APPLICATIONINSIGHTS_CONNECTION_STRING) {
  console.warn('⚠️  APPLICATIONINSIGHTS_CONNECTION_STRING not set. Telemetry will not be sent to Application Insights.');
  console.warn('    Logs will still appear in Application Logs (stdout/stderr).');
} else {
  useAzureMonitor({
    azureMonitorExporterOptions: {
      connectionString: process.env.APPLICATIONINSIGHTS_CONNECTION_STRING,
    },

    // Sampling configuration
    // 1.0 = 100% (all telemetry), 0.1 = 10% (sample 10%)
    samplingRatio: parseFloat(process.env.SAMPLING_RATIO || '1.0'),

    // Auto-collect standard telemetry
    enableAutoCollectExceptions: true,
    enableAutoCollectPerformance: true,
    enableAutoCollectExternalLoggers: true, // Winston, Bunyan, etc.
  });

  console.log('✅ Application Insights initialized (OpenTelemetry)');
  console.log(`   Sampling ratio: ${process.env.SAMPLING_RATIO || '1.0'}`);
}

// ============================================================================
// Winston Logger Configuration
// ============================================================================

/**
 * Winston log levels mapped to Application Insights SeverityLevel:
 *   error   → 3 (Error)
 *   warn    → 2 (Warning)
 *   info    → 1 (Information)
 *   http    → 1 (Information)
 *   verbose → 0 (Verbose)
 *   debug   → 0 (Verbose)
 *   silly   → 0 (Verbose)
 * 
 * Configuration via environment variables:
 *   LOG_LEVEL - Minimum log level (default: info)
 *   NODE_ENV  - Set to 'production' for JSON format
 */

const logLevel = process.env.LOG_LEVEL || 'info';
const isProduction = process.env.NODE_ENV === 'production';

// Development format: colorized, human-readable
const devFormat = winston.format.combine(
  winston.format.colorize(),
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.printf(({ timestamp, level, message, ...meta }) => {
    let metaStr = '';
    if (Object.keys(meta).length > 0) {
      metaStr = '\n' + JSON.stringify(meta, null, 2);
    }
    return `${timestamp} [${level}] ${message}${metaStr}`;
  })
);

// Production format: JSON for structured logging
const prodFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.json()
);

const logger = winston.createLogger({
  level: logLevel,
  format: isProduction ? prodFormat : devFormat,

  // Transport: Console (stdout/stderr)
  // Captured by:
  //   1. App Service runtime → /home/LogFiles
  //   2. Application Insights SDK → AppTraces table
  transports: [
    new winston.transports.Console({
      stderrLevels: ['error'], // Errors go to stderr, others to stdout
    }),
  ],

  // Default metadata for all log entries
  defaultMeta: {
    service: 'azure-appservice-reference',
    environment: process.env.NODE_ENV || 'development',
  },
});

// Startup log
logger.info('Advanced telemetry initialized', {
  logLevel,
  isProduction,
  samplingRatio: process.env.SAMPLING_RATIO || '1.0',
  appInsightsEnabled: !!process.env.APPLICATIONINSIGHTS_CONNECTION_STRING,
});

module.exports = { logger };
