---
name: kong
description: >-
  Use when working on Kong Gateway or Konnect and the answer must be
  current rather than recalled: declarative configuration, GitOps with
  decK or kongctl, Kubernetes via KIC or the Kong Operator, the
  Terraform providers, plugin selection and ordering, auth strategy, or
  writing a custom Lua plugin. Runs a research pass against Kong's own
  docs before answering, because edition and version change the answer.
when_to_use: >-
  Trigger for kong.yml, kong.conf, decK state files, KongPlugin or
  KongIngress CRDs, handler.lua, schema.lua, `deck`/`kongctl` commands,
  Kong Terraform providers, and questions like "how should we do auth on
  Kong", "GitOps for Kong", "is this plugin Enterprise-only", or "how do
  I write a custom Kong plugin" — any Kong answer where being one major
  version or one edition wrong would be actively harmful.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/kong.yml"
  - "**/kong.yaml"
  - "**/kong.conf"
  - "**/deck.yaml"
  - "**/*.deck.yaml"
  - "**/kongctl.yaml"
  - "**/handler.lua"
  - "**/schema.lua"
shell: bash
---
# Kong — research-first playbook

This skill deliberately encodes **no Kong best practices**. Kong ships
several gateway releases a year (3.16.0.0 landed 2026-09-15), the docs
domain moved to `developer.konghq.com`, and the same question has
different correct answers in OSS, Enterprise, and Konnect. A frozen
rulebook here would be wrong within two quarters and wrong silently.

What this encodes instead: **how to find the current answer, what to
distrust, and what to state alongside it.** Run the steps in order. Do
not answer a Kong question from memory — model priors on Kong are
reliably stale on exactly the points that matter (edition gating, plugin
priorities, removed APIs).

## Step 0 — anchor, before anything else

Four facts change the correct answer completely. Establish all four from
the repo, or ask. Never assume.

| Anchor                    | Why it decides the answer                                                                                                                                  |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Version**         | 3.x vs 2.x differ on plugin APIs, router, and config schema. Ask which minor — features land in minors.                                                   |
| **Edition**         | OSS (Community) / Enterprise / Konnect. Roughly 30 plugins are Enterprise-only. An OSS shop cannot use the answer you'd give an EE shop.                   |
| **Deployment mode** | Traditional (DB) / DB-less / hybrid (CP+DP) / Konnect. DB-less makes the Admin API read-only, which invalidates every "just POST to`/consumers`" answer. |
| **Config tool**     | decK / kongctl / KIC + CRDs / Terraform / Admin API. These are not interchangeable — see Step 3.                                                          |

Grep for the evidence first: `kong.conf`, `KONG_DATABASE`, `_format_version`
in a state file, `deck.yaml`, `KongPlugin` CRDs, a `kong/kong-gateway` or
`kong/konnect` Terraform provider block.

## Step 1 — check for Kong's own skills, and offer to install them

Kong publishes agent skills that are closer to the product than this
file will ever be. **Check first, then say so.** If they are absent and
the user's work is Konnect, decK, or Terraform-managed Kong, surface the
install commands once — do not install anything yourself, and do not
nag if they decline.

```bash
ls .claude/skills .kongctl/skills 2>/dev/null   # already installed?
```

If a bundled skill owns the surface, defer to it and stop here.

**Kong official — `kongctl` bundled skills.** `kongctl-declarative`
(plan/diff/apply/sync/adopt flows, `kongctl explain`/`scaffold`, decK
via `_deck`) and `kongctl-extension-builder`. Konnect-scoped.

```bash
brew install --formula kong/kongctl/kongctl   # or:
curl -fsSL https://get.konghq.com/kongctl | sh

kongctl install skills --dry-run   # preview the files and symlinks
kongctl install skills             # writes .kongctl/skills/, symlinks
                                   # into .claude/skills/ and .agents/skills/
```

https://developer.konghq.com/kongctl/skills/

**Community set — ~17 skills, Kong-employee maintained, tech preview.**
`deck-gateway`, `terraform-kong-gateway`, `terraform-konnect`,
`gateway-plugin-datakit`, and the Konnect triage family.

```bash
/plugin marketplace add johnharris85/kong-skills
/plugin install kong-konnect@kong-skills
/reload-plugins

npx skills add johnharris85/kong-skills   # skill-only, no Konnect token
```

Caveats to pass on, not hide: it is **tech preview**, and its own docs
give the source as `kong/skills`, which is not a public repo as of
2026-09-19 — hence the `johnharris85/` path above. Re-check whether
`kong/skills` has gone public before quoting the docs verbatim. Kong's
docs also print the install pair as `kong-skills@kong-konnect`; the
marketplace is named `kong-skills` and the plugin `kong-konnect`, so the
order above is the one that resolves.

Neither set covers **writing a custom Lua plugin** — no published skill
does. That surface is Step 3 plus your own judgement.

## Step 2 — pull current docs, in this precedence order

Prefer **context7** over web search for Kong docs — it is indexed, and
`developer.konghq.com` alone carries ~20k snippets.

