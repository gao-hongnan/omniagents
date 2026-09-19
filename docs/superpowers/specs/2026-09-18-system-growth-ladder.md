# System growth ladder — source dossier

- **Date:** 2026-09-18
- **Status:** applied; verification in §6; release pending (`make release`)
- **Trigger:** The maintainer shared a practitioner post that lays out database scaling as order-of-magnitude rungs (1k → 10k → 100k → 1M RPS), each with "what breaks", a write-path fix, and a read-path fix, and asked whether `omniagents-design-patterns:system` covers that way of thinking. It did not. This dossier is the source of truth for the edits that followed and for future edits to the growth reference. Every rung, anchor, and stance below must be traceable to §1 (evidence), §3 (stances), or already-verified content in the sibling reference files.

## 1. Evidence: the gap audit

Audit target: `plugins/design-patterns/skills/system/` (7 refs, 11,025 lines, hub `SKILL.md` 162 lines). Method: grep for the post's vocabulary and mechanisms, then read every trail head the post's rungs would need.

| Post mechanism | Present in skill? | Where |
|---|---|---|
| Connection pooler multiplexing app sockets onto tens of server connections | yes | `scaling.md#connection-pooling` (HikariCP math, ~10 MB per backend, PgBouncer modes) |
| Cache-aside absorbing hot-key reads, stampede protection | yes | `scaling.md#cache-aside-lazy-loading` (single-flight), `anti-patterns.md#naive-caching` |
| Read replicas + read-your-writes | yes | `data.md#replication`, `data.md#eventual-consistency` |
| Ingest writes to a partitioned log, ack `202`, apply in batches | split across three entries, never framed as one move | `scaling.md#write-behind--write-back`, `communication.md#asynchronous-request-reply`, `communication.md#pubsub-async` |
| Sharded cache via consistent hashing; DB shards by tenant | yes | `scaling.md#load-balancing`, `data.md#sharding` |
| In-process L1 with short TTL and single-flight | yes | `scaling.md#read-through` (sketch), `scaling.md#stacking-caches` (L1/L2/CDN ordering rule) |
| B-tree vs LSM storage engine | **absent** | zero hits for `LSM`, `B-Tree`, `btree`, `IOPS` |
| "What breaks" physics per rung (backend memory, IOPS contention, fsync-bound commits, replica apply lag, single-thread cache node, write amplification) | **absent** as a frame; fragments only | pool memory in `scaling.md`; lag as a correctness issue in `data.md`; no capacity signal table anywhere |
| Load-indexed entry point ("we are at N, going to 10N") | **absent** | `SKILL.md` decision flow routes by axis only; zero hits for `RPS` bands, `order of magnitude` as a threshold, `what breaks` |
| Read/write split as a lens at every rung | only as a pattern to adopt (CQRS) | `data.md#cqrs`; `data.md#the-big-picture` q.4 "Replication first, then Sharding" is the only ladder-shaped line |

Conclusion: roughly 80% of the *mechanisms* exist; what is missing is the *index* (load → saturated resource → move per path → existing entry), the *physics* that makes the next break predictable, and one mechanism (storage engine choice).

## 2. Diagnosis

1. **Catalogue indexed by pattern only.** A user arriving with a number has no route into the skill; the hub asks "which axis", never "which resource saturates next". Fragmented mechanisms (write-behind + async request-reply + pub/sub) are never composed into the single rung-2 move the post describes.
2. **No bottleneck physics.** Entries name the cure and the "When to reach for it" signal, but rarely the resource that saturates or the metric that proves it, so the skill can react to a bottleneck but not predict the next one.
3. **One real hole.** Storage-engine choice (B-tree vs LSM) is a system-shape decision at the write-amplification rung and appears nowhere in the plugin.

## 3. Stances (what the skill now encodes)

