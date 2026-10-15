# Reviewed documentation binaries

`python scripts/privacy_check.py --history` rejects unreviewed binary candidates
and historical blobs. CI runs this command without suppressing failures.

The sole approval source is `scripts/reviewed_binaries.json`. Its default is empty:

```json
{
  "version": 1,
  "assets": []
}
```

After inspecting an asset's visible contents and embedded metadata for private
data, an authorized reviewer can add an object to `assets` with exactly two fields:
`path` (the exact repository-relative path) and `sha256` (the 64-character lowercase
SHA-256 of the reviewed bytes). Commit the review entry with the approved asset.
This file records approvals; it does not perform the human review itself.

Rules enforced by the checker:

- Paths must be beneath `docs/assets/`, use forward slashes, and name a file.
  Directory components use ASCII letters, digits, underscores or hyphens; file
  names start with a letter/digit and may also contain dots. Absolute paths,
  traversal, empty components, wildcards and directory approvals are invalid.
- Only manifest version 1 and the documented fields are accepted. A missing manifest,
  invalid JSON, duplicate JSON keys, duplicate paths (including case aliases),
  malformed hashes and extra fields fail closed without printing their contents.
- An approval requires **both exact path and exact bytes**. Renaming, copying to
  another path or changing bytes requires a separate review. Historical scanning
  checks the same path/digest pair; it never trusts an old manifest as authority.
  One path has one approved digest. Use a new versioned filename for changed
  assets when retaining the previous version in history.
- Text privacy checks still run for UTF-8 content even if its path/hash is listed.
  Existing forbidden-artifact, identity, secret and locked-spec checks remain in
  force. A matching digest never overrides another privacy violation.
- History deduplication uses path **and** blob, so an approved blob at another
  historical path cannot inherit its approval.

Run the checker on the complete candidate checkout and its history. An empty
manifest intentionally continues to reject any pending screenshot candidates.
When preparing a tooling-only commit alongside unapproved presentation work,
verify an isolated checkout containing exactly the staged tooling files; do not
hide or approve the pending assets to make the main working-tree scan pass.
