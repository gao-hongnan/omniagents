---
name: api-design
description: >-
  Use when designing, reviewing, or implementing a REST or gRPC API
  contract: resource hierarchy, standard vs custom methods, pagination,
  filtering, field masks, long-running operations, error models,
  idempotency, etags, batch methods, versioning, or breaking changes —
  grounded in Google's AIPs.
when_to_use: >-
  Trigger for .proto files, OpenAPI / Swagger specs, endpoint lists, the API
  section of a design doc, and asks like "design an endpoint", "review this
  API", "is this a breaking change", or "cite the AIP".
argument-hint: "[design|review|implement|evolve] <spec, proto, or feature>"
disable-model-invocation: false
user-invocable: true
allowed-tools:
  - "WebSearch"
  - "WebFetch(domain:google.aip.dev)"
  - "WebFetch(domain:raw.githubusercontent.com)"
  - "WebFetch(domain:docs.cloud.google.com)"
  - "WebFetch(domain:protobuf.dev)"
  - "WebFetch(domain:linter.aip.dev)"
---

# API Design — Google AIPs, retrieved and cited

This skill deliberately encodes **no Google API rules**. Google's guidance
lives in the API Improvement Proposals at `google.aip.dev`, and it moves:
AIP-184 and interface-based versioning landed on 2026-08-17, and AIP-136,
AIP-164, and AIP-203 all changed earlier in 2026. Model priors on AIPs are
reliably stale on exactly the details reviewers check — the requirement
level, the condition a rule applies under, and its exceptions.

What this encodes instead: **where each rule lives, how to retrieve it
faithfully, how to label and cite every claim, and the house conventions for
design docs, reviews, and code.** Searching and retrieving mid-task is always
allowed and expected. A retrieval costs seconds; a misremembered rule costs a
redesign.

## Step 0 — anchor, before anything else

Establish these from the repo, or ask once. Each one changes the answer.

| Anchor             | Why it decides the answer                                                                    | Evidence                                                                         |
| ------------------ | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| **Mode**           | Quick question, design, review, implement, or evolve — sets retrieval depth and output shape | The ask                                                                          |
| **Surface**        | Proto-first, REST/OpenAPI-only, or both via transcoding — decides where wire facts come from | `*.proto`, `buf.yaml`, `openapi*.y*ml`, framework route files                    |
| **Release status** | Unreleased or live, and its stability level. On a live API the "fix" can be the breaking change | Version paths, changelogs, known clients                                       |
| **Local standard** | Team standards and existing-surface conventions can outrank AIPs (see Precedence)            | `docs/api*`, `.api-linter.yaml`, `.spectral.y*ml`, sibling specs, org AIPs       |
| **Consumers**      | One team, an internal platform, or external — sets the ceremony tier                         | Ask                                                                              |
| **Domain**         | If you cannot name each resource's parent and the top use cases, ask before designing        | —                                                                                |

## Research protocol — retrieve what you cite, cite what you retrieved

**No AIP number, AIP link, or must / should / may attributed to Google
appears in your output — prose, table, code comment, or review finding —
unless that AIP was retrieved in this session and the retrieved text contains
the claim, including its condition.**

Retrieval methods, best first:

1. **context7 `/aip-dev/google.aip.dev`** — verbatim AIP markdown with the
   bold keywords intact. Chunks can omit an exception stated elsewhere on the
   page, so read the page's Guidance section before a rule becomes
   load-bearing. Results link GitHub blobs; cite the rendered
   `https://google.aip.dev/{n}` instead.
2. **Raw source, with a shell** — exact text, headings plus every normative
   line:
   `curl -fsSL https://raw.githubusercontent.com/aip-dev/google.aip.dev/master/aip/general/0158.md | grep -nE '^#{1,4} |\*\*(must|should|may)( not)?\*\*'`.
   Numbers are four-digit zero-padded; scoped AIPs live under
   `aip/{scope}/`. Lines wrap, so read neighbours with `sed -n`.
