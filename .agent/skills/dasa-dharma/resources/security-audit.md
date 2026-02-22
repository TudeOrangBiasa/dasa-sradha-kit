# OWASP / PCI Security Audit Checklist
**Owner: Dasa Dharma (The Guardian)**

When conducting a security review of a plan or implementation, explicitly check against the following critical vulnerabilities. Do not approve a `task.md` or `implementation_plan.md` if these are violated.

## 1. Injection (SQLi, NoSQLi, XSS, Command Injection)
- [ ] Are all database inputs parameterized or using a secure ORM?
- [ ] Is user input sanitized before being rendered in the DOM?
- [ ] Are shell commands executed with unchecked user input?

## 2. Authentication & Session Management
- [ ] Are passwords hashed using strong algorithms (e.g., Argon2, bcrypt)?
- [ ] Are tokens (JWT/OAuth) stored securely (HttpOnly cookies, not LocalStorage for sensitive data)?
- [ ] Do sessions timeout appropriately?

## 3. Sensitive Data Exposure
- [ ] Are API keys, secrets, or database credentials hardcoded in the source or pushed to Git?
- [ ] Is PII (Personally Identifiable Information) encrypted at rest?
- [ ] Are TLS/SSL encryptions strictly enforced in transit?

## 4. Broken Access Control (IDOR)
- [ ] Can an authenticated user access another user's data by changing an ID in the URL/API payload?
- [ ] Are admin endpoints rigorously protected with proper role checks?

## 5. Security Misconfiguration
- [ ] Are debug modes or verbose error traces disabled in production setups?
- [ ] Are CORS policies locked down to specific origins (no `*` in production)?