1. **Anchors, not triggers.** RPS figures per rung describe one reference workload (OLTP, ~1 KB rows, working set in RAM through rung 1, ~10:1 reads to writes, indexed point queries). Payload size, working-set ratio, write mix, fan-out, and node size move every anchor by up to an order of magnitude. The trigger is the measured saturation signal (USE method per resource), never the RPS number.
2. **One move per path per rung.** Every rung names what breaks, the signal, a write-path move, a read-path move, the contracts the move creates, a stop sign, and links to the entries holding the sketches. Reads and writes diverge from rung 1 on; that is lightweight CQRS reached by necessity, not adopted upfront.
3. **Contracts accumulate; rungs stay.** Every copy adds a staleness contract; every async write adds an idempotency contract; every shard adds a key discipline. A higher rung never removes a lower rung's mechanism.
4. **Never skip a rung.** Kafka at rung 0 and sharding at rung 1 buy the contracts without the throughput problem; the skill names this as an anti-ladder failure and points at the existing premature-adoption entries.
5. **Storage engine is a per-table decision at rung 3**, taken only after the write path has been batched (rung 2). Modelled with the RUM trade (read / update / memory amplification); the relational core stays relational.
6. **The post's numbers are corrected, not transcribed.** A single Postgres serves 1k simple RPS; what breaks at rung 1 is connection count and IOPS contention, not RPS. A Redis node is on the order of 10⁵ simple ops/s *without pipelining*, far more with it. LSM is a write-amplification trade against read amplification and compaction stalls, not "migrate to Cassandra". DynamoDB is not asserted to be an LSM engine (its engine is not public).
7. **No duplicated sketches.** `growth.md` holds one typed sketch (Little's Law sizing) and otherwise cross-links; every link is verified against the target file's headings by slug.
8. **Scale-up remains available at every rung** and shifts anchors by a constant, never the shape of what breaks. `scaling.md#vertical-vs-horizontal-scaling` governs rung 0 and is linked, not restated.

## 4. What this is not

- Not a vendor guide. PgBouncer, Kafka, Redis Cluster, RocksDB, Cassandra appear as representative shapes, as they already do in `scaling.md`; the hub's "does NOT cover vendor choices" clause stands.
- Not a capacity model. Little's Law and amplification arithmetic only; no queueing theory beyond that, no USL curve fitting.
- Not a substitute for measurement. A system with no per-resource instrumentation is defined to be on rung 0 whatever its traffic.
- Not the interview-book progression verbatim. Xu's single-server-to-sharded ladder is cited as canon; the rungs here are indexed by saturated resource, not by component added.
- Not a new skill. Same trigger surface as `system`; the global listing budget is already over (audit F1), so the paradigm ships as a reference file plus ~50 chars of trigger words.

## 5. Edit map (shipped)

| File | Change |
|---|---|
| `plugins/design-patterns/skills/system/growth.md` | **new** cross-cutting reference: anchors-not-triggers table, saturation-signal table (USE), Little's Law sketch, rungs 0–4 in the fixed rung shape, "what every rung adds", anti-ladder failures, review checklist, references; TOC; every cross-link slug-verified |
| `plugins/design-patterns/skills/system/data.md` | new entry `Storage Engine: B-Tree vs LSM` (house entry shape, RUM table, append-only port sketch) placed before Tombstones; TOC entry; big-picture question 6; "When to reach for what" item 7 (renumbered); review-checklist item 13 |
| `plugins/design-patterns/skills/system/SKILL.md` | description +2 trigger phrases (capacity planning, what breaks at the next 10× load); intro names the growth ladder; reference-index row for `growth.md` and Storage Engine mention in the `data.md` row; line-count header updated; decision-flow step 2 gains the load-number entry; citing example added |
| `docs/superpowers/specs/2026-09-18-system-growth-ladder.md` | this dossier |
| `plugins/design-patterns/skills/system/communication.md` | two pre-existing broken same-file anchors surfaced by the cross-link check (`#request-reply-sync`, `#pub-sub-async`) re-pointed at the real slugs (`#requestreply-sync`, `#pubsub-async`); no prose changed |
| `.agents/`, `plugins/design-patterns/.codex-plugin/` | regenerated via `scripts/sync-codex.sh` (manifests unchanged in content; skills-only sync) |

## 6. Verification

All run at authoring time on 2026-09-18 from the repo root.

| Check | Result |
|---|---|
| Cross-link check (custom slugger over every `](file.md#anchor)`, `](#anchor)`, and `` `file.md#anchor` `` in the system dir) | 198 references across 9 files; 0 broken in new or edited material; 2 pre-existing broken same-file anchors in `communication.md` fixed (see §5) |
| `mypy --strict --python-version 3.13` on the two new sketches (`LoadPoint` / `slots_required`; `ActivityEvent` / `ActivityLog`) | clean |
| `pyright` with `# pyright: strict` on the same two sketches | 0 errors, 0 warnings |
| `markdownlint` with the repo `.markdownlint.json` | only MD013 (200 cols) on reference-index table rows, which untouched siblings also trip (house-tolerated); the one new over-long row in `data.md` shortened under 200 |
| `claude plugin validate .` (`make validate`) | passed |
| Listing budget: `system` description | 510 chars (cap 1,536); +53 chars for the two trigger phrases |
| `scripts/sync-codex.sh` (`make sync-codex`) | ran; Codex manifests are byte-copies of unchanged `plugin.json` files, so no diff |
| Reference line counts | `growth.md` 509 (new); `data.md` 1,237 → 1,389; eight refs total 11,524 → `SKILL.md` header "~11,500 lines across 8 refs" |

Not done here: `make release VERSION=x.y.z` and the push. The marketplace is GitHub-sourced and the plugin cache keys on the version string, so nothing above reaches an installed plugin until a release is cut.
