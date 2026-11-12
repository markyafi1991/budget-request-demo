# Budget Request Demo — Project Package

**Version 0.1.0** · 2026-11-12 · Scaffold / not a completed demo

**A Power Apps front end and a simple Power BI report for a fictional department budget-request workflow.**

This is an entirely fictional portfolio scenario. No client data, credentials, private vault content or private repository history is included. The application and report have not yet been built or acceptance-tested.

## Start here

The intended demonstration is request → review decision → financial impact. The first milestone is a working two-screen app and one report page before adding optional automation or more employees.

## Component repositories

| Component | Repository | State |
|---|---|---|
| Project knowledge, data and audit | [This hub](https://github.com/markyafi1991/budget-request-demo) | Scaffold and synthetic fixtures |
| Power Apps | [App source](https://github.com/markyafi1991/budget-request-demo-powerapps) | Contract only; app not built |
| Power BI | [Report source](https://github.com/markyafi1991/budget-request-demo-powerbi) | Contract only; report not built |
| AI employees | [Definitions and configuration](https://github.com/markyafi1991/budget-request-demo-employees) | Draft charters; not deployed |

`project-package.json` pins component commits and file hashes. It is the project grouping and future release-bundle inventory, not a published container image or completed downloadable multi-repository bundle.

## Included now

- Curated public project knowledge in `knowledge/project-brief.md`.
- Fictional November 2026 fixtures and independent expected values.
- Component scope, draft employee definitions and explicit missing-artifact status.
- A reproduction checklist in `REPRODUCE.md`.

## GitHub Packages

Intended future employee image: `ghcr.io/markyafi1991/budget-request-demo-employees`. Registry package, image digest, container recipe and deployment test are not present yet. Packages will distribute images; a future complete release must also bundle the permitted pinned repository snapshots and instructions. Existing private vault repositories stay separate and are not dependencies of this public scaffold.

## Evidence and reproduction

No app/report run or customer result is claimed. A fresh-workspace reproduction with exact versions, expected outputs, failure/recovery checks and required accounts is the release gate. Credentials stay local. External services, licenses and tools must be documented before handoff. This repository is currently a planning/source scaffold, not a finished reporting product.
