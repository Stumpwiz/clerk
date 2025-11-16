# AWS Deployment Context — App Runner + RDS PostgreSQL

Status: ✅ App Runner Active | ⏳ RDS Migration Pending

Database: PostgreSQL 18.1 (Exclusive) on AWS RDS

Account: 365591166807
Region: us-east-1

Backend App Runner ARN: arn:aws:apprunner:us-east-1:365591166807:service/clerk-backend/181518238ff148e88363a488640dd90d
Frontend App Runner ARN: arn:aws:apprunner:us-east-1:365591166807:service/clerk-frontend/7d7f42151edb48fb87d706a4cceb2e4a

Backend URL: https://yjppumxuvt.us-east-1.awsapprunner.com
Frontend URL: https://ejqrduz5xi.us-east-1.awsapprunner.com

PostgreSQL is now the exclusive database across all environments. There is no SQLite fallback.

---

## 1) Overview of AWS Architecture

We deploy stateless containers to AWS App Runner and use AWS RDS for the PostgreSQL database. Images are built locally or in CI and pushed to Amazon ECR. App Runner pulls images from ECR and runs them in managed containers. RDS runs in a private VPC; App Runner accesses it via a VPC connector.

Key properties:
- Fully managed compute (App Runner) with autoscaling and HTTPS by default.
- Managed PostgreSQL (RDS) for reliability, backups, and monitoring.
- Build → Push to ECR → App Runner deploys new revision.
- Secrets provided via App Runner environment variables sourced from SSM Parameter Store.

---

## 2) Architecture Diagram (text)

```
                      +-------------------------------+
                      |        GitHub Actions         |
                      |  (build, test, push to ECR)   |
                      +---------------+---------------+
                                      |
                                      v
                              +---------------+
                              |   Amazon ECR  |
                              | clerk-* repos |
                              +-------+-------+
                                      |
              +-----------------------+-----------------------+
              |                                               |
              v                                               v
   +----------------------+                        +----------------------+
   |  App Runner Service  |                        |  App Runner Service  |
   |   clerk-backend      |                        |   clerk-frontend     |
   | (HTTPS endpoint)     |                        | (HTTPS endpoint)     |
   +----------+-----------+                        +----------+-----------+
              |                                               |
              | VPC Connector (for backend only)              |
              v                                               |
        +-----------+                                +--------+--------+
        |   VPC     |                                |   Internet     |
        +-----+-----+                                +----------------+
              |
              v
      +--------------+
      |  AWS RDS     |
      | PostgreSQL   |
      +--------------+
```

---

## 3) AWS Resources and Configuration

- Account ID: 365591166807
- Region: us-east-1

Compute (App Runner):
- Backend
  - ARN: arn:aws:apprunner:us-east-1:365591166807:service/clerk-backend/181518238ff148e88363a488640dd90d
  - URL: https://yjppumxuvt.us-east-1.awsapprunner.com
  - Port: 8000 (Uvicorn)
  - VPC access: required to reach RDS (via VPC Connector)
- Frontend
  - ARN: arn:aws:apprunner:us-east-1:365591166807:service/clerk-frontend/7d7f42151edb48fb87d706a4cceb2e4a
  - URL: https://ejqrduz5xi.us-east-1.awsapprunner.com

Container Registry (ECR):
- Suggested repos (create if not existing):
  - 365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-backend
  - 365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-frontend

Database (RDS):
- Engine: PostgreSQL 18.1
- Instance class: start small (e.g., db.t4g.micro) for non-prod; size according to load in prod.
- Storage: gp3 with autoscaling; Multi-AZ for production availability.
- Connectivity: private subnets, security group allowing inbound from App Runner’s VPC Connector ENIs.
- Backups: automated backups with PITR enabled.

Networking:
- VPC: private subnets for RDS, NAT or no direct internet depending on policy.
- App Runner VPC Connector: attach to private subnets to reach RDS.
- Security Groups: restrict RDS to App Runner connector sources only.

---

## 4) Environment Variables

PostgreSQL is the only supported database. Use `DATABASE_URL` (no SQLite fallback).

Backend (App Runner service: clerk-backend):
- DATABASE_URL=postgresql://<db_user>:<db_password>@<rds-endpoint>:5432/clerk_community_admin
- CLERK_SECRET_KEY=... (secret)
- CLERK_PUBLISHABLE_KEY=...
- API_HOST=0.0.0.0
- API_PORT=8000
- DEBUG=false
- CORS_ORIGINS=https://ejqrduz5xi.us-east-1.awsapprunner.com,https://your-custom-domain
- UVICORN_WORKERS=2 (adjust per CPU)
- DISABLE_AUTO_MIGRATE=false (set true if running migrations externally)

