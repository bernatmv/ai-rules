# Security Review Criteria

OWASP-aligned security review checklist. Always evaluated regardless of mode.

Severity levels reference `$SKILLS/sdd-common/references/review-conventions.md`.

## Contents
- [Authentication and Authorization](#authentication-and-authorization)
- [Input Validation and Injection Prevention](#input-validation-and-injection-prevention)
- [Cryptographic Practices](#cryptographic-practices)
- [Data Protection](#data-protection)
- [Logging and Error Handling](#logging-and-error-handling)
- [Cloud Security (Conditional)](#cloud-security-conditional)
- [OWASP Severity Mapping](#owasp-severity-mapping)

---

## Authentication and Authorization

| # | Check | Severity | Pass | Fail |
|---|-------|----------|------|------|
| 1 | Auth checks on protected routes | Critical | All protected endpoints verify authentication | Missing auth middleware on sensitive routes |
| 2 | Authorization enforcement | Critical | Role/permission checks before resource access | Users can access resources beyond their role |
| 3 | Session management | High | Sessions expire; tokens rotated; logout invalidates | Sessions never expire; tokens reused after logout |
| 4 | Secure token handling | High | Tokens stored securely; not exposed in URLs or logs | Tokens in URL params, localStorage (when cookies available), or logged |
| 5 | Default deny | Medium | Access denied unless explicitly granted | Permissive defaults; new endpoints open by default |

## Input Validation and Injection Prevention

| # | Check | Severity | Pass | Fail |
|---|-------|----------|------|------|
| 6 | SQL/NoSQL parameterization | Critical | All queries use parameterized statements or ORM | String concatenation in queries; raw user input in queries |
| 7 | XSS prevention | Critical | User input escaped/sanitized before rendering; CSP headers set | Raw HTML insertion; `dangerouslySetInnerHTML` with user input |
| 8 | Command injection | Critical | No shell commands with user input; arguments escaped | `exec()` or `system()` with unsanitized input |
| 9 | Path traversal | High | File paths validated; no `../` sequences allowed | User-controlled file paths without validation |
| 10 | Input boundary validation | Medium | Length limits, type checks, range validation on all inputs | Unbounded string inputs; missing type coercion |
| 11 | CSRF protection | High | Anti-CSRF tokens on state-changing requests; SameSite cookies | No CSRF protection on forms or API mutations |

## Cryptographic Practices

| # | Check | Severity | Pass | Fail |
|---|-------|----------|------|------|
| 12 | No hardcoded secrets | Critical | Secrets from environment/vault/secrets manager | API keys, passwords, tokens in source code |
| 13 | Strong algorithms | High | Industry-standard algorithms (AES-256, bcrypt, SHA-256+) | MD5 for hashing; DES; custom crypto implementations |
| 14 | TLS enforcement | High | All external communication over HTTPS/TLS | HTTP endpoints; mixed content; TLS 1.0/1.1 |
| 15 | Key management | High | Keys rotatable; stored in secrets manager; not in code | Keys embedded in source; no rotation mechanism |

## Data Protection

| # | Check | Severity | Pass | Fail |
|---|-------|----------|------|------|
| 16 | PII handling | High | PII identified and protected; minimized collection | PII stored in plain text; collected unnecessarily |
| 17 | Encryption at rest | High | Sensitive data encrypted in storage | Sensitive data in plain-text files or unencrypted DB fields |
| 18 | Data minimization | Medium | Only necessary data collected and retained | Excessive data collection; no retention policy |
| 19 | Secure deletion | Medium | Sensitive data properly purged when no longer needed | Data left in temp files, caches, or logs after use |

## Logging and Error Handling

| # | Check | Severity | Pass | Fail |
|---|-------|----------|------|------|
| 20 | No sensitive data in logs | High | Logs redact PII, tokens, passwords, keys | Passwords, tokens, or PII written to log output |
| 21 | Sufficient audit trail | Medium | Security-relevant events logged (auth, access, changes) | No logging of authentication attempts or access patterns |
| 22 | No verbose errors in production | Medium | Production errors show generic messages; details in server logs | Stack traces, SQL errors, or internal paths exposed to users |
| 23 | Error handling completeness | Medium | All error paths handled; no information leakage | Unhandled exceptions reveal implementation details |

## Cloud Security (Conditional)

Load this section when:
1. **Spec-aware mode**: tech.md mentions AWS, GCP, Azure, or cloud infrastructure.
2. **Standalone mode (no tech.md)**: Scan changed files for cloud SDK imports (`boto3`, `@aws-sdk/*`, `@google-cloud/*`, `@azure/*`, `aws-cdk`, `terraform`). If any found, apply these checks.

| # | Check | Severity | Pass | Fail |
|---|-------|----------|------|------|
| 24 | IAM least privilege | High | Service roles have minimum required permissions | Wildcard permissions; overly broad IAM policies |
| 25 | Storage bucket policies | High | Buckets/blobs not publicly accessible unless intended | Public read/write on storage containing sensitive data |
| 26 | Secrets manager usage | High | Runtime secrets from secrets manager, not env files | Secrets in .env files committed to repo; hardcoded in config |

## OWASP Severity Mapping

| OWASP Category | Maps to Severity |
|---------------|-----------------|
| A01 Broken Access Control | Critical |
| A02 Cryptographic Failures | Critical |
| A03 Injection | Critical |
| A04 Insecure Design | High (Critical if exploitable) |
| A05 Security Misconfiguration | High (Critical if exploitable) |
| A06 Vulnerable Components | Medium |
| A07 Auth Failures | High (Critical if exploitable) |
| A08 Software/Data Integrity | High |
| A09 Logging Failures | Medium |
| A10 SSRF | High (Critical if exploitable) |
