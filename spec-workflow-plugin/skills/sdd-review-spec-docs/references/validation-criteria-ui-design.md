# ui-design.md Validation Criteria

### 1. Layout Structure Clearly Described

**Pass:**
- Page/screen layouts are described with visual hierarchy
- Spatial relationships between components are clear
- Wireframes or layout descriptions provided for each affected view
- Layout flow is logical and user-friendly

**Fail:**
- No layout descriptions
- Ambiguous component placement
- Missing views that are in scope
- Layout contradicts requirements

### 2. Component Inventory Complete

**Pass:**
- All new and modified components listed
- Props, states, and visual variants documented
- Component reuse opportunities identified
- Status (new/modified) clearly indicated

**Fail:**
- Missing components referenced in requirements
- No props or states documented
- Duplicate components not consolidated
- Incomplete variant coverage

### 3. Interaction Patterns Defined

**Pass:**
- User flows described step-by-step
- State transitions documented
- Click, hover, keyboard behaviors specified
- Loading, error, and empty states covered

**Fail:**
- Missing user flows for key features
- No state transition documentation
- Edge case interactions undefined
- Missing feedback/response descriptions

### 4. Accessibility Requirements Addressed

**Pass:**
- WCAG compliance level stated
- Keyboard navigation documented
- Screen reader support specified
- Color contrast considerations noted
- Reduced motion preferences addressed

**Fail:**
- No accessibility section
- Missing keyboard navigation plan
- No ARIA roles or labels mentioned
- Color-only information indicators

### 5. Responsive Behavior Specified

**Pass:**
- Breakpoints defined with layout adaptations
- Mobile-first or adaptive strategy documented
- Component behavior across device sizes described
- Touch vs pointer interactions considered

**Fail:**
- No responsive strategy
- Missing breakpoint definitions
- Desktop-only design with no mobile consideration
- Inconsistent behavior across sizes