Frontend (App Runner service: clerk-frontend):
- NEXT_PUBLIC_API_URL=https://yjppumxuvt.us-east-1.awsapprunner.com
- NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=...
- CLERK_SECRET_KEY=... (only if needed for server-side functions)
- NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
- NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
- NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
- NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard

Note: Prefer injecting secrets at deploy time via SSM Parameter Store references rather than hardcoding.

---

## 5) SSM Parameter Store Recommendations

Use SecureString parameters with a KMS key. Suggested hierarchy (examples):

Backend (prod):
- /clerk/prod/backend/DATABASE_URL (SecureString)
- /clerk/prod/backend/CLERK_SECRET_KEY (SecureString)
- /clerk/prod/backend/CLERK_PUBLISHABLE_KEY (String)
- /clerk/prod/backend/CORS_ORIGINS (String)

Frontend (prod):
- /clerk/prod/frontend/NEXT_PUBLIC_API_URL (String)
- /clerk/prod/frontend/NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY (String)

In App Runner, set environment variables to the SSM parameter ARNs using the console or `aws apprunner update-service` with `ValueType: PARAMETER_STORE` (if using the API). Ensure the App Runner instance role has `ssm:GetParameter` and KMS decrypt permissions for the key.

---

## 6) Deployment Workflows

### A. Initial Setup
1. Create ECR Repositories (if not existing):
   - clerk-backend
   - clerk-frontend
2. Configure App Runner services for backend and frontend pulling from ECR.
3. Create VPC Connector for backend service and attach it.
4. Provision RDS PostgreSQL (see RDS migration steps below).
5. Configure SSM parameters and bind them to App Runner env vars.

### B. Current State
- App Runner services are active at the URLs listed above.
- RDS migration is pending; backend may still be using a temporary database. Move to RDS as soon as provisioned.

### C. RDS Migration Steps
1. Provision RDS PostgreSQL 18.1 in private subnets; enable automated backups and Performance Insights.
2. Create `clerk_user` and `clerk_community_admin` database; enforce SSL.
3. Allow inbound from App Runner VPC connector SG to RDS SG on port 5432.
4. Update SSM `/clerk/prod/backend/DATABASE_URL` to RDS endpoint (optionally add `?sslmode=require`).
5. Trigger a backend deployment (or restart) — backend startup orchestrator runs `alembic upgrade head` unless `DISABLE_AUTO_MIGRATE=true`.
6. Verify connectivity and schema (`/health`, logs, and Alembic state).
7. Run smoke tests and switch traffic (if using custom domains) once healthy.

---

## 7) Deployment Commands (CLI Examples)

Authenticate Docker to ECR:
```
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin 365591166807.dkr.ecr.us-east-1.amazonaws.com
```

Build, tag, push (backend):
```
docker build -t clerk-backend:prod ./backend
docker tag clerk-backend:prod 365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-backend:prod
docker push 365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-backend:prod
```

Build, tag, push (frontend):
```
docker build -t clerk-frontend:prod ./frontend \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_xxx \
  --build-arg NEXT_PUBLIC_API_URL=https://yjppumxuvt.us-east-1.awsapprunner.com
docker tag clerk-frontend:prod 365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-frontend:prod
docker push 365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-frontend:prod
```

Update App Runner service to new image (backend):
```
aws apprunner update-service \
  --service-arn arn:aws:apprunner:us-east-1:365591166807:service/clerk-backend/181518238ff148e88363a488640dd90d \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-backend:prod",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000"
      }
    },
    "AutoDeploymentsEnabled": true
  }'
```

Update App Runner service to new image (frontend):
```
aws apprunner update-service \
  --service-arn arn:aws:apprunner:us-east-1:365591166807:service/clerk-frontend/7d7f42151edb48fb87d706a4cceb2e4a \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-frontend:prod",
      "ImageRepositoryType": "ECR"
    },
    "AutoDeploymentsEnabled": true
  }'
```

Note: If setting env vars via CLI, use `RuntimeEnvironmentVariables` in the `ImageConfiguration`. For Parameter Store, configure via console or API with parameter bindings.

---

