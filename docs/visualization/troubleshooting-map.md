---
title: Troubleshooting Map
slug: troubleshooting-map
doc_type: map
section: visualization
topics:
  - troubleshooting
  - navigation
  - diagnostics
products:
  - azure-app-service
related:
  - core-knowledge-graph
  - decision-tree
  - evidence-map
  - mental-model
prerequisites:
  - troubleshooting-architecture-overview
summary: Visual navigation map for troubleshooting workflows, showing connections between playbooks, labs, KQL queries, and evidence patterns.
status: stable
last_reviewed: 2026-04-08
content_sources:
  diagrams:
    - id: visualization-troubleshooting-map-diagram-1
      type: graph
      source: self-generated
      justification: "Self-generated visualization synthesized from official Azure App Service documentation to explain guide structure and relationships."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/overview
        - https://learn.microsoft.com/en-us/azure/app-service/environment/overview
    - id: visualization-troubleshooting-map-diagram-2
      type: graph
      source: self-generated
      justification: "Self-generated visualization synthesized from official Azure App Service documentation to explain guide structure and relationships."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/overview
        - https://learn.microsoft.com/en-us/azure/app-service/environment/overview
    - id: visualization-troubleshooting-map-diagram-3
      type: graph
      source: self-generated
      justification: "Self-generated visualization synthesized from official Azure App Service documentation to explain guide structure and relationships."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/overview
        - https://learn.microsoft.com/en-us/azure/app-service/environment/overview
    - id: visualization-troubleshooting-map-diagram-4
      type: graph
      source: self-generated
      justification: "Self-generated visualization synthesized from official Azure App Service documentation to explain guide structure and relationships."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/overview
        - https://learn.microsoft.com/en-us/azure/app-service/environment/overview
    - id: visualization-troubleshooting-map-diagram-5
      type: graph
      source: self-generated
      justification: "Self-generated visualization synthesized from official Azure App Service documentation to explain guide structure and relationships."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/overview
        - https://learn.microsoft.com/en-us/azure/app-service/environment/overview
---
# Troubleshooting Map

Navigate the troubleshooting documentation visually. This map shows how symptoms lead to playbooks, how playbooks connect to labs and KQL queries, and how evidence patterns validate hypotheses.

<div id="troubleshooting-map-container">
  <div id="ts-controls">
    <input type="text" id="ts-search" placeholder="Search by symptom or topic..." />
    <select id="ts-category">
      <option value="all">All Categories</option>
      <option value="startup">Startup & Availability</option>
      <option value="performance">Performance</option>
      <option value="network">Outbound Network</option>
    </select>
    <select id="ts-type">
      <option value="all">All Types</option>
      <option value="playbook">Playbooks</option>
      <option value="lab">Labs</option>
      <option value="kql">KQL Queries</option>
      <option value="map">Maps & Guides</option>
    </select>
    <button id="ts-reset">Reset View</button>
  </div>
  <div id="troubleshooting-graph" style="width: 100%; height: 700px; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 4px;"></div>
  <div id="ts-info">
    <p><strong>Selected:</strong> <span id="ts-selected-node">None</span></p>
    <p><strong>Category:</strong> <span id="ts-node-category">-</span></p>
    <p><strong>Evidence:</strong> <span id="ts-node-evidence">-</span></p>
  </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
  if (typeof initTroubleshootingMap === 'function') {
    // Resolve path relative to site base using MkDocs Material's __md_scope
    var basePath = typeof __md_scope !== 'undefined' ? __md_scope.href : '/';
    var dataUrl = new URL('assets/graph/troubleshooting-map.json', basePath).href;
    initTroubleshootingMap('troubleshooting-graph', dataUrl);
  }
});
</script>

## Troubleshooting Structure

### Entry Points

Start your troubleshooting journey from these entry points:

<!-- diagram-id: visualization-troubleshooting-map-diagram-1 -->
```mermaid
graph TD
    subgraph Entry Points
        QD[Quick Diagnosis Cards]
        DT[Decision Tree]
        F10[First 10 Minutes]
    end
    
    subgraph Categories
        SA[Startup & Availability]
        PF[Performance]
        ON[Outbound Network]
    end
    
    QD --> SA
    QD --> PF
    QD --> ON
    DT --> SA
    DT --> PF
    DT --> ON
    F10 --> SA
    F10 --> PF
    F10 --> ON
```

### Startup & Availability

<!-- diagram-id: visualization-troubleshooting-map-diagram-2 -->
```mermaid
graph LR
    subgraph Playbooks
        P1[Container HTTP Pings]
        P2[Deployment Succeeded Startup Failed]
        P3[Failed to Forward Request]
        P4[Slot Swap Config Drift]
        P5[Auth Redirect Loop]
    end
    
    subgraph Labs
        L1[Lab: Container HTTP Pings]
        L2[Lab: Deployment Startup]
        L3[Lab: Failed to Forward]
        L4[Lab: Slot Swap Drift]
    end
    
    subgraph KQL
        K1[Startup Errors]
        K2[Container Binding Errors]
        K3[Repeated Startup Attempts]
    end
    
    P1 --> L1
    P1 --> K1
    P1 --> K2
    P2 --> L2
    P2 --> K1
    P3 --> L3
    P3 --> K3
    P4 --> L4
```

