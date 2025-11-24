# Backend - FastAPI Application

This directory contains the FastAPI backend for the Retirement Community Management System.

## Database Configuration (PostgreSQL)

> Note: This application requires PostgreSQL 18.1 or later. SQLite is not supported.

The backend uses PostgreSQL for all environments (development, staging, production).

- Configure the database using the `DATABASE_URL` environment variable.
- The application auto-detects the dialect based on the URL and configures SQLAlchemy accordingly.

Examples (PostgreSQL):

- `DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST:PORT/DBNAME`

See `.env.example` in this folder for a ready-to-copy template.

### Install dependencies

```
pip install -r requirements.txt
```

Note: PostgreSQL requires the driver. We use `psycopg2-binary` which is already included in `requirements.txt`.

### PostgreSQL 18.1 — Local installation

#### Install PostgreSQL 18.1 locally
- Windows/macOS/Linux installers: https://www.postgresql.org/download/
- Recommended settings for local dev:
  - Port: 5432
  - Superuser: postgres (with a password you remember)
  - Ensure `psql` is on your PATH

#### Configure environment
- Copy `.env.example` to `backend/.env` and set either a composite URL or individual parts:
  - Option A: Composite URL
    - `DATABASE_URL=postgresql://clerk_user:clerk_password@localhost:5432/clerk_community_admin`
  - Option B: Individual parts (auto‑assembled by the app/alembic):
    - `POSTGRES_HOST=localhost`
    - `POSTGRES_PORT=5432`
    - `POSTGRES_DB=clerk_community_admin`
    - `POSTGRES_USER=clerk_user`
    - `POSTGRES_PASSWORD=clerk_password`

#### One‑command local setup
- Linux/macOS:
  ```bash
  bash backend/scripts/local_migrate_to_postgres.sh
  ```
- Windows (PowerShell or Command Prompt):
  ```bat
  backend\scripts\local_migrate_to_postgres.bat
  ```

What the script does:
- Verifies PostgreSQL is running (`pg_isready`/`psql`)
- Creates the database `clerk_community_admin` and role `clerk_user` if they don’t exist
- Grants necessary privileges and sets public schema ownership
- Exports `DATABASE_URL` for the current session
- Resets Alembic state safely and runs migrations to `head`
- Validates the setup by running `backend/scripts/test_models.py`

Notes:
- The scripts default to `clerk_community_admin`/`clerk_user`/`clerk_password`. Override via env vars if needed.
- To auto‑migrate data without prompt, set `AUTO_MIGRATE_DATA=yes`.

#### Manual setup using SQL (optional)
If you prefer to run SQL manually, see `backend/scripts/setup_local_postgres.sql` as a reference. Example commands:
```sql
-- Run as a superuser (postgres)
CREATE ROLE clerk_user LOGIN PASSWORD 'clerk_password';
CREATE DATABASE clerk_community_admin OWNER clerk_user;
GRANT ALL PRIVILEGES ON DATABASE clerk_community_admin TO clerk_user;

-- Connect to the new DB, then:
ALTER SCHEMA public OWNER TO clerk_user;
GRANT USAGE, CREATE ON SCHEMA public TO clerk_user;
-- Optional extensions:
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

#### Run Alembic migrations
- From the `backend` directory (or use `-c backend/alembic.ini` from project root):
  ```bash
  alembic upgrade head
  ```
Alembic resolves `DATABASE_URL` from environment or assembles from `POSTGRES_*` via `app.config.get_database_url()`.

Alembic reads the connection string from the `DATABASE_URL` environment variable (falls back to the `sqlalchemy.url` value in `alembic.ini` if not provided). The Alembic environment also loads variables from a local `.env` if present.

### Running the backend locally

```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Ensure `DATABASE_URL` is set in your environment or `.env` before running.

### Docker and Docker Compose

This backend runs against PostgreSQL inside Docker. The images embed a startup orchestrator that:

Startup sequence inside container:
1. `backend/scripts/docker_start.py` resolves `DATABASE_URL` (or POSTGRES_* envs)
2. Calls `backend/scripts/wait_for_db.py` to poll until the DB accepts connections
3. Runs `alembic upgrade head` to apply pending migrations
4. Starts `uvicorn app.main:app`

Notes:
- You can disable the auto‑migrate step by setting `DISABLE_AUTO_MIGRATE=true` on the backend service.

#### Compose for PostgreSQL

Use the provided `docker-compose.postgres.yml` for a local stack with PostgreSQL + backend + frontend.

Run:
```
docker-compose -f docker-compose.postgres.yml up --build
```

What it does:
- Spins up a `postgres:18.1` service with a healthcheck (`pg_isready`)
- Mounts `backend/scripts/setup_local_postgres.sql` to initialize role/db on first run
- Builds and starts the backend image which, on start, waits for Postgres, migrates with Alembic, and then starts the API
- Starts the frontend and waits until backend is healthy (backend healthcheck assumes `/health` endpoint)

Environment used by backend in this compose file:
- `DATABASE_URL=postgresql://clerk_user:clerk_password@db:5432/clerk_community_admin`

Ports:
- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- Postgres: localhost:5432


#### Manual healthcheck considerations

