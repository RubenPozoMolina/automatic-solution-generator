---
name: create-ticket
description: Create structured task tickets in the tasks directory
license: MIT
compatibility: opencode
metadata:
  audience: developers, product-owners, qa-engineers, architects
  workflow: task-management
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Ticket Creation Skill

## What I do

I create structured task tickets as Markdown files in the `tasks/` directory of the **target project directory**. Each ticket follows a standardized format with metadata, clear descriptions, acceptance criteria, and workflow state tracking.

The target project directory is the output/project folder specified in the current operation context (e.g., `output_path/tasks/` or the designated project root's `tasks/` directory).

## When to use me

Use this skill when you need to:

- Create a new task, story, bug, epic, spike, or subtask
- Document a technical decision request
- Track work items in a structured format
- Escalate issues or uncertainties to other team members
- Create reproducible bug reports
- Plan technical investigation or research

## Ticket Types

| Type | Purpose |
|------|---------|
| **Epic** | Large initiatives grouping multiple stories/tasks |
| **Story** | User-facing functionality from user's perspective |
| **Task** | Technical work (implementation, refactoring, decisions) |
| **Bug** | Defects, regressions, or unexpected behaviors |
| **Subtask** | Smaller steps within a parent ticket |
| **Spike** | Technical research or investigation to reduce uncertainty |

## Status Values

| Status | Description |
|--------|-------------|
| **Backlog** | Ticket created but not yet prioritized |
| **To Do** | Prioritized and ready for work |
| **In Progress** | Work currently being done |
| **In Review** | Implementation complete, awaiting review |
| **In Testing** | Approved in review, awaiting QA verification |
| **Blocked** | Work stopped due to external dependency |
| **Done** | All criteria verified, meeting Definition of Done |

## Priority Values

| Priority | Description | When to Use |
|----------|-------------|-------------|
| **P0 (Critical)** | Must be done immediately, blocks release | Critical bugs, security issues, showstoppers |
| **P1 (High)** | High priority, should be done this sprint | Major features, critical improvements |
| **P2 (Medium)** | Normal priority, plan for next sprint | Standard features, improvements |
| **P3 (Low)** | Nice to have, do when capacity allows | Enhancements, cosmetics, technical debt |

## How to invoke me

Call me with details about the ticket you want to create and the target project:

```
create-ticket: Create a bug ticket for login authentication failing with valid credentials in project: /path/to/project (P0)
```

```
create-ticket: Create a story for user profile management feature in project: [output_path] (P2)
```

```
create-ticket: Create a spike to investigate database migration options (3 days) in project: [target_project] (P1)
```

**Note**: Specify the target project directory where the `tasks/` folder should be created. This is typically the output directory or the project being generated/worked on. You can also specify the priority level (P0-P3).

## Ticket Metadata

Every ticket includes these fields:

| Field | Description |
|-------|-------------|
| **Type** | Epic, Story, Task, Bug, Subtask, or Spike |
| **Status** | Workflow state (starts as Backlog) |
| **Priority** | P0 (Critical), P1 (High), P2 (Medium), P3 (Low) |
| **Created By** | Who created the ticket (you/your agent) |
| **Assigned To** | Who should work on this ticket |

## Ticket Template

When creating a ticket, I use this structure:

```markdown
# [TICKET-ID]: [Short, Descriptive Title]

## Metadata
- **Type:** [Type]
- **Status:** Backlog
- **Priority:** P0/P1/P2/P3
- **Created By:** [Your identifier]
- **Assigned To:** [Assignee identifier]

---

## Description
[Clear and concise summary]

---

## Details & Context
- **Target Files / Modules:** [Affected files or components]
- **Prerequisites / Dependencies:** [Blocking tickets or required config]

---

## Specification / Options / Steps to Reproduce
[Varies by type - detailed requirements, alternative options, or reproduction steps]

---

## Acceptance Criteria (Definition of Done)
- [ ] Functional criteria verified
- [ ] Unit & integration tests implemented (>=90% coverage if applicable)
- [ ] Clean code & security standards verified
- [ ] Logging properly integrated
```

## Examples

### Creating a Bug Report

**Input:** `create-ticket: Bug - API returns 500 error when uploading large files`

**Output:** Ticket with:
- Clear reproduction steps
- Expected vs actual behavior
- Error logs and stack traces
- Affected endpoints and file sizes tested

### Creating a Technical Decision Task

**Input:** `create-ticket: Task - Decide between PostgreSQL and MongoDB for document storage`

**Output:** Ticket with:
- Problem context
- Option A: PostgreSQL with trade-offs
- Option B: MongoDB with trade-offs
- Recommendation for review

### Creating a Spike

**Input:** `create-ticket: Spike - Research Kubernetes deployment options (2 days)`

**Output:** Ticket with:
- Research question
- Timebox: 2 days
- Investigation scope
- Expected deliverables: findings and recommendations

## Ticket Lifecycle

```
Backlog → To Do → In Progress → In Review → In Testing → Done
                ↖          ↙            ↙
                  Blocked ←─────────┘
```

## Important Notes

- Tickets are created in the `tasks/` directory **of the target project directory** (not necessarily the current working directory)
- The target project is specified when invoking the skill (e.g., `in project: [output_path]`)
- New tickets start with `Status: Backlog` and default `Priority: P2 (Medium)`
- Explicitly set priority: P0 (Critical), P1 (High), P2 (Medium), P3 (Low)
- Use English for ticket content (following best practices)
- Assign appropriate agents based on the ticket type and workflow state
- Include sufficient context for the assignee to understand and act
