# Cache Key

Status: Canonical
Date: 2026-05-02 (corrects V3 SHA-256 reference value; adds V4 for calendar-profile bump)

This document is the canonical recipe for the response cache key. Every implementation must match it byte-for-byte so that two engineers — or two services — produce identical keys for identical inputs. The fixture rows at the bottom are reproducible test vectors.

Implemented in `app/domain/services/cache_service.py:cache_key()`.

## Algorithm

```python
def cache_key(fields: dict) -> str:
    canonical = json.dumps(
        fields,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

Key properties:

1. **Sorted keys.** `sort_keys=True`.
2. **No whitespace** between separators.
3. **UTF-8** encoded; non-ASCII characters preserved (`ensure_ascii=False`).
4. **SHA-256** of the canonical bytes; lowercase hex.

The result is a 64-character lowercase hex string.

## Fields

The cache-key dict contains exactly these keys, in any order (sorting is canonical):

| Key | Source | Normalization | Required |
|---|---|---|---|
| `tenantId` | `Principal.tenantId` | none | yes |
| `queryNormalized` | the user query | see "Query Normalization" below | yes |
| `role` | `Principal.role` | none | yes |
| `sessionHash` | `Session.sessionHash` if follow-up; otherwise `null` | none | yes (may be `null`) |
| `answerMode` | resolved `RetrievalPlan.answerMode` | none | yes |
| `corpusVersion` | active `tenants.config.corpusVersion` | none | yes |
| `promptVersion` | active prompt-version row for the A5 route | none | yes |
| `modelRouteId` | the certified A5 `ModelRoute.routeId` | none | yes |
| `schemaVersion` | `ACTIVE_SCHEMA_VERSION` | none | yes |
| `configVersion` | `tenants.config_version` | none | yes |
| `calendarVersion` | `tenants.config.calendarProfile.version` | none | yes |

No additional keys are permitted. Adding a key changes every existing cached entry's key and is therefore a cache-flush event; add only with a documented version bump.

## Query Normalization

```python
def normalize_query(q: str) -> str:
    q = unicodedata.normalize("NFKC", q)
    q = q.casefold().strip()
    q = " ".join(q.split())   # collapse internal whitespace
    return q
