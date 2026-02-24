#!/usr/bin/env bash
# rds-create-snapshot.sh — Create an on-demand RDS PostgreSQL snapshot and wait until available.

set -euo pipefail

AWS_REGION=${AWS_REGION:-us-east-1}

usage() {
  cat <<USAGE
Usage: $0 --db-instance-id <identifier> [--snapshot-id <id>] [--tag Key=Project,Value=Clerk]... [--region us-east-1]

Examples:
  $0 --db-instance-id clerk-rds-pg
  $0 --db-instance-id clerk-rds-pg --snapshot-id clerk-rds-pg-$(date -u +%Y%m%dT%H%M%SZ)

Environment:
  AWS_REGION  (default: us-east-1)

Requires: aws
USAGE
}

require() { command -v "$1" >/dev/null 2>&1 || { echo "[ERROR] Missing command: $1" >&2; exit 1; }; }

require aws

DB_INSTANCE_ID=""
SNAPSHOT_ID=""
TAG_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-instance-id) DB_INSTANCE_ID="$2"; shift 2;;
    --snapshot-id) SNAPSHOT_ID="$2"; shift 2;;
    --tag) TAG_ARGS+=("$2"); shift 2;;
    --region) AWS_REGION="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "[ERROR] Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

[[ -n "$DB_INSTANCE_ID" ]] || { echo "[ERROR] --db-instance-id is required" >&2; usage; exit 1; }

if [[ -z "$SNAPSHOT_ID" ]]; then
  SNAPSHOT_ID="${DB_INSTANCE_ID}-$(date -u +%Y%m%dT%H%M%SZ)"
fi

echo "[INFO] Creating snapshot $SNAPSHOT_ID for instance $DB_INSTANCE_ID in $AWS_REGION…"

aws rds create-db-snapshot \
  --region "$AWS_REGION" \
  --db-snapshot-identifier "$SNAPSHOT_ID" \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  >/dev/null

echo "[INFO] Waiting for snapshot to become available…"
aws rds wait db-snapshot-available --region "$AWS_REGION" --db-snapshot-identifier "$SNAPSHOT_ID"

DESC=$(aws rds describe-db-snapshots --region "$AWS_REGION" --db-snapshot-identifier "$SNAPSHOT_ID")
ARN=$(printf '%s' "$DESC" | python - <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data['DBSnapshots'][0]['DBSnapshotArn'])
PY
)
echo "[OK] Snapshot available: $SNAPSHOT_ID"
echo "[OK] Snapshot ARN: $ARN"

if [[ ${#TAG_ARGS[@]} -gt 0 ]]; then
  echo "[INFO] Tagging snapshot…"
  aws rds add-tags-to-resource --region "$AWS_REGION" --resource-name "$ARN" --tags "${TAG_ARGS[@]}"
  echo "[OK] Tags added."
fi

echo "[INFO] Done."
