---
name: docker-image-manager
description: Create, build, pull, list, and manage Docker images for testing, development, and deployment workflows
license: MIT
compatibility: opencode
metadata:
  audience: devops, qa-automation
  workflow: docker
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# ⚠️ IMPORTANT: Blocking Workflow for QA Automation

## When QA Cannot Complete Testing

If you are **qa-automation** and you encounter an environment issue that prevents you from completing testing (e.g., lack of Docker container environment, browser automation not available, test infrastructure missing):

### DO NOT STALL THE TICKET

Instead, follow this **Blocked Protocol** from the ticket-workflow skill:

### Step 1: Mark Current Ticket as BLOCKED

Update your ticket JSON with:
```json
{
  "status": "blocked",
  "assignee": "qa-automation",
  "statusHistory": [
    {
      "from": "in-testing",
      "to": "blocked",
      "actor": "qa-automation",
      "timestamp": "2026-10-24T00:00:00Z",
      "reason": "Cannot complete testing without Docker environment. Creating blocker ticket for DevOps to create testable Docker image.",
      "evidence": ["error:browser-not-available", "error:nodejs-runtime-missing"]
    }
  ]
}
```

### Step 2: Create A BLOCKER TICKET

Create a new task JSON file in the tasks directory:

```json
{
  "id": "TASK-XXX",
  "type": "task",
  "title": "Create Docker Image for Testing [BLOCKER]",
  "parent": "STORY-XXX",  // The story this blocks
  "sprint": current_sprint,
  "priority": "P0",
  "estimatedEffort": 3,
  "status": "backlog",
  "assignee": null,
  "createdBy": "qa-automation",
  "description": "QA cannot verify implementation without Docker environment. DevOps must create a Docker image that can be run for testing purposes. This is a blocker for testing TASK-XXX.",
  "acceptanceCriteria": [
    "Dockerfile created at project root",
    "Image builds successfully with: docker build -t app:test .",
    "Container starts with: docker run -p 8080:80 app:test",
    "Application is accessible inside container",
    "Documentation in README with run instructions"
  ],
  "technicalNotes": "Use multi-stage build for optimized image. Prefer alpine or slim base images. Ensure non-root user for security.",
  "definitionDone": [
    "Code completed and reviewed",
    "Tests passing",
    "Documentation updated",
    "Deployed to staging"
  ],
  "createdAt": "2026-10-24T00:00:00Z",
  "updatedAt": "2026-10-24T00:00:00Z",
  "statusHistory": [
    {
      "from": null,
      "to": "backlog",
      "actor": "qa-automation",
      "timestamp": "2026-10-24T00:00:00Z",
      "reason": "Blocker ticket created by QA to enable testing",
      "evidence": []
    }
  ]
}
```

### Step 3: Add Dependency to Original Ticket

Update the original ticket's dependencies array:
```json
{
  "dependencies": ["TASK-XXX"]  // Add the blocker ticket ID
}
```

### Step 4: Notify Project Manager

The `project-manager` will:
1. Assign the blocker ticket to `devops-engineer`
2. When blocker is complete, move original ticket back to `in-testing`
3. Continue testing

### Step 5: DevOps Completes Blocker

When `devops-engineer` completes the Docker image:
1. Update blocker ticket status to `done`
2. Add evidence: Docker image ID, run commands, test results
3. Project manager will unblock original ticket

## Why This Matters

❌ **WRONG** - Stalling in `in-testing` with no action (causes sprint blocks)  
✅ **RIGHT** - Create blocker ticket and move to `blocked` status

This ensures:
- Clear ownership of what's blocking
- Visible dependency tracking
- Sprint velocity is maintained
- DevOps knows exactly what's needed

# Skill: docker-image-manager

## What I Do

I provide comprehensive Docker image management capabilities including:
- **Pulling images** from Docker Hub and private registries
- **Building images** from Dockerfiles with proper build arguments
- **Creating multi-stage builds** for optimized production images
- **Listing and searching** available images
- **Tagging and pushing** images to registries
- **Running containers** for testing and validation
- **Cleaning up** unused images and containers

## When to Use Me

Use me whenever you need to:
- Set up test environments with specific base images
- Build application images for deployment
- Validate Dockerfile configurations
- Create reproducible test environments
- Push images to registries for CI/CD pipelines
- Clean up Docker resources

## Prerequisites

Before using this skill, ensure:
- Docker is installed and running (`docker --version`)
- You have permission to pull/push to required registries
- Sufficient disk space is available (`df -h`)
- Network connectivity to Docker registries

## Step-by-Step Instructions

### 1. Check Docker Status

```bash
docker --version
docker info
docker image ls
```

### 2. Pull Base Images

To pull a specific base image:
```bash
# Latest version
docker pull python:3.11-slim

# Specific version
docker pull node:18-alpine

# Specific registry
docker pull registry.example.com/my-app:latest
```

### 3. Build Images from Dockerfile

Basic build:
```bash
docker build -t my-app:1.0.0 .
```

