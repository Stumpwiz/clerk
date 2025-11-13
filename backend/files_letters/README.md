# Files Letters Directory

This directory contains generated welcome letter PDFs and their LaTeX source files.

## File Naming Convention

Generated files follow this pattern:

- `YYYY-MM-DD_LastName.pdf` - Generated PDF file
- `YYYY-MM-DD_LastName.tex` - LaTeX source file (may be retained temporarily)

Example: `2025-11-12_Smith.pdf`

## Automatic Cleanup

The letter generation process automatically:

- Generates the `.tex` file from the template
- Compiles it with XeLaTeX to create the PDF
- Removes auxiliary files (`.aux`, `.log`, `.out`, `.synctex.gz`, etc.)

## File Management

PDFs can be:

- **Viewed**: Via the Letters page or direct API access
- **Downloaded**: Through the browser's PDF viewer
- **Deleted**: Via the Letters page interface

Files are sorted in the UI with dated PDFs first (ascending order), then undated PDFs alphabetically.
