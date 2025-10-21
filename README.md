# CLERK System (Community Leadership, Events, Records & Knowledge)

A FastAPI + Next.js application that manages members, offices/terms, and generates LaTeX-based PDFs (letters, rosters, reports). Built for 1–2 concurrent users with SQLite. Local dev supports Docker or bare-metal; production target is AWS ECS Fargate with ECR and EFS.

## Technology Stack
- Backend: Python 3.13.7, FastAPI, SQLAlchemy, Alembic, Jinja2
- Frontend: Next.js 15.5.4, React 19.1.0, TypeScript, Clerk Authentication
- PDF: LaTeX via XeLaTeX (template-based with Jinja2 and custom delimiters)
- Database: SQLite
- Deployment: Docker containers, AWS ECS Fargate

## Repository Structure (key paths)
