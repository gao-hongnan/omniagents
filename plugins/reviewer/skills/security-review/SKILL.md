---
name: security-review
description: >-
  Use when reviewing code for security vulnerabilities: injection (SQL,
  command, template, log), authentication/authorization gaps, secrets in
  code, unsafe deserialization, path traversal, SSRF, dependency
  vulnerabilities, cryptographic misuse, data exposure, or OWASP Top 10
  patterns.
when_to_use: >-
  Trigger for security code review: SQL injection, command injection,
  template injection, log injection, XSS, CSRF, authentication bypass,
  authorization gaps, IDOR, hardcoded secrets, API keys in code, JWT
  misuse, unsafe deserialization, path traversal, SSRF, open redirect,
  dependency vulnerabilities, cryptographic misuse (MD5, SHA1, ECB,
  hardcoded keys), PII in logs, error message information leakage,
  OWASP Top 10, CWE Top 25.
disable-model-invocation: false
user-invocable: false
---

# Security Review — Hunt Protocols

Find code an attacker can exploit to gain access, execute code, leak data,
or corrupt integrity. Security review is taint tracing: every finding is a
path from attacker-influenced input to a dangerous effect, or a missing
control an attacker can walk through.

## Hunts

Execute every hunt whose `When` matches; skip the rest. Exemplars are
calibration anchors, never templates — do not copy their wording into
reports.

### Hunt: Source-to-Sink Taint Trace

- **When**: the diff contains a sink (SQL execution, subprocess/shell,
  filesystem path built from variables, URL fetch, template render, HTML
  insertion, log write of external data) or reads external input (request
  params, headers, cookies, uploads, queue payloads, webhook bodies).
- **Protocol**:
    1. Grep the diff for sinks: `execute`/`.raw`/`text(`, `subprocess`/
       `os.system`/`child_process`, `open(`/`Path(` with variables,
       `requests.`/`fetch(`/`urllib`, `render_template_string`,
       `innerHTML`/`dangerouslySetInnerHTML`, log calls on request data.
    2. Trace each sink argument **backward** to its origin — read the full
       file, follow `callers_of` up until you reach a trust boundary or a
       server-side constant.
    3. Name the neutralizer on the path: parameterization, argv list with
       `shell=False`, canonicalize-then-prefix-check, allowlist,
       autoescape, output encoding. Attacker-reachable origin with no
       neutralizer = finding.
- **Evidence bar**: a complete source→sink path with the missing
  neutralizer named.
- **Falsifiers**: every origin is a server-side constant or admin-only
  config; a safe construct already neutralizes (parameterized query,
  `shell=False` argv, autoescape on); the framework escapes by default at
  that sink.
- **Exemplar**: BLOCKER 93 — "search handler f-strings the `q` request
  param into SQL; no parameterization anywhere on the path." / **Noise
  twin**: an f-string building SQL from an internal enum — origin is a
  server constant; not tainted.

### Hunt: Sibling Endpoint Parity

- **When**: new or changed route, handler, RPC method, resolver, or
  CLI/job entrypoint.
- **Protocol**:
    1. Read the **whole** router/controller file; list the auth
       decorators, middleware, and ownership/tenant checks its sibling
       endpoints carry.
    2. Flag the asymmetry the diff introduces — the one handler missing
       what its siblings have.
    3. For every ID-shaped parameter, locate the ownership check between
       parse and use (IDOR); "logged in" is not "owns this resource".
    4. Check verb semantics: state-changing operations reachable via GET.
- **Evidence bar**: the sibling that has the check, plus the new handler
  that lacks it — or an ID used with no ownership filter.
- **Falsifiers**: middleware applies the check globally (read the app/
  blueprint registration, not just the handler); the route is documented
  public; ownership is enforced at the query (`WHERE owner_id = ...`).
- **Exemplar**: BLOCKER 91 — "new `DELETE /api/keys/<id>` checks login but
  never ownership; its `GET` sibling filters by `owner_id` — any user
  deletes any key." / **Noise twin**: no decorator on a handler mounted
  under a blueprint whose registration applies `require_admin` —
  inherited.

### Hunt: Secret Spill

- **When**: new config keys, env handling, logging of objects,
  serialization or response shaping, error handlers.
- **Protocol**:
    1. Grep the diff for credential-shaped names and literals (`key`,
       `token`, `secret`, `password`, `Bearer `, `BEGIN PRIVATE`).
    2. Read log statements and serializer/response changes for sensitive
       fields (`model_dump`, `to_dict`, `repr` of settings objects, full
       request/response bodies).
    3. Confirm secrets travel the established secret path — env/secret
       manager/`SecretStr` — not literals or ad-hoc files.
- **Evidence bar**: a real credential literal, or a sensitive field that
  reaches logs, responses, or serialized output.
- **Falsifiers**: clearly fake test/fixture value that cannot run in
  production; the serializer already redacts the field; the "secret" is a
  public identifier (client_id, publishable key).
- **Exemplar**: BLOCKER 90 — "error handler returns `repr(settings)` to
  the client, including `db_password`." / **Noise twin**:
  `API_KEY = "fake-for-tests"` inside a test fixture that production
  never imports.

### Hunt: Hostile Input Materialization

- **When**: the diff parses external data into objects, builds filesystem
  paths or URLs from input, or extracts archives.
