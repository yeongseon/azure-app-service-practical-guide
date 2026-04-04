const express = require('express');
const router = express.Router();

router.get('/', (req, res) => {
  res.json({
    name: 'azure-appservice-nodejs-guide',
    version: '1.0.0',
    node: process.version,
    environment: process.env.NODE_ENV || 'development',
    telemetryMode: process.env.TELEMETRY_MODE || 'basic',
  });
});

module.exports = router;
