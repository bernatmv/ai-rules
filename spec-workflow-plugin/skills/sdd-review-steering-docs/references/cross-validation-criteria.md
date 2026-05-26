# Steering Document Cross-Validation Criteria

Applies the **Cross-Document Validation Framework** from `$SKILLS/sdd-common/references/cross-validation.md`
to the three steering documents.

## Contents
- [Document Pairs](#document-pairs)
- [Duplication Detection Criteria](#duplication-detection-criteria)
- [Conflict Detection Criteria](#conflict-detection-criteria)
- [Gap Detection Criteria](#gap-detection-criteria)
- [Report Format](#report-format)

## Document Pairs

| Pair | Key Overlap Areas |
|------|------------------|
| product.md ↔ tech.md | Feature capabilities vs technology that enables them; performance claims vs architecture |
| product.md ↔ structure.md | Feature areas vs code locations; user-facing concepts vs module organization |
| tech.md ↔ structure.md | Technology patterns vs directory conventions; framework usage vs file placement |

## Duplication Detection Criteria

### product.md ↔ tech.md Duplication

**Common duplications:**
- Technology stack listed in both (tech list belongs in tech.md only)
- Architecture overview repeated (belongs in tech.md only)
- Performance targets stated in both (product.md states user-facing goals, tech.md states technical constraints)

**Pass:**
- product.md describes *what* the tech enables without re-listing the stack
- tech.md describes *how* without restating product goals
- Cross-references used instead of repetition

**Fail:**
- Same technology list appears in both documents
- Architecture described at the same level of detail in both
- Copy-pasted sections with minor wording differences

### product.md ↔ structure.md Duplication

**Common duplications:**
- Feature lists duplicated as module descriptions
- Component names repeated with identical descriptions

**Pass:**
- product.md names features; structure.md shows where they live
- No prose overlap — structure.md maps features to paths, not re-describing them

**Fail:**
- Feature descriptions copy-pasted into structure.md module descriptions
- Identical component explanations in both docs

### tech.md ↔ structure.md Duplication

**Common duplications:**
- Technology patterns described in both (pattern belongs in tech.md, directory mapping in structure.md)
- Configuration file listings duplicated

**Pass:**
- tech.md describes the pattern; structure.md shows which directories follow it
- Config files listed once in structure.md, referenced from tech.md

**Fail:**
- Same pattern explanation in both documents
- Configuration files enumerated in both

## Conflict Detection Criteria

| Conflict Type | Example | Severity |
|--------------|---------|----------|
| **Technology contradiction** | tech.md says "REST API", structure.md organizes around GraphQL resolvers | 🔴 Critical |
| **Architecture mismatch** | tech.md says "monolith", product.md references "microservice deployment" | 🔴 Critical |
| **Feature scope conflict** | product.md lists a feature, structure.md shows no corresponding module | 🟡 Warning |
| **Naming inconsistency** | product.md calls it "Dashboard", tech.md calls it "Admin Panel", structure.md uses "control-panel/" | 🟡 Warning |
| **Version conflict** | tech.md says Node 18, structure.md references Node 20 config | 🔴 Critical |

### Conflict Resolution Rules

1. **Technology facts** → tech.md is authoritative, other docs must align
2. **Product scope** → product.md is authoritative, other docs must reflect
3. **File/directory facts** → structure.md is authoritative (verifiable against filesystem)
4. **When both are outdated** → Flag for user decision, do not auto-resolve

## Gap Detection Criteria

| Gap Type | Check | Severity |
|----------|-------|----------|
| Feature without tech backing | product.md feature has no tech.md pattern/component | 🟡 Warning |
| Tech pattern without structure | tech.md pattern has no structure.md directory mapping | 🟡 Warning |
| Structure module without product context | structure.md module has no product.md feature | 🟢 Suggestion |
| Integration without structure mapping | tech.md lists external integration, structure.md has no corresponding adapter/client directory | 🟡 Warning |

## Report Format

Include in the steering review report after per-document sections:

### Cross-Validation Summary

| Metric | Count |
|--------|-------|
| Document pairs checked | 3 |
| Duplications found | [n] |
| Conflicts found | [n] |
| Gaps found | [n] |
| Total issues | [n] |

### Cross-Validation Findings

| # | Documents | Topic | Issue | Severity | Recommendation |
|---|-----------|-------|-------|----------|---------------|
| 1 | [pair] | [topic] | [type] | [icon] | [single sentence] |

### Consolidation Recommendations

For each duplication/conflict, provide:
1. **Authoritative document** (which doc should own this content)
2. **Action for other doc(s)** (remove and cross-reference / update to match / escalate to user)
3. **Suggested edit** (brief description of what to change)
