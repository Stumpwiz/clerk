#!/usr/bin/env python3
"""Import a verified PDF manifest into the explicitly selected database.

Run from backend: python scripts/import_generated_letters.py /path/manifest.json
The default is a read-only dry run; --apply is required to write rows.
DATABASE_URL must be explicitly present in the environment; never use .env implicitly.
"""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    url = os.environ.get('DATABASE_URL', '')
    if not url.startswith(('postgresql://', 'postgresql+psycopg2://')):
        parser.error('Set DATABASE_URL explicitly to the intended PostgreSQL database')
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.letter_storage import import_manifest
    engine = create_engine(url, hide_parameters=True)
    try:
        with Session(engine) as db:
            result = import_manifest(db, args.manifest, dry_run=not args.apply)
        print(result)
    except ValueError as exc:
        print(f'Import refused: {exc}', file=sys.stderr)
        return 1
    except Exception:
        # DB exception strings may include parameters/PDF contents or credentials.
        print('Import failed; transaction rolled back. Check manifest integrity and filename conflicts.', file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
