#!/usr/bin/env bash
# rds-restore-from-snapshot.sh — Restore an RDS instance from a snapshot (creates a NEW instance).

set -euo pipefail

AWS_REGION=${AWS_REGION:-us-east-1}

usage() {
  cat <<USAGE
Usage: $0 --snapshot-id <snapshot-id> --new-db-instance-id <new-id> \
          [--db-instance-class db.t4g.micro] [--db-subnet-group <name>] \
          [--vpc-security-group-ids sg-abc,sg-def] [--publicly-accessible true|false] \
          [--tag Key=Project,Value=Clerk]... [--region us-east-1]

Notes:
  - This creates a NEW DB instance from the specified snapshot.
  - You are responsible for deleting old instances and snapshots you no longer need.

Requires: aws, jq
USAGE
}

require() { command -v "$1" >/dev/null 2>&1 || { echo "[ERROR] Missing command: $1" >&2; exit 1; }; }

require aws
require jq

SNAPSHOT_ID=""
NEW_ID=""
CLASS="db.t4g.micro"
SUBNET_GROUP=""
SG_IDS=""
PUBLIC="true"
TAG_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --snapshot-id) SNAPSHOT_ID="$2"; shift 2;;
    --new-db-instance-id) NEW_ID="$2"; shift 2;;
    --db-instance-class) CLASS="$2"; shift 2;;
    --db-subnet-group) SUBNET_GROUP="$2"; shift 2;;
    --vpc-security-group-ids) SG_IDS="$2"; shift 2;;
    --publicly-accessible) PUBLIC="$2"; shift 2;;
    --tag) TAG_ARGS+=("$2"); shift 2;;
    --region) AWS_REGION="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "[ERROR] Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

[[ -n "$SNAPSHOT_ID" && -n "$NEW_ID" ]] || { echo "[ERROR] --snapshot-id and --new-db-instance-id are required" >&2; usage; exit 1; }

echo "[INFO] Restoring $NEW_ID from snapshot $SNAPSHOT_ID in $AWS_REGION…"

ARGS=(
  --region "$AWS_REGION"
  --db-instance-identifier "$NEW_ID"
  --db-snapshot-identifier "$SNAPSHOT_ID"
  --db-instance-class "$CLASS"
  --publicly-accessible "$PUBLIC"
)

if [[ -n "$SUBNET_GROUP" ]]; then
  ARGS+=(--db-subnet-group-name "$SUBNET_GROUP")
fi
if [[ -n "$SG_IDS" ]]; then
  ARGS+=(--vpc-security-group-ids "$SG_IDS")
fi

aws rds restore-db-instance-from-db-snapshot "${ARGS[@]}" >/dev/null

echo "[INFO] Waiting for new instance to become available…"
aws rds wait db-instance-available --region "$AWS_REGION" --db-instance-identifier "$NEW_ID"

DESC=$(aws rds describe-db-instances --region "$AWS_REGION" --db-instance-identifier "$NEW_ID")
ENDPOINT=$(printf '%s' "$DESC" | jq -r '.DBInstances[0].Endpoint.Address')
PORT=$(printf '%s' "$DESC" | jq -r '.DBInstances[0].Endpoint.Port')
ARN=$(printf '%s' "$DESC" | jq -r '.DBInstances[0].DBInstanceArn')

echo "[OK] Restored instance: $NEW_ID"
echo "[OK] Endpoint: $ENDPOINT:$PORT"
echo "[OK] ARN: $ARN"

if [[ ${#TAG_ARGS[@]} -gt 0 ]]; then
  echo "[INFO] Tagging instance…"
  aws rds add-tags-to-resource --region "$AWS_REGION" --resource-name "$ARN" --tags "${TAG_ARGS[@]}"
  echo "[OK] Tags added."
fi

echo "[INFO] Done."
