# CLERK System (Community Leadership, Events, Records & Knowledge)

CLERK is a small, production-ready system for community administration. It manages people and offices/terms, enforces business rules (including max incumbents), and generates high-quality PDFs (letters, rosters, reports) by rendering Jinja2-templated LaTeX and compiling with XeLaTeX. The target audience is a small admin team (1–2 concurrent users). Backend is FastAPI + SQLite; frontend is Next.js with Clerk authentication. Local dev supports Docker Compose or bare metal; production targets AWS ECS Fargate.

## Key features
- Member and office/term management (CRUD)
- PDF generation:
  - Letters, rosters, and reports via Jinja2 → LaTeX → XeLaTeX
  - Custom LaTeX-friendly delimiters and full LaTeX escaping
  - Logo support and predictable output directories
- Clerk-protected routes on the web and API endpoints for authenticated operations
- Health and diagnostics endpoints for monitoring
- Robust ordering rules for rosters; accurate vacancy reporting
- Dockerized dev and deploy; CI validates builds; CD publishes to ECR and can trigger ECS deploys

## Technology stack
- Backend: Python 3.13.7, FastAPI, SQLAlchemy, Alembic, Jinja2; SQLite database file
- Frontend: Next.js 15.5.4, React 19.1.0, TypeScript; Clerk authentication
- PDF toolchain: XeLaTeX (installed in API container)
- Infrastructure: Dockerfiles for API/Web, docker-compose for local dev, GitHub Actions CI/CD, AWS ECS Fargate + ECR + EFS + ALB

## Repository structure (high level)
```
.
├─ apps/
│  ├─ api/                    # FastAPI service, XeLaTeX, PDF output dirs
│  └─ web/                    # Next.js app with Clerk auth; proxies to API
├─ deploy/                    # Infra/deployment helpers (if present)
├─ docs/                      # Additional documentation (ci-cd, licenses)
├─ docker-compose.yml         # Local dev for API and Web
├─ LICENSE                    # Apache-2.0 for code
├─ README.md                  # This file
└─ main.py                    # (Root entrypoint or tooling; may delegate to apps/api)
```

## Quick start
Choose one of the following options.

### Option A: Docker Compose (recommended)
Prereqs: Docker Desktop with Compose v2.

Commands:
```bash
# From repo root
docker compose up --build
```

What you get:
- API at http://localhost:8000
- Web at http://localhost:3000
- Bind-mounted SQLite database file at apps/api/community_admin.db
- Named volumes for PDF outputs:
  - apps/api/files_letters → volume letters_data
  - apps/api/files_roster_reports → volume roster_data
- API container security hardening: read-only root FS with tmpfs /tmp; healthchecks

Stopping and cleanup:
```bash
docker compose down
# To remove volumes as well:
docker compose down -v
```

Notes:
- docker-compose.yml sets safe local defaults for env vars (see Environment variables).
- XeLaTeX is already installed in the API image; no host install needed for Compose.

### Option B: Bare metal (no containers)

Backend API
1) Create and activate a virtualenv:
```bash
python -m venv .venv
. .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
```
2) Install dependencies:
```bash
pip install -r apps/api/requirements.txt
```
3) Configure environment (.env or shell):
```
DATABASE_URL=sqlite:////app/data/community_admin.db
XELATEX_PATH=xelatex
ALLOWED_ORIGINS=["http://localhost:3000"]
# Clerk verification settings as needed
```
4) Run the API with uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir apps/api
```

Frontend Web
1) Install Node deps:
```bash
cd apps/web
npm ci
```
2) Configure env (apps/web/.env.local):
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
# Clerk publishable key, e.g.:
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_XXXXXXXXXXXXXXXX
```
3) Run the dev server:
```bash
npm run dev
```

## Environment variables
Docker Compose provides sensible defaults for local development. For production, set these explicitly.

Backend (API)
- DATABASE_URL: sqlite:////app/data/community_admin.db (SQLite filepath inside container)
- XELATEX_PATH: xelatex (binary available in API image)
- ALLOWED_ORIGINS: JSON array of allowed origins for CORS, e.g. ["https://your-domain"]
- Clerk verification settings: set according to your auth strategy (e.g., JWKS, issuer)

Frontend (Web)
- NEXT_PUBLIC_API_BASE_URL: Base URL of API, e.g. https://api.your-domain
- NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: Clerk publishable key for the browser

## Health and diagnostics
- GET /health and /health/: liveness probes for the API service
- GET /api/v1/db-check: verifies DB connectivity/migrations
- Protected endpoints (require Clerk-authenticated requests):
  - GET /api/v1/me
  - GET /api/v1/protected

