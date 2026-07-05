# Retirement Community Management System - Frontend

Next.js 15 frontend application with TypeScript, Tailwind CSS, and local authentication.

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env.local
```

Set the backend API URL:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

`NEXT_PUBLIC_API_URL` is the only frontend API base URL variable. Browser requests use this value when calling the FastAPI backend.

### 3. Run Locally

```bash
npm run dev
```

Open `http://localhost:3000/local-login` and sign in with a local user created by the backend bootstrap script or the Users page.

## Authentication

Authentication is local and backend-enforced.

- The login page posts email and password to the backend.
- The backend sets a signed HTTP-only session cookie.
- Frontend API calls include credentials so the browser sends the cookie.
- `frontend/lib/auth.ts` is the frontend auth service boundary.
- Logout clears the backend session cookie and returns the user to `/local-login`.
- The Users page manages local application users.
- The Profile page supports self-service password changes.

No third-party identity-provider frontend variables are required.

## Production Build

Set the production API URL before building:

```bash
NEXT_PUBLIC_API_URL=https://api.example.com npm run build
```

Then start the built frontend:

```bash
npm run start
```

For container builds, pass `NEXT_PUBLIC_API_URL` as the Docker build argument used by the frontend Dockerfile.
