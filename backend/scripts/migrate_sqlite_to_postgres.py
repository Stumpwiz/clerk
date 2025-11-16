#!/usr/bin/env python3
"""
SQLite -> PostgreSQL data migration utility for the Clerk backend.

This script copies data from a source SQLite database into a target PostgreSQL
database using SQLAlchemy. It attempts to preserve foreign key integrity by
inserting tables in a dependency-safe order and validates row counts after
migration. It is intended for one-time or occasional migrations (e.g., moving
from the default SQLite dev DB to PostgreSQL).

Environment variables
---------------------
- DATABASE_URL   -> Source (SQLite) connection string (e.g., sqlite:///./instance/community_admin.db)
- POSTGRES_URL   -> Target (PostgreSQL) connection string (e.g., postgresql://user:pass@host:5432/db)

You may also pass these via CLI flags to override the environment.

Usage examples
--------------
From the project root, with a Python environment that has backend requirements installed:

1) Basic migration using env vars:
   set DATABASE_URL=sqlite:///./backend/instance/community_admin.db
   set POSTGRES_URL=postgresql://clerk_user:clerk_password@localhost:5432/clerk_community_admin
   python backend/scripts/migrate_sqlite_to_postgres.py

2) Override URLs and run with a larger batch size and forced truncate of target tables:
   python backend/scripts/migrate_sqlite_to_postgres.py \
       --source sqlite:///./backend/instance/community_admin.db \
       --target postgresql://clerk_user:clerk_password@localhost:5432/clerk_community_admin \
       --batch-size 2000 --force-truncate

3) Dry-run to preview the plan (no writes):
   python backend/scripts/migrate_sqlite_to_postgres.py --dry-run

Notes
-----
- Ensure the target PostgreSQL schema/tables already exist (e.g., run Alembic migrations first).
- Stop the application while migrating to avoid concurrent writes.
- The script assumes the target is empty unless --force-truncate is provided.
- If your schema has circular FKs that are not deferrable, consider temporarily
  deferring constraints or running in two passes (parents first, then children).
"""

from __future__ import annotations

import os
import sys
import time
import math
import argparse
from typing import Dict, List, Set, Tuple, Iterable

from sqlalchemy import create_engine, text, MetaData, Table, select
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
    parser.add_argument("--source", dest="source", default=os.getenv("DATABASE_URL"), help="SQLite DATABASE_URL (env: DATABASE_URL)")
    parser.add_argument("--target", dest="target", default=os.getenv("POSTGRES_URL"), help="PostgreSQL URL (env: POSTGRES_URL)")
    parser.add_argument("--schema", dest="schema", default="public", help="Target Postgres schema (default: public)")
    parser.add_argument("--batch-size", dest="batch_size", type=int, default=1000, help="Insert batch size (default: 1000)")
    parser.add_argument("--tables", nargs="*", default=None, help="Optional subset of tables to migrate (space-separated)")
    parser.add_argument("--exclude", nargs="*", default=None, help="Optional list of tables to exclude")
    parser.add_argument("--dry-run", action="store_true", help="Plan only – do not write to target")
    parser.add_argument("--force-truncate", action="store_true", help="Truncate target tables before import")
    parser.add_argument("--validate-only", action="store_true", help="Do not copy, only validate counts between source and target")
    return parser.parse_args()


def ensure_urls(args: argparse.Namespace) -> Tuple[str, str]:
    src = args.source
    tgt = args.target
    if not src:
        raise SystemExit("Missing source SQLite URL. Set DATABASE_URL or pass --source.")
    if not tgt:
        raise SystemExit("Missing target PostgreSQL URL. Set POSTGRES_URL or pass --target.")
    if not src.startswith("sqlite"):
        raise SystemExit(f"Source must be SQLite. Got: {src}")
    if not tgt.startswith("postgresql"):
        raise SystemExit(f"Target must be PostgreSQL. Got: {tgt}")
    return src, tgt


def mk_engine(url: str) -> Engine:
    is_sqlite = url.startswith("sqlite")
    return create_engine(
        url,
        connect_args={"check_same_thread": False} if is_sqlite else {},
        pool_pre_ping=True,
        echo=False,
        future=True,
    )


