# Azure Cache for Redis Integration

Connect your Flask application to Azure Cache for Redis for caching and session management.

## Prerequisites

- Azure Cache for Redis instance
- Web App deployed to App Service

## Setup

### 1. Create Redis Cache

```bash
RG="rg-myapp"
REDIS_NAME="redis-myapp"
LOCATION="koreacentral"

az redis create \
    --resource-group $RG \
    --name $REDIS_NAME \
    --location $LOCATION \
    --sku Basic \
    --vm-size c0 \
    --enable-non-ssl-port false
```

### 2. Get Connection Information

```bash
# Get hostname
REDIS_HOST=$(az redis show \
    --resource-group $RG \
    --name $REDIS_NAME \
    --query hostName \
    --output tsv)

# Get primary key
REDIS_KEY=$(az redis list-keys \
    --resource-group $RG \
    --name $REDIS_NAME \
    --query primaryKey \
    --output tsv)

# SSL port is 6380
REDIS_PORT=6380
```

### 3. Configure App Settings

```bash
APP_NAME="app-myapp"

az webapp config appsettings set \
    --resource-group $RG \
    --name $APP_NAME \
    --settings REDIS_HOST=$REDIS_HOST \
               REDIS_PORT=$REDIS_PORT \
               REDIS_PASSWORD=$REDIS_KEY \
               REDIS_SSL=true
```

## Python Code

### Install Dependencies

```bash
pip install redis
```

### Redis Client

```python
import os
import redis

def get_redis_client():
    """Create Redis client with SSL."""
    return redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=int(os.environ.get("REDIS_PORT", 6380)),
        password=os.environ["REDIS_PASSWORD"],
        ssl=os.environ.get("REDIS_SSL", "true").lower() == "true",
        decode_responses=True,
    )

# Caching Operations
def cache_get(key: str) -> str | None:
    client = get_redis_client()
    return client.get(key)

def cache_set(key: str, value: str, ttl_seconds: int = 3600) -> bool:
    client = get_redis_client()
    return client.setex(key, ttl_seconds, value)

def cache_delete(key: str) -> int:
    client = get_redis_client()
    return client.delete(key)

def cache_exists(key: str) -> bool:
    client = get_redis_client()
    return client.exists(key) > 0
```

### Flask Caching Decorator

```python
import json
import functools
from flask import request

def cached(ttl_seconds: int = 300):
    """Cache decorator for Flask routes."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and request
            cache_key = f"{func.__name__}:{request.path}:{request.query_string.decode()}"
            
            # Try to get from cache
            cached_value = cache_get(cache_key)
            if cached_value:
                return json.loads(cached_value)
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_set(cache_key, json.dumps(result), ttl_seconds)
            return result
        return wrapper
    return decorator
```

### Flask Route Example

```python
from flask import Blueprint, jsonify

redis_bp = Blueprint("redis", __name__)

@redis_bp.route("/expensive-query")
@cached(ttl_seconds=600)
def expensive_query():
    # Simulating expensive operation
    import time
    time.sleep(2)
    return {"data": "expensive result", "cached": True}

@redis_bp.route("/cache/<key>", methods=["GET"])
def get_cache(key):
    value = cache_get(key)
    if value is None:
        return jsonify({"error": "Key not found"}), 404
    return jsonify({"key": key, "value": value})

@redis_bp.route("/cache/<key>", methods=["PUT"])
def set_cache(key):
    from flask import request
    data = request.get_json()
    ttl = data.get("ttl", 3600)
    cache_set(key, data["value"], ttl)
    return jsonify({"status": "cached", "key": key, "ttl": ttl})

@redis_bp.route("/cache/<key>", methods=["DELETE"])
def delete_cache(key):
    deleted = cache_delete(key)
    return jsonify({"deleted": deleted})
```

### Flask Session with Redis

```python
from flask import Flask
from flask_session import Session

app = Flask(__name__)

# Configure Flask-Session with Redis
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_REDIS"] = get_redis_client()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_KEY_PREFIX"] = "session:"

Session(app)
```

## Troubleshooting

### Connection Refused

- Ensure SSL is enabled (port 6380, not 6379)
- Check firewall rules or use Private Endpoint
- Verify the hostname is correct

### Authentication Failed

- Double-check the access key
- Ensure the key hasn't been regenerated

### SSL Certificate Error

If you see certificate verification errors:

```python
# For development/testing only
client = redis.Redis(
    ...
    ssl_cert_reqs=None,  # Disable cert verification
)
```

## Advanced: Managed Identity (Preview)

Azure Cache for Redis supports Managed Identity (preview):

```bash
# Enable Entra ID authentication
az redis update \
    --resource-group $RG \
    --name $REDIS_NAME \
    --set redisConfiguration.aad-enabled=true

# Assign role to Web App identity
az role assignment create \
    --role "Redis Cache Contributor" \
    --assignee $PRINCIPAL_ID \
    --scope $(az redis show --resource-group $RG --name $REDIS_NAME --query id --output tsv)
```

## See Also

- [redis-py Documentation](https://redis-py.readthedocs.io/)
- [Azure Cache for Redis](https://learn.microsoft.com/azure/azure-cache-for-redis/)
- [Flask-Session](https://flask-session.readthedocs.io/)