## 8) Monitoring & Logs (CloudWatch)

App Runner:
- Request count, latency, 4xx/5xx error rates.
- CloudWatch log groups per service; enable log retention (e.g., 30–90 days).
- Alarms: high 5xx, high latency (p95), CPU/memory saturation.

RDS PostgreSQL:
- Performance Insights for query analysis.
- Enhanced Monitoring and CloudWatch metrics: CPU, connections, free storage, read/write IOPS, replicas lag (if applicable).
- Alarms: CPU > 70% sustained, connections near max, storage < 15% free.

Application:
- Health endpoint: `/health` on backend.
- Alembic state validation after deploy.

---

## 9) Security Best Practices

- Secrets management via SSM Parameter Store (SecureString) and KMS; avoid plaintext in repos.
- Restrict RDS security group to App Runner VPC connector ENIs only; no public exposure.
- Enforce TLS to RDS (DATABASE_URL with `sslmode=require` when policy dictates).
- Use least privilege IAM roles for App Runner to pull parameters and images.
- Consider WAF on custom domains for frontend/backend if exposed publicly.
- Keep base images updated; rebuild periodically to pull patched OS layers.
- Disable DEBUG in production.

---

## 10) Cost Optimization

- Start with small RDS instance class (db.t4g.micro) and scale based on metrics.
- Enable autoscaling on App Runner and set sensible min/max concurrency.
- Optimize log retention to lower storage costs.
- Use multi-stage Docker builds and slimmer base images to reduce transfer time.
- Consider PgBouncer if connection spikes cause RDS scaling pressure.

---

## 11) Troubleshooting

Connectivity (backend → RDS):
- Ensure backend App Runner service is attached to a VPC connector with routes to the RDS subnets.
- Verify RDS SG inbound from the connector’s SG on 5432.
- Check that `DATABASE_URL` host is the RDS endpoint, not `localhost`.

App Runner image pull or start failures:
- Confirm ECR image tag exists and IAM permissions are correct.
- Review CloudWatch logs for startup errors (e.g., Alembic migrations).

Clerk auth issues:
- Verify publishable/secret keys and allowed origins for the frontend URL.

Migrations:
- If using `DISABLE_AUTO_MIGRATE=true`, run `alembic upgrade head` from a runner with VPC access to RDS.

---

## 12) Rollback Procedures

Application rollback:
1. Identify the previous working image tag or digest in ECR.
2. Update the App Runner service to that image (`update-service`).
3. If a config change caused the issue, revert the environment variable or Parameter Store value and redeploy.

Database rollback:
1. Stop write traffic if necessary.
2. Use RDS PITR or a snapshot to restore to a new instance.
3. Update `DATABASE_URL` to point to the restored instance and redeploy.
4. Apply forward migrations if needed to align schema with app version.

Note: Rollback to SQLite is not supported; PostgreSQL is exclusive.

---

## 13) Production Readiness Checklist

- [ ] Backend and frontend App Runner services healthy and autoscaling configured.
- [ ] Custom domains and HTTPS validated (optional but recommended).
- [ ] RDS in Multi-AZ with automated backups and Performance Insights enabled.
- [ ] App Runner VPC connector configured; RDS SG restricted to connector.
- [ ] SSM Parameter Store in place with proper IAM permissions.
- [ ] DEBUG disabled in production; CORS configured to allowed domains only.
- [ ] Alembic migrations tested in staging and applied cleanly in prod.
- [ ] CloudWatch alarms for 5xx, latency, CPU, connections, storage.
- [ ] Runbooks documented for on-call (deploy, rollback, backup/restore).

---

## 14) References

- App Runner Backend: https://yjppumxuvt.us-east-1.awsapprunner.com
- App Runner Frontend: https://ejqrduz5xi.us-east-1.awsapprunner.com
- ECR: 365591166807.dkr.ecr.us-east-1.amazonaws.com
- Docs: `docs/database-migration-complete.md` (PostgreSQL migration)
- Compose: `docker-compose.yml`
- Backend Startup: `backend/scripts/docker_start.py`
- CI: `.github/workflows/test-postgres.yml`

---

## 15) Conclusion

We operate a managed, container-first deployment on App Runner with PostgreSQL on RDS as the exclusive database. With VPC connectivity, Parameter Store secrets, and CloudWatch monitoring, the stack is production-ready once the RDS migration is completed and validated. Follow the checklists and workflows here to deploy, observe, and evolve safely.
