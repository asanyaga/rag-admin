---
name: implement
description: "Start implementing a feature, fix, or chore against a GitHub issue. Reads the issue, finds relevant specs, creates a branch, implements with tests, verifies, and creates a PR."
argument-hint: "[issue-url-or-number]"
disable-model-invocation: true
---

You are starting the implementation workflow for a GitHub issue.

**Input:** $ARGUMENTS (GitHub issue URL, issue number,task or empty)

## Step 1: Resolve the issue

- If $ARGUMENTS is empty, ask the user what they want to implement. If there's no GitHub issue yet, suggest creating one and wait for confirmation.
- If $ARGUMENTS is a task, plan with user to determine if it is a feature, fix or chore and create a gihub issue and spec if needed.
- If $ARGUMENTS is a number, fetch the issue from the current repo using `gh issue view <number>`.
- If $ARGUMENTS is a URL, fetch it with `gh issue view <url>`.
- Read the issue title, body, and labels.

## Step 2: Find the spec

- Search `docs/planning/` and `docs/specs/` for files related to the issue topic.
- If a relevant spec exists, read it.
- If no spec exists, note this and proceed — not all work needs a spec.

## Step 3: Plan (for non-trivial work)

- If the issue involves changes to 3+ files or touches both frontend and backend, enter Plan mode and outline:
  - Files to create/modify
  - Key design decisions
  - Test approach
- Present the plan to the user and wait for alignment before proceeding.
- For simple changes (1-2 files, straightforward), skip planning and proceed.

## Step 4: Create a branch

- Branch from main: `feat/issue-<number>-<short-description>` (features), `fix/issue-<number>-<short-description>` (bugs), `chore/issue-<number>-<short-description>` (devops/maintenance)
- If a branch already exists for this issue, switch to it instead.

## Step 5: Implement

- Create tasks to track progress.
- For bugs: write a failing test first, confirm it fails, then fix.
- For features: write tests alongside implementation.
- Follow project patterns (see claude.md).
- Update tasks as you complete them.

## Step 6: Verify

- Launch the change-verifier agent to run lint/build/type checks.
- Launch the regression-runner agent to run the full test suites.
- Run both agents in parallel.
- Fix any failures before proceeding.

## Step 7: Create PR

- Create a PR linking to the issue using `gh pr create`.
- Include a summary of changes and test plan.
- Tell the user the PR is ready for review.
- Do NOT merge — wait for the user.

## Step 8: Cleanup (after user merges)

- Only when the user confirms the PR is merged:
  - Switch to main and pull
  - Delete the local and remote feature branch