def get_tables_in_dependency_order(src_engine: Engine, schema: str | None = None, include: List[str] | None = None, exclude: List[str] | None = None) -> List[str]:
    inspector = inspect(src_engine)
    all_tables = inspector.get_table_names(schema=schema)
    if include:
        all_tables = [t for t in all_tables if t in set(include)]
    if exclude:
        all_tables = [t for t in all_tables if t not in set(exclude)]

    # Build dependency graph based on FKs
    deps: Dict[str, Set[str]] = {t: set() for t in all_tables}
    for t in all_tables:
        for fk in inspector.get_foreign_keys(t, schema=schema):
            referred_table = fk.get("referred_table")
            if referred_table and referred_table in deps:
                # t depends on referred_table (parent must be inserted first)
                deps[t].add(referred_table)

    # Topological sort (Kahn's algorithm)
    result: List[str] = []
    deps_copy: Dict[str, Set[str]] = {k: set(v) for k, v in deps.items()}
    while deps_copy:
        # pick all nodes with no deps
        no_deps = [t for t, d in deps_copy.items() if not d]
        if not no_deps:
            # cycle detected – fall back to original order to avoid infinite loop
            # Put remaining items in deterministic order
            remaining = sorted(deps_copy.keys())
            result.extend(remaining)
            break
        result.extend(sorted(no_deps))
        for nd in no_deps:
            deps_copy.pop(nd, None)
        for dset in deps_copy.values():
            dset.difference_update(no_deps)

    # Final filter to preserve requested subset ordering
    return [t for t in result if t in all_tables]


def reflect_table(engine: Engine, table_name: str, schema: str | None) -> Table:
    md = MetaData(schema=schema)
    return Table(table_name, md, autoload_with=engine)


def count_rows(engine: Engine, table: Table) -> int:
    with engine.connect() as conn:
        return int(conn.execute(select(text("count(*)")).select_from(table)).scalar_one())


def iter_rows_in_batches(engine: Engine, table: Table, batch_size: int) -> Iterable[List[RowMapping]]:
    # Prefer primary key ordering if available to avoid LIMIT/OFFSET cost explosion.
    pk_cols = list(table.primary_key.columns) if table.primary_key else []
    order_by = pk_cols if pk_cols else list(table.columns)
    with engine.connect() as conn:
        total = int(conn.execute(select(text("count(*)")).select_from(table)).scalar_one())
        if total == 0:
            return
        pages = math.ceil(total / batch_size)
        for i in range(pages):
            stmt = select(table)
            for col in order_by:
                stmt = stmt.order_by(col)
            stmt = stmt.limit(batch_size).offset(i * batch_size)
            result = conn.execute(stmt)
            rows = [dict(r._mapping) for r in result]
            yield rows


def intersection_columns(src_table: Table, tgt_table: Table) -> List[str]:
    src_cols = {c.name for c in src_table.columns}
    tgt_cols = {c.name for c in tgt_table.columns}
    cols = [c for c in src_table.columns.keys() if c in tgt_cols]
    return cols


