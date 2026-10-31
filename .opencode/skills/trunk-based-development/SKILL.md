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
repository: everybody integrates **small, frequent commits into a single trunk branch** and
pushes them to the remote, instead of keeping long-lived feature branches.

The repository URL and the trunk branch name are given in the prompt (`repository` and
`repository_branch` of the generator configuration; the default trunk is `main`).
The orchestrator has already run `git init`, configured the `origin` remote and created a
`.gitignore`; you only commit and push.

## Rules

1. **One trunk.** Work directly on the trunk branch, or on a **short-lived branch (less than one
   day, one ticket, one developer)** that is merged back and deleted the same day. Never keep
   long-lived branches.
2. **Small commits.** One logical change per commit; the trunk must always build and its tests must
   pass (run them in containers, see `docker-test-runner`).
3. **Integrate often.** Pull, then push at least once per ticket phase. Do not accumulate unpushed
   work.
4. **Never push a broken trunk.** Run the relevant containerized tests before pushing. If they
   fail, fix them first; do not push and do not disable the tests.
5. **Unfinished features go behind a flag**, not behind a branch (feature flags or a disabled
   entry point), so incomplete work can still be integrated.
6. **No force pushes** on the trunk (`--force` is forbidden). Resolve conflicts with a rebase.
7. **Never commit** secrets, `node_modules/`, logs, `*.pid`, binaries (`*.deb`) or QA artifacts
   (`qa-artifacts/`, `test-results/`).
8. **Reviews are fast and small.** The `in-review` phase reviews the commit(s) already on the trunk
   (or the short-lived branch); the reviewer requests changes as follow-up commits.

## Workflow

Run these commands from the project directory (never run `git` against the generator repository):

```bash
# 1. start from the latest trunk
git fetch origin
git checkout main                    # use the trunk name from the prompt
git pull --rebase origin main        # skip when the remote has no commits yet

# 2. work in small steps, commit each one
git add --all
git commit -m "TASK-012: validate column names in the table editor"

# 3. integrate and publish
git pull --rebase origin main
git push origin main                 # first push: git push --set-upstream origin main
```

### Commit message format

```
<TICKET-ID>: <imperative summary, max 72 characters>

<optional body: what and why>
```

Examples: `TASK-004: add draggable table headers`, `TASK-021: fix clipped column inputs`.

### Short-lived branch (only when a change cannot land in one commit)

```bash
git checkout -b task-012-column-validation
# ...small commits...
git fetch origin && git rebase origin/main
git checkout main && git merge --ff-only task-012-column-validation
git push origin main
git branch -d task-012-column-validation
```

### Conflicts

```bash
git pull --rebase origin main
# edit the conflicting files, keep both intentions
git add <files> && git rebase --continue
# if it cannot be resolved cleanly: git rebase --abort, and report `blocked` with the reason
```

## Automatic Publication

The orchestrator also commits and pushes pending project changes to the trunk **after each
completed ticket phase** as a safety net. This does not replace your commits: commit with a
meaningful message yourself so the history stays readable, and record the commit hashes in
`resultEvidence` (for example `commit:3f2a1c9`).

## When Pushing Fails

- No network or no credentials for the remote: do **not** retry in a loop and do **not** change the
  remote URL. Keep the commits locally, mention `push-failed:<reason>` in `resultEvidence` and
  continue; the orchestrator will retry after the next phase.
- Rejected push (non-fast-forward): `git pull --rebase origin <trunk>` and push again.

## Checklist Before Finishing a Phase

- [ ] Tests ran in Docker and passed
- [ ] Commits are small, with `TICKET-ID:` prefix
- [ ] `git pull --rebase` and `git push` done (or `push-failed` documented)
- [ ] No secrets, logs, binaries or artifacts committed
- [ ] Commit hashes listed in `resultEvidence`
