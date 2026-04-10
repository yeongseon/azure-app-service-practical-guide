---
hide:
  - toc
title: Networking
slug: networking
doc_type: concept
section: platform
topics:
  - networking
  - security
  - vnet
products:
  - azure-app-service
prerequisites:
  - how-app-service-works
related:
  - scaling
  - networking-best-practices
summary: Inbound and outbound networking controls - access restrictions, private endpoints, VNet integration.
status: stable
last_reviewed: 2026-04-08
content_sources:
  diagrams:
    - id: networking-model-overview
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/networking-features
      description: "Shows the split between inbound networking features and outbound networking features in multitenant App Service."
    - id: access-restrictions-flow
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/overview-access-restrictions
      description: "Illustrates how front-end access restriction rules allow or deny requests before the app handles them."
    - id: private-endpoint-inbound
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/networking-features
      description: "Shows private endpoint ingress from a client in the virtual network to the App Service app."
    - id: vnet-integration-outbound
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/overview-vnet-integration
      description: "Shows outbound virtual network integration from the app into private dependencies on the delegated subnet path."
    - id: private-inbound-outbound-pattern
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/networking-features
      description: "Combines private endpoint ingress with outbound VNet integration for end-to-end private application patterns."
    - id: private-endpoint-dns-resolution
      type: sequenceDiagram
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/networking-features
      description: "Shows the CNAME-to-private-DNS resolution flow used by App Service private endpoints."
---
# Networking

Azure App Service networking controls define who can reach your application and how your application reaches downstream services. Correct networking design is fundamental for security, compliance, and predictable performance.

## Prerequisites

- Familiarity with virtual networks, subnets, DNS, and private IP ranges
- Understanding of ingress vs egress traffic
- Access to configure App Service networking features

## Main Content

### Networking model overview

<!-- diagram-id: networking-model-overview -->
```mermaid
graph TD
    Internet[Internet Clients] --> Ingress{Inbound Path}
    Ingress --> Public[Public Endpoint + Access Rules]
    Ingress --> Private[Private Endpoint]

    App[App Service App] --> Egress{Outbound Path}
    Egress --> Default[Platform Outbound]
    Egress --> VNet[VNet Integration]
    VNet --> PrivateResources[Private Resources in VNet]
```

### Inbound traffic controls

By default, an app has a public endpoint. You can tighten inbound access using:

- Access restrictions (IP, service tags, priority rules)
- Private endpoint (private ingress over Private Link)
- Authentication/authorization policy at the edge

#### Access restrictions

Access restrictions provide allow/deny controls evaluated before traffic reaches your app process.

<!-- diagram-id: access-restrictions-flow -->
```mermaid
graph LR
    Client[Client] --> FE[App Service Frontend]
    FE --> Rules[Access Restriction Rules]
    Rules -->|Allow| App[Application]
    Rules -->|Deny| Reject[403 Response]
```

Best practices:

- Use explicit allowlist rules
- Keep rule priorities documented
- Apply equivalent restrictions to SCM site where needed

!!! note
    Misconfigured access rules are a common cause of "app is up but unreachable" incidents.

#### Private endpoint for inbound isolation

A private endpoint assigns a private IP for app access within your network boundary.

<!-- diagram-id: private-endpoint-inbound -->
```mermaid
graph LR
    Internet[Public Internet] -- blocked or restricted --> App[App Service]
    subgraph VNet[Virtual Network]
        Client[VNet Client] --> PE[Private Endpoint]
    end
    PE --> App
```

Benefits:

- Reduces internet exposure
- Enables private-only ingress architectures
- Supports strict network segmentation requirements

### Outbound traffic controls

Outbound traffic covers calls from your app to databases, APIs, and service dependencies.

#### VNet integration for outbound connectivity

VNet integration lets app outbound traffic reach private resources.

<!-- diagram-id: vnet-integration-outbound -->
```mermaid
graph LR
    App[App Service App] --> Integration[VNet Integration Subnet]
    Integration --> Database[(Private Database)]
    Integration --> Api[Private API]
    Integration --> Vault[Private Secret Store]
```

Key requirements:

- Dedicated integration subnet
- Proper subnet delegation (`Microsoft.Web/serverFarms`)
- Sufficient subnet address space (minimum sizing guidance applies)

!!! warning "Ingress vs egress"
    VNet integration controls outbound connectivity. It does not make your app privately reachable from clients. Use private endpoint for private inbound access.

### Combining inbound and outbound private patterns

High-security architecture commonly combines:

- Private endpoint for inbound
- VNet integration for outbound
- Private DNS zones for name resolution
- Strict NSG and route governance

