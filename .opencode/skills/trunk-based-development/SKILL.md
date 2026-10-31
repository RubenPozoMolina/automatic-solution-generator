---
name: trunk-based-development
description: Integrate work with trunk-based development (https://trunkbaseddevelopment.com/) and push small commits to the project remote automatically
license: MIT
compatibility: opencode
metadata:
  audience: all-agents
  workflow: version-control
  opencode/slash: "true"
  opencode/autoinvoke: "true"
---

# Skill: trunk-based-development

## What I Do

I apply [trunk-based development](https://trunkbaseddevelopment.com/) to the project
repository: everybody integrates **small, frequent commits into a single trunk branch**, using
**short-lived branches (one per ticket)** that are merged back as soon as the work is done, instead
of keeping long-lived feature branches. Nobody commits or pushes directly to the trunk.

The repository URL and the trunk branch name are given in the prompt. The trunk is the
`repository_branch` of the generator configuration; when it is not configured, the orchestrator
uses the **default branch of the remote repository** if it has one, and `main` otherwise.
The orchestrator has already run `git init`, configured the `origin` remote and created a
`.gitignore` and checked out the short-lived branch `ticket/<TICKET-ID>` of your ticket; you only
commit on it (and push it when asked).

## Rules

1. **One trunk, short-lived branches.** The trunk is the only long-lived branch. Each ticket works
   on its own branch `ticket/<TICKET-ID>` (already checked out for you), which lives only until
   the ticket is `done`. **Never commit or push directly to the trunk** and never create other
   long-lived branches.
2. **Small commits.** One logical change per commit; the trunk must always build and its tests must
   pass (run them in containers, see `docker-test-runner`).
3. **Integrate often.** Commit and push your branch at least once per ticket phase. Do not
   accumulate unpushed work.
4. **Never merge a broken branch.** Run the relevant containerized tests before finishing a phase.
   If they fail, fix them first; do not disable the tests. The branch reaches the trunk only when
   the ticket is `done` (implementation, tests and review passed).
5. **Unfinished features go behind a flag**, not behind a branch (feature flags or a disabled
   entry point), so incomplete work can still be integrated.
6. **No force pushes** (`--force` is forbidden). Resolve conflicts with a rebase.
7. **Never commit** secrets, `node_modules/`, logs, `*.pid`, binaries (`*.deb`) or QA artifacts
   (`qa-artifacts/`, `test-results/`).
8. **Reviews are fast and small.** The `in-review` phase reviews the commit(s) on the ticket
   branch (`git log origin/<trunk>..HEAD`, `git diff origin/<trunk>...HEAD`); the reviewer requests
   changes as follow-up commits on the same branch. Merging into the trunk is done by the
   orchestrator once the ticket is `done`.

## Initial Check: Detect the Default Branch

Before your first commit, check whether the remote already has a default branch, so you never
create a second, unrelated trunk next to it (for example `main` next to an existing `master`):

```bash
git ls-remote --symref origin HEAD   # first line: ref: refs/heads/<default>	HEAD
```

- **No output** (empty remote, or no access): there is no default branch yet. Use the trunk name
  from the prompt.
- **Default branch equals the trunk in the prompt**: continue.
- **Default branch differs from the trunk in the prompt**: do not create or push the prompt's
  trunk branch. Use the remote default branch as trunk in every command below, and mention
  `trunk-mismatch:<default>` in `resultEvidence`. The orchestrator logs a warning when the trunk
  was set explicitly in the configuration and differs from the remote default; in that case the
  prompt is authoritative, so keep its trunk and only report the mismatch.
- Never delete or rename the remote default branch, and never force-push to align histories.

## Workflow

Run these commands from the project directory (never run `git` against the generator repository):

```bash
# 1. check you are on your ticket branch (the orchestrator checked it out)
git branch --show-current            # ticket/TASK-012

# 2. work in small steps, commit each one
git add --all
git commit -m "TASK-012: validate column names in the table editor"

# 3. publish the branch (never the trunk)
git push --set-upstream origin ticket/TASK-012
```

### Commit message format

```
<TICKET-ID>: <imperative summary, max 72 characters>

<optional body: what and why>
```

Examples: `TASK-004: add draggable table headers`, `TASK-021: fix clipped column inputs`.

### Conflicts

```bash
git fetch origin && git rebase origin/<trunk>
# edit the conflicting files, keep both intentions
git add <files> && git rebase --continue
# if it cannot be resolved cleanly: git rebase --abort, and report `blocked` with the reason
```

## Automatic Publication

The orchestrator commits and pushes pending changes of the ticket branch **after each completed
ticket phase** as a safety net. When the ticket reaches `done` it rebases the branch onto the
latest trunk, fast-forwards the trunk to it (linear history), pushes the trunk and deletes the
ticket branch. If the rebase has conflicts, the branch stays on the remote and a warning is logged.
This does not replace your commits: commit with a meaningful message yourself so the history stays
readable, and record the commit hashes in `resultEvidence` (for example `commit:3f2a1c9`).

## When Pushing Fails

- No network or no credentials for the remote: do **not** retry in a loop and do **not** change the
  remote URL. Keep the commits locally, mention `push-failed:<reason>` in `resultEvidence` and
  continue; the orchestrator will retry after the next phase.
- Rejected push of your ticket branch (non-fast-forward): `git pull --rebase origin ticket/<ID>`
  and push again.

## Checklist Before Finishing a Phase

- [ ] Remote default branch checked and the trunk matches it (or the mismatch is documented)
- [ ] Tests ran in Docker and passed
- [ ] Commits are small, with `TICKET-ID:` prefix
- [ ] Work committed on the ticket branch and pushed (or `push-failed` documented)
- [ ] Nothing committed or pushed directly to the trunk
- [ ] No secrets, logs, binaries or artifacts committed
- [ ] Commit hashes listed in `resultEvidence`
