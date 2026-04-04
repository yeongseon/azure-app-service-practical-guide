# Azure SQL Database Integration with Managed Identity

Connect your Flask application to Azure SQL Database using Managed Identity for passwordless authentication.

## Prerequisites

- Azure SQL Server and Database
- Web App with System-assigned Managed Identity enabled
- pyodbc with ODBC Driver 18

## Setup

### 1. Create Azure SQL Server and Database

```bash
RG="rg-myapp"
SQL_SERVER="sql-myapp"
SQL_DB="appdb"
LOCATION="koreacentral"
ADMIN_USER="sqladmin"

az sql server create \
    --resource-group $RG \
    --name $SQL_SERVER \
    --location $LOCATION \
    --enable-ad-only-auth \
    --external-admin-principal-type User \
    --external-admin-name "your-admin@example.com" \
    --external-admin-sid "<object-id>"

az sql db create \
    --resource-group $RG \
    --server $SQL_SERVER \
    --name $SQL_DB \
    --service-objective S0
```

### 2. Add Web App Identity as Database User

Connect to the database using Azure AD authentication and run:

```sql
CREATE USER [app-myapp] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [app-myapp];
ALTER ROLE db_datawriter ADD MEMBER [app-myapp];
```

### 3. Configure App Settings

```bash
APP_NAME="app-myapp"
SQL_FQDN="$SQL_SERVER.database.windows.net"

az webapp config appsettings set \
    --resource-group $RG \
    --name $APP_NAME \
    --settings SQL_SERVER=$SQL_FQDN \
               SQL_DATABASE=$SQL_DB
```

### 4. Allow App Service Access

```bash
# Get outbound IPs
OUTBOUND_IPS=$(az webapp show \
    --resource-group $RG \
    --name $APP_NAME \
    --query outboundIpAddresses \
    --output tsv)

# Add firewall rules (or use Private Endpoint)
for IP in $(echo $OUTBOUND_IPS | tr ',' ' '); do
    az sql server firewall-rule create \
        --resource-group $RG \
        --server $SQL_SERVER \
        --name "AppService-$IP" \
        --start-ip-address $IP \
        --end-ip-address $IP
done
```

## Python Code

### Install Dependencies

```bash
pip install pyodbc azure-identity
```

Note: App Service Linux includes ODBC Driver 18 by default.

### SQL Client with Managed Identity

```python
import os
import struct
import pyodbc
from azure.identity import DefaultAzureCredential

def get_connection():
    """Create SQL connection with Managed Identity token."""
    server = os.environ["SQL_SERVER"]
    database = os.environ["SQL_DATABASE"]
    
    # Get access token for Azure SQL
    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    
    # Encode token for pyodbc
    token_bytes = token.token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    
    connection_string = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
    )
    
    return pyodbc.connect(connection_string, attrs_before={1256: token_struct})

# Database Operations
def execute_query(query: str, params: tuple = None) -> list:
    with get_connection() as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

def execute_command(query: str, params: tuple = None) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        conn.commit()
        return cursor.rowcount
```

### Flask Route Example

```python
from flask import Blueprint, jsonify, request

sql_bp = Blueprint("sql", __name__)

@sql_bp.route("/users", methods=["GET"])
def list_users():
    users = execute_query("SELECT id, name, email FROM users")
    return jsonify(users)

@sql_bp.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    query = "INSERT INTO users (name, email) VALUES (?, ?)"
    execute_command(query, (data["name"], data["email"]))
    return jsonify({"status": "created"}), 201

@sql_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    users = execute_query("SELECT * FROM users WHERE id = ?", (user_id,))
    if not users:
        return jsonify({"error": "Not found"}), 404
    return jsonify(users[0])
```

## Troubleshooting

### Login Failed for User '<token-identified principal>'

The Managed Identity is not added as a database user. Run the SQL command in step 2.

### ODBC Driver Not Found

Ensure you're using the correct driver name:

```python
# Check available drivers
import pyodbc
print(pyodbc.drivers())
```

### Connection Timeout

- Check firewall rules or use Private Endpoint
- Verify the SQL server FQDN is correct

## See Also

- [pyodbc Documentation](https://github.com/mkleehammer/pyodbc)
- [Azure SQL with Managed Identity](https://learn.microsoft.com/azure/azure-sql/database/authentication-azure-ad-user-assigned-managed-identity)
- [Managed Identity Recipe](../../docs/recipes/managed-identity.md)
