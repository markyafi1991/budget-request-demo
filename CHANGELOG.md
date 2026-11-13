# Project Changelog

## 0.1.1 — Establish reviewed package change records

Why: Give each package update a file inventory, rationale, reported checks, exact versions and upgrade/rollback guidance

Actor/model: Codex; model identifier not independently recorded

### File changes

- No component/content changes; establishing or updating package metadata only.

### Reported verification (not executed by updater)

- passed: Updater regression tests — 21 tests and 17 subtests passed; command python3 -m pytest scripts/tests/test\_project\_package\_updates\.py -q; updater SHA-256 a9b614bd2331d4c7f8d291cd4e61689c0a636b2641a96430bd8390953263efb1
- not-run: Power Apps / Power BI / container acceptance — App, report and container image are not implemented or deployed by this metadata update

Upgrade: No app or report upgrade; metadata proposal only\. Application/report/image acceptance remains pending\.

Rollback: use the previous manifest's exact component commits; no history reset is performed. Commit retention is not guaranteed: retain complete release snapshots or owner-created tags.

All hub file hashes, including metadata excluded from content-diff counts, are retained in the packet. Hub content is re-baselined by hash, not reconstructed historical text.

This PR does not merge, publish a release, build/publish an image, export the private vault, or provision employee access.

