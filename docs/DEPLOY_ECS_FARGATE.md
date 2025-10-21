ECS Fargate Deployment (Low-Volume, Single ALB, EFS persistence)

Overview
- Containers: api (FastAPI + XeLaTeX) and web (Next.js).
- Load balancer: 1 ALB with two target groups:
  - Path /api/* → api service (port 8000)
  - Default (/) → web service (port 3000)
- Storage: 1 EFS filesystem mounted into the api task:
  - /app/data (SQLite DB)
  - /app/files_letters (generated letters)
  - /app/files_roster_reports (generated rosters/reports)
- Secrets: Clerk keys via AWS Secrets Manager.
- Images: Stored in two ECR repositories.

Prereqs
- AWS account with permissions for ECR, ECS, EFS, IAM, and ALB.
- Docker installed; able to build images locally.

1) Create ECR repositories
- In AWS Console → ECR → Create repositories:
  - clerk-api
  - clerk-web
- Note each repository URI, e.g.:
  - <account_id>.dkr.ecr.<region>.amazonaws.com/clerk-api
  - <account_id>.dkr.ecr.<region>.amazonaws.com/clerk-web

2) Build and push images
- Use provided helper scripts (edit REGION/ACCOUNT/REPO as needed):
  - bash deploy/aws/ecr_push_api.sh
  - bash deploy/aws/ecr_push_web.sh

3) Create EFS filesystem
- AWS Console → EFS → Create file system.
- Choose the same VPC you’ll use for ECS.
- Note the File system ID (fs-xxxxxxxx).
- (Optional) Create an access point; not required for this setup.
- Ensure security groups/subnets allow NFS (2049) from ECS tasks.

4) Create IAM roles
- Execution role: ecsTaskExecutionRole (AWS managed policy AmazonECSTaskExecutionRolePolicy).
- Task role: ecsTaskRole (least-privilege; can be basic unless you access AWS APIs).

5) Create Secrets in AWS Secrets Manager
- Names (example):
  - CLERK_PUBLISHABLE_KEY
  - CLERK_SECRET_KEY
- Store your values. Note each secret ARN.

6) Create ECS Cluster
- ECS → Create cluster → Networking only (Fargate).
- Choose your VPC and subnets (public subnets are simplest to start).

7) Target groups and ALB
- Create two target groups (IP type):
  - tg-api (HTTP 8000), health check path: /health
  - tg-web (HTTP 3000), health check path: / (root)
- Create an ALB:
  - Internet-facing, in same VPC/subnets.
  - Listener HTTP 80 (or 443 with ACM cert).
  - Listener rules:
    - If path is /api/* → forward to tg-api
    - Default action → forward to tg-web

8) Task Definitions
- Use the example task definitions:
  - deploy/aws/ecs/taskdef-api.json
  - deploy/aws/ecs/taskdef-web.json
- Replace placeholders:
  - ${ECR_API_IMAGE_URI}, ${ECR_WEB_IMAGE_URI}
  - ${ECS_EXECUTION_ROLE_ARN}, ${ECS_TASK_ROLE_ARN}
  - ${EFS_FILESYSTEM_ID}
  - ${ALLOWED_ORIGINS} (e.g., ["https://your-domain.com","http://localhost:3000"])
  - Secrets ARNs for Clerk keys
- Register both task definitions in ECS (Console → Task definitions → Create new).

9) Create Services
- In ECS cluster → Create service (Fargate) for api:
  - Task definition: api task (latest revision)
  - Desired tasks: 1 (low volume)
  - Networking: same VPC/subnets, a security group that allows ingress from ALB SG
  - Load balancing: attach tg-api, container port 8000
  - Health check grace period: 30–60s
- Create service for web:
  - Task definition: web task (latest)
  - Load balancing: attach tg-web, container port 3000
- Set minimum task size:
  - api: 0.5 vCPU / 1 GB OK
  - web: 0.25–0.5 vCPU / 0.5–1 GB OK

10) Environment variables
- api task:
  - DATABASE_URL=sqlite:////app/data/community_admin.db
  - XELATEX_PATH=xelatex
  - ALLOWED_ORIGINS=["https://your-domain.com","http://localhost:3000"]
  - Secrets: CLERK_PUBLISHABLE_KEY, CLERK_SECRET_KEY from Secrets Manager
- web task:
  - NEXT_PUBLIC_API_BASE_URL=https://<your-ALB-DNS-or-domain>
  - API_INTERNAL_BASE_URL=https://<your-ALB-DNS-or-domain>
  - NODE_ENV=production

11) Verify
- ALB DNS name → should serve web.
- Visit /api/v1/db-check via web proxy:
  - https://<ALB>/api/proxy/api/v1/db-check
- PDF generation endpoints work; files persist in EFS.

Notes / Tips
- Persistence: EFS keeps your SQLite DB and PDFs across service restarts.
- Backups: create an EFS backup plan or periodically copy files from EFS to S3.
- TLS: Recommend HTTPS (ACM certificate on ALB’s 443 listener).
- Scaling: You can keep desired count at 1 for both services.
- Costs: EFS standard is fine for minimal usage; consider EFS IA for cost optimization if appropriate.
- CORS: keep ALLOWED_ORIGINS aligned with your web origin.
- Health checks: api: /health, web: /. Target group healthy is required for ALB to route.

Appendix: Troubleshooting
- 502/503 from ALB:
  - Check target health; ensure security groups allow ALB → task traffic.
  - Ensure health check paths match (/health and /).
- 403/401 on protected endpoints:
  - Verify Clerk keys and that the browser is signed in.
- PDFs fail:
  - Ensure xelatex is installed (in API image) and outputs to mounted folders.
  - Check API logs in ECS for LaTeX errors.
