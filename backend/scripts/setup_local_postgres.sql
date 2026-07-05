-- PostgreSQL initialization script for the community administration application
-- This script is idempotent and can be run multiple times safely.
--
-- When used with Docker's /docker-entrypoint-initdb.d/, the database and user
-- are already created via POSTGRES_DB and POSTGRES_USER environment variables.
-- This script ensures proper permissions are set.

-- Create user only if it doesn't exist (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'clerk_user') THEN
    CREATE ROLE clerk_user LOGIN PASSWORD 'clerk_password';
  END IF;
END
$$;

-- Grant privileges on the current database to the app role
GRANT ALL PRIVILEGES ON DATABASE clerk_community_admin TO clerk_user;

-- Public schema ownership and privileges
ALTER SCHEMA public OWNER TO clerk_user;
GRANT USAGE ON SCHEMA public TO clerk_user;
GRANT CREATE ON SCHEMA public TO clerk_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO clerk_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO clerk_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO clerk_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO clerk_user;

-- Optional extensions commonly used; uncomment if needed by the app
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Done.
