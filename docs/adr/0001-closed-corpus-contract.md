# ADR 0001: Closed-Corpus Contract

Date: 2026-04-26
Status: Accepted

## Context

The assistant is trusted only if every answer is traceable to tenant-approved source material. General model knowledge, open-web facts, and unapproved corpus content are not valid evidence.

## Decision

All user-facing theological answers and generated artifacts must be produced only from approved, tenant-visible evidence admitted into an `EvidencePacket`.

A5 composition may not use external knowledge. A6 must reject unsupported claims, fabricated citations, and citations to suppressed or unapproved evidence.

## Rules

1. Qdrant retrieval always filters by `tenant_id` and `approved = true`.
2. A4 is the evidence admission boundary.
3. A5 sees only the evidence packet, prompt rules, answer mode, and safe tenant config.
4. Claims require source support.
5. Missing or weak source support returns YELLOW or RED fallback.
6. Unapproved chunks, candidate graph edges, admin-only content, and suppressed sources are never user-facing evidence.
7. Open-web browsing is not allowed in answer-time agents.

## Tests

- Cross-tenant chunks are not retrieved.
- Unapproved chunks are not admitted.
- A5 cannot cite a source absent from `EvidencePacket`.
- Unsupported claims fail verification.
- Empty corpus returns setup or RED fallback.
