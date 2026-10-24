---
name: ticket-workflow
description: Controls ticket status transitions, assigns ownership, and enforces sprint, review, testing, blocked, and done rules
license: MIT
compatibility: opencode
metadata:
  audience: all-agents
  workflow: project-management
  opencode/slash: "false"
  opencode/autoinvoke: "true"
---

## What I Do

I define **who owns a ticket in each status** and **who is allowed to change it**. I keep every
ticket moving through a single, auditable lifecycle inside an active sprint.

Canonical status slugs (machine-readable, lowercase):

| Slug | Display name | Accountable owner |
|---|---|---|
| `backlog` | Backlog | `project-manager` |
| `to-do` | To Do | `project-manager` (planning) / `assignee` (execution) |
| `in-progress` | In Progress | current `assignee` |
| `in-review` | In Review | assigned reviewer (default `software-architect`) |
| `in-testing` | In Testing | `qa-automation` / `qa-manual` |
| `blocked` | Blocked | current `assignee` + `project-manager` (unblocking) |
| `done` | Done | `project-manager` |

## When to Use Me

Use me whenever you:

- start, finish, review, test, block, unblock, close, or reopen a ticket
- receive a ticket and need to know whether you are allowed to change its status
- need to create a blocker ticket
- are unsure who the next `assignee` should be

## Golden Rules

1. **One owner at a time.** A ticket has exactly one `assignee` per status.
2. **Only the status owner changes the status.** Never modify a ticket you do not own.
3. **Only `project-manager` sets `done`.** No subagent may close a ticket.
4. **No status change without a history entry.** Update `status`, `assignee`, `updatedAt` and
   append to `statusHistory` in the same operation.
5. **No skipped states**, except `in-progress → in-testing` for non-code work.
6. **Everything happens inside the sprint.** Unverified work is carried over or returned to
   `backlog`; `done` is never set after sprint close.
7. **Blocked keeps ownership.** The original assignee stays responsible while the blocker ticket
   is solved by another agent.

## Orchestrated Runs

When the prompt says the orchestrator applies the transition, the orchestrator owns `status`,
`assignee` and `statusHistory`. In that case the executing agent must **not** edit those fields.
When its phase is finished it writes:

- `result`: `completed`, `blocked`, `changes-requested`, `failed`, `passed` or `done`
- `resultEvidence`: list of evidence (files, commits, test reports)

A phase whose `result` is not written does not count and is repeated in the next sprint.
Reserve your last steps for writing `result` and `resultEvidence`.

## Transition Matrix

| # | From | To | Who may transition | New `assignee` | Gate / artifact |
|---|---|---|---|---|---|
| T1 | `backlog` | `to-do` | `project-manager` (with `product-owner`) | executing agent | sprint, priority, acceptance criteria, dependencies |
| T2 | `to-do` | `in-progress` | current `assignee` | same | start note |
| T3 | `in-progress` | `in-review` | current `assignee` | reviewer (see below) | implementation + self-tests + commit/PR + evidence |
| T4 | `in-progress` | `in-testing` | current `assignee` | `qa-automation` / `qa-manual` | only non-code work; evidence |
| T5 | `in-progress` | `blocked` | current `assignee` | same | blocker reason + blocker ticket |
| T6 | `in-review` | `in-testing` | assigned reviewer | `qa-automation` / `qa-manual` | review approval |
| T7 | `in-review` | `in-progress` | assigned reviewer | original implementer | change requests |
| T8 | `in-testing` | `done` | **only `project-manager`** | none | QA pass + product-owner acceptance + verified evidence |
| T9 | `in-testing` | `in-progress` | QA agent | original implementer | failure evidence; optional bug ticket |
| T10 | `blocked` | `to-do` / `in-progress` | `project-manager` | original assignee | blocker ticket is `done` |
| T11 | any non-done | `backlog` | `project-manager` / `product-owner` | none | sprint rollback or deprioritization |
| T12 | `done` | `in-progress` | `project-manager` | original implementer | regression / invalidated evidence |

## Reviewer Assignment (`in-review`)

The implementer must reassign to a reviewer different from itself:

1. Default: `software-architect`.
2. If the implementer is `software-architect`: senior peer in the same domain
   (`backend-developer`, `web-developer`, or `devops-engineer`).
3. Test tooling: `qa-automation`.
4. No suitable peer: `project-manager` assigns and records the reviewer.

The reviewer must never be the implementer. The reviewer owns the ticket in `in-review` and is the
only agent allowed to move it to `in-testing` or back to `in-progress`.

## Blocked Protocol

1. Set `status: "blocked"` and **keep the same `assignee`**.
2. Create a blocker ticket (`type: task` or `bug`) describing exactly what must be solved.
3. Add the blocker ticket ID to the original ticket's `dependencies`.
4. The `project-manager` assigns the blocker ticket to the agent that can solve it.
5. When the blocker is `done`, the `project-manager` moves the original ticket back to `to-do`
   or `in-progress` and reassigns it to the original assignee.

## Done Gate

`project-manager` may set `done` only when all of the following exist:

- QA has verified the acceptance criteria and attached evidence.
- The `product-owner` has accepted the value / acceptance criteria.
- No regression or open blocker remains.
- The ticket is still inside its sprint.

QA does **not** set `done`. QA records the result, updates the evidence and reassigns the ticket
to `project-manager` while leaving the status in `in-testing`.

In orchestrated runs QA only writes `result: passed` or `result: failed` plus `resultEvidence`;
the orchestrator closes the ticket on `passed` and sends it back to the implementer on `failed`.

## Required Ticket Fields

```json
{
  "status": "in-review",
  "assignee": "software-architect",
  "implementedBy": "backend-developer",
  "reviewedBy": "software-architect",
  "updatedAt": "2026-10-23T15:30:00Z",
  "statusHistory": [
    {
      "from": "in-progress",
      "to": "in-review",
      "actor": "backend-developer",
      "timestamp": "2026-10-23T15:30:00Z",
      "reason": "Implementation complete; unit tests passing",
      "evidence": ["commit:abc123", "test-report:unit-20261023"]
    }
  ]
}
```

## Examples

### Implementer finishes code

```text
backend-developer: in-progress → in-review
assignee: software-architect
history: implementation + tests attached
```

### Reviewer approves

```text
software-architect: in-review → in-testing
assignee: qa-automation
history: review approved
```

### QA passes

```text
qa-automation: status stays in-testing
assignee: project-manager
history: acceptance criteria verified + evidence
```

### Implementer is blocked

```text
backend-developer: in-progress → blocked
assignee: backend-developer (unchanged)
creates TASK-042 "Provision staging DB access"
adds TASK-042 to dependencies
project-manager assigns TASK-042 to devops-engineer
```
