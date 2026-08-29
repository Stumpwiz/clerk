# Changelog

## Unreleased

### Added

- In-application Help with task links and an authenticated printable Administrative Assistant guide.

## 2.0.0

### Changed

- Replaced hosted third-party authentication with local database-backed authentication.
- Added secure HTTP-only signed cookie sessions.
- Enforced authentication in the backend.
- Standardized frontend API configuration on `NEXT_PUBLIC_API_URL`.

### Added

- Local login and logout.
- Local Users page administration:
  - List Users
  - Add User
  - Edit User
  - Activate and deactivate users
  - Administrator Reset Password
- Profile page self-service Change Password.
- First-user bootstrap script: `backend/scripts/create_local_user.py`.
- Local authentication architecture documentation.

### Removed

- Hosted identity-provider runtime dependency.
- Hosted identity-provider runtime, middleware, account-provisioning workflow, and environment-variable requirements.

### Deployment

- Production deployment verified with local authentication.
- Production requires `DATABASE_URL`, `AUTH_SECRET_KEY`, `CORS_ORIGINS`, local session-cookie settings, and frontend `NEXT_PUBLIC_API_URL`.
