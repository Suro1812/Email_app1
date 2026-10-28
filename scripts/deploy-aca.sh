#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Build a versioned Docker image, push it to Azure Container Registry, and deploy
Azure Container Apps with the ARM template in infra/aca/azuredeploy.json.

Required values can be passed as flags or environment variables:
  --version VERSION              Image/application version, for example 0.1.1
  --resource-group NAME          Azure resource group, or AZURE_RESOURCE_GROUP
  --acr-name NAME                Azure Container Registry name, or ACR_NAME
  --aca-env-name NAME            Container Apps environment name, or ACA_ENV_NAME
  --api-app-name NAME            API Container App name, or ACA_API_APP_NAME

Optional:
  --location NAME                Azure location, or AZURE_LOCATION (default: eastus)
  --image-name NAME              Repository name in ACR (default: email-reminders)
  --worker-app-name NAME         Deploy/update a worker Container App too
  --identity-name NAME           User-assigned identity for ACR pull
  --platform PLATFORM            Docker build platform (default: linux/amd64)
  --env-vars "KEY=VALUE ..."     Extra ACA env vars, or ACA_ENV_VARS
  --template-file PATH           ARM template path
  --no-latest                    Do not push the latest tag
  --help                         Show this help

Versioning:
  The version is used as the immutable Docker tag and ACA revision suffix.
  Example image tag: myregistry.azurecr.io/email-reminders:0.1.1
  The ARM deployment also sets APP_VERSION and resource tags.

Examples:
  scripts/deploy-aca.sh \
    --version 0.1.1 \
    --resource-group rg-email-reminders \
    --acr-name myregistry \
    --aca-env-name email-reminders-env \
    --api-app-name email-reminders-api \
    --worker-app-name email-reminders-worker

  VERSION=0.1.1 AZURE_RESOURCE_GROUP=rg-email-reminders ACR_NAME=myregistry \
    ACA_ENV_NAME=email-reminders-env ACA_API_APP_NAME=email-reminders-api \
    scripts/deploy-aca.sh
USAGE
}

VERSION="${VERSION:-}"
AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"
AZURE_LOCATION="${AZURE_LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-}"
ACA_ENV_NAME="${ACA_ENV_NAME:-}"
ACA_API_APP_NAME="${ACA_API_APP_NAME:-}"
ACA_WORKER_APP_NAME="${ACA_WORKER_APP_NAME:-}"
ACA_IDENTITY_NAME="${ACA_IDENTITY_NAME:-email-reminders-aca-pull}"
IMAGE_NAME="${IMAGE_NAME:-email-reminders}"
PLATFORM="${PLATFORM:-linux/amd64}"
ACA_ENV_VARS="${ACA_ENV_VARS:-}"
ARM_TEMPLATE_FILE="${ARM_TEMPLATE_FILE:-infra/aca/azuredeploy.json}"
PUSH_LATEST="true"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version)
      VERSION="${2:?Missing value for --version}"
      shift 2
      ;;
    --resource-group)
      AZURE_RESOURCE_GROUP="${2:?Missing value for --resource-group}"
      shift 2
      ;;
    --location)
      AZURE_LOCATION="${2:?Missing value for --location}"
      shift 2
      ;;
    --acr-name)
      ACR_NAME="${2:?Missing value for --acr-name}"
      shift 2
      ;;
    --aca-env-name)
      ACA_ENV_NAME="${2:?Missing value for --aca-env-name}"
      shift 2
      ;;
    --api-app-name)
      ACA_API_APP_NAME="${2:?Missing value for --api-app-name}"
      shift 2
      ;;
    --worker-app-name)
      ACA_WORKER_APP_NAME="${2:?Missing value for --worker-app-name}"
      shift 2
      ;;
    --identity-name)
      ACA_IDENTITY_NAME="${2:?Missing value for --identity-name}"
      shift 2
      ;;
    --image-name)
      IMAGE_NAME="${2:?Missing value for --image-name}"
      shift 2
      ;;
    --platform)
      PLATFORM="${2:?Missing value for --platform}"
      shift 2
      ;;
    --env-vars)
      ACA_ENV_VARS="${2:?Missing value for --env-vars}"
      shift 2
      ;;
    --template-file)
      ARM_TEMPLATE_FILE="${2:?Missing value for --template-file}"
      shift 2
      ;;
    --no-latest)
      PUSH_LATEST="false"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_value() {
  local name="$1"
  local value="$2"

  if [ -z "$value" ]; then
    echo "Missing required value: $name" >&2
    usage >&2
    exit 2
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 127
  fi
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

env_vars_to_json() {
  local env_json="["
  local first="true"
  local pair name value

  if [ -n "$ACA_ENV_VARS" ]; then
    read -r -a EXTRA_ENV_ARGS <<< "$ACA_ENV_VARS"
    for pair in "${EXTRA_ENV_ARGS[@]}"; do
      name="${pair%%=*}"
      value="${pair#*=}"

      if [ -z "$name" ] || [ "$name" = "$pair" ]; then
        echo "Invalid env var '$pair'. Use KEY=VALUE format." >&2
        exit 2
      fi

      if [ "$first" = "true" ]; then
        first="false"
      else
        env_json+=","
      fi

      env_json+="{\"name\":\"$(json_escape "$name")\",\"value\":\"$(json_escape "$value")\"}"
    done
  fi

  env_json+="]"
  printf '%s' "$env_json"
}

sanitize_revision_suffix() {
  echo "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9-]+/-/g; s/^-+//; s/-+$//; s/-+/-/g' \
    | cut -c 1-63
}

require_value "VERSION or --version" "$VERSION"
require_value "AZURE_RESOURCE_GROUP or --resource-group" "$AZURE_RESOURCE_GROUP"
require_value "ACR_NAME or --acr-name" "$ACR_NAME"
require_value "ACA_ENV_NAME or --aca-env-name" "$ACA_ENV_NAME"
require_value "ACA_API_APP_NAME or --api-app-name" "$ACA_API_APP_NAME"

if [ ! -f "$ARM_TEMPLATE_FILE" ]; then
  echo "ARM template not found: $ARM_TEMPLATE_FILE" >&2
  exit 2
fi

require_command az
require_command docker
require_command sed

az account show >/dev/null

GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || true)"
REVISION_SUFFIX="$(sanitize_revision_suffix "v-${VERSION}")"

