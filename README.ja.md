# Azure App Service 実務ガイド

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

📘 ドキュメントサイト: <https://yeongseon.github.io/azure-app-service-practical-guide/>

[![Docs](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/docs.yml/badge.svg)](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/docs.yml)
[![CI](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/app-infra-ci.yml/badge.svg)](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/app-infra-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

最初のデプロイから運用環境のトラブルシューティングまで、Azure App Service で Web アプリケーションを実行するための包括的なガイドです。

## 主な内容

| セクション | 説明 | ステータス |
|---------|-------------|--------|
| [ここから開始 (Start Here)](https://yeongseon.github.io/azure-app-service-practical-guide/) | 概要、学習パス、およびリポジトリマップ | Comprehensive |
| [プラットフォーム (Platform)](https://yeongseon.github.io/azure-app-service-practical-guide/platform/) | アーキテクチャ、ホスティングモデル、ネットワーク、スケーリング | Comprehensive |
| [ベストプラクティス (Best Practices)](https://yeongseon.github.io/azure-app-service-practical-guide/best-practices/) | 運用ベースライン、セキュリティ、ネットワーク、デプロイ、スケーリング、信頼性 | Comprehensive |
| [言語別ガイド (Language Guides)](https://yeongseon.github.io/azure-app-service-practical-guide/language-guides/) | Python、Node.js、Java、および .NET のステップバイステップチュートリアル | Comprehensive |
| [運用 (Operations)](https://yeongseon.github.io/azure-app-service-practical-guide/operations/) | デプロイスロット、ヘルスチェック、セキュリティ、コスト最適化 | Comprehensive |
| [トラブルシューティング (Troubleshooting)](https://yeongseon.github.io/azure-app-service-practical-guide/troubleshooting/) | プレイブック、ハンズオンラボ、KQL クエリパック、決定木、エビデンスマップ | Lab-validated |
| [リファレンス (Reference)](https://yeongseon.github.io/azure-app-service-practical-guide/reference/) | CLI チートシート、KQL クエリ、プラットフォームの制限、診断リファレンス | Comprehensive |

**ステータス凡例**: **Lab-validated** = 包括的かつ再現可能なラボによってガイドが実証済み · **Comprehensive** = 完成したセクション、MSLearn 検証済み、運用準備完了 · **Published** = 中核コンテンツ完備、継続的に拡張中 · **In progress** = 部分的なコンテンツ、活発に開発中 · **Planned** = プレースホルダー、コンテンツ未着手

## 言語別ガイド

- **Python** (Flask + Gunicorn)
- **Node.js** (Express)
- **Java** (Spring Boot)
- **.NET** (ASP.NET Core)

各ガイドでは、ローカル開発、最初のデプロイ、構成、ロギング、Infrastructure as Code (IaC)、CI/CD、およびカスタムドメインについて説明します。

## クイックスタート

```bash
git clone https://github.com/yeongseon/azure-app-service-practical-guide.git
cd azure-app-service-practical-guide

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-docs.txt

mkdocs serve
```

ローカルで `http://127.0.0.1:8000` にアクセスしてドキュメントを閲覧してください。

## リファレンスアプリケーション

Azure App Service のパターンを示す最小限のリファレンスアプリケーションです：

- `apps/python-flask/` — Flask + Gunicorn
- `apps/nodejs/` — Express
- `apps/java-springboot/` — Spring Boot
- `apps/dotnet-aspnetcore/` — ASP.NET Core

## トラブルシューティングラボ (Troubleshooting Labs)

`labs/` フォルダには、実際の App Service の問題を再現する Bicep テンプレートを使用した 10 個のハンズオンラボが含まれています。各ラボの構成は以下の通りです：

- 反証可能な仮説とステップバイステップのランブック
- 実際の Azure デプロイデータ (KQL ログ、CLI 出力、診断エンドポイント)
- 予想されるエビデンス (Expected Evidence) セクション (反証ロジックを含む発生前/発生中/発生後)
- 対応するプレイブックへのクロスリンク

## 貢献

貢献を歓迎します！以下の内容については [貢献ガイド](https://yeongseon.github.io/azure-app-service-practical-guide/contributing/) を参照してください：

- リポジトリ構造とコンテンツの構成
- ドキュメントテンプレートと執筆基準
- CLI コマンドスタイルと PII ルール
- ローカル開発環境のセットアップとビルド検証
- プルリクエストのプロセス

## 関連プロジェクト

| リポジトリ | 説明 |
|---|---|
| [azure-virtual-machine-practical-guide](https://github.com/yeongseon/azure-virtual-machine-practical-guide) | Azure Virtual Machines 実務ガイド |
| [azure-networking-practical-guide](https://github.com/yeongseon/azure-networking-practical-guide) | Azure Networking 実務ガイド |
| [azure-storage-practical-guide](https://github.com/yeongseon/azure-storage-practical-guide) | Azure Storage 実務ガイド |
| [azure-app-service-practical-guide](https://github.com/yeongseon/azure-app-service-practical-guide) | Azure App Service 実務ガイド |
| [azure-functions-practical-guide](https://github.com/yeongseon/azure-functions-practical-guide) | Azure Functions 実務ガイド |
| [azure-communication-services-practical-guide](https://github.com/yeongseon/azure-communication-services-practical-guide) | Azure Communication Services 実務ガイド |
| [azure-container-apps-practical-guide](https://github.com/yeongseon/azure-container-apps-practical-guide) | Azure Container Apps 実務ガイド |
| [azure-kubernetes-service-practical-guide](https://github.com/yeongseon/azure-kubernetes-service-practical-guide) | Azure Kubernetes Service (AKS) 実務ガイド |
| [azure-architecture-practical-guide](https://github.com/yeongseon/azure-architecture-practical-guide) | Azure Architecture 実務ガイド |
| [azure-monitoring-practical-guide](https://github.com/yeongseon/azure-monitoring-practical-guide) | Azure Monitoring 実務ガイド |

## 免責事項 (Disclaimer)

これは独立したコミュニティプロジェクトです。Microsoft との提携や承認を受けているものではありません。Azure および App Service は Microsoft Corporation の商標です。

## ライセンス

[MIT](LICENSE)
