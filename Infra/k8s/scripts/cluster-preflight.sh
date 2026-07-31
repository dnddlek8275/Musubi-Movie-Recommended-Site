#!/usr/bin/env bash

set -euo pipefail

namespace="${1:-cineverse}"

fail() {
  echo "::error::$1" >&2
  exit 1
}

require_resource() {
  local resource="$1"
  local name="$2"
  kubectl -n "${namespace}" get "${resource}" "${name}" >/dev/null 2>&1 ||
    fail "Required ${resource}/${name} was not found in namespace ${namespace}."
}

require_jsonpath_value() {
  local resource="$1"
  local name="$2"
  local jsonpath="$3"
  local description="$4"
  local value
  value="$(kubectl -n "${namespace}" get "${resource}" "${name}" -o "jsonpath=${jsonpath}")"
  [[ -n "${value}" ]] || fail "${description} is not configured."
  printf '%s' "${value}"
}

reject_placeholder() {
  local description="$1"
  local value="$2"
  case "${value}" in
    *registry.example.com* | *service.example.com* | *smtp.example.com* | *ai.internal* | *db.internal* | *REPLACE_ME* | *REPLACE_WITH* | *USER:PASSWORD*)
      fail "${description} still contains a template placeholder."
      ;;
  esac
}

kubectl get namespace "${namespace}" >/dev/null 2>&1 ||
  fail "Namespace ${namespace} was not found. Complete the initial Kubernetes bootstrap first."

for resource_name in \
  "configmap cineverse-config" \
  "secret cineverse-secrets" \
  "secret cineverse-migration-secrets" \
  "persistentvolumeclaim backend-uploads" \
  "service backend" \
  "service frontend" \
  "deployment backend" \
  "deployment frontend" \
  "ingress cineverse-backend" \
  "ingress cineverse-frontend"; do
  read -r resource name <<<"${resource_name}"
  require_resource "${resource}" "${name}"
done

pvc_phase="$(require_jsonpath_value persistentvolumeclaim backend-uploads '{.status.phase}' 'backend-uploads PVC phase')"
[[ "${pvc_phase}" == "Bound" ]] ||
  fail "persistentvolumeclaim/backend-uploads is ${pvc_phase}; it must be Bound."

pvc_access_modes="$(require_jsonpath_value persistentvolumeclaim backend-uploads '{.spec.accessModes[*]}' 'backend-uploads access mode')"
[[ " ${pvc_access_modes} " == *" ReadWriteMany "* ]] ||
  fail "persistentvolumeclaim/backend-uploads must support ReadWriteMany for two backend replicas."

for key in AI_BASE_URL CORS_ORIGINS FRONTEND_BASE_URL MAIL_HOST MAIL_FROM; do
  value="$(require_jsonpath_value configmap cineverse-config "{.data.${key}}" "configmap/cineverse-config ${key}")"
  reject_placeholder "configmap/cineverse-config ${key}" "${value}"
done

app_database_url="$(
  require_jsonpath_value secret cineverse-secrets \
    '{.data.DATABASE_URL}' 'secret/cineverse-secrets DATABASE_URL' | base64 --decode
)"
migration_database_url="$(
  require_jsonpath_value secret cineverse-migration-secrets \
    '{.data.DATABASE_URL}' 'secret/cineverse-migration-secrets DATABASE_URL' | base64 --decode
)"

reject_placeholder "secret/cineverse-secrets DATABASE_URL" "${app_database_url}"
reject_placeholder "secret/cineverse-migration-secrets DATABASE_URL" "${migration_database_url}"
[[ "${app_database_url}" != "${migration_database_url}" ]] ||
  fail "Runtime and migration database URLs must be different."
[[ "${app_database_url}" == *":6432/"* ]] ||
  fail "Runtime DATABASE_URL must use PgBouncer port 6432."
[[ "${migration_database_url}" == *":5432/"* ]] ||
  fail "Migration DATABASE_URL must use direct PostgreSQL port 5432."

for deployment in backend frontend; do
  image="$(require_jsonpath_value deployment "${deployment}" \
    "{.spec.template.spec.containers[?(@.name==\"${deployment}\")].image}" \
    "deployment/${deployment} image")"
  reject_placeholder "deployment/${deployment} image" "${image}"

  for resource_path in requests.cpu requests.memory limits.cpu limits.memory; do
    require_jsonpath_value deployment "${deployment}" \
      "{.spec.template.spec.containers[?(@.name==\"${deployment}\")].resources.${resource_path}}" \
      "deployment/${deployment} resources.${resource_path}" >/dev/null
  done
done

for ingress in cineverse-backend cineverse-frontend; do
  host="$(require_jsonpath_value ingress "${ingress}" '{.spec.rules[0].host}' "ingress/${ingress} host")"
  reject_placeholder "ingress/${ingress} host" "${host}"
done

echo "Cluster preflight passed for namespace ${namespace}."
