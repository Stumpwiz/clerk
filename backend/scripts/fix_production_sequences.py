#!/usr/bin/env python3
"""
Fix auto-increment sequences in production database.

This script resets all PostgreSQL sequences to match the actual max ID values
in their respective tables. This fixes the "duplicate key value" errors that
occur when sequences are out of sync.

Usage:
    # Using environment variables (recommended for production)
    export DATABASE_URL="postgresql://user:pass@host:port/dbname"
    python backend/scripts/fix_production_sequences.py

    # Or with command line argument
    python backend/scripts/fix_production_sequences.py --database-url "postgresql://user:pass@host:port/dbname"

    # Dry run (show what would be fixed without making changes)
    python backend/scripts/fix_production_sequences.py --dry-run

Safe to run multiple times - it's idempotent.
"""

import argparse
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# Tables and their primary key columns that use sequences
TABLES_TO_FIX = [
    ('person', 'personid'),
    ('body', 'body_id'),
    ('office', 'office_id'),
    # Note: 'term' table uses composite primary key, no sequence
    ('users', 'id'),
]


def fix_sequence(engine, table_name: str, column_name: str, dry_run: bool = False) -> dict:
    """
    Fix the sequence for a specific table.

    Returns:
        dict with keys: table, column, old_value, new_value, fixed
    """
    result = {
        'table': table_name,
        'column': column_name,
        'old_value': None,
        'new_value': None,
        'fixed': False,
        'error': None
    }

    try:
        with engine.connect() as conn:
            # Get the sequence name
            seq_query = text(f"SELECT pg_get_serial_sequence('{table_name}', '{column_name}')")
            seq_result = conn.execute(seq_query)
            sequence_name = seq_result.scalar()

            if not sequence_name:
                result['error'] = f"No sequence found for {table_name}.{column_name}"
                return result

            # Get current sequence value
            current_val_query = text(f"SELECT last_value FROM {sequence_name}")
            current_result = conn.execute(current_val_query)
            result['old_value'] = current_result.scalar()

            # Get max ID from table
            max_id_query = text(f"SELECT COALESCE(MAX({column_name}), 0) FROM {table_name}")
            max_result = conn.execute(max_id_query)
            max_id = max_result.scalar()

            # Calculate what the new sequence value should be
            new_value = max_id if max_id > 0 else 1
            result['new_value'] = new_value

            # Check if fix is needed
            if result['old_value'] < new_value:
                if not dry_run:
                    # Fix the sequence
                    fix_query = text(
                        f"SELECT setval('{sequence_name}', :new_val, :is_called)"
                    )
                    conn.execute(
                        fix_query, 
                        {'new_val': new_value, 'is_called': max_id > 0}
                    )
                    conn.commit()
                    result['fixed'] = True
                else:
                    result['fixed'] = True  # Would be fixed
            else:
                result['error'] = 'Sequence is already correct'

    except SQLAlchemyError as e:
        result['error'] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Fix PostgreSQL sequences in the database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--database-url',
        help='Database connection URL (or set DATABASE_URL env var)',
        default=os.getenv('DATABASE_URL')
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be fixed without making changes'
    )

    args = parser.parse_args()

    if not args.database_url:
        print("ERROR: Database URL not provided.", file=sys.stderr)
        print("Set DATABASE_URL environment variable or use --database-url argument.", file=sys.stderr)
        sys.exit(1)

    # Mask password in output
    safe_url = args.database_url
    if '@' in safe_url:
        parts = safe_url.split('@')
        credentials = parts[0].split('//')[-1]
        if ':' in credentials:
            user = credentials.split(':')[0]
            safe_url = safe_url.replace(credentials, f"{user}:****")

    print(f"{'=' * 70}")
    print(f"PostgreSQL Sequence Fixer")
    print(f"{'=' * 70}")
    print(f"Database: {safe_url}")
    print(f"Mode: {'DRY RUN (no changes will be made)' if args.dry_run else 'LIVE (sequences will be updated)'}")
    print(f"{'=' * 70}\n")

    try:
        engine = create_engine(args.database_url)

        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[OK] Database connection successful\n")

    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to connect to database: {e}", file=sys.stderr)
        sys.exit(1)

    # Fix each table
    results = []
    for table, column in TABLES_TO_FIX:
        print(f"Checking {table}.{column}...", end=' ')
        result = fix_sequence(engine, table, column, args.dry_run)
        results.append(result)

        if result['error']:
            if 'already correct' in result['error']:
                print(f"[OK] (current: {result['old_value']}, max: {result['new_value']})")
            else:
                print(f"[WARN] {result['error']}")
        elif result['fixed']:
            action = "Would update" if args.dry_run else "Updated"
            print(f"[FIXED] {action}: {result['old_value']} -> {result['new_value']}")
        else:
            print(f"[OK] Already correct")

    # Summary
    print(f"\n{'=' * 70}")
    print("Summary:")
    print(f"{'=' * 70}")

    fixed_count = sum(1 for r in results if r['fixed'] and not r['error'])
    ok_count = sum(1 for r in results if 'already correct' in (r['error'] or ''))
    error_count = sum(1 for r in results if r['error'] and 'already correct' not in r['error'])

    print(f"Tables checked: {len(results)}")
    if args.dry_run:
        print(f"Would fix: {fixed_count}")
    else:
        print(f"Fixed: {fixed_count}")
    print(f"Already correct: {ok_count}")
    if error_count > 0:
        print(f"Errors: {error_count}")

    if args.dry_run and fixed_count > 0:
        print(f"\n[NOTE] This was a DRY RUN. Run without --dry-run to apply changes.")
    elif fixed_count > 0:
        print(f"\n[SUCCESS] Sequences have been fixed! You can now insert new records.")
    else:
        print(f"\n[SUCCESS] All sequences are correct. No changes needed.")

    print(f"{'=' * 70}\n")


if __name__ == '__main__':
    main()
