# Azure App Service 실무 가이드

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

📘 문서 사이트: <https://yeongseon.github.io/azure-app-service-practical-guide/>

[![Docs](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/docs.yml/badge.svg)](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/docs.yml)
[![CI](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/app-infra-ci.yml/badge.svg)](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/app-infra-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

첫 배포부터 운영 환경의 트러블슈팅까지, Azure App Service에서 웹 애플리케이션을 실행하기 위한 포괄적인 가이드입니다.

## 주요 내용

| 섹션 | 설명 | 상태 |
|---------|-------------|--------|
| [시작하기 (Start Here)](https://yeongseon.github.io/azure-app-service-practical-guide/) | 개요, 학습 경로 및 저장소 맵 | Comprehensive |
| [플랫폼 (Platform)](https://yeongseon.github.io/azure-app-service-practical-guide/platform/) | 아키텍처, 호스팅 모델, 네트워킹, 확장(Scaling) | Comprehensive |
| [베스트 프랙티스 (Best Practices)](https://yeongseon.github.io/azure-app-service-practical-guide/best-practices/) | 운영 기준(Baseline), 보안, 네트워킹, 배포, 확장, 안정성 | Comprehensive |
| [언어별 가이드 (Language Guides)](https://yeongseon.github.io/azure-app-service-practical-guide/language-guides/) | Python, Node.js, Java, .NET을 위한 단계별 튜토리얼 | Comprehensive |
| [운영 (Operations)](https://yeongseon.github.io/azure-app-service-practical-guide/operations/) | 배포 슬롯, 상태 체크(Health checks), 보안, 비용 최적화 | Comprehensive |
| [트러블슈팅 (Troubleshooting)](https://yeongseon.github.io/azure-app-service-practical-guide/troubleshooting/) | 플레이북, 실습 실험(Labs), KQL 쿼리 팩, 의사 결정 트리, 증거 맵(Evidence map) | Lab-validated |
| [참조 (Reference)](https://yeongseon.github.io/azure-app-service-practical-guide/reference/) | CLI 치트시트, KQL 쿼리, 플랫폼 제한 사항, 진단 참조 | Comprehensive |

**상태 범례**: **Lab-validated** = 포괄적이며 재현 가능한 실험으로 가이드가 검증됨 · **Comprehensive** = 완성된 섹션, MSLearn 검증 완료, 운영 준비 완료 · **Published** = 핵심 콘텐츠 완비, 지속 확장 중 · **In progress** = 부분 콘텐츠, 활발히 개발 중 · **Planned** = 자리 표시자, 아직 콘텐츠 미착수

## 언어별 가이드

- **Python** (Flask + Gunicorn)
- **Node.js** (Express)
- **Java** (Spring Boot)
- **.NET** (ASP.NET Core)

각 가이드는 로컬 개발, 첫 배포, 설정, 로깅, 코드형 인프라(IaC), CI/CD, 커스텀 도메인을 다룹니다.

## 빠른 시작

```bash
git clone https://github.com/yeongseon/azure-app-service-practical-guide.git
cd azure-app-service-practical-guide

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-docs.txt

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

- 반증 가능한 가설 및 단계별 런북
- 실제 Azure 배포 데이터 (KQL 로그, CLI 출력, 진단 엔드포인트)
- 예상 증거(Expected Evidence) 섹션 (반증 논리를 포함한 전/중/후 상태)
- 관련 플레이북과의 교차 링크

## 기여하기

기여는 언제나 환영합니다! 다음 내용은 [기여 가이드](https://yeongseon.github.io/azure-app-service-practical-guide/contributing/)를 참고하세요:

- 저장소 구조 및 콘텐츠 구성
- 문서 템플릿 및 작성 표준
- CLI 명령어 스타일 및 PII 규칙
- 로컬 개발 환경 설정 및 빌드 검증
- 풀 리퀘스트 프로세스

## 관련 프로젝트

| 저장소 | 설명 |
|---|---|
| [azure-virtual-machine-practical-guide](https://github.com/yeongseon/azure-virtual-machine-practical-guide) | Azure Virtual Machines 실무 가이드 |
| [azure-networking-practical-guide](https://github.com/yeongseon/azure-networking-practical-guide) | Azure Networking 실무 가이드 |
| [azure-storage-practical-guide](https://github.com/yeongseon/azure-storage-practical-guide) | Azure Storage 실무 가이드 |
| [azure-app-service-practical-guide](https://github.com/yeongseon/azure-app-service-practical-guide) | Azure App Service 실무 가이드 |
| [azure-functions-practical-guide](https://github.com/yeongseon/azure-functions-practical-guide) | Azure Functions 실무 가이드 |
| [azure-communication-services-practical-guide](https://github.com/yeongseon/azure-communication-services-practical-guide) | Azure Communication Services 실무 가이드 |
| [azure-container-apps-practical-guide](https://github.com/yeongseon/azure-container-apps-practical-guide) | Azure Container Apps 실무 가이드 |
| [azure-kubernetes-service-practical-guide](https://github.com/yeongseon/azure-kubernetes-service-practical-guide) | Azure Kubernetes Service (AKS) 실무 가이드 |
| [azure-architecture-practical-guide](https://github.com/yeongseon/azure-architecture-practical-guide) | Azure Architecture 실무 가이드 |
| [azure-monitoring-practical-guide](https://github.com/yeongseon/azure-monitoring-practical-guide) | Azure Monitoring 실무 가이드 |

## 면책 조항 (Disclaimer)

이 프로젝트는 독립적인 커뮤니티 프로젝트입니다. Microsoft와 제휴하거나 보증을 받지 않았습니다. Azure 및 App Service는 Microsoft Corporation의 상표입니다.

## 라이선스

[MIT](LICENSE)
