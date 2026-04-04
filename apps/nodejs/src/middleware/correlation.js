/**
 * Correlation Middleware
 * 
 * Adds correlation ID to all requests for distributed tracing.
 * The correlation ID is propagated through logs and responses.
 * 
 * Headers:
 *   - x-correlation-id: If present, use this value; otherwise generate a new UUID
 *   - x-request-id: Alias for x-correlation-id
 * 
 * Usage:
 *   const { correlationMiddleware } = require('./middleware/correlation');
 *   app.use(correlationMiddleware);
 *   
 *   // In route handlers:
 *   req.correlationId  // The correlation ID for this request
 *   req.logger         // Logger with correlationId bound
 */

const { randomUUID } = require('crypto');

/**
 * Create correlation middleware with the provided logger.
 * 
 * @param {Object} logger - Logger instance with child() method
 * @returns {Function} Express middleware function
 */
function createCorrelationMiddleware(logger) {
  return function correlationMiddleware(req, res, next) {
    // Extract or generate correlation ID
    const correlationId =
      req.headers['x-correlation-id'] ||
      req.headers['x-request-id'] ||
      randomUUID();

    // Attach to request
    req.correlationId = correlationId;

    // Create child logger with correlation ID bound
    req.logger = logger.child({ correlationId });

    // Add to response headers for client visibility
    res.setHeader('x-correlation-id', correlationId);

    next();
  };
}

module.exports = { createCorrelationMiddleware };