- **Protocol**:
    1. Identify the loader: `pickle`/`yaml.load`/`eval`/`exec`, schema-less
       `JSON.parse` straight into trusted shapes.
    2. Paths: canonicalize (`resolve`/`realpath`) then check containment
       against the base directory **before** use; archive extraction must
       validate member paths (zip-slip).
    3. URLs: scheme/host allowlist, redirect policy, and whether
       validation happens at fetch time (DNS rebinding) — SSRF.
- **Evidence bar**: untrusted bytes reaching an unsafe loader, or a
  path/URL used without containment.
- **Falsifiers**: `SafeLoader`/`safe_load`; a schema validates the input
  upstream (point at it); the path is joined then verified against the
  base; the data is signed and verified before parsing.
- **Exemplar**: BLOCKER 94 — "`yaml.load(body)` with the default loader on
  a webhook body — arbitrary object construction from the network." /
  **Noise twin**: `pickle.loads` on the service's own HMAC-verified cache
  bytes — the signature check keeps the trust boundary uncrossed.

### Hunt: Crypto Discipline

- **When**: the diff touches hashing, encryption, randomness, tokens,
  signatures, or TLS settings.
- **Protocol**:
    1. Identify the primitive **and its purpose** (integrity, secrecy,
       identity, dedup?).
    2. Check banned-for-security list: MD5, SHA1, DES/3DES, ECB, RC4,
       hand-rolled crypto.
    3. Check provenance: hardcoded keys/IVs, IV reuse under CTR/GCM,
       `random`/`Math.random()` where `secrets`/`crypto.randomBytes`
       is required.
    4. Check verification flags: `verify=False`,
       `rejectUnauthorized: false`, JWT `alg`/`exp`/`aud`/`iss` actually
       validated.
- **Evidence bar**: the primitive or flag plus its security-relevant
  purpose.
- **Falsifiers**: MD5/SHA1 used for non-security cache keys or dedup
  (and named as such); a TLS bypass gated to a test environment that
  cannot be production.
- **Exemplar**: IMPORTANT 87 — "password-reset tokens built with
  `random.choices` — seedable PRNG, predictable output; use
  `secrets.token_urlsafe`." / **Noise twin**: MD5 over rendered HTML as a
  cache key — no security claim on it.

### Hunt: Boundary Shift

- **When**: a refactor moves validation or sanitization, changes
  middleware order, splits a request path, or adds a second entry path
  into existing logic.
- **Protocol**:
    1. Diff the before/after position of validate-vs-use on every
       affected path.
    2. Enumerate **all** entry paths to the sink (`callers_of` on the
       moved function); check each still passes through the control.
    3. For dual-path migrations, confirm the old path kept its checks.
- **Evidence bar**: an entry path that now reaches the use site without
  the moved control.
- **Falsifiers**: the check moved *into* the shared callee — strictly
  deeper, covers every path; the new path cannot carry external input.
- **Exemplar**: IMPORTANT 86 — "sanitization moved from the shared parser
  up into the HTTP handler; the queue-consumer path now feeds the parser
  unsanitized." / **Noise twin**: validation moved from two handlers into
  the one service both call — coverage got stronger, not weaker.

### Hunt: Dependency Delta

- **When**: dependency manifests or lockfiles are in the changed set
  (triage may have flagged this for priority).
- **Protocol**:
    1. Read the manifest hunk: new packages, version jumps, loosened pins.
    2. Check pin discipline against repo convention, downgrades that cross
       security fixes, and suspicious provenance (typosquat-shaped names,
       brand-new packages for trivial tasks).
    3. Confirm the lockfile matches the manifest's intent.
- **Evidence bar**: the manifest line plus the concrete risk it admits.
- **Falsifiers**: the lockfile pins an exact safe version regardless of
  the loose range; the "new" package is an existing workspace member;
  automated dependency tooling governs the pin.
- **Exemplar**: IMPORTANT 80 — "`requests` loosened from `==2.32.3` to
  `>=2.0`, making CVE-affected pre-2.31 versions installable." / **Noise
  twin**: lockfile-only churn that re-resolves to identical versions.

## Severity Anchors

Grade with the contract's Severity Rubric and elevation rule. In this
dimension:

- **BLOCKER**: attacker-reachable exploit — a complete taint path, missing
  authz on a state-changing handler, a live secret reaching client or VCS.
- **IMPORTANT**: exploitable under named conditions, or a
  defense-in-depth gap with a concrete scenario — predictable tokens,
  validation asymmetry, risky dependency loosening.
- **SUGGESTION**: hardening with a named payoff — constant-time compare,
  `SameSite`, a missing security header on an authenticated app.

## Recall Sweep

After the hunts, sweep the diff once against these. Flag only what passes
the contract's Taste Test:

- XSS sinks: `innerHTML`, `document.write`, reflected URL params, template
  literals in HTML context.
- Log injection: newline forging, structured-log fields from untrusted
  input.
- CSRF: state change via GET, missing token validation, `SameSite` unset.
- CORS: wildcard origin with credentials; permissive methods/headers.
- Sessions/JWT: fixation (no rotation at login), tokens in localStorage,
  missing `exp`, `alg: none`.
- Headers: CSP, `X-Content-Type-Options: nosniff`, HSTS; version
  disclosure.
- Exposure: stack traces or internal paths in client errors, PII at
  INFO/DEBUG, GraphQL introspection in prod, unauthenticated debug/admin
  endpoints, open redirects.
