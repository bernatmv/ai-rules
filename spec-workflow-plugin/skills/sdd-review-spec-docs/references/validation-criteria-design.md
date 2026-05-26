# design.md Validation Criteria

## Contents
- [Steering Document Alignment Documented](#1-steering-document-alignment-documented)
- [Code Reuse Analysis Thorough](#2-code-reuse-analysis-thorough)
- [Architecture Clearly Described](#3-architecture-clearly-described)
- [Components and Interfaces Well-Defined](#4-components-and-interfaces-well-defined)
- [Error Handling Comprehensive](#5-error-handling-comprehensive)
- [Testing Strategy Thorough](#6-testing-strategy-thorough)
- [Dependency Removal Impact Documented](#7-dependency-removal-impact-documented)

### 1. Steering Document Alignment Documented

**Pass:**
- References tech.md for technology decisions
- References structure.md for organization
- Explains how design follows documented patterns
- Deviations justified

**Verification:** Mentioned patterns exist in steering docs

**Fail:**
- No steering doc references
- Claims alignment without demonstration
- Uses undocumented patterns without explanation

### 2. Code Reuse Analysis Thorough

**Pass:**
- Lists existing components to leverage
- Explains how utilities will be used
- Identifies integration points
- Notes new vs extended code

**Verification:** Mentioned components exist in codebase

**Fail:**
- No code reuse mention
- Reinvents existing functionality
- Missing obvious reuse opportunities
- Integration points unclear

### 3. Architecture Clearly Described

**Pass:**
- High-level architecture diagram/description
- Data flow explained
- Component relationships clear
- Patterns named and justified
- Modular design followed

**Fail:**
- No architecture overview
- Diagram incomprehensible
- Data flow unclear
- Monolithic without separation
- Patterns unexplained

### 4. Components and Interfaces Well-Defined

**Pass:**
- Each component has clear purpose
- Public interfaces specified
- Dependencies listed per component
- Reuse of existing components documented
- Code examples where helpful

**Fail:**
- Vague component descriptions
- No interface specifications
- Dependencies unclear/circular
- Missing component boundaries
- Too abstract to implement

### 5. Error Handling Comprehensive

**Pass:**
- Error scenarios identified
- Handling strategy per error type
- User impact documented
- Recovery mechanisms described
- No inconsistent system states

**Fail:**
- No error handling section
- Only happy path considered
- Generic "errors handled" statements
- Missing recovery strategies

### 6. Testing Strategy Thorough

**Pass:**
- Unit testing approach with key components
- Integration testing with flows/integration points
- E2E testing with user scenarios
- Aligns with acceptance criteria
- Edge cases included

**Verification:** Each acceptance criterion maps to test approach

**Fail:**
- Testing section missing/empty
- Only one testing level
- No specific components/flows identified
- Doesn't cover acceptance criteria
- Vague "tests will be written"

**Thoroughness:** Comprehensive (all 3 levels, all criteria) → Adequate (2+ levels) → Basic (single level) → Insufficient (missing/vague)

### 7. Dependency Removal Impact Documented

**Pass:**
- Design explains how removed behavior is achieved
- Provider strategy stated for feature management
- Vendor-neutral approach considered
- Data flow shows new configuration source
- Decoupling risks identified with mitigations

**Fail:**
- Removes dependency without replacing behavior
- No provider strategy for dynamic config
- Data flow implies old dependency
- Trade-offs not acknowledged
