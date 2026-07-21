# Document ingestion

Authenticated users upload through an expiring, site-scoped session. The browser calculates SHA-256, the backend validates membership, MIME type, size and duplicates, then issues a presigned object-storage URL. Confirmation checks the stored object's declared size and content type before extraction.

Supported formats are PDF, TXT, Markdown, CSV, DOCX and XLSX. Extraction is bounded by file, page, sheet, row, column, cell, character and chunk limits. PDF text retains page locators; spreadsheets retain sheet and row context; DOCX headings are retained where available. Image-only PDFs fail with an explicit message because OCR is not currently implemented.

Successful extraction persists genuine evidence regions and overlapping document chunks with tenant, site, revision and source locator metadata. Embedding and Neo4j enrichment are separate best-effort stages; lexical evidence remains usable when either provider is unavailable.