| Library ID                              | Covers                                                              |
| --------------------------------------- | ------------------------------------------------------------------- |
| `/kong/developer.konghq.com`          | Official docs: gateway, plugins, PDK, decK, kongctl, custom plugins |
| `/kong/kong`                          | Gateway source + CHANGELOG — the authority on breaking changes     |
| `/kong/kubernetes-ingress-controller` | KIC, Gateway API, CRDs                                              |
| `/kong/charts`                        | Helm install shapes                                                 |
| `/kong/kong-operator`                 | Operator-managed deployments                                        |

Precedence when sources disagree, highest first:

1. `developer.konghq.com` for the **specific version** in play.
2. The `Kong/kong` CHANGELOG for that version — breaking changes are
   documented there before they are documented anywhere readable.
3. Kong engineering blog (`konghq.com/blog/engineering`) — good for
   rationale, weaker for current syntax.
4. Everything else — treat as a hypothesis to verify, never as a cite.

**Distrust on sight:** anything pre-3.0 (late 2022), `docs.konghq.com`
legacy URLs, Stack Overflow answers using `BasePlugin`, and any tutorial
that does not state its Kong version. Blog posts age badly here.

## Step 3 — route by question genre

| The question is about…                                    | Go to                                                            | Tool that owns it                                                                                        |
| ---------------------------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| GitOps, config in Git, CI-applied state                    | `developer.konghq.com/deck/`                                   | **decK** for Gateway entities (services, routes, plugins, consumers)                               |
| Konnect platform: APIs, dev portals, control planes, teams | `developer.konghq.com/kongctl/`                                | **kongctl** — one level *above* the gateway; invokes decK inline via a `_deck` entry          |
| Kubernetes                                                 | `/kong/kubernetes-ingress-controller`, `/kong/kong-operator` | **KIC** + Gateway API / CRDs, or the **Operator**                                            |
| Existing HCL estate                                        | Kong Terraform providers                                         | `kong/kong-gateway` (self-managed Admin API) vs `kong/konnect` — different providers, do not mix up |
| Which plugin for a policy                                  | `developer.konghq.com/plugins/`                                | Built-in plugin first; custom plugin is a last resort                                                    |
| Writing a custom Lua plugin                                | `developer.konghq.com/custom-plugins/`                         | `Kong/kong-plugin` template + **pongo** test runner                                              |

decK and kongctl are **complementary, not alternatives**. decK configures
the gateway; kongctl manages the Konnect platform. Getting this wrong
produces confidently wrong answers — check which one the repo uses.

## Step 4 — verify these before asserting them

These are where a model's Kong priors are most often stale or wrong.
Confirm each against Step 2 sources rather than recalling it.

- **Is the plugin Enterprise-only?** `openid-connect` is EE — an OSS shop
  wanting OIDC must chain `jwt`/`oauth2`, put an OIDC proxy in front, or
  write a custom plugin. Say this explicitly; it is usually the single
  most consequential fact in an auth conversation —
  https://developer.konghq.com/plugins/openid-connect/
- **Plugin execution order.** Priority numbers decide it, and Kong has
  moved them between releases. Auth must run before ACL and before rate
  limiting. Look up the current priority table; never guess a number.
- **`BasePlugin` is gone.** Removed in 3.0 — custom plugins return a
  plain table with phase functions. Any example inheriting from
  `BasePlugin` is pre-3.0 and everything around it is suspect.
- **DB-less constraints.** Admin API is read-only; anything that creates
  entities at runtime (consumer registration, credential issuance) needs
  a different design.
- **`_format_version`** in decK state files is version-gated — read the
  current value from the decK docs, don't copy one from a blog.
- **Secrets.** Never inline in declarative config. Kong vault references
  (`{vault://...}`) or env — confirm which backends the edition allows.

## Step 5 — answer shape

Every Kong recommendation carries, inline:

- the **version** it was verified against,
- the **edition** it requires — flag EE-only before the user builds on it,
- the **source URL**,
- and an explicit note on anything you could not verify. "The docs do not
  say" is a valid and useful answer; an invented config key is not.

When the user is new to Kong, name the tool boundary (Step 3) before the
syntax. Most Kong confusion is picking the wrong tool for the layer, not
getting a key wrong.

## What "enterprise-grade" has to mean

When asked for an enterprise-level setup, these are the questions to
force answers to — research each against Step 2 rather than asserting a
default. Rows are the shared infra reference set used across the
omniagents-devops skills.

| Control                                         | T1 demo  | T2 production | T3 regulated                          |
| ----------------------------------------------- | -------- | ------------- | ------------------------------------- |
| Config in Git, CI-applied, no console edits     | optional | required      | required + mandatory review           |
| Non-prod → prod promotion path                 | optional | required      | required, with plan artifact retained |
| Secrets via vault refs, never inline            | optional | required      | required (mandated backend)           |
| Auth on every route (no anonymous default)      | optional | required      | required + ACL groups                 |
| Rate limiting + request size caps               | optional | required      | required                              |
| Observability: metrics, tracing, audit log      | basic    | required      | required, retained                    |
| CP/DP split (hybrid) with mTLS                  | no       | recommended   | required                              |
| Custom plugins security-reviewed + pongo-tested | no       | required      | required, pinned versions             |

Drift is the usual enterprise failure: config applied by hand in the
console, then overwritten by the next `deck sync`. If GitOps is the
stated goal, confirm console write access is actually closed — otherwise
the pipeline is decorative.