if [ -z "$REVISION_SUFFIX" ]; then
  echo "Version '$VERSION' cannot be converted into a valid ACA revision suffix." >&2
  exit 2
fi

echo "Reading ACR login server for: $ACR_NAME"
ACR_LOGIN_SERVER="$(
  az acr show \
    --name "$ACR_NAME" \
    --query loginServer \
    --output tsv
)"
ACR_RESOURCE_ID="$(
  az acr show \
    --name "$ACR_NAME" \
    --query id \
    --output tsv
)"

IMAGE_REF="${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${VERSION}"
LATEST_REF="${ACR_LOGIN_SERVER}/${IMAGE_NAME}:latest"

echo "Building image: $IMAGE_REF"
docker build \
  --platform "$PLATFORM" \
  --label "org.opencontainers.image.version=$VERSION" \
  --label "org.opencontainers.image.revision=$GIT_SHA" \
  --tag "$IMAGE_REF" \
  --tag "$LATEST_REF" \
  .

echo "Logging in to ACR: $ACR_NAME"
az acr login --name "$ACR_NAME"

echo "Pushing image: $IMAGE_REF"
docker push "$IMAGE_REF"

if [ "$PUSH_LATEST" = "true" ]; then
  echo "Pushing image: $LATEST_REF"
  docker push "$LATEST_REF"
fi

APP_ENV_JSON="$(env_vars_to_json)"

echo "Deploying Azure Container Apps from ARM template: $ARM_TEMPLATE_FILE"
az deployment group create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --template-file "$ARM_TEMPLATE_FILE" \
  --parameters \
    location="$AZURE_LOCATION" \
    version="$VERSION" \
    gitSha="$GIT_SHA" \
    imageRef="$IMAGE_REF" \
    revisionSuffix="$REVISION_SUFFIX" \
    acrLoginServer="$ACR_LOGIN_SERVER" \
    acrResourceId="$ACR_RESOURCE_ID" \
    managedIdentityName="$ACA_IDENTITY_NAME" \
    containerAppsEnvironmentName="$ACA_ENV_NAME" \
    apiAppName="$ACA_API_APP_NAME" \
    workerAppName="$ACA_WORKER_APP_NAME" \
    appEnv="$APP_ENV_JSON"

echo
echo "Deployment complete."
echo "Version: $VERSION"
echo "Image: $IMAGE_REF"
echo "ARM template: $ARM_TEMPLATE_FILE"
echo "API app: $ACA_API_APP_NAME"
if [ -n "$ACA_WORKER_APP_NAME" ]; then
  echo "Worker app: $ACA_WORKER_APP_NAME"
fi
