---
content_sources:
  diagrams:
    - id: tutorial-flow
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/
validation:
  az_cli:
    last_tested:
    cli_version:
    result: not_tested
---
# .NET Tutorial

Follow this 7-step path to build, deploy, configure, observe, automate, and secure an ASP.NET Core app on Azure App Service.

## Prerequisites

- .NET 8 SDK
- Azure CLI
- Visual Studio Code or Visual Studio

## Tutorial flow

<!-- diagram-id: tutorial-flow -->
```mermaid
flowchart TD
    A[01 Local Run] --> B[02 First Deploy]
    B --> C[03 Configuration]
    C --> D[04 Logging & Monitoring]
    D --> E[05 Infrastructure as Code]
    E --> F[06 CI/CD]
    F --> G[07 Custom Domain & SSL]
```

## Step map

| Step | Tutorial | Link | Outcome |
|---|---|---|---|
| 01 | Local run | [01-local-run.md](01-local-run.md) | Verify the app runs locally |
| 02 | First deploy | [02-first-deploy.md](02-first-deploy.md) | Publish to App Service |
| 03 | Configuration | [03-configuration.md](03-configuration.md) | Set app settings and runtime config |
| 04 | Logging & monitoring | [04-logging-monitoring.md](04-logging-monitoring.md) | Add diagnostics and telemetry |
| 05 | Infrastructure as Code | [05-infrastructure-as-code.md](05-infrastructure-as-code.md) | Provision with Bicep/Terraform |
| 06 | CI/CD | [06-ci-cd.md](06-ci-cd.md) | Automate builds and deployment |
| 07 | Custom domain & SSL | [07-custom-domain-ssl.md](07-custom-domain-ssl.md) | Secure the app with custom domain and TLS |

## Run It in the Portal

#### Portal view: App Service Web App overview (tutorial destination blade)

![Azure portal Overview blade for `app-test-20251107` (Web App) with a command bar (`Browse`, `Stop`, `Swap`, `Restart`, `Delete`, `Refresh`, `Download publish profile`, `Reset publish profile`, `Share to mobile`, `Send us your feedback`) and an Essentials panel showing Resource group `rg-test-20251107`, Status `Running`, Location `Korea Central`, Subscription `Visual Studio Enterprise Subscription`, Subscription ID `00000000-0000-0000-0000-000000000000`, Default domain `app-test-20251107.azurewebsites.net`, App Service Plan `asp-test-20251107 (P0v3: 1)`, Operating System `Linux`, and Health Check `Not Configured`. The Properties tab is selected (next to Monitoring, Logs, Capabilities, Notifications (1), Recommendations) and surfaces Web app (`Publishing model: Code`, `Runtime Stack: Python - 3.11`, `Runtime status: Healthy`), Domains (`2 Domains View all`), Hosting (`Plan Type: App Service plan`, `Instance Count: 1`, `SKU and size: Premium0V3 (P0v3)` with `Scale up` link), Deployment Center (`Last deployment: Successful on Thursday, November 6, 10:58:01 PM`, `Deployment provider: None`), Application Insights (`Name: ai-test-20251107`, `Region: Korea Central`), and Networking (`Inbound IP addresses: <ip-redacted>, <ipv6-redacted>`, `Private endpoint connections: 0 private endpoints`, `Virtual network integration: Not configured`). Left nav under the search box lists Overview (selected), Activity log, Access control (IAM), Tags, Diagnose and solve problems, Microsoft Defender for Cloud, Events (preview), Log stream, AI (preview), Resource visualizer, with collapsed groups Deployment, Settings, Performance, App Service plan, Development Tools, API, Monitoring, Automation, and Support + troubleshooting.](../../../assets/platform/architecture/01-app-service-overview.png)

The Web App `Overview` blade is the Portal destination this tutorial works toward. This particular screenshot was captured from a Python deployment, so the visible `Operating System: Linux` and `Runtime Stack: Python - 3.11` reflect that deployment; for the ASP.NET Core 8 path in this tutorial the equivalent values read `Windows` and `.NET 8` because the guide uses `--runtime "DOTNETCORE:8.0"` on a Windows App Service plan. The remaining `Essentials` fields — `Status: Running`, `Default domain`, the attached `App Service Plan`, `Plan Type: App Service plan` — and the `Hosting`, `Deployment Center`, `Application Insights`, and `Networking` summaries are the same OS-agnostic surfaces you use to verify each tutorial step.

## See also

- [.NET Guide](../index.md)
- [.NET runtime guide](../dotnet-runtime.md)
- [.NET recipes](../recipes/index.md)

## See Also

- [Guide home](../../../index.md)
- [Start here](../../../start-here/overview.md)

## Sources

- [Azure App Service documentation](https://learn.microsoft.com/en-us/azure/app-service/)