- The backend compose files include a healthcheck that probes `http://localhost:8000/health`. Ensure your FastAPI app exposes this endpoint. If not, either add a simple health route or remove/adjust the healthcheck.

#### Verify migrations ran automatically

Inspect logs of the backend container; you should see entries like:
- `[wait-for-db] Database is ready ...`
- `Running upgrade ...` from Alembic
- `Uvicorn running on http://0.0.0.0:8000`

You can also verify DB objects inside the Postgres container:
```
docker exec -it clerk-app-postgres psql -U clerk_user -d clerk_community_admin -c "\\dt"
docker exec -it clerk-app-postgres psql -U clerk_user -d clerk_community_admin -c "\\dv report_record"
```

## Directory Structure

### Database helper scripts

Two helper scripts are provided under `backend/scripts` to streamline database setup and container startup:

1) `init_db.py` — initialize and migrate the database
- Purpose: Create tables (if needed), run Alembic migrations, and optionally seed initial data.
- It reads `DATABASE_URL` from `.env` or the environment via the app configuration.
- Typical usage:
  - Create tables only (no migrations):
    ```
    python backend/scripts/init_db.py --create --no-migrate
    ```
  - Run migrations to latest (default action if nothing is specified):
    ```
    python backend/scripts/init_db.py --migrate
    ```
  - Do everything (create + migrate + seed):
    ```
    python backend/scripts/init_db.py --create --migrate --seed
    ```

2) `wait_for_db.py` — wait for the database to be ready
- Purpose: In container environments, ensure PostgreSQL is reachable before starting the API.
- Behavior: Retries `SELECT 1` with exponential backoff until success or timeout.
- Usage examples:
  - Wait up to 120s for DB:
    ```
    python backend/scripts/wait_for_db.py --timeout 120
    ```
  - Wait, then run Alembic followed by the API server:
    ```
    python backend/scripts/wait_for_db.py -- alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```

### How Docker Compose uses these scripts

`docker-compose.yml` is configured to wait for the `db` service to be healthy and then, inside the `backend` container, run:

```
python backend/scripts/wait_for_db.py --timeout 120 -- alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

This guarantees the backend only starts after PostgreSQL is accepting connections and the database schema is migrated to the latest Alembic revision.


## PostgreSQL environments

- PostgreSQL is required for all environments (development, staging, production).
- Provide `DATABASE_URL` or `POSTGRES_*` env vars; the app assembles the URL automatically if needed.

## Troubleshooting

- psql not found / command not recognized
  - Ensure PostgreSQL client tools are installed and on PATH. On macOS with Homebrew: `brew install libpq && brew link --force libpq`.

- Cannot connect to PostgreSQL / server not running
  - Start the service: Windows Services app; macOS (Homebrew): `brew services start postgresql`; Linux: `sudo systemctl start postgresql`.
  - Verify with: `pg_isready -h localhost -p 5432`.

- Authentication failed for user
  - Check `POSTGRES_SUPERUSER`/`POSTGRES_SUPERPASS` used by scripts for initial setup.
  - If using password auth, ensure `pg_hba.conf` allows local connections (md5/scram‑sha‑256) and you set the right password.

- Role/database already exists errors when running SQL
  - Safe to ignore if created previously. The wrapper scripts check existence before creating.

- Alembic complains about heads or `alembic_version`
  - Run: `python backend/scripts/reset_alembic.py` and then `alembic upgrade head`.

- Backend container starts but migrations did not apply
  - Ensure `DATABASE_URL` points to the Postgres service (e.g., `db` hostname inside compose)
  - Check environment variable `DISABLE_AUTO_MIGRATE` is not set to true
  - Review backend logs for Alembic errors

- Backend healthcheck failing
  - Confirm a `/health` endpoint exists and returns 200 OK
  - Temporarily remove or relax the healthcheck if you need to diagnose startup

- Type mismatch on foreign keys
  - Ensure you are on the latest code. `Office.office_body_id` now uses `Integer` to match `Body.body_id`.

- Data migration errors (FK violations or duplicates)
  - Try `--force-truncate` on the migration script against a clean target DB.
  - Confirm the target schema matches the baseline migration.

- Windows quoting/path issues
  - Use double quotes around paths; prefer the provided `.bat` script.

- macOS with Homebrew PostgreSQL
  - Ensure your PATH includes the keg: `export PATH="/opt/homebrew/opt/libpq/bin:$PATH"`.

## Backups and Restores (PostgreSQL and AWS RDS)

For detailed procedures, see `docs/backup-restore-guide.md`.

Quick commands:
- Local backup (auto-detects DB from `DATABASE_URL`):
  ```
  python backend/scripts/backup_database.py
  ```
- Local restore with confirmation prompts:
  ```
  python backend/scripts/restore_database.py --backup backend/backups/<your-backup-file>
  ```
- Create an RDS on-demand snapshot (AWS CLI):
  ```
  bash scripts/rds-create-snapshot.sh --db-instance-id <rds-instance-id>
  ```
- Verify a snapshot (optionally restore temp instance and probe):
  ```
  bash scripts/rds-verify-backup.sh --snapshot-id <snapshot-id> --probe --cleanup
  ```
