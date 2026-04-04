# Networking Operations

Secure traffic paths by controlling inbound access, private inbound endpoints, and outbound connectivity to private resources. This guide provides operational patterns for App Service networking in production.

```mermaid
graph TD
    subgraph "External Traffic"
        Client[Client] -- Inbound --> Restrictions[Access Restrictions]
        Client -- Inbound --> PE[Private Endpoint]
    end
    subgraph "App Service Plan"
        App[Application]
    end
    subgraph "Azure Virtual Network"
        Integration[VNet Integration Subnet]
        Resources[Private Resources]
    end
    Restrictions -- Allow --> App
    PE -- Private Link --> App
    App -- Outbound --> Integration
    Integration -- Private Routing --> Resources
```

### Combined Architecture (Private Inbound + Private Outbound)

```mermaid
graph TD
    subgraph Corporate VNet
        subgraph snet-pe["Private Endpoint Subnet"]
            PE[Private Endpoint<br/>10.0.1.5]
        end
        subgraph snet-int["Integration Subnet (min /28)<br/>Microsoft.Web/serverFarms delegation"]
            VI[VNet Integration]
        end
        subgraph snet-backend["Backend Subnet"]
            DB[(Database / Cache)]
            KV[Secrets Store]
        end
        InternalClient[Internal Client]
    end

    subgraph "App Service Platform"
        App[Application]
    end

    subgraph "Private DNS Zones"
        DNS1["privatelink.azurewebsites.net<br/>→ 10.0.1.5"]
        DNS2["Private service zones<br/>→ 10.0.2.4"]
    end

    InternalClient -- "lookup app.azurewebsites.net" --> DNS1
    DNS1 -- "A record 10.0.1.5" --> InternalClient
    InternalClient --> PE
    PE -- "Private Link" --> App
    App -- "outbound" --> VI
    VI --> DB
    VI -- "lookup private dependency" --> DNS2
    VI --> KV
```

## Prerequisites

- Existing Web App and App Service Plan
- Existing VNet and subnets for:
  - private endpoint
  - VNet integration
- Required RBAC permissions for Web, Network, and DNS resources
- Variables set:
  - `RG`
  - `APP_NAME`
  - `VNET_NAME`
  - `INTEGRATION_SUBNET_NAME`
  - `PRIVATE_ENDPOINT_SUBNET_NAME`

## Main Content

### Configure Inbound Access Restrictions

Allow only known source ranges:

```bash
az webapp config access-restriction add \
  --resource-group $RG \
  --name $APP_NAME \
  --rule-name AllowCorp \
  --action Allow \
  --ip-address 203.0.113.0/24 \
  --priority 100 \
  --output json
```

Add explicit deny-all fallback:

```bash
az webapp config access-restriction add \
  --resource-group $RG \
  --name $APP_NAME \
  --rule-name DenyAll \
  --action Deny \
  --ip-address 0.0.0.0/0 \
  --priority 2147483647 \
  --output json
```

Review configured rules:

```bash
az webapp config access-restriction show \
  --resource-group $RG \
  --name $APP_NAME \
  --query "ipSecurityRestrictions[].{name:name,action:action,ip:ipAddress,priority:priority}" \
  --output table
```

### Enable VNet Integration for Outbound Traffic

```bash
az webapp vnet-integration add \
  --resource-group $RG \
  --name $APP_NAME \
  --vnet $VNET_NAME \
  --subnet $INTEGRATION_SUBNET_NAME \
  --output json
```

Route all outbound traffic into VNet path:

```bash
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings WEBSITE_VNET_ROUTE_ALL=1 \
  --output json
```

Inspect integration state:

```bash
az webapp vnet-integration list \
  --resource-group $RG \
  --name $APP_NAME \
  --output table
```

### Create Private Endpoint for Inbound Private Access

```bash
APP_ID=$(az webapp show \
  --resource-group $RG \
  --name $APP_NAME \
  --query id \
  --output tsv)

az network private-endpoint create \
  --resource-group $RG \
  --name "pe-$APP_NAME" \
  --vnet-name $VNET_NAME \
  --subnet $PRIVATE_ENDPOINT_SUBNET_NAME \
  --private-connection-resource-id $APP_ID \
  --group-id sites \
  --connection-name "pec-$APP_NAME" \
  --output json
```

Check private endpoint status:

```bash
az network private-endpoint show \
  --resource-group $RG \
  --name "pe-$APP_NAME" \
  --query "{state:provisioningState,privateIp:customDnsConfigs[0].ipAddresses[0]}" \
  --output json
```

### Configure Private DNS Resolution

