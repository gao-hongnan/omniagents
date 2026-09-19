# Growth Ladder — What Breaks at the Next Order of Magnitude

> The load-indexed entry into this catalogue. The other files answer *which shape*; this
> one answers *which resource saturates next, and which shape relieves it*, split by write
> path and read path at every rung. Each rung names the physics that fails, the signal that
> proves it, the smallest move on each path, the contract that move makes mandatory, and
> the entry elsewhere in this skill that holds the sketch.

A system does not scale continuously. It runs fine, then one resource saturates and every
latency percentile bends upward at once. The next order of magnitude is always gated by a
*different* resource than the last one, which is why the fix that bought the previous 10×
buys nothing for the next. Thinking in rungs turns "we need to scale" into a named
bottleneck, a measurement that proves it, and one move per path.

The default posture: **measure the saturated resource before choosing a rung; split reads
from writes from rung 1 onward; keep every previous rung's mechanism in place; never skip
a rung.**

## Table of Contents

- [How to use this file](#how-to-use-this-file)
- [Anchors, not triggers](#anchors-not-triggers)
- [Finding the saturated resource](#finding-the-saturated-resource)
- [The arithmetic](#the-arithmetic)
- [Rung 0 — One box](#rung-0--one-box)
- [Rung 1 — Connections and unindexed reads](#rung-1--connections-and-unindexed-reads)
- [Rung 2 — Synchronous commits, replication lag, one cache node](#rung-2--synchronous-commits-replication-lag-one-cache-node)
- [Rung 3 — Write amplification and viral keys](#rung-3--write-amplification-and-viral-keys)
- [Rung 4 — Coordination and blast radius](#rung-4--coordination-and-blast-radius)
- [What every rung adds](#what-every-rung-adds)
- [Anti-ladder failures](#anti-ladder-failures)
- [Review Checklist](#review-checklist)
- [References](#references)

---

## How to use this file

Read this file when the question arrives as a number rather than a pattern: "we are at N
requests per second and the roadmap says 10N", "the database is slow and someone said
shard", a capacity review, or a post-incident "what breaks next". Find your rung by the
**signal** column, not by the RPS anchor. Then read the one move per path and follow the
link to the entry that holds the sketch; this file deliberately holds no second copy of any
sketch.

Each rung follows one shape: `Anchor` · `What breaks` · `Signal` · `Write path` · `Read
path` · `Mandatory contracts this rung creates` · `Stop sign` · `Read next`.

If the question is a pattern choice with no load number attached, start from the axis
files instead (`SKILL.md` decision flow). If the load number is a wish rather than a
measurement, this file's first job is to send you back to instrument.

---

## Anchors, not triggers

The RPS figures on each rung describe one **reference workload**: OLTP, rows around 1 KB, a
working set that fits in RAM through rung 1, roughly ten reads per write, and simple indexed
queries. Every anchor moves by up to an order of magnitude when the workload differs:

| Workload property | Moves the anchor… | Because |
| --- | --- | --- |
| Payloads of 10–100 KB instead of 1 KB | down | network and disk bytes saturate before request count does |
| Working set larger than RAM | down, sharply | every miss is a disk read; the buffer-cache hit rate collapses |
| Write-heavy (writes ≥ reads) | down for rung 2 | fsync and lock contention arrive at lower RPS; read moves buy little |
| Fan-out queries (joins, aggregates, scatter-gather) | down | one request costs many resource units |
| Bigger node (cores, NVMe, RAM) | up, by a constant | each rung's failure is per node; scale-up shifts the anchor but never the shape of what breaks |
| Point reads by primary key only | up | the cheapest possible unit of work per request |

Stack Overflow served a top-100 site from a handful of web servers and a few SQL boxes for
over a decade: a reference workload on big nodes sits at the top of every anchor range. A
50 KB-document, write-heavy service reaches rung 2 at a few hundred RPS. The ladder orders
the moves; the workload sets the numbers. See
[`scaling.md#vertical-vs-horizontal-scaling`](scaling.md#vertical-vs-horizontal-scaling)
for the scale-up-first argument that governs rung 0.

---

## Finding the saturated resource

Per resource, in this order, ask utilization, saturation, errors (Gregg's USE method).
Utilization near 100% with no queue is fine; a growing queue at 60% utilization is the
bottleneck. The rung is named by the *first* resource that saturates, not the busiest one.

| Resource | Utilization | Saturation (the signal) | Points at |
| --- | --- | --- | --- |
| DB connections | `numbackends / max_connections` | pool `acquire` wait time at the app; "too many connections" errors | rung 1 |
| DB disk reads | read IOPS vs device ceiling; buffer-cache hit ratio | `pg_stat_statements` top entries by `shared_blks_read`; read latency rising while CPU idles | rung 1 |
| DB commit path | write IOPS; WAL bytes/s | commit latency p99 tracks fsync latency; lock waits on a handful of hot rows | rung 2 |
| Replication | replica apply rate | `pg_stat_replication` lag in seconds, growing during write bursts | rung 2 |
| Shared cache node | one core at 100%; network bytes/s on one node | client latency rises while ops/s flatten; slow-log entries | rung 2 |
| Storage engine | bytes written to disk ÷ bytes ingested (write amplification) | checkpoint-aligned latency spikes; VACUUM and bloat falling behind; compaction stalls | rung 3 |
| One hot key | one cache shard hot, the rest idle | `--hotkeys` output; miss storms at TTL expiry; source load spikes on a fixed period | rung 3 |
| Leader / region | single writer at ceiling; cross-region RTT | every write waits on one node; one zone outage is a global outage | rung 4 |

If none of these is measured, the system is on rung 0 regardless of its traffic, and the
first move is instrumentation: p50/p99 per endpoint, per-resource utilization, and queue
depth at every pool. Nothing below is decidable without them.

---

## The arithmetic

Two formulas cover most capacity decisions on this ladder.

**Little's Law.** Mean in-flight requests at a resource equal arrival rate times mean time
held: `L = λ · W`. It sizes every pool and worker count and explains every queue: if
`λ · W` exceeds the slots available, the excess waits, waiting adds to `W`, and `L` rises
again. That feedback is why saturation bends every percentile at once.

**Amplification.** Each retry layer, fan-out, or cache miss multiplies load at the resource
below: three retry layers × three attempts is 27× at the bottom
([`anti-patterns.md#retry-storms`](anti-patterns.md#retry-storms)); one hot key expiring
under 20,000 readers/s is 20,000 misses at the source in the same window unless a single
flight coalesces them ([`anti-patterns.md#naive-caching`](anti-patterns.md#naive-caching)).

```python
import math
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class LoadPoint:
    """One measured operating point at a resource: arrival rate and mean hold time."""

    rps: float           # λ: arrivals per second
    mean_hold_s: float   # W: mean seconds each arrival occupies the resource

    @property
    def in_flight(self) -> float:
        """L = λ·W — mean concurrent occupancy (Little, 1961)."""
        return self.rps * self.mean_hold_s


HEADROOM: Final[float] = 1.5  # p99 hold time sits above the mean; never plan at the mean


def slots_required(point: LoadPoint, *, headroom: float = HEADROOM) -> int:
    """Slots (connections, workers) so that arrivals do not queue at the mean."""
    if point.rps < 0 or point.mean_hold_s <= 0 or headroom < 1.0:
        raise ValueError("rps >= 0, mean_hold_s > 0, headroom >= 1.0 required")
    return math.ceil(point.in_flight * headroom)


# 5,000 queries/s held 4 ms each → 20 in flight → 30 server-side connections.
# 50 app replicas × 20 client connections each = 1,000 client sockets: a pooler
# must multiplex those onto the 30, or Postgres pays a process and ~10 MB per socket.
SERVER_SLOTS: Final[int] = slots_required(LoadPoint(rps=5_000, mean_hold_s=0.004))
```

Run the same arithmetic at each rung with the new `W`: a replica adds nothing to write
slots; an asynchronous ingest path changes the caller's `W` from commit latency to append
latency and moves the commit cost to a consumer whose `λ` you now control with batch size.

---

## Rung 0 — One box

**Anchor.** Up to roughly 10³ RPS on the reference workload; far higher on a large node.

**What breaks.** Nothing structural. What fails at this rung is almost always a missing
index, an N+1 query, a connection opened per request, or a synchronous call to a slow
dependency on the hot path. These masquerade as "we have outgrown Postgres".

**Signal.** One slow query dominates `pg_stat_statements`; latency scales with rows
returned rather than with traffic; connection count equals request count.

**Write path.** One primary, one transaction per request, an app-side pool sized by
Little's Law. Fix queries before touching topology.

**Read path.** The same database and pool, with indexes that match the query plans.

**Mandatory contracts this rung creates.** Instrumentation (previous section). Without it
every later rung is a guess.

**Stop sign.** A bigger node is the correct answer more often than any pattern below;
reach for it before rung 1 unless fault tolerance, not throughput, is the pain.

**Read next.** [`scaling.md#vertical-vs-horizontal-scaling`](scaling.md#vertical-vs-horizontal-scaling),
[`anti-patterns.md#chatty-interfaces-n1-rpc`](anti-patterns.md#chatty-interfaces-n1-rpc),
[`scaling.md#connection-pooling`](scaling.md#connection-pooling).

---

## Rung 1 — Connections and unindexed reads

**Anchor.** 10³ → 10⁴ RPS.

**What breaks.**

- *Connection storms.* Every app replica multiplied by its pool size lands on the primary
  as a process each. Postgres forks a backend per connection at roughly 10 MB baseline
  plus `work_mem` per sort or hash; past a few hundred *active* backends the CPU goes to
  context switching and lock-manager contention, and throughput falls while connections
  rise. Autoscaling churn makes it worse: each new replica opens a full pool at once.
- *Reads steal from writes.* Unindexed or wide reads sequential-scan, evict hot pages from
  `shared_buffers`, and take disk read IOPS on the same device the WAL is fsynced to.
  Write latency rises although nothing about the write path changed.

**Signal.** Pool `acquire` wait at the app; `numbackends` near `max_connections`; read
IOPS at the device ceiling with CPU idle; the top of `pg_stat_statements` ordered by
`shared_blks_read`.

**Write path.** Keep writing to the single primary, but through a **pooler** (PgBouncer,
pgcat, RDS Proxy) in transaction mode that multiplexes thousands of client sockets onto
tens of server connections. Size the server side by Little's Law, not by replica count.
Transaction pooling breaks session state: `SET`, advisory locks, `LISTEN`, and prepared
statements on PgBouncer before 1.21. Audit the app for these before cutting over.

**Read path.** A **cache-aside** layer with single-flight for hot keys, and **read
replicas** for the misses. The cache absorbs the hot-key majority; replicas absorb the long
tail without touching the primary's IOPS.

**Mandatory contracts this rung creates.**

- A staleness contract per read path: TTL, invalidation order (write the source, then
  invalidate), negative caching for misses.
- **Read-your-writes** for the writing session, because a replica can lag the row the user
  just wrote.
- Replica-lag and cache-hit-rate alarms. Both are the leading indicators for rung 2.

**Stop sign.** If commit latency, not read latency, is what is rising, adding replicas and
cache buys nothing: that is rung 2's problem arriving early because the workload is
write-heavy.

**Read next.** [`scaling.md#connection-pooling`](scaling.md#connection-pooling),
[`scaling.md#cache-aside-lazy-loading`](scaling.md#cache-aside-lazy-loading),
[`scaling.md#cache-invalidation`](scaling.md#cache-invalidation),
[`data.md#replication`](data.md#replication),
[`data.md#eventual-consistency`](data.md#eventual-consistency).

---

## Rung 2 — Synchronous commits, replication lag, one cache node

**Anchor.** 10⁴ → 10⁵ RPS.

**What breaks.**

- *Synchronous commits are fsync-bound.* Each transaction costs a durable WAL write and,
  for updated rows, dirty pages the checkpointer must later flush. Group commit amortizes
  the fsync, but the disk's write IOPS still cap the transaction rate, and hot rows
  (counters, `last_seen`, inventory) serialize behind row locks.
- *Replication lag balloons.* The primary writes with many backends; a streaming replica
  applies WAL with far less parallelism. Under a write burst lag grows from milliseconds
  to minutes, and every rung-1 read path that assumed "slightly stale" now serves
  minutes-old rows to users.
- *One cache node saturates.* A Redis node executes commands on one thread; I/O threads
  offload the sockets, not the commands. On the reference workload a node serves on the
  order of 10⁵ simple operations per second without pipelining, and a single big key,
  `KEYS`, or a large `SMEMBERS` stalls everything queued behind it. One node is also one
  network interface and one memory ceiling.

**Signal.** Commit latency p99 tracks fsync latency; lock waits on the same handful of
rows; `pg_stat_replication` lag in seconds during bursts; one cache core pinned at 100%
while client latency climbs and ops/s flatten.

**Write path.** Stop committing synchronously from the request path. **Ingest into a
durable, partitioned log** (Kafka, Pulsar, Kinesis), answer `202 Accepted` with a status
location, and let consumers apply the log to the database in **bulk sequential
micro-batches** (multi-row `INSERT`, `COPY`). N random single-row transactions become a few
batched ones; the disk sees sequential writes; the caller's `W` becomes append latency.
This is write-behind with a durable buffer in place of a lossy in-memory one, and the first
rung at which a write no longer touches the database on the request path. When a write
genuinely cannot be asynchronous (a payment authorization), keep it synchronous and shard
the hot rows instead (sharded counters, per-tenant tables), partition large tables, and
reserve `synchronous_commit = off` for writes whose loss on crash is acceptable, with that
loss written down.

**Read path.** **Shard the cache**: Redis Cluster hashes each key to one of 16,384 slots,
with hash tags to co-locate keys a multi-key command must touch together; or client-side
consistent hashing over independent nodes. Replicate the hottest keys across several nodes
(key suffixing) so no single node owns a hot key. Shard heavy read tables by tenant or user
id so one replica set serves one shard's traffic.

**Mandatory contracts this rung creates.**

- **Idempotency keys** on every ingested write, because the log delivers at least once and
  a consumer retry must not double-apply. An **inbox** on the consumer side deduplicates.
- A status endpoint and a **dead-letter queue** with a depth alarm: the request path no
  longer knows whether the write succeeded.
- A consumer-lag alarm and a **backpressure** shape for when consumers fall behind; the log
  buffers but does not absorb forever.
- A shard-key discipline: a query without the shard key is a scatter-gather across every
  shard, and a multi-key cache command outside one hash slot fails.
- Read-your-writes now spans a queue: the write is not readable until applied. The API
  contract or the UI must say so.

**Stop sign.** Reaching for a log at rung 1 buys the contracts above without the throughput
problem they solve
([`anti-patterns.md#premature-microservices-adoption`](anti-patterns.md#premature-microservices-adoption)).
Reaching for database sharding here, before the log and the cache shards, is the classic
premature shard ([`data.md#sharding`](data.md#sharding), *When to reach for it*).

**Read next.** [`scaling.md#write-behind--write-back`](scaling.md#write-behind--write-back),
[`communication.md#asynchronous-request-reply`](communication.md#asynchronous-request-reply),
[`communication.md#pubsub-async`](communication.md#pubsub-async),
[`reliability.md#idempotency-keys`](reliability.md#idempotency-keys),
[`data.md#inbox-pattern`](data.md#inbox-pattern),
[`reliability.md#dead-letter-queue`](reliability.md#dead-letter-queue),
[`reliability.md#backpressure`](reliability.md#backpressure),
[`scaling.md#load-balancing`](scaling.md#load-balancing) (consistent hashing),
[`data.md#sharding`](data.md#sharding),
[`anti-patterns.md#hot-path-database-locking`](anti-patterns.md#hot-path-database-locking).

---

## Rung 3 — Write amplification and viral keys

**Anchor.** 10⁵ → 10⁶ RPS.

**What breaks.**

- *B-tree in-place updates.* Even batched, each updated row dirties an 8 KB page at a
  random location, plus a page per affected index, plus the WAL record, plus a full-page
  image after each checkpoint; under MVCC the old version stays until VACUUM reclaims it.
  Bytes written to disk per byte ingested (write amplification) climbs with index count;
  the SSD controller's own garbage collection adds another multiplier under random writes;
  checkpoints become periodic latency cliffs; VACUUM falls behind, tables bloat, and the
  read path degrades too.
- *Viral keys melt a shard.* One key read 10⁵ times per second lives on one cache node
  whatever the cluster size; sharding spreads keys, not the traffic of a single key. When
  its TTL expires every reader misses in the same window and the source takes the storm
  ([`anti-patterns.md#naive-caching`](anti-patterns.md#naive-caching)).

**Signal.** Write amplification rising; latency spikes aligned with checkpoints; bloat and
VACUUM lag; one cache node hot and the rest idle; miss storms on a fixed period.

**Write path.** Move the write-heavy tables to a **log-structured storage engine**
(RocksDB-based stores, Cassandra, ScyllaDB, HBase; MyRocks for MySQL). Writes land in an
in-memory memtable and an append-only commit log, then flush as sorted immutable segments:
random writes become sequential throughput. The cost is read amplification (a point read
may consult several levels, mitigated by Bloom filters), compaction I/O with occasional
stalls, tombstones until compaction, and transactions that stop at a partition boundary.
Choose per table, not per system: the catalogue, the ledger, and the user table stay
relational; the events, telemetry, and feed tables move. Time-partition and drop old
partitions rather than delete rows, and feed downstream stores by CDC instead of dual
writes.

**Read path.** Add an **in-process L1 cache** inside every app replica: local RAM, a 1–2 s
TTL, single-flight per key, and probabilistic early refresh so expiry never aligns across
replicas. A viral key is then served from N replicas' memory and the shared cache sees at
most N requests per TTL instead of 10⁵ per second. For anything addressable by URL,
coalesce further out at the CDN with `stale-while-revalidate`.

**Mandatory contracts this rung creates.**

- The L1 makes replicas disagree for up to one TTL. That inconsistency is now a product
  decision; write it into the read contract.
- Inner TTL ≤ outer TTL across L1, L2, and CDN, and a bounded L1 (`maxsize`), or the cache
  becomes a memory leak.
- Per-layer hit-rate metrics; remove a layer that hits under 50%.
- Access-pattern discipline for the LSM tables: partition key plus range, no ad-hoc joins,
  tombstone retention tuned to the anti-entropy schedule.

**Stop sign.** If the write path has not been batched (rung 2), an LSM engine solves a
problem you have not reached; batching alone usually buys the order of magnitude.

**Read next.** [`data.md#storage-engine-b-tree-vs-lsm`](data.md#storage-engine-b-tree-vs-lsm),
[`data.md#change-data-capture-cdc`](data.md#change-data-capture-cdc),
[`data.md#tombstones-and-soft-delete`](data.md#tombstones-and-soft-delete),
[`scaling.md#read-through`](scaling.md#read-through) (in-process single-flight sketch),
[`scaling.md#refresh-ahead`](scaling.md#refresh-ahead),
[`scaling.md#stacking-caches`](scaling.md#stacking-caches),
[`scaling.md#cdn-and-edge-caching`](scaling.md#cdn-and-edge-caching).

---

## Rung 4 — Coordination and blast radius

**Anchor.** Beyond 10⁶ RPS, or any load that must survive the loss of a region.

**What breaks.** The remaining single things: one write leader, one control plane, one
failure domain. Cross-region round trips make anything synchronous impossible within the
latency budget, and a shared component turns a local fault into a global outage.

**Signal.** Every write waits on one node however many replicas exist; a single zone or
region incident shows up in every customer's dashboard; cross-region p99 is dominated by
RTT.

**Write path.** **Cell-based architecture**: partition users or tenants into cells that
each run the whole stack, and route at the edge; a cell's failure takes its slice only.
Within a cell the previous rungs stand. Across regions, **multi-leader or leaderless
replication** with an explicit conflict policy (CRDTs for data that tolerates merge,
partitioned single-leader for data that does not).

**Read path.** Geographic sharding so reads are served in-region; quorum reads where the
staleness bound matters.

**Mandatory contracts this rung creates.** Cell routing keys; a conflict policy per table;
regional bulkheads with their own capacity; game days that kill a cell.

**Stop sign.** Cells multiply every rung below them by the cell count. Do not enter this
rung with rung-2 contracts (idempotency, DLQ, shard keys) still undocumented.

**Read next.** [`cloud.md#cell-based-architecture`](cloud.md#cell-based-architecture),
[`cloud.md#bulkheading-at-the-infrastructure-level`](cloud.md#bulkheading-at-the-infrastructure-level),
[`data.md#replication`](data.md#replication),
[`distributed.md#crdts`](distributed.md#crdts),
[`distributed.md#quorum-reads-and-writes`](distributed.md#quorum-reads-and-writes).

---

## What every rung adds

The moves compose; the contracts accumulate. Reading the ladder top-down:

```
rung 0  one box                      : instruments, indexes, app-side pool
rung 1  + pooler                     : + staleness contract, read-your-writes
        + cache-aside + replicas
rung 2  + durable log + batching     : + idempotency keys, inbox, status, DLQ, backpressure
        + cache shards + read shards : + shard-key discipline
rung 3  + LSM tables                 : + access-pattern discipline, tombstone retention
        + in-process L1              : + cross-replica staleness, TTL ordering, bounded size
rung 4  + cells, multi-leader        : + conflict policy, cell routing, regional bulkheads
```

Five rules hold across the whole ladder.

1. **Every rung stays.** Rung 3 still has the pooler, the L2 cache, and the replicas.
   Removing a lower rung's mechanism because a higher one exists reopens the lower failure.
2. **Every copy adds a staleness contract.** Replica, L2, L1, CDN: each needs a TTL, an
   invalidation path, and a place in the inner-before-outer ordering.
3. **Every asynchronous write adds an idempotency contract** and a way for the caller to
   learn the outcome.
4. **Every shard adds a key discipline.** Queries without the key are scatter-gather;
   transactions across keys are gone.
5. **Reads and writes diverge from rung 1 on.** This is lightweight CQRS
   ([`data.md#cqrs`](data.md#cqrs)) reached by necessity, one rung at a time, rather than
   adopted upfront.

---

## Anti-ladder failures

- **Calendar scaling.** Adopting a rung because the roadmap says so, with no saturated
  resource in evidence. Each rung's contracts are paid immediately; its benefit arrives
  only when the resource it relieves is actually the bottleneck.
- **Wrong-resource scaling.** Adding read replicas to fix commit latency; sharding the
  database when the cache node is the hot spot; buying a bigger disk for a connection
  storm. The signal table names the resource; the move must relieve *that* resource.
- **Skipping a rung.** Sharding at rung 1 or a log at rung 0 buys the contracts without the
  throughput; the failure returns as operational load
  ([`anti-patterns.md#premature-microservices-adoption`](anti-patterns.md#premature-microservices-adoption),
  [`anti-patterns.md#distributed-monolith`](anti-patterns.md#distributed-monolith)).
- **One-path scaling.** Scaling reads without noticing that the write path is now the
  bottleneck, or the reverse. Re-run the signal table after every move.
- **Unbounded amplification.** Retries, hedges, and fan-out multiply the load each rung
  must carry; a rung sized for `λ` and delivered `27λ` fails on the first incident
  ([`reliability.md#stacking-the-patterns`](reliability.md#stacking-the-patterns)).
- **Scaling on a wish.** No measurement, so no rung. Instrument first.

---

## Review Checklist

For any proposal that says "we need to scale", "shard", "add Kafka", "add a cache", or
"move to Cassandra":

1. Which resource is saturated? Name the metric and the measured value.
2. Which rung does that signal point at? Does the proposed move relieve that resource, or a
   different one?
3. Is this a write-path move or a read-path move? What is the other path's state after it?
4. Which contracts does the move create (staleness, idempotency, shard key, conflict
   policy)? Where are they written down and alarmed?
5. Is a lower rung being skipped? Would a query fix, an index, batching, or a bigger node
   buy the same order of magnitude for less?
6. Are the previous rungs' mechanisms still in place and measured after the change?
7. What breaks next, and which leading indicator will fire before it does?
8. Have the anchors been adjusted for this workload's payload size, working-set ratio, and
   read/write mix, or copied from a reference workload?

If any answer is "I don't know", the proposal is a hypothesis, not a plan.

---

## References

- Xu, A., *System Design Interview — An Insider's Guide*, vol. 1, ch. 1 "Scale from zero to
  millions of users", 2020 — the canonical single-server-to-sharded progression.
- Kleppmann, M., *Designing Data-Intensive Applications*, O'Reilly 2017 — ch. 3 (B-trees vs
  LSM-trees, write amplification), ch. 5 (replication lag), ch. 6 (partitioning).
- Gregg, B., *The USE Method*, brendangregg.com; *Systems Performance*, 2nd ed., 2020.
- Little, J. D. C., "A Proof for the Queuing Formula: L = λW", *Operations Research* 9(3),
  1961.
- Gunther, N. J., *Guerrilla Capacity Planning*, Springer 2007 — the Universal Scalability
  Law and why coordination caps scale-out.
- Dean, J., Barroso, L. A., "The Tail at Scale", *CACM* 56(2), 2013.
- Nishtala, R., et al., "Scaling Memcache at Facebook", NSDI 2013 — leases against
  stampedes, regional pools; the read-path story of rungs 1–3.
- Vattani, A., Chierichetti, F., Lowenstein, K., "Optimal Probabilistic Cache Stampede
  Prevention", VLDB 2015.
- Bronson, N., et al., "Metastable Failures in Distributed Systems", HotOS 2021 — why a
  stampede or retry storm persists after its trigger is gone.
- O'Neil, P., et al., "The Log-Structured Merge-Tree (LSM-Tree)", *Acta Informatica* 33,
  1996.
- Athanassoulis, M., et al., "Designing Access Methods: The RUM Conjecture", EDBT 2016.
- PostgreSQL docs — *Resource Consumption* (`max_connections`, `shared_buffers`,
  `work_mem`), *Write-Ahead Log* (`synchronous_commit`, checkpoints), *Monitoring
  Statistics* (`pg_stat_statements`, `pg_stat_replication`).
- PgBouncer docs — pooling modes; release notes 1.21 (prepared statements in transaction
  mode).
- Redis docs — *Cluster specification* (16,384 hash slots, hash tags); *Optimizing Redis*
  (pipelining, big keys, `redis-cli --hotkeys`).
- Apache Kafka docs — producer `linger.ms` / `batch.size`; consumer lag.
- Craver, N., *Stack Overflow: The Architecture — 2016 Edition*, nickcraver.com — the
  scale-up counterexample for every anchor.
