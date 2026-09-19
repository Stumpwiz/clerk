# Legacy letter directory

Generated PDFs now live in PostgreSQL's `generated_letters` table, with filename,
PDF bytes, and creation timestamp. This directory is no longer used for generation,
listing, retrieval, or deletion.

Each LaTeX run uses an isolated temporary directory, removed on completion or
failure. The database commit finishes before generation reports success.
Generating the same filename replaces its bytes and preserves its creation time.

Legacy PDFs must be preserved and imported explicitly; startup does not import
local files. See `docs/letter-persistence-release.md` for the release procedure.
