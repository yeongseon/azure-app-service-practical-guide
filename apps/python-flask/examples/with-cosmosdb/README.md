# Cosmos DB Integration with Managed Identity

Connect your Flask application to Azure Cosmos DB using Managed Identity for passwordless authentication.

## Prerequisites

- Azure Cosmos DB account (NoSQL API)
- Web App with System-assigned Managed Identity enabled
- Cosmos DB Data Contributor role assigned to the Web App identity

## Setup

### 1. Create Cosmos DB Account

```bash
RG="rg-myapp"
COSMOS_ACCOUNT="cosmos-myapp"
LOCATION="koreacentral"

az cosmosdb create \
    --resource-group $RG \
    --name $COSMOS_ACCOUNT \
    --kind GlobalDocumentDB \
    --default-consistency-level Session \
    --locations regionName=$LOCATION failoverPriority=0 isZoneRedundant=false
```

### 2. Create Database and Container

```bash
az cosmosdb sql database create \
    --resource-group $RG \
    --account-name $COSMOS_ACCOUNT \
    --name "appdb"

az cosmosdb sql container create \
    --resource-group $RG \
    --account-name $COSMOS_ACCOUNT \
    --database-name "appdb" \
    --name "items" \
    --partition-key-path "/category"
```

### 3. Assign RBAC Role to Web App

```bash
APP_NAME="app-myapp"

# Get Web App's Managed Identity principal ID
PRINCIPAL_ID=$(az webapp identity show \
    --resource-group $RG \
    --name $APP_NAME \
    --query principalId \
    --output tsv)

# Get Cosmos DB account ID
COSMOS_ID=$(az cosmosdb show \
    --resource-group $RG \
    --name $COSMOS_ACCOUNT \
    --query id \
    --output tsv)

# Assign Cosmos DB Data Contributor role
az cosmosdb sql role assignment create \
    --resource-group $RG \
    --account-name $COSMOS_ACCOUNT \
    --role-definition-name "Cosmos DB Built-in Data Contributor" \
    --principal-id $PRINCIPAL_ID \
    --scope $COSMOS_ID
```

### 4. Configure App Settings

```bash
COSMOS_ENDPOINT=$(az cosmosdb show \
    --resource-group $RG \
    --name $COSMOS_ACCOUNT \
    --query documentEndpoint \
    --output tsv)

az webapp config appsettings set \
    --resource-group $RG \
    --name $APP_NAME \
    --settings COSMOS_ENDPOINT=$COSMOS_ENDPOINT \
               COSMOS_DATABASE="appdb" \
               COSMOS_CONTAINER="items"
```

## Python Code

### Install Dependencies

```bash
pip install azure-cosmos azure-identity
```

### Cosmos DB Client

```python
import os
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

def get_cosmos_client():
    """Create Cosmos DB client with Managed Identity."""
    endpoint = os.environ["COSMOS_ENDPOINT"]
    credential = DefaultAzureCredential()
    return CosmosClient(endpoint, credential=credential)

def get_container():
    """Get reference to the items container."""
    client = get_cosmos_client()
    database = client.get_database_client(os.environ["COSMOS_DATABASE"])
    return database.get_container_client(os.environ["COSMOS_CONTAINER"])

# CRUD Operations
def create_item(item: dict) -> dict:
    container = get_container()
    return container.create_item(body=item)

def read_item(item_id: str, partition_key: str) -> dict:
    container = get_container()
    return container.read_item(item=item_id, partition_key=partition_key)

def query_items(category: str) -> list:
    container = get_container()
    query = "SELECT * FROM c WHERE c.category = @category"
    parameters = [{"name": "@category", "value": category}]
    return list(container.query_items(query=query, parameters=parameters))

def delete_item(item_id: str, partition_key: str) -> None:
    container = get_container()
    container.delete_item(item=item_id, partition_key=partition_key)
```

### Flask Route Example

```python
from flask import Blueprint, jsonify, request

cosmos_bp = Blueprint("cosmos", __name__)

@cosmos_bp.route("/items", methods=["POST"])
def create():
    data = request.get_json()
    item = create_item(data)
    return jsonify(item), 201

@cosmos_bp.route("/items/<item_id>", methods=["GET"])
def read(item_id):
    category = request.args.get("category")
    item = read_item(item_id, category)
    return jsonify(item)

@cosmos_bp.route("/items", methods=["GET"])
def list_by_category():
    category = request.args.get("category")
    items = query_items(category)
    return jsonify(items)
```

## Troubleshooting

### 403 Forbidden Error

Ensure the Managed Identity has the correct RBAC role:

```bash
# List role assignments
az cosmosdb sql role assignment list \
    --resource-group $RG \
    --account-name $COSMOS_ACCOUNT \
    --output table
```

### Connection Timeout

Check that the Web App can reach Cosmos DB:
- If using Private Endpoint, ensure VNet integration is configured
- Verify firewall rules allow access from App Service

## See Also

- [Cosmos DB Python SDK](https://learn.microsoft.com/python/api/overview/azure/cosmos-readme)
- [Managed Identity Recipe](../../docs/recipes/managed-identity.md)