```

- NFKC (Unicode canonical compatibility composition).
- Casefold (full Unicode lowercase, including Greek).
- Strip leading/trailing whitespace.
- Collapse internal whitespace runs to a single space.

Diacritics, punctuation, and word-internal characters are **preserved** (unlike the A6 quote-overlap normalization, which is more aggressive). The cache key is sensitive to punctuation and accents because two genuinely different queries should not collide on cache.

## Standalone vs Follow-up

- **Standalone query**: `sessionHash = null`. Standalone queries can share a cache entry across users in the same tenant/role/version scope.
- **Follow-up**: `sessionHash` is the stable hash of (`sessionId` + `tenantId`) per `docs/schemas/session.schema.json`. Follow-ups never share a cache entry with standalones (the `null` vs string difference flips the canonical JSON and the hash).

## Invalidation

Bumping any of these versions invalidates the entire cache scope tied to it:

- `corpusVersion`: tenant-wide flush of cached answers from that corpus.
- `promptVersion` / `modelRouteId` / `schemaVersion`: global (cross-tenant) effective flush, since old keys never match.
- `configVersion` / `calendarVersion`: tenant-wide flush.
- Tenant `status` change to non-`active`: keys still hash, but the auth layer rejects upstream so the cache is unreachable.

The cache itself does not delete old entries; expired keys roll off via the 1-hour TTL (per ADR 0005). Active key changes simply stop hitting old entries.

## Reference Test Vectors

Each vector lists the input dict, the canonical JSON the algorithm produces, and the expected SHA-256. An implementation passes if for each row, hashing the canonical JSON produces the listed `sha256`.

### V1 — Standalone English query, member role

Input:
```json
{
  "tenantId": "tn_orthodoxethos",
  "queryNormalized": "what do the fathers teach about prayer?",
  "role": "member",
  "sessionHash": null,
  "answerMode": "consensus",
  "corpusVersion": "2026-05-01.1",
  "promptVersion": "a5_compose@2026-05-01.1",
  "modelRouteId": "a5_compose_anthropic@2026-05-01.1",
  "schemaVersion": "2026-05-01.1",
  "configVersion": "2026-05-01.1",
  "calendarVersion": "2026-05-01.1"
}
```

Canonical JSON (no whitespace, sorted keys):
```
{"answerMode":"consensus","calendarVersion":"2026-05-01.1","configVersion":"2026-05-01.1","corpusVersion":"2026-05-01.1","modelRouteId":"a5_compose_anthropic@2026-05-01.1","promptVersion":"a5_compose@2026-05-01.1","queryNormalized":"what do the fathers teach about prayer?","role":"member","schemaVersion":"2026-05-01.1","sessionHash":null,"tenantId":"tn_orthodoxethos"}
```

SHA-256: `3747051a45549400be4f16d9340761023c213ec49bbc494096957c49a3b24478`

### V2 — Same scope, follow-up turn with sessionHash

Input differs from V1 only in `sessionHash` and `queryNormalized`:

```json
{
  "...same versions and role as V1...",
  "queryNormalized": "tell me more.",
  "sessionHash": "sh_5f2a"
}
```

Canonical JSON:
```
{"answerMode":"consensus","calendarVersion":"2026-05-01.1","configVersion":"2026-05-01.1","corpusVersion":"2026-05-01.1","modelRouteId":"a5_compose_anthropic@2026-05-01.1","promptVersion":"a5_compose@2026-05-01.1","queryNormalized":"tell me more.","role":"member","schemaVersion":"2026-05-01.1","sessionHash":"sh_5f2a","tenantId":"tn_orthodoxethos"}
```

SHA-256: `002b80c9435eedc48f06966d5328883e63fae49d4a25162165937dfa2e9320d3`

### V3 — Standalone Greek query, scholar role

Input differs from V1 in `role` and `queryNormalized`:

```json
{
  "...same versions as V1...",
  "queryNormalized": "τί διδάσκουν οἱ πατέρεσ περὶ προσευχῆσ;",
  "role": "scholar",
  "sessionHash": null
}
```

(Note the trailing `σ` instead of `ς` in `πατέρες` and `προσευχῆς`. Casefold maps Greek final-sigma `ς` → `σ` per Unicode standard. This is intentional and stable.)

Canonical JSON:
```
{"answerMode":"consensus","calendarVersion":"2026-05-01.1","configVersion":"2026-05-01.1","corpusVersion":"2026-05-01.1","modelRouteId":"a5_compose_anthropic@2026-05-01.1","promptVersion":"a5_compose@2026-05-01.1","queryNormalized":"τί διδάσκουν οἱ πατέρεσ περὶ προσευχῆσ;","role":"scholar","schemaVersion":"2026-05-01.1","sessionHash":null,"tenantId":"tn_orthodoxethos"}
```

SHA-256: `ccf8de99418794534e41615ba8c81519155ca84dbbda2656b52b0fd1fcc3b0c8`

> Correction (2026-05-02): the previous published V3 SHA-256 (`9768d2ed...`) was incorrect for the canonical JSON shown above. The corrected value matches `sha256` of the canonical bytes literally. Implementations writing the V3 unit test must hash to the corrected value.

### V4 — Standalone English query, calendar-profile bump

Same as V1 except `calendarVersion` and `configVersion` advanced (e.g., the tenant changed `calendarProfile.paschalion` from `julian` to `gregorian`, which bumps both versions per `safe tenant config` change rules).

```json
{
  "tenantId": "tn_orthodoxethos",
  "queryNormalized": "what do the fathers teach about prayer?",
  "role": "member",
  "sessionHash": null,
  "answerMode": "consensus",
  "corpusVersion": "2026-05-01.1",
  "promptVersion": "a5_compose@2026-05-01.1",
  "modelRouteId": "a5_compose_anthropic@2026-05-01.1",
  "schemaVersion": "2026-05-01.1",
  "configVersion": "2026-05-01.2",
  "calendarVersion": "2026-05-02.1"
}
```

Canonical JSON:
```
{"answerMode":"consensus","calendarVersion":"2026-05-02.1","configVersion":"2026-05-01.2","corpusVersion":"2026-05-01.1","modelRouteId":"a5_compose_anthropic@2026-05-01.1","promptVersion":"a5_compose@2026-05-01.1","queryNormalized":"what do the fathers teach about prayer?","role":"member","schemaVersion":"2026-05-01.1","sessionHash":null,"tenantId":"tn_orthodoxethos"}
```

SHA-256: `2c15b2345f7c327e7ca29cd904da3f490b7532c055a74dad72c9671fcd121c19`

V4 must NOT collide with V1: a `calendarProfile.version` change is a tenant-wide cache flush per `tenants.config.calendarProfile.version`. The shape of `calendarProfile` itself is defined in `docs/schemas/calendar-profile.schema.json`.

## Verification

The unit test `tests/unit/test_cache_key.py` (added in T-005) hashes V1, V2, V3 and asserts equality with the SHA-256 values above. Any implementation change that breaks these tests must bump `schemaVersion` or `promptVersion`/`modelRouteId` as appropriate, accept the cache flush, and update this document.

## Forbidden

- Building cache keys with string concatenation or f-strings.
- Including any field not on the table above (e.g., timestamps, request IDs, IP addresses).
- Hashing with anything other than SHA-256.
- Trimming or modifying `queryNormalized` after `normalize_query` runs.
- Reading `tenantId` from anywhere other than `Principal`.