## PDF generation
- Templates rendered via Jinja2 with LaTeX-friendly delimiters:
  - Variables: \VAR{name}
  - Blocks: \BLOCK{...}
  - Comments: %{{...}}  (written in code as %{...})
- All interpolated content is LaTeX-escaped.
- Logo path used in templates: ../static/logo.jpg
- Output directories (persisted):
  - apps/api/files_letters/
  - apps/api/files_roster_reports/
- XeLaTeX is installed in the API image. For bare-metal runs, ensure XeLaTeX is installed and XELATEX_PATH is resolvable on PATH.

## Database and migrations
- SQLite database file path (container): /app/data/community_admin.db
  - In Compose: bound to apps/api/community_admin.db on the host.
- Alembic handles migrations; ensure you run migrations as part of your deploy/release process.
- Business rule: Office.max_incumbents is a nullable integer.
  - NULL or 0 → unlimited incumbents
  - 1 → single-incumbent office
  - Overlap rules on terms are enforced accordingly.

## Rosters and Reports
- Canonical ordering for rosters:
  1) Body precedence ascending
  2) Office precedence ascending (NULL last)
  3) Person first name (case-insensitive)
  4) Person last name (case-insensitive)
- Vacancies report: lists active terms where the incumbent has person.first = "(Vacant)" and preserves SQL ordering. Avoid template-side re-sorting.

## Authentication and authorization
- Authentication: Clerk.
- Authorization: enforced by the application using DB-backed rules (briefly: ensure the authenticated user has appropriate roles/permissions for protected operations). The web app calls Clerk-protected API routes via middleware-proxied requests.

## CI/CD overview
- CI (GitHub Actions): builds API and Web, runs basic checks/tests, validates Dockerfiles. See .github/workflows/ci.yml.
- CD (GitHub Actions): builds and pushes Docker images to ECR via GitHub OIDC and can force ECS redeploys. See .github/workflows/cd-ecr.yml.
- Enable OIDC:
  - Create an AWS IAM role with GitHub OIDC trust and grant minimal ECR (and optional ECS) permissions.
  - Add repository secrets/variables (AWS_ROLE_TO_ASSUME, AWS_REGION, ECR repos, optional ECS cluster/service names).
  - Detailed steps live in docs/ci-cd.md.

## AWS deployment (high level)
- ALB path routing:
  - / → Web (Next.js)
  - /api/* and /health → API (FastAPI)
- EFS mounts in ECS tasks:
  - /app/data for SQLite file
  - /app/files_letters and /app/files_roster_reports for PDF outputs
- ECS task definitions pull ECR images and set required environment variables.
- Security hardening: read-only root filesystem with tmpfs /tmp for the API container.

## Post-deploy verification checklist
- Check API health: GET https://your-domain/health
- Check DB connectivity: GET https://your-domain/api/v1/db-check
- Verify protected route requires auth: GET https://your-domain/api/v1/protected (expect 401/403 when logged out)
- Sign in via Clerk and hit /api/v1/me
- Generate PDFs (letters/rosters/reports) and confirm files appear in mounted EFS paths

## Troubleshooting
- PDF compilation issues:
  - Ensure XeLaTeX is installed (bare metal) and XELATEX_PATH resolves.
  - Check that template variables are properly escaped and delimiters match (\\VAR, \\BLOCK, %{}).
- Permissions on EFS:
  - Verify the task execution role and access point/UID/GID settings allow writing to /app/data and PDF output dirs.
- CORS errors:
  - Confirm ALLOWED_ORIGINS includes your web origin.
  - Ensure NEXT_PUBLIC_API_BASE_URL points to the correct public API URL.
- Healthcheck failures:
  - Check container logs; validate /health and /api/v1/db-check.

## Contributing and next steps
- Add tests over time (API and Web). Wire into CI (pytest, Playwright, etc.).
- Linting and type checks (e.g., ruff/flake8, mypy, eslint, tsc).
- Enable Dependabot for dependency updates.
- Consider staging and production environments with separate configurations and tags.

## Notes on assumptions
- Protected endpoints /api/v1/me and /api/v1/protected are documented per design; if names differ in your build, adjust accordingly.
- Root main.py presence varies by setup; refer to apps/api as the primary API app directory.

## License
- Code: Apache License 2.0 — see LICENSE
- Documentation: CC BY 4.0 — see docs/LICENSE-docs
- Logo/branding: All Rights Reserved

END OF README
