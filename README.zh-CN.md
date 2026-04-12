# Azure PaaS 故障排除实验室 (Azure App Service Practical Guide)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

从首次部署到生产环境故障排除，在 Azure App Service 上运行 Web 应用程序的全方位指南。

## 主要内容

| 章节 | 描述 |
|---------|-------------|
| [从这里开始 (Start Here)](https://yeongseon.github.io/azure-app-service-practical-guide/) | 概述、学习路径和仓库地图 |
| [平台 (Platform)](https://yeongseon.github.io/azure-app-service-practical-guide/platform/) | 架构、托管模型、网络、扩展 |
| [最佳实践 (Best Practices)](https://yeongseon.github.io/azure-app-service-practical-guide/best-practices/) | 生产基线、安全、网络、部署、扩展、可靠性 |
| [语言指南 (Language Guides)](https://yeongseon.github.io/azure-app-service-practical-guide/language-guides/) | Python、Node.js、Java 和 .NET 的分步教程 |
| [运营 (Operations)](https://yeongseon.github.io/azure-app-service-practical-guide/operations/) | 部署槽、健康检查、安全、成本优化 |
| [故障排除 (Troubleshooting)](https://yeongseon.github.io/azure-app-service-practical-guide/troubleshooting/) | 16 个实战手册、10 个动手实验、KQL 查询包、决策树、证据图 |
| [参考 (Reference)](https://yeongseon.github.io/azure-app-service-practical-guide/reference/) | CLI 速查表、KQL 查询、平台限制、诊断参考 |

## 语言指南

- **Python** (Flask + Gunicorn)
- **Node.js** (Express)
- **Java** (Spring Boot)
- **.NET** (ASP.NET Core)

每个指南都涵盖：本地开发、首次部署、配置、日志记录、基础设施即代码 (IaC)、CI/CD 和自定义域名。

## 快速入门

```bash
# 克隆仓库
git clone https://github.com/yeongseon/azure-app-service-practical-guide.git

# 安装 MkDocs 依赖
pip install mkdocs-material mkdocs-minify-plugin

# 启动本地文档服务器
mkdocs serve
```

访问 `http://127.0.0.1:8000` 在本地浏览文档。

## 参考应用程序

展示 Azure App Service 模式的最小化参考应用程序：

- `apps/python-flask/` — Flask + Gunicorn
- `apps/nodejs/` — Express
- `apps/java-springboot/` — Spring Boot
- `apps/dotnet-aspnetcore/` — ASP.NET Core

## 故障排除实验 (Troubleshooting Labs)

`labs/` 文件夹中包含 10 个动手实验，配有 Bicep 模板，可重现真实的 App Service 问题。每个实验包括：

- 可证伪的假设和分步运行手册
- 真实的 Azure 部署 data (KQL 日志、CLI 输出、诊断端点)
- 预期证据 (Expected Evidence) 章节 (包含证伪逻辑的发生前/发生中/发生后)
- 到相应实战手册的交叉链接

## 贡献

欢迎贡献。请确保：
- 所有 CLI 示例使用长标记 (使用 `--resource-group` 而不是 `-g`)
- 所有文档包含 mermaid 图表
- 所有内容参考 Microsoft Learn 并附带源 URL
- CLI 输出示例中不含个人身份信息 (PII)

## 相关项目

| 仓库 | 描述 |
|---|---|
| [azure-virtual-machine-practical-guide](https://github.com/yeongseon/azure-virtual-machine-practical-guide) | Azure Virtual Machines 实操指南 |
| [azure-networking-practical-guide](https://github.com/yeongseon/azure-networking-practical-guide) | Azure Networking 实操指南 |
| [azure-storage-practical-guide](https://github.com/yeongseon/azure-storage-practical-guide) | Azure Storage 实操指南 |
| [azure-functions-practical-guide](https://github.com/yeongseon/azure-functions-practical-guide) | Azure Functions 实操指南 |
| [azure-container-apps-practical-guide](https://github.com/yeongseon/azure-container-apps-practical-guide) | Azure Container Apps 实操指南 |
| [azure-kubernetes-service-practical-guide](https://github.com/yeongseon/azure-kubernetes-service-practical-guide) | Azure Kubernetes Service (AKS) 实操指南 |
| [azure-monitoring-practical-guide](https://github.com/yeongseon/azure-monitoring-practical-guide) | Azure Monitoring 实操指南 |

## 从旧仓库迁移 (Migration from Legacy Repos)

本仓库整合了之前托管在独立仓库中的实验：

| 旧仓库 | 状态 | 已迁移至 |
|---|---|---|
| [lab-memory-pressure](https://github.com/yeongseon/lab-memory-pressure) | 已归档 | [App Service: Memory Pressure](docs/troubleshooting/lab-guides/memory-pressure.md) |
| [lab-node-memory-pressure](https://github.com/yeongseon/lab-node-memory-pressure) | 已归档 | [App Service: Memory Pressure](docs/troubleshooting/lab-guides/memory-pressure.md) (Node.js 对比) |

### 为什么要整合？

- **可发现性 (Discoverability)**：所有 PaaS 故障排除实验的单一位置
- **相互引用**：服务间的轻松比较（App Service vs Functions vs Container Apps）
- **一致的方法论**：共享的实验模板和证据模型
- **更易于维护**：单一文档站点，统一的 CI/CD

### 旧仓库政策

旧仓库已归档，但仍可供参考。新的实验应添加到此整合仓库中。

## 免责声明 (Disclaimer)

这是一个独立的社区项目。与 Microsoft 无关，也不受其认可。Azure 和 App Service 是 Microsoft Corporation 的商标。

## 许可证

[MIT](LICENSE)
