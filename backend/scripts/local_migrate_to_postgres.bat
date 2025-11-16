@echo off
REM local_migrate_to_postgres.bat — Set up local PostgreSQL and migrate from SQLite (Windows)
SETLOCAL ENABLEDELAYEDEXPANSION

REM Configuration (override by setting env vars before running)
IF NOT DEFINED POSTGRES_HOST SET POSTGRES_HOST=localhost
IF NOT DEFINED POSTGRES_PORT SET POSTGRES_PORT=5432
IF NOT DEFINED POSTGRES_SUPERUSER SET POSTGRES_SUPERUSER=postgres
REM Optional superuser password for non-trust auth
IF NOT DEFINED POSTGRES_SUPERPASS SET POSTGRES_SUPERPASS=
IF NOT DEFINED POSTGRES_DB SET POSTGRES_DB=clerk_community_admin
IF NOT DEFINED POSTGRES_USER SET POSTGRES_USER=clerk_user
IF NOT DEFINED POSTGRES_PASSWORD SET POSTGRES_PASSWORD=clerk_password

REM Optional: SQLite source for data migration
IF NOT DEFINED DATABASE_URL_SQLITE SET DATABASE_URL_SQLITE=sqlite:///./backend/instance/community_admin.db

REM Behavior flags: ask|yes|no
IF NOT DEFINED AUTO_MIGRATE_DATA SET AUTO_MIGRATE_DATA=ask

SET ROOT_DIR=%~dp0..\..
FOR %%I IN ("%ROOT_DIR%") DO SET ROOT_DIR=%%~fI
SET BACKEND_DIR=%ROOT_DIR%\backend

REM Ensure required commands exist
where psql >NUL 2>&1
IF ERRORLEVEL 1 (
  echo [ERROR] psql not found on PATH. Install PostgreSQL client tools. & EXIT /B 1
)

where python >NUL 2>&1
IF ERRORLEVEL 1 (
  echo [ERROR] python not found on PATH. Install Python 3. & EXIT /B 1
)

where alembic >NUL 2>&1
IF ERRORLEVEL 1 (
  echo [ERROR] alembic not found on PATH. Activate your Python env and install requirements. & EXIT /B 1
)

REM Test connection by listing databases
SET PGPASSWORD=%POSTGRES_SUPERPASS%
psql -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_SUPERUSER% -tAc "SELECT 1" >NUL 2>&1
IF ERRORLEVEL 1 (
  echo [ERROR] Cannot connect to PostgreSQL at %POSTGRES_HOST%:%POSTGRES_PORT% as %POSTGRES_SUPERUSER%. Ensure the server is running and credentials are correct.
  EXIT /B 1
)

REM Create role if missing
FOR /F "usebackq delims=" %%R IN (`psql -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_SUPERUSER% -tAc "SELECT 1 FROM pg_roles WHERE rolname='%POSTGRES_USER%'"`) DO SET ROLE_EXISTS=%%R
IF NOT "%ROLE_EXISTS%"=="1" (
  echo [INFO] Creating role %POSTGRES_USER%...
  psql -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_SUPERUSER% -v ON_ERROR_STOP=1 -c "CREATE ROLE \"%POSTGRES_USER%\" LOGIN PASSWORD '%POSTGRES_PASSWORD%';" || EXIT /B 1
) ELSE (
  echo [INFO] Role %POSTGRES_USER% already exists.
)

REM Create database if missing
FOR /F "usebackq delims=" %%D IN (`psql -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_SUPERUSER% -tAc "SELECT 1 FROM pg_database WHERE datname='%POSTGRES_DB%'"`) DO SET DB_EXISTS=%%D
IF NOT "%DB_EXISTS%"=="1" (
  echo [INFO] Creating database %POSTGRES_DB% owned by %POSTGRES_USER%...
  psql -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_SUPERUSER% -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"%POSTGRES_DB%\" OWNER \"%POSTGRES_USER%\";" || EXIT /B 1
) ELSE (
  echo [INFO] Database %POSTGRES_DB% already exists.
)

REM Grants and schema ownership
echo [INFO] Granting privileges and setting schema ownership...
psql -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_SUPERUSER% -d %POSTGRES_DB% -v ON_ERROR_STOP=1 -c "GRANT ALL PRIVILEGES ON DATABASE \"%POSTGRES_DB%\" TO \"%POSTGRES_USER%\";" || EXIT /B 1
psql -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_SUPERUSER% -d %POSTGRES_DB% -v ON_ERROR_STOP=1 -c "ALTER SCHEMA public OWNER TO \"%POSTGRES_USER%\";" || EXIT /B 1
psql -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_SUPERUSER% -d %POSTGRES_DB% -v ON_ERROR_STOP=1 -c "GRANT USAGE, CREATE ON SCHEMA public TO \"%POSTGRES_USER%\";" || EXIT /B 1

REM Optional extensions (commented out)
REM psql -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_SUPERUSER% -d %POSTGRES_DB% -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
REM psql -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_SUPERUSER% -d %POSTGRES_DB% -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

REM Export DATABASE_URL for current process
SET DATABASE_URL=postgresql://%POSTGRES_USER%:%POSTGRES_PASSWORD%@%POSTGRES_HOST%:%POSTGRES_PORT%/%POSTGRES_DB%
SET POSTGRES_URL=%DATABASE_URL%
echo [INFO] DATABASE_URL=%DATABASE_URL%

REM Reset Alembic version table (if present)
echo [INFO] Resetting Alembic version table...
python "%BACKEND_DIR%\scripts\reset_alembic.py" || EXIT /B 1

REM Run Alembic migrations
echo [INFO] Running Alembic migrations...
pushd "%BACKEND_DIR%" >NUL
alembic upgrade head || (popd >NUL & EXIT /B 1)
popd >NUL

REM Optional data migration
SET DO_MIGRATE=no
IF /I "%AUTO_MIGRATE_DATA%"=="yes" SET DO_MIGRATE=yes
IF /I "%AUTO_MIGRATE_DATA%"=="ask" (
  SET /P CHOICE=[PROMPT] Migrate existing data from SQLite (%DATABASE_URL_SQLITE%)? [y/N] = 
  IF /I "%CHOICE%"=="y" SET DO_MIGRATE=yes
)

IF /I "%DO_MIGRATE%"=="yes" (
  echo [INFO] Migrating data from SQLite to PostgreSQL...
  python "%BACKEND_DIR%\scripts\migrate_sqlite_to_postgres.py" --source "%DATABASE_URL_SQLITE%" --target "%DATABASE_URL%" || EXIT /B 1
) ELSE (
  echo [INFO] Skipping data migration.
)

REM Validate with model tests
echo [INFO] Validating database with model sanity tests...
python "%BACKEND_DIR%\scripts\test_models.py" || EXIT /B 1

echo [INFO] Local PostgreSQL setup and migration completed successfully.
EXIT /B 0
