#!/usr/bin/env bash
set -euo pipefail

# Configure these
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-000000000000}"
REPO="clerk-api"
IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO}"

echo "Logging into ECR..."
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "Building image..."
docker build -t "${REPO}" ./apps/api

echo "Tagging image..."
docker tag "${REPO}:latest" "${IMAGE_URI}:latest"

echo "Pushing image..."
docker push "${IMAGE_URI}:latest"

echo "Done. Image available at: ${IMAGE_URI}:latest"
