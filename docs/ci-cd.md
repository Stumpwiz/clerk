# CI/CD with GitHub Actions (CLERK System)

This project includes:
- CI workflow: build API and Web, run basic tests, and validate Docker builds.
- CD workflow: build and push Docker images to Amazon ECR using GitHub OIDC, and optionally force ECS service redeploys.

## 1) Prerequisites

- GitHub repository created and this code pushed (including .github/workflows).
- AWS account with:
  - ECR repositories for images (suggested names):
    - clerk-api
    - clerk-web
  - ECS cluster and services (optional for automatic redeploy).
- Create an IAM Role for GitHub OIDC:
  - Trusted entity: GitHub OIDC provider.
  - Trust policy restricted to your repo (owner/name) and workflows if desired.
  - Permissions: ECR (push), and ECS (optional) update-service.
    - Example AWS managed policies to start: AmazonEC2ContainerRegistryPowerUser, AmazonECSFullAccess (narrow as needed).

Useful AWS docs: https://github.com/aws-actions/configure-aws-credentials

## 2) Configure GitHub repository secrets and variables

In GitHub repo Settings:
- Secrets:
  - AWS_ROLE_TO_ASSUME: arn:aws:iam::<account-id>:role/<role-name>
  - AWS_REGION: your region, e.g., us-east-1
- Variables (Settings → Variables → Actions → Repository variables):
  - ECR_REPOSITORY_API: clerk-api
  - ECR_REPOSITORY_WEB: clerk-web
  - ECS_CLUSTER: your-ecs-cluster-name (optional)
  - ECS_SERVICE_API: your-api-service-name (optional)
  - ECS_SERVICE_WEB: your-web-service-name (optional)

The CD workflow is designed to skip gracefully until the required secrets/vars are present.

## 3) CI workflow (automatic on PRs and pushes to main)

What it does:
- API: installs Python deps, syntax-compiles the FastAPI app, and runs pytest if tests are present.
- Web: installs Node deps and runs a production build.
- Docker: performs a no-push docker build for both images to catch Dockerfile errors.

File: .github/workflows/ci.yml

## 4) CD workflow (manual or tag-based)

Triggers:
- Manual: Actions → CD - Push Docker images to ECR → Run workflow.
- Tag push: git tag v1.0.0 && git push origin v1.0.0.

What it does:
- Configures AWS creds via OIDC (no static keys).
- Logs in to ECR.
- Builds and pushes two images with tags:
  - <registry>/<repo>:<short-sha>
  - <registry>/<repo>:<tag or build-N>
- Optionally forces ECS service new deployment(s) if ECS_* variables are defined.

File: .github/workflows/cd-ecr.yml

## 5) Mapping to this repo

- API context: apps/api (Dockerfile present; XeLaTeX installed in image).
- Web context: apps/web (Next.js production build in image).
- Local dev remains via docker-compose.yml.

## 6) Post-push verification (after ECS redeploy)

- ALB paths:
  - /health
  - /api/v1/db-check
- Web should proxy to API internally and respect Clerk config.
- Validate PDF generation endpoints (letters, rosters, reports).

## 7) Notes and best practices

- Prefer GitHub OIDC over long-lived AWS keys.
- Pin action major versions (done) and update periodically.
- Add real tests over time; CI currently runs them only if present.
- Consider adding lint/type-check steps as you adopt tools (ruff/flake8/mypy).
- For production, consider pushing both :<sha> and :latest or :<env> tags as needed.
