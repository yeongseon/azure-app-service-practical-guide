# Azure PaaS トラブルシューティング ラボ (Azure App Service Practical Guide)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

最初のデプロイから運用環境のトラブルシューティングまで、Azure App Service で Web アプリケーションを実行するための包括的なガイドです。

## 主な内容

| セクション | 説明 |
|---------|-------------|
| [ここから開始 (Start Here)](https://yeongseon.github.io/azure-app-service-practical-guide/) | 概要、学習パス、およびリポジトリマップ |
| [プラットフォーム (Platform)](https://yeongseon.github.io/azure-app-service-practical-guide/platform/) | アーキテクチャ、ホスティングモデル、ネットワーク、スケーリング |
| [ベストプラクティス (Best Practices)](https://yeongseon.github.io/azure-app-service-practical-guide/best-practices/) | 運用ベースライン、セキュリティ、ネットワーク、デプロイ、スケーリング、信頼性 |
| [言語別ガイド (Language Guides)](https://yeongseon.github.io/azure-app-service-practical-guide/language-guides/) | Python、Node.js、Java、および .NET のステップバイステップチュートリアル |
| [運用 (Operations)](https://yeongseon.github.io/azure-app-service-practical-guide/operations/) | デプロイスロット、ヘルスチェック、セキュリティ、コスト最適化 |
| [トラブルシュー팅 (Troubleshooting)](https://yeongseon.github.io/azure-app-service-practical-guide/troubleshooting/) | 16個のプレイブック、10個のハンズオンラボ、KQL クエリパック、決定木、エビデンスマップ |
| [リファレンス (Reference)](https://yeongseon.github.io/azure-app-service-practical-guide/reference/) | CLI チートシート、KQL クエリ、プラットフォームの制限、診断リファレンス |

## 言語別ガイド

- **Python** (Flask + Gunicorn)
- **Node.js** (Express)
- **Java** (Spring Boot)
- **.NET** (ASP.NET Core)

各ガイドでは、ローカル開発、最初のデプロイ、構成、ロギング、Infrastructure as Code (IaC)、CI/CD、およびカスタムドメインについて説明します。

## クイックスタート

```bash
# リポジトリをクローン
git clone https://github.com/yeongseon/azure-app-service-practical-guide.git

# MkDocs の依存関係をインストール
pip install mkdocs-material mkdocs-minify-plugin

# ローカルドキュメントサーバーを起動
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

貢献を歓迎します。以下の点を確認してください：
- すべての CLI の例で長いフラグを使用してください (`-g` ではなく `--resource-group`)
- すべてのドキュメントに Mermaid ダイアグラムを含めてください
- すべてのコンテンツは、ソース URL とともに Microsoft Learn を参照してください
- CLI 出力の例に個人情報 (PII) を含めないでください

## 関連プロジェクト

| リポジトリ | 説明 |
|---|---|
| [azure-virtual-machine-practical-guide](https://github.com/yeongseon/azure-virtual-machine-practical-guide) | Azure Virtual Machines 実務ガイド |
| [azure-networking-practical-guide](https://github.com/yeongseon/azure-networking-practical-guide) | Azure Networking 実務ガイド |
| [azure-storage-practical-guide](https://github.com/yeongseon/azure-storage-practical-guide) | Azure Storage 実務ガイド |
| [azure-functions-practical-guide](https://github.com/yeongseon/azure-functions-practical-guide) | Azure Functions 実務ガイド |
| [azure-container-apps-practical-guide](https://github.com/yeongseon/azure-container-apps-practical-guide) | Azure Container Apps 実務ガイド |
| [azure-kubernetes-service-practical-guide](https://github.com/yeongseon/azure-kubernetes-service-practical-guide) | Azure Kubernetes Service (AKS) 実務ガイド |
| [azure-monitoring-practical-guide](https://github.com/yeongseon/azure-monitoring-practical-guide) | Azure Monitoring 実務ガイド |

## レガシーリポジトリからの移行 (Migration from Legacy Repos)

このリポジトリは、以前は個別のリポジトリでホストされていた実験を統合したものです：

| レガシーリポジトリ | ステータス | 移行先 |
|---|---|---|
| [lab-memory-pressure](https://github.com/yeongseon/lab-memory-pressure) | アーカイブ済み | [App Service: Memory Pressure](docs/troubleshooting/lab-guides/memory-pressure.md) |
| [lab-node-memory-pressure](https://github.com/yeongseon/lab-node-memory-pressure) | アーカイブ済み | [App Service: Memory Pressure](docs/troubleshooting/lab-guides/memory-pressure.md) (Node.js との比較) |

### 統合する理由

- **発見しやすさ (Discoverability)**: すべての PaaS トラブルシューティング実験のための単一の場所
- **相互参照**: サービス間 (App Service vs Functions vs Container Apps) の簡単な比較
- **一貫した方法論**: 共有された実験テンプレートとエビデンスモデル
- **メンテナンスの容易さ**: 単一のドキュメントサイト、統合された CI/CD

### レガシーリポジトリのポリシー

レガシーリポジトリはアーカイブされていますが、参照のために引き続きアクセス可能です。新しい実験は、この統合されたリポジトリに追加する必要があります。

## 免責事項 (Disclaimer)

これは独立したコミュニティプロジェクトです。Microsoft との提携や承認を受けているものではありません。Azure および App Service は Microsoft Corporation の商標です。

## ライセンス

[MIT](LICENSE)
