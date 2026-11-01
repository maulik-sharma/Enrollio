#!/usr/bin/env bash
# Brings the full stack up and fails unless every service reports healthy
# within 120 seconds. Used by `make smoke` and CI.
set -euo pipefail

readonly TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"

cleanup() {
  if [[ "${KEEP_STACK_UP:-0}" != "1" ]]; then
    docker compose down -v
  fi
}
trap cleanup EXIT

docker compose up --build -d

service_count=$(docker compose config --services | wc -l)
deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))

while (( $(date +%s) < deadline )); do
  healthy_count=$(
    docker compose ps --format '{{.Service}}|{{.State}}|{{.Health}}' \
      | awk -F'|' '$2 == "running" && $3 == "healthy"' \
      | wc -l
  )
  if (( healthy_count >= service_count )); then
    echo "All ${service_count} services are healthy."
    exit 0
  fi
  sleep 2
done

echo "Services did not become healthy within ${TIMEOUT_SECONDS}s:" >&2
docker compose ps >&2
docker compose logs --no-color --tail=100 >&2
exit 1
