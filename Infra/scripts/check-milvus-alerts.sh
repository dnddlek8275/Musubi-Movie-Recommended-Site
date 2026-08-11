#!/usr/bin/env bash

set -u

# Milvus v2.4.0 known warning:
# DataCoord metrics code stores IndexID in the FieldID slot, so RootCoord
# repeatedly logs the message below while reporting indexed entity metrics.
# This is a Milvus v2.4.0 version bug, not evidence of collection corruption.
# Keep the original Docker logs; exclude only this exact message from this
# operational alert view so that other WARN/ERROR/FATAL/PANIC messages remain visible.
KNOWN_MILVUS_V240_WARNING='field id not found, ignore to report indexed num entities'
SINCE="${1:-10m}"
CONTAINER="${MILVUS_CONTAINER:-milvus-standalone}"

if ! sudo docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "ERROR: Milvus container not found: $CONTAINER" >&2
  exit 2
fi

STATE="$(sudo docker inspect "$CONTAINER" --format 'status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} restarts={{.RestartCount}}')"
echo "$STATE"

if [[ "$STATE" != *"status=running"* ]] || [[ "$STATE" == *"health=unhealthy"* ]]; then
  echo "ERROR: Milvus container state requires attention." >&2
  exit 2
fi

FILTERED_LOGS="$(sudo docker logs --since "$SINCE" "$CONTAINER" 2>&1 \
  | grep -vF "$KNOWN_MILVUS_V240_WARNING" \
  | grep -Ei 'warn|error|fatal|panic' || true)"

if [[ -n "$FILTERED_LOGS" ]]; then
  echo "$FILTERED_LOGS"
  exit 1
fi

echo "OK: No actionable Milvus warnings or errors in the last $SINCE."
