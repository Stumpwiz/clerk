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

## File generation: Step 3C-2

The nine report-generation routes and `/api/mailing-lists/{list_id}` now require
POST, authentication, and a trusted Origin. Their old GET methods return 405
without generation or publication. Short-roster publication remains conditional
on its existing enable flag and is covered by the POST guard. Metadata and
existing-document downloads remain GET. Mailing-list View deliberately regenerates
via POST, preserving its prior behavior.

Focused synthetic tests with stubbed generation/publication verify this boundary;
this resolves the generating-GET blocker in the local implementation only. Deploy
the matching frontend/backend changes together; old generation bookmarks and GET
clients will receive 405. No live rendering or publication was validated.

Production configuration validation and secret-safe signing-key rotation remain
recovery prerequisites. Do not use `scripts/update_apprunner_env.py` unchanged.
Production services remain paused; this document does not authorize restoration.
