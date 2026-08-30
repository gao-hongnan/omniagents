# Design it twice

Ousterhout's rule: the first interface you write for anything important is rarely
the best one. The interface is paid for by every caller for the life of the
module, so spend an hour designing it two or three ways before committing.

## 1. Frame the problem first

Write a short, caller-facing statement before sketching any design: the
behaviour the module must hide, the dependencies it sits in front of, the hard
constraints (latency, failure modes, call frequency), and the call site you wish
you could write. Candidates are judged against this frame; without it they
optimize different unstated goals and cannot be compared.

## 2. Generate designs that diverge

Produce two or three genuinely different interfaces, each pushed toward a
different priority so they do not converge on the first idea:

- the **smallest** interface that meets the constraint, everything else pushed
  inside;
- the one that **absorbs the most variation** without a signature change;
- the one that makes the **common call site** trivial, with an explicit escape
  hatch for the rest;
- the one that **moves the least across the boundary**.

These can be explored in parallel (e.g. one agent per priority); keep the briefs
independent so the designs stay distinct. The mechanism does not matter — the
divergence does.

## 3. Choose by depth, locality, seam placement

Compare, do not average:

- **Depth** — behaviour hidden per interface point; prefer the design that hides
  the most behind the least.
- **Locality** — where the *next* likely change lands; prefer the design where it
  lands in one place.
- **Seam placement** — whether the boundaries sit at real substitution points
  (≥2 implementations) or speculative ones. A "flexible" design whose extra seams
  will never get a second implementation is shallow dressed as general.

Be opinionated: deliver one recommendation with the trade-off named, not a
neutral menu. Record a rejected alternative only when the rejection is
load-bearing — hard to reverse, surprising without context, the result of a real
trade-off.
