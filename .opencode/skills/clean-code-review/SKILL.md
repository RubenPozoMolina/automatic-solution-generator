---
name: clean-code-review
description: Review and improve code following Clean Code principles from Robert C. Martin
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: code-quality
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Clean Code Review

**What I do:**
Review code following Clean Code principles from Robert C. Martin to improve readability, maintainability, and software quality.

**When to use me:**
- Reviewing pull requests
- During refactoring
- Before important merges
- When improving legacy code
- In individual code reviews

**Fundamental Principles:**

## 1. Meaningful Names
- ✅ Use intention-revealing names
- ✅ Avoid disinformation (don't use `list` if it's not a list)
- ✅ Make meaningful distinctions (not `a`, `b`, `c`)
- ✅ Use pronounceable names (`generationDate` not `genrdt`)
- ✅ Use searchable names (`MAX_THREADS` not `20`)
- ❌ Avoid mental mappings and Hungarian notation
- ❌ Don't be cute, avoid puns

## 2. Functions
- **Small**: Maximum 20 lines ideally
- **Do one thing**: Each function should do ONE thing and do it well
- **One level of abstraction**: Don't mix levels in a function
- **Step-down rule**: From top to bottom, general to specific
- **Arguments**:
  - 0-1 arguments: Ideal
  - 2 arguments: Avoid when possible
  - 3+ arguments: Use objects/structured arguments
  - ❌ Avoid boolean flags: `process(true)` doesn't say what it does
- **No side effects**: Don't modify state unexpectedly
- **Command Query Separation**: Query function does NOT modify, command does NOT return
- ❌ Avoid `null`: Throw exceptions or return default values

## 3. Comments
- ✅ Comments that explain INTENTION
- ✅ Warnings about consequences
- ✅ TODOs with context
- ❌ DON'T use comments to explain HOW code works
  - Improve code to make it self-documenting
- ❌ Remove commented-out code
- ❌ Remove obsolete and redundant comments
- ❌ Don't comment closing braces

## 4. Formatting
- **Vertical**: Spacing between concepts, like a newspaper
  - Related functions near each other vertically
  - Order by dependency (dependencies below)
- **Horizontal**:
  - Maximum 80-100 characters per line
  - Consistent indentation (2 or 4 spaces)
  - Alignment when it improves readability

## 5. Objects and Data Structures
- **Hide structure**: Use getters instead of public field access
- **Law of Demeter**: No method chains (`a.getB().getC().do()`)
  - ❌ Avoid "train wrecks": `context.getProject().getUser().getAddress().getCity()`
  - ✅ Prefer: `context.getCity()`
- **Small classes**: Maximum 200 lines ideally
- **Single Responsibility**: One class, one responsibility

## 6. Error Handling
- ✅ Use EXCEPTIONS instead of error codes
- ✅ Throw unchecked exceptions by default
- ✅ Provide context in exception messages
- ✅ Define exceptions in terms of caller's needs
- ✅ Try-catch-finally skeleton first
- ❌ Don't return null
- ❌ Don't pass null

## 7. Tests
- **Three laws of TDD**:
  1. Don't write production code without a failing test first
  2. Don't write more tests than sufficient to fail
  3. Don't write more code than sufficient to pass the test
- ✅ Clean tests: readable, expressive
- ✅ **F.I.R.S.T.**:
  - **F**ast: Fast tests
  - **I**solated: Isolated
  - **R**epeatable: Repeatable
  - **S**elf-validating: Self-validating
  - **T**imely: Timely
- ✅ One assert per test (preferable)
- ✅ Expressive test names

**Clean Code Principles:**
- **Boy Scout Rule**: Leave the campground cleaner than you found it
- **DRY**: Don't Repeat Yourself
- **KISS**: Keep It Simple, Stupid
- **YAGNI**: You Aren't Gonna Need It

**Common Heuristics (Smells):**
- Functions with too many arguments (F1)
- Flag arguments (F3)
- Dead functions (F4)
- Duplication (G5)
- Code at wrong level of abstraction (G6)
- Inconsistency (G11)
- Clutter (G12)
- Feature Envy (G14) - function uses more data from another class than its own
- Descriptive names (N1)
- Insufficient tests (T1)

**Review Process:**
1. Analyze variable, function, class names
2. Verify size and single responsibility
3. Detect duplication
4. Review error handling
5. Evaluate comments (know when to remove vs necessary)
6. Identify specific code smells
7. Provide concrete changes with examples
8. Prioritize by maintainability impact

**Example change:**

```javascript
// ❌ DIRTY CODE
function p(d){
  let a=d.filter(x=>x>10);
  let b=a.map(x=>x*2);
  return b;
}

// ✅ CLEAN CODE
function filterAndDouble(values) {
  const MIN_VALUE = 10;
  const multiplier = 2;
  
  const filtered = values.filter(value => value > MIN_VALUE);
  const doubled = filtered.map(value => value * multiplier);
  
  return doubled;
}
```

**How to use me:**
When invoked, request:
1. What file or code do you want reviewed?
2. Are there specific aspects to focus on? (names, functions, tests, etc.)
3. Provide detailed analysis with refactoring examples
4. Suggest step-by-step changes

**Expected results:**
- Identification of Clean Code violations
- Concrete refactoring suggestions
- Improved readability and maintainability
- More expressive and professional code

---

# Configuration for English

To enforce English language for all future agents, skills, and configuration:

## Global Configuration (Recommended)

Add to your global config `~/.config/opencode/opencode.json`:

```jsonc
{
  "language": "en",
  "language_preference": "always_use_english"
}
```

## Project-level Configuration

Add to project config `.opencode/opencode.json`:

```jsonc
{
  "language": "en"
}
```

## Agent/Skill Frontmatter

All agents and skills should use English in:
- `description` field
- `name` field  
- Content and documentation
- Prompts and instructions

This ensures consistency across all projects and team collaboration.