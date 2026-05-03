# Quote-Overlap Algorithm (A6 Verification)

Status: Canonical
Date: 2026-05-01

A6 verifies that every claim in the composed answer is supported by the cited chunk. The default supporting check is **shingle-based quote overlap with a 0.70 threshold**. This document is the reference algorithm — A6 implementations must match it exactly so that the threshold remains comparable across runs and providers.

## Inputs

- `claim_text`: the candidate substring or sentence from the answer being verified.
- `source_text`: the `text` field of the cited chunk from `EvidencePacket.admittedChunks[i]`.
- Both strings are UTF-8.

## Output

- `ratio` ∈ [0.0, 1.0] — fraction of `claim_text` shingles that also appear in `source_text`.
- A6 passes the citation when `ratio ≥ 0.70`.

## Algorithm

```
def quote_overlap(claim_text: str, source_text: str) -> float:
    claim_tokens  = normalize(claim_text)
    source_tokens = normalize(source_text)

    n = 5  # shingle size
    if len(claim_tokens) < n:
        # short claims: fall back to exact-substring containment in normalized form
        return 1.0 if " ".join(claim_tokens) in " ".join(source_tokens) else 0.0

    claim_shingles  = make_shingles(claim_tokens, n)
    source_shingles = make_shingles(source_tokens, n)

    if not claim_shingles:
        return 0.0

    intersection = claim_shingles & source_shingles
    return len(intersection) / len(claim_shingles)
```

### `normalize(text)`

1. **Unicode normalize** to NFKC.
2. **Lowercase** with default Unicode casefolding (`str.casefold()` in Python).
3. **Strip combining diacritics** for the purposes of overlap *only* (do not mutate stored text). Use `unicodedata.normalize("NFD", s)` and drop characters with `unicodedata.category(c) == "Mn"`. This handles polytonic Greek breathings/accents and common Latin diacritics uniformly.
4. **Replace** every Unicode-category-`P` punctuation character with a single space.
5. **Collapse** consecutive whitespace to a single space and strip.
6. **Tokenize** on whitespace.

### `make_shingles(tokens, n)`

Return the set of contiguous n-grams of length `n` joined by single spaces. Implementation uses a Python `set` so duplicate shingles count once (this is intentional — repeated boilerplate should not inflate overlap).

```
def make_shingles(tokens, n):
    return {" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)}
```

## Language Handling

- English and Greek both use the same algorithm.
- The diacritic-stripping step in `normalize` makes polytonic and monotonic Greek interoperable. Iota subscript is preserved (it is not category `Mn`).
- For mixed-language source chunks (`language: "mixed"`), the algorithm runs unchanged — shingles cross language boundaries naturally because the boundary is whitespace.

## Threshold

- Default: **0.70**. Tenant-tunable via safe config field `quoteOverlapThreshold` (range 0.50–0.95). Value below 0.50 is rejected by config validation per ADR 0002 / safety policy.
- A6 records the actual ratio per citation in the run trace so threshold changes are auditable.

## Test Vectors

Each vector lists `(claim_text, source_text, expected_ratio_rounded_to_2dp)`. Implementations must match within ±0.01.

### V1 — Exact match

```
claim:  "Pray without ceasing, says the Apostle."
source: "The Apostle teaches us: pray without ceasing, says the Apostle, in every season."
expected: 1.00
```
After normalization both produce a claim shingle set of 4 shingles, all of which appear in source.

### V2 — Partial paraphrase

```
claim:  "The fathers teach prayer is constant communion with God."
source: "Saint John writes that prayer is constant communion with God for those who seek Him."
expected: 0.50
```
Claim has 7 shingles (n=5); 3 of them match (`prayer is constant communion with`, etc., depending on tokenizer; reference implementation produces 3/6 ≈ 0.50 after normalization drops "the" boundaries).

### V3 — No overlap (different topic)

```
claim:  "The liturgy begins with the great litany."
source: "Saint Basil writes about almsgiving and care for the poor."
expected: 0.00
```

### V4 — Diacritic-insensitive Greek

```
claim:  "Κύριε ἐλέησον"
source: "ψάλλομεν Κυριε ελεησον τρίτον"
expected: 1.00
```
The claim has 0 full shingles at n=5 (only 2 tokens), so the short-claim fallback applies: normalized claim `"κυριε ελεησον"` appears in normalized source. Returns 1.0.

### V5 — Short claim, fallback hit

```
claim:  "ancestral sin"
source: "Orthodox theology distinguishes ancestral sin from original sin."
expected: 1.00
```
Claim < n tokens → fallback: normalized claim `"ancestral sin"` contained in normalized source. Returns 1.0.

### V6 — Short claim, fallback miss

```
claim:  "ancestral sin"
source: "Orthodox theology speaks of original guilt and inherited mortality."
expected: 0.00
```
Claim < n tokens → fallback: not contained. Returns 0.0.

## A6 Integration Notes

- A6 runs `quote_overlap` once per `(claim, citationId)` pair.
- A claim may be supported by *any* cited chunk. A6 takes the maximum ratio across the claim's citations and compares to threshold.
- If max ratio < threshold, the citation fails and the run handling becomes `insufficient_evidence` (or YELLOW with disclaimer if `sensitiveHandlingStrictness=standard` and the claim is non-doctrinal — see ADR 0002).
- Lineage claims ("X quotes Y", "X builds on Y") are **not** verified by quote overlap. They are verified by approved-edge presence in `EvidencePacket.lineageContext` per ADR 0006.
- The optional certified low-cost consistency judge (ADR 0004) runs *after* deterministic overlap. It can downgrade GREEN→YELLOW but cannot upgrade or override a deterministic miss.

## Forbidden Variants

A6 implementations must not:

- Use cosine similarity over embeddings as a substitute for shingle overlap.
- Use LLM-based "is this supported?" without first passing the deterministic check.
- Vary `n` per language (the algorithm is uniform).
- Ignore the diacritic-stripping step (it is required for Greek).
- Use a Jaccard denominator (`|A ∪ B|`); the denominator is `|claim_shingles|` (asymmetric containment) so that long source chunks do not dilute the score.
