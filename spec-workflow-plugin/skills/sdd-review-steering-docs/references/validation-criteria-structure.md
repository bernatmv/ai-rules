# structure.md Validation Criteria

### 0. Document Size

Apply the **Document Size Limits** check from `$SKILLS/sdd-common/references/size-limits.md`.

### 1. Directory Structure Matches Codebase

**Pass:**
- Top-level directories accurate
- Purpose of each explained
- Important subdirectories called out

**Verification:** Run `ls -la` or `tree -L 2`

**Fail:**
- Directories don't exist
- Missing major directories
- Outdated from refactoring

### 2. Naming Conventions Accurate

**Pass:**
- File naming patterns documented
- Class/function conventions stated
- Test file patterns specified

**Verification:** Spot-check 5-10 files

**Fail:**
- Conventions don't match files
- Inconsistencies not acknowledged
- Missing common file types

### 3. Import Patterns Correctly Documented

**Pass:**
- Absolute vs relative preference stated
- Module alias patterns documented
- Import ordering conventions

**Verification:** Check source files for import styles

**Fail:**
- Import style contradicts code
- Missing alias configurations
- No import guidance

### 4. Module Boundaries Clear

**Pass:**
- Layered architecture explained
- Clear guidance on where code goes
- Module dependencies documented

**Fail:**
- Unclear where new features go
- Contradictory placement rules
- No boundary explanation

### 5. Code Organization Reflects Practices

**Pass:**
- Reflects actual team practices
- Testing patterns documented
- Component/service patterns explained

**Fail:**
- Idealistic patterns not followed
- Missing visible patterns
- Contradicts recent changes
