# Backend Dockerfile for the community administration application
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies including LaTeX and curl (for healthchecks)
RUN apt-get update && apt-get install -y \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-latex-extra \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for generated files
RUN mkdir -p files_letters files_roster_reports

# Make helper scripts runnable (optional; we typically invoke via `python`)
RUN chmod +x scripts/*.py || true

# Expose port
EXPOSE 8000

# Default command: orchestrated startup that waits for DB (if Postgres),
# runs Alembic migrations, then starts Uvicorn.
# Note: scripts are copied to /app/scripts, not /app/backend/scripts
CMD ["python", "scripts/docker_start.py"]
