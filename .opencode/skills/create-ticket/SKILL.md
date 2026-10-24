---
name: create-ticket
description: Create structured task tickets with sprint assignments from PRD analysis
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: project-management
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

## What I Do

I analyze PRDs (Product Requirement Documents) and create structured task tickets in JSON format with the following information:
- Task ID and title
- Sprint assignment
- Priority level
- Estimated effort (story points)
- Dependencies
- Acceptance criteria
- Technical notes
- Definition of done
- Timestamps

## When to Use Me

Use this skill when:
- You have a completed PRD that needs to be broken down into tasks
- You need to create tickets for a sprint backlog
- Tasks need to be organized by sprint assignments

## Process

### Step 1: Analyze the PRD
- Read the provided PRD file
- Identify major features and user stories
- Extract requirements and acceptance criteria
- Note any dependencies between features

### Step 2: Create Task Tickets

For each task, create a JSON file in the `/tasks/` directory with the following structure:

Naming convention: `TYPE-ID-description.json`

```json
{
  "id": "TASK-001",
  "type": "<epic|story|task|subtask>",
  "title": "<Task Title>",
  "parent": "<PARENT-TYPE-ID or null>",
  "sprint": null,
  "priority": "<P0|P1|P2|P3>",
  "estimatedEffort": <story-points>,
  "status": "backlog",
  "assignee": null,
  "implementedBy": null,
  "reviewedBy": null,
  "testedBy": null,
  "requiresReview": true,
  "resultEvidence": [],
  "createdBy": "project-manager",
  "dependencies": ["<TYPE-XXX>"],
  "description": "<Clear description of what needs to be done>",
  "acceptanceCriteria": [
    "<Criterion 1>",
    "<Criterion 2>",
    "<Criterion 3>"
  ],
  "technicalNotes": "<Any technical implementation details or considerations>",
  "definitionDone": [
    "Code completed and reviewed",
    "Tests passing",
    "Documentation updated",
    "Deployed to staging"
  ],
  "statusHistory": [
    {
      "from": null,
      "to": "backlog",
      "actor": "project-manager",
      "timestamp": "<ISO-8601-timestamp>",
      "reason": "Ticket created",
      "evidence": []
    }
  ],
  "createdAt": "<ISO-8601-timestamp>",
  "updatedAt": "<ISO-8601-timestamp>"
}
```

**Orchestrator fields**:

- `requiresReview`: `true` for code changes; `false` for non-code work (documentation, design,
  research), which goes from `in-progress` straight to `in-testing`.
- `testedBy`: QA agent for `in-testing` (`qa-automation` by default, `qa-manual` for UX checks).
- `resultEvidence`: filled by the executing agent together with `result` when its phase ends.
- `priority` must be one of `P0`, `P1`, `P2`, `P3`; any other value is planned last.

**Status lifecycle**: every ticket starts in `backlog`. All later transitions follow the
`ticket-workflow` skill. Only `project-manager` may set `done`.

| Status slug | Owner |
|---|---|
| `backlog` | `project-manager` |
| `to-do` | `project-manager` (planning) / `assignee` (execution) |
| `in-progress` | current `assignee` |
| `in-review` | assigned reviewer (default `software-architect`) |
| `in-testing` | `qa-automation` / `qa-manual` |
| `blocked` | current `assignee` + `project-manager` |
| `done` | `project-manager` only |

**Note**: the `sprint` field is left as `null`. Sprints are assigned during backlog planning.

**Naming conventions by type:**

| Type | Prefix | Example file |
|------|---------|-------------------|
| Epic | `EPIC-` | `EPIC-001-user-auth.json` |
| Story | `STORY-` | `STORY-001-login-form.json` |
| Task | `TASK-` | `TASK-001-validate-email.json` |
| Subtask | `SUBTASK-` | `SUBTASK-001-unit-tests.json` |

**Ticket types:**

| Type | Description | Parent |
|------|-------------|--------|
| `epic` | Large initiative or theme | `null` |
| `story` | User story | `EPIC-XXX` |
| `task` | Technical task | `STORY-XXX` or `EPIC-XXX` |
| `subtask` | Detailed subtask | `TASK-XXX` |

### Step 3: Sprint Assignment

Sprint assignments are left as `null` during ticket creation. Sprint planning happens separately during backlog planning sessions.

**Guidelines for planning (applied later):**

- **Sprint 0**: Project setup, infrastructure, environment configuration
- **Sprint 1+**: Features and functionality
- Consider dependencies when assigning sprints
- Children can inherit sprint from parent during planning

