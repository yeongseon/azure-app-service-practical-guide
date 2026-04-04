/**
 * HTTP Request Logger Middleware
 * 
 * Logs HTTP request completion with timing information.
 * Uses the request-scoped logger (req.logger) if available.
 * 
 * Usage:
 *   const { httpLoggerMiddleware } = require('./middleware/httpLogger');
 *   app.use(httpLoggerMiddleware);
 */

/**
 * Create HTTP logger middleware with the provided fallback logger.
 * 
 * @param {Object} logger - Fallback logger if req.logger is not available
 * @returns {Function} Express middleware function
 */
function createHttpLoggerMiddleware(logger) {
  return function httpLoggerMiddleware(req, res, next) {
    const start = Date.now();

    res.on('finish', () => {
      const duration = Date.now() - start;
      const log = req.logger || logger;

      log.http('HTTP Request', {
        method: req.method,
        url: req.originalUrl,
        statusCode: res.statusCode,
        duration,
        userAgent: req.headers['user-agent'],
      });
    });

    next();
  };
}

module.exports = { createHttpLoggerMiddleware };
