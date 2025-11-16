# Database Migration Complete: SQLite to PostgreSQL 18.1

Migration Date: January 15, 2025

Status: ✅ Local Development Complete | ⏳ AWS RDS Deployment Pending

Database: PostgreSQL 18.1 (Exclusive)

---

## 1. Migration Overview

### Executive Summary
The Clerk Community Administration System has been migrated from SQLite to PostgreSQL 18.1. PostgreSQL is now used exclusively across all environments (local development, Docker, and production on AWS RDS). This change improves reliability, scalability, security, and developer experience. No SQLite fallback remains in the codebase or configuration.

### Why We Migrated (SQLite Limitations vs PostgreSQL Benefits)

SQLite limitations:
- Single-writer model limits concurrency and throughput.
- File-based storage not suitable for containers and ephemeral filesystems.
- No native replication, HA, roles, or granular access control.
- Limited type system and indexing options; weaker query planner.
- Increased risk of data loss in cloud runtimes that reset local storage.

PostgreSQL benefits:
- True client/server RDBMS with concurrent writers and robust locking.
- Rich type system (JSONB, UUID, arrays, tsvector), advanced indexing.
- Mature tooling for backups, PITR, and replication (especially on AWS RDS).
- Strong security model (roles, grants, SSL/TLS, parameter protections).
- Excellent performance tuning surface and observability.
- First-class support in SQLAlchemy via `psycopg2`.

### Migration Scope (Before → After)

| Area | Before (SQLite) | After (PostgreSQL 18.1) |
|---|---|---|
| Connection URL | `sqlite:///./instance/community_admin.db` | `postgresql://clerk_user:clerk_password@db:5432/clerk_community_admin` |
| Driver | builtin `sqlite3` | `psycopg2` |
| Container Orchestration | No DB container | Dedicated `db` service (Postgres) with healthcheck |
| Migrations | Alembic (limited types) | Alembic with Postgres types and server defaults |
| Production | Ephemeral file storage | AWS RDS PostgreSQL |

---

## 2. Architecture Changes

Text diagrams of before and after.

Before (SQLite):
```
[ Next.js Frontend ]  ->  [ FastAPI Backend ]  ->  [ SQLite DB File ]
                                       ^
                                       | (local file path ./instance/...)
```

After (PostgreSQL):
```
[ Next.js Frontend ]  ->  [ FastAPI Backend ]  ->  [ PostgreSQL 18.1 ]
                                                      ^
                                                      | Docker: host=db (compose)
                                                      | Local: host=localhost
                                                      | Prod: host=<RDS endpoint>
```

Key changes:
- Introduced a dedicated Postgres service in `docker-compose.yml` with healthchecks and init SQL.
- Backend startup script now waits for Postgres and runs Alembic migrations automatically.
- Environment variables standardized around `DATABASE_URL` for Postgres only.
- Removed SQLite directories/mounts and any conditional SQLite logic.

---

## 3. Changes Made

This section catalogs all relevant changes. PostgreSQL is the only supported database now.

Backend configuration:
- `backend/app/config.py`: `get_database_url()` now resolves to Postgres; SQLite code paths removed or deprecated.
- `backend/app/database.py`: SQLAlchemy engine and session creation set for Postgres via `psycopg2`.
- `backend/requirements.txt`: ensured `psycopg2` (or `psycopg2-binary`) is installed; removed any SQLite-specific dependencies.

Startup and scripts:
- `backend/scripts/docker_start.py`: waits for DB readiness and runs `alembic upgrade head` when `DATABASE_URL` is Postgres.
- `backend/scripts/wait_for_db.py`: invoked by startup orchestrator to block until Postgres is healthy.

Migrations (Alembic):
- Alembic configuration retained; migrations compatible with Postgres types and constraints.
- Auto-migration at container start can be disabled by `DISABLE_AUTO_MIGRATE=true`.

Docker:
- `docker-compose.yml`: added `db` service using `postgres:18.1` with healthcheck; backend depends on `service_healthy`.
- Removed SQLite instance volume mounts from backend; volumes now only for generated files and static assets.

Environment files:
- `.env.docker.example`: updated to use Postgres URL and comments clarifying hostnames for Docker vs local.
- `backend/.env.example`: aligned to Postgres-only configuration.

CI/CD:
- `.github/workflows/test-postgres.yml`: adds/uses Postgres for tests in CI (where applicable).

Documentation:
- Root `README.md`: updated to reference Postgres 18.1 exclusively and removed SQLite mentions.
- This document: definitive reference for the completed migration.

---

## 4. Migration Workflow

The workflows below ensure consistent behavior across local, Docker, and production (AWS RDS) environments.

### 4.1 Local (without Docker)
1. Install PostgreSQL 18.1+ locally.
2. Create database and user:
   ```
   CREATE USER clerk_user WITH PASSWORD 'clerk_password';
   CREATE DATABASE clerk_community_admin OWNER clerk_user;
   GRANT ALL PRIVILEGES ON DATABASE clerk_community_admin TO clerk_user;
   ```
3. Set `DATABASE_URL` in `.env`:
   ```
   DATABASE_URL=postgresql://clerk_user:clerk_password@localhost:5432/clerk_community_admin
   ```
