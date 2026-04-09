---
hide:
  - toc
---

# Checklists

Fast triage guides for the first 10 minutes of an investigation.

These checklists help you quickly narrow down the problem category and identify which playbook to follow for deeper analysis.

```mermaid
graph TD
    A[Initial incident signal] --> B{Choose first-response checklist}
    B --> C[Performance checklist]
    B --> D[Outbound or Network checklist]
    B --> E[Startup or Availability checklist]
    C --> F[Performance playbooks]
    D --> G[Network playbooks]
    E --> H[Startup playbooks]
```

| Checklist | When to Use |
|-----------|-------------|
| [Performance](performance.md) | Slow responses, high latency, elevated error rates |
| [Outbound / Network](outbound-network.md) | Outbound connection failures, DNS issues, SNAT |
| [Startup / Availability](startup-availability.md) | Container won't start, site down, deployment failures |

## See Also

- [Performance Checklist](performance.md)
- [Outbound / Network Checklist](outbound-network.md)
- [Startup / Availability Checklist](startup-availability.md)
