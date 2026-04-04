const express = require('express');
const router = express.Router();
const { logger } = require('../../config/telemetry');

router.get('/log-levels', (req, res) => {
  const userId = req.query.userId || 'demo-user-123';

  logger.debug('Debug level log - detailed diagnostic info', {
    userId,
    endpoint: '/api/requests/log-levels',
    cacheStatus: 'miss',
    queryParams: req.query,
  });

  logger.info('Info level log - normal operational message', {
    userId,
    action: 'log-levels-demo',
    timestamp: new Date().toISOString(),
  });

  logger.warn('Warn level log - potential issue detected', {
    userId,
    warning: 'Demo warning: userId parameter not provided',
    recommendation: 'Include userId query parameter for tracking',
  });

  logger.error('Error level log - application error', {
    userId,
    error: 'Demo error: simulating error condition',
    errorCode: 'DEMO_ERROR',
    severity: 'high',
  });

  res.json({
    message: 'Log level examples generated',
    note: 'Check Application Logs (az webapp log tail) and Application Insights (AppTraces table)',
    logLevels: {
      debug: 'Verbose (0) - Detailed diagnostic info',
      info: 'Information (1) - Normal operational messages',
      warn: 'Warning (2) - Potential issues',
      error: 'Error (3) - Application errors',
    },
    query: {
      applicationLogs: 'az webapp log tail --name <app-name> --resource-group <rg-name>',
      appInsights: 'AppTraces | where timestamp > ago(5m) | project timestamp, severityLevel, message, customDimensions',
    },
  });
});

router.post('/user-login', (req, res) => {
  const { username, loginMethod } = req.body;

  if (!username) {
    req.logger.warn('Login attempt without username', { ip: req.ip });

    return res.status(400).json({
      error: 'Bad Request',
      message: 'Username is required',
      correlationId: req.correlationId,
    });
  }

  req.logger.info('User login successful', {
    userId: `user-${Date.now()}`,
    username,
    loginMethod: loginMethod || 'password',
    timestamp: new Date().toISOString(),
  });

  res.status(200).json({
    message: 'Login successful',
    userId: `user-${Date.now()}`,
    correlationId: req.correlationId,
  });
});

router.post('/create-order', (req, res) => {
  const { items, totalAmount } = req.body;

  if (!items || !Array.isArray(items) || items.length === 0) {
    req.logger.warn('Order creation failed: no items', { requestBody: req.body });

    return res.status(400).json({
      error: 'Bad Request',
      message: 'Items array is required',
      correlationId: req.correlationId,
    });
  }

  const orderId = `order-${Date.now()}`;

  req.logger.info('Order created', {
    orderId,
    itemCount: items.length,
    totalAmount,
    timestamp: new Date().toISOString(),
  });

  res.status(201).json({
    message: 'Order created successfully',
    orderId,
    itemCount: items.length,
    totalAmount,
    correlationId: req.correlationId,
  });
});

module.exports = router;
