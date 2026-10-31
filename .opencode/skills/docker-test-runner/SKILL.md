---
name: docker-test-runner
description: Run tests, browsers, builds and application servers exclusively inside isolated, hardened Docker containers instead of on the host
license: MIT
compatibility: opencode
metadata:
  audience: backend-developer, database-expert, web-developer, qa-automation, qa-manual, devops-engineer
  workflow: testing
  opencode/slash: "true"
  opencode/autoinvoke: "true"
---

# Skill: docker-test-runner

## What I Do

I make every test execution happen inside a **Docker container**, never on the host. The
container gives you:

- **Security**: generated code and test dependencies run in an isolated environment.
- **Reproducibility**: the container image provides the exact runtime and browsers the tests need,
  whatever is (or is not) installed on the host.

## Hard Rules

1. **Never run on the host**: `npm test`, `npx playwright|cypress|jest|vitest`, `pytest`,
   `python -m http.server`, `chromium`, `google-chrome`, `firefox`, or any application server.
   Run them with `docker run` / `docker compose run` instead.
2. **Never assume a host browser.** Use a browser that ships with the image
   (see *Images*).
3. **Never weaken the container**: no `--privileged`, no `--network host`, no mounting
   `/var/run/docker.sock`, no mounting `/`, `$HOME`, or `~/.ssh`.
4. **Mount only the project directory** and only what the run needs (read-only whenever possible).
5. **Always clean up** containers and networks you create (`--rm`, `docker network rm`).
6. If Docker itself is unavailable, do not fall back to the host. Follow the *Blocked Protocol*
   of the `docker-image-manager` skill and the `ticket-workflow` skill.

## Images

Pin versions; never use `latest`.

| Need | Image |
|---|---|
| Browser tests with Node (Playwright, Cypress-like flows) | `mcr.microsoft.com/playwright:v1.49.1-noble` |
| Browser tests / visual checks with Python | `mcr.microsoft.com/playwright/python:v1.49.1-noble` |
| Node unit tests | `node:20-alpine` |
| Python unit tests | `python:3.12-slim` |
| PostgreSQL for integration tests (and `psql`) | `postgres:16-alpine` |
| Static web server for the app under test | `nginxinc/nginx-unprivileged:1.27-alpine` (listens on port 8080) |
| Browser checks with the Python helper of `visual-qa` | `asg-visual-qa:1.49.1` (built from the `visual-qa` skill `Dockerfile`) |

The Playwright images include Chromium, Firefox and WebKit, so the browser is always the
expected one. Browser not available for the platform (for example Safari on Linux): mark that
criterion `skipped-unsupported-platform` in `resultEvidence`.

## Hardened Run Template

```bash
docker run --rm \
  --init \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit 512 \
  --memory 2g \
  --shm-size 1g \
  --user "$(id -u):$(id -g)" \
  -v "$PROJECT_DIR":/work:ro \
  -v "$PROJECT_DIR/qa-artifacts":/artifacts \
  -w /work \
  node:20-alpine \
  sh -c "npm ci --ignore-scripts && npm test"
```

Notes:

- Use `-v "$PROJECT_DIR":/work` (read-write) only when the tool must write inside the project
  (for example `node_modules`); prefer a `tmpfs` or copying into the container otherwise.
- Chromium inside the container is launched with `--no-sandbox`; the container is the sandbox.
- Pass `--ipc=host` is **not** needed: `--shm-size 1g` is enough and keeps isolation.
- Give containers a `--name` that includes the ticket ID so you can find and remove them.

## Serving the Application and Testing It from a Browser Container

Use a dedicated network so the app is **never published on the host** and the browser reaches it
by name:

