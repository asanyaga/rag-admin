# Claude Code Workflow Guide

Based on Anthropic's official best practices and community learnings.

## Core Principles

1. **CLAUDE.md should be concise** — LLMs follow ~150 instructions reliably; Claude Code's system prompt uses ~50. Every line competes for attention.

2. **Use `/clear` frequently** — Context degradation is the primary failure mode. Clear between tasks.

3. **Plan before coding** — Ask Claude to explore and plan first. Explicitly say "don't write code yet."

4. **Use thinking keywords** — "think" < "think hard" < "think harder" < "ultrathink" for progressively deeper reasoning.

5. **Course correct early** — Escape to interrupt, double-Escape to go back and try differently.

---

## Session Types

| Type | When | Key Prompt |
|------|------|------------|
| **Explore** | Understanding code, learning | "Explain X. I'm learning [tech]. Don't code yet." |
| **Plan** | Before non-trivial work | `/plan` or "Plan how to [goal]. Think hard. Wait for approval." |
| **Implement** | After plan approval | "Implement your plan. Explain key design decisions." |
| **Fix/Debug** | Something broken | "Help me debug [issue]. Explain the root cause before fixing." |

### Learning Mode Prefix

You know Python/React—add this to understand *why* things are done:

```
Explain your reasoning and any design decisions as you work.
```

This gets you: why this pattern over alternatives, trade-offs considered, how it fits the architecture.

---

## Session Pattern

```
/clear                              ← Start fresh
"Read [files]. Don't code yet."     ← Explore
"Think hard. Make a plan."          ← Plan
[Review plan, ask questions]        ← Verify
"Implement your plan."              ← Code
"Run tests. Fix any failures."      ← Validate
/commit                             ← Save
/clear                              ← Reset for next task
```

---

## Dual Tracking

Track work two ways:

1. **Tasks** (`/tasks`) — Work items that persist across sessions
2. **Session Log** (`docs/session-log.md`) — Learning, context, summaries

### Session Log Entry Format

```markdown
## YYYY-MM-DD: [Brief Title]
**Goal:** What you wanted to accomplish
**Outcome:** What actually happened
**Learned:** Key concepts or patterns
**Tasks:** #1, #3 (completed task IDs)
**Next:** What to do next session
```

---

## Post-Session Checklist

Before ending a substantive session:

```
Session wrap-up:

1. **Summary**: What did we accomplish?
2. **Learning Points**: What concepts or patterns did we use?
3. **Task Update**: Mark completed tasks, note what's next
4. **Doc Review**: Do any of these need updates?
   - claude.md
   - docs/planning/[relevant files]
   - workflow-guide.md
5. **Session Log Entry**: Format for docs/session-log.md
```

### Pre-Commit Review

```
Before we commit, review the changes and:
1. Explain what this code does (for my learning)
2. Check for any issues or improvements
3. Suggest a clear commit message
```

### Document Review (after features)

```
Review these docs for accuracy after today's changes:
- claude.md
- docs/planning/[relevant-prd].md
- workflow-guide.md
Suggest specific updates if needed.
```

---

## Prompting by Task

### Understanding a Pattern
```
Explain why [pattern/approach] is used in this codebase.
Show me examples and explain the trade-offs.
```

### New Feature
```
/plan
I want to add [feature].
Read the relevant PRD in docs/planning/ and explain your approach.
```
Then: "Implement. Explain key design decisions."

### Fixing a Bug
```
I have an issue: [describe problem]
Error: [paste error]

Find the root cause and explain why it's happening before fixing.
```

### Updating Existing Code
```
I need to modify [feature/file].
Read the current code, explain the current design, then plan changes.
```

### Code Review
```
Review this code: [file or paste]
Focus on: patterns, potential issues, and why improvements would help.
```

### Unfamiliar Tech
```
I know Python/React but not [TypeScript generics / async patterns / etc].
Explain how this code works and why it's written this way.
```

---

## Key Commands

| Command | Purpose |
|---------|---------|
| `/clear` | Reset context between tasks |
| `/plan` | Enter plan mode for non-trivial features |
| `/commit` | Smart commit with message |
| `/tasks` | View/manage task list |
| `/review-pr` | PR review |
| `/frontend-design` | UI component generation (uses shadcn) |
| `#` | Add instruction to CLAUDE.md mid-session |
| Escape | Interrupt current operation |
| Escape×2 | Go back in history, try different approach |

---

## Quick Reference

| What You Want | How |
|--------------|-----|
| New feature | `/plan` → describe goal → implement after approval |
| Fix a bug | "Debug [issue]. Explain root cause before fixing." |
| Understand code | "Explain why [file/pattern] is designed this way." |
| End session | "Session wrap-up" (triggers checklist) |
| Commit | `/commit` |
| UI component | `/frontend-design` or search shadcn registry |
| Track work | `/tasks` |
| Fresh start | `/clear` |

---

## When Things Go Wrong

**Claude goes in circles:**
```
Stop. You've tried this approach twice.
Let's step back. What's the actual error? Show me the relevant code.
```

**Context seems degraded:**
```
/clear
```
Then re-orient with specific file references.

**Wrong approach taken:**
- Press Escape to stop
- Press Escape twice to go back in history
- Edit your prompt and try again

---

## File References

- **Specs:** `docs/planning/` — Always read before implementing
- **Session guide:** `docs/planning/CLAUDE-SESSION-GUIDE.md` — Resuming work
- **Session log:** `docs/session-log.md` — Learning and context tracking

## What NOT to Put in CLAUDE.md

- Exhaustive command lists (Claude can run `--help`)
- Detailed style guides (use a linter instead)
- Instructions for edge cases (handle when they arise)
- Anything that isn't universally applicable

## Evolving Your CLAUDE.md

Use `#` during sessions to add learnings:

```
# When writing tests, always use pytest fixtures from conftest.py
```

Claude adds this to CLAUDE.md. Periodically review and prune what isn't working.
