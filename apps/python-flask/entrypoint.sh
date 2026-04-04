#!/bin/bash
set -e

# Start SSH daemon for Azure App Service debugging
echo "Starting SSH daemon..."
/usr/sbin/sshd

# Start Gunicorn with the Flask application
echo "Starting Gunicorn..."
exec gunicorn --config gunicorn.conf.py
