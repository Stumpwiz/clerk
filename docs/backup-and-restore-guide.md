### Backup and Restore Guide (SQLite, PostgreSQL, and AWS RDS)

This guide explains how to back up and restore your database for both local environments (SQLite and PostgreSQL) and AWS RDS PostgreSQL. It also includes snapshot, point-in-time recovery (PITR) notes, and verification steps.

#### Prerequisites
- Python 3 with project requirements installed.
- For PostgreSQL tasks: pg_dump, pg_restore, and psql on PATH.
- For AWS integrations: AWS CLI v2 configured, and jq for JSON parsing.
- Ensure DATABASE_URL (or POSTGRES_* envs) points to the correct target.

---

### Local backups (SQLite and PostgreSQL)

Back up using:
```
python backend/scripts/backup_database.py
```

What it does:
- Detects DB type from app.config.get_database_url().
- Stores backups under backend/backups/ with a UTC timestamp.
- SQLite: copies the .db file (after verifying a SQLite header).
- PostgreSQL: runs pg_dump -Fc to create a custom-format dump suitable for pg_restore.

Options:
- Override the database URL:
```
python backend/scripts/backup_database.py --database-url postgresql://user:pass@host:5432/db
```
- Upload to S3 after local backup:
```
python backend/scripts/backup_database.py --s3-bucket my-bucket --s3-prefix clerk/prod
```

Safety notes:
- PostgreSQL backups include schema and data. Consider excluding large tables or using --table on manual runs of pg_dump if needed.
- Verify that credentials used in the URL have read privileges.

---

### Local restores (SQLite and PostgreSQL)

Restore using:
```
python backend/scripts/restore_database.py --backup <path-to-backup>
```

What it does:
- Validates backup file format.
- Dry-run support (--dry-run).
- Prompts for confirmation unless --force is provided.
- SQLite: makes a pre-restore copy of the current DB at *.pre-restore.<timestamp>, then replaces it.
- PostgreSQL: restores .dump files via pg_restore --clean --if-exists --no-owner --no-privileges; .sql files via psql -v ON_ERROR_STOP=1.

Examples:
- Dry run:
```
python backend/scripts/restore_database.py --backup backend/backups/postgres_db@host_20250101T000000Z.dump --dry-run
```
- Force restore to a specific database URL:
```
python backend/scripts/restore_database.py --backup path/to/file.dump --database-url postgresql://user:pass@host:5432/db --force
```

Post-restore validation:
- Run
```
python backend/scripts/test_models.py
```
to execute CRUD sanity checks against your PostgreSQL target.

---

### AWS RDS PostgreSQL Backups

There are three mechanisms to consider:
1) Logical dumps (same as local PostgreSQL) using backend/scripts/backup_database.py pointed at RDS.
2) RDS Snapshots (on-demand or automated): full instance-level backups managed by AWS.
3) Point-in-time recovery (PITR): restore the DB to a specific time within the retention period.

#### Create an on-demand RDS snapshot
```
bash scripts/rds-create-snapshot.sh --db-instance-id <your-rds-instance-id>
```
- Creates a snapshot named <instance>-<UTC timestamp> and waits until it’s available.
- Prints the snapshot ARN.

Add tags:
```
bash scripts/rds-create-snapshot.sh --db-instance-id clerk-rds-pg \
  --tag Key=Project,Value=Clerk --tag Key=Env,Value=Prod
```

#### Verify a snapshot
```
bash scripts/rds-verify-backup.sh --snapshot-id <snapshot-id>
```
- Checks that the snapshot is available and prints engine version.
- Optional deeper verification by restoring to a temporary instance and running a probe query:
```
bash scripts/rds-verify-backup.sh --snapshot-id <snapshot-id> --probe --cleanup \
  --temp-instance-class db.t4g.micro --temp-sg-ids sg-xxxx --temp-subnet-group my-db-subnets
```

#### Restore from a snapshot (to a NEW instance)
```
bash scripts/rds-restore-from-snapshot.sh \
  --snapshot-id <snapshot-id> \
  --new-db-instance-id <new-instance-id> \
  --db-instance-class db.t4g.micro \
  --vpc-security-group-ids sg-abc,sg-def \
  --db-subnet-group my-db-subnets \
  --publicly-accessible false
```
- Waits for the new instance to become available and prints the endpoint.
- Update your application DATABASE_URL to point to the new endpoint when ready.

#### Point-in-time recovery (PITR) overview
- With automated backups enabled, you can restore to a specific timestamp:
  1. Identify the source DB instance id and the target time (UTC) within your retention window.
  2. Use the AWS Console or CLI: aws rds restore-db-instance-to-point-in-time.
  3. Provide a new DB instance identifier and optional subnet group/SGs.
  4. Wait until available, then validate and update the app’s connection string.
- Example (CLI):
```
aws rds restore-db-instance-to-point-in-time \
  --region us-east-1 \
  --source-db-instance-identifier clerk-rds-pg \
  --target-db-instance-identifier clerk-rds-pg-pitr-TEST \
  --restore-time 2025-11-15T12:00:00Z \
  --use-latest-restorable-time false \
  --db-instance-class db.t4g.micro \
  --publicly-accessible false
```

---

### Safety and best practices
- Always test restores regularly (either to a local Postgres or a temporary RDS instance) to validate backups.
- For PostgreSQL restores, never restore over a production instance without a current snapshot and a clear maintenance plan.
- Store backups in versioned S3 buckets with lifecycle rules for retention.
- Encrypt backups at rest (RDS snapshots are encrypted if the instance is encrypted; S3 uploads should use SSE as needed).
- Restrict Security Group rules to least privilege. Prefer private RDS with App Runner VPC Connector for production.

---

### Quick Reference
- Local backup: python backend/scripts/backup_database.py
- Local restore: python backend/scripts/restore_database.py --backup <file> [--force]
- RDS snapshot: bash scripts/rds-create-snapshot.sh --db-instance-id <id>
- Verify snapshot: bash scripts/rds-verify-backup.sh --snapshot-id <id> [--probe --cleanup]
- Restore snapshot (new instance): bash scripts/rds-restore-from-snapshot.sh --snapshot-id <id> --new-db-instance-id <new>
