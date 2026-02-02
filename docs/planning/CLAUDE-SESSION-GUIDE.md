# Claude Code Session Guide

This document explains how to resume work on planned projects with Claude Code in new sessions.

---

## How Claude Code Works Across Sessions

Claude Code does **not** automatically remember previous sessions. Each new session starts fresh. However, you can provide context to help Claude quickly understand where you left off.

### Key Files Claude Can Use

1. **PRD/TRD Documents** - Requirements and technical plans in `docs/planning/`
2. **Task Lists** - Claude Code's built-in task tracking (persists across sessions)
3. **Code Comments** - TODO comments, documentation in the code itself

---

## Resuming the Observability Project

### Quick Start Prompt

Copy and paste this prompt to resume work on observability:

```
I'm implementing observability for this application.

Read the PRD at docs/planning/observability-prd.md and check the current task list with /tasks.

Continue working through the Phase 1 tasks in order. Pick up the next pending task that isn't blocked.
```

### Alternative: Specify a Phase

```
I'm implementing observability. Read docs/planning/observability-prd.md.

I want to work on Phase 2 (Enhancement). Create tasks for Phase 2 if they don't exist, then start implementing.
```

### Alternative: Specific Task

```
I'm implementing observability. Read docs/planning/observability-prd.md.

I want to work on structured JSON logging specifically. Check task #4 and implement it.
```

---

## General Pattern for Resuming Any Project

### 1. Point Claude to Planning Documents

```
Read the PRD/plan at docs/planning/<project-name>.md
```

### 2. Check Existing Tasks

```
Show me the current task list with /tasks
```

Or ask Claude:
```
Check the task list and tell me what's pending and what's completed.
```

### 3. Give Direction

Be specific about what you want to do:

- **Continue where you left off:** "Continue with the next pending task"
- **Work on specific phase:** "Work on Phase 2"
- **Work on specific task:** "Implement task #5"
- **Review progress:** "Summarize what's been completed and what's remaining"

---

## Tips for Effective Sessions

### Do:
- Keep PRD documents updated as requirements change
- Use descriptive task names that explain the goal
- Mark tasks complete when done
- Reference the PRD when asking questions ("Per the PRD, how should we handle X?")

### Don't:
- Assume Claude remembers previous sessions
- Skip providing context - Claude works better with clear direction
- Let task lists get stale - clean up completed/obsolete tasks

---

## Example Prompts for Common Scenarios

### "I forgot where I left off"
```
Read docs/planning/observability-prd.md and check /tasks.
Summarize what's completed and what's next.
```

### "I want to change the approach"
```
Read docs/planning/observability-prd.md.

I want to change from SigNoz to Grafana stack instead.
Update the PRD and create new tasks for the revised approach.
```

### "I need to pause and resume later"
```
Before I go, summarize the current state of the observability implementation
and update the task list with any work in progress.
```

### "Something isn't working"
```
Read docs/planning/observability-prd.md.

I'm having an issue with [describe problem].
The relevant code is in [file path]. Help me debug this.
```

---

## Project-Specific Context

### Observability Project Files

| File | Purpose |
|------|---------|
| `docs/planning/observability-prd.md` | Full PRD and TRD with all phases |
| `docker-compose.observability.yml` | SigNoz stack (created in Phase 1) |
| `backend/app/observability/` | Python OTel modules |
| `frontend/src/observability/` | Frontend error tracking (Phase 2) |

### Phases Overview

- **Phase 1 (Foundation):** Docker stack, auto-instrumentation, basic logging/metrics
- **Phase 2 (Enhancement):** Custom spans, business metrics, frontend errors
- **Phase 3 (Production-Ready):** Alerting, retention, security, dashboards
- **Phase 4 (Advanced):** Full RUM, synthetic monitoring (future)

---

## Command Reference

| Command | Purpose |
|---------|---------|
| `/tasks` | View all tasks |
| `/task <id>` | View specific task details |
| `/clear` | Clear conversation (keeps tasks) |
| `/help` | Show all available commands |
