# tech.md Validation Criteria

### 0. Document Size

Apply the **Document Size Limits** check from `$SKILLS/sdd-common/references/size-limits.md`.

### 1. Technology Stack Accurate

**Pass:**
- Language and version specified
- Frameworks named with versions
- Database/storage identified
- Major dependencies listed

**Verification:** Check the project's dependency manifest(s) (e.g., `package.json`, `requirements.txt`, `go.mod`, `Package.swift`, etc.)

**Fail:**
- Missing major technologies
- Wrong versions
- Outdated mentions

### 2. Architecture Patterns Correctly Described

**Pass:**
- High-level architecture named (monolith, microservices)
- Key patterns identified (MVC, MVVM, event-driven)
- Data flow explained

**Fail:**
- Pattern doesn't match code
- Conflicting patterns
- Too generic ("best practices")

### 3. External Integrations Listed

**Pass:**
- Third-party APIs identified
- Internal service dependencies noted
- Auth providers mentioned

**Verification:** Check for API clients, SDK imports, config files

**Fail:**
- Missing integrations visible in code
- Deprecated integrations listed
- No integrations when code has many

### 4. Performance Requirements Realistic

**Pass:**
- Latency targets specified
- Throughput expectations mentioned
- Resource constraints acknowledged

**Fail:**
- Unrealistic targets
- No performance considerations
- Contradicts system behavior

### 5. Security Considerations Addressed

**Pass:**
- Authentication method documented
- Authorization model explained
- Data sensitivity classified
- Compliance requirements noted

**Fail:**
- No security section
- Contradicts implementation
- Missing obvious security patterns
