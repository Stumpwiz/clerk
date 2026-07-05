# Community Administration System

A web application for managing retirement community administrative bodies, offices, terms, user accounts, and official documents.

## Features

- **Bodies Management**: Manage administrative bodies and committees.
- **Offices Management**: Track committee positions and roles.
- **Persons Management**: Maintain community members and residents.
- **Terms Management**: Assign persons to offices with terms.
- **Letters Generation**: Generate personalized welcome letters as LaTeX-based PDFs.
- **Rosters & Reports**: Generate long-form rosters, short-form rosters, vacancy reports, expiring-term reports, and email lists.
- **Local Authentication**: Secure local login with HTTP-only signed cookies and backend-enforced protected routes.
- **User Management**: List users, add users, edit display names and active status, change your own password, and reset another user's password.

## Tech Stack

### Frontend

- **Next.js 15**
- **TypeScript**
- **Tailwind CSS**
- **Lucide React**

### Backend

- **FastAPI**
- **SQLAlchemy**
- **PostgreSQL 18.1+**
- **Alembic**
- **psycopg2**
- **Jinja2**
- **XeLaTeX**

## Authentication Overview

The application uses local authentication backed by the `users` table.

- Email is the only login identifier.
- Passwords are hashed by the backend and plaintext passwords are never stored.
- Successful login issues a signed HTTP-only session cookie.
- Logout clears the session cookie.
- Backend routers enforce authentication before returning protected application data.
- Inactive users cannot log in.
- There are no roles or permissions; every active authenticated user is trusted to use the administrative application.

See [Local Authentication Architecture](docs/authentication_architecture.md) for the full login, logout, user lifecycle, password management, and deployment model.

## Required Environment Variables

### Backend

Required:

- `DATABASE_URL`: PostgreSQL connection string.
- `AUTH_SECRET_KEY`: high-entropy secret used to sign session cookies.
- `CORS_ORIGINS`: comma-separated list of allowed frontend origins.

Recommended:

- `SESSION_COOKIE_NAME`: defaults to `clerk_session` for continuity with existing deployments.
- `SESSION_COOKIE_SECURE`: set to `true` for HTTPS production.
- `SESSION_COOKIE_SAMESITE`: usually `lax`; review for cross-site frontend/backend deployments.
- `SESSION_TTL_SECONDS`: signed session lifetime in seconds.
- `DEBUG`: set to `false` in production.

### Frontend

- `NEXT_PUBLIC_API_URL`: browser-visible backend API base URL.

No third-party identity-provider environment variables are required.

## Local Development Setup

### 1. Prerequisites

- Node.js 20+
- Python 3.13+
- PostgreSQL 18.1+
- XeLaTeX for PDF generation

If you use a local PostgreSQL service and Docker on the same machine, make sure only one PostgreSQL server is bound to port `5432`.

### 2. Configure PostgreSQL

Create the local database and user:

```bash
psql -U postgres -f backend/scripts/setup_local_postgres.sql
```

Default local database values:

- Database: `clerk_community_admin`
- User: `clerk_user`
- Password: `clerk_password`

### 3. Configure Backend

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set at least:

```bash
# Set DATABASE_URL to your PostgreSQL database URL.
AUTH_SECRET_KEY=replace-with-a-local-development-secret
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=lax
```

Install and migrate:

```bash
cd backend
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

Create the first local administrator:

```bash
python scripts/create_local_user.py
```

The script prompts for email, display name, password, and password confirmation. It creates an active local user with a hashed password.

Start the backend:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Configure Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
```

Edit `frontend/.env.local` if needed:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the frontend:

```bash
npm run dev
```

### 5. Authenticate Locally

1. Open `http://localhost:3000/local-login`.
2. Sign in with the local administrator created by `backend/scripts/create_local_user.py`.
3. Confirm the dashboard loads.
4. Use the Users page to add and maintain additional local users.

## Deployment Requirements

Before deploying:

1. Set backend environment variables:
   - `DATABASE_URL`
   - `AUTH_SECRET_KEY`
   - `CORS_ORIGINS`
   - `SESSION_COOKIE_SECURE=true`
   - `SESSION_COOKIE_SAMESITE=lax` or the value required by your frontend/backend domain topology
   - `SESSION_TTL_SECONDS`
   - `DEBUG=false`
2. Set frontend environment variables:
   - `NEXT_PUBLIC_API_URL`
3. Run Alembic migrations against the production PostgreSQL database.
4. Bootstrap the first local administrator if the target database has no active users.
5. Confirm the production frontend origin is present in `CORS_ORIGINS`.

After deploying:

1. Sign in through `/local-login`.
2. Confirm dashboard access, logout, and refresh behavior.
3. Confirm active users can log in and inactive users cannot.
4. Verify Add User, Edit User, Change Password, and Administrator Reset Password.

## Architecture

### Database

- **Production**: AWS RDS PostgreSQL 18.1+
- **Local Development**: Local or containerized PostgreSQL
- **Migrations**: Alembic
- **Backups**: PostgreSQL logical backups and AWS RDS snapshots

### Deployment

- **Frontend**: AWS App Runner containerized Next.js
- **Backend**: AWS App Runner containerized FastAPI
- **Database**: AWS RDS PostgreSQL
- **Authentication**: Local signed HTTP-only cookies
- **File Storage**: Generated letter and report directories

## Documentation

- [Local Authentication Architecture](docs/authentication_architecture.md)
- [Database Migration Guide](docs/database-migration-complete.md)
- [CORS Configuration Guide](docs/cors-configuration.md)
- [Backup & Restore Guide](docs/backup-and-restore-guide.md)
- [Report Registry](docs/report_registry.md)
- [Backend README](backend/README.md)
- [Frontend README](frontend/README.md)
- [Changelog](CHANGELOG.md)

## Local Development Guardrails

To reduce the chance of committing secrets, this repository includes secret-scanning guardrails that run both locally and in GitHub Actions.

### Local Pre-commit Hook

1. Install `gitleaks`.
2. Configure the repo-local hooks path:

   ```bash
   git config core.hooksPath .githooks
   ```

Once enabled, `gitleaks` scans staged changes for secrets before every commit using `.gitleaks.toml`.

### GitHub Actions CI

Push and pull request events to `master` are scanned for secrets using the same `.gitleaks.toml` rules.

## Project Structure

```text
clerk-community-admin/
├── backend/                    # FastAPI backend
│   ├── app/                    # Application code
│   ├── alembic/                # Database migrations
│   ├── scripts/                # Utility scripts
│   ├── tests/                  # Test suite
│   └── Dockerfile
├── frontend/                   # Next.js frontend
│   ├── app/                    # App Router pages
│   ├── components/             # Shared UI components
│   ├── lib/                    # Frontend API/auth helpers
│   └── Dockerfile
├── docs/                       # Documentation
└── scripts/                    # Deployment and operations scripts
```

## Contributing

Contributions can't be accommodated at this time.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Support

For issues and questions:

- Check the documentation in [docs/](docs/).
- Check local authentication endpoints under `/api/auth`.
- Review backend logs for authentication, database, or CORS failures.
