# Docker Local Dev and AWS Deployment Outline

## Local Development

Prereqs:
- Docker Desktop
- Clerk keys
- XeLaTeX is provided by the API container

Steps:
1) Create env files:
   - Copy apps/api/.env.example to apps/api/.env and set CLERK keys.
   - Copy apps/web/.env.local.example to apps/web/.env.local and set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.

2) Start:
   docker compose up --build

3) Access:
   - Web: http://localhost:3000
   - API Docs: http://localhost:8000/docs

4) Persistence:
   - SQLite DB: named volume `db_data` at /app/data/community_admin.db
   - PDFs: `letters_data` and `roster_data` volumes.

5) Template Editing:
   - Uncomment the templates bind mount in docker-compose.yml for live LaTeX edits if desired.

## Environment Variables

API (apps/api/.env):
- CLERK_PUBLISHABLE_KEY, CLERK_SECRET_KEY
- DATABASE_URL=sqlite:////app/data/community_admin.db
- XELATEX_PATH=xelatex
- ALLOWED_ORIGINS=["http://localhost:3000"]

Web (apps/web/.env.local):
- NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
- NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

## AWS Deployment (Outline)

Approach A: ECS (Fargate)
- Build and push images:
  - Backend: apps/api
  - Frontend: apps/web (static Next server)
- Secrets: Store Clerk keys in AWS Secrets Manager; inject as env in Task Definitions.
- Storage:
  - SQLite is fine for 1–2 users but requires persistent volume:
    - Use EFS mounted to /app/data for API task.
    - Alternatively, migrate to RDS if you need multi-task scaling.
  - PDFs:
    - Option 1: Keep on EFS under /app/files_*.
    - Option 2: Upload to S3 after generation (future enhancement).
- Networking:
  - ALB with 2 target groups (web 3000, api 8000) or one TG and path routing.
- CORS:
  - Set ALLOWED_ORIGINS to your public web URL.

Approach B: Single EC2
- Use docker compose or systemd services running the two containers.
- Persist /app/data and /app/files_* on an attached EBS volume.

Notes:
- Health checks: expose /docs or a simple /health on the API if needed.
- Logging: ship container logs to CloudWatch.
- Scaling: ECS allows future scaling; SQLite limits write concurrency; plan for Postgres if scale increases.
