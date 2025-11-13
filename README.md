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
- **SQLite** - Database (can be swapped for PostgreSQL)
- **Jinja2** - Template engine for LaTeX documents
- **XeLaTeX** - PDF generation engine
- **Clerk API** - User management integration

## Prerequisites

- **Docker & Docker Compose** (recommended)
  - OR -
- **Node.js 20+** and **Python 3.13+**
- **Clerk Account** - Sign up at [clerk.com](https://clerk.com)

## Quick Start (Docker)

### 1. Clone the Repository