3. **Fetch the rendered page** (WebFetch in Claude Code) with the extraction
   prompt below. Fetch tools summarize: generic prompts drop levels and
   conditions, and verbatim requests are sometimes refused and, when
   honoured, still skip exceptions. Ask per rule, and name the exceptions
   you need.
4. **Search** — discovery only, to learn *which* AIP. Never cite a search
   result or its summary.

Extraction prompt: *"From AIP-{n}, for each rule about {topic}: its sentence
(quoted if short), the requirement keyword exactly as bolded (must, must
not, should, should not, may), its section heading, what it constrains, and
any condition or scope
(management plane, declarative-friendly, 'if present', existing APIs only).
List exceptions. Say 'silent' if the page does not address {question}. Give
the page state (approved, draft, reviewing)."*

**Depth by mode:**

- **Quick question:** the governing AIP only — one or two retrievals.
- **Review:** one AIP per finding category present in the spec.
- **Design:** core set plus triggered set. Core: 121, 122, the standard
  methods used (131–135), 158 if any List exists, 193, 185. Proto adds 127,
  191, 192, 203. REST/OpenAPI adds 127, 203, and the ProtoJSON mapping.
  Data-plane methods (predictions, uploads, streams) add 111. Triggered: an
  AIP only when the design contains its subject — route via
  [`references/aip-map.md`](references/aip-map.md).
- **Implement:** reuse the design's ledger; retrieve only behaviour the
  design left open.
- **Evolve:** 180 and 185 (plus 184 for date or header versions), then the
  AIPs of whatever changes.
- **Design and review:** read the index `https://google.aip.dev/general`
  once per session. Note any task-relevant AIP missing from the map and every
  Draft or Reviewing badge.

**Ledger.** Keep one row per source: id · title · URL · state · retrieved
(date, method) · claims used (keyword + condition). References are built from
it. Never retrieve a page twice, except to verify a claim verbatim once it
becomes load-bearing (a must, a blocker, a deviation).

**On failure,** keep the decision, write `AIP-n (unverified: not retrieved
YYYY-MM-DD)` with no level, and list it under Open questions. Never
substitute memory or a search snippet. Never guess a URL or an anchor.

## When to retrieve — observable triggers

Retrieve before writing the sentence when any is true:

1. You are about to state a Google-attributed specific — field name, verb,
   URI pattern, error or status code, standard field, or requirement keyword
   — and its source is not in the ledger.
2. You recall an AIP number or rule you have not retrieved this session.
3. The topic is not in the map: translate the user's words with the map's
   vocabulary table, then search.
4. Sources disagree (AIP vs AIP, AIP vs Design Guide, AIP vs precedent), or
   a retrieved summary surprises you.
5. The surface is not proto-shaped (REST-only, webhooks, streaming, file
   transfer, framework routing): confirm the AIP applies at all; wire facts
   come from [SPEC] sources.
6. The AIP is not approved, or it is on the map's stale-priors list.
7. The claim will carry a must, a blocker, or a deviation — verify it
   verbatim.
8. You are about to link an anchor you have not seen in retrieved text.

Do not search for domain modelling (ask the user), team conventions (grep
the repo, then ask once), or anything already in the ledger.

**Search mechanics:** query `google aip <AIP term>` — bare "AIP" also
matches unrelated products. Restrict rule searches to `google.aip.dev`
(`allowed_domains` in Claude Code) and discard off-domain hits; the filter
leaks. Retry once with another AIP term, then scan the index titles. Open
the page before using it.

