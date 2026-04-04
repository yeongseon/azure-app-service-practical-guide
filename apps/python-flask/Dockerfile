# Multi-stage build for Azure App Service with SSH support
# https://learn.microsoft.com/azure/app-service/configure-custom-container

# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies for native packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

# Stage 2: Production image
FROM python:3.11-slim

# App Service SSH requirement
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH for Azure App Service
COPY sshd_config /etc/ssh/
RUN mkdir -p /run/sshd \
    && ssh-keygen -A \
    && echo "root:Docker!" | chpasswd

WORKDIR /app

# Copy wheels from builder and install
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application code
COPY src/ ./src/
COPY gunicorn.conf.py .

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose ports: 8000 for app, 2222 for SSH
EXPOSE 8000 2222

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use entrypoint script to start SSH and Gunicorn
ENTRYPOINT ["/entrypoint.sh"]
