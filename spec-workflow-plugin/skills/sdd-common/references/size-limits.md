# Document Size Limits

Steering documents should remain high-level and concise. When a document exceeds
its line limit, it likely contains implementation details, historical context, or
redundant content that belongs elsewhere.


## Contents

- [Default Limits](#default-limits)
- [Simplification Recommendation Template](#simplification-recommendation-template)
- [Line Counting Rules](#line-counting-rules)

## Default Limits

| Document Type | Line Limit | Severity When Exceeded |
|---------------|-----------|----------------------|
| Steering docs (product.md, tech.md, structure.md) | 200 lines | 🟡 Warning |
| PRD (prd.md) | 400 lines | 🟡 Warning |

## Simplification Recommendation Template

When a document exceeds its limit, generate recommendations using this structure:

| Section | Current Lines | Recommended Action | Target Lines |
|---------|--------------|-------------------|-------------|
| [section name] | [count] | [action: extract / condense / remove] | [target] |

**Standard actions:**
- **Extract to spec**: Move implementation-level detail into a spec document
- **Condense**: Rewrite section at higher abstraction level
- **Remove**: Content is redundant with another steering doc or outdated
- **Link instead**: Replace inline content with a reference to an external doc

## Line Counting Rules

- Count only non-empty, non-comment lines (exclude blank lines and HTML comments)
- Frontmatter (between `---` delimiters) is excluded
- **Fenced code blocks** (lines between ` ``` ` markers, fences included)
  are excluded — the counter targets authored prose, not transcribed
  output
- Tables and list markers count as one line each (standard markdown
  semantics)
- The limit is a guideline — exceeding it is a warning, not a failure

**Programmatic check** (source of truth: `sdd_core.text.iter_line_categories`):

```
.spec-workflow/sdd review/count-effective-lines.py --file <path> [--verbose]
```

`--verbose` adds a per-category breakdown (`effective`, `blank`,
`frontmatter`, `code_block`, `html_comment`).
