# Python production-bar skill upgrades — source dossier

- **Date:** 2026-08-30
- **Status:** applied and verified (§6 re-audit passed all expectations)
- **Trigger:** An audit of `/Users/gaohn/gaohn/packages/hypervigilant/hypervigilant/objectstore` — run with `omniagents-design-patterns:software`, `omniagents-python:typings`, and `omniagents-python:pydantic` explicitly consulted — failed to flag smells the maintainer identified by eye. This dossier is the source of truth for the edits that followed and for future edits to the skills named here. Every rule that survives into the skills must be traceable to §1 (evidence), §3 (stances), or already-verified content in the existing SKILL.md files.

## 1. Evidence: the objectstore catalog

Package: 13 files, ~4.9k LOC, substantial unit + contract tests. Mature in most respects — 16 frozen `extra="forbid"` pydantic models with cross-field validators (`config.py`, `options.py`), 10 `StrEnum`s, `Final` constants, value objects (`ObjectKey`, `ETag`, `ByteRange`). The smells below are real, narrow, and (the key fact) **each is defended in a module docstring** — an audit that reads those docstrings defers to them unless the skill tells it to adjudicate.

| Smell | Evidence |
|---|---|
| `_as_*` isinstance-coercion family | 9 helpers, 72 call sites, all in `backends/s3.py` (e.g. `_as_str` :114, `_as_int` :118, `_as_optional_int` :122). Includes the `isinstance(x, int) and not isinstance(x, bool)` dance ×3. Docstring :36-40 defends it ("responses are narrowed, not trusted") |
| Value fabrication (~14 sites) | `ETag(_as_str(...) or "")` ×5 (:439, :489, :511, :635, :650); `or "Unknown"` :375; `_EPOCH` sentinel for missing dates :697; `_as_int(...)` defaulting to fabricated `0` :634 — which `models.py:207-210` itself criticizes |
| Plain alias as fake domain type | `type BucketName = str` (`keys.py:96`) — zero static distinctness; docstring :3-5 argues against NewType ("runtime validation is the entire point") |
| Duplicated defaults / two-owner constants | `"us-east-1"` ×2 (`config.py:418`, `:771`); `prefix_segments=2` in 3 signatures + config = 4 owners (`keys.py:146`, `:285`, `:316`, `config.py:626`); inline `3`/`63` duplicating `MIN/MAX_BUCKET_NAME_LENGTH` (`config.py:114` vs `keys.py:85-86`); `_METADATA_KEY_PATTERN` ×2 modules (`config.py:106`, `options.py:32`) |
| Copy-pasted guards across backends | batch-size, metadata-budget, conditional-multipart guards byte-identical between `s3.py` and `memory.py`; `_context()` triplicated |
| Unvalidated `str` on pydantic models | `if_match`, `content_type`, `region` (`min_length=2` only) in `options.py` / `config.py` |
| Deliberate choices worth respecting | No `BaseSettings` — argued `config.py:15-34` (consumer owns the env namespace); dataclasses for own-trusted outputs — argued `models.py:3-7` |

## 2. Diagnosis: three-link failure chain

1. **Delivery (audit mode).** The reviewer design specialist's context is its agent prompt + preloaded SKILL.md bodies. `design-review`'s 8 hunts and Recall Sweep never mention primitives, magic values, config consolidation, or coercion helpers — "primitive obsession" appears once, in frontmatter triggers only — so nothing sends the reviewer to `anti-patterns.md` (not preloaded) or to pydantic content (not preloaded by `agents/design.md` at all).
2. **Content (author/consult mode).** The consulted skills don't name the smells: no `_as_*` coercion smell anywhere; no consolidation bridge (typings promotes magic numbers into *more* scattered `Final` constants; pydantic shows greenfield `BaseSettings`, never migration from scattered constants); NewType guidance is alias-first ("Default to a `type` alias") with no rule for when the checker *must* distinguish; no openai-python-style domain-ID example in the plugin; typings is the only python skill with no review-facing Traps/Anti-Patterns section.
3. **Adversarial cases.** Smells defended by module docstrings, and `anti-patterns.md`'s own `type-erosion` Fixed example *endorsing* hand-rolled isinstance boundary validation. Nothing tells a reviewer that a docstring defending a pattern is a claim to adjudicate, not authority to defer to.

## 3. Stances (the bar the skills now encode)

Target confirmed with the maintainer: the **applicable openai-python subset** — not SDK machinery (`NotGiven`, `construct_type`).

