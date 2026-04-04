# Integration Examples

This directory contains complete integration examples for common Azure services.

## Available Examples

| Example | Description | Authentication |
|---------|-------------|----------------|
| [with-cosmosdb](./with-cosmosdb/) | Cosmos DB NoSQL integration | Managed Identity |
| [with-azure-sql](./with-azure-sql/) | Azure SQL Database integration | Managed Identity |
| [with-redis](./with-redis/) | Azure Cache for Redis | Access Key / Managed Identity |

## Usage

Each example includes:
- `README.md` - Setup instructions and code walkthrough
- Python client code ready to integrate into your Flask app

## Prerequisites

- Azure subscription
- Resource group with Web App (Managed Identity enabled)
- Target Azure service provisioned

## Quick Start

```bash
# 1. Clone this repository
git clone https://github.com/yeongseon/azure-appservice-python-guide.git
cd azure-appservice-python-guide

# 2. Navigate to desired example
cd examples/with-cosmosdb

# 3. Follow the README.md instructions
```