If the PRD doesn't specify sprint assignments:
- Group related tasks together
- Consider dependencies (tasks that depend on others should be in later sprints)
- Aim for 5-8 tasks per sprint for a typical 2-week sprint

### Step 4: Validate Tasks

Before finalizing:
- Ensure each task is independent and testable
- Verify all acceptance criteria are clear and measurable
- Check that dependencies are correctly identified
- Confirm sprint assignments respect task dependencies

## Examples

### Example Epic (no parent)

```json
{
  "id": "EPIC-001",
  "type": "epic",
  "title": "Implement user authentication system",
  "parent": null,
  "sprint": null,
  "priority": "P0",
  "estimatedEffort": 13,
  "status": "backlog",
  "assignee": null,
  "implementedBy": null,
  "reviewedBy": null,
  "testedBy": null,
  "requiresReview": true,
  "resultEvidence": [],
  "createdBy": "project-manager",
  "dependencies": [],
  "description": "Implement a complete user authentication system with login, registration, and password recovery.",
  "acceptanceCriteria": [
    "Users can register with email and password",
    "Users can login with credentials",
    "Password recovery via email",
    "Session management implemented"
  ],
  "technicalNotes": "Use JWT tokens for session management. Follow OWASP security guidelines.",
  "definitionDone": [
    "Code completed and reviewed",
    "Tests passing",
    "Documentation updated",
    "Deployed to staging"
  ],
  "createdAt": "2026-10-22T10:00:00Z",
  "updatedAt": "2026-10-22T10:00:00Z"
}
```

### Example Story (with parent epic)

```json
{
  "id": "STORY-001",
  "type": "story",
  "title": "User login functionality",
  "parent": "EPIC-001",
  "sprint": null,
  "priority": "P0",
  "estimatedEffort": 5,
  "status": "backlog",
  "assignee": null,
  "implementedBy": null,
  "reviewedBy": null,
  "testedBy": null,
  "requiresReview": true,
  "resultEvidence": [],
  "createdBy": "project-manager",
  "dependencies": [],
  "description": "As a user, I want to log in to my account so that I can access my personalized dashboard.",
  "acceptanceCriteria": [
    "Login form validates email format",
    "Invalid credentials show error message",
    "Successful login redirects to dashboard",
    "Remember me option works"
  ],
  "technicalNotes": "Integrate with authentication service created in TASK-001.",
  "definitionDone": [
    "Code completed and reviewed",
    "Tests passing",
    "Documentation updated",
    "Deployed to staging"
  ],
  "createdAt": "2026-10-22T10:00:00Z",
  "updatedAt": "2026-10-22T10:00:00Z"
}
```

### Example Task (with parent story)

```json
{
  "id": "TASK-001",
  "type": "task",
  "title": "Create login form component",
  "parent": "STORY-001",
  "sprint": null,
  "priority": "P0",
  "estimatedEffort": 3,
  "status": "backlog",
  "assignee": null,
  "implementedBy": null,
  "reviewedBy": null,
  "testedBy": null,
  "requiresReview": true,
  "resultEvidence": [],
  "createdBy": "project-manager",
  "dependencies": [],
  "description": "Create a React login form component with validation and error handling.",
  "acceptanceCriteria": [
    "Form has email and password fields",
    "Client-side validation implemented",
    "Loading state shown during API call",
    "Error messages display correctly"
  ],
  "technicalNotes": "Use Formik for form management and Yup for validation.",
  "definitionDone": [
    "Code completed and reviewed",
    "Tests passing",
    "Documentation updated",
    "Deployed to staging"
  ],
  "createdAt": "2026-10-22T10:00:00Z",
  "updatedAt": "2026-10-22T10:00:00Z"
}
```

## Troubleshooting

### Issue: Unclear requirements in PRD
**Solution**: Create a TASK-000 for requirements clarification and add it to Sprint 1

### Issue: Task too large for one sprint
**Solution**: Break down the task into smaller, independent subtasks

### Issue: Missing dependencies
**Solution**: Review task relationships and add dependency markers

## Best Practices

1. **Keep hierarchy clear**: Maximum 4 levels (Epic → Story → Task → Subtask)
2. **Use parent field**: Always assign parent for traceability
3. **Epics have no parent**: Epics always have `parent: null`
4. **Subtasks point to direct parent**: Subtasks always point to TASK, not STORY
5. **Consistent IDs**: Use sequential numbers per ticket type
6. **Sprint inheritance**: Children inherit sprint from parent if not explicitly assigned
