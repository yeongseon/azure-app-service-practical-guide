const express = require('express');
const router = express.Router();
const { logger } = require('../../config/telemetry');

router.get('/external', async (req, res) => {
  const apiUrl = 'https://jsonplaceholder.typicode.com/posts/1';

  logger.debug('Calling external API', {
    url: apiUrl,
    correlationId: req.correlationId,
  });

  const start = Date.now();

  try {
    const response = await fetch(apiUrl);
    const duration = Date.now() - start;
    const data = await response.json();

    logger.info('External API call successful', {
      url: apiUrl,
      statusCode: response.status,
      duration,
      correlationId: req.correlationId,
    });

    res.json({
      message: 'External dependency call successful',
      data,
      metadata: {
        duration,
        statusCode: response.status,
        correlationId: req.correlationId,
      },
    });
  } catch (error) {
    const duration = Date.now() - start;

    logger.error('External API call failed', {
      url: apiUrl,
      error: error.message,
      duration,
      correlationId: req.correlationId,
    });

    res.status(503).json({
      error: 'Service Unavailable',
      message: 'Failed to call external API',
      correlationId: req.correlationId,
    });
  }
});

router.get('/database-query', async (req, res) => {
  const queryName = req.query.query || 'getUserById';

  logger.debug('Simulated database query', {
    queryName,
    correlationId: req.correlationId,
  });

  const start = Date.now();
  await new Promise((resolve) => setTimeout(resolve, Math.random() * 200 + 50));
  const duration = Date.now() - start;

  // Simulate 10% failure rate
  if (Math.random() > 0.9) {
    logger.error('Database query failed', {
      queryName,
      error: 'Connection timeout',
      duration,
      correlationId: req.correlationId,
    });

    return res.status(500).json({
      error: 'Internal Server Error',
      message: 'Database query failed',
      correlationId: req.correlationId,
    });
  }

  logger.info('Database query successful', {
    queryName,
    duration,
    rowsReturned: 1,
    correlationId: req.correlationId,
  });

  res.json({
    message: 'Database query successful',
    queryName,
    metadata: {
      duration,
      rowsReturned: 1,
      correlationId: req.correlationId,
    },
  });
});

module.exports = router;
