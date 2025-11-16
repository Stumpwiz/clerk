#!/usr/bin/env bash
# rds-verify-backup.sh — Verify an RDS snapshot by checking its status and (optionally) restoring to a temporary instance and running a probe query.

set -euo pipefail

AWS_REGION=${AWS_REGION:-us-east-1}

usage() {
  cat <<USAGE
Usage: $0 --snapshot-id <snapshot-id> [--probe] [--temp-instance-class db.t4g.micro] [--temp-sg-ids sg-123] [--temp-subnet-group name] [--cleanup]

Options:
  --probe                Restore snapshot to a temporary instance and run SELECT 1 via psql
  --cleanup              If --probe is used, delete the temporary instance after verification
  --temp-instance-class  Instance class for the temp restore (default: db.t4g.micro)
  --temp-sg-ids          Comma-separated SG IDs for temp instance (optional)
  --temp-subnet-group    DB subnet group name for temp instance (optional)
  --region               AWS region (default: us-east-1)

Requires: aws, jq, psql (for --probe)
USAGE
}

require() { command -v "$1" >/dev/null 2>&1 || { echo "[ERROR] Missing command: $1" >&2; exit 1; }; }

require aws
require jq

SNAPSHOT_ID=""
PROBE="false"
CLEANUP="false"
CLASS="db.t4g.micro"
SG_IDS=""
SUBNET_GROUP=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --snapshot-id) SNAPSHOT_ID="$2"; shift 2;;
    --probe) PROBE="true"; shift 1;;
    --cleanup) CLEANUP="true"; shift 1;;
    --temp-instance-class) CLASS="$2"; shift 2;;
    --temp-sg-ids) SG_IDS="$2"; shift 2;;
    --temp-subnet-group) SUBNET_GROUP="$2"; shift 2;;
    --region) AWS_REGION="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "[ERROR] Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

[[ -n "$SNAPSHOT_ID" ]] || { echo "[ERROR] --snapshot-id is required" >&2; usage; exit 1; }

echo "[INFO] Checking snapshot status for $SNAPSHOT_ID in $AWS_REGION…"
DESC=$(aws rds describe-db-snapshots --region "$AWS_REGION" --db-snapshot-identifier "$SNAPSHOT_ID")
STATUS=$(printf '%s' "$DESC" | jq -r '.DBSnapshots[0].Status')
ARN=$(printf '%s' "$DESC" | jq -r '.DBSnapshots[0].DBSnapshotArn')
ENGINE=$(printf '%s' "$DESC" | jq -r '.DBSnapshots[0].Engine')
VERSION=$(printf '%s' "$DESC" | jq -r '.DBSnapshots[0].EngineVersion')

echo "[OK] Snapshot: $SNAPSHOT_ID"
echo "[OK] Status:   $STATUS"
echo "[OK] Engine:   $ENGINE $VERSION"
echo "[OK] ARN:      $ARN"

if [[ "$STATUS" != "available" ]]; then
  echo "[WARN] Snapshot is not available; verification limited to status check."
  exit 1
fi

if [[ "$PROBE" != "true" ]]; then
  echo "[INFO] Verification complete (status: available)."
  exit 0
fi

require psql

TMP_ID="verify-$(echo "$SNAPSHOT_ID" | tr -cd '[:alnum:]-' | cut -c1-35)-$(date -u +%H%M%S)"
echo "[INFO] Restoring temporary instance $TMP_ID for probe…"

ARGS=(
  --region "$AWS_REGION"
  --db-instance-identifier "$TMP_ID"
  --db-snapshot-identifier "$SNAPSHOT_ID"
  --db-instance-class "$CLASS"
  --publicly-accessible true
)
[[ -n "$SUBNET_GROUP" ]] && ARGS+=(--db-subnet-group-name "$SUBNET_GROUP")
[[ -n "$SG_IDS" ]] && ARGS+=(--vpc-security-group-ids "$SG_IDS")

aws rds restore-db-instance-from-db-snapshot "${ARGS[@]}" >/dev/null
aws rds wait db-instance-available --region "$AWS_REGION" --db-instance-identifier "$TMP_ID"

DESC=$(aws rds describe-db-instances --region "$AWS_REGION" --db-instance-identifier "$TMP_ID")
HOST=$(printf '%s' "$DESC" | jq -r '.DBInstances[0].Endpoint.Address')
PORT=$(printf '%s' "$DESC" | jq -r '.DBInstances[0].Endpoint.Port')
USER=$(printf '%s' "$DESC" | jq -r '.DBInstances[0].MasterUsername')

echo "[INFO] Probing connectivity to $HOST:$PORT (username: $USER)…"
echo "[INFO] You may need to provide PGPASSWORD in env if snapshot has non-empty password."

set +e
PGPASSWORD=${PGPASSWORD:-} psql -h "$HOST" -p "$PORT" -U "$USER" -d postgres -c 'select 1' -v ON_ERROR_STOP=1
RC=$?
set -e

if [[ $RC -eq 0 ]]; then
  echo "[OK] Probe query succeeded."
else
  echo "[WARN] Probe query failed with exit code $RC. Check SG rules and password."
fi

if [[ "$CLEANUP" == "true" ]]; then
  echo "[INFO] Cleaning up temporary instance $TMP_ID…"
  aws rds delete-db-instance --region "$AWS_REGION" --db-instance-identifier "$TMP_ID" --skip-final-snapshot >/dev/null || true
  echo "[INFO] Waiting for deletion…"
  set +e
  aws rds wait db-instance-deleted --region "$AWS_REGION" --db-instance-identifier "$TMP_ID"
  set -e
  echo "[OK] Temporary instance deleted."
fi

exit $RC