Priors known to be stale — check the map's
[stale-priors list](references/aip-map.md#stale-priors) before relying on
recall for versioning (184/185), errors (193), custom-method verbs (136),
update masks (134), soft delete (164), batch atomicity (233–235), or field
behaviour (203).

## Claims and citations

Every justifying claim carries exactly one type. **Only [AIP] may say must,
should, may, or requires.**

| Type            | Use for                                                       | Write it as                                                                                   |
| --------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| **[AIP]**       | A rule in an approved AIP, in the ledger                      | "A negative `pageSize` fails with `INVALID_ARGUMENT` ([AIP-158](https://google.aip.dev/158), must)." Keep any condition. |
| **[AIP-DRAFT]** | A Draft or Reviewing AIP                                      | "AIP-162 (draft) recommends …" — informative, never "requires"                               |
| **[SPEC]**      | Wire facts AIPs delegate: ProtoJSON, `google.rpc.Code`, RFCs  | Link the spec                                                                                 |
| **[PRECEDENT]** | What a beta or GA Google API does                             | "Vertex AI v1 exposes `…:predict` (link)." Shows feasibility, not conformance                |
| **[TEAM]**      | Team standard or existing-surface convention                  | Link the doc or file                                                                          |
| **[JUDGMENT]**  | Our tradeoff                                                  | "We choose X because Y; alternative Z." No AIP link. "AIPs are silent on X" is a valid claim  |

- Cite once per decision (one cluster per method contract), not per field.
  Decision tables carry a **Basis** column.
- Link an anchor only when you saw its ID; otherwise link the page and name
  the section ("AIP-193 §Permission Denied").
- Paraphrase. Quote only when exact wording settles a dispute: 15 words or
  fewer, one quote per page at most. This is house style, not a licence term.
- Deviation: "Deviation from AIP-n (linked, with its level): what · why ·
  who decided · cost to reverse."
- Every design doc and review ends with References (id · title · URL ·
  state · retrieved date) and the attribution line in
  [`references/design-doc.md`](references/design-doc.md#references-and-attribution).
  AIP text is CC BY 4.0; AIP code samples are Apache 2.0.

## Precedence when sources conflict

**Floor — never overridden silently:** correctness (errors are never 2xx;
verbs keep their semantics), security (authorization before existence;
nothing leaks), data integrity. If anything below conflicts with the floor,
flag it and ask.

Then, highest first:

1. The user's explicit instruction for this task.
2. Compatibility of a live API (AIP-180).
3. Consistency with the existing surface (AIP-200, "Local consistency").
4. The written team standard — org-specific AIPs (see the map's source
   mechanics), style guide, lint config.
5. Approved AIPs: must over should over may. AIP vs AIP: cite both with
   their levels, prefer the more specific AIP for its own method, flag it.
6. [SPEC] · 7. [PRECEDENT] · 8. Draft or Reviewing AIPs · 9. [JUDGMENT].

Rows 2–3 apply to existing surfaces only. Record every conflict in the
Deviations table; never pick silently.

## Calibrate ceremony

**Adopt now what is breaking to add later; defer what is additive.** Copy
no Google infrastructure — `projects/*/locations/*` parents, `*.googleapis.com`
names, Google IAM permission strings, `X-Goog-*` headers, `google.cloud.*`
packages — unless the org genuinely has those concepts; the map flags
Google-specific guidance. Every heavyweight feature (a hierarchy level, an
LRO, etags, request IDs, batch, soft delete) carries a one-line reason or
moves to "Future additive options". The tier table is in
[`references/design-doc.md`](references/design-doc.md#calibration-tiers).

## Red flags — stop and retrieve

- You typed "AIP-" and the number is not in your ledger.
- You wrote must where the retrieved sentence says should, or dropped its
  condition ("if present", "management plane", "declarative-friendly").
- You cited an AIP for a JSON wire detail (casing, timestamp format, success
  status) — that is [SPEC], or "AIPs are silent".
- A Google product's behaviour or a search summary is presented as a rule.
- A Draft or Reviewing AIP is phrased as a requirement.
- You appended `#…` to an AIP URL you have not seen.
- A team-standard vs AIP conflict was resolved without a Deviations row.
- You proposed an in-place rename on a live API.

## Route by mode

| Mode              | Read                                                                 | Output                                                                     |
| ----------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Quick question    | `aip-map.md`                                                         | Ten lines or fewer, claim types, one or two citations, no template         |
| Design            | `aip-map.md`, `design-doc.md`; `rest-and-openapi.md` for REST        | The API section, per the template                                          |
| Review            | `aip-map.md`, `review.md`; `rest-and-openapi.md` for REST            | Findings → top three → already right → References                          |
| Implement         | `implement.md`, `rest-and-openapi.md`                                | Code, tests, and in-code citations                                         |
| Evolve a live API | `review.md` § Evolving a live API, `aip-map.md`                      | Each change classified additive or breaking, with a migration path         |

All files are under [`references/`](references/). A quick question that
turns out to imply a full design should say so and offer the design.

## Verify before delivering

1. Every [AIP] sentence maps to a ledger row retrieved this session; its
   keyword and condition match the source.
2. Every must, blocker, and deviation was verified verbatim (context7 or raw
   source).
3. Grep the deliverable for `must|should|requires|required|mandat|per AIP`.
   Each hit is a cited [AIP] claim, or it gets reworded.
4. [SPEC], [PRECEDENT], and [JUDGMENT] sentences carry no AIP link, except
   "AIPs are silent on …".
5. Every URL was opened this session; anchors appear only where seen.
6. One casing, one time encoding, one error envelope, and one pagination
   shape throughout. JSON examples parse and match the tables.
7. Live API: every change is labelled additive or breaking, with a
   migration path.
8. Every heavyweight feature carries a reason or sits in Future additive
   options.
9. References are complete — dated, with state — and the attribution line is
   present.

## What this skill does NOT cover

- **Choosing the channel** — sync vs async, REST vs gRPC vs GraphQL,
  pub/sub, webhooks, streaming, gateway/BFF/mesh topology. Load the `system`
  skill from this plugin
  ([`../system/communication.md#picking-a-shape`](../system/communication.md#picking-a-shape)).
  This skill starts once a request/response API is the chosen shape.
- **Reliability machinery behind the contract** — timeouts, retry budgets,
  rate limits, and how an idempotency key is stored and replayed
  ([`../system/reliability.md#idempotency-keys`](../system/reliability.md#idempotency-keys)).
  This skill owns the request field and its promised semantics; `system`
  owns the mechanism.
- **Async work outside AIP style** — `202 + Location + Retry-After` job
  polling belongs to `system`
  ([`../system/communication.md#asynchronous-request-reply`](../system/communication.md#asynchronous-request-reply)).
  When the API follows AIPs, the long-running-operation AIP governs the
  contract and `system` governs the worker behind it.
- **In-process interfaces** — module depth, seams, wrappers. "Interface"
  here means a network API; load `codebase-design` for code-level interfaces.
- **Client SDKs** — construction, retries, timeouts, auto-paging, exception
  hierarchies. Load `python:library-patterns` or
  `typescript:library-patterns`. An SDK for an AIP-style API mirrors the
  server's field names.
- **Code review of a diff** — correctness, security, performance, and design
  findings belong to `omniagents-reviewer`. This skill grades a contract
  against AIPs, borrowing the reviewer severity scale; it does not emit
  reviewer JSON or join `/review`.
- **Release mechanics** — tags, changelogs, package semver. This skill says
  whether an API change is breaking; a release-workflow skill, where
  installed, says how to ship it.
- **AuthN/AuthZ mechanisms, GraphQL schemas, AsyncAPI and event payloads** —
  AIPs do not govern them. Say so rather than bending an AIP to fit. This
  skill records only the permission each method requires.
- **Document craft** — Markdown hygiene is `writing:markdown-conventions`;
  persuasive framing is `writing:measured-persuasion`. This skill supplies
  the API section's content and its citations.

## Freshness

The map was verified against `google.aip.dev` at upstream commit `615875b`
(2026-10-07) on 2026-10-11. Re-read the index when the map is more than six
months old or the index lists AIPs the map lacks. New Google facts belong in
the map as rows or stale-prior prompts — never as stances in this file.
