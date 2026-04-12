# Azure PaaS 트러블슈팅 실험실 (Azure App Service Practical Guide)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

첫 배포부터 운영 환경의 트러블슈팅까지, Azure App Service에서 웹 애플리케이션을 실행하기 위한 포괄적인 가이드입니다.

## 주요 내용

| 섹션 | 설명 |
|---------|-------------|
| [시작하기 (Start Here)](https://yeongseon.github.io/azure-app-service-practical-guide/) | 개요, 학습 경로 및 저장소 맵 |
| [플랫폼 (Platform)](https://yeongseon.github.io/azure-app-service-practical-guide/platform/) | 아키텍처, 호스팅 모델, 네트워킹, 확장(Scaling) |
| [베스트 프랙티스 (Best Practices)](https://yeongseon.github.io/azure-app-service-practical-guide/best-practices/) | 운영 기준(Baseline), 보안, 네트워킹, 배포, 확장, 안정성 |
| [언어별 가이드 (Language Guides)](https://yeongseon.github.io/azure-app-service-practical-guide/language-guides/) | Python, Node.js, Java, .NET을 위한 단계별 튜토리얼 |
| [운영 (Operations)](https://yeongseon.github.io/azure-app-service-practical-guide/operations/) | 배포 슬롯, 상태 체크(Health checks), 보안, 비용 최적화 |
| [트러블슈팅 (Troubleshooting)](https://yeongseon.github.io/azure-app-service-practical-guide/troubleshooting/) | 16개의 플레이북, 10개의 실습 실험(Labs), KQL 쿼리 팩, 의사 결정 트리, 증거 맵(Evidence map) |
| [참조 (Reference)](https://yeongseon.github.io/azure-app-service-practical-guide/reference/) | CLI 치트시트, KQL 쿼리, 플랫폼 제한 사항, 진단 참조 |

## 언어별 가이드

- **Python** (Flask + Gunicorn)
- **Node.js** (Express)
- **Java** (Spring Boot)
- **.NET** (ASP.NET Core)

각 가이드는 로컬 개발, 첫 배포, 설정, 로깅, 코드형 인프라(IaC), CI/CD, 커스텀 도메인을 다룹니다.

## 빠른 시작

```bash
# 저장소 복제
git clone https://github.com/yeongseon/azure-app-service-practical-guide.git

# MkDocs 의존성 설치
pip install mkdocs-material mkdocs-minify-plugin

# 로컬 문서 서버 시작
mkdocs serve
```

로컬에서 `http://127.0.0.1:8000`에 접속하여 문서를 확인하세요.

## 참조 애플리케이션

Azure App Service 패턴을 보여주는 최소한의 참조 애플리케이션들입니다:

- `apps/python-flask/` — Flask + Gunicorn
- `apps/nodejs/` — Express
- `apps/java-springboot/` — Spring Boot
- `apps/dotnet-aspnetcore/` — ASP.NET Core

## 트러블슈팅 실험 (Troubleshooting Labs)

`labs/` 폴더에는 실제 App Service 이슈를 재현하는 Bicep 템플릿과 함께 10개의 실습 실험이 포함되어 있습니다. 각 실험의 구성은 다음과 같습니다:

- 가설 검증 및 단계별 런북
- 실제 Azure 배포 데이터 (KQL 로그, CLI 출력, 진단 엔드포인트)
- 예상 증거(Expected Evidence) 섹션 (반증 논리를 포함한 전/중/후 상태)
- 관련 플레이북과의 교차 링크

## 기여하기

기여는 언제나 환영합니다. 다음 사항을 준수해 주세요:
- 모든 CLI 예제에는 긴 플래그를 사용하세요 (`-g` 대신 `--resource-group`)
- 모든 문서에는 Mermaid 다이어그램을 포함하세요
- 모든 콘텐츠는 출처 URL과 함께 Microsoft Learn을 참조해야 합니다
- CLI 출력 예제에 개인 식별 정보(PII)를 포함하지 마세요

## 관련 프로젝트

| 저장소 | 설명 |
|---|---|
| [azure-virtual-machine-practical-guide](https://github.com/yeongseon/azure-virtual-machine-practical-guide) | Azure Virtual Machines 실무 가이드 |
| [azure-networking-practical-guide](https://github.com/yeongseon/azure-networking-practical-guide) | Azure Networking 실무 가이드 |
| [azure-storage-practical-guide](https://github.com/yeongseon/azure-storage-practical-guide) | Azure Storage 실무 가이드 |
| [azure-functions-practical-guide](https://github.com/yeongseon/azure-functions-practical-guide) | Azure Functions 실무 가이드 |
| [azure-container-apps-practical-guide](https://github.com/yeongseon/azure-container-apps-practical-guide) | Azure Container Apps 실무 가이드 |
| [azure-kubernetes-service-practical-guide](https://github.com/yeongseon/azure-kubernetes-service-practical-guide) | Azure Kubernetes Service (AKS) 실무 가이드 |
| [azure-monitoring-practical-guide](https://github.com/yeongseon/azure-monitoring-practical-guide) | Azure Monitoring 실무 가이드 |

## 기존 저장소로부터의 마이그레이션 (Migration from Legacy Repos)

이 저장소는 이전에 개별 저장소에서 호스팅되던 실험들을 통합합니다:

| 기존 저장소 | 상태 | 마이그레이션 대상 |
|---|---|---|
| [lab-memory-pressure](https://github.com/yeongseon/lab-memory-pressure) | 보관됨(Archived) | [App Service: Memory Pressure](docs/troubleshooting/lab-guides/memory-pressure.md) |
| [lab-node-memory-pressure](https://github.com/yeongseon/lab-node-memory-pressure) | 보관됨(Archived) | [App Service: Memory Pressure](docs/troubleshooting/lab-guides/memory-pressure.md) (Node.js 비교) |

### 통합 이유

- **발견 가능성(Discoverability)**: 모든 PaaS 트러블슈팅 실험을 위한 단일 위치
- **교차 참조**: 서비스 간 쉬운 비교 (App Service vs Functions vs Container Apps)
- **일관된 방법론**: 공유된 실험 템플릿 및 증거 모델
- **쉬운 유지 관리**: 단일 문서 사이트, 통합된 CI/CD

### 기존 저장소 정책

기존 저장소는 보관되지만 참조를 위해 계속 접근 가능합니다. 새로운 실험은 이 통합된 저장소에 추가되어야 합니다.

## 면책 조항 (Disclaimer)

이 프로젝트는 독립적인 커뮤니티 프로젝트입니다. Microsoft와 제휴하거나 보증을 받지 않았습니다. Azure 및 App Service는 Microsoft Corporation의 상표입니다.

## 라이선스

[MIT](LICENSE)