<!-- diagram-id: private-inbound-outbound-pattern -->
```mermaid
graph LR
    subgraph VNet[Virtual Network]
        Client[VNet Client] --> PE[Private Endpoint]
        Subnet[Integration Subnet] --> DB[(Private Data Service)]
    end
    PE --> App[App Service]
    App --> Subnet
```

### DNS behavior with private endpoint

Private endpoint access typically relies on a CNAME chain and private DNS zone mapping.

<!-- diagram-id: private-endpoint-dns-resolution -->
```mermaid
sequenceDiagram
    participant Client as VNet Client
    participant DNS as DNS Resolver
    participant Zone as Private DNS Zone
    participant PE as Private Endpoint
    participant App as App Service

    Client->>DNS: Resolve app.azurewebsites.net
    DNS-->>Client: CNAME app.privatelink.azurewebsites.net
    Client->>Zone: Resolve app.privatelink.azurewebsites.net
    Zone-->>Client: A record 10.x.x.x
    Client->>PE: Connect to private IP
    PE->>App: Forward over Azure backbone
```

### Outbound SNAT and connection planning

Outbound connections consume SNAT ports. High churn or poor connection reuse can cause intermittent failures.

Common symptoms:

- Sporadic outbound timeout spikes
- Dependency connection resets under burst load
- Recovery after traffic drop

Mitigations:

- Reuse outbound connections
- Use connection pooling in dependency clients
- Consider NAT Gateway with VNet integration for larger outbound capacity

### Hybrid connectivity

To reach on-premises or cross-network systems:

- VNet integration + VPN/ExpressRoute for full network extension
- Hybrid connections for simpler TCP scenarios

Choose based on latency, throughput, protocol support, and operational ownership.

### CLI examples for networking configuration

Show current network-related app configuration:

```bash
az webapp show \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --query "{defaultHostName:defaultHostName, httpsOnly:httpsOnly, hostNames:hostNames}" \
    --output json
```

Add access restriction rule:

```bash
az webapp config access-restriction add \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --rule-name "allow-corp" \
    --action Allow \
    --ip-address "203.0.113.0/24" \
    --priority 100
```

List access restriction rules:

```bash
az webapp config access-restriction show \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --output table
```

Create private endpoint (conceptual example):

```bash
az network private-endpoint create \
    --resource-group "$RG" \
    --name "$PE_NAME" \
    --vnet-name "$VNET_NAME" \
    --subnet "$SUBNET_NAME" \
    --private-connection-resource-id "$APP_RESOURCE_ID" \
    --group-id "sites" \
    --connection-name "$PE_CONNECTION_NAME"
```

Example output snippet (PII masked):

```json
{
  "customDnsConfigs": [
    {
      "fqdn": "app-<masked>.privatelink.azurewebsites.net",
      "ipAddresses": [
        "10.0.2.4"
      ]
    }
  ],
  "id": "/subscriptions/<subscription-id>/resourceGroups/rg-<masked>/providers/Microsoft.Network/privateEndpoints/pe-<masked>"
}
```

### Troubleshooting matrix

| Symptom | Likely Cause | Validation Path |
|---|---|---|
| Public clients blocked unexpectedly | Restriction rule precedence | Review priorities/actions |
| Private endpoint unreachable | DNS zone/link issue | Verify CNAME/A resolution in VNet |
| App cannot reach private DB | Missing VNet integration route | Validate subnet/delegation/NSG |
| Intermittent outbound timeouts | SNAT exhaustion | Inspect connection reuse + outbound metrics |

## Advanced Topics

### Zero-trust ingress pattern

Use private endpoint + strict access restrictions + identity-aware upstream gateway for layered controls.

### Route-all outbound strategy

In some designs, all outbound flows through controlled network paths for inspection and policy enforcement. Validate latency impact before broad rollout.

### Multi-environment DNS governance

Separate private DNS zones by environment when strict isolation is required, and document naming conventions to prevent resolution drift.

### Networking readiness checklist

- Inbound path explicitly documented (public/private)
- Access restrictions tested from allowed/denied sources
- Private DNS resolution validated in each subnet
- Outbound dependency inventory mapped to route path
- Alerting enabled for connectivity failures

## Language-Specific Details

For language-specific implementation details, see:
- [Node.js Guide](../language-guides/nodejs/index.md)
- [Python Guide](../language-guides/python/index.md)
- [Java Guide](../language-guides/java/index.md)
- [.NET Guide](../language-guides/dotnet/index.md)

## See Also

- [How App Service Works](./how-app-service-works.md)
- [Request Lifecycle](./request-lifecycle.md)
- [Scaling](./scaling.md)
- [Resource Relationships](./resource-relationships.md)
- [App Service networking features (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/networking-features)
- [VNet integration overview (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/overview-vnet-integration)

## Sources

- [App Service networking features (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/networking-features)
- [VNet integration overview (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/overview-vnet-integration)
