---
name: git-pr
description: Workflow for creating feature branches, verifying changes with make test, committing, pushing to GitHub, and opening pull requests using the gh CLI.
---

# Git & GitHub Pull Request Workflow

Use this skill when preparing code changes, committing work, pushing branches to GitHub, and opening Pull Requests (PRs).

## Prerequisites

- Ensure the working directory is clean or only contains the intended changes (`git status`).
- Ensure `gh` CLI is available and authenticated (`gh auth status`).

## Step-by-Step Procedure

### 1. Create and Switch to a Feature Branch

Ensure you are branching off the latest `main`:
```bash
git checkout main
git pull origin main
git checkout -b <branch_name>
```

**Naming Conventions**:
- Features: `feature/<short-description>` (e.g. `feature/gps-logging`)
- Bug fixes: `fix/<short-description>` (e.g. `fix/ringbuffer-concurrency`)
- Documentation: `docs/<short-description>` (e.g. `docs/add-agents-guidelines`)
- Refactoring: `refactor/<short-description>` (e.g. `refactor/camera-recorder`)

### 2. Verify Changes

Always run the full test and lint suite prior to committing:
```bash
make test
```
Do not proceed if `flake8` or any unit test fails.

### 3. Stage and Commit

Stage only relevant modified or new files:
```bash
git add <files>
git commit -m "<type>: <concise description of what changed>"
```

### 4. Push Feature Branch

Push the branch to the remote repository and set upstream:
```bash
git push -u origin <branch_name>
```

### 5. Create the Pull Request

Create a PR using the GitHub CLI with structured markdown content:
```bash
gh pr create \
  --title "<PR Title>" \
  --body "## Summary
- <Brief bullet points of what this PR does>

## Verification
- Verified by running \`make test\` (flake8 + unit/simulation tests passed cleanly)."
```

### 6. Output PR URL

Retrieve and output the PR link returned by `gh pr create` to the user.
