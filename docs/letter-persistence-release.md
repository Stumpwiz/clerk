# Letter persistence release procedure

These are planned operator steps, not automatic startup actions. Production
migration, import, commits, pushes, and deployments require explicit authorization.
App Runner overrides Docker startup with Uvicorn, so it will not apply migrations.

## Preserve before any backend replacement

Use an existing authorized API session cookie file outside Git. Never put credentials
on the command line or paste them into chat. Set `CLERK_COOKIE_FILE` to its path and
`CLERK_PDF_EXPORT` to a new private directory outside the repo. From `backend/`, using
the configured Python interpreter:

```sh
python scripts/preserve_generated_letters.py --cookie-file "$CLERK_COOKIE_FILE" --output "$CLERK_PDF_EXPORT"
```

The exporter uses only GETs, refuses redirects, checks inventory before and after
export, reads saved bytes back, and compares a second download. It writes the
manifest of filenames, sizes, and SHA-256 checksums only after every file verifies.
Any failure means stop. A partial export is not proof of complete preservation.
App Runner can have multiple instances with different ephemeral files; differing
inventories/content must be resolved before release. Keep the archive outside
App Runner and Git.

Before cutover coordinate a pause in letter generation/deletion, repeat export to
a new directory, and use that final manifest. Do not replace the backend until
all PDFs have been imported and verified. An earlier export does not capture
letters generated or deleted afterward.

## Migration and import, after approval

1. Verify the production DB target, backup, and Alembic revision. Expected existing
   head: `7a4d1f8c2e91`; investigate any mismatch. Confirm no production foreign keys
   reference `users` before releasing deletion.
2. Set `DATABASE_URL` securely in the operator environment, never in command arguments
   or logs. From `backend/` in the reviewed checkout, apply the additive migration:

   ```sh
   python -m alembic upgrade 92d6f8a1c430
   ```

3. Dry-run import, explicitly apply, then verify with another dry run:

   ```sh
   python scripts/import_generated_letters.py "$CLERK_PDF_EXPORT/manifest.json"
   python scripts/import_generated_letters.py "$CLERK_PDF_EXPORT/manifest.json" --apply
   python scripts/import_generated_letters.py "$CLERK_PDF_EXPORT/manifest.json"
   ```

   The final dry run must report zero `would_insert` and all entries `identical`.
   All source files are checked first. Identical DB records are skipped; different
   bytes under an existing filename abort and roll back the entire import.
   Concurrent inserts never silently overwrite content. Historical creation times
   are unavailable from the old API, so imported rows receive an import timestamp;
   letter dates remain in filenames.
4. Release persistence first. Pushing backend files to `master` automatically
   triggers deployment, so do not push until preservation/migration/import pass.
   No workflow change is needed. Changing the workflow itself deploys both services.
5. After backend replacement, verify via the authenticated API:

   ```sh
   python scripts/preserve_generated_letters.py --cookie-file "$CLERK_COOKIE_FILE" --verify "$CLERK_PDF_EXPORT/manifest.json"
   ```

   Require identical inventory, lengths, and checksums; open a saved letter in the UI.
   In an isolated test environment generate a letter, replace the application while
   keeping PostgreSQL, verify bytes, then delete it. Repeat the production manifest
   comparison following a later authorized backend replacement.
6. After persistence verification, release user deletion separately and verify both
   services. The existing push workflow can deploy backend and frontend concurrently;
   wait for both before checking self/active refusal and inactive-other confirmation.
   End the coordinated pause in letter writes.

Keep the preservation archive. Do not drop/downgrade `generated_letters` as a rollback
step. Filesystem-only code hides DB PDFs and reintroduces loss for new letters;
fix forward or restore database-backed code.

## Tests

Use only disposable PostgreSQL: `pg_session` deletes application rows between tests.
Set `DATABASE_URL` explicitly to that test DB. Run the backend suite, including
`test_letters.py` and `test_user_deletion.py`. The latter verifies DELETE waits for
concurrent reactivation and then returns 409. In `frontend/`, `npm test` verifies
confirmation/cancellation/refusals; `npm run build` checks UI integration.
