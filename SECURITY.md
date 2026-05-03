# Security Policy

## Reporting a Vulnerability

If you believe you have found a security vulnerability in this project, please report it privately. Do **not** open a public GitHub issue.

**Email:** `security@orthodoxethos.com`

When reporting, please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce.
- The affected component (`backend/`, `web/`, contract docs, infrastructure).
- Any proof-of-concept code or screenshots.
- Whether the issue is already publicly known or has been disclosed elsewhere.

We will acknowledge your report within **3 business days** and aim to provide an initial assessment within **10 business days**.

## Scope

In scope:

- The `backend/` FastAPI service and its `adapters/` to Anthropic, OpenAI, Qdrant, Redis, Clerk, Stripe.
- The `web/` Next.js application.
- The closed-corpus retrieval and citation pipeline (A1–A6).
- Tenant isolation and authentication boundaries.
- Sensitive log redaction and raw-text encryption.
- CI safety-gate workflow.

Out of scope:

- Third-party services we depend on (Clerk, Stripe, Anthropic, OpenAI, Railway). Report to those vendors directly.
- Theological accuracy or doctrinal disagreements — these are governed by the safety suite and founder review, not the security process.
- Attacks requiring physical access to the device of an already-authenticated administrator.

## Hardening Commitments

Per ADR 0001–0007 and the canonical contract pack:

- Closed-corpus rule: every user-facing answer is traceable to an approved tenant chunk. Pipeline shortcuts that skip approval are critical bugs.
- Tenant isolation: cross-tenant data exposure (Qdrant, SQL, cache, logs, admin UI) is a critical bug.
- Secrets handling: secrets live in `.env` or an approved secret manager. Hardcoded secrets in any committed file are a critical bug.
- Sensitive logs: raw sensitive query text is encrypted, admin-only, audited, and retained ≤30 days during private beta. Any path that exposes raw text outside this control is a critical bug.

## Disclosure Policy

We follow coordinated disclosure. After we have validated and remediated a reported issue, we will agree on a disclosure timeline with the reporter. Credit is given by default unless the reporter requests anonymity.
