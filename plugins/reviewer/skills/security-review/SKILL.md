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

# Security Review Checklist

Trace every external input to its first use. Verify sanitization or
validation at the trust boundary. The goal is to find code that can be
exploited to gain unauthorized access, execute arbitrary code, leak
sensitive data, or compromise system integrity.

## When to Flag

- Flag only when untrusted input can actually reach the sink. Trace the taint;
  if every input is a server-side constant or already validated, skip.
- Test, example, or fixture code with hardcoded fake secrets is not a finding
  unless it can run in production.
- A safe construct (parameterized query, `shell=False`, autoescape on) is not
  a finding even when it touches user input.

## 1. Injection

### SQL Injection

- String interpolation or f-strings in SQL queries:
  `f"SELECT * FROM users WHERE id = {user_id}"`
- String concatenation in query building:
  `query = "SELECT " + columns`
- Raw SQL without parameterized queries in ORMs
  (`text()`, `.raw()`, `execute()`)
- Stored procedures with dynamic SQL inside
- **Safe**: parameterized queries (`%s`, `$1`, `:param`), ORM
  query builders with bound parameters

### Command Injection

- `subprocess` with `shell=True` and user-controlled input
- `os.system()`, `os.popen()` with interpolated arguments
- Template-based command construction:
  `f"grep {pattern} {filename}"`
- `child_process.exec()` in Node.js with user input
- **Safe**: `subprocess.run([cmd, arg1, arg2], shell=False)`,
  `shlex.quote()`

### Template Injection

- Jinja2 without autoescaping:
  `Environment(autoescape=False)`
- User input rendered directly in templates without escaping
- `render_template_string()` with user-controlled template
- **Safe**: `Environment(autoescape=True)`,
  `markupsafe.escape()`

### Log Injection

- User input logged without sanitization:
  `logger.info(f"User: {user_input}")`
- Log forging: newlines in user input create fake log entries
- Structured logging fields from untrusted sources

### Cross-Site Scripting (XSS)

- `innerHTML`, `dangerouslySetInnerHTML` with user content
- `document.write()` with unsanitized input
- Template literals rendered in HTML context
- URL parameters reflected in page content without encoding

## 2. Authentication and Authorization

### Authentication Gaps

- Endpoint/handler missing authentication decorator/middleware
- Authentication check in conditional branch that can be bypassed
- Token validation that doesn't verify expiration, issuer, or
  audience
- Password comparison using `==` instead of constant-time compare
- Session fixation: session ID not rotated after login

### Authorization Gaps

- Missing authorization check on state-changing operations
  (POST, PUT, DELETE)
- **IDOR** (Insecure Direct Object Reference): accessing
  resources by ID without ownership check
- Horizontal privilege escalation: user A accesses user B's data
- Vertical privilege escalation: regular user accesses admin
  endpoints
- Role check that doesn't account for role hierarchy

### JWT and Token Security

- JWT with `alg: none` accepted
- JWT secret hardcoded in source code
- Missing token expiration (`exp` claim)
- Refresh token reuse not detected (token replay)
- Token stored in localStorage (XSS accessible) vs httpOnly
  cookie

## 3. Secrets and Credentials

### Hardcoded Secrets

- API keys, passwords, tokens in source code or configuration
  committed to git
- Connection strings with embedded credentials
- Private keys, certificates in the repository
- Default passwords or test credentials in production code paths

### Secret Patterns to Detect

- `password = "..."`, `api_key = "..."`, `secret = "..."`
- `AWS_SECRET_ACCESS_KEY`, `PRIVATE_KEY`, `Bearer <token>`
- Base64-encoded secrets that decode to credential-like strings
- `.env` files committed to version control

### Secure Secret Handling

- Secrets loaded from environment variables or secret managers
- `SecretStr` in Pydantic for sensitive fields (prevents
  logging/serialization)
- Secrets not logged, not in error responses, not serialized

## 4. Cryptographic Misuse

### Banned Primitives

- **MD5** for security purposes (collision-vulnerable)
- **SHA1** for security purposes (collision-demonstrated)
- **DES/3DES** (deprecated, short key length)
- **ECB mode** (reveals patterns in encrypted data)
- **RC4** (biased output, broken)

### Dangerous Patterns

- Hardcoded encryption keys or initialization vectors (IVs)
- IV reuse with the same key (destroys confidentiality in
  CTR/GCM)
- Using `random` or `Math.random()` for security-sensitive
  randomness (use `secrets`, `crypto.randomBytes()`)
- Custom cryptographic implementations (use established
  libraries)
- Certificate validation disabled (`verify=False`,
  `rejectUnauthorized: false`)

## 5. Data Exposure

### PII in Logs

- Email addresses, phone numbers, IP addresses logged at INFO
  or DEBUG
- Full request/response bodies logged without redaction
- Stack traces with sensitive data in production error responses
- User session tokens or credentials in log output

### Error Message Leakage

- Database error messages exposed to the client (table names,
  query structure)
- Stack traces returned in API responses in production
- Internal file paths revealed in error messages
- Version numbers and technology stack disclosed in headers

### Serialization Safety

- `model_dump()` or `to_dict()` including sensitive fields
- GraphQL introspection enabled in production
- API responses including internal-only fields
- Debug endpoints or admin panels accessible without auth

## 6. Input Validation at Trust Boundaries

### Missing Validation

- Request parameters used directly without type checking or
  bounds
- File upload without type, size, or content validation
- URL parameters parsed and used without sanitization
- Headers or cookies used as trusted input

### Unsafe Deserialization

- `pickle.loads()` on untrusted data (arbitrary code execution)
- `yaml.load()` without `Loader=SafeLoader` (arbitrary code
  execution)
- `eval()`, `exec()` on user-controlled strings
- `JSON.parse()` on untrusted input without schema validation

### Path Traversal

- User-controlled filename concatenated to a base path without
  sanitization
- `../` sequences not stripped or resolved before file access
- Symbolic link following in file operations
- Archive extraction (zip, tar) without path validation
  (zip slip)

### SSRF (Server-Side Request Forgery)

- User-controlled URL passed to `requests.get()`, `fetch()`,
  `urllib`
- DNS rebinding: URL validated against allowlist but DNS resolves
  differently at fetch time
- Internal network access via URL schemes (`file://`, `gopher://`,
  `dict://`)
- Redirect following that leads to internal resources

## 7. Dependency Security

### Version Pinning

- Unpinned dependencies: `requests` vs `requests>=2.31.0,<3.0`
- Wildcard versions: `*`, `latest`, `^` with major version 0
- Lock file out of sync with requirements

### Known Vulnerabilities

- Dependencies with known CVEs (check `pyproject.toml`,
  `package.json`)
- Deprecated packages still in use
- Packages with maintainer compromise history

## 8. Configuration Security

### CORS

- `Access-Control-Allow-Origin: *` on authenticated endpoints
- Credentials allowed with wildcard origin
- Overly permissive allowed methods or headers

### CSRF

- State-changing operations via GET requests
- Missing CSRF token validation on POST/PUT/DELETE
- SameSite cookie attribute not set

### Headers

- Missing `Content-Security-Policy`
- Missing `X-Content-Type-Options: nosniff`
- Missing `Strict-Transport-Security` on HTTPS endpoints
- Server version disclosed in `Server` header