### Performance

<!-- diagram-id: visualization-troubleshooting-map-diagram-3 -->
```mermaid
graph LR
    subgraph Playbooks
        P1[Intermittent 5xx Under Load]
        P2[Memory Pressure & Worker Degradation]
        P3[No Space Left on Device]
        P4[Slow Response but Low CPU]
        P5[Slow Start / Cold Start]
    end
    
    subgraph Labs
        L1[Lab: Intermittent 5xx]
        L2[Lab: Memory Pressure]
        L3[Lab: No Space Left]
        L4[Lab: Slow Start]
    end
    
    subgraph KQL
        K1[5xx Trend Over Time]
        K2[Latency vs Errors]
        K3[Restarts vs Latency]
        K4[Slowest Requests by Path]
    end
    
    P1 --> L1
    P1 --> K1
    P1 --> K2
    P2 --> L2
    P2 --> K2
    P2 --> K3
    P3 --> L3
    P4 --> K4
    P5 --> L4
    P5 --> K3
```

### Outbound Network

<!-- diagram-id: visualization-troubleshooting-map-diagram-4 -->
```mermaid
graph LR
    subgraph Playbooks
        P1[DNS Resolution with VNet]
        P2[Private Endpoint DNS Confusion]
        P3[SNAT or Application Issue]
    end
    
    subgraph Labs
        L1[Lab: DNS VNet Resolution]
        L2[Lab: SNAT Exhaustion]
    end
    
    P1 --> L1
    P3 --> L2
```

## Evidence Validation Chain

Each playbook hypothesis is validated through a chain of evidence:

<!-- diagram-id: visualization-troubleshooting-map-diagram-5 -->
```mermaid
graph TD
    subgraph Hypothesis
        H[Memory pressure causes worker degradation]
    end
    
    subgraph Evidence Collection
        E1[KQL: Latency vs Errors]
        E2[KQL: Restarts vs Latency]
        E3[Detector: Memory Analysis]
    end
    
    subgraph Validation
        L[Lab: Memory Pressure]
    end
    
    subgraph Falsification
        F[Restart recovers temporarily but returns]
    end
    
    H --> E1
    H --> E2
    H --> E3
    E1 --> L
    E2 --> L
    E3 --> L
    L --> F
```

## Relationship Types

| Edge Type | Visual | Meaning |
|-----------|--------|---------|
| `validated_by_lab` | Solid green | Playbook hypothesis tested by this lab |
| `investigated_with_kql` | Dashed purple | KQL query used to gather evidence |
| `guided_by_map` | Dotted teal | Methodology document guides investigation |
| `symptom_to_playbook` | Thick orange | Symptom points to likely playbook |
| `prerequisite` | Thin gray | Understanding A helps with B |

## Using the Map

### Symptom-Based Navigation

1. **Identify your symptom** (e.g., "5xx errors under load")
2. **Search** using the search box or start from Quick Diagnosis Cards
3. **Follow edges** to find the relevant playbook
4. **Explore connected nodes** to find:
   - Labs for hands-on verification
   - KQL queries for data collection
   - Related playbooks for similar issues

### Evidence-Based Navigation

1. **Start from the Evidence Map**
2. **Find your available evidence** (logs, metrics, detectors)
3. **Follow edges** to playbooks that use this evidence
4. **Verify** using connected labs

### Category-Based Navigation

Use the category filter to focus on specific problem domains:

- **Startup & Availability**: App won't start, 503 errors, deployment issues
- **Performance**: Slow responses, timeouts, memory/CPU issues
- **Outbound Network**: Connection failures, DNS issues, SNAT exhaustion

## Data Source

The troubleshooting map is generated from document frontmatter by `tools/build_troubleshooting_map.py`. The JSON file is located at:

```
docs/assets/graph/troubleshooting-map.json
```

To regenerate:

```bash
python tools/build_troubleshooting_map.py
```

## Integration with Other Tools

The troubleshooting map connects to other navigation tools:

| Tool | Purpose | Link |
|------|---------|------|
| Quick Diagnosis Cards | Rapid symptom identification | [Quick Diagnosis Cards](../troubleshooting/quick-diagnosis-cards.md) |
| Decision Tree | Step-by-step diagnostic flow | [Decision Tree](../troubleshooting/decision-tree.md) |
| Evidence Map | Evidence-to-playbook mapping | [Evidence Map](../troubleshooting/evidence-map.md) |
| Mental Model | Conceptual framework | [Mental Model](../troubleshooting/mental-model.md) |
