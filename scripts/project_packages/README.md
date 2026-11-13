# Project package updates

**Version 1.0** · 2026-11-12

Manual update review for the four public Budget Request Demo repositories. This
does not export the private vault, keep every repository in the estate current,
merge pull requests, publish Releases, build GHCR images or schedule anything.

## Ownership and source updates

- App/report code and employee definitions are edited on branches in their
  component repositories, then reviewed and merged by the owner.
- Knowledge starts in the vault. Select the project-specific files, curate a
  public copy, inspect the entire proposed export and history, then propose it in
  the appropriate public repository. No automatic vault export exists in this
  utility. Do not point an agent at the full private vault to update public code.
- The hub manifest pins a compatible set of component commits. Moving component
  main branches does not silently change an already recorded package version.
- This updater detects differences in those public components and prepares the
  hub's next manifest, changelog and auditable update packet. It supports the
  fixed Budget Demo repository set only; onboarding another project requires a
  separately reviewed destination/scope change.

## Prepare: read-only remote operations

Requires Python 3.10+ and an authenticated GitHub CLI. Prepare reads public
repository metadata and committed file contents. Its only local write is a new
packet file; an existing packet is never overwritten.

Create an explicit checks JSON file, for example:

```json
[
  {"check": "Power Apps acceptance", "result": "not-run", "evidence": "App is not built"},
  {"check": "Updater regression tests", "result": "passed", "evidence": "Record the exact test command, source revision and retained output"}
]
```

```sh
python3 scripts/project_packages/update_project.py prepare \
  --summary "Describe this update" \
  --why "Explain the reason, not an inferred motivation" \
  --actor "Builder identity and actual model, if known" \
  --version 0.1.1 \
  --upgrade "Recipient steps, or why no upgrade is needed" \
  --checks /private/tmp/budget-demo-checks.json \
  --output /private/tmp/budget-demo-update.json
```

The packet includes added/modified/deleted file inventories, component text
diffs, before/after hashes, exact commits, previous/next manifest, supplied
reason/actor/checks, recipient instructions and rollback source revisions.
Hub changes use hashes because the original hub baseline only recorded hashes;
the packet links the current hub commit for inspection. All hub files, including
metadata excluded from content-diff counts, are listed in its hash inventory.
Hub content is explicitly re-baselined by hash, not reconstructed historical text.
Component `source_hashes_checked_at_prepare` means bytes were read and hashed,
not that a publication or application test passed. Reported checks are
labelled as reported; the updater does not run Power Apps or Power BI tests and
does not upgrade app/report/image/reproduction readiness flags.

It refuses private/forked/archived destinations, rewritten component history,
baseline hash mismatches, truncated inventories, unsafe paths, symlinks,
executables, binaries, files over 1 MB, more than 500 tree entries, snapshots over
16 MB, and common token/private-key signatures. These are conservative checks,
not proof that prose contains no confidential information. Owner content review
and applicable third-party rights review are still required. A PBIX/MSAPP or
large binary needs a separately reviewed asset path; this text-only first version
will stop rather than silently omit it.

## Propose: explicit remote writes

After independent release review of this utility, inspect the exact packet and
approve its printed SHA-256:

```sh
python3 scripts/project_packages/update_project.py propose \
  --packet /private/tmp/budget-demo-update.json \
  --approved-sha256 THE_EXACT_REVIEWED_PACKET_HASH
```

This reconstructs the packet from current public sources and checks every head
again. It creates only a uniquely named `codex/project-update-*` hub branch and a
draft PR containing `project-package.json`, `CHANGELOG.md` and `updates/<hash>.json`.
It never writes a component repository or main. Existing proposal branches/PRs
are reconciled; changed or closed proposals stop rather than being overwritten.
A race detected after branch creation can leave a proposal branch for inspection.
On a timeout, rerun the same exact reviewed packet after inspecting current state;
never regenerate/reapprove blindly. Harmless unreferenced Git objects can remain
if a write fails before the branch is created.

The owner reviews and merges separately. Releases and package images are another
later, evidence-based action. Older manifests remain available for rollback; the
utility does not reset branches or undo recipient data migrations.
SHA references do not guarantee indefinite commit retention after force-pushes;
retain complete release snapshots or owner-created tags. Record the independently
reviewed updater/test/guide hashes in the release audit; `tool_sha256` binds
prepare/propose to one file version but does not itself prove independent review.

## Verification

```sh
python3 -m pytest scripts/tests/test_project_package_updates.py -q
```

No unattended schedule is installed. Before scheduling even PR preparation,
battle-test the manual process, register ownership/cadence and use scoped
credentials. A GitHub topic/hub groups repositories but does not itself create
a GitHub Packages registry entry.
