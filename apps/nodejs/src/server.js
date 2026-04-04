const { logger } = require('./config/telemetry');
const express = require('express');
const { createCorrelationMiddleware } = require('./middleware/correlation');
const { createHttpLoggerMiddleware } = require('./middleware/httpLogger');

const healthRouter = require('./routes/health');
const infoRouter = require('./routes/info');
const requestsRouter = require('./routes/demo/requests');
const dependenciesRouter = require('./routes/demo/dependencies');
const exceptionsRouter = require('./routes/demo/exceptions');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(createCorrelationMiddleware(logger));
app.use(createHttpLoggerMiddleware(logger));

app.get('/', (req, res) => {
  logger.info('Root endpoint accessed');

  res.send(`
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Azure App Service Reference App</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #f5f5f5;
            color: #333;
        }
        .container {
            background: white;
            border-radius: 8px;
            padding: 40px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 { color: #0078d4; margin-top: 0; }
        h2 {
            color: #333;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 8px;
            margin-top: 32px;
        }
        .endpoint {
            background: #f8f9fa;
            border-left: 4px solid #0078d4;
            padding: 16px;
            margin: 12px 0;
            border-radius: 4px;
        }
        .endpoint-method {
            display: inline-block;
            background: #0078d4;
            color: white;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 12px;
        }
        .endpoint-path { font-family: monospace; color: #333; font-weight: 500; }
        .endpoint-desc { color: #666; margin-top: 8px; font-size: 14px; }
        a { color: #0078d4; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .badge {
            display: inline-block;
            background: #107c10;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 8px;
        }
        code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 13px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Azure App Service Reference App <span class="badge">Running</span></h1>
        <p>Reference implementation for Node.js on Azure App Service.</p>
        <p><strong>Docs:</strong> <a href="https://github.com/yeongseon/azure-appservice-nodejs-guide" target="_blank">GitHub Repository</a></p>

        <h2>Endpoints</h2>

        <div class="endpoint">
            <span class="endpoint-method">GET</span>
            <span class="endpoint-path">/health</span>
            <div class="endpoint-desc">Health check</div>
        </div>

        <div class="endpoint">
            <span class="endpoint-method">GET</span>
            <span class="endpoint-path">/info</span>
            <div class="endpoint-desc">Application info</div>
        </div>

        <div class="endpoint">
            <span class="endpoint-method">GET</span>
            <span class="endpoint-path">/api/requests/log-levels</span>
            <div class="endpoint-desc">Generate logs at all severity levels</div>
        </div>

        <div class="endpoint">
            <span class="endpoint-method">GET</span>
            <span class="endpoint-path">/api/dependencies/external</span>
            <div class="endpoint-desc">External API call demo</div>
        </div>

        <div class="endpoint">
            <span class="endpoint-method">POST</span>
            <span class="endpoint-path">/api/exceptions/test-error</span>
            <div class="endpoint-desc">Error handling demo</div>
        </div>
    </div>
</body>
</html>
  `);
});

app.use('/health', healthRouter);
app.use('/info', infoRouter);
app.use('/api/requests', requestsRouter);
app.use('/api/dependencies', dependenciesRouter);
app.use('/api/exceptions', exceptionsRouter);

app.use((req, res) => {
  logger.warn('Route not found', {
    method: req.method,
    url: req.originalUrl,
    correlationId: req.correlationId,
  });

  res.status(404).json({
    error: 'Not Found',
    message: `Cannot ${req.method} ${req.originalUrl}`,
    correlationId: req.correlationId,
  });
});

app.use((err, req, res, next) => {
  logger.error('Unhandled error', {
    error: err.message,
    stack: err.stack,
    url: req.originalUrl,
    method: req.method,
    correlationId: req.correlationId,
  });

  res.status(err.status || 500).json({
    error: 'Internal Server Error',
    message: process.env.NODE_ENV === 'production' ? 'An error occurred' : err.message,
    correlationId: req.correlationId,
  });
});

app.listen(PORT, () => {
  logger.info('Server started', {
    port: PORT,
    environment: process.env.NODE_ENV || 'development',
    nodeVersion: process.version,
    telemetryMode: process.env.TELEMETRY_MODE || 'basic',
  });
});

process.on('SIGTERM', () => {
  logger.info('SIGTERM signal received: closing HTTP server');
  process.exit(0);
});

process.on('SIGINT', () => {
  logger.info('SIGINT signal received: closing HTTP server');
  process.exit(0);
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Promise Rejection', {
    reason: reason instanceof Error ? reason.message : reason,
    stack: reason instanceof Error ? reason.stack : undefined,
  });
});

module.exports = app;