```bash
NETWORK="qa-$TICKET_ID"
docker network create "$NETWORK"

# the official nginx image cannot start with `--cap-drop ALL`; use the unprivileged variant
docker run -d --rm --name "app-$TICKET_ID" --network "$NETWORK" \
  --cap-drop ALL --security-opt no-new-privileges --read-only --tmpfs /tmp \
  -v "$PROJECT_DIR":/usr/share/nginx/html:ro \
  nginxinc/nginx-unprivileged:1.27-alpine

# wait until the app answers
docker run --rm --network "$NETWORK" curlimages/curl:8.10.1 \
  --retry 15 --retry-connrefused --retry-delay 1 -sf "http://app-$TICKET_ID:8080/"

# run the browser tests against http://app-$TICKET_ID:8080/
docker run --rm --network "$NETWORK" --init --cap-drop ALL \
  --security-opt no-new-privileges --shm-size 1g \
  -e BASE_URL="http://app-$TICKET_ID:8080/" \
  -v "$PROJECT_DIR":/work:ro \
  -v "$PROJECT_DIR/qa-artifacts":/artifacts \
  mcr.microsoft.com/playwright:v1.49.1-noble \
  sh -c "cd /work && npx --yes playwright@1.49.1 test"

docker rm -f "app-$TICKET_ID"
docker network rm "$NETWORK"
```

For visual and exploratory checks use the `visual-qa` skill, which builds on this template.

## Dockerfile / docker compose for the Project

When the project has no containerized test setup yet, create one before running tests:

- `Dockerfile` (or `docker/Dockerfile.test`) based on a pinned image from the table above.
- Optional `docker-compose.test.yml` with `app` and `tests` services on a private network.
- A short **"Running the tests"** section in the project `README.md` with the exact
  `docker` commands.

Commit these files so every agent runs the tests the same way.

## Evidence

Always list in `resultEvidence`:

- the exact `docker run` / `docker compose` command and the image tag used,
- the test output summary (passed/failed counts),
- paths of reports and screenshots inside `qa-artifacts/`.

## Cleanup

```bash
docker ps -a --filter "name=-$TICKET_ID" -q | xargs -r docker rm -f
docker network ls --filter "name=qa-$TICKET_ID" -q | xargs -r docker network rm
```

Do not run `docker system prune` on a shared host; remove only what you created.

## Database services (PostgreSQL)

Integration tests that need a database use a **throwaway PostgreSQL container** on a private
network, never a server installed on the host and never an external or real database.

```bash
NET="$TICKET_ID-net"
PGPASSWORD="$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')"   # generated, never committed

docker network create "$NET"
docker run -d --rm --name "$TICKET_ID-postgres" --network "$NET" \
  --cap-drop ALL --cap-add CHOWN --cap-add SETUID --cap-add SETGID --cap-add DAC_OVERRIDE --cap-add FOWNER \
  --security-opt no-new-privileges --pids-limit 256 --memory 1g \
  --tmpfs /var/lib/postgresql/data \
  -e POSTGRES_PASSWORD="$PGPASSWORD" -e POSTGRES_DB=app_test \
  postgres:16-alpine

# wait until it accepts connections
until docker exec "$TICKET_ID-postgres" pg_isready -U postgres -d app_test; do sleep 1; done

# run the tests in another container that joins the same network
docker run --rm --init --cap-drop ALL --security-opt no-new-privileges --network "$NET" \
  --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work -w /work \
  -e DATABASE_URL="postgresql://postgres:$PGPASSWORD@$TICKET_ID-postgres:5432/app_test" \
  node:20-alpine sh -c "npm ci --ignore-scripts && npm test"

# clean up
docker rm -f "$TICKET_ID-postgres"; docker network rm "$NET"
```

Rules:

- The database data lives in `tmpfs`: nothing persists and nothing is mounted from the host.
- Do not publish the database port (`-p`) on the host; containers reach it by name on the private network.
- The password is generated per run and passed through environment variables; never write it to a
  file in the project, to logs, or to `resultEvidence`.
- Seed schemas for tests (tables, composite keys, self-referencing and circular foreign keys) with
  `docker exec -i "$TICKET_ID-postgres" psql -U postgres -d app_test -v ON_ERROR_STOP=1 < seed.sql`
  or from the test code; `psql` runs inside the container only.
- For `docker-compose.test.yml`, declare the `postgres` service with a `healthcheck`
  (`pg_isready`) and no `ports` section.
