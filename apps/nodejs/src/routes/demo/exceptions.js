const express = require('express');
const router = express.Router();
const { logger } = require('../../config/telemetry');

router.post('/test-error', (req, res, next) => {
  const errorType = req.body.errorType || 'generic';

  logger.warn('Triggering test error', {
    errorType,
    correlationId: req.correlationId,
  });

  const errors = {
    validation: { message: 'Validation failed: Invalid input data', status: 400, code: 'VALIDATION_ERROR' },
    notfound: { message: 'Resource not found', status: 404, code: 'NOT_FOUND' },
    database: { message: 'Database connection failed', status: 500, code: 'DB_CONNECTION_ERROR' },
    timeout: { message: 'Request timeout', status: 504, code: 'TIMEOUT' },
    generic: { message: 'Generic error occurred', status: 500, code: 'GENERIC_ERROR' },
  };

  const errorConfig = errors[errorType] || errors.generic;
  const error = new Error(errorConfig.message);
  error.status = errorConfig.status;
  error.code = errorConfig.code;

  next(error);
});

router.get('/throw-exception', (req, res) => {
  logger.error('About to throw unhandled exception', {
    correlationId: req.correlationId,
  });

  throw new Error('Unhandled exception - this will be caught by Express error handler');
});

router.get('/unhandled-rejection', async (req, res) => {
  logger.error('About to trigger unhandled promise rejection', {
    correlationId: req.correlationId,
  });

  Promise.reject(new Error('Unhandled promise rejection'));

  res.status(500).json({
    message: 'Triggered unhandled promise rejection - check logs',
    correlationId: req.correlationId,
  });
});

router.post('/division-by-zero', (req, res) => {
  const { numerator, denominator } = req.body;

  if (denominator === 0) {
    logger.error('Division by zero attempted', {
      numerator,
      denominator,
      correlationId: req.correlationId,
    });

    return res.status(400).json({
      error: 'Bad Request',
      message: 'Cannot divide by zero',
      correlationId: req.correlationId,
    });
  }

  const result = numerator / denominator;

  logger.info('Division operation successful', {
    numerator,
    denominator,
    result,
    correlationId: req.correlationId,
  });

  res.json({
    result,
    correlationId: req.correlationId,
  });
});

module.exports = router;
