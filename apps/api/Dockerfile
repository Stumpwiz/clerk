# API Dockerfile (FastAPI + XeLaTeX)
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install XeLaTeX and minimal TeX packages + curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-xetex texlive-latex-recommended texlive-fonts-recommended texlive-latex-extra \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY . /app

# Ensure data/output dirs exist
RUN mkdir -p /app/data /app/files_letters /app/files_roster_reports

# Copy and enable startup script
RUN chmod +x /app/start.sh

# Defaults suitable for container
ENV DATABASE_URL=sqlite:////app/data/community_admin.db \
    XELATEX_PATH=xelatex

EXPOSE 8000

CMD ["/app/start.sh"]
