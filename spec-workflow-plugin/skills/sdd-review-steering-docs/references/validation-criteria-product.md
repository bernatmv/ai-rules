# product.md Validation Criteria

### 0. Document Size

Apply the **Document Size Limits** check from `$SKILLS/sdd-common/references/size-limits.md`.

### 1. Product Purpose Clearly Stated

**Pass:**
- One clear sentence/paragraph explaining what the product does
- Answers "what problem does this solve?"
- No unexplained jargon

**Fail:**
- Vague statements ("improves productivity")
- Technical implementation instead of purpose
- Multiple conflicting purposes

### 2. Target Users Accurately Described

**Pass:**
- Specific user types identified (e.g., "engineering managers")
- User needs/pain points mentioned
- Primary vs secondary users distinguished

**Fail:**
- Generic "users" without specificity
- No mention of who benefits
- Internal vs external unclear

### 3. Key Features Comprehensive

**Pass:**
- Core features listed (3-7 typically)
- Features map to user needs
- Current vs planned distinguished

**Fail:**
- Missing obvious features from codebase
- Too granular (implementation details)
- Too abstract (no concrete capabilities)

### 4. Business Objectives Align with Reality

**Pass:**
- Objectives specific and achievable
- Timeline/priorities mentioned
- Connects features to business value

**Fail:**
- Aspirational without grounding
- Contradicts actual code behavior
- No connection to features

### 5. Success Metrics Measurable

**Pass:**
- Quantifiable metrics (latency, adoption)
- Metrics relate to objectives
- Baseline or target mentioned

**Fail:**
- Vague ("improve satisfaction")
- No metrics
- Unmeasurable metrics