1. **NewType for domain IDs at boundaries.** Where two same-shape primitives could be swapped across signatures (ids, tokens, bucket/key names), use `NewType("BucketName", str)`; a bare `type X = str` alias carries zero static information and only names a primitive.
2. **Literal / StrEnum for closed sets** (already covered; reinforced).
3. **Pydantic at every parse boundary.** Untrusted payloads (`dict[str, object]` from SDKs, env, JSON) are parsed by a `TypeAdapter` or boundary `BaseModel` — not by per-field isinstance-coercion helpers. Strict int-not-bool, declared shapes, and error paths come free.
4. **TypeIs for checker-only narrowing** — a sound predicate, not a coercer.
5. **Configuration is consolidated, single-owner.** Values that are configuration (timeouts, retries, budgets, URLs, env-read values) live in one settings tree (pydantic `BaseSettings`/frozen `BaseModel` config object), defaults referenced — never re-stated in signatures or duplicated across modules. A default with two owners has already drifted.
6. **No value fabrication.** `or ""`, sentinel `_EPOCH`, default `0` for missing data fabricate values indistinguishable from real ones — model `Optional` and make absence explicit.
7. **Docstring rationale is a claim, not authority.** When code defends a pattern in prose, the review adjudicates the claim against these stances; it does not defer.
8. **Respect argued exceptions on their merits.** A library config that deliberately nests into the consumer's settings object, or dataclasses for own-trusted outputs, can be right — the review engages the argument rather than pattern-matching "no BaseSettings = bad".

## 4. What this is not

- Not a mandate to wrap every primitive (see `anti-patterns.md` primitive-obsession "When NOT to refactor").
- Not a demand for `BaseSettings` inside reusable libraries — the consumer-owned-namespace pattern (objectstore `config.py`) is a legitimate stance-8 exception.
- Not SDK machinery emulation.

## 5. Edit map (shipped)

| Target | Change |
|---|---|
| `plugins/python/skills/typings/SKILL.md` | new `## Traps reviewers should catch`; NewType section rebalanced to boundary-driven rule; `Final` rule routes config values to pydantic Settings; frontmatter trigger vocabulary added |
| `plugins/python/skills/typings/references/decision-trees.md` | Type Alias vs NewType vs Subclass: alias-default → boundary-driven |
| `plugins/python/skills/typings/references/canonical-examples.md` | `FileId`-style NewType domain-ID example; TOC added |
| `plugins/python/skills/pydantic/SKILL.md` | TypeAdapter positioned as coercion-helper replacement; Anti-Patterns +2 (isinstance coercion at parse boundary; scattered constants as config); Settings migration move |
| `plugins/python/skills/library-patterns/SKILL.md` | Domain-identifiers passage (NewType IDs + Literal params, openai-python canon); `Table(str, Enum)` → `StrEnum`; `Union[str, int]` → `str \| int` |
| `plugins/design-patterns/skills/software/anti-patterns.md` | new entries `scattered-configuration` and `hand-rolled-boundary-coercion`; `type-erosion` Fixed example re-routed to pydantic; magic-numbers Fixed extended to settings consolidation; TOC; review-checklist additions |
| `plugins/design-patterns/.claude-plugin/plugin.json` | description drift: "two skills" → software + system + codebase-design |
| `plugins/reviewer/skills/design-review/SKILL.md` | new hunt (domain-value discipline) + Recall Sweep bullets |
| `plugins/reviewer/agents/design.md` | preload `omniagents-python:pydantic` |

## 6. Verification

**Mechanics (all pass):** reviewer doctor 0 errors (after fixing a pre-existing Python-2 `except` syntax error in `scripts/doctor.py`); `claude plugin validate` passes for python, design-patterns, reviewer; listing budgets — typings 979, pydantic 738, library-patterns 692, design-review 559 (cap 1,536); body lines — typings 312, pydantic 465, design-review 275, library-patterns 642 (pre-existing overage, split is backlog P2); anti-patterns TOC anchors all resolve; Codex manifests regenerated via `scripts/sync-codex.sh`.

**Re-audit (2026-08-30):** a fresh reviewer agent loaded the updated skills and audited the objectstore slice. It produced 3 IMPORTANT + 4 SUGGESTION findings that cover every §1 smell with the stance-correct remediation:

1. IMPORTANT — the 8-helper `_as_*` family + fabricated values → boundary `BaseModel`s with `T | None` (it found corruption scenarios beyond the catalog: missing `Key` reported as `""` successfully deleted, `_EPOCH` flowing into TTL arithmetic).
2. IMPORTANT — bucket/prefix shape rules with two drifted owners (config pattern accepts IPv4-shaped names `validate_bucket_name` rejects → config-valid, first-backend-construction failure) → single stdlib-only owner.
3. IMPORTANT — `prefix_segments=2` four owners, framed as privacy-policy drift (a PII tightening of the settings field leaves signature-default callers logging more than policy allows) → required kwarg, default only in `SecurityConfig`.
4-7. SUGGESTION — `"us-east-1"` ×2; `dict[str, Any]` kwargs at the boto3 seam despite stubs; `BucketName` costume alias → NewType; stale `TransferConfig` "not read yet" docstring contradiction.

Adjudication was the designed behavior, not deference: the BaseSettings rejection **survived** (sanctioned consumer-owned-namespace pattern), the keys.py NewType rejection **survived for the value objects** while being rejected for the `BucketName` alias, `_reject` logging and `StorageClass._missing_` → `UNKNOWN` **survived** (modeled absence, the opposite of fabrication); the s3 "narrowed, not trusted" defense was split — argument survives, per-field hand-rolled conclusion fails.
