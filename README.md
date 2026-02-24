# Clerk - Community Administration System

A modern web application for managing retirement community administrative bodies, offices, terms, and generating official documents.

## Features

- **Bodies Management**: Manage administrative bodies and committees
- **Offices Management**: Track committee positions and roles
- **Persons Management**: Maintain community members and residents
- **Terms Management**: Assign persons to offices with terms
- **Letters Generation**: Generate personalized welcome letters (LaTeX-based PDFs)
- **Rosters & Reports**: Generate professional rosters and reports (4 types)
  - Long Form Roster (detailed contact information)
  - Short Form Roster (condensed version)
  - Vacancies Report
  - Expiring Terms Report
- **User Management**: Clerk-based authentication with invitation system

## Tech Stack

### Frontend
- **Next.js 15** - React framework
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first CSS
- **Clerk** - Authentication and user management
- **Lucide React** - Icon library

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - SQL toolkit and ORM
- **PostgreSQL 18.1** - Production-grade relational database
- **Alembic** - Database migrations
- **psycopg2** - PostgreSQL adapter for Python
- **Jinja2** - Template engine for LaTeX documents
- **XeLaTeX** - PDF generation engine
- **Clerk API** - User management integration

## Prerequisites

- **Docker & Docker Compose** (recommended)
  - OR -
- **Node.js 20+** and **Python 3.13+**
- **PostgreSQL 18.1+** (required for all environments)
- **Clerk Account** - Sign up at [clerk.com](https://clerk.com)

> **Note**: If you have native PostgreSQL installed, configure it for **Manual** startup to avoid port conflicts with Docker PostgreSQL. See [Development Workflow](#development-workflow) below.

## Development Workflow

### First-Time Setup

If you have native PostgreSQL 18 installed on Windows, prevent port conflicts:

1. Press **Win + R**, type `services.msc`, press Enter
2. Find **"postgresql-x64-18 - PostgreSQL Server 18"**
3. Right-click → **Properties**
4. Change **Startup type** to **Manual**
5. Click **OK**

This ensures Docker PostgreSQL can use port 5432 without conflicts.

### Daily Startup

1. **Start Docker Desktop** (if not already running)
2. **Open project** in PyCharm or your preferred IDE
3. **Start the Docker stack** (in terminal):
   ```bash
   docker-compose up
   ```

   Wait for the startup message:
   ```
   *** Clerk started ***
   Database: postgresql://clerk_user:***@db:5432/clerk_community_admin
   API Docs: http://0.0.0.0:8000/docs
   ```

4. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Daily Shutdown

```bash
# Stop and remove containers
docker-compose down

# Or stop containers but keep them (faster restart)
docker-compose stop
```

### Useful Commands

```bash
# View logs in real-time
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# Restart a single service
docker-compose restart backend

# Rebuild after code changes
docker-compose up --build

# Clean restart (removes volumes/data)
docker-compose down -v
docker-compose up --build
```

## Quick Start (Docker with PostgreSQL)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd clerk-community-admin
```

### 2. Set Up Environment Variables

```bash
# Copy the example file
cp .env.docker.example .env

# Edit .env and add your Clerk credentials:
# CLERK_SECRET_KEY=sk_test_...
# CLERK_PUBLISHABLE_KEY=pk_test_...
```

### 3. Start with Docker Compose

```bash
# Start all services (PostgreSQL + Backend + Frontend)
docker-compose up --build

# Or use the convenience script
./start-docker.sh  # Linux/Mac
start-docker.bat   # Windows
```

Services will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432

### 4. Access the Application

1. Open http://localhost:3000 in your browser
2. Sign up with Clerk authentication
3. Start managing your community data!

## Quick Start (Local Development)

### 1. Set Up PostgreSQL Database

```bash
# Ensure PostgreSQL 18.1+ is installed on your system
# Create the database and user
psql -U postgres -f backend/scripts/setup_local_postgres.sql
```

This creates:
- Database: `clerk_community_admin`
- User: `clerk_user`
- Password: `clerk_password`

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variable
export DATABASE_URL=postgresql://clerk_user:clerk_password@localhost:5432/clerk_community_admin

# Run migrations
alembic upgrade head

# Start the backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local.backup with your Clerk keys
cp .env.local.backup.example .env.local.backup
# Edit .env.local.backup and add your credentials

# Start the frontend
npm run dev
```

## Architecture

### Database Architecture
- **Production**: AWS RDS PostgreSQL 18.1
- **Local Development**: Docker PostgreSQL or native PostgreSQL
- **Migrations**: Alembic-based schema versioning
- **Backup**: Automated daily backups with 7-day retention

### Deployment Architecture
- **Frontend**: AWS App Runner (containerized Next.js)
- **Backend**: AWS App Runner (containerized FastAPI)
- **Database**: AWS RDS PostgreSQL (Multi-AZ optional)
- **Authentication**: Clerk (managed service)
- **File Storage**: Container volumes (letters & reports)

## Documentation

- **[Database Migration Guide](docs/database-migration-complete.md)** - Complete migration documentation
- **[AWS Deployment Guide](docs/aws-deployment-context.md)** - Production deployment instructions
- **[Backup & Restore Guide](docs/backup-and-restore-guide.md)** - Backup and recovery procedures
- **[Backend README](backend/README.md)** - Backend setup and API documentation

## Project Structure

```
clerk-community-admin/
├── backend/                    # FastAPI backend
│   ├── app/                   # Application code
│   ├── alembic/               # Database migrations
│   ├── scripts/               # Utility scripts
│   ├── tests/                 # Test suite
│   └── Dockerfile
├── frontend/                  # Next.js frontend
│   ├── src/                   # React components
│   └── Dockerfile
├── docs/                      # Documentation
├── scripts/                   # Deployment scripts
└── docker-compose.yml         # Docker orchestration
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [documentation](docs/)
- Review [Clerk documentation](https://clerk.com/docs) for auth-related questions