Create and link private DNS zone:

```bash
az network private-dns zone create \
  --resource-group $RG \
  --name privatelink.azurewebsites.net \
  --output json

az network private-dns link vnet create \
  --resource-group $RG \
  --zone-name privatelink.azurewebsites.net \
  --name "link-$VNET_NAME" \
  --virtual-network $VNET_NAME \
  --registration-enabled false \
  --output json
```

!!! warning "DNS is often the root cause"
    Private endpoint networking is correct only when hostname resolution returns private IPs from your VNet context.

### Outbound IP and NAT Considerations

App Service outbound IP lists are potential addresses. Validate real egress path when NAT is used.

```bash
az webapp show \
  --resource-group $RG \
  --name $APP_NAME \
  --query "{outbound:outboundIpAddresses,possible:possibleOutboundIpAddresses}" \
  --output json
```

If integration subnet uses NAT Gateway, validate NAT association:

```bash
az network vnet subnet show \
  --resource-group $RG \
  --vnet-name $VNET_NAME \
  --name $INTEGRATION_SUBNET_NAME \
  --query "natGateway.id" \
  --output tsv
```

### Verification Steps

#### Access Restrictions

```bash
curl --silent --output /dev/null --write-out "%{http_code}" \
  "https://$APP_NAME.azurewebsites.net/health"
```

Expected:

- allowed source: `200`
- blocked source: `403`

#### Private Endpoint Name Resolution

From a VM/resource inside linked VNet:

```bash
nslookup "$APP_NAME.azurewebsites.net"
```

Expected: private IP (`10.x.x.x` or similar), not public internet address.

#### Outbound Private Dependency Reachability

From Kudu/SSH diagnostics console:

```bash
nameresolver your-private-resource.contoso.local
tcpping 10.0.2.4 443
```

### Network Debugging Checklist

```mermaid
flowchart TD
    Start["Connectivity Issue"] --> DNS["1. nameresolver/nslookup hostname"]
    DNS -->|"Resolves to public IP\nor NXDOMAIN"| DNSFix["❌ Check Private DNS Zone\nand VNet link"]
    DNS -->|"Resolves to private IP\n(10.x.x.x)"| Ping["2. tcpping private-ip"]
    Ping -->|"Timeout / unreachable"| PingFix["❌ Check NSG rules,\nroute tables, peering"]
    Ping -->|"Reachable"| Port["3. tcpping private-ip:port"]
    Port -->|"Connection refused\nor timeout"| PortFix["❌ Check target service\nfirewall, port config"]
    Port -->|"Port open"| App["4. curl https://endpoint"]
    App -->|"HTTP error\n(401/403/5xx)"| AppFix["❌ Check auth config,\ncertificates, app health"]
    App -->|"200 OK"| Done["✅ Connection working"]
```

Layered checks:

1. DNS resolution
2. IP reachability
3. Port connectivity
4. Application response

### Common Failures and Fixes

| Symptom | Likely Cause | Fix |
|---|---|---|
| `NXDOMAIN` | Private DNS zone not linked | Link VNet to zone |
| Resolves to public IP | Wrong DNS record path | Configure private zone record |
| IP reachable, port closed | Service firewall/ACL | Update target service network rules |
| HTTP 403 | Access restriction or auth policy | Validate allow rules and auth configuration |
| Intermittent egress failures | SNAT/NAT path assumptions | Validate actual egress through NAT design |

## Advanced Topics

### Zero Public Ingress Pattern

Combine these controls:

- Private Endpoint for inbound
- Access restrictions denying public traffic
- Internal DNS resolution only
- VNet-integrated outbound for private dependencies

### Hub-and-Spoke Network Governance

For large environments:

- central firewall and DNS in hub
- workload VNets as spokes
- private DNS zone linking strategy documented and automated

### Change Management for Networking

- stage DNS and NSG changes with validation windows
- keep subnet delegation and address space inventory current
- run synthetic checks after each network change

!!! info "Enterprise Considerations"
    Operational reliability improves when DNS, NSG, and route ownership are explicit across teams. Most App Service networking incidents are cross-team configuration drift issues.

## Language-Specific Details

For language-specific operational guidance, see:
- [Node.js Guide](../language-guides/nodejs/index.md)
- [Python Guide](../language-guides/python/index.md)
- [Java Guide](../language-guides/java/index.md)
- [.NET Guide](../language-guides/dotnet/index.md)

## See Also

- [Operations Index](./index.md)
- [Security](./security.md)
- [Health and Recovery](./health-recovery.md)
- [App Service networking features (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/networking-features)
- [VNet integration (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/overview-vnet-integration)