4. Apply migrations:
   ```
   cd backend
   alembic upgrade head
   ```
5. Run backend and frontend as usual.

### 4.2 Docker (recommended for dev)
1. Ensure `.env` has Clerk keys and the default Docker Postgres `DATABASE_URL` is used by compose.
2. Start services:
   ```
   docker compose up --build
   ```
3. Backend waits for Postgres, applies migrations, then starts Uvicorn.
4. Access API at `http://localhost:8000` and frontend at `http://localhost:3000`.

### 4.3 Production (AWS RDS)
1. Provision AWS RDS for PostgreSQL 18.1+ in your VPC.
2. Create database and user (same as local, but on RDS instance). Enforce SSL.
3. Set `DATABASE_URL` to the RDS endpoint:
   ```
   DATABASE_URL=postgresql://clerk_user:REDACTED@<rds-endpoint>:5432/clerk_community_admin
   ```
4. Run Alembic migrations from your CI/CD runner or on container startup (ensure minimal downtime):
   ```
   cd backend && alembic upgrade head
   ```
5. Configure security groups, IAM, backups, monitoring (CloudWatch), and alarms.

---

## 5. Performance Improvements

- Concurrent writers now supported; eliminates SQLite write lock contention.
- Better query planning and indexing (e.g., btree, gin, gist) yields lower latency under load.
- Connection pooling and healthchecks improve resilience and throughput.
- JSONB support enables richer querying on semi-structured fields where applicable.

---

## 6. Troubleshooting

Common issues and fixes:

- Backend can’t connect to DB (Docker):
  - Ensure the `db` service is healthy: `docker compose ps`.
  - Verify `DATABASE_URL` uses host `db`, not `localhost`.
  - Check healthcheck logs: `docker logs clerk-app-postgres`.

- Alembic migration failures:
  - Inspect last migration scripts for Postgres-only SQL.
  - Re-run with verbose logs: `alembic upgrade head -x verbose=true`.
  - If schema drift exists, generate a new migration and apply.

- Authentication errors to RDS:
  - Confirm security group rules and that the runner/container has network access to RDS.
  - Require SSL in `DATABASE_URL` if your policy enforces it (e.g., `?sslmode=require`).

- Performance/regression concerns:
  - Add indexes for frequent query predicates.
  - Use `EXPLAIN ANALYZE` to profile slow queries.

---

## 7. Backup & Recovery

Local/Docker:
- Use `pg_dump` for logical backups:
  ```
  pg_dump -h localhost -U clerk_user -d clerk_community_admin -F c -f backup.dump
  ```
- Restore with `pg_restore`:
  ```
  createdb -h localhost -U clerk_user clerk_community_admin_restore
  pg_restore -h localhost -U clerk_user -d clerk_community_admin_restore -c backup.dump
  ```

AWS RDS:
- Enable automated backups and set a retention period.
- Use snapshots for point-in-time restore (PITR) in incident scenarios.
- Practice restores periodically to validate RTO/RPO.

---

## 8. Cost Analysis

- Development: Dockerized Postgres runs locally; cost = developer machine resources.
- Production on RDS: costs depend on instance class, storage (gp3/io2), backup retention, Multi-AZ.
- Connection pooling (e.g., PgBouncer) can reduce required instance size under spiky traffic.
- Elimination of data loss incidents reduces hidden operational costs.

---

## 9. Security Improvements

- Strong roles and grants model; application uses a least-privilege user.
- Support for encrypted connections (TLS), mandatory on RDS.
- Better auditability via Postgres logs and RDS enhanced monitoring.
- Future option: row-level security (RLS) where applicable.

---

## 10. Rollback Procedures

Rollback policy favors forward-fix; however, if necessary:
1. Stop write traffic to the application.
2. Restore latest verified backup/snapshot to a new Postgres instance.
3. Point `DATABASE_URL` to the restored instance.
4. Run Alembic migrations if needed to match the target app version.
5. Validate application smoke tests before resuming traffic.

Note: Rollback to SQLite is not supported. PostgreSQL is exclusive.

---

## 11. Next Steps

- [ ] Finalize AWS RDS provisioning and networking.
- [ ] Configure automated migrations in CI/CD for production deploys.
- [ ] Set up monitoring: CloudWatch metrics, alarms, error budgets.
- [ ] Configure backups, PITR testing, and periodic restore drills.
- [ ] Evaluate connection pooling (PgBouncer) if load requires.
- [ ] Document DBA runbooks for on-call.

---

## 12. References

- `docker-compose.yml` — Postgres service, healthchecks, backend dependency.
- `.env.docker.example` — Postgres `DATABASE_URL` examples for Docker and local.
- `backend/scripts/docker_start.py` — Wait-for-DB and Alembic orchestration.
- `backend/requirements.txt` — Includes `psycopg2`.
- `.github/workflows/test-postgres.yml` — CI reference using Postgres.
- Alembic migration history — schema definitions and changes.

---

## Conclusion

The migration to PostgreSQL 18.1 is complete for local development and Docker workflows, with production deployment to AWS RDS pending. PostgreSQL is now the single, exclusive database across all environments. This shift unlocks improved reliability, performance, and operational maturity for the Clerk Community Administration System.