def reset_identity_sequence(engine: Engine, schema: str | None, table: Table) -> None:
    # Try to reset identity/serial sequences based on max(id)
    pk_cols = list(table.primary_key.columns) if table.primary_key else []
    if len(pk_cols) != 1:
        return
    pk = pk_cols[0]
    if str(pk.type).lower() not in ("integer", "bigint", "serial", "bigserial"):
        return
    full_name = f'"{schema}"."{table.name}"' if schema else f'"{table.name}"'
    pk_name = pk.name
    sql = text(
        f"""
        SELECT setval(
          pg_get_serial_sequence('{full_name}', :pk),
          COALESCE((SELECT MAX("{pk_name}") FROM {full_name}), 0)
        );
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, {"pk": pk_name})


def truncate_table(engine: Engine, schema: str | None, table_name: str) -> None:
    full_name = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {full_name} RESTART IDENTITY CASCADE"))


def validate_counts(src_engine: Engine, tgt_engine: Engine, schema: str | None, table_names: List[str]) -> Tuple[bool, List[str]]:
    ok = True
    issues: List[str] = []
    for t in table_names:
        src_t = reflect_table(src_engine, t, None)  # SQLite has no schema
        tgt_t = reflect_table(tgt_engine, t, schema)
        with src_engine.connect() as sconn, tgt_engine.connect() as tconn:
            sc = int(sconn.execute(select(text("count(*)")).select_from(src_t)).scalar_one())
            tc = int(tconn.execute(select(text("count(*)")).select_from(tgt_t)).scalar_one())
        if sc != tc:
            ok = False
            issues.append(f"Row count mismatch for {t}: source={sc} target={tc}")
    return ok, issues


def main() -> int:
    args = parse_args()
    src_url, tgt_url = ensure_urls(args)

    print("== Clerk DB Migration: SQLite -> PostgreSQL ==")
    print(f"Source: {src_url}")
    print(f"Target: {tgt_url}")
    if args.dry_run:
        print("[DRY-RUN] No changes will be made.")

    src_engine = mk_engine(src_url)
    tgt_engine = mk_engine(tgt_url)

    # Determine copy order based on source FK relationships
    table_order = get_tables_in_dependency_order(
        src_engine,
        schema=None,
        include=args.tables,
        exclude=args.exclude,
    )

    if not table_order:
        print("No tables found to migrate. Ensure the source DB has tables.")
        return 1

    print("Planned table order:")
    for t in table_order:
        print(f"  - {t}")

    if args.validate_only:
        ok, issues = validate_counts(src_engine, tgt_engine, args.schema, table_order)
        if ok:
            print("Validation OK: Row counts match for all listed tables.")
            return 0
        print("Validation FAILED:")
        for msg in issues:
            print(" -", msg)
        return 2

    if args.force_truncate and not args.dry_run:
        print("Truncating target tables (CASCADE) in reverse dependency order...")
        for t in reversed(table_order):
            try:
                truncate_table(tgt_engine, args.schema, t)
                print(f"  TRUNCATE {t} OK")
            except SQLAlchemyError as e:
                print(f"  TRUNCATE {t} FAILED -> {e}")
                return 1

    overall_start = time.time()
    copied_totals: Dict[str, int] = {t: 0 for t in table_order}
    try:
        with tgt_engine.begin() as tgt_conn:
            # Optionally try to defer constraints (works if constraints are deferrable)
            try:
                if not args.dry_run:
                    tgt_conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))
            except SQLAlchemyError:
                pass  # Not all constraints are deferrable

            for tname in table_order:
                print(f"\nMigrating table: {tname}")
                src_table = reflect_table(src_engine, tname, None)
                tgt_table = reflect_table(tgt_engine, tname, args.schema)
                cols = intersection_columns(src_table, tgt_table)
                if not cols:
                    print(f"  Skipping: no matching columns between source and target for {tname}")
                    continue

                inserted = 0
                batch_idx = 0
                for batch in iter_rows_in_batches(src_engine, src_table, args.batch_size):
                    if not batch:
                        break
                    # Map rows to matching columns only
                    payload = [{k: row.get(k) for k in cols} for row in batch]
                    count = len(payload)
                    if args.dry_run:
                        print(f"  [DRY-RUN] Would insert batch {batch_idx} rows={count}")
                    else:
                        tgt_conn.execute(tgt_table.insert(), payload)
                    inserted += count
                    batch_idx += 1
                    if count:
                        print(f"  Inserted {inserted} rows...", end="\r")

                if not args.dry_run:
                    # Reset sequences for serial/identity PKs
                    try:
                        reset_identity_sequence(tgt_engine, args.schema, tgt_table)
                    except SQLAlchemyError:
                        pass

                print(f"  Done. Inserted {inserted} rows total.")
                copied_totals[tname] = inserted

    except SQLAlchemyError as e:
        print("Migration failed; rolling back.")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\nValidating row counts...")
    ok, issues = validate_counts(src_engine, tgt_engine, args.schema, table_order)
    if not ok:
        print("Validation FAILED:")
        for msg in issues:
            print(" -", msg)
        return 2

    elapsed = time.time() - overall_start
    print("\nMigration completed successfully.")
    for t in table_order:
        print(f"  {t}: {copied_totals.get(t, 0)} rows")
    print(f"Total time: {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
