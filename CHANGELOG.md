# Project Changelog

## 0.1.1 — Record reviewed updater publication and package change history

Why: Pin the published update tooling and establish readable change details with separate reported test evidence

Actor/model: Codex builder; independent review by Claude Code reporting claude-sonnet-5-5

### File changes

- modified: markyafi1991/budget-request-demo/README\.md
- added: markyafi1991/budget-request-demo/UPDATER\_REVIEW\.md
- added: markyafi1991/budget-request-demo/scripts/project\_packages/README\.md
- added: markyafi1991/budget-request-demo/scripts/project\_packages/update\_project\.py
- added: markyafi1991/budget-request-demo/scripts/tests/test\_project\_package\_updates\.py

### Reported verification (not executed by updater)

- passed: Updater regression tests — 21 tests and 17 subtests passed; command python3 -m pytest scripts/tests/test\_project\_package\_updates\.py -q; updater SHA-256 a9b614bd2331d4c7f8d291cd4e61689c0a636b2641a96430bd8390953263efb1
- not-run: Power Apps / Power BI / container acceptance — App, report and container image are not implemented or deployed by this metadata update
- passed: Independent engineering release review — Claude Code reported claude-sonnet-5-5: RELEASE after same-file corrections; reviewed hashes are published in UPDATER\_REVIEW\.md\. Static review, not an executed app test\.
- passed: Live proposal and retry — Public PR \#1 created for exact packet and second run returned the same PR; no duplicate\. Proof PR is superseded by this refreshed update after tooling merge\.
- passed: Reviewed tooling publication — Owner-approved PR \#2 merged at 8aa01a504b9cea3bf2e8d89be236f4f9eca043d1\. Code, tests and guide were byte-read-back checked on the reviewed branch\.

Upgrade: Update the hub checkout to this version to obtain the manual updater\. No app, report, model or container upgrade is included\.

Rollback: use the previous manifest's exact component commits; no history reset is performed. Commit retention is not guaranteed: retain complete release snapshots or owner-created tags.

All hub file hashes, including metadata excluded from content-diff counts, are retained in the packet. Hub content is re-baselined by hash, not reconstructed historical text.

This PR does not merge, publish a release, build/publish an image, export the private vault, or provision employee access.

