# Audits

Status: Reference (non-canonical)

This directory holds **non-canonical scope and design audits** produced when an
external proposal, brainstorm, or strategy document needs to be evaluated
against the project's locked contracts and ADRs without amending them.

## What goes here

- Per-document audits that map an external proposal section-by-section to the
  current canonical sources (`AGENTS.md`, `docs/contracts/*`, `docs/adr/*`,
  `docs/api/*`, `docs/schemas/*`, `docs/task_cards/*`).
- Each audit classifies the proposal's elements as **Aligned**, **Deferred**,
  **Conflicts**, or **Rejected** and cites the specific canonical clause that
  justifies the label.
- Each audit ends with a **Harvest list** of items worth promoting to future
  ADR drafts.

## What does NOT go here

- New ADRs (those live in `docs/adr/`).
- Contract amendments (those live in `docs/contracts/`).
- Schema additions (those live in `docs/schemas/`).
- Decisions. An audit surfaces options; it does not make a decision.

## Filename convention

`YYYY-MM-DD-<short-slug>.md`

Each audit must carry a `Status: reference (non-canonical analysis)` header so
no future agent treats it as an active source. Audits do not override
contracts, ADRs, or schemas under any circumstance.

## Index

Audits are listed in `docs/DOCS_INDEX.md` under the *Reference Material* table
and traced back to the source proposal under the *Traceability* table.
