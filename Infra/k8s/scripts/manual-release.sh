#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 FRONTEND_IMAGE BACKEND_IMAGE" >&2
  exit 2
fi

frontend_image=$1
backend_image=$2
namespace=${NAMESPACE:-cineverse}
migration_job="backend-migration-$(date -u +%Y%m%d%H%M%S)"

if [[ "${CONFIRM_DEPLOY:-}" != "DEPLOY" ]]; then
  echo "set CONFIRM_DEPLOY=DEPLOY after checking the image names" >&2
  exit 1
fi

if [[ "${BACKUP_VERIFIED:-}" != "BACKUP_VERIFIED" ]]; then
  echo "set BACKUP_VERIFIED=BACKUP_VERIFIED after checking a restorable backup" >&2
  exit 1
fi

for image in "${frontend_image}" "${backend_image}"; do
  if [[ "${image}" != *:* ]]; then
    echo "an immutable image tag is required: ${image}" >&2
    exit 1
  fi
done

bash Infra/k8s/scripts/cluster-preflight.sh "${namespace}"

temporary_manifest=$(mktemp)
trap 'rm -f "${temporary_manifest}"' EXIT
sed \
  -e "s/^  name: backend-migration$/  name: ${migration_job}/" \
  -e "s#^          image: .*$#          image: ${backend_image}#" \
  Infra/k8s/base/migration-job.yaml >"${temporary_manifest}"

grep -Fq "name: ${migration_job}" "${temporary_manifest}"
grep -Fq "image: ${backend_image}" "${temporary_manifest}"

kubectl apply -f "${temporary_manifest}"
if ! kubectl -n "${namespace}" wait \
  --for=condition=complete "job/${migration_job}" --timeout=300s; then
  kubectl -n "${namespace}" logs "job/${migration_job}" --all-containers || true
  kubectl -n "${namespace}" describe "job/${migration_job}" || true
  exit 1
fi

kubectl -n "${namespace}" logs "job/${migration_job}"
kubectl -n "${namespace}" set image deployment/backend "backend=${backend_image}"
kubectl -n "${namespace}" set image deployment/frontend "frontend=${frontend_image}"
kubectl -n "${namespace}" rollout status deployment/backend --timeout=300s
kubectl -n "${namespace}" rollout status deployment/frontend --timeout=300s

curl --fail --silent --show-error https://movieverse.cloud/api/ready >/dev/null
curl --fail --silent --show-error https://movieverse.cloud/api/db-test >/dev/null
curl --fail --silent --show-error https://movieverse.cloud/api/ai-health >/dev/null

echo "manual release completed"
