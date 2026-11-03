# Cookie and Origin configuration

`CLERK_ENV` defaults to `production`. Production startup requires:

- `SESSION_COOKIE_SECURE=true` and `SESSION_COOKIE_SAMESITE=lax`.
- An explicit, nonempty `AUTH_SECRET_KEY` that is not a known development
  placeholder. Provision a cryptographically random key; validation cannot
  establish randomness. Never put its value in source or logs.
- Explicit `CORS_ORIGINS`: a JSON array or comma-separated list of exact HTTPS
  frontend origins, with no path, trailing slash, wildcard, query, or fragment.
  Select the actual restoration frontend; repository defaults are not evidence
  of current production use.

Cookie creation and deletion use HttpOnly, host-only scope and Path `/`.
The same configured allowlist governs credentialed CORS and Origin enforcement.
POST, PUT, PATCH and DELETE require exactly one valid, approved Origin header,
including login and logout. Missing or rejected origins receive 403 before
route execution. OPTIONS preflight and GET requests remain available.

For local development explicitly set `CLERK_ENV=development`; for isolated
tests use `CLERK_ENV=test`. Non-production modes permit HTTP origins and
non-Secure cookies but do not disable Origin enforcement. Browser fetch sends
Origin on mutations. Command-line mutation clients must supply an approved
Origin as well as satisfy normal authentication and authorization.

## Restoration blocker: Step 3C-2

File-generating GET routes in `app/routers/reports.py` and
`app/routers/mailing_lists.py` remain unchanged and are not protected by the
unsafe-method guard. Short-roster generation can also publish to IONOS when
enabled. Step 3C-1 alone is not sufficient for restoration. Step 3C-2 must cover
these side effects and their frontend callers while preserving read-only
metadata and existing-file downloads. Production services remain paused;
this document does not authorize restoration.