With build arguments:
```bash
docker build \
  --build-arg NODE_ENV=production \
  --build-arg APP_VERSION=1.0.0 \
  -t my-app:1.0.0 \
  -f Dockerfile.prod \
  .
```

Multi-platform build:
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t my-app:1.0.0 \
  --push \
  .
```

### 4. Tag and Push Images

```bash
# Tag for registry
docker tag my-app:1.0.0 registry.example.com/my-app:1.0.0

# Login to registry
docker login registry.example.com

# Push image
docker push registry.example.com/my-app:1.0.0
```

### 5. Run Containers for Testing

```bash
# Run with port mapping
docker run -d \
  --name my-app-test \
  -p 8080:80 \
  -e NODE_ENV=test \
  my-app:1.0.0

# Run with volume mount
docker run -d \
  --name my-app-test \
  -v $(pwd)/test-data:/data \
  my-app:1.0.0

# Run interactively
docker run -it --rm my-app:1.0.0 /bin/bash
```

### 6. Verify Image Contents

```bash
# Inspect image metadata
docker image inspect my-app:1.0.0

# List layers
docker history my-app:1.0.0

# Run shell in container
docker run --rm -it my-app:1.0.0 /bin/sh
```

### 7. Cleanup

```bash
# Remove unused images
docker image prune -f

# Remove all unused images (not just dangling)
docker image prune -a -f

# Remove container
docker rm -f my-app-test

# Remove all unused containers, networks, and images
docker system prune -a -f --volumes
```

## Common Use Cases

### DevOps: Production Image Creation

```bash
docker build \
  --build-arg NODE_ENV=production \
  --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
  --build-arg VCS_REF=$(git rev-parse --short HEAD) \
  -t my-app:${VERSION:-latest} \
  -f Dockerfile.prod \
  --target production \
  .

docker tag my-app:${VERSION:-latest} registry.example.com/my-app:${VERSION:-latest}
docker push registry.example.com/my-app:${VERSION:-latest}
```

### QA Automation: Test Environment Setup

```bash
# Create test container with specific dependencies
docker run -d \
  --name test-runner \
  -e CI=true \
  -e TEST_TIMEOUT=30000 \
  -v $(pwd)/test-results:/test-results \
  -v $(pwd)/coverage:/coverage \
  node:18-alpine \
  /bin/sh -c "npm install && npm test"

# Check test results
docker logs test-runner
docker cp test-runner:/test-results ./test-results-local
```

### Development: Local Image Testing

```bash
# Build development image
docker build -t my-app:dev .

# Run with hot-reload support
docker run -d \
  -p 3000:3000 \
  -v $(pwd):/app \
  -v /app/node_modules \
  -e NODE_ENV=development \
  -e WATCH_MODE=true \
  my-app:dev
```

## Best Practices

1. **Use specific tags**: Always use specific version tags (e.g., `python:3.11-slim`) instead of `latest`
2. **Multi-stage builds**: Use multi-stage Dockerfiles to reduce final image size
3. **Minimal base images**: Prefer `alpine` or `-slim` variants when possible
4. **Non-root users**: Run containers as non-root users for security
5. **Environment variables**: Use build arguments and environment variables for configuration
6. **Layer caching**: Order Dockerfile instructions from least to most frequently changing
7. **Clean regularly**: Prune unused images to prevent disk space issues

## Troubleshooting

### Build fails with "pull access denied"
```bash
# Login to registry
docker login registry.example.com
```

### Image size too large
```bash
# Use multi-stage build
# Use --squash option (experimental)
# Choose smaller base image
```

### Container exits immediately
```bash
# Check logs
docker logs <container-name>

# Run interactively to debug
docker run -it <image-name> /bin/bash
```

### Permission denied when mounting volumes
```bash
# Ensure correct file permissions
chmod -R 755 $(pwd)/test-data
```

## Success Criteria

✅ Pull: Image downloaded successfully and listed in `docker images`  
✅ Build: Container builds without errors and starts correctly  
✅ Tag/Push: Image tagged and pushed to registry with correct metadata  
✅ Run: Container starts, runs, and exits as expected  
✅ Cleanup: Unused resources removed without affecting active containers  

## Common Dockerfile Patterns

### Multi-Stage Build for Node.js
```dockerfile
# Stage 1: Build
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Production
FROM node:18-alpine AS production
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./
USER node
EXPOSE 3000
CMD ["node", "dist/index.js"]
```

### Multi-Stage Build for Python
```dockerfile
# Stage 1: Build
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --user virtualenv
ENV PATH=/root/.local/bin:$PATH
RUN virtualenv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Stage 2: Production
FROM python:3.11-slim AS production
WORKDIR /app
RUN groupadd -r app && useradd -r -g app app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/dist ./dist
ENV PATH=/opt/venv/bin:$PATH
USER app
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "dist.main:app"]
```

---

**Note**: This skill requires proper Docker installation and appropriate permissions. Always verify Docker is running and accessible before executing commands.
