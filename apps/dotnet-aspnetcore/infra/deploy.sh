#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail

echo "=============================================="
echo "Azure App Service .NET Guide - Manual Deploy"
echo "=============================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  echo "Loading deployment settings from infra/.env"
  set -a
  source "${SCRIPT_DIR}/.env"
  set +a
fi

RESOURCE_GROUP_NAME="${RESOURCE_GROUP_NAME:-rg-appservice-dotnet-guide}"
LOCATION="${LOCATION:-eastus}"
BASE_NAME="${BASE_NAME:-dotnet-guide}"
APP_SERVICE_PLAN_SKU="${APP_SERVICE_PLAN_SKU:-B1}"
LOG_ANALYTICS_RETENTION_DAYS="${LOG_ANALYTICS_RETENTION_DAYS:-30}"
SAMPLING_PERCENTAGE="${SAMPLING_PERCENTAGE:-100}"

echo "Deployment configuration"
echo "  Resource Group: ${RESOURCE_GROUP_NAME}"
echo "  Location: ${LOCATION}"
echo "  Base Name: ${BASE_NAME}"
echo "  App Service Plan SKU: ${APP_SERVICE_PLAN_SKU}"
echo "  Log Analytics Retention: ${LOG_ANALYTICS_RETENTION_DAYS}"

echo "Step 1/5: Checking Azure CLI login status"
if ! az account show --output none >/dev/null 2>&1; then
  echo "Not logged in. Run: az login"
  exit 1
fi

SUBSCRIPTION_NAME="$(az account show --query name --output tsv)"
echo "Logged in to subscription: ${SUBSCRIPTION_NAME}"

echo "Step 2/5: Ensuring resource group exists"
if az group exists --name "${RESOURCE_GROUP_NAME}" --output tsv | grep --quiet '^true$'; then
  echo "Resource group already exists: ${RESOURCE_GROUP_NAME}"
else
  az group create \
    --name "${RESOURCE_GROUP_NAME}" \
    --location "${LOCATION}" \
    --output none
  echo "Created resource group: ${RESOURCE_GROUP_NAME}"
fi

echo "Step 3/5: Deploying Bicep infrastructure"
DEPLOYMENT_OUTPUT="$(az deployment group create \
  --resource-group "${RESOURCE_GROUP_NAME}" \
  --template-file "${SCRIPT_DIR}/main.bicep" \
  --parameters \
    baseName="${BASE_NAME}" \
    location="${LOCATION}" \
    appServicePlanSku="${APP_SERVICE_PLAN_SKU}" \
    logAnalyticsRetentionDays="${LOG_ANALYTICS_RETENTION_DAYS}" \
    samplingPercentage="${SAMPLING_PERCENTAGE}" \
  --output json)"

WEB_APP_NAME="$(jq --raw-output '.properties.outputs.webAppName.value' <<< "${DEPLOYMENT_OUTPUT}")"
WEB_APP_URL="$(jq --raw-output '.properties.outputs.webAppUrl.value' <<< "${DEPLOYMENT_OUTPUT}")"
APP_INSIGHTS_NAME="$(jq --raw-output '.properties.outputs.appInsightsName.value' <<< "${DEPLOYMENT_OUTPUT}")"
LOG_ANALYTICS_NAME="$(jq --raw-output '.properties.outputs.logAnalyticsWorkspaceName.value' <<< "${DEPLOYMENT_OUTPUT}")"

echo "Infrastructure deployment complete"
echo "  Web App: ${WEB_APP_NAME}"
echo "  URL: ${WEB_APP_URL}"

echo "Step 4/5: Publishing ASP.NET Core app"
APP_PROJECT_DIR="${REPO_ROOT}/app/GuideApi"
PUBLISH_DIR="${APP_PROJECT_DIR}/publish"
ZIP_PATH="${APP_PROJECT_DIR}/guideapi.zip"

rm --recursive --force "${PUBLISH_DIR}" "${ZIP_PATH}"

dotnet restore "${APP_PROJECT_DIR}/GuideApi.csproj"
dotnet publish "${APP_PROJECT_DIR}/GuideApi.csproj" \
  --configuration Release \
  --output "${PUBLISH_DIR}"

echo "Step 5/5: Deploying zip package with az webapp deploy"
(
  cd "${PUBLISH_DIR}"
  zip --recurse-paths --quiet "${ZIP_PATH}" .
)

az webapp deploy \
  --resource-group "${RESOURCE_GROUP_NAME}" \
  --name "${WEB_APP_NAME}" \
  --src-path "${ZIP_PATH}" \
  --type zip \
  --output none

rm --recursive --force "${PUBLISH_DIR}" "${ZIP_PATH}"

echo "=============================================="
echo "Deployment finished"
echo "=============================================="
echo "Resource Group: ${RESOURCE_GROUP_NAME}"
echo "Web App: ${WEB_APP_NAME}"
echo "Application Insights: ${APP_INSIGHTS_NAME}"
echo "Log Analytics: ${LOG_ANALYTICS_NAME}"
echo "Health endpoint: ${WEB_APP_URL}/health"
