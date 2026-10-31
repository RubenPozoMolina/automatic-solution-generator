---
name: visual-qa
description: Manual and visual QA of web UIs in a containerized browser - screenshots, layout defect detection (clipped fields, scrollbars inside components) and end-to-end interaction checks
license: MIT
compatibility: opencode
metadata:
  audience: qa-manual
  workflow: testing
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Skill: visual-qa

## What I Do

I let the QA agent **look at the real application the way a user does**: open it in a real browser
that runs **inside a Docker container**, interact with it, take screenshots, inspect them and
detect layout problems that code review and unit tests never find.

All browsers and servers run in containers (see the `docker-test-runner` skill). Never use a
browser installed on the host.

## When to Use Me

- A ticket in `in-testing` whose work is a user interface (the orchestrator assigns it to
  `qa-manual`).
- Any acceptance criterion about what the user sees or does: forms, editors, diagrams, drag and
  drop, relationships between entities, responsive layout.

## Step 1 - Build the Browser Image Once

`$SKILL_DIR` is the base directory of this skill (the `visual-qa` folder that contains this file;
the skill loader reports it when the skill is loaded). You work inside the project directory, so
always use that absolute path.

```bash
docker image inspect asg-visual-qa:1.49.1 >/dev/null 2>&1 \
  || docker build -t asg-visual-qa:1.49.1 "$SKILL_DIR"
```

The image is the official Playwright image plus the `playwright` Python package. If `$SKILL_DIR`
cannot be found, create the same `Dockerfile` (two lines: `FROM
mcr.microsoft.com/playwright/python:v1.49.1-noble` and `RUN pip install playwright==1.49.1`) and
save `scripts/visual_check.py` under `qa-tools/` in the project.

## Step 2 - Serve the Application in a Container

Follow the *Serving the Application* recipe of `docker-test-runner`: a private network, the
unprivileged nginx image on port 8080, nothing published on the host.

## Step 3 - Automatic Layout Check

`scripts/visual_check.py` opens a URL at several viewports (default 1280x720, 1920x1080,
768x1024), takes full-page screenshots and reports layout defects. It exits with code 1 when it
finds any defect or console error.

```bash
docker run --rm --network "$NETWORK" --init --cap-drop ALL \
  --security-opt no-new-privileges --shm-size 1g --user "$(id -u):$(id -g)" \
  -v "$SKILL_DIR/scripts":/skill:ro \
  -v "$PROJECT_DIR/qa-artifacts":/artifacts \
  asg-visual-qa:1.49.1 \
  python /skill/visual_check.py "http://app-$TICKET_ID:8080/" --output /artifacts/$TICKET_ID
```

Defect types in `visual-report.json`:

| Type | Meaning |
|---|---|
| `clipped-by-container` | A control (input, select, button, link) is partly hidden by a parent with `overflow` hidden/auto/scroll |
| `horizontal-scroll-inside-component` | A card/panel has its own horizontal scrollbar: its content does not fit |
| `text-truncated` | The text of an input/textarea is wider than the field |
| `select-text-truncated` | The selected option of a `<select>` does not fit (for example `INTEGER` cut off) |
| `outside-viewport` | A control lies outside the visible window |
| `page-horizontal-scroll` | The whole page scrolls horizontally |

**Any defect fails the visual criterion.** Do not mark a ticket `passed` while the report lists
defects: set `result: failed` and describe each defect (type, element, numbers) in
`resultEvidence`. The developer must fix the CSS (for example size cards to their content with
`width: max-content`, `min-width`, `flex-wrap`, or remove `overflow` on the card) instead of
hiding the symptom.

## Step 4 - Look at the Screenshots

Open the PNG files from `qa-artifacts/` and **actually inspect them**. The automatic check does
not replace your eyes. Verify:

- [ ] Every field of every component is completely visible: names, types, flags and action
      buttons are not cut off, overlapped or hidden behind scrollbars.
- [ ] Text is readable and not truncated; labels are not overlapped.
- [ ] Buttons, toolbars and mode indicators are fully visible and not wrapped awkwardly.
- [ ] Spacing, alignment and colors are consistent; nothing overlaps.
- [ ] The layout still works at the other viewports.
- [ ] Empty, loading and error states look right.

## Step 5 - Exercise the Interactions

Write a short Playwright script (Python, `asg-visual-qa` image) for the flows in the acceptance
criteria and **assert on the visible result**, then take a screenshot after each key step. Reuse
`LayoutInspector` from `visual_check.py` by mounting `/skill` and adding it to `PYTHONPATH`.

```python
import sys
sys.path.insert(0, "/skill")
from playwright.sync_api import sync_playwright
from visual_check import LayoutInspector

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    inspector = LayoutInspector(page)
    page.goto("http://app-TICKET:8080/", wait_until="networkidle")

    page.get_by_role("button", name="Add Table").click()
    page.get_by_role("button", name="Add Table").click()
    # ... create columns, enter relationship mode, click the two columns ...
    page.screenshot(path="/artifacts/after-relationship.png", full_page=True)

    assert page.locator("svg line, svg path.relationship").count() >= 1, "no relationship line"
    assert not inspector.find_layout_defects(), inspector.find_layout_defects()
    assert not inspector.console_errors, inspector.console_errors
    browser.close()
```

Adapt the selectors to the real DOM (read the HTML/JS first). Typical flows to cover:

- Create, rename, move (drag), delete and resize components; undo/redo.
- **Relationships between entities**: enter relationship mode, pick the two endpoints, and verify
  that a connector is drawn **between the right endpoints**, follows the components when they are
  dragged, shows the correct cardinality label, persists after export/import or reload, and
  disappears when either endpoint is deleted. A relationship feature that only changes a mode
  label without drawing anything **fails**.
- Forms and inline editors: long names, special characters, empty values, duplicates.
- Persistence: reload the page and verify the state is restored.
- Keyboard use and focus visibility (basic accessibility).

## Step 6 - Report

In the ticket write:

- `result`: `passed` / `passed-with-skips` only when every executable criterion is verified and
  the layout report is clean; `failed` otherwise; `blocked` when the environment cannot run.
- `resultEvidence`: the commands and image tags, defect list (or "0 layout defects"), paths of
  the screenshots in `qa-artifacts/`, the interactions verified, and bugs found with steps to
  reproduce (see the bug template of the `qa-manual` agent).

## Step 7 - Clean Up

```bash
docker rm -f "app-$TICKET_ID"
docker network rm "qa-$TICKET_ID"
```

`qa-artifacts/` is git-ignored; refer to the files from the evidence but do not commit them.
